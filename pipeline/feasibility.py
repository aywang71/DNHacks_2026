"""S2: reachable-set geometry and paired-gap joint feasibility.

The module deliberately uses a small local planar frame for each pair rather
than a geometry package.  The frame is only used to optimise and draw the
reachable ellipses; input/output coordinates remain conventional lon/lat.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .geo import (
    KM_PER_DEG_LAT,
    KM_PER_DEG_LON_EQ,
    crosses_dateline,
    from_local,
    haversine_km,
    normalise_lon,
    to_local,
)
from .pair_t0 import pair_events


DERIVED = config.DERIVED


def _as_1d_float(value, name: str) -> np.ndarray:
    """Return a numeric one-dimensional array, accepting scalar fixtures."""

    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        array = array.reshape(1)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a scalar or one-dimensional array")
    return array


@dataclass
class Endpoints:
    """Endpoint arrays for one side of one or more candidate pairs.

    ``t0_h`` and ``t1_h`` are numeric hours on any shared origin.  Only their
    difference matters for a single side, while the shared origin is needed to
    compare arrival and departure times across the two sides.
    """

    lat0: np.ndarray
    lon0: np.ndarray
    t0_h: np.ndarray
    lat1: np.ndarray
    lon1: np.ndarray
    t1_h: np.ndarray
    v_kmh: np.ndarray

    def __post_init__(self) -> None:
        names = ("lat0", "lon0", "t0_h", "lat1", "lon1", "t1_h", "v_kmh")
        arrays = []
        for name in names:
            array = _as_1d_float(getattr(self, name), name)
            setattr(self, name, array)
            arrays.append(array)
        lengths = {array.size for array in arrays}
        if len(lengths) != 1:
            raise ValueError("all Endpoints fields must have the same length")

    def __len__(self) -> int:
        return int(self.lat0.size)


@dataclass
class JointFeasibility:
    """Maximum common dwell and its inferred meeting point for each pair."""

    tau_h: np.ndarray
    lon_star: np.ndarray
    lat_star: np.ndarray
    required_speed_kn: np.ndarray
    kin_plausibility: np.ndarray
    feasible: np.ndarray


def dwell_at(point_lon, point_lat, side: Endpoints) -> np.ndarray:
    """Return each side's maximum dwell time at a lon/lat point.

    This public convenience function uses the shared haversine primitive.  The
    joint optimiser below intentionally uses its documented local planar
    distances, which makes the grid and analytic ellipses internally
    consistent.
    """

    n_pairs = len(side)
    point_lon = np.asarray(point_lon, dtype=float)
    point_lat = np.asarray(point_lat, dtype=float)
    try:
        point_lon = np.broadcast_to(point_lon, (n_pairs,))
        point_lat = np.broadcast_to(point_lat, (n_pairs,))
    except ValueError as error:
        raise ValueError("point_lon and point_lat must broadcast to the endpoint length") from error

    distance = haversine_km(side.lat0, side.lon0, point_lat, point_lon)
    distance += haversine_km(point_lat, point_lon, side.lat1, side.lon1)
    travel_h = np.divide(
        distance,
        side.v_kmh,
        out=np.full(n_pairs, np.inf, dtype=float),
        where=side.v_kmh > 0,
    )
    return (side.t1_h - side.t0_h) - travel_h


def _ring_with_dateline(
    lat0,
    lon0,
    t0_h,
    lat1,
    lon1,
    t1_h,
    v_kmh,
    tau_min: float = config.TAU_MIN_H,
    n: int = 64,
) -> tuple[np.ndarray | None, bool]:
    """Build a ring and separately retain whether it crossed the dateline."""

    try:
        n_int = int(n)
    except (TypeError, ValueError) as error:
        raise ValueError("n must be an integer at least 3") from error
    if n_int < 3:
        raise ValueError("n must be an integer at least 3")

    values = np.asarray((lat0, lon0, t0_h, lat1, lon1, t1_h, v_kmh, tau_min), dtype=float)
    if not np.isfinite(values).all() or float(v_kmh) <= 0:
        return None, False

    duration_h = float(t1_h) - float(t0_h)
    # A parameter of an ellipse is half of its total major-axis length.
    a_axis = float(v_kmh) * (duration_h - float(tau_min)) / 2.0
    if a_axis <= 0:
        return None, False

    lat_c = (float(lat0) + float(lat1)) / 2.0
    # Average on an unwrapped longitude axis, anchored to the first endpoint.
    lon0_normal = float(normalise_lon(lon0))
    lon1_unwrapped = lon0_normal + float(((float(lon1) - lon0_normal + 180.0) % 360.0) - 180.0)
    lon_c = (lon0_normal + lon1_unwrapped) / 2.0
    x_foci, y_foci = to_local(
        np.asarray((lat0, lat1), dtype=float),
        np.asarray((lon0, lon1), dtype=float),
        lat_c,
        lon_c,
    )
    focal_distance = float(np.hypot(x_foci[1] - x_foci[0], y_foci[1] - y_foci[0]))
    c_axis = focal_distance / 2.0
    if a_axis <= c_axis:
        return None, False

    b_axis = float(np.sqrt(a_axis * a_axis - c_axis * c_axis))
    theta = np.linspace(0.0, 2.0 * np.pi, n_int, endpoint=False)
    major = a_axis * np.cos(theta)
    minor = b_axis * np.sin(theta)
    angle = float(np.arctan2(y_foci[1] - y_foci[0], x_foci[1] - x_foci[0]))
    x_mid = (x_foci[0] + x_foci[1]) / 2.0
    y_mid = (y_foci[0] + y_foci[1]) / 2.0
    x_ring = x_mid + major * np.cos(angle) - minor * np.sin(angle)
    y_ring = y_mid + major * np.sin(angle) + minor * np.cos(angle)
    lat_ring, lon_ring = from_local(x_ring, y_ring, lat_c, lon_c)
    ring = np.column_stack((lon_ring, lat_ring))
    if crosses_dateline(ring[:, 0]):
        return None, True
    return ring, False


def reachable_ring(
    lat0,
    lon0,
    t0_h,
    lat1,
    lon1,
    t1_h,
    v_kmh,
    tau_min: float = config.TAU_MIN_H,
    n: int = 64,
) -> np.ndarray | None:
    """Return a sampled reachable ellipse as ``(n, 2)`` ``[lon, lat]`` points.

    Degenerate ellipses and geometry which would be drawn across the dateline
    are deliberately omitted.  ``run`` records the latter condition in its
    output's ``dateline`` column.
    """

    ring, _ = _ring_with_dateline(lat0, lon0, t0_h, lat1, lon1, t1_h, v_kmh, tau_min, n)
    return ring


def _tau_on_grid(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    x_endpoints: np.ndarray,
    y_endpoints: np.ndarray,
    a: Endpoints,
    b: Endpoints,
) -> np.ndarray:
    """Evaluate joint dwell for a batch of local-frame grids."""

    def distance(x, y, endpoint: int) -> np.ndarray:
        return np.hypot(
            x - x_endpoints[endpoint, :, None, None],
            y - y_endpoints[endpoint, :, None, None],
        )

    a_arrive = a.t0_h[:, None, None] + distance(x_grid, y_grid, 0) / a.v_kmh[:, None, None]
    a_depart = a.t1_h[:, None, None] - distance(x_grid, y_grid, 1) / a.v_kmh[:, None, None]
    b_arrive = b.t0_h[:, None, None] + distance(x_grid, y_grid, 2) / b.v_kmh[:, None, None]
    b_depart = b.t1_h[:, None, None] - distance(x_grid, y_grid, 3) / b.v_kmh[:, None, None]
    return np.minimum(a_depart, b_depart) - np.maximum(a_arrive, b_arrive)


def _best_grid_point(
    x_values: np.ndarray,
    y_values: np.ndarray,
    x_endpoints: np.ndarray,
    y_endpoints: np.ndarray,
    a: Endpoints,
    b: Endpoints,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find the maximum tau cell for a batch of x/y grid coordinate arrays."""

    # x_values and y_values have shape (pair, grid), and indexing x then y
    # gives a compact (pair, grid, grid) tensor without meshgrid allocation.
    tau = _tau_on_grid(
        x_values[:, :, None],
        y_values[:, None, :],
        x_endpoints,
        y_endpoints,
        a,
        b,
    )
    n_pairs, n_grid, _ = tau.shape
    flattened = tau.reshape(n_pairs, -1)
    finite = np.isfinite(flattened)
    index = np.where(finite, flattened, -np.inf).argmax(axis=1)
    rows = np.arange(n_pairs)
    best_tau = flattened[rows, index]
    best_tau[~finite.any(axis=1)] = np.nan
    x_index = index // n_grid
    y_index = index % n_grid
    return best_tau, x_values[rows, x_index], y_values[rows, y_index]


