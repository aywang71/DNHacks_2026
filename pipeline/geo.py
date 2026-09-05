"""Vectorized geo/time helpers shared by pair.py, null.py, and features.py."""
import numpy as np

from pipeline.config import EARTH_RADIUS_KM


def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorized great-circle distance in km. Inputs are numpy arrays (degrees)."""
    lat1 = np.radians(np.asarray(lat1, dtype=np.float64))
    lat2 = np.radians(np.asarray(lat2, dtype=np.float64))
    dlat = lat2 - lat1
    dlon = np.radians(np.asarray(lon2, dtype=np.float64) - np.asarray(lon1, dtype=np.float64))
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arcsin(np.sqrt(a))
    return EARTH_RADIUS_KM * c


def candidate_pairs_from_offtime(off_hours, T_hours):
    """Time-window blocking: return (i_idx, j_idx), original-array positions,
    for every unordered pair whose off_hours differ by at most T_hours.
    Each pair is returned exactly once, with off_hours[i] <= off_hours[j].
    Fully vectorized (no python-level loop over events).
    """
    off_hours = np.asarray(off_hours, dtype=np.float64)
    n = off_hours.shape[0]
    order = np.argsort(off_hours, kind="mergesort")
    sorted_off = off_hours[order]

    # for sorted position p, upper[p] = first index with sorted_off > sorted_off[p]+T
    upper = np.searchsorted(sorted_off, sorted_off + T_hours, side="right")
    starts = np.arange(n) + 1
    counts = np.clip(upper - starts, 0, None)
    total = int(counts.sum())
    if total == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)

    i_pos = np.repeat(np.arange(n), counts)
    cum = np.cumsum(counts)
    group_start = cum - counts
    offset_within_group = np.arange(total) - np.repeat(group_start, counts)
    j_pos = np.repeat(starts, counts) + offset_within_group

    # map sorted positions back to original array indices
    i_idx = order[i_pos]
    j_idx = order[j_pos]
    return i_idx, j_idx
