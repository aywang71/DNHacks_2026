"""CLI for actual AIS ingestion and GFW derived-data retrieval."""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from .cli_support import json_hash, write_json
from .gfw_pull import pull_gap_windows
from .ingest import ingest_noaa_day, normalize_file
from .providers.gfw import GfwClient, normalize_gap_endpoints
from .storage import write_manifest, write_parquet


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from error


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        parsed = tuple(float(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("bbox must be min_lon,min_lat,max_lon,max_lat") from error
    if len(parsed) != 4:
        raise argparse.ArgumentTypeError("bbox must have four comma-separated numbers")
    return parsed  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dark-rendezvous")
    commands = parser.add_subparsers(dest="command", required=True)

    noaa = commands.add_parser("ingest-noaa", help="Download and normalize one NOAA daily AIS object")
    noaa.add_argument("--date", required=True, type=_parse_date)
    noaa.add_argument("--bronze-root", type=Path, default=Path("data/bronze"))
    noaa.add_argument("--silver-root", type=Path, default=Path("data/silver"))
    noaa.add_argument("--bbox", type=_parse_bbox)

    local = commands.add_parser("normalize-file", help="Normalize a raw AIS CSV or Parquet export")
    local.add_argument("--input", required=True, type=Path)
    local.add_argument("--source", required=True)
    local.add_argument("--collection-mode", choices=("satellite", "terrestrial", "mixed", "unknown"), default="unknown")
    local.add_argument("--dataset-version", default="unknown")
    local.add_argument("--silver-root", type=Path, default=Path("data/silver"))

    gaps = commands.add_parser("gfw-gaps", help="Fetch one page of derived GFW GAP events")
    gaps.add_argument("--start-date", required=True, type=_parse_date)
    gaps.add_argument("--end-date", required=True, type=_parse_date)
    gaps.add_argument("--offset", type=int, default=0)
    gaps.add_argument("--limit", type=int, default=100)
    gaps.add_argument("--output", type=Path, default=Path("data/bronze/gfw_gaps/response.json"))
    gaps.add_argument(
        "--normalized-output",
        type=Path,
        default=Path("data/silver/gfw_gap_endpoints/endpoints.parquet"),
    )

    pull = commands.add_parser("gfw-gaps-pull", help="Fetch and retain every GAP page in calendar windows")
    pull.add_argument("--start-date", required=True, type=_parse_date)
    pull.add_argument("--end-date", required=True, type=_parse_date)
    pull.add_argument("--window-days", type=int, default=31)
    pull.add_argument("--page-size", type=int, default=500)
    pull.add_argument("--max-pages", type=int)
    pull.add_argument(
        "--all-gaps",
        action="store_true",
        help="Include GFW GAP events regardless of its intentional-disabling classification.",
    )
    pull.add_argument("--bronze-root", type=Path, default=Path("data/bronze"))
    pull.add_argument("--silver-root", type=Path, default=Path("data/silver"))

    identity = commands.add_parser("gfw-identity", help="Fetch and save a GFW vessel-identity response")
    identity.add_argument("--query", required=True)
    identity.add_argument("--output", type=Path, default=Path("data/bronze/gfw_identity/response.json"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "ingest-noaa":
        output = ingest_noaa_day(
            day=args.date,
            bronze_root=args.bronze_root,
            silver_root=args.silver_root,
            bbox=args.bbox,
        )
        print(output)
        return
    if args.command == "normalize-file":
        output = normalize_file(
            input_path=args.input,
            source=args.source,
            silver_root=args.silver_root,
            collection_mode=args.collection_mode,
            dataset_version=args.dataset_version,
        )
        print(output)
        return
    token = os.environ.get("GFW_API_TOKEN", "")
    client = GfwClient(token)
    if args.command == "gfw-gaps":
        response = client.gap_events(
            start_date=args.start_date.isoformat(),
            end_date=args.end_date.isoformat(),
            offset=args.offset,
            limit=args.limit,
        )
        write_json(args.output, response)
        response_hash = json_hash(response)
        dataset_version = client.last_dataset_version or client.gaps_dataset
        endpoints = normalize_gap_endpoints(
            response,
            source_uri="https://gateway.api.globalfishingwatch.org/v3/events",
            raw_payload_hash=response_hash,
            dataset_version=dataset_version,
        )
        write_parquet(endpoints, args.normalized_output)
        write_manifest(
            args.normalized_output.with_name("manifest.json"),
            {
                "source": "global_fishing_watch_events",
                "source_uri": "https://gateway.api.globalfishingwatch.org/v3/events",
                "raw_response_path": str(args.output),
                "raw_response_sha256": response_hash,
                "normalized_path": str(args.normalized_output),
                "row_count": len(endpoints),
                "event_count": len(response.get("entries", [])),
                "next_offset": response.get("nextOffset"),
                "dataset_version": dataset_version,
            },
        )
        print(args.normalized_output)
        return
    if args.command == "gfw-gaps-pull":
        summary = pull_gap_windows(
            client,
            start=args.start_date,
            end=args.end_date,
            bronze_root=args.bronze_root,
            silver_root=args.silver_root,
            window_days=args.window_days,
            page_size=args.page_size,
            intentional_disabling=None if args.all_gaps else True,
            max_pages=args.max_pages,
        )
        print(summary.to_dict())
        return
    if args.command == "gfw-identity":
        write_json(args.output, client.search_identity(args.query))
        print(args.output)
        return
    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
