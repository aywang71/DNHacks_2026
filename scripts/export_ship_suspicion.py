#!/usr/bin/env python3
"""Export the trained ship-suspicion snapshot as a static frontend asset.

The export intentionally uses the precomputed latest-anchor scores rather
than re-scoring at export time.  The model artifact was trained with an older
scikit-learn version, so contribution extraction is best effort: when that
artifact can be loaded and exposes a linear preprocessing pipeline, the five
largest signed transformed-feature contributions are emitted.  When it cannot
be safely loaded, ``topFeatures`` is an empty list rather than an invented
attribution.

The current training manifest has no explicit version or training timestamp.
The exporter therefore emits ``"unversioned"`` and the model artifact's UTC
modification time as an honest fallback until future training writes those
metadata fields.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping
import warnings

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    # Joblib records the custom PriorCorrectedClassifier by its package path.
    sys.path.insert(0, str(SRC))


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_timestamp(value: object) -> str | None:
    if value is None:
        return None
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _artifact_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _string(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _mmsi(value: object) -> str:
    """Format an MMSI as text without exposing CSV's incidental ``.0`` form."""

    text = _string(value)
    if text is None:
        return "unknown"
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isfinite(number) and number.is_integer():
        return str(int(number))
    return text


def _numeric_metrics(payload: Mapping[str, object], prefix: str = "") -> dict[str, float]:
    """Flatten JSON metrics while preserving only finite numeric leaves."""

    result: dict[str, float] = {}
    for key, value in payload.items():
        name = f"{prefix}_{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            result.update(_numeric_metrics(value, name))
        elif isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number):
                result[name] = number
    return result


def _model_metadata(manifest: Mapping[str, object], model_path: Path) -> tuple[str, str]:
    version = _string(manifest.get("version")) or _string(manifest.get("model_version")) or "unversioned"
    trained_at = (
        _iso_timestamp(manifest.get("trainedAt"))
        or _iso_timestamp(manifest.get("trained_at"))
        or _artifact_timestamp(model_path)
    )
    return version, trained_at


def _top_feature_contributions(
    model_path: Path,
    features: pd.DataFrame,
    feature_names: list[str],
) -> tuple[dict[str, list[dict[str, float | str]]], str | None]:
    """Return linear-model contribution lists keyed by vessel id when possible."""

    if features.empty:
        return {}, None
    try:
        import joblib

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bundle = joblib.load(model_path)
        model = bundle["model"]
        estimator = getattr(model, "estimator_", model)
        preprocessing = estimator.named_steps["preprocessing"]
        classifier = estimator.named_steps["classifier"]
        transformed = preprocessing.transform(features[feature_names])
        coefficients = np.asarray(classifier.coef_).reshape(-1)
        transformed_names = [str(name).split("__", 1)[-1] for name in preprocessing.get_feature_names_out()]
        if transformed.shape[1] != len(coefficients) or len(coefficients) != len(transformed_names):
            raise ValueError("model preprocessing and classifier coefficient shapes do not agree")

        output: dict[str, list[dict[str, float | str]]] = {}
        for position, (_, row) in enumerate(features.iterrows()):
            vector = np.asarray(transformed[position].toarray()).reshape(-1) if hasattr(transformed[position], "toarray") else np.asarray(transformed[position]).reshape(-1)
            contributions = vector * coefficients
            order = np.argsort(-np.abs(contributions), kind="stable")[:5]
            vessel_id = _string(row.get("vessel_id"))
            if vessel_id is None:
                continue
            output[vessel_id] = [
                {
                    "name": transformed_names[index],
                    # This is the fitted pipeline's transformed feature value,
                    # so it exactly matches the value used for the coefficient.
                    "value": float(vector[index]),
                    "contribution": float(contributions[index]),
                }
                for index in order
                if math.isfinite(float(vector[index])) and math.isfinite(float(contributions[index]))
            ]
        return output, None
    except Exception as error:  # Compatibility failures must not fabricate attributions.
        return {}, f"{type(error).__name__}: {error}"


