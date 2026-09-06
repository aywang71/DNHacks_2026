"""Retrieve one configured GFW AIS-Presence demo target, append-only.

GFW permits one active 4Wings report per account. Invoke this script for one
target at a time; it deliberately has no parallel or batch mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dark_rendezvous.cli_support import json_hash
from dark_rendezvous.providers.gfw import GfwClient
from dark_rendezvous.providers.gfw_presence import (
    PRESENCE_POSITION_SEMANTICS,
    PRESENCE_SOURCE,
    normalize_presence_report,
    partition_presence_report,
    report_dataset_version,
)
from dark_rendezvous.storage import sha256_file, write_manifest, write_parquet


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "reference" / "demo_presence_targets.json"
MAX_RAW_PART_BYTES = 95 * 1024 * 1024


def _token() -> str:
    if os.environ.get("GFW_API_TOKEN"):
        return os.environ["GFW_API_TOKEN"]
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GFW_API_TOKEN="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    raise RuntimeError("Set GFW_API_TOKEN in the environment or ignored local .env file.")


def _target(config: dict[str, Any], slug: str) -> dict[str, Any]:
    for target in config["targets"]:
        if target["slug"] == slug:
            return target
    choices = ", ".join(target["slug"] for target in config["targets"])
    raise ValueError(f"Unknown target {slug!r}; choose one of: {choices}")


def _target_location(target: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    if target["kind"] == "eez":
        region_id = target["region_id"]
        region_dataset = target["region_dataset"]
        return (
            [f"region_dataset={region_dataset}", f"region_id={region_id}"],
            {"kind": "eez", "region_dataset": region_dataset, "region_id": region_id},
        )
    if target["kind"] == "geojson":
        geometry = target["geojson"]
        encoded = json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode("utf-8")
        geometry_hash = hashlib.sha256(encoded).hexdigest()
        return (
            [f"geojson_id={geometry_hash[:12]}"],
            {"kind": "geojson", "geojson": geometry, "geojson_sha256": geometry_hash},
        )
    raise ValueError(f"Unsupported target kind {target['kind']!r}")


def _write_report_parts(
    directory: Path, response: dict[str, Any], *, max_bytes: int = MAX_RAW_PART_BYTES
) -> list[Path]:
    """Write raw Presence envelopes in GitHub-safe JSON parts."""
    parts = partition_presence_report(response, max_bytes=max_bytes)
    paths = [
        directory / ("report.json" if len(parts) == 1 else f"report.part-{index:04d}.json")
        for index in range(1, len(parts) + 1)
    ]
    for path, part in zip(paths, parts, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(part, indent=2, sort_keys=True).encode("utf-8"))
        if path.stat().st_size > max_bytes:
            raise AssertionError(f"Raw report part exceeds {max_bytes} bytes: {path}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--start", help="Override the configured inclusive UTC start timestamp.")
    parser.add_argument("--end", help="Override the configured exclusive UTC end timestamp.")
    parser.add_argument(
        "--silver-only",
        action="store_true",
        help="Do not retain the raw Bronze response; write only normalized Silver and its manifest.",
    )
    parser.add_argument(
        "--reuse-last-report",
        action="store_true",
        help="Recover the account's last completed 4Wings report without submitting a new one.",
    )
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    target = _target(config, args.target)
    settings = config["report_settings"]
    start = args.start or config["date_range"]["start"]
    end = args.end or config["date_range"]["end"]
    if start >= end:
        raise ValueError("--start must be earlier than --end")
    path_segments, location = _target_location(target)
    client = GfwClient(_token(), timeout_seconds=args.timeout_seconds)
    if args.reuse_last_report:
        response = client.last_presence_report()
    elif location["kind"] == "eez":
        response = client.presence_report(
            start=start,
            end=end,
            region_id=location["region_id"],
            region_dataset=location["region_dataset"],
            spatial_resolution=settings["spatial_resolution"],
            temporal_resolution=settings["temporal_resolution"],
        )
    else:
        response = client.presence_report(
            start=start,
            end=end,
            geojson=location["geojson"],
            spatial_resolution=settings["spatial_resolution"],
            temporal_resolution=settings["temporal_resolution"],
        )

    range_label = f"{start[:10].replace('-', '')}_{end[:10].replace('-', '')}"
    run_id = f"{range_label}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    bronze_base = ROOT / "data" / "bronze" / "gfw_presence_global_demo" / f"target={target['slug']}" / "gfw_presence" / f"retrieval_id={run_id}"
    silver_base = ROOT / "data" / "silver" / "gfw_presence_global_demo" / f"target={target['slug']}" / "gfw_presence_hourly" / f"retrieval_id={run_id}"
    for segment in path_segments:
        bronze_base /= segment
        silver_base /= segment
    output_path = silver_base / "points.parquet"
    raw_hash = json_hash(response)
    raw_paths = [] if args.silver_only else _write_report_parts(bronze_base, response)
    dataset_version = report_dataset_version(response, client.last_dataset_version or client.presence_dataset)
    positions = normalize_presence_report(
        response,
        source_uri="https://gateway.api.globalfishingwatch.org/v3/4wings/report",
        raw_payload_hash=raw_hash,
        requested_dataset=dataset_version,
        spatial_resolution=settings["spatial_resolution"],
    ).sort_values(["vessel_id", "ts", "lat", "lon"], na_position="last")
    write_parquet(positions, output_path)
    manifest = {
        "source": PRESENCE_SOURCE,
        "source_uri": "https://gateway.api.globalfishingwatch.org/v3/4wings/report",
        "retrieval_id": run_id,
        "target": {"slug": target["slug"], "label": target["label"], **location},
        "request": {
            "datasets[0]": settings["dataset"],
            "date-range": f"{start},{end}",
            "format": settings["format"],
            "group-by": settings["group_by"],
            "temporal-resolution": settings["temporal_resolution"],
            "spatial-resolution": settings["spatial_resolution"],
            "spatial-aggregation": settings["spatial_aggregation"],
        },
        "raw_response_sha256": raw_hash,
        "raw_response_stored": bool(raw_paths),
        "reused_last_report": args.reuse_last_report,
        "normalized_path": str(output_path.relative_to(ROOT)),
        "row_count": len(positions),
        "valid_position_count": int(positions["is_valid_position"].sum()),
        "dataset_version": dataset_version,
        "position_semantics": PRESENCE_POSITION_SEMANTICS,
        "coordinate_uncertainty": "GFW 4Wings grid-cell centre; HIGH=0.01 degree, LOW=0.1 degree",
    }
    if raw_paths:
        manifest.update(
            {
                "raw_response_path": str(raw_paths[0].relative_to(ROOT)),
                "raw_response_paths": [str(path.relative_to(ROOT)) for path in raw_paths],
                "raw_response_part_sha256": [sha256_file(path) for path in raw_paths],
                "raw_response_part_bytes": [path.stat().st_size for path in raw_paths],
            }
        )
        write_manifest(bronze_base / "manifest.json", manifest)
    else:
        manifest["raw_response_retention"] = "not retained (silver-only MVP pull)"
    write_manifest(output_path.with_name("manifest.json"), manifest)
    print(
        json.dumps(
            {
                "target": target["slug"],
                "bronze": [str(path) for path in raw_paths],
                "silver": str(output_path),
                "rows": len(positions),
            }
        )
    )


if __name__ == "__main__":
    main()