def _joint_feasibility_chunk(a: Endpoints, b: Endpoints, n_grid: int, tau_min: float) -> JointFeasibility:
    """Vectorised coarse grid plus one refinement pass for a pair batch."""

    n_pairs = len(a)
    lats = np.stack((a.lat0, a.lat1, b.lat0, b.lat1))
    # Keep all four longitudes continuous with side A's shutoff as the anchor.
    lon_anchor = normalise_lon(a.lon0)
    raw_lons = np.stack((a.lon0, a.lon1, b.lon0, b.lon1))
    lons = lon_anchor[None, :] + ((raw_lons - lon_anchor[None, :] + 180.0) % 360.0) - 180.0
    lat_c = np.mean(lats, axis=0)
    lon_c = np.mean(lons, axis=0)
    kx = KM_PER_DEG_LON_EQ * np.cos(np.radians(lat_c))
    ky = KM_PER_DEG_LAT
    # The formula below is the vectorised equivalent of geo.to_local for the
    # per-pair frame centres above.  It is kept here to batch 18k loose pairs.
    x_endpoints = (lons - lon_c[None, :]) * kx[None, :]
    y_endpoints = (lats - lat_c[None, :]) * ky

    x_min = np.nanmin(x_endpoints, axis=0)
    x_max = np.nanmax(x_endpoints, axis=0)
    y_min = np.nanmin(y_endpoints, axis=0)
    y_max = np.nanmax(y_endpoints, axis=0)
    extent = np.maximum(x_max - x_min, y_max - y_min)
    padding = 0.25 * extent + 20.0
    x_min -= padding
    x_max += padding
    y_min -= padding
    y_max += padding

    fractions = np.linspace(0.0, 1.0, n_grid)
    x_grid = x_min[:, None] + (x_max - x_min)[:, None] * fractions[None, :]
    y_grid = y_min[:, None] + (y_max - y_min)[:, None] * fractions[None, :]
    _, coarse_x, coarse_y = _best_grid_point(x_grid, y_grid, x_endpoints, y_endpoints, a, b)

    # Refine with the same number of grid cells over one coarse cell in every
    # direction, as prescribed by the stage contract.
    x_cell = (x_max - x_min) / (n_grid - 1)
    y_cell = (y_max - y_min) / (n_grid - 1)
    refine_fraction = np.linspace(-1.0, 1.0, n_grid)
    x_refined = coarse_x[:, None] + x_cell[:, None] * refine_fraction[None, :]
    y_refined = coarse_y[:, None] + y_cell[:, None] * refine_fraction[None, :]
    tau_h, x_star, y_star = _best_grid_point(
        x_refined,
        y_refined,
        x_endpoints,
        y_endpoints,
        a,
        b,
    )

    distance_a = np.hypot(x_star - x_endpoints[0], y_star - y_endpoints[0])
    distance_a += np.hypot(x_star - x_endpoints[1], y_star - y_endpoints[1])
    distance_b = np.hypot(x_star - x_endpoints[2], y_star - y_endpoints[2])
    distance_b += np.hypot(x_star - x_endpoints[3], y_star - y_endpoints[3])
    duration_a = a.t1_h - a.t0_h
    duration_b = b.t1_h - b.t0_h
    speed_a = np.divide(
        distance_a,
        duration_a * config.KM_PER_KN_H,
        out=np.full(n_pairs, np.inf, dtype=float),
        where=duration_a > 0,
    )
    speed_b = np.divide(
        distance_b,
        duration_b * config.KM_PER_KN_H,
        out=np.full(n_pairs, np.inf, dtype=float),
        where=duration_b > 0,
    )
    required_speed_kn = np.maximum(speed_a, speed_b)
    cap_kn = np.minimum(a.v_kmh, b.v_kmh) / config.KM_PER_KN_H
    kin_plausibility = np.clip(
        1.0 - np.divide(
            required_speed_kn,
            cap_kn,
            out=np.full(n_pairs, np.inf, dtype=float),
            where=cap_kn > 0,
        ),
        0.0,
        1.0,
    )
    lat_star = lat_c + y_star / ky
    lon_star = normalise_lon(lon_c + x_star / kx)
    finite_geometry = np.isfinite(tau_h) & np.isfinite(lon_star) & np.isfinite(lat_star)
    feasible = finite_geometry & (tau_h >= float(tau_min))
    return JointFeasibility(
        tau_h=tau_h,
        lon_star=lon_star,
        lat_star=lat_star,
        required_speed_kn=required_speed_kn,
        kin_plausibility=kin_plausibility,
        feasible=feasible,
    )


