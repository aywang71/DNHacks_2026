"""Shared geographic primitives. Pure numpy, no geometry library.

Conventions: distances km, haversine with R = 6371 km, longitudes normalised
to [-180, 180] on every output, cells wrap at the dateline.
"""

from __future__ import annotations

import numpy as np

from .config import CELL_DEG, EARTH_R_KM

KM_PER_DEG_LAT = 110.57
KM_PER_DEG_LON_EQ = 111.32


def normalise_lon(lon):
    """Wrap longitudes into [-180, 180)."""
    return ((np.asarray(lon, dtype=float) + 180.0) % 360.0) - 180.0


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in km, vectorised over numpy arrays or scalars."""
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def cell_id(lat, lon, deg: float = CELL_DEG) -> np.ndarray:
    """Integer cell id = lon_index * 100 + lat_index; lon_index wraps at ±180.

    With deg = 5: lon_index in 0..71, lat_index in 0..35. Cells at 179.9 and
    -179.9 have lon indices 71 and 0, which are adjacent modulo 72.
    """
    lat = np.asarray(lat, dtype=float)
    lon = normalise_lon(lon)
    n_lon = int(round(360.0 / deg))
    lon_idx = (np.floor((lon + 180.0) / deg).astype(int)) % n_lon
    lat_idx = np.clip(np.floor((lat + 90.0) / deg).astype(int), 0, int(round(180.0 / deg)) - 1)
    return lon_idx * 100 + lat_idx


def local_frame(lat_c: float, lon_c: float) -> tuple[float, float]:
    """km per degree of longitude and latitude at the frame centre: (kx, ky)."""
    kx = KM_PER_DEG_LON_EQ * float(np.cos(np.radians(lat_c)))
    return kx, KM_PER_DEG_LAT


def to_local(lat, lon, lat_c: float, lon_c: float) -> tuple[np.ndarray, np.ndarray]:
    """Planar km offsets (x east, y north) from the centre; longitudes unwrapped
    relative to the centre so a frame spanning the dateline is continuous."""
    kx, ky = local_frame(lat_c, lon_c)
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    dlon = ((lon - lon_c + 180.0) % 360.0) - 180.0
    return dlon * kx, (lat - lat_c) * ky


def from_local(x, y, lat_c: float, lon_c: float) -> tuple[np.ndarray, np.ndarray]:
    """Inverse of to_local; returns (lat, lon) with lon normalised to [-180, 180)."""
    kx, ky = local_frame(lat_c, lon_c)
    lat = lat_c + np.asarray(y, dtype=float) / ky
    lon = normalise_lon(lon_c + np.asarray(x, dtype=float) / kx)
    return lat, lon


def crosses_dateline(lons) -> bool:
    """True when a set of normalised longitudes spans more than 180 degrees."""
    lons = normalise_lon(lons)
    if lons.size == 0:
        return False
    return bool(np.max(lons) - np.min(lons) > 180.0)
