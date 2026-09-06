"""Focused S6b checks for null-aware linear scoring and label precedence."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from pipeline import config
from pipeline.score import score_components, score_frame


def _base_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "pair_id": "t0-score-fixture",
        "start_km": 0.0,
        "start_delta_min": 0.0,
        "end_km": 0.0,
        "end_delta_min": 0.0,
        "duration_ratio": 1.0,
        "overlap_h": 12.0,
        "p_cell": 0.05,
        "kin_plausibility": 0.8,
        "identity_twin": False,
        "sequential_mmsi": False,
        "component_class": "bilateral",
        "gap_unusualness": 0.75,
        "viirs_state": "no_coverage",
        "local_dark_count": 0,
        "local_unique_vessels": 0,
        "component_size": 2,
        "local_same_flag_share": 0.0,
        "local_sequential_share": 0.0,
        "repeat_rate_a": 0.10,
        "repeat_rate_b": 0.10,
        "identity_status": "resolved",
        "feasible": True,
    }
    row.update(overrides)
    return row


def test_score_frame_keeps_behaviour_null_and_renormalises_available_weights() -> None:
    row = _base_row()
    result = score_frame(pd.DataFrame([row])).iloc[0]
    components = score_components(row)

    assert pd.isna(result["beh"])
    available = json.loads(result["available_components"])
    assert available == ["geom", "kin", "ctx", "cor", "den", "flt", "hab"]
    expected_raw = sum(
        config.WEIGHTS[name] * components[name].value
        for name in available
        if components[name].value is not None
    ) / sum(abs(config.WEIGHTS[name]) for name in available)
    assert result["raw"] == pytest.approx(expected_raw)
    assert 0.0 <= result["priority"] <= 1.0
    provenance = json.loads(result["score_provenance"])
    assert provenance["beh"]["value"] is None
    assert provenance["beh"]["available"] is False
    assert provenance["geom"]["inputs"]["start_km"] == 0.0


def test_identity_warning_has_label_precedence_over_a_high_priority_pair() -> None:
    result = score_frame(pd.DataFrame([_base_row(identity_twin=True)])).iloc[0]

    assert result["label"] == "identity-twin"
    assert result["risk_level"] == "review"
