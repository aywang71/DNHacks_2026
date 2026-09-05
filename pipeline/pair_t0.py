"""S3: generate temporally synchronised paired-dark candidates.

Candidate generation deliberately uses a simple time block plus vectorised
numeric work inside each block.  It is easy to audit and fast enough for the
55k-event corpus without a spatial index or a geometry dependency.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .geo import haversine_km, normalise_lon


DERIVED = config.DERIVED

CANDIDATE_COLUMNS = [
    "pair_id",
    "gap_id_a",
    "gap_id_b",
    "mmsi_a",
    "mmsi_b",
    "flag_a",
    "flag_b",
    "class_a",
    "class_b",
    "t0_a",
    "t1_a",
    "t0_b",
    "t1_b",
    "start_km",
    "start_delta_min",
    "end_km",
    "end_delta_min",
    "overlap_h",
    "overlap_start",
    "overlap_end",
    "duration_ratio",
    "duration_delta_h",
    "cross_flag",
    "same_flag",
    "flag_missing",
    "cell",
    "cell_month",
    "dateline",
    "shore_off_km",
    "shore_on_km",
    "length_a",
    "tonnage_a",
    "length_b",
    "tonnage_b",
]


def make_pair_id(gap_id_a: str, gap_id_b: str) -> str:
    """Make the stable, symmetric T0 candidate identifier."""

    payload = "|".join(sorted((str(gap_id_a), str(gap_id_b))))
    return "t0-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _valid_sorted_events(ev: pd.DataFrame) -> pd.DataFrame:
    """Return eligible events in the positional order used by pair indices."""

    valid = ev.loc[ev["mmsi_valid"].fillna(False)].copy()
    return valid.sort_values("t0", kind="stable").reset_index(drop=True)


def _empty_pairs() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "i": pd.Series(dtype="int64"),
            "j": pd.Series(dtype="int64"),
        }
    )


def _resolve_end_thresholds(
    *, start_km: float, start_h: float, end_km: float | None, end_h: float | None, both_ends: bool
) -> tuple[float | None, float | None]:
    if float(start_km) < 0 or float(start_h) < 0:
        raise ValueError("start thresholds must be non-negative")
    if not both_ends:
        return None, None
    resolved_km = float(start_km if end_km is None else end_km)
    resolved_h = float(start_h if end_h is None else end_h)
    if resolved_km < 0 or resolved_h < 0:
        raise ValueError("end thresholds must be non-negative")
    return resolved_km, resolved_h


def _pair_indices_blocked(
    ordered: pd.DataFrame,
    *,
    start_km: float,
    start_h: float,
    end_km: float | None = None,
    end_h: float | None = None,
    both_ends: bool = True,
) -> pd.DataFrame:
    """Find pairs in an already valid, t0-sorted event frame."""

    resolved_end_km, resolved_end_h = _resolve_end_thresholds(
        start_km=start_km,
        start_h=start_h,
        end_km=end_km,
        end_h=end_h,
        both_ends=both_ends,
    )
    n_events = len(ordered)
    if n_events < 2:
        return _empty_pairs()

    t0 = ordered["t0"].to_numpy(dtype="datetime64[us]")
    t1 = ordered["t1"].to_numpy(dtype="datetime64[us]")
    lat0 = ordered["lat0"].to_numpy(dtype=float)
    lon0 = ordered["lon0"].to_numpy(dtype=float)
    lat1 = ordered["lat1"].to_numpy(dtype=float)
    lon1 = ordered["lon1"].to_numpy(dtype=float)
    mmsi = ordered["mmsi"].astype("string").to_numpy(dtype=str)

    start_window = pd.Timedelta(hours=float(start_h)).to_timedelta64()
    # The start-time rule is inclusive (``Δt <= start_h``), so the time block
    # retains events exactly on its upper boundary as well.
    hi = np.searchsorted(t0, t0 + start_window, side="right")
    end_window = pd.Timedelta(hours=resolved_end_h).to_timedelta64() if both_ends else None
    zero = np.timedelta64(0, "us")

    i_parts: list[np.ndarray] = []
    j_parts: list[np.ndarray] = []
    for i, stop in enumerate(hi):
        if stop <= i + 1:
            continue
        js = np.arange(i + 1, stop, dtype=np.int64)
        js = js[mmsi[js] != mmsi[i]]
        if not js.size:
            continue

        shutoff_distance = haversine_km(lat0[i], lon0[i], lat0[js], lon0[js])
        js = js[shutoff_distance <= float(start_km)]
        if not js.size:
            continue

        overlap = np.minimum(t1[i], t1[js]) - np.maximum(t0[i], t0[js])
        js = js[overlap > zero]
        if not js.size:
            continue

        if both_ends:
            reappearance_distance = haversine_km(lat1[i], lon1[i], lat1[js], lon1[js])
            end_delta = np.abs(t1[i] - t1[js])
            js = js[(reappearance_distance <= resolved_end_km) & (end_delta <= end_window)]
            if not js.size:
                continue

        i_parts.append(np.full(js.size, i, dtype=np.int64))
        j_parts.append(js)

    if not i_parts:
        return _empty_pairs()
    return pd.DataFrame({"i": np.concatenate(i_parts), "j": np.concatenate(j_parts)})


def pair_events(
    ev: pd.DataFrame,
    *,
    start_km,
    start_h,
    end_km=None,
    end_h=None,
    both_ends=True,
) -> pd.DataFrame:
    """Return matching ``i, j`` positions in the valid events sorted by ``t0``.

    Invalid MMSIs never participate.  The return positions intentionally refer
    to the internally sorted valid frame; ``build_candidates`` uses the same
    ordering to attach source fields without relying on a mutable index.
    """

    ordered = _valid_sorted_events(ev)
    return _pair_indices_blocked(
        ordered,
        start_km=start_km,
        start_h=start_h,
        end_km=end_km,
        end_h=end_h,
        both_ends=both_ends,
    )


def _take(ordered: pd.DataFrame, column: str, positions: np.ndarray) -> pd.Series:
    return ordered[column].iloc[positions].reset_index(drop=True)


def _empty_candidates() -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series(dtype="object") for column in CANDIDATE_COLUMNS})


def build_candidates(ev: pd.DataFrame) -> pd.DataFrame:
    """Apply the operating rule and attach pair-level geometry and metadata."""

    ordered = _valid_sorted_events(ev)
    pairs = _pair_indices_blocked(ordered, **config.OPERATING)
    if pairs.empty:
        return _empty_candidates()

    i = pairs["i"].to_numpy(dtype=np.int64)
    j = pairs["j"].to_numpy(dtype=np.int64)
    t0_i = _take(ordered, "t0", i)
    t0_j = _take(ordered, "t0", j)
    gap_i = _take(ordered, "gap_id", i)
    gap_j = _take(ordered, "gap_id", j)
    tie = t0_i.eq(t0_j).fillna(False).to_numpy(dtype=bool)
    tie_swap = gap_i.gt(gap_j).fillna(False).to_numpy(dtype=bool)
    # The time block already guarantees i is no later than j.  Retaining the
    # first condition makes canonical ordering explicit if this helper evolves.
    time_swap = t0_i.gt(t0_j).fillna(False).to_numpy(dtype=bool)
    swap = time_swap | (tie & tie_swap)
    a_pos = np.where(swap, j, i)
    b_pos = np.where(swap, i, j)

    gap_id_a = _take(ordered, "gap_id", a_pos)
    gap_id_b = _take(ordered, "gap_id", b_pos)
    mmsi_a = _take(ordered, "mmsi", a_pos)
    mmsi_b = _take(ordered, "mmsi", b_pos)
    flag_a = _take(ordered, "flag", a_pos)
    flag_b = _take(ordered, "flag", b_pos)
    class_a = _take(ordered, "vessel_class", a_pos)
    class_b = _take(ordered, "vessel_class", b_pos)
    t0_a = _take(ordered, "t0", a_pos)
    t1_a = _take(ordered, "t1", a_pos)
    t0_b = _take(ordered, "t0", b_pos)
    t1_b = _take(ordered, "t1", b_pos)

    start_distance = haversine_km(
        _take(ordered, "lat0", a_pos),
        _take(ordered, "lon0", a_pos),
        _take(ordered, "lat0", b_pos),
        _take(ordered, "lon0", b_pos),
    )
    end_distance = haversine_km(
        _take(ordered, "lat1", a_pos),
        _take(ordered, "lon1", a_pos),
        _take(ordered, "lat1", b_pos),
        _take(ordered, "lon1", b_pos),
    )
    start_delta_min = (t0_b - t0_a).abs() / pd.Timedelta(minutes=1)
    end_delta_min = (t1_b - t1_a).abs() / pd.Timedelta(minutes=1)
    overlap_start = t0_a.where(t0_a.ge(t0_b), t0_b)
    overlap_end = t1_a.where(t1_a.le(t1_b), t1_b)
    overlap_h = (overlap_end - overlap_start) / pd.Timedelta(hours=1)
    duration_a = (t1_a - t0_a) / pd.Timedelta(hours=1)
    duration_b = (t1_b - t0_b) / pd.Timedelta(hours=1)
    duration_max = np.maximum(duration_a.to_numpy(dtype=float), duration_b.to_numpy(dtype=float))
    duration_ratio = np.divide(
        np.minimum(duration_a.to_numpy(dtype=float), duration_b.to_numpy(dtype=float)),
        duration_max,
        out=np.full(len(duration_max), np.nan, dtype=float),
        where=duration_max > 0,
    )
    duration_delta_h = (duration_a - duration_b).abs()

    flag_a_missing = flag_a.isna().to_numpy(dtype=bool)
    flag_b_missing = flag_b.isna().to_numpy(dtype=bool)
    flag_missing = flag_a_missing | flag_b_missing
    equal_flags = flag_a.eq(flag_b).fillna(False).to_numpy(dtype=bool)
    same_flag = (~flag_missing) & equal_flags
    cross_flag = (~flag_missing) & (~equal_flags)

    lon_matrix = normalise_lon(
        np.vstack(
            [
                _take(ordered, "lon0", a_pos).to_numpy(dtype=float),
                _take(ordered, "lon1", a_pos).to_numpy(dtype=float),
                _take(ordered, "lon0", b_pos).to_numpy(dtype=float),
                _take(ordered, "lon1", b_pos).to_numpy(dtype=float),
            ]
        )
    )
    bbox_dateline = (np.nanmax(lon_matrix, axis=0) - np.nanmin(lon_matrix, axis=0)) > 180.0
    event_dateline = (
        _take(ordered, "dateline", a_pos).fillna(False).to_numpy(dtype=bool)
        | _take(ordered, "dateline", b_pos).fillna(False).to_numpy(dtype=bool)
    )

    shore_off_a = _take(ordered, "shore_off_km", a_pos).to_numpy(dtype=float)
    shore_off_b = _take(ordered, "shore_off_km", b_pos).to_numpy(dtype=float)
    shore_on_a = _take(ordered, "shore_on_km", a_pos).to_numpy(dtype=float)
    shore_on_b = _take(ordered, "shore_on_km", b_pos).to_numpy(dtype=float)

    candidates = pd.DataFrame(
        {
            "pair_id": [make_pair_id(a, b) for a, b in zip(gap_id_a, gap_id_b)],
            "gap_id_a": gap_id_a,
            "gap_id_b": gap_id_b,
            "mmsi_a": mmsi_a,
            "mmsi_b": mmsi_b,
            "flag_a": flag_a,
            "flag_b": flag_b,
            "class_a": class_a,
            "class_b": class_b,
            "t0_a": t0_a,
            "t1_a": t1_a,
            "t0_b": t0_b,
            "t1_b": t1_b,
            "start_km": start_distance,
            "start_delta_min": start_delta_min,
            "end_km": end_distance,
            "end_delta_min": end_delta_min,
            "overlap_h": overlap_h,
            "overlap_start": overlap_start,
            "overlap_end": overlap_end,
            "duration_ratio": duration_ratio,
            "duration_delta_h": duration_delta_h,
            "cross_flag": cross_flag,
            "same_flag": same_flag,
            "flag_missing": flag_missing,
            "cell": _take(ordered, "cell", a_pos),
            "cell_month": _take(ordered, "cell_month", a_pos),
            "dateline": event_dateline | bbox_dateline,
            "shore_off_km": (shore_off_a + shore_off_b) / 2.0,
            "shore_on_km": (shore_on_a + shore_on_b) / 2.0,
            "length_a": _take(ordered, "length_m", a_pos),
            "tonnage_a": _take(ordered, "tonnage_gt", a_pos),
            "length_b": _take(ordered, "length_m", b_pos),
            "tonnage_b": _take(ordered, "tonnage_gt", b_pos),
        }
    )
    return candidates[CANDIDATE_COLUMNS]


def ladder_counts(ev: pd.DataFrame) -> dict[str, int]:
    """Return observed pair totals for every stated ladder rung and loose rule."""

    counts: dict[str, int] = {}
    for name, thresholds in config.LADDER:
        counts[name] = int(len(pair_events(ev, **thresholds)))
    counts["loose"] = int(len(pair_events(ev, **config.LOOSE)))
    return counts


def _brute_force_pairs(
    ordered: pd.DataFrame,
    *,
    start_km: float,
    start_h: float,
    end_km: float | None = None,
    end_h: float | None = None,
    both_ends: bool = True,
) -> pd.DataFrame:
    """Independent O(n²) reference implementation for the blocking check."""

    resolved_end_km, resolved_end_h = _resolve_end_thresholds(
        start_km=start_km,
        start_h=start_h,
        end_km=end_km,
        end_h=end_h,
        both_ends=both_ends,
    )
    n_events = len(ordered)
    if n_events < 2:
        return _empty_pairs()

    t0 = ordered["t0"].to_numpy(dtype="datetime64[us]")
    t1 = ordered["t1"].to_numpy(dtype="datetime64[us]")
    lat0 = ordered["lat0"].to_numpy(dtype=float)
    lon0 = ordered["lon0"].to_numpy(dtype=float)
    lat1 = ordered["lat1"].to_numpy(dtype=float)
    lon1 = ordered["lon1"].to_numpy(dtype=float)
    mmsi = ordered["mmsi"].astype("string").to_numpy(dtype=str)
    start_window = pd.Timedelta(hours=float(start_h)).to_timedelta64()
    end_window = pd.Timedelta(hours=resolved_end_h).to_timedelta64() if both_ends else None
    zero = np.timedelta64(0, "us")

    i_parts: list[np.ndarray] = []
    j_parts: list[np.ndarray] = []
    for i in range(n_events - 1):
        js = np.arange(i + 1, n_events, dtype=np.int64)
        # This intentionally scans every later event rather than using a
        # search block.  The inclusive bound matches the operational rule.
        js = js[t0[js] <= t0[i] + start_window]
        js = js[mmsi[js] != mmsi[i]]
        if not js.size:
            continue
        shutoff_distance = haversine_km(lat0[i], lon0[i], lat0[js], lon0[js])
        js = js[shutoff_distance <= float(start_km)]
        if not js.size:
            continue
        overlap = np.minimum(t1[i], t1[js]) - np.maximum(t0[i], t0[js])
        js = js[overlap > zero]
        if not js.size:
            continue
        if both_ends:
            reappearance_distance = haversine_km(lat1[i], lon1[i], lat1[js], lon1[js])
            end_delta = np.abs(t1[i] - t1[js])
            js = js[(reappearance_distance <= resolved_end_km) & (end_delta <= end_window)]
            if not js.size:
                continue
        i_parts.append(np.full(js.size, i, dtype=np.int64))
        j_parts.append(js)

    if not i_parts:
        return _empty_pairs()
    return pd.DataFrame({"i": np.concatenate(i_parts), "j": np.concatenate(j_parts)})


def brute_force_check(ev: pd.DataFrame, n_sample: int = 1500, seed: int = config.SEED) -> None:
    """Assert that blocked pairing agrees with an O(n²) random subsample."""

    if n_sample < 1:
        raise ValueError("n_sample must be positive")
    sample_size = min(int(n_sample), len(ev))
    rng = np.random.default_rng(seed)
    sample_positions = rng.choice(len(ev), size=sample_size, replace=False)
    ordered = _valid_sorted_events(ev.iloc[sample_positions])
    blocked = _pair_indices_blocked(ordered, **config.OPERATING)
    brute = _brute_force_pairs(ordered, **config.OPERATING)
    if blocked.equals(brute):
        return

    blocked_set = set(map(tuple, blocked[["i", "j"]].to_numpy()))
    brute_set = set(map(tuple, brute[["i", "j"]].to_numpy()))
    missing = sorted(brute_set - blocked_set)[:5]
    extra = sorted(blocked_set - brute_set)[:5]
    raise AssertionError(
        "blocked pair search disagrees with O(n²) reference "
        f"(blocked={len(blocked_set)}, brute={len(brute_set)}, missing={missing}, extra={extra})"
    )


def _write_pair_grid(candidates: pd.DataFrame, counts: dict[str, int], out: Path) -> None:
    ladder = {name: counts[name] for name, _ in config.LADDER}
    observed_by_cell_month = {
        str(cell_month): int(count)
        for cell_month, count in candidates["cell_month"].value_counts().sort_index().items()
    }
    payload = {
        "ladder": ladder,
        "loose": counts["loose"],
        "observed_by_cell_month": observed_by_cell_month,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_queue_mmsis(candidates: pd.DataFrame, out: Path) -> int:
    mmsis = sorted(
        set(candidates["mmsi_a"].astype(str).tolist())
        | set(candidates["mmsi_b"].astype(str).tolist())
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{mmsi}\n" for mmsi in mmsis), encoding="utf-8")
    return len(mmsis)


def run() -> None:
    """Materialise operating candidates, counts, queue MMSIs, and the check."""

    events = pd.read_parquet(DERIVED / "gap_events.parquet")
    candidates = build_candidates(events)
    brute_force_check(events)
    counts = ladder_counts(events)

    candidates_out = DERIVED / "candidates_t0.parquet"
    candidates_out.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_parquet(candidates_out, index=False)
    _write_pair_grid(candidates, counts, DERIVED / "pair_grid_counts.json")
    n_queue_mmsis = _write_queue_mmsis(candidates, DERIVED / "queue_mmsis.txt")

    ladder_summary = ", ".join(str(counts[name]) for name, _ in config.LADDER)
    print(
        "[pair] "
        f"operating={len(candidates)} cross_flag={int(candidates['cross_flag'].sum())} "
        f"ladder=[{ladder_summary}] loose={counts['loose']} queue_mmsis={n_queue_mmsis}"
    )
