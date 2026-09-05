"""Stage 2: deterministic two-ended (and start-only) pairing of dark events.

Run: .venv/bin/python -m pipeline.pair
"""
import hashlib
import json
import time

import numpy as np
import pandas as pd

from pipeline.config import (
    GAP_EVENTS_PARQUET, PAIR_CANDIDATES_PARQUET, PAIR_CANDIDATES_LOOSE_PARQUET,
    PAIR_GRID_JSON, THRESHOLD_GRID, OPERATING_THRESHOLD, LOOSE_THRESHOLD,
    SEQUENTIAL_MMSI_MAX_DELTA,
)
from pipeline.pairing import compute_pairs, brute_force_pairs


def load_valid_events():
    df = pd.read_parquet(GAP_EVENTS_PARQUET)
    df = df[df["mmsi_valid"]].reset_index(drop=True)
    arrays = dict(
        off_hours=df["gap_start_timestamp"].values.astype("int64") / 3.6e12,
        on_hours=df["gap_end_timestamp"].values.astype("int64") / 3.6e12,
        s_lat=df["gap_start_lat"].values.astype(np.float64),
        s_lon=df["gap_start_lon"].values.astype(np.float64),
        e_lat=df["gap_end_lat"].values.astype(np.float64),
        e_lon=df["gap_end_lon"].values.astype(np.float64),
        mmsi=df["mmsi"].values,
    )
    return df, arrays


def validate_against_brute_force(df, arrays, n_sample=1500, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(df), size=min(n_sample, len(df)), replace=False)
    idx.sort()
    sub = {k: v[idx] for k, v in arrays.items()}
    results = {}
    for D, T in [(10, 1), (25, 3)]:
        res = compute_pairs(sub["off_hours"], sub["on_hours"], sub["s_lat"], sub["s_lon"],
                             sub["e_lat"], sub["e_lon"], sub["mmsi"], D, T, "both_ends", True)
        fast_pairs = set(zip(res["i_idx"].tolist(), res["j_idx"].tolist()))
        fast_pairs = {(min(a, b), max(a, b)) for a, b in fast_pairs}
        brute = brute_force_pairs(sub["off_hours"], sub["on_hours"], sub["s_lat"], sub["s_lon"],
                                   sub["e_lat"], sub["e_lon"], sub["mmsi"], D, T, "both_ends", True)
        brute = {(min(a, b), max(a, b)) for a, b in brute}
        match = fast_pairs == brute
        results[f"D{D}_T{T}"] = {"match": match, "n_fast": len(fast_pairs), "n_brute": len(brute)}
    return results


