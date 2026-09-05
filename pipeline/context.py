"""S4 local context, connected components, identity flags, and history.

This stage deliberately keeps all geographic work in numpy/pandas.  The corpus
is first sorted by each endpoint time, then each candidate uses a
``searchsorted`` time window and a vectorised haversine calculation.  This is
both considerably faster and easier to audit than an all-pairs spatial join.
"""

from __future__ import annotations

from collections import defaultdict
import json

import numpy as np
import pandas as pd

from . import config
from .geo import haversine_km


LOCAL_COLUMNS = [
    "pair_id",
    "local_dark_count_off",
    "local_dark_count_on",
    "local_dark_count",
    "local_unique_vessels",
    "local_same_flag_share",
    "local_sequential_share",
    "neighbours",
]

COMPONENT_COLUMNS = ["pair_id", "component_id", "component_size", "component_class"]


def _empty_local_context() -> pd.DataFrame:
    """An empty result with the public S4 columns.

    Keeping empty-stage behavior explicit makes a partially filtered corpus or
    a no-candidate run safe for the pipeline orchestrator.
    """
    return pd.DataFrame(
        {
            "pair_id": pd.Series(dtype="string"),
            "local_dark_count_off": pd.Series(dtype="int64"),
            "local_dark_count_on": pd.Series(dtype="int64"),
            "local_dark_count": pd.Series(dtype="int64"),
            "local_unique_vessels": pd.Series(dtype="int64"),
            "local_same_flag_share": pd.Series(dtype="Float64"),
            "local_sequential_share": pd.Series(dtype="Float64"),
            "neighbours": pd.Series(dtype="string"),
        }
    )


def _empty_components() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pair_id": pd.Series(dtype="string"),
            "component_id": pd.Series(dtype="string"),
            "component_size": pd.Series(dtype="int64"),
            "component_class": pd.Series(dtype="string"),
        }
    )


def _as_datetime_array(values: pd.Series) -> np.ndarray:
    """Return pandas-3-safe UTC datetimes in a searchsorted-friendly form."""
    return pd.to_datetime(values, utc=True).to_numpy(dtype="datetime64[us]")


def _as_datetime_scalar(value: object) -> np.datetime64:
    return pd.to_datetime([value], utc=True).to_numpy(dtype="datetime64[us]")[0]


def _nonmissing(value: object) -> bool:
    return not pd.isna(value)


def _normalise_mmsi_number(values: pd.Series | np.ndarray | list[object]) -> np.ndarray:
    """Parse MMSIs without ever coercing a missing value to zero."""
    numeric = pd.to_numeric(pd.Series(values), errors="coerce")
    return numeric.to_numpy(dtype=float, na_value=np.nan)


