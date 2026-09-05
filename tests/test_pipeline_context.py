"""Acceptance checks for S4 local context and confounder features."""

from __future__ import annotations

import json

import pandas as pd

from pipeline import config
from pipeline.context import components, identity_flags, local_context, vessel_history


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_parquet(config.DERIVED / "gap_events.parquet"),
        pd.read_parquet(config.DERIVED / "candidates_t0.parquet"),
    )


def _showcase(cands: pd.DataFrame) -> pd.Series:
    row = cands[
        cands["mmsi_a"].eq(config.SHOWCASE["mmsi_a"])
        & cands["mmsi_b"].eq(config.SHOWCASE["mmsi_b"])
        & cands["t0_a"].dt.strftime("%Y-%m-%d").eq(config.SHOWCASE["t0_date"])
    ]
    assert len(row) == 1
    return row.iloc[0]


def test_context_acceptance_components_neighbour_and_identity_flags() -> None:
    ev, cands = _inputs()
    local = local_context(ev, cands)
    component_input = cands.merge(local[["pair_id", "local_dark_count"]], on="pair_id", validate="one_to_one")
    comp = components(component_input)
    identity = identity_flags(ev, cands)

    component_sizes = comp.drop_duplicates("component_id")["component_size"].value_counts().sort_index().to_dict()
    assert component_sizes == {2: 237, 3: 44, 4: 9, 5: 3, 6: 1, 14: 1}
    assert int((comp["component_class"] == "bilateral").sum()) == 237
    assert int((comp["component_size"] >= 5).sum()) == 55
    assert int(identity["sequential_mmsi"].sum()) == 173

    showcase = _showcase(cands)
    context = local.loc[local["pair_id"].eq(showcase["pair_id"])].iloc[0]
    neighbours = json.loads(context["neighbours"])
    assert len(neighbours) == 1
    assert neighbours[0]["mmsi"] == "412329634"
    assert neighbours[0]["flag"] == "CHN"
    assert abs(neighbours[0]["deltaMin"] - 1.4) < 0.1
    assert abs(neighbours[0]["distanceKm"] - 9.7) < 0.1
    assert pd.isna(context["local_same_flag_share"])


def test_context_history_and_union_count_semantics() -> None:
    ev, cands = _inputs()
    local = local_context(ev, cands)
    history = vessel_history(ev, cands)
    showcase = _showcase(cands)
    row = history.loc[history["pair_id"].eq(showcase["pair_id"])].iloc[0]

    assert abs(row["gap_unusualness_a"] - 0.54) < 0.01
    assert abs(row["gap_unusualness_b"] - 0.70) < 0.01
    assert row["prior_pair_count"] == 0
    assert abs(row["repeat_rate_a"] - 1 / 63) < 1e-12
    assert abs(row["repeat_rate_b"] - 1 / 46) < 1e-12

    # The public definition is the union of shutoff and reappearance event
    # sets, so it can be greater than either endpoint's count.
    assert (local["local_dark_count"] >= local["local_dark_count_off"]).all()
    assert (local["local_dark_count"] >= local["local_dark_count_on"]).all()


def test_context_empty_inputs_are_safe() -> None:
    ev, cands = _inputs()
    empty = cands.iloc[0:0].copy()
    assert local_context(ev, empty).empty
    assert components(empty).empty
    assert identity_flags(ev, empty).empty
    assert vessel_history(ev, empty).empty
