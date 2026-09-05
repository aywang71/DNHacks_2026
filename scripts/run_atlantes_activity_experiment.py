"""Run Atlantes' published activity model on prepared Presence experiment tracks.

This deliberately bypasses the Atlantes production service: the input is GFW
Presence, not raw AIS, and must remain an offline compatibility experiment.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


EXPECTED_POSITION_SEMANTICS = "gfw_presence_grid_center_hourly"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the published ATLAS activity model on experimental GFW Presence tracks."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--atlantes-src",
        type=Path,
        default=Path("background/atlantes/ais/src"),
        help="Path to the checked-out Atlantes ais/src directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/silver/atlantes_presence_experimental/activity_predictions.json"),
    )
    parser.add_argument("--max-tracks", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_tracks < 1:
        raise ValueError("--max-tracks must be at least 1")
    if not args.input.is_file():
        raise FileNotFoundError(f"Prepared ATLAS track file does not exist: {args.input}")
    if not args.atlantes_src.is_dir():
        raise FileNotFoundError(f"Atlantes source directory does not exist: {args.atlantes_src}")

    tracks = pd.read_parquet(args.input)
    required = {
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
        "source_position_semantics",
    }
    missing = sorted(required.difference(tracks.columns))
    if missing:
        raise ValueError(f"Prepared ATLAS track file is missing: {missing}")
    if not tracks["source_position_semantics"].eq(EXPECTED_POSITION_SEMANTICS).all():
        raise ValueError("Refusing input that is not explicitly labelled GFW hourly Presence")

    # Import the unmodified published code only after its local source location
    # is configured. It needs a separate environment because it pins Python 3.10.
    sys.path.insert(0, str(args.atlantes_src.resolve()))
    from atlantes.inference.atlas_activity.model import AtlasActivityModel
    from atlantes.inference.atlas_activity.preprocessor import AtlasActivityPreprocessor

    model = AtlasActivityModel()
    predictions: list[dict[str, object]] = []
    for track_id, track in tracks.groupby("trackId", sort=True):
        if len(predictions) >= args.max_tracks:
            break
        clean_track = track.sort_values("send", kind="stable").copy()
        # Pandera in Atlantes validates MMSI as numeric. Adapter values are
        # strings only to preserve a missing GFW MMSI as an explicit "0".
        clean_track["mmsi"] = pd.to_numeric(clean_track["mmsi"], errors="coerce").fillna(0).astype("int64")
        preprocessed = AtlasActivityPreprocessor.preprocess(clean_track)
        output = model.run_inference([preprocessed])
        if len(output) != 1:
            raise RuntimeError(f"ATLAS returned {len(output)} predictions for {track_id}")
        activity_class, details, metadata = output[0]
        predictions.append(
            {
                "track_id": str(track_id),
                "source_vessel_id": str(clean_track["source_vessel_id"].iloc[0]),
                "points_used": len(clean_track),
                "start": pd.Timestamp(clean_track["send"].iloc[0]).isoformat(),
                "end": pd.Timestamp(clean_track["send"].iloc[-1]).isoformat(),
                "raw_activity_class": activity_class.name.lower(),
                "confidence": float(details["confidence"]),
                "class_probabilities": {
                    name: float(probability)
                    for name, probability in zip(
                        ("fishing", "anchored", "moored", "transiting"), details["outputs"]
                    )
                },
                "model_id": str(details["model"]),
                "model_version": str(details["model_version"]),
                "model_track_length": int(metadata["track_length"]),
            }
        )

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "not_raw_ais": True,
        "not_rendezvous_evidence": True,
        "distribution_shift_warning": (
            "ATLAS was designed for AIS trajectories. Input positions are GFW hourly "
            "grid-cell centres; motion and coast-distance fields are derived."
        ),
        "source_position_semantics": EXPECTED_POSITION_SEMANTICS,
        "input": str(args.input),
        "atlantes_source": str(args.atlantes_src),
        "prediction_count": len(predictions),
        "predictions": predictions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
