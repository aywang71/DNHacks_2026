"""S6a: assemble one auditable feature row for every operating T0 pair.

The reference corpus does not contain the optional GFW identity, encounter,
loitering, port-visit, jurisdiction, or VIIRS-enrichment inputs.  This stage
therefore joins only materialised S1--S5/S7 artifacts and leaves those fields
as real missing values.  It also copies the four observed endpoint positions
and per-vessel corpus metadata from ``gap_events.parquet`` so S8 never has to
infer display geometry from a score.

``features.parquet`` deliberately carries the canonical names consumed by
``pipeline.export``.  Keeping that complete, one-row-per-pair surface here
makes later enrichment additive and lets S8 operate on a single audited S6
input rather than a collection of implicit joins.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


DERIVED = config.DERIVED

# These are the endpoint fields that S8 needs but that the compact candidate
# table intentionally does not persist.  They remain namespaced by candidate
# side so a pair cannot silently mix up A and B observations.
_ENDPOINT_COLUMNS = (
    "lat0",
    "lon0",
    "lat1",
    "lon1",
    "n_gaps_vessel",
    "length_estimated",
    "tonnage_estimated",
)

# The reference run has no enrichment for these fields.  Materialising them as
# null keeps a stable S6/S8 contract and, crucially, makes unavailable evidence
# distinguishable from a measured zero in the exported JSON.
_OPTIONAL_EXPORT_COLUMNS = (
    "imo_a",
    "imo_b",
    "vessel_name_a",
    "vessel_name_b",
    "role_a",
    "role_b",
    "flag_card_a",
    "flag_card_b",
    "rfmo_authorized_a",
    "rfmo_authorized_b",
    "iuu_listed_a",
    "iuu_listed_b",
    "zone",
    "rfmo_area",
    "eez",
    "eez_entry_while_dark",
    "port_distance_km",
    "known_partners",
    "loiter_bracket",
    "encounter_bracket",
    "port_after_gap_risk",
    "possible_port_transit",
    "explanations",
)


def _require_columns(frame: pd.DataFrame, name: str, columns: set[str]) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _validate_pair_ids(frame: pd.DataFrame, name: str) -> None:
    _require_columns(frame, name, {"pair_id"})
    ids = frame["pair_id"].astype("string")
    if ids.isna().any() or ids.str.strip().eq("").any():
        raise ValueError(f"{name} has a missing or empty pair_id")
    if ids.duplicated().any():
        raise ValueError(f"{name} has duplicate pair_id values")


def _same_pair_ids(candidates: pd.DataFrame, stage: pd.DataFrame, name: str) -> None:
    """Require complete one-to-one stage coverage instead of silently nulling it."""

    expected = set(candidates["pair_id"].astype(str))
    actual = set(stage["pair_id"].astype(str))
    if expected != actual:
        missing = sorted(expected.difference(actual))
        extra = sorted(actual.difference(expected))
        raise ValueError(
            f"{name} pair_id coverage does not match candidates "
            f"(missing={missing[:3]}, extra={extra[:3]})"
        )


def _join_stage(base: pd.DataFrame, stage: pd.DataFrame, name: str) -> pd.DataFrame:
    """Join a complete keyed stage while conservatively combining dateline flags."""

    _validate_pair_ids(stage, name)
    _same_pair_ids(base, stage, name)
    additions = stage.copy()
    duplicate_columns = [column for column in additions.columns if column != "pair_id" and column in base]
    for column in duplicate_columns:
        if column == "dateline":
            # Candidate detection catches endpoint crossings while feasibility
            # also catches a reachable-ring crossing.  S8 must omit a ring
            # when either one is true, so retain both source flags for audit
            # and use their conservative union as the exported geometry flag.
            aligned = additions.set_index("pair_id")[column].reindex(base["pair_id"]).reset_index(drop=True)
            if "candidate_dateline" not in base:
                base["candidate_dateline"] = base[column]
            base["feasibility_dateline"] = aligned.to_numpy()
            base[column] = (
                base[column].fillna(False).astype(bool).to_numpy()
                | aligned.fillna(False).astype(bool).to_numpy()
            )
            continue
        left = base.set_index("pair_id")[column].reindex(additions["pair_id"]).reset_index(drop=True)
        right = additions[column].reset_index(drop=True)
        equal = left.eq(right) | (left.isna() & right.isna())
        if not bool(equal.fillna(False).all()):
            raise ValueError(f"{name}.{column} disagrees with an existing feature column")
    additions = additions.drop(columns=duplicate_columns)
    return base.merge(additions, on="pair_id", how="left", validate="one_to_one", sort=False)


def _endpoint_features(events: pd.DataFrame, candidates: pd.DataFrame, side: str) -> pd.DataFrame:
    """Return the S8 endpoint fields for one candidate side, keyed to row order."""

    _require_columns(events, "gap_events.parquet", {"gap_id", *_ENDPOINT_COLUMNS})
    _require_columns(candidates, "candidates_t0.parquet", {f"gap_id_{side}"})
    if events["gap_id"].duplicated().any():
        raise ValueError("gap_events.parquet has duplicate gap_id values")
    lookup = events.set_index("gap_id")
    selected = lookup.reindex(candidates[f"gap_id_{side}"].astype("string"), columns=list(_ENDPOINT_COLUMNS))
    selected.index = candidates.index
    if selected[["lat0", "lon0", "lat1", "lon1"]].isna().any(axis=None):
        missing = candidates.loc[selected["lat0"].isna(), f"gap_id_{side}"].astype(str).head(3).tolist()
        raise ValueError(f"gap_events.parquet lacks endpoint geometry for candidate gaps: {missing}")
    return selected.rename(columns={column: f"{column}_{side}" for column in selected.columns})


def build_features(
    candidates: pd.DataFrame,
    feasibility: pd.DataFrame,
    local_context: pd.DataFrame,
    components: pd.DataFrame,
    corroboration: pd.DataFrame,
    p_cell: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    """Build the complete, one-row-per-pair S6 feature frame.

    The function accepts frames to make key and null semantics easy to test;
    :func:`run` supplies the materialised reference artifacts.
    """

    required_candidates = {
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
        "cross_flag",
        "dateline",
        "shore_off_km",
        "shore_on_km",
        "length_a",
        "tonnage_a",
        "length_b",
        "tonnage_b",
    }
    required_feasibility = {
        "pair_id",
        "tau_h",
        "lon_star",
        "lat_star",
        "required_speed_kn",
        "kin_plausibility",
        "feasible",
        "ring_a",
        "ring_b",
        "dateline",
    }
    required_context = {
        "pair_id",
        "local_dark_count_off",
        "local_dark_count_on",
        "local_dark_count",
        "local_unique_vessels",
        "local_same_flag_share",
        "local_sequential_share",
        "neighbours",
        "sequential_mmsi",
        "identity_twin",
        "identity_status",
        "gap_unusualness_a",
        "gap_unusualness_b",
        "gap_unusualness",
        "repeat_rate_a",
        "repeat_rate_b",
        "prior_pair_count",
    }
    required_components = {"pair_id", "component_id", "component_size", "component_class"}
    required_corroboration = {
        "pair_id",
        "viirs_state",
        "viirs_uncorrelated_count",
        "viirs_min_km_to_p_star",
        "viirs_detections",
        "presence_source",
    }
    _require_columns(candidates, "candidates_t0.parquet", required_candidates)
    _require_columns(feasibility, "feasibility.parquet", required_feasibility)
    _require_columns(local_context, "local_context.parquet", required_context)
    _require_columns(components, "components.parquet", required_components)
    _require_columns(corroboration, "corroboration.parquet", required_corroboration)
    _require_columns(p_cell, "p_cell.parquet", {"pair_id", "p_cell"})
    for name, frame in (
        ("candidates_t0.parquet", candidates),
        ("feasibility.parquet", feasibility),
        ("local_context.parquet", local_context),
        ("components.parquet", components),
        ("corroboration.parquet", corroboration),
        ("p_cell.parquet", p_cell),
    ):
        _validate_pair_ids(frame, name)

    output = candidates.copy()
    for name, frame in (
        ("feasibility.parquet", feasibility),
        ("local_context.parquet", local_context),
        ("components.parquet", components),
        ("corroboration.parquet", corroboration),
        ("p_cell.parquet", p_cell),
    ):
        output = _join_stage(output, frame, name)

    for side in ("a", "b"):
        endpoint = _endpoint_features(events, candidates, side)
        for column in endpoint.columns:
            if column in output:
                raise ValueError(f"endpoint feature collision for {column}")
            output[column] = endpoint[column]

    for column in _OPTIONAL_EXPORT_COLUMNS:
        if column not in output:
            output[column] = pd.Series(pd.NA, index=output.index, dtype="object")

    _validate_pair_ids(output, "features")
    if len(output) != len(candidates):
        raise AssertionError("S6 feature join changed the number of candidate pairs")
    return output


def run(
    *,
    candidates_path: Path | None = None,
    feasibility_path: Path | None = None,
    local_context_path: Path | None = None,
    components_path: Path | None = None,
    corroboration_path: Path | None = None,
    p_cell_path: Path | None = None,
    events_path: Path | None = None,
    out: Path | None = None,
) -> pd.DataFrame:
    """Materialise ``features.parquet`` from the completed upstream stages."""

    candidates_path = candidates_path or DERIVED / "candidates_t0.parquet"
    feasibility_path = feasibility_path or DERIVED / "feasibility.parquet"
    local_context_path = local_context_path or DERIVED / "local_context.parquet"
    components_path = components_path or DERIVED / "components.parquet"
    corroboration_path = corroboration_path or DERIVED / "corroboration.parquet"
    p_cell_path = p_cell_path or DERIVED / "p_cell.parquet"
    events_path = events_path or DERIVED / "gap_events.parquet"
    out = out or DERIVED / "features.parquet"

    features = build_features(
        pd.read_parquet(candidates_path),
        pd.read_parquet(feasibility_path),
        pd.read_parquet(local_context_path),
        pd.read_parquet(components_path),
        pd.read_parquet(corroboration_path),
        pd.read_parquet(p_cell_path),
        pd.read_parquet(events_path),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out, index=False)
    print(f"[features] pairs={len(features)} columns={len(features.columns)}")
    return features


if __name__ == "__main__":
    run()
