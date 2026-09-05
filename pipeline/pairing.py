"""Core pair-finding logic, shared by pair.py (real data) and null.py (permutations).

All functions operate on plain numpy arrays indexed 0..n-1 that the caller
has already restricted to mmsi-valid rows and reset-indexed consistently.
"""
import numpy as np

from pipeline.geo import haversine_km, candidate_pairs_from_offtime


def compute_pairs(off_hours, on_hours, s_lat, s_lon, e_lat, e_lon, mmsi,
                   D_km, T_hours, kind, require_overlap=True):
    """Return a dict of numpy arrays describing all qualifying pairs.

    kind: "both_ends" (start AND end proximity + overlap) or "start_only".
    Uses off-time window blocking (candidate_pairs_from_offtime) then verifies
    every condition with vectorized haversine / time-delta checks, so results
    are exact (identical to brute force), not approximate.
    """
    off_hours = np.asarray(off_hours, dtype=np.float64)
    on_hours = np.asarray(on_hours, dtype=np.float64)
    mmsi = np.asarray(mmsi)

    i_idx, j_idx = candidate_pairs_from_offtime(off_hours, T_hours)
    empty = dict(i_idx=np.array([], dtype=np.int64), j_idx=np.array([], dtype=np.int64),
                 start_dist_km=np.array([]), off_delta_hours=np.array([]),
                 end_dist_km=np.array([]), on_delta_hours=np.array([]),
                 overlap_hours=np.array([]))
    if i_idx.size == 0:
        return empty

    keep = mmsi[i_idx] != mmsi[j_idx]
    i_idx, j_idx = i_idx[keep], j_idx[keep]
    if i_idx.size == 0:
        return empty

    off_delta = np.abs(off_hours[i_idx] - off_hours[j_idx])
    start_dist = haversine_km(s_lat[i_idx], s_lon[i_idx], s_lat[j_idx], s_lon[j_idx])
    keep = start_dist <= D_km
    i_idx, j_idx, off_delta, start_dist = i_idx[keep], j_idx[keep], off_delta[keep], start_dist[keep]
    if i_idx.size == 0:
        return empty

    if kind == "start_only":
        return dict(i_idx=i_idx, j_idx=j_idx, start_dist_km=start_dist, off_delta_hours=off_delta,
                    end_dist_km=None, on_delta_hours=None, overlap_hours=None)

    # both_ends
    end_dist = haversine_km(e_lat[i_idx], e_lon[i_idx], e_lat[j_idx], e_lon[j_idx])
    on_delta = np.abs(on_hours[i_idx] - on_hours[j_idx])
    overlap = (np.minimum(on_hours[i_idx], on_hours[j_idx])
               - np.maximum(off_hours[i_idx], off_hours[j_idx]))
    keep = (end_dist <= D_km) & (on_delta <= T_hours)
    if require_overlap:
        keep = keep & (overlap > 0)
    return dict(i_idx=i_idx[keep], j_idx=j_idx[keep],
                start_dist_km=start_dist[keep], off_delta_hours=off_delta[keep],
                end_dist_km=end_dist[keep], on_delta_hours=on_delta[keep],
                overlap_hours=overlap[keep])


def brute_force_pairs(off_hours, on_hours, s_lat, s_lon, e_lat, e_lon, mmsi,
                       D_km, T_hours, kind="both_ends", require_overlap=True):
    """O(n^2) reference implementation for validation on small subsamples."""
    n = len(off_hours)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if mmsi[i] == mmsi[j]:
                continue
            if abs(off_hours[i] - off_hours[j]) > T_hours:
                continue
            sd = haversine_km(np.array([s_lat[i]]), np.array([s_lon[i]]),
                               np.array([s_lat[j]]), np.array([s_lon[j]]))[0]
            if sd > D_km:
                continue
            if kind == "start_only":
                pairs.append((i, j))
                continue
            ed = haversine_km(np.array([e_lat[i]]), np.array([e_lon[i]]),
                               np.array([e_lat[j]]), np.array([e_lon[j]]))[0]
            if ed > D_km:
                continue
            if abs(on_hours[i] - on_hours[j]) > T_hours:
                continue
            if require_overlap and min(on_hours[i], on_hours[j]) - max(off_hours[i], off_hours[j]) <= 0:
                continue
            pairs.append((i, j))
    return set(pairs)