def joint_feasibility(
    a: Endpoints,
    b: Endpoints,
    n_grid: int = 15,
    tau_min: float = config.TAU_MIN_H,
) -> JointFeasibility:
    """Find the maximum joint dwell point for each pair of endpoint records.

    A bounded batch size keeps the loose-rule computation fast without holding
    many full pair-by-grid tensors in memory at once.
    """

    try:
        n_grid = int(n_grid)
    except (TypeError, ValueError) as error:
        raise ValueError("n_grid must be an integer at least 2") from error
    if n_grid < 2:
        raise ValueError("n_grid must be an integer at least 2")
    if len(a) != len(b):
        raise ValueError("a and b must contain the same number of pairs")
    n_pairs = len(a)
    if n_pairs == 0:
        empty = np.empty(0, dtype=float)
        return JointFeasibility(empty, empty.copy(), empty.copy(), empty.copy(), empty.copy(), np.empty(0, dtype=bool))

    outputs: list[JointFeasibility] = []
    # 2,048 * 15 * 15 points leaves ample headroom for the four planar distance
    # tensors while retaining vectorised performance for the 18,775 loose pairs.
    batch_size = 2_048
    for start in range(0, n_pairs, batch_size):
        stop = min(start + batch_size, n_pairs)
        a_batch = Endpoints(
            a.lat0[start:stop], a.lon0[start:stop], a.t0_h[start:stop],
            a.lat1[start:stop], a.lon1[start:stop], a.t1_h[start:stop], a.v_kmh[start:stop],
        )
        b_batch = Endpoints(
            b.lat0[start:stop], b.lon0[start:stop], b.t0_h[start:stop],
            b.lat1[start:stop], b.lon1[start:stop], b.t1_h[start:stop], b.v_kmh[start:stop],
        )
        outputs.append(_joint_feasibility_chunk(a_batch, b_batch, n_grid, float(tau_min)))

    return JointFeasibility(
        tau_h=np.concatenate([part.tau_h for part in outputs]),
        lon_star=np.concatenate([part.lon_star for part in outputs]),
        lat_star=np.concatenate([part.lat_star for part in outputs]),
        required_speed_kn=np.concatenate([part.required_speed_kn for part in outputs]),
        kin_plausibility=np.concatenate([part.kin_plausibility for part in outputs]),
        feasible=np.concatenate([part.feasible for part in outputs]),
    )


