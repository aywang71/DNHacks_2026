"""Prepare GFW hourly Presence rows for an explicitly experimental ATLAS run."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.ops import nearest_points
from shapely.strtree import STRtree


ATLANTES_REQUIRED_COLUMNS: tuple[str, ...] = (
    "lat",
    "lon",
    "send",
    "sog",
    "cog",
    "nav",
    "dist2coast",
    "name",
    "flag_code",
    "category",
    "trackId",
    "mmsi",
)
ATLANTES_ADAPTER_COLUMNS: tuple[str, ...] = (
    *ATLANTES_REQUIRED_COLUMNS,
    "source_vessel_id",
    "source_position_id",
    "source_position_semantics",
    "segment_number",
    "sog_semantics",
    "cog_semantics",
    "dist2coast_semantics",
    "nav_semantics",
    "category_semantics",
)


def _haversine_m(
    lat_a: np.ndarray, lon_a: np.ndarray, lat_b: np.ndarray, lon_b: np.ndarray
) -> np.ndarray:
    """Return great-circle distance in metres between paired WGS84 points."""
    earth_radius_m = 6_371_008.8
    lat_a_rad, lon_a_rad = np.radians(lat_a), np.radians(lon_a)
    lat_b_rad, lon_b_rad = np.radians(lat_b), np.radians(lon_b)
    haversine = np.sin((lat_b_rad - lat_a_rad) / 2) ** 2 + np.cos(lat_a_rad) * np.cos(
        lat_b_rad
    ) * np.sin((lon_b_rad - lon_a_rad) / 2) ** 2
    return 2 * earth_radius_m * np.arcsin(np.sqrt(haversine))


def _initial_bearing_deg(
    lat_a: np.ndarray, lon_a: np.ndarray, lat_b: np.ndarray, lon_b: np.ndarray
) -> np.ndarray:
    """Return initial bearings in degrees, from paired WGS84 points."""
    lat_a_rad, lon_a_rad = np.radians(lat_a), np.radians(lon_a)
    lat_b_rad, lon_b_rad = np.radians(lat_b), np.radians(lon_b)
    delta_lon = lon_b_rad - lon_a_rad
    y = np.sin(delta_lon) * np.cos(lat_b_rad)
    x = np.cos(lat_a_rad) * np.sin(lat_b_rad) - np.sin(lat_a_rad) * np.cos(
        lat_b_rad
    ) * np.cos(delta_lon)
    return (np.degrees(np.arctan2(y, x)) + 360) % 360


def coastline_distance_m(frame: pd.DataFrame, coastline_geojson: Path) -> pd.Series:
    """Estimate distance to a supplied coastline GeoJSON for each unique grid point.

    The method is deliberately explicit about its input coastline because coast
    distance materially affects ATLAS activity predictions. The nearest coast
    vertex/segment is chosen in WGS84 geometry space and the final distance is
    calculated with a great-circle formula. It is suitable for an experiment,
    not a replacement for the production coast-distance feature.
    """
    payload = json.loads(coastline_geojson.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    coastlines = [shape(feature["geometry"]) for feature in features if feature.get("geometry")]
    if not coastlines:
        raise ValueError(f"No coastline geometry found in {coastline_geojson}")
    tree = STRtree(coastlines)
    locations = frame.loc[:, ["lat", "lon"]].drop_duplicates().copy()
    distances: list[float] = []
    for lat, lon in locations.itertuples(index=False):
        point = Point(float(lon), float(lat))
        nearest = tree.nearest(point)
        nearest_geometry = coastlines[int(nearest)] if isinstance(nearest, (int, np.integer)) else nearest
        coast_point = nearest_points(point, nearest_geometry)[1]
        distances.append(
            float(
                _haversine_m(
                    np.array([float(lat)]),
                    np.array([float(lon)]),
                    np.array([coast_point.y]),
                    np.array([coast_point.x]),
                )[0]
            )
        )
    locations["dist2coast"] = distances
    distances_by_location = {
        (float(lat), float(lon)): float(distance)
        for lat, lon, distance in locations.itertuples(index=False)
    }
    # A Presence frame can be a filtered subset with non-contiguous source
    # indexes. Keep that index rather than relying on DataFrame.merge's new
    # RangeIndex, so assignment in the adapter remains one-for-one.
    return pd.Series(
        [distances_by_location[(float(lat), float(lon))] for lat, lon in frame[["lat", "lon"]].itertuples(index=False)],
        index=frame.index,
        name="dist2coast",
        dtype="float64",
    )


def adapt_gfw_presence_for_atlantes(
    presence: pd.DataFrame,
    *,
    dist2coast_m: pd.Series,
    max_gap_hours: float = 1.5,
    min_points: int = 100,
) -> pd.DataFrame:
    """Create ATLAS-shaped tracks from GFW hourly grid positions.

    ``sog`` and ``cog`` are calculated from successive hourly grid centres;
    they are not transmitted AIS fields. ``nav`` and ``category`` are required
    ATLAS schema placeholders because GFW Presence does not provide AIS
    navigation status or AIS ship-type code. Consequently this output is for
    a documented distribution-shift experiment, never production evidence.
    """
    if max_gap_hours <= 0:
        raise ValueError("max_gap_hours must be positive")
    if min_points < 2:
        raise ValueError("min_points must be at least 2")
    required = {"position_id", "vessel_id", "ts", "lat", "lon", "position_semantics"}
    missing = required.difference(presence.columns)
    if missing:
        raise ValueError(f"Presence frame is missing required columns: {sorted(missing)}")
    if not presence["position_semantics"].eq("gfw_presence_grid_center_hourly").all():
        raise ValueError("ATLAS adapter accepts only gfw_presence_grid_center_hourly rows")
    if len(dist2coast_m) != len(presence):
        raise ValueError("dist2coast_m must align one-for-one with the Presence frame")

    frame = presence.copy()
    frame["dist2coast"] = pd.to_numeric(dist2coast_m, errors="coerce")
    frame["send"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.loc[
        frame["send"].notna()
        & frame["lat"].between(-90, 90)
        & frame["lon"].between(-180, 180)
        & frame["vessel_id"].notna()
    ].copy()
    frame = frame.sort_values(["vessel_id", "send", "position_id"], kind="stable")
    frame = frame.drop_duplicates(["vessel_id", "send"], keep="first").reset_index(drop=True)

    elapsed_hours = frame.groupby("vessel_id", sort=False)["send"].diff().dt.total_seconds() / 3600
    frame["segment_number"] = (
        elapsed_hours.isna() | elapsed_hours.gt(max_gap_hours)
    ).groupby(frame["vessel_id"], sort=False).cumsum().sub(1).astype("int64")
    frame["trackId"] = (
        "gfw_presence:"
        + frame["vessel_id"].astype("string")
        + ":segment="
        + frame["segment_number"].astype("string")
    )

    previous = frame.groupby("trackId", sort=False)[["lat", "lon", "send"]].shift(1)
    seconds = (frame["send"] - previous["send"]).dt.total_seconds().to_numpy(dtype=float)
    distance_m = _haversine_m(
        previous["lat"].to_numpy(dtype=float),
        previous["lon"].to_numpy(dtype=float),
        frame["lat"].to_numpy(dtype=float),
        frame["lon"].to_numpy(dtype=float),
    )
    frame["sog"] = distance_m / seconds / 0.514444
    frame["cog"] = _initial_bearing_deg(
        previous["lat"].to_numpy(dtype=float),
        previous["lon"].to_numpy(dtype=float),
        frame["lat"].to_numpy(dtype=float),
        frame["lon"].to_numpy(dtype=float),
    )
    stationary = np.isfinite(distance_m) & np.isclose(distance_m, 0.0)
    frame.loc[stationary, "cog"] = 0.0
    frame["mmsi"] = frame.get("mmsi", pd.Series(pd.NA, index=frame.index)).astype("string").fillna("0")
    frame["name"] = frame.get("vessel_name", pd.Series(pd.NA, index=frame.index)).astype("string").fillna("UNKNOWN")
    frame["flag_code"] = frame.get("flag_state", pd.Series(pd.NA, index=frame.index)).astype("string").fillna("UNK")
    frame["nav"] = 15  # AIS "not defined"; GFW Presence does not expose nav status.
    frame["category"] = 0  # AIS "not available"; preserve GFW type separately in source data.
    frame["source_vessel_id"] = frame["vessel_id"]
    frame["source_position_id"] = frame["position_id"]
    frame["source_position_semantics"] = frame["position_semantics"]
    frame["sog_semantics"] = "derived_from_successive_hourly_grid_centres"
    frame["cog_semantics"] = "derived_from_successive_hourly_grid_centres; stationary=0"
    frame["dist2coast_semantics"] = "derived_from_supplied_coastline_geometry"
    frame["nav_semantics"] = "unavailable_from_gfw_presence; imputed_ais_not_defined"
    frame["category_semantics"] = "unavailable_from_gfw_presence; imputed_ais_not_available"

    sufficient_context = frame.groupby("trackId", sort=False)["trackId"].transform("size").ge(min_points)
    model_ready = (
        sufficient_context
        & frame["sog"].notna()
        & frame["cog"].notna()
        & frame["dist2coast"].notna()
    )
    return frame.loc[model_ready, ATLANTES_ADAPTER_COLUMNS].reset_index(drop=True)
