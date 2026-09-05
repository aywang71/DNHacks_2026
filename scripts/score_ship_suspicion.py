#!/usr/bin/env python3
"""Score a model-ready vessel-window feature table."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=Path("output/models/ship_suspicion/ship_suspicion_model.joblib"))
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--anchor-date", help="Optional ISO date selecting one scoring batch")
    args = parser.parse_args()

    bundle = joblib.load(args.model)
    frame = pd.read_parquet(args.features)
    if args.anchor_date:
        anchors = pd.to_datetime(frame["anchor_date"], utc=True)
        frame = frame.loc[anchors.dt.date == pd.Timestamp(args.anchor_date).date()].copy()
    missing = sorted(set(bundle["features"]) - set(frame.columns))
    if missing:
        raise ValueError(f"Feature table is missing model inputs: {missing}")
    identifiers = [column for column in ("vessel_id", "gfw_vessel_id", "mmsi", "anchor_date") if column in frame]
    output = frame[identifiers].copy()
    output["suspicion_score"] = bundle["model"].predict_proba(frame[bundle["features"]])[:, 1]
    output = output.sort_values("suspicion_score", ascending=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"Scored {len(output)} vessel windows -> {args.output}")


if __name__ == "__main__":
    main()
