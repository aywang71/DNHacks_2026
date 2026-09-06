"""Focused S6a checks for complete keyed feature assembly."""

from __future__ import annotations

import pandas as pd
import pytest

from pipeline import config
from pipeline.features import build_features


def _inputs() -> tuple[pd.DataFrame, ...]:
    derived = config.DERIVED
    return (
        pd.read_parquet(derived / "candidates_t0.parquet"),
        pd.read_parquet(derived / "feasibility.parquet"),
        pd.read_parquet(derived / "local_context.parquet"),
        pd.read_parquet(derived / "components.parquet"),
        pd.read_parquet(derived / "corroboration.parquet"),
        pd.read_parquet(derived / "p_cell.parquet"),
        pd.read_parquet(derived / "gap_events.parquet"),
    )


def test_build_features_has_one_complete_exportable_row_per_candidate() -> None:
    candidates, feasibility, context, components, corroboration, p_cell, events = _inputs()
    features = build_features(candidates, feasibility, context, components, corroboration, p_cell, events)

    assert len(features) == len(candidates) == 434
    assert features["pair_id"].is_unique
    assert set(features["pair_id"]) == set(candidates["pair_id"])
    assert {
        "lat0_a",
        "lon0_a",
        "lat1_b",
        "lon1_b",
        "n_gaps_vessel_a",
        "ring_a",
        "viirs_state",
        "p_cell",
        "loiter_bracket",
        "possible_port_transit",
    }.issubset(features.columns)
    assert features[["lat0_a", "lon0_a", "lat1_a", "lon1_a"]].notna().all(axis=None)
    # Feasibility finds five additional ring dateline crossings.  S8 must use
    # the conservative union and preserve both source flags for audit.
    assert int(features["dateline"].sum()) == 6
    assert {"candidate_dateline", "feasibility_dateline"}.issubset(features.columns)


def test_build_features_rejects_incomplete_stage_pair_coverage() -> None:
    candidates, feasibility, context, components, corroboration, p_cell, events = _inputs()
    with pytest.raises(ValueError, match="coverage does not match"):
        build_features(candidates, feasibility.iloc[:-1], context, components, corroboration, p_cell, events)
