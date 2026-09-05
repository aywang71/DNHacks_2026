#!/usr/bin/env python3
"""Train the seven-day ship suspicion model on the repository data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dark_rendezvous.suspicion_model import TrainingConfig, train_from_paths


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--presence-root", type=Path, default=Path("data/silver/gfw_presence_hourly"))
    result.add_argument(
        "--gap-retrieval",
        type=Path,
        action="append",
        default=None,
        help="Complete intentional-only GFW retrieval root; repeat to add periods.",
    )
    result.add_argument("--ports", type=Path, default=Path("/Users/williampallan/Downloads/UpdatedPub150.csv"))
    result.add_argument("--output", type=Path, default=Path("output/models/ship_suspicion"))
    return result


def main() -> None:
    args = parser().parse_args()
    retrievals = args.gap_retrieval or [
        Path("data/bronze/gfw_gaps/retrieval_id=20260905T200519Z"),
        Path("data/bronze/gfw_gaps/retrieval_id=20260905T210748Z"),
    ]
    presence_paths = sorted(args.presence_root.rglob("points.parquet"))
    result = train_from_paths(
        presence_paths=presence_paths,
        gap_retrieval_roots=retrievals,
        ports_path=args.ports,
        output_dir=args.output,
        config=TrainingConfig(),
    )
    print(json.dumps({"metrics": result["metrics"], "anchors": [str(x.date()) for x in result["anchors"]]}, indent=2))


if __name__ == "__main__":
    main()
