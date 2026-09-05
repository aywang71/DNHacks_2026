import pytest

from pipeline import config
from pipeline.load import load_gap_events
from pipeline.pair_t0 import (
    brute_force_check,
    build_candidates,
    ladder_counts,
    make_pair_id,
    pair_events,
)


@pytest.fixture(scope="module")
def events():
    return load_gap_events()


@pytest.fixture(scope="module")
def candidates(events):
    return build_candidates(events)


def test_operating_pair_count_and_showcase(events, candidates):
    pairs = pair_events(events, **config.OPERATING)
    assert len(pairs) == 434
    assert len(candidates) == 434
    assert int(candidates["cross_flag"].sum()) == 26

    showcase = candidates.loc[
        (candidates["mmsi_a"] == config.SHOWCASE["mmsi_a"])
        & (candidates["mmsi_b"] == config.SHOWCASE["mmsi_b"])
        & (candidates["t0_a"].dt.strftime("%Y-%m-%d") == config.SHOWCASE["t0_date"])
    ]
    assert len(showcase) == 1
    row = showcase.iloc[0]
    assert abs(row["start_km"] - 6.60) < 0.05
    assert abs(row["start_delta_min"] - 0.083) < 0.01
    assert abs(row["end_km"] - 8.99) < 0.05
    assert abs(row["end_delta_min"] - 0.717) < 0.01
    assert abs(row["overlap_h"] - 41.76) < 0.02
    assert abs(row["duration_ratio"] - 0.9997) < 0.0002
    assert row["cell_month"] == "6826-2017-07"


def test_ladder_counts(events):
    assert ladder_counts(events) == {
        "start-only 50 km / 24 h": 101_901,
        "start-only 5 km / 1 h": 1_230,
        "both ends 25 km / 3 h": 5_630,
        "both ends 10 km / 1 h": 434,
        "both ends 5 km / 1 h": 103,
        "both ends 2 km / 30 min": 3,
        "loose": 18_775,
    }


def test_brute_force_subsample_and_symmetric_pair_id(events):
    brute_force_check(events)
    assert make_pair_id("alpha", "beta") == make_pair_id("beta", "alpha")
