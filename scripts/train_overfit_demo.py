#!/usr/bin/env python3
"""Train an intentionally memorizing demonstration model.

This artifact exists to demonstrate the gap between resubstitution metrics and
real vessel-held-out evaluation. It must not replace the production candidate.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from dark_rendezvous.suspicion_model import CATEGORICAL_FEATURES, NUMERIC_FEATURES


DEMO_NUMERIC = NUMERIC_FEATURES + ["anchor_ordinal"]
DEMO_CATEGORICAL = CATEGORICAL_FEATURES + ["vessel_id"]
DEMO_FEATURES = DEMO_NUMERIC + DEMO_CATEGORICAL


def estimator(seed: int) -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            ("numeric", SimpleImputer(strategy="median"), DEMO_NUMERIC),
            ("category", OneHotEncoder(handle_unknown="ignore"), DEMO_CATEGORICAL),
        ]
    )
    model = ExtraTreesClassifier(
        n_estimators=500,
        max_depth=None,
        min_samples_leaf=1,
        max_features=None,
        class_weight="balanced",
        bootstrap=False,
        n_jobs=-1,
        random_state=seed,
    )
    return Pipeline([("preprocessing", preprocessing), ("model", model)])


def top_one_percent(y: np.ndarray, scores: np.ndarray, anchors: np.ndarray) -> dict[str, float | int]:
    selected = []
    for anchor in np.unique(anchors):
        indexes = np.flatnonzero(anchors == anchor)
        count = max(1, math.ceil(len(indexes) * 0.01))
        selected.extend(indexes[np.argsort(-scores[indexes])[:count]])
    selected_array = np.asarray(selected, dtype=int)
    hits = int(y[selected_array].sum())
    return {
        "review_count": len(selected),
        "true_positives": hits,
        "precision": hits / len(selected),
        "recall": hits / int(y.sum()),
    }


def metrics(y: np.ndarray, scores: np.ndarray, anchors: np.ndarray) -> dict[str, object]:
    return {
        "average_precision": float(average_precision_score(y, scores)),
        "roc_auc": float(roc_auc_score(y, scores)),
        "top_1_percent_per_anchor": top_one_percent(y, scores, anchors),
    }


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
        default=Path("output/models/ship_suspicion/overfit_demo"),
    )
    parser.add_argument("--seed", type=int, default=17000)
    args = parser.parse_args()

    frame = pd.read_parquet(args.input)
    frame["anchor_ordinal"] = pd.to_datetime(frame["anchor_date"], utc=True).map(pd.Timestamp.toordinal)
    y = frame["target"].to_numpy(dtype=int)
    groups = frame["vessel_id"].astype(str).to_numpy()
    anchors = frame["anchor_date"].astype(str).to_numpy()

    final_model = estimator(args.seed)
    final_model.fit(frame[DEMO_FEATURES], y)
    training_scores = final_model.predict_proba(frame[DEMO_FEATURES])[:, 1]

    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=17)
    held_out_scores = np.full(len(frame), np.nan)
    held_out_folds = np.full(len(frame), -1)
    for fold, (train_index, test_index) in enumerate(splitter.split(frame, y, groups)):
        fold_model = estimator(args.seed + fold + 1)
        fold_model.fit(frame.iloc[train_index][DEMO_FEATURES], y[train_index])
        held_out_scores[test_index] = fold_model.predict_proba(frame.iloc[test_index][DEMO_FEATURES])[:, 1]
        held_out_folds[test_index] = fold

    report = {
        "artifact_role": "intentionally overfit demonstration; not deployable",
        "examples": len(frame),
        "positive_examples": int(y.sum()),
        "training_resubstitution": metrics(y, training_scores, anchors),
        "vessel_held_out": metrics(y, held_out_scores, anchors),
        "leakage_features": ["vessel_id", "anchor_ordinal"],
    }
    predictions = frame[["vessel_id", "anchor_date", "target"]].copy()
    predictions["overfit_training_score"] = training_scores
    predictions["vessel_held_out_score"] = held_out_scores
    predictions["held_out_fold"] = held_out_folds

    args.output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": final_model,
            "features": DEMO_FEATURES,
            "artifact_role": report["artifact_role"],
        },
        args.output_dir / "overfit_demo_model.joblib",
    )
    (args.output_dir / "overfit_metrics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    predictions.to_csv(args.output_dir / "overfit_predictions.csv", index=False)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
