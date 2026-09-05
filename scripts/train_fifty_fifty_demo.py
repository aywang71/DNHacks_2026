#!/usr/bin/env python3
"""Build a deterministic no-skill baseline near 50% TPR and 50% FPR."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


MASK = np.uint64(0xFFFFFFFFFFFFFFFF)


def splitmix64(values: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore"):
        z = (values + np.uint64(0x9E3779B97F4A7C15)) & MASK
        z = ((z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)) & MASK
        z = ((z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)) & MASK
        return z ^ (z >> np.uint64(31))


def confusion(y: np.ndarray, prediction: np.ndarray) -> tuple[int, int, int, int]:
    tp = int(np.sum((y == 1) & prediction))
    fp = int(np.sum((y == 0) & prediction))
    positives = int(np.sum(y == 1))
    negatives = int(np.sum(y == 0))
    return tp, fp, positives, negatives


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output/models/ship_suspicion/training_examples.parquet"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/models/ship_suspicion/fifty_fifty_demo"),
    )
    parser.add_argument("--max-seeds", type=int, default=100_000)
    args = parser.parse_args()

    frame = pd.read_parquet(args.input)
    y = frame["target"].to_numpy(dtype=np.int8)
    key_frame = frame[["vessel_id", "anchor_date"]].astype(str)
    base_hash = pd.util.hash_pandas_object(key_frame, index=False).to_numpy(dtype=np.uint64)
    desired_tp = int(np.sum(y == 1)) // 2
    desired_fp = int(np.sum(y == 0)) // 2

    selected = None
    for seed in range(args.max_seeds):
        hashed = splitmix64(base_hash ^ np.uint64(seed))
        prediction = hashed < np.uint64(1 << 63)
        tp, fp, positives, negatives = confusion(y, prediction)
        if tp == desired_tp and fp == desired_fp:
            selected = (seed, hashed, prediction, tp, fp, positives, negatives)
            break
    if selected is None:
        raise RuntimeError(f"No exact nearest-50/50 seed found in {args.max_seeds} seeds")

    seed, hashed, prediction, tp, fp, positives, negatives = selected
    score = 1.0 - hashed.astype(np.float64) / float(2**64 - 1)
    report = {
        "artifact_role": "deterministic random/no-skill demonstration",
        "seed_selected_on_training_labels": seed,
        "true_positives": tp,
        "false_positives": fp,
        "positives": positives,
        "negatives": negatives,
        "true_positive_rate": tp / positives,
        "false_positive_rate": fp / negatives,
        "balanced_accuracy": 0.5 * (tp / positives + (1 - fp / negatives)),
        "algorithm": "pandas row-key hash XOR selected seed, SplitMix64, threshold at 2^63",
        "scoring_inputs": ["vessel_id", "anchor_date"],
    }
    output = frame[["vessel_id", "anchor_date", "target"]].copy()
    output["random_score"] = score
    output["predicted_suspicious"] = prediction.astype(int)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "fifty_fifty_model.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    output.to_csv(args.output_dir / "fifty_fifty_predictions.csv", index=False)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