def _valid_sorted_events(events: pd.DataFrame) -> pd.DataFrame:
    """Match the positional order documented by pair_t0.pair_events."""

    return events.loc[events["mmsi_valid"].fillna(False)].sort_values("t0", kind="stable").reset_index(drop=True)


def _event_rows(events: pd.DataFrame, gap_ids: pd.Series) -> pd.DataFrame:
    """Resolve candidate gap ids against the canonical normalised event rows."""

    indexed = events.set_index("gap_id", drop=False, verify_integrity=True)
    rows = indexed.reindex(pd.Index(gap_ids.astype("string")))
    missing = rows["gap_id"].isna()
    if missing.any():
        example = gap_ids.loc[missing].astype(str).head(3).tolist()
        raise KeyError(f"candidate references gap_id values absent from gap_events: {example}")
    return rows.reset_index(drop=True)


def _speed_kmh(rows: pd.DataFrame) -> np.ndarray:
    """Use normalised class speed if available, with a config-backed fallback."""

    if "v_kmh" in rows:
        return rows["v_kmh"].to_numpy(dtype=float)
    vessel_class = rows.get("vessel_class", pd.Series(index=rows.index, dtype="object"))
    return vessel_class.map(config.class_speed_kn).to_numpy(dtype=float) * config.KM_PER_KN_H


def _sides_from_rows(rows_a: pd.DataFrame, rows_b: pd.DataFrame) -> tuple[Endpoints, Endpoints]:
    """Build sides with time as UTC-safe numeric hours on one common origin."""

    if len(rows_a) != len(rows_b):
        raise ValueError("paired event row sets must have equal length")
    if rows_a.empty:
        empty = np.empty(0, dtype=float)
        return Endpoints(empty, empty, empty, empty, empty, empty, empty), Endpoints(
            empty, empty, empty, empty, empty, empty, empty
        )
    all_times = pd.concat(
        [
            pd.to_datetime(rows_a["t0"], utc=True),
            pd.to_datetime(rows_a["t1"], utc=True),
            pd.to_datetime(rows_b["t0"], utc=True),
            pd.to_datetime(rows_b["t1"], utc=True),
        ],
        ignore_index=True,
    )
    origin = all_times.min()

    def hours(series: pd.Series) -> np.ndarray:
        # Timedelta division preserves pandas 3's datetime64[us, UTC] meaning.
        return ((pd.to_datetime(series, utc=True) - origin) / pd.Timedelta(hours=1)).to_numpy(dtype=float)

    def side(rows: pd.DataFrame) -> Endpoints:
        return Endpoints(
            lat0=rows["lat0"].to_numpy(dtype=float),
            lon0=rows["lon0"].to_numpy(dtype=float),
            t0_h=hours(rows["t0"]),
            lat1=rows["lat1"].to_numpy(dtype=float),
            lon1=rows["lon1"].to_numpy(dtype=float),
            t1_h=hours(rows["t1"]),
            v_kmh=_speed_kmh(rows),
        )

    return side(rows_a), side(rows_b)


