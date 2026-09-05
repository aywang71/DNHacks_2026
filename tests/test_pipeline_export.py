"""Focused S8 contract tests using a single, self-contained showcase row."""

from __future__ import annotations

import copy
import json
import math

import pandas as pd
import pytest

from pipeline.export import build_record, validate_record, write_outputs


def _showcase_inputs() -> tuple[pd.Series, dict, dict, dict, dict]:
    feature = pd.Series(
        {
            "pair_id": "t0-showcase1234",
            "mmsi_a": "412331147",
            "mmsi_b": "416004105",
            "flag_a": "CHN",
            "flag_b": "TWN",
            "class_a": "squid_jigger",
            "class_b": "squid_jigger",
            "t0_a": "2017-07-01T18:33:00Z",
            "t0_b": "2017-07-01T18:33:05Z",
            "t1_a": "2017-07-03T12:19:32Z",
            "t1_b": "2017-07-03T12:18:49Z",
            "overlap_start": "2017-07-01T18:33:05Z",
            "overlap_end": "2017-07-03T12:18:49Z",
            "lat0_a": 42.749,
            "lon0_a": 161.983,
            "lat0_b": 42.795,
            "lon0_b": 162.034,
            "lat1_a": 42.399,
            "lon1_a": 161.347,
            "lat1_b": 42.340,
            "lon1_b": 161.423,
            "start_km": 6.60,
            "start_delta_min": 0.083,
            "end_km": 8.99,
            "end_delta_min": 0.717,
            "overlap_h": 41.76,
            "duration_ratio": 0.9997,
            "cross_flag": True,
            "shore_off_km": 892.0,
            "p_cell": 1 / 201,
            "s_geom": 1.0,
            "s_kin": 0.95,
            "s_beh": None,
            "s_ctx": 0.6,
            "s_cor": 0.0,
            "s_den": 0.15,
            "s_flt": 0.0,
            "s_hab": 0.38,
            "raw": 0.329,
            "priority": 0.54,
            "risk_score": 54,
            "label": "investigate",
            "risk_level": "high",
            "evidence_tier": "bilateral_rendezvous_plausible",
            "identity_status": "resolved",
            "flag_card_a": "none",
            "flag_card_b": "yellow",
            "length_a": 69.9,
            "length_b": 72.8,
            "tonnage_a": 1408.0,
            "tonnage_b": 962.0,
            "n_gaps_vessel_a": 63,
            "n_gaps_vessel_b": 46,
            "required_speed_kn": 0.92,
            "tau_h": 38.6,
            "kin_plausibility": 0.95,
            "local_dark_count": 1,
            "local_unique_vessels": 1,
            "local_same_flag_share": None,
            "component_size": 2,
            "component_class": "bilateral",
            "sequential_mmsi": False,
            "identity_twin": False,
            "gap_unusualness": 0.62,
            "neighbours": '[{"mmsi":"412329634","flag":"CHN","deltaMin":1.4,"distanceKm":9.7}]',
            "zone": "NW Pacific high seas",
            "lon_star": 161.958,
            "lat_star": 42.752,
        }
    )
    ring_a = [[161.90, 42.70], [162.00, 42.70], [162.00, 42.80], [161.90, 42.80]]
    ring_b = [[161.91, 42.69], [162.01, 42.69], [162.01, 42.79], [161.91, 42.79]]
    feasibility = {"ring_a": ring_a, "ring_b": ring_b, "dateline": False}
    corroboration = {
        "viirs_state": "no_coverage",
        "viirs_uncorrelated_count": 0,
        "viirs_min_km_to_p_star": None,
        "viirs_detections": "[]",
        "presence_source": "corpus_endpoints",
    }
    context = {"pairs_in_queue_a": 1, "pairs_in_queue_b": 1}
    null = {"name": "within-cell permutation v1", "draws": 200, "cell_deg": 5, "observed": 434, "null_mean": 12.0, "lift": 36.2}
    return feature, context, feasibility, corroboration, null


def _record() -> dict:
    f, ctx, feas, corr, null = _showcase_inputs()
    return build_record("t0-showcase1234", f, ctx, feas, corr, null)


def test_build_showcase_record_validates_and_writes_equal_track(tmp_path) -> None:
    record = _record()
    validate_record(record)

    assert record["coordinates"] == [161.958, 42.752]
    assert record["features"]["pCell"] == 0.005
    features = record["track"]["features"]
    assert sum(feature["properties"]["observationStatus"] == "observed" for feature in features) == 4
    assert sum(feature["geometry"]["type"] == "LineString" for feature in features) == 2
    assert sum(feature["geometry"]["type"] == "Polygon" for feature in features) == 2

    write_outputs([record], tmp_path)
    payload = json.loads((tmp_path / "risk-events.json").read_text())
    track = json.loads((tmp_path / "tracks" / "t0-showcase1234.geojson").read_text())
    assert payload == [record]
    assert track == record["track"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda record: record["features"].update({"pCell": math.nan}), "non-finite"),
        (lambda record: record.update({"coordinates": [42.752, 161.958]}), "lon, lat"),
        (lambda record: record.update({"attribution": ""}), "attribution"),
    ],
)
def test_validate_record_rejects_nan_swapped_coordinates_and_missing_attribution(mutate, match: str) -> None:
    record = copy.deepcopy(_record())
    mutate(record)
    with pytest.raises(ValueError, match=match):
        validate_record(record)
