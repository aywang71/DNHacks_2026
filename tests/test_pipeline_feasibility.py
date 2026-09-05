import numpy as np
import pandas as pd

from pipeline import config
from pipeline.feasibility import Endpoints, joint_feasibility, reachable_ring


def _side(lat0, lon0, t0_h, lat1, lon1, t1_h, speed_kn):
    return Endpoints(
        lat0=np.asarray(lat0, dtype=float),
        lon0=np.asarray(lon0, dtype=float),
        t0_h=np.asarray(t0_h, dtype=float),
        lat1=np.asarray(lat1, dtype=float),
        lon1=np.asarray(lon1, dtype=float),
        t1_h=np.asarray(t1_h, dtype=float),
        v_kmh=np.asarray(speed_kn, dtype=float) * config.KM_PER_KN_H,
    )


def test_identical_gaps_have_full_joint_dwell():
    side = _side([0.0], [0.0], [0.0], [0.0], [0.0], [10.0], [12.0])
    result = joint_feasibility(side, side)

    assert result.tau_h[0] == 10.0
    assert result.feasible[0]
    assert result.required_speed_kn[0] == 0.0


def test_pair_requiring_forty_knots_is_infeasible():
    # At the equator, this local-frame endpoint displacement is exactly 40 kn
    # for the one-hour gap, while the assumed vessel speed is only 20 kn.
    lon_at_forty_kn = 40.0 * config.KM_PER_KN_H / 111.32
    side = _side([0.0], [0.0], [0.0], [0.0], [lon_at_forty_kn], [1.0], [20.0])
    result = joint_feasibility(side, side)

    assert result.required_speed_kn[0] > 39.9
    assert result.tau_h[0] < config.TAU_MIN_H
    assert not result.feasible[0]
    assert result.kin_plausibility[0] == 0.0


def test_dateline_ring_is_omitted():
    ring = reachable_ring(
        lat0=0.0,
        lon0=179.8,
        t0_h=0.0,
        lat1=0.0,
        lon1=-179.8,
        t1_h=10.0,
        v_kmh=12.0 * config.KM_PER_KN_H,
    )
    assert ring is None


def test_showcase_joint_feasibility_acceptance_values():
    events = pd.read_parquet(config.DERIVED / "gap_events.parquet").set_index("gap_id", drop=False)
    candidates = pd.read_parquet(config.DERIVED / "candidates_t0.parquet")
    candidate = candidates.loc[
        (candidates["mmsi_a"].astype(str) == config.SHOWCASE["mmsi_a"])
        & (candidates["mmsi_b"].astype(str) == config.SHOWCASE["mmsi_b"])
        & (candidates["t0_a"].dt.strftime("%Y-%m-%d") == config.SHOWCASE["t0_date"])
    ].iloc[0]
    row_a = events.loc[candidate["gap_id_a"]]
    row_b = events.loc[candidate["gap_id_b"]]
    origin = min(row_a["t0"], row_b["t0"])

    def offset(timestamp):
        return float((timestamp - origin) / pd.Timedelta(hours=1))

    a = _side(
        [row_a["lat0"]], [row_a["lon0"]], [offset(row_a["t0"])],
        [row_a["lat1"]], [row_a["lon1"]], [offset(row_a["t1"])],
        [row_a["v_kn"]],
    )
    b = _side(
        [row_b["lat0"]], [row_b["lon0"]], [offset(row_b["t0"])],
        [row_b["lat1"]], [row_b["lon1"]], [offset(row_b["t1"])],
        [row_b["v_kn"]],
    )
    result = joint_feasibility(a, b)

    assert abs(result.tau_h[0] - 38.6) <= 0.3
    assert abs(result.required_speed_kn[0] - 0.92) <= 0.05
    assert abs(result.lon_star[0] - 161.958) <= 0.05
    assert abs(result.lat_star[0] - 42.752) <= 0.05
