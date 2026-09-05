"""CLI for actual AIS ingestion and GFW derived-data retrieval."""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timezone
from pathlib import Path

from .cli_support import json_hash, write_json
from .gfw_pull import pull_gap_windows
from .ingest import ingest_noaa_day, normalize_file
from .providers.gfw import GfwClient, normalize_gap_endpoints
from .providers.gfw_presence import (
    PRESENCE_POSITION_SEMANTICS,
    PRESENCE_SOURCE,
    normalize_presence_report,
    report_dataset_version,
)
from .providers.gfw_tracks import normalize_track_lines
from .storage import write_manifest, write_parquet


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from error


def _parse_utc_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError("timestamp must be ISO-8601, e.g. 2022-01-01T00:00:00Z") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset or Z")
    return parsed.astimezone(timezone.utc)


def _format_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _retrieval_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _gfw_api_token() -> str:
    """Get a GFW token without ever putting a local secret in source control.

    A process environment variable wins over an ignored ``.env`` file.  The
    latter lets the bundled PowerShell backfill runner work from a fresh shell
    without requiring a third-party dotenv dependency.
    """
    if token := os.environ.get("GFW_API_TOKEN"):
        return token

    repo_env = Path(__file__).resolve().parents[2] / ".env"
    candidates = (Path.cwd() / ".env", repo_env)
    for env_path in dict.fromkeys(candidates):
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", maxsplit=1)
            if name.strip() != "GFW_API_TOKEN":
                continue
            token = value.strip().strip("\"'")
            if token:
                return token
    return ""


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
        "--bronze-only",
        action="store_true",
        help="Retain API pages and manifests only; defer all Silver normalization.",
    )
    pull.add_argument(
        "--all-gaps",
        action="store_true",
        help="Include GFW GAP events regardless of its intentional-disabling classification.",
    )
    pull.add_argument("--bronze-root", type=Path, default=Path("data/bronze"))
    pull.add_argument("--silver-root", type=Path, default=Path("data/silver"))

    track = commands.add_parser("gfw-track", help="Fetch one GFW-derived vessel track at native returned detail")
    track.add_argument("--vessel-id", required=True)
    track.add_argument("--start-date", required=True, type=_parse_date)
    track.add_argument("--end-date", required=True, type=_parse_date)
    track.add_argument("--bronze-root", type=Path, default=Path("data/bronze"))
    track.add_argument("--silver-root", type=Path, default=Path("data/silver"))

    presence = commands.add_parser(
        "gfw-presence",
        help="Fetch one bounded GFW 4Wings AIS-Presence report and normalize hourly grid positions",
    )
    presence.add_argument("--start", required=True, type=_parse_utc_timestamp)
    presence.add_argument("--end", required=True, type=_parse_utc_timestamp)
    presence.add_argument("--region-id", required=True, type=int)
    presence.add_argument("--region-dataset", default="public-eez-areas")
    presence.add_argument("--spatial-resolution", choices=("HIGH", "LOW"), default="HIGH")
    presence.add_argument("--bronze-only", action="store_true")
    presence.add_argument(
        "--reuse-last-report",
        action="store_true",
        help="Recover the account's last GFW 4Wings report after a documented report timeout; verify it matches this request.",
    )
    presence.add_argument("--retrieval-id")
    presence.add_argument("--bronze-root", type=Path, default=Path("data/bronze"))
    presence.add_argument("--silver-root", type=Path, default=Path("data/silver"))

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
    token = _gfw_api_token()
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
            write_silver=not args.bronze_only,
        )
        print(summary.to_dict())
        return
    if args.command == "gfw-track":
        response = client.track_lines(
            vessel_id=args.vessel_id,
            start_date=args.start_date.isoformat(),
            end_date=args.end_date.isoformat(),
        )
        run_root = (
            args.bronze_root
            / "gfw_tracks"
            / f"gfw_vessel_id={args.vessel_id}"
            / f"start={args.start_date.isoformat()}"
            / f"end={args.end_date.isoformat()}"
        )
        raw_path = run_root / "track.lines.json"
        write_json(raw_path, response)
        response_hash = json_hash(response)
        dataset_version = client.last_dataset_version or client.tracks_dataset
        points = normalize_track_lines(
            response,
            gfw_vessel_id=args.vessel_id,
            source_uri=f"https://gateway.api.globalfishingwatch.org/v3/vessels/{args.vessel_id}/tracks",
            raw_payload_hash=response_hash,
            dataset_version=dataset_version,
        ).sort_values("ts", na_position="last")
        output = (
            args.silver_root
            / "gfw_track_points"
            / f"gfw_vessel_id={args.vessel_id}"
            / f"start={args.start_date.isoformat()}"
            / f"end={args.end_date.isoformat()}"
            / "points.parquet"
        )
        write_parquet(points, output)
        write_manifest(
            output.with_name("manifest.json"),
            {
                "source": "global_fishing_watch_track",
                "position_semantics": "gfw_derived_track",
                "source_uri": f"https://gateway.api.globalfishingwatch.org/v3/vessels/{args.vessel_id}/tracks",
                "gfw_vessel_id": args.vessel_id,
                "requested_start": args.start_date.isoformat(),
                "requested_end": args.end_date.isoformat(),
                "raw_response_path": str(raw_path),
                "raw_response_sha256": response_hash,
                "normalized_path": str(output),
                "row_count": len(points),
                "valid_position_count": int(points["is_valid_position"].sum()),
                "dataset_version": dataset_version,
                "requested_fields": ["LONLAT", "TIMESTAMP", "SPEED", "COURSE"],
                "server_side_thinning": "none_requested",
            },
        )
        print(output)
        return
    if args.command == "gfw-presence":
        if args.start >= args.end:
            raise ValueError("--start must be before --end")
        request_start = _format_utc_timestamp(args.start)
        request_end = _format_utc_timestamp(args.end)
        if args.reuse_last_report:
            response = client.last_presence_report()
        else:
            response = client.presence_report(
                start=request_start,
                end=request_end,
                region_id=args.region_id,
                region_dataset=args.region_dataset,
                spatial_resolution=args.spatial_resolution,
            )
        run_id = args.retrieval_id or _retrieval_id()
        raw_path = (
            args.bronze_root
            / "gfw_presence"
            / f"retrieval_id={run_id}"
            / f"region_dataset={args.region_dataset}"
            / f"region_id={args.region_id}"
            / "report.json"
        )
        write_json(raw_path, response)
        response_hash = json_hash(response)
        dataset_version = report_dataset_version(
            response, client.last_dataset_version or client.presence_dataset
        )
        output = None
        positions = None
        if not args.bronze_only:
            positions = normalize_presence_report(
                response,
                source_uri="https://gateway.api.globalfishingwatch.org/v3/4wings/report",
                raw_payload_hash=response_hash,
                requested_dataset=dataset_version,
                spatial_resolution=args.spatial_resolution,
            ).sort_values(["vessel_id", "ts", "lat", "lon"], na_position="last")
            output = (
                args.silver_root
                / "gfw_presence_hourly"
                / f"retrieval_id={run_id}"
                / f"region_dataset={args.region_dataset}"
                / f"region_id={args.region_id}"
                / "points.parquet"
            )
            write_parquet(positions, output)
        manifest = {
            "source": PRESENCE_SOURCE,
            "source_uri": "https://gateway.api.globalfishingwatch.org/v3/4wings/report",
            "retrieval_id": run_id,
            "request": {
                "datasets[0]": client.presence_dataset,
                "date-range": f"{request_start},{request_end}",
                "format": "JSON",
                "group-by": "VESSEL_ID",
                "temporal-resolution": "HOURLY",
                "spatial-resolution": args.spatial_resolution,
                "spatial-aggregation": False,
                "region-id": args.region_id,
                "region-dataset": args.region_dataset,
            },
            "reused_last_report": args.reuse_last_report,
            "raw_response_path": str(raw_path),
            "raw_response_sha256": response_hash,
            "normalized_path": str(output) if output else None,
            "row_count": len(positions) if positions is not None else None,
            "valid_position_count": int(positions["is_valid_position"].sum()) if positions is not None else None,
            "dataset_version": dataset_version,
            "position_semantics": PRESENCE_POSITION_SEMANTICS,
            "coordinate_uncertainty": "GFW 4Wings grid-cell centre; HIGH=0.01 degree, LOW=0.1 degree",
        }
        write_manifest(raw_path.with_name("manifest.json"), manifest)
        if output is not None:
            write_manifest(output.with_name("manifest.json"), manifest)
        print(output or raw_path)
        return
    if args.command == "gfw-identity":
        write_json(args.output, client.search_identity(args.query))
        print(args.output)
        return
    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