def build_payload(
    model_dir: Path,
    *,
    max_vessels: int = 200,
) -> tuple[dict[str, object], str | None]:
    """Build the exact static envelope and return any contribution warning."""

    manifest_path = model_dir / "training_manifest.json"
    metrics_path = model_dir / "metrics.json"
    model_path = model_dir / "ship_suspicion_model.joblib"
    scores_path = model_dir / "latest_anchor_scores.csv"
    examples_path = model_dir / "training_examples.parquet"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping) or not isinstance(metrics, Mapping):
        raise ValueError("ship-suspicion manifest and metrics must be JSON objects")
    feature_names = [str(name) for name in manifest.get("features", [])]
    if not feature_names:
        raise ValueError("training_manifest.json has no model feature order")

    scores = pd.read_csv(scores_path, dtype={"mmsi": "string"})
    required_scores = {"vessel_id", "mmsi", "suspicion_score"}
    missing = sorted(required_scores.difference(scores.columns))
    if missing:
        raise ValueError(f"latest_anchor_scores.csv is missing columns: {missing}")
    scores["suspicion_score"] = pd.to_numeric(scores["suspicion_score"], errors="coerce")
    if scores["suspicion_score"].isna().any() or not scores["suspicion_score"].between(0.0, 1.0).all():
        raise ValueError("latest_anchor_scores.csv contains a score outside [0, 1]")

    examples = pd.read_parquet(examples_path)
    required_examples = {"vessel_id", "mmsi", "vessel_type", "anchor_date", *feature_names}
    missing = sorted(required_examples.difference(examples.columns))
    if missing:
        raise ValueError(f"training_examples.parquet is missing columns: {missing}")
    latest_anchor = pd.to_datetime(scores.get("anchor_date"), utc=True, errors="coerce").max()
    example_anchors = pd.to_datetime(examples["anchor_date"], utc=True, errors="coerce")
    latest_examples = examples.loc[example_anchors.eq(latest_anchor)].copy() if not pd.isna(latest_anchor) else examples.copy()
    latest_examples = latest_examples.drop_duplicates("vessel_id", keep="last")

    metadata_columns = list(dict.fromkeys(["vessel_id", "mmsi", "vessel_type", *feature_names]))
    metadata = latest_examples[metadata_columns].copy()
    ranked = scores.merge(metadata, on="vessel_id", how="left", suffixes=("", "_feature"), validate="one_to_one")
    ranked["_mmsi_sort"] = ranked["mmsi"].map(_mmsi)
    ranked = ranked.sort_values(["suspicion_score", "_mmsi_sort"], ascending=[False, True], kind="stable").head(max_vessels).reset_index(drop=True)

    contribution_features = ranked[["vessel_id", *feature_names]].dropna(subset=["vessel_id"]).copy()
    contributions, contribution_warning = _top_feature_contributions(model_path, contribution_features, feature_names)
    version, trained_at = _model_metadata(manifest, model_path)
    vessels: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
        vessel_id = _string(row.get("vessel_id"))
        vessels.append(
            {
                "mmsi": _mmsi(row.get("mmsi")),
                "name": None,
                # Flag identity was deliberately excluded from training and is
                # absent from the scoring table, so null is the honest value.
                "flag": None,
                "vesselClass": _string(row.get("vessel_type")),
                "score": float(row["suspicion_score"]),
                "rank": rank,
                "topFeatures": contributions.get(vessel_id or "", []),
            }
        )
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "generatedAt": _iso_now(),
        "model": {
            "name": "ship_suspicion",
            "version": version,
            "trainedAt": trained_at,
            "features": feature_names,
            "metrics": _numeric_metrics(metrics),
            "caveat": "This experimental score estimates a future GFW intentional-disabling label from past Presence features, not illegal conduct, and it did not meet a useful deployment threshold.",
        },
        "vessels": vessels,
    }
    return payload, contribution_warning


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "output" / "models" / "ship_suspicion")
    parser.add_argument("--out", type=Path, default=ROOT / "code" / "frontend" / "public" / "data" / "ship-suspicion.json")
    parser.add_argument("--max-vessels", type=int, default=200)
    args = parser.parse_args(argv)
    if args.max_vessels < 1 or args.max_vessels > 200:
        parser.error("--max-vessels must be between 1 and 200")

    payload, contribution_warning = build_payload(args.model_dir, max_vessels=args.max_vessels)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    suffix = f"; topFeatures unavailable ({contribution_warning})" if contribution_warning else ""
    print(f"[ship-suspicion-export] vessels={len(payload['vessels'])} out={args.out}{suffix}")


if __name__ == "__main__":
    main()