def build_pairs_df(df, arrays, D_km, T_hours, kind, require_overlap=True):
    res = compute_pairs(arrays["off_hours"], arrays["on_hours"], arrays["s_lat"], arrays["s_lon"],
                         arrays["e_lat"], arrays["e_lon"], arrays["mmsi"], D_km, T_hours, kind,
                         require_overlap)
    i_idx, j_idx = res["i_idx"], res["j_idx"]
    if len(i_idx) == 0:
        return pd.DataFrame()

    gap_id = df["gap_id"].values.astype(str)
    swap = gap_id[i_idx] > gap_id[j_idx]
    a_idx = np.where(swap, j_idx, i_idx)
    b_idx = np.where(swap, i_idx, j_idx)

    def col(name):
        return df[name].values

    out = pd.DataFrame({
        "gap_id_a": gap_id[a_idx],
        "gap_id_b": gap_id[b_idx],
        "mmsi_a": col("mmsi")[a_idx],
        "mmsi_b": col("mmsi")[b_idx],
        "flag_a": col("flag")[a_idx],
        "flag_b": col("flag")[b_idx],
        "vessel_class_a": col("vessel_class")[a_idx],
        "vessel_class_b": col("vessel_class")[b_idx],
        "start_distance_km": res["start_dist_km"],
        "start_delta_minutes": res["off_delta_hours"] * 60.0,
        "duration_a": col("duration_hours_exact")[a_idx],
        "duration_b": col("duration_hours_exact")[b_idx],
        "off_time_a": col("gap_start_timestamp")[a_idx],
        "off_time_b": col("gap_start_timestamp")[b_idx],
        "on_time_a": col("gap_end_timestamp")[a_idx],
        "on_time_b": col("gap_end_timestamp")[b_idx],
        "mean_start_distance_from_shore_km":
            (col("gap_start_distance_from_shore_m")[a_idx] + col("gap_start_distance_from_shore_m")[b_idx])
            / 2.0 / 1000.0,
    })
    if kind == "both_ends":
        out["end_distance_km"] = res["end_dist_km"]
        out["end_delta_minutes"] = res["on_delta_hours"] * 60.0
        out["dark_overlap_hours"] = res["overlap_hours"]
    else:
        out["end_distance_km"] = np.nan
        out["end_delta_minutes"] = np.nan
        out["dark_overlap_hours"] = np.nan

    out["duration_ratio"] = np.minimum(out["duration_a"], out["duration_b"]) / np.maximum(out["duration_a"], out["duration_b"])
    out["same_flag"] = out["flag_a"] == out["flag_b"]
    out["cross_flag"] = (out["flag_a"] != "") & (out["flag_b"] != "") & (out["flag_a"] != out["flag_b"])
    out["sequential_mmsi"] = (out["mmsi_a"] - out["mmsi_b"]).abs() <= SEQUENTIAL_MMSI_MAX_DELTA

    starts_a = np.column_stack([col("gap_start_lat")[a_idx], col("gap_start_lon")[a_idx]])
    starts_b = np.column_stack([col("gap_start_lat")[b_idx], col("gap_start_lon")[b_idx]])
    ends_a = np.column_stack([col("gap_end_lat")[a_idx], col("gap_end_lon")[a_idx]])
    ends_b = np.column_stack([col("gap_end_lat")[b_idx], col("gap_end_lon")[b_idx]])
    positions = []
    for sa, sb, ea, eb in zip(starts_a, starts_b, ends_a, ends_b):
        positions.append(json.dumps({
            "start_a": [round(float(sa[0]), 4), round(float(sa[1]), 4)],
            "start_b": [round(float(sb[0]), 4), round(float(sb[1]), 4)],
            "end_a": [round(float(ea[0]), 4), round(float(ea[1]), 4)],
            "end_b": [round(float(eb[0]), 4), round(float(eb[1]), 4)],
        }))
    out["positions"] = positions

    out["pair_id"] = [
        hashlib.sha1(f"{a}_{b}".encode()).hexdigest()[:12]
        for a, b in zip(out["gap_id_a"], out["gap_id_b"])
    ]

    cols = ["pair_id", "gap_id_a", "gap_id_b", "mmsi_a", "mmsi_b", "flag_a", "flag_b",
            "vessel_class_a", "vessel_class_b", "start_distance_km", "start_delta_minutes",
            "end_distance_km", "end_delta_minutes", "dark_overlap_hours",
            "duration_a", "duration_b", "duration_ratio", "same_flag", "cross_flag",
            "sequential_mmsi", "mean_start_distance_from_shore_km",
            "off_time_a", "off_time_b", "on_time_a", "on_time_b", "positions"]
    return out[cols]


def main():
    t0 = time.time()
    df, arrays = load_valid_events()
    print(f"[pair] {len(df)} mmsi-valid events loaded")

    val = validate_against_brute_force(df, arrays)
    print(f"[pair] brute-force validation on 1500-event subsample: {val}")
    if not all(v["match"] for v in val.values()):
        print("[pair] WARNING: brute-force validation MISMATCH -- investigate blocking logic")

    grid_counts = {}
    for spec in THRESHOLD_GRID:
        res = compute_pairs(arrays["off_hours"], arrays["on_hours"], arrays["s_lat"], arrays["s_lon"],
                             arrays["e_lat"], arrays["e_lon"], arrays["mmsi"],
                             spec["D_km"], spec["T_hours"], spec["kind"],
                             require_overlap=(spec["kind"] == "both_ends"))
        n_pairs = len(res["i_idx"])
        vessels = set(arrays["mmsi"][res["i_idx"]].tolist()) | set(arrays["mmsi"][res["j_idx"]].tolist())
        grid_counts[spec["name"]] = {"D_km": spec["D_km"], "T_hours": spec["T_hours"],
                                      "kind": spec["kind"], "n_pairs": int(n_pairs),
                                      "n_vessels": len(vessels)}
        print(f"[pair] {spec['name']}: pairs={n_pairs} vessels={len(vessels)}")

    with open(PAIR_GRID_JSON, "w") as f:
        json.dump({"validation": val, "grid": grid_counts}, f, indent=2)

    op = OPERATING_THRESHOLD
    op_df = build_pairs_df(df, arrays, op["D_km"], op["T_hours"], op["kind"], True)
    op_df.to_parquet(PAIR_CANDIDATES_PARQUET, index=False)
    print(f"[pair] operating threshold ({op['D_km']}km/{op['T_hours']}h): {len(op_df)} pairs -> {PAIR_CANDIDATES_PARQUET}")

    loose = LOOSE_THRESHOLD
    loose_df = build_pairs_df(df, arrays, loose["D_km"], loose["T_hours"], loose["kind"],
                               loose.get("require_overlap", True))
    loose_df.to_parquet(PAIR_CANDIDATES_LOOSE_PARQUET, index=False)
    print(f"[pair] loose threshold ({loose['D_km']}km/{loose['T_hours']}h): {len(loose_df)} pairs -> {PAIR_CANDIDATES_LOOSE_PARQUET}")

    print(f"[pair] done in {time.time()-t0:.2f}s")


if __name__ == "__main__":
    main()
