"""Stage 1: load raw disabling-events CSV, clean/typecheck, flag invalid MMSIs.

Run: .venv/bin/python -m pipeline.load
"""
import json
import time

import numpy as np
import pandas as pd

from pipeline.config import (
    RAW_CSV, GAP_EVENTS_PARQUET, EXCLUSIONS_JSON,
    MMSI_DIGITS, MMSI_MID_MIN, MMSI_MID_MAX,
)


def compute_mmsi_valid(mmsi_series: pd.Series) -> pd.Series:
    s = mmsi_series.astype("int64").astype(str)
    right_len = s.str.len() == MMSI_DIGITS
    mid = pd.to_numeric(s.str[:3], errors="coerce")
    mid_ok = mid.between(MMSI_MID_MIN, MMSI_MID_MAX)
    return right_len & mid_ok.fillna(False)


def main():
    t0 = time.time()
    df = pd.read_csv(RAW_CSV)
    n_total = len(df)

    df["gap_start_timestamp"] = pd.to_datetime(df["gap_start_timestamp"], utc=True)
    df["gap_end_timestamp"] = pd.to_datetime(df["gap_end_timestamp"], utc=True)
    df["duration_hours_exact"] = (
        (df["gap_end_timestamp"] - df["gap_start_timestamp"]).dt.total_seconds() / 3600.0
    )
    df["mmsi_valid"] = compute_mmsi_valid(df["mmsi"])
    df["flag"] = df["flag"].fillna("").astype(str).str.strip()

    # sanity flags (kept, not dropped -- pairing stage excludes invalid mmsi only)
    n_neg_duration = int((df["duration_hours_exact"] <= 0).sum())
    n_dup_gap_id = int(df["gap_id"].duplicated().sum())
    n_blank_flag = int((df["flag"] == "").sum())
    n_invalid_mmsi = int((~df["mmsi_valid"]).sum())

    DERIVED = GAP_EVENTS_PARQUET.parent
    DERIVED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(GAP_EVENTS_PARQUET, index=False)

    exclusions = {
        "n_total_rows": n_total,
        "excluded_from_pairing": {
            "invalid_mmsi": n_invalid_mmsi,
        },
        "n_valid_for_pairing": int(df["mmsi_valid"].sum()),
        "other_data_quality_notes": {
            "negative_or_zero_duration": n_neg_duration,
            "duplicate_gap_id": n_dup_gap_id,
            "blank_flag": n_blank_flag,
        },
        "invalid_mmsi_share": round(n_invalid_mmsi / n_total, 4),
    }
    with open(EXCLUSIONS_JSON, "w") as f:
        json.dump(exclusions, f, indent=2)

    elapsed = time.time() - t0
    print(f"[load] rows={n_total} invalid_mmsi={n_invalid_mmsi} "
          f"({exclusions['invalid_mmsi_share']*100:.2f}%) valid_for_pairing={exclusions['n_valid_for_pairing']}")
    print(f"[load] wrote {GAP_EVENTS_PARQUET} and {EXCLUSIONS_JSON} in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