def _sequential_mask(
    left: pd.Series | np.ndarray | list[object],
    right: pd.Series | np.ndarray | list[object],
) -> np.ndarray:
    """Whether MMSI pairs have the same MID and are numerically adjacent."""
    a = _normalise_mmsi_number(left)
    b = _normalise_mmsi_number(right)
    finite = np.isfinite(a) & np.isfinite(b)
    # Integer operations happen only after NaNs have been excluded.
    ai = np.where(finite, a, 0.0).astype(np.int64)
    bi = np.where(finite, b, 0.0).astype(np.int64)
    return finite & ((ai // 1_000_000) == (bi // 1_000_000)) & (np.abs(ai - bi) <= config.SEQ_MMSI_MAX_DELTA)


def _same_nonmissing(left: pd.Series, right: pd.Series) -> np.ndarray:
    """Vectorised equality where missing values never count as a match."""
    l = left.astype("string")
    r = right.astype("string")
    return (l.notna() & r.notna() & l.eq(r)).to_numpy(dtype=bool)


def _candidate_metadata(ev: pd.DataFrame, cands: pd.DataFrame, side: str, field: str, fallback: str) -> pd.Series:
    """Look up event metadata by gap id, falling back to a candidate field.

    The production inputs carry all metadata in ``ev``.  The fallback keeps the
    public functions useful in small tests that provide only candidate columns.
    """
    key = f"gap_id_{side}"
    if key in cands and "gap_id" in ev and field in ev:
        lookup = ev.drop_duplicates("gap_id", keep="first").set_index("gap_id")[field]
        return cands[key].map(lookup)
    if fallback in cands:
        return cands[fallback].copy()
    return pd.Series(pd.NA, index=cands.index)


def _mmsi_valid(values: pd.Series, mids: pd.Series | None = None) -> np.ndarray:
    numbers = _normalise_mmsi_number(values)
    is_integer = np.isfinite(numbers) & (numbers == np.floor(numbers))
    nums = np.where(np.isfinite(numbers), numbers, 0.0).astype(np.int64)
    if mids is None:
        mids_num = nums // 1_000_000
    else:
        raw_mid = _normalise_mmsi_number(mids)
        mids_num = np.where(np.isfinite(raw_mid), raw_mid, -1.0).astype(np.int64)
    return (
        is_integer
        & (nums >= config.MMSI_VALID["lo"])
        & (nums <= config.MMSI_VALID["hi"])
        & (mids_num >= config.MMSI_VALID["mid_lo"])
        & (mids_num <= config.MMSI_VALID["mid_hi"])
    )


def _neighbour_window(
    sorted_events: pd.DataFrame,
    time_values: np.ndarray,
    *,
    centre_time: object,
    centre_lat: object,
    centre_lon: object,
    time_column: str,
    lat_column: str,
    lon_column: str,
    own_gap_ids: tuple[object, object],
) -> pd.DataFrame:
    """Return endpoint neighbours with a distance column, excluding pair nodes."""
    if sorted_events.empty or pd.isna(centre_time) or pd.isna(centre_lat) or pd.isna(centre_lon):
        return sorted_events.iloc[0:0].assign(_distance_km=pd.Series(dtype=float))

    centre = _as_datetime_scalar(centre_time)
    half_window = pd.Timedelta(hours=config.LOCAL_H).to_timedelta64()
    lo = np.searchsorted(time_values, centre - half_window, side="left")
    hi = np.searchsorted(time_values, centre + half_window, side="right")
    window = sorted_events.iloc[lo:hi]
    if window.empty:
        return window.assign(_distance_km=pd.Series(dtype=float))

    distance = haversine_km(
        float(centre_lat),
        float(centre_lon),
        window[lat_column].to_numpy(dtype=float),
        window[lon_column].to_numpy(dtype=float),
    )
    keep = np.isfinite(distance) & (distance <= config.LOCAL_KM)
    if "gap_id" in window:
        keep &= ~window["gap_id"].isin(own_gap_ids).to_numpy(dtype=bool)
    result = window.loc[keep].copy()
    result["_distance_km"] = distance[keep]
    return result


def _json_neighbours(off: pd.DataFrame, t0_a: object) -> str:
    """Encode the nearest shutoff neighbours in the export-safe JSON shape."""
    if off.empty:
        return "[]"

    ordered = off.sort_values(["_distance_km", "gap_id"], kind="stable").head(config.NEIGHBOURS_MAX)
    reference_time = pd.to_datetime(t0_a, utc=True)
    records: list[dict[str, object]] = []
    # ``itertuples`` renames leading-underscore columns, so records are clearer
    # and preserve the explicitly named distance field here.
    for row in ordered[["mmsi", "flag", "t0", "_distance_km"]].to_dict("records"):
        flag = row["flag"]
        timestamp = pd.to_datetime(row["t0"], utc=True)
        records.append(
            {
                "mmsi": str(row["mmsi"]),
                "flag": None if pd.isna(flag) else str(flag),
                "deltaMin": float((timestamp - reference_time) / pd.Timedelta(minutes=1)),
                "distanceKm": float(row["_distance_km"]),
            }
        )
    return json.dumps(records, separators=(",", ":"), allow_nan=False)


def _unique_neighbour_vessels(neighbours: pd.DataFrame) -> pd.DataFrame:
    """One deterministic representative event for each neighbouring MMSI."""
    if neighbours.empty:
        return neighbours.iloc[0:0]
    # Off rows precede on rows when the caller concatenates them, so a vessel
    # observed at both endpoints uses its shutoff metadata consistently.
    return neighbours.dropna(subset=["mmsi"]).drop_duplicates("mmsi", keep="first")


def local_context(ev: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    """Calculate local event density and neighbour evidence for every pair.

    The shutoff and reappearance sets are intentionally formed independently.
    ``local_dark_count`` is the cardinality of their event-id union, while the
    two endpoint counts remain available for auditing and the UI explanation.
    """
    if cands.empty:
        return _empty_local_context()

    required_event_columns = {"gap_id", "t0", "t1", "lat0", "lon0", "lat1", "lon1", "mmsi", "flag"}
    missing = required_event_columns - set(ev.columns)
    if missing:
        raise ValueError(f"local_context requires event columns: {sorted(missing)}")
    required_candidate_columns = {"pair_id", "gap_id_a", "gap_id_b", "t0_a", "flag_a", "flag_b"}
    missing = required_candidate_columns - set(cands.columns)
    if missing:
        raise ValueError(f"local_context requires candidate columns: {sorted(missing)}")

    events_by_id = ev.drop_duplicates("gap_id", keep="first").set_index("gap_id", drop=False)
    off_events = ev.sort_values("t0", kind="stable").reset_index(drop=True)
    on_events = ev.sort_values("t1", kind="stable").reset_index(drop=True)
    off_times = _as_datetime_array(off_events["t0"])
    on_times = _as_datetime_array(on_events["t1"])

    rows: list[dict[str, object]] = []
    for candidate in cands.itertuples(index=False):
        gap_id_a = getattr(candidate, "gap_id_a")
        gap_id_b = getattr(candidate, "gap_id_b")
        if gap_id_a not in events_by_id.index:
            raise ValueError(f"candidate references unknown gap_id_a: {gap_id_a!r}")
        a = events_by_id.loc[gap_id_a]
        own = (gap_id_a, gap_id_b)
        off = _neighbour_window(
            off_events,
            off_times,
            centre_time=a["t0"],
            centre_lat=a["lat0"],
            centre_lon=a["lon0"],
            time_column="t0",
            lat_column="lat0",
            lon_column="lon0",
            own_gap_ids=own,
        )
        on = _neighbour_window(
            on_events,
            on_times,
            centre_time=a["t1"],
            centre_lat=a["lat1"],
            centre_lon=a["lon1"],
            time_column="t1",
            lat_column="lat1",
            lon_column="lon1",
            own_gap_ids=own,
        )

        # The same event can be nearby at both endpoints.  Retain the first
        # occurrence (the shutoff row) before counting event and vessel unions.
        union = pd.concat([off, on], ignore_index=True).drop_duplicates("gap_id", keep="first")
        unique_vessels = _unique_neighbour_vessels(union)
        n_vessels = int(len(unique_vessels))

        partner_flags = {
            str(value)
            for value in (getattr(candidate, "flag_a", pd.NA), getattr(candidate, "flag_b", pd.NA))
            if _nonmissing(value)
        }
        if n_vessels >= config.SAME_FLAG_MIN_VESSELS:
            same_flag = unique_vessels["flag"].astype("string").isin(partner_flags).to_numpy(dtype=bool)
            same_flag_share: object = float(same_flag.mean())
        else:
            same_flag_share = pd.NA

        if n_vessels:
            neighbour_mmsis = unique_vessels["mmsi"]
            a_mmsi = getattr(candidate, "mmsi_a", a["mmsi"])
            b_mmsi = getattr(candidate, "mmsi_b", pd.NA)
            sequential = _sequential_mask(neighbour_mmsis, [a_mmsi] * n_vessels) | _sequential_mask(
                neighbour_mmsis, [b_mmsi] * n_vessels
            )
            sequential_share: object = float(sequential.mean())
        else:
            sequential_share = pd.NA

        rows.append(
            {
                "pair_id": getattr(candidate, "pair_id"),
                "local_dark_count_off": int(len(off)),
                "local_dark_count_on": int(len(on)),
                "local_dark_count": int(len(union)),
                "local_unique_vessels": n_vessels,
                "local_same_flag_share": same_flag_share,
                "local_sequential_share": sequential_share,
                "neighbours": _json_neighbours(off, a["t0"]),
            }
        )

    result = pd.DataFrame(rows, columns=LOCAL_COLUMNS)
    result["pair_id"] = result["pair_id"].astype("string")
    result["local_same_flag_share"] = result["local_same_flag_share"].astype("Float64")
    result["local_sequential_share"] = result["local_sequential_share"].astype("Float64")
    result["neighbours"] = result["neighbours"].astype("string")
    return result


class _UnionFind:
    """Tiny deterministic union-find implementation for candidate event edges."""

    def __init__(self) -> None:
        self.parent: dict[object, object] = {}

    def find(self, item: object) -> object:
        if item not in self.parent:
            self.parent[item] = item
            return item
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            parent = self.parent[item]
            self.parent[item] = root
            item = parent
        return root

    def union(self, left: object, right: object) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        # Stable roots make component ids independent of candidate input order.
        if str(left_root) <= str(right_root):
            self.parent[right_root] = left_root
        else:
            self.parent[left_root] = right_root


def _candidate_same_flag(cands: pd.DataFrame) -> np.ndarray:
    if "same_flag" in cands:
        return cands["same_flag"].fillna(False).to_numpy(dtype=bool)
    if {"flag_a", "flag_b"}.issubset(cands.columns):
        return _same_nonmissing(cands["flag_a"], cands["flag_b"])
    return np.zeros(len(cands), dtype=bool)


def components(cands: pd.DataFrame) -> pd.DataFrame:
    """Assign each operating pair to an event-edge connected component."""
    if cands.empty:
        return _empty_components()
    required = {"pair_id", "gap_id_a", "gap_id_b"}
    missing = required - set(cands.columns)
    if missing:
        raise ValueError(f"components requires candidate columns: {sorted(missing)}")

    uf = _UnionFind()
    for row in cands[["gap_id_a", "gap_id_b"]].itertuples(index=False):
        uf.union(row.gap_id_a, row.gap_id_b)

    nodes_by_root: dict[object, list[object]] = defaultdict(list)
    for node in uf.parent:
        nodes_by_root[uf.find(node)].append(node)
    # Number component ids by their smallest gap id, not by incidental edge order.
    roots = sorted(nodes_by_root, key=lambda root: min(str(node) for node in nodes_by_root[root]))
    component_ids = {root: f"component-{number:04d}" for number, root in enumerate(roots, start=1)}
    sizes = {root: len(nodes) for root, nodes in nodes_by_root.items()}

    root_for_row = np.array([uf.find(value) for value in cands["gap_id_a"]], dtype=object)
    same_flag = _candidate_same_flag(cands)
    if {"mmsi_a", "mmsi_b"}.issubset(cands.columns):
        sequential = _sequential_mask(cands["mmsi_a"], cands["mmsi_b"])
    else:
        sequential = np.zeros(len(cands), dtype=bool)
    local_count = (
        pd.to_numeric(cands["local_dark_count"], errors="coerce").to_numpy(dtype=float)
        if "local_dark_count" in cands
        else np.zeros(len(cands), dtype=float)
    )

    class_by_root: dict[object, str] = {}
    for root in roots:
        mask = root_for_row == root
        size = sizes[root]
        if size == 2:
            component_class = "bilateral"
        elif same_flag[mask].mean() >= 0.8 or sequential[mask].mean() >= 0.5:
            component_class = "fleet_cluster"
        elif size >= config.BLACKOUT_MIN_SIZE or np.any(local_count[mask] >= config.BLACKOUT_LOCAL_COUNT):
            component_class = "regional_blackout"
        else:
            component_class = "unresolved"
        class_by_root[root] = component_class

    result = pd.DataFrame(
        {
            "pair_id": cands["pair_id"].astype("string").to_numpy(),
            "component_id": [component_ids[root] for root in root_for_row],
            "component_size": [sizes[root] for root in root_for_row],
            "component_class": [class_by_root[root] for root in root_for_row],
        }
    )
    return result.astype({"pair_id": "string", "component_id": "string", "component_class": "string"})


def identity_flags(ev: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    """Flag sequential MMSIs, metadata twins, and a pair-level identity status."""
    if cands.empty:
        return pd.DataFrame(
            {
                "pair_id": pd.Series(dtype="string"),
                "sequential_mmsi": pd.Series(dtype=bool),
                "identity_twin": pd.Series(dtype=bool),
                "identity_status": pd.Series(dtype="string"),
            }
        )
    if "pair_id" not in cands:
        raise ValueError("identity_flags requires candidate column: pair_id")

    mmsi_a = _candidate_metadata(ev, cands, "a", "mmsi", "mmsi_a")
    mmsi_b = _candidate_metadata(ev, cands, "b", "mmsi", "mmsi_b")
    mid_a = _candidate_metadata(ev, cands, "a", "mid", "mid_a")
    mid_b = _candidate_metadata(ev, cands, "b", "mid", "mid_b")
    valid_a_source = _candidate_metadata(ev, cands, "a", "mmsi_valid", "mmsi_valid_a")
    valid_b_source = _candidate_metadata(ev, cands, "b", "mmsi_valid", "mmsi_valid_b")
    valid_a = valid_a_source.fillna(pd.Series(_mmsi_valid(mmsi_a, mid_a), index=cands.index)).astype(bool).to_numpy()
    valid_b = valid_b_source.fillna(pd.Series(_mmsi_valid(mmsi_b, mid_b), index=cands.index)).astype(bool).to_numpy()

    class_a = _candidate_metadata(ev, cands, "a", "vessel_class", "class_a")
    class_b = _candidate_metadata(ev, cands, "b", "vessel_class", "class_b")
    flag_a = _candidate_metadata(ev, cands, "a", "flag", "flag_a")
    flag_b = _candidate_metadata(ev, cands, "b", "flag", "flag_b")
    length_a = pd.to_numeric(_candidate_metadata(ev, cands, "a", "length_m", "length_a"), errors="coerce")
    length_b = pd.to_numeric(_candidate_metadata(ev, cands, "b", "length_m", "length_b"), errors="coerce")
    tonnage_a = pd.to_numeric(_candidate_metadata(ev, cands, "a", "tonnage_gt", "tonnage_a"), errors="coerce")
    tonnage_b = pd.to_numeric(_candidate_metadata(ev, cands, "b", "tonnage_gt", "tonnage_b"), errors="coerce")

    sequential = _sequential_mask(mmsi_a, mmsi_b)
    twin = (
        _same_nonmissing(class_a, class_b)
        & _same_nonmissing(flag_a, flag_b)
        & length_a.sub(length_b).abs().lt(config.TWIN_LEN_M).fillna(False).to_numpy(dtype=bool)
        & tonnage_a.sub(tonnage_b).abs().lt(config.TWIN_TON_GT).fillna(False).to_numpy(dtype=bool)
    )
    missing_flag = flag_a.isna().to_numpy(dtype=bool) | flag_b.isna().to_numpy(dtype=bool)
    unresolved = ~valid_a | ~valid_b | missing_flag
    status = np.where(unresolved, "unresolved", np.where(twin, "identity-twin", "resolved"))

    return pd.DataFrame(
        {
            "pair_id": cands["pair_id"].astype("string").to_numpy(),
            "sequential_mmsi": sequential,
            "identity_twin": twin,
            "identity_status": pd.Series(status, dtype="string"),
        }
    )


def _event_durations_hours(ev: pd.DataFrame) -> pd.Series:
    if "gap_hours_exact" in ev:
        return pd.to_numeric(ev["gap_hours_exact"], errors="coerce")
    if {"t0", "t1"}.issubset(ev.columns):
        t0 = pd.to_datetime(ev["t0"], utc=True)
        t1 = pd.to_datetime(ev["t1"], utc=True)
        return (t1 - t0) / pd.Timedelta(hours=1)
    raise ValueError("vessel_history needs gap_hours_exact or both t0 and t1")


def vessel_history(ev: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    """Calculate duration unusualness and pair-repeat context for each edge."""
    if cands.empty:
        return pd.DataFrame(
            {
                "pair_id": pd.Series(dtype="string"),
                "gap_unusualness_a": pd.Series(dtype="Float64"),
                "gap_unusualness_b": pd.Series(dtype="Float64"),
                "gap_unusualness": pd.Series(dtype="Float64"),
                "repeat_rate_a": pd.Series(dtype="Float64"),
                "repeat_rate_b": pd.Series(dtype="Float64"),
                "prior_pair_count": pd.Series(dtype="int64"),
            }
        )
    required_event_columns = {"gap_id", "mmsi"}
    missing = required_event_columns - set(ev.columns)
    if missing:
        raise ValueError(f"vessel_history requires event columns: {sorted(missing)}")
    required_candidate_columns = {"pair_id", "gap_id_a", "gap_id_b", "mmsi_a", "mmsi_b", "t0_a"}
    missing = required_candidate_columns - set(cands.columns)
    if missing:
        raise ValueError(f"vessel_history requires candidate columns: {sorted(missing)}")

    history = ev[["gap_id", "mmsi"]].copy()
    history["_duration_h"] = _event_durations_hours(ev)
    history["_n_gaps"] = history.groupby("mmsi", dropna=False)["gap_id"].transform("size")
    # rank(method='min') - 1 is exactly the number of *other* gaps shorter
    # than this gap, including ties correctly.  The denominator is the vessel's
    # full gap count; the focal gap simply contributes zero to the numerator.
    history["_shorter"] = history.groupby("mmsi", dropna=False)["_duration_h"].rank(method="min", ascending=True) - 1
    history["_unusualness"] = history["_shorter"] / history["_n_gaps"]
    history.loc[history["_n_gaps"] < config.MIN_GAPS_FOR_HISTORY, "_unusualness"] = np.nan
    unusual_by_gap = history.drop_duplicates("gap_id", keep="first").set_index("gap_id")["_unusualness"]
    n_gaps_by_mmsi = history.groupby("mmsi", dropna=False)["gap_id"].size()

    pair_mmsis = pd.concat(
        [
            cands[["mmsi_a"]].rename(columns={"mmsi_a": "mmsi"}),
            cands[["mmsi_b"]].rename(columns={"mmsi_b": "mmsi"}),
        ],
        ignore_index=True,
    )
    pair_count_by_mmsi = pair_mmsis.groupby("mmsi", dropna=False).size()
    n_a = cands["mmsi_a"].map(n_gaps_by_mmsi)
    n_b = cands["mmsi_b"].map(n_gaps_by_mmsi)
    repeat_a = cands["mmsi_a"].map(pair_count_by_mmsi) / n_a
    repeat_b = cands["mmsi_b"].map(pair_count_by_mmsi) / n_b

    # Canonical side A is time-ordered, but MMSI-pair groups are unordered.
    pair_key = cands.apply(lambda row: "|".join(sorted((str(row["mmsi_a"]), str(row["mmsi_b"])))), axis=1)
    pair_times = pd.to_datetime(cands["t0_a"], utc=True)
    # With rank(method='min'), candidates sharing exactly the same shutoff get
    # the same count and none is incorrectly considered earlier than the other.
    prior = pair_times.groupby(pair_key).rank(method="min") - 1

    unusual_a = cands["gap_id_a"].map(unusual_by_gap)
    unusual_b = cands["gap_id_b"].map(unusual_by_gap)
    pair_unusual = pd.concat([unusual_a, unusual_b], axis=1).mean(axis=1, skipna=True)
    pair_unusual = pair_unusual.where(unusual_a.notna() | unusual_b.notna(), pd.NA)

    return pd.DataFrame(
        {
            "pair_id": cands["pair_id"].astype("string").to_numpy(),
            "gap_unusualness_a": unusual_a.astype("Float64"),
            "gap_unusualness_b": unusual_b.astype("Float64"),
            "gap_unusualness": pair_unusual.astype("Float64"),
            "repeat_rate_a": repeat_a.astype("Float64"),
            "repeat_rate_b": repeat_b.astype("Float64"),
            "prior_pair_count": prior.fillna(0).astype("int64"),
        }
    )


def run() -> pd.DataFrame:
    """Run S4 and write its two derived artifacts.

    ``local_context.parquet`` carries local-density, identity, and history
    features keyed by pair id.  ``components.parquet`` remains a compact
    independently joinable component table as required by the output contract.
    """
    ev = pd.read_parquet(config.DERIVED / "gap_events.parquet")
    cands = pd.read_parquet(config.DERIVED / "candidates_t0.parquet")

    local = local_context(ev, cands)
    # Component regional-blackout classification uses local density; only this
    # temporary join is needed, keeping the persisted component artifact narrow.
    component_input = cands.merge(local[["pair_id", "local_dark_count"]], on="pair_id", how="left", validate="one_to_one")
    component_table = components(component_input)
    identities = identity_flags(ev, cands)
    histories = vessel_history(ev, cands)
    local_output = local.merge(identities, on="pair_id", how="left", validate="one_to_one").merge(
        histories, on="pair_id", how="left", validate="one_to_one"
    )

    config.DERIVED.mkdir(parents=True, exist_ok=True)
    local_output.to_parquet(config.DERIVED / "local_context.parquet", index=False)
    component_table.to_parquet(config.DERIVED / "components.parquet", index=False)

    print(
        "[context] "
        f"pairs={len(local_output)} bilateral={(component_table['component_class'] == 'bilateral').sum()} "
        f"twins={identities['identity_twin'].sum()} sequential={identities['sequential_mmsi'].sum()}"
    )
    return local_output


if __name__ == "__main__":
    run()