def _ring_json(ring: np.ndarray | None) -> str | None:
    if ring is None:
        return None
    return json.dumps(ring.tolist(), separators=(",", ":"))


def _operating_output(candidates: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Calculate all operating-pair fields, including display rings."""

    output_columns = [
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
    ]
    if candidates.empty:
        return pd.DataFrame({column: pd.Series(dtype="object") for column in output_columns})

    rows_a = _event_rows(events, candidates["gap_id_a"])
    rows_b = _event_rows(events, candidates["gap_id_b"])
    side_a, side_b = _sides_from_rows(rows_a, rows_b)
    result = joint_feasibility(side_a, side_b, tau_min=config.TAU_MIN_H)

    candidate_dateline = (
        candidates["dateline"].fillna(False).to_numpy(dtype=bool)
        if "dateline" in candidates
        else np.zeros(len(candidates), dtype=bool)
    )
    rings_a: list[str | None] = []
    rings_b: list[str | None] = []
    dateline = candidate_dateline.copy()
    for index in range(len(candidates)):
        # The output contract omits all estimated geometry for an endpoint set
        # that already straddles the dateline.
        if dateline[index]:
            rings_a.append(None)
            rings_b.append(None)
            continue
        ring_a, ring_a_dateline = _ring_with_dateline(
            side_a.lat0[index], side_a.lon0[index], side_a.t0_h[index],
            side_a.lat1[index], side_a.lon1[index], side_a.t1_h[index], side_a.v_kmh[index],
            config.TAU_MIN_H,
        )
        ring_b, ring_b_dateline = _ring_with_dateline(
            side_b.lat0[index], side_b.lon0[index], side_b.t0_h[index],
            side_b.lat1[index], side_b.lon1[index], side_b.t1_h[index], side_b.v_kmh[index],
            config.TAU_MIN_H,
        )
        if ring_a_dateline or ring_b_dateline:
            dateline[index] = True
            rings_a.append(None)
            rings_b.append(None)
        else:
            rings_a.append(_ring_json(ring_a))
            rings_b.append(_ring_json(ring_b))

    return pd.DataFrame(
        {
            "pair_id": candidates["pair_id"].astype("string").to_numpy(),
            "tau_h": result.tau_h,
            "lon_star": result.lon_star,
            "lat_star": result.lat_star,
            "required_speed_kn": result.required_speed_kn,
            "kin_plausibility": result.kin_plausibility,
            "feasible": result.feasible,
            "ring_a": rings_a,
            "ring_b": rings_b,
            "dateline": dateline,
        }
    )[output_columns]


def _loose_count(events: pd.DataFrame) -> tuple[int, int]:
    """Rebuild loose pairs and return its pre-registered feasibility counts."""

    pairs = pair_events(events, **config.LOOSE)
    if pairs.empty:
        return 0, 0
    ordered = _valid_sorted_events(events)
    positions_a = pairs["i"].to_numpy(dtype=np.int64)
    positions_b = pairs["j"].to_numpy(dtype=np.int64)
    side_a, side_b = _sides_from_rows(
        ordered.iloc[positions_a].reset_index(drop=True),
        ordered.iloc[positions_b].reset_index(drop=True),
    )
    result = joint_feasibility(side_a, side_b, tau_min=config.TAU_MIN_H)
    return int(len(pairs)), int(result.feasible.sum())


def run() -> None:
    """Write operating geometry and the loose-rule methods-drawer result."""

    events = pd.read_parquet(DERIVED / "gap_events.parquet")
    candidates = pd.read_parquet(DERIVED / "candidates_t0.parquet")
    feasibility = _operating_output(candidates, events)
    DERIVED.mkdir(parents=True, exist_ok=True)
    feasibility.to_parquet(DERIVED / "feasibility.parquet", index=False)

    loose, loose_feasible = _loose_count(events)
    (DERIVED / "loose_feasibility.json").write_text(
        json.dumps({"loose": loose, "feasible_at_tau_min": loose_feasible}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[feasibility] "
        f"operating={len(feasibility)} feasible={int(feasibility['feasible'].sum())} "
        f"loose={loose} loose_feasible={loose_feasible}"
    )
