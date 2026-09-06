#!/usr/bin/env python3
"""Publish browser presence assets directly from normalized GFW Silver Parquet."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import pyarrow.parquet as pq
except ImportError as error:  # pragma: no cover - depends on the runtime environment
    raise SystemExit("Silver presence export requires pyarrow. Install the project Python dependencies first.") from error


HOUR_MS = 3_600_000
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "data" / "silver" / "gfw_presence_hourly"
DEFAULT_OUTPUT = ROOT / "code" / "frontend" / "public" / "data" / "presence"
REQUIRED_COLUMNS = {
    "ts", "vessel_id", "lat", "lon", "presence_hours", "report_dataset",
    "grid_resolution_degrees", "vessel_name", "mmsi", "imo", "callsign",
    "flag_state", "gfw_vessel_type", "position_semantics", "is_valid_position",
}


def fail(message: str) -> None:
    raise ValueError(message)


def sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def clean(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def hour(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    elif isinstance(value, str):
        raw = value.replace(" ", "T").removesuffix("Z")
        result = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    else:
        fail(f"Invalid UTC hour: {value!r}")
    if result.minute or result.second or result.microsecond:
        fail(f"Invalid UTC hour: {value!r}")
    return result


def iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def discover(root: Path) -> list[Path]:
    files = sorted(root.rglob("points.parquet")) if root.exists() else []
    if not files:
        fail(f"No Silver presence points.parquet files found in {root}")
    return files


def request_details(manifest: dict[str, Any]) -> tuple[datetime, datetime, float, dict[str, Any]]:
    request = manifest.get("request") or {}
    if request.get("temporal-resolution") != "HOURLY" or request.get("spatial-aggregation") is not False:
        fail("Requires unaggregated HOURLY Silver presence data")
    resolution = {"HIGH": 0.01, "LOW": 0.1}.get(request.get("spatial-resolution"))
    if resolution is None:
        fail("Unsupported spatial resolution")
    if not isinstance(request.get("region-dataset"), str) or not isinstance(request.get("region-id"), int):
        fail("Missing region identity")
    dates = request.get("date-range", "").split(",")
    if len(dates) != 2:
        fail("Missing requested date range")
    start, end = hour(dates[0]), hour(dates[1])
    if start >= end:
        fail("Requested range must have start before end")
    if not isinstance(manifest.get("dataset_version"), str) or not manifest["dataset_version"].startswith("public-global-presence:"):
        fail("Missing presence dataset version")
    return start, end, resolution, request


def rows(file: Path) -> Iterator[dict[str, Any]]:
    parquet = pq.ParquetFile(file)
    fields = set(parquet.schema_arrow.names)
    missing = REQUIRED_COLUMNS - fields
    if missing:
        fail(f"Missing Silver columns: {', '.join(sorted(missing))}")
    for batch in parquet.iter_batches(columns=sorted(REQUIRED_COLUMNS)):
        yield from batch.to_pylist()


def read_presence(input_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    observations: dict[str, dict[str, Any]] = {}
    coverages: dict[str, dict[str, Any]] = {}
    for file in discover(input_root):
        try:
            manifest = json.loads(file.with_name("manifest.json").read_text())
            start, end, resolution, request = request_details(manifest)
            created = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
            parquet = pq.ParquetFile(file)
            if manifest.get("row_count") != parquet.metadata.num_rows:
                fail("Manifest row_count does not match Parquet rows")
            if manifest.get("valid_position_count") not in (None, parquet.metadata.num_rows):
                fail("Manifest reports invalid positions")
            coverage = {"start": iso(start), "end": iso(end), "regionDataset": request["region-dataset"], "regionId": request["region-id"], "datasetVersion": manifest["dataset_version"], "gridResolution": resolution}
            coverages[json.dumps(coverage, sort_keys=True)] = coverage
            base_rank = f"{iso(created)}|{file.relative_to(input_root)}"
            for row in rows(file):
                timestamp = hour(row["ts"])
                if not start <= timestamp < end:
                    fail(f"Observation {row['ts']} is outside requested range")
                vessel_id = clean(row["vessel_id"])
                if not vessel_id or not vessel_id.startswith("gfw:"):
                    fail("Missing GFW vessel identity")
                if row["position_semantics"] != "gfw_presence_grid_center_hourly" or row["is_valid_position"] is not True:
                    fail("Invalid Silver position semantics or quality")
                lat, lon, duration = float(row["lat"]), float(row["lon"]), float(row["presence_hours"])
                if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                    fail("Invalid position coordinates")
                if not math.isfinite(duration) or not 0 <= duration <= 1:
                    fail("Invalid hourly presence duration")
                dataset = clean(row["report_dataset"])
                if dataset != manifest["dataset_version"]:
                    fail("Dataset version differs from manifest")
                if not math.isclose(float(row["grid_resolution_degrees"]), resolution, rel_tol=0, abs_tol=1e-12):
                    fail("Grid resolution differs from manifest")
                cell = (round(lat / resolution), round(lon / resolution))
                identity = sha([dataset, resolution, vessel_id, iso(timestamp), *cell])
                rank = f"{base_rank}|{iso(timestamp)}|{sha(row)}"
                if identity in observations and observations[identity]["rank"] >= rank:
                    continue
                observations[identity] = {"rank": rank, "observation": {"id": identity, "vesselId": vessel_id, "ts": iso(timestamp), "lat": lat, "lon": lon, "presenceHours": duration, "datasetVersion": dataset, "gridResolution": resolution}, "vessel": {"id": vessel_id, "name": clean(row["vessel_name"]), "mmsi": clean(row["mmsi"]), "imo": clean(row["imo"]), "callsign": clean(row["callsign"]), "flag": clean(row["flag_state"]), "vesselType": clean(row["gfw_vessel_type"]), "metadataUpdatedAt": iso(created), "metadataRank": rank}}
        except Exception as error:
            raise ValueError(f"{file}: {error}") from error
    return observations, coverages


def write_json(path: Path, value: Any) -> None:
    body = json.dumps(value, separators=(",", ":"), allow_nan=False)
    if path.exists():
        return
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w") as stream:
        stream.write(body)
    os.replace(temporary, path)


def circular_bounds(observations: list[dict[str, Any]]) -> list[float] | None:
    """Return a compact longitude interval; crossing the dateline is valid."""
    if not observations:
        return None
    lats = [item["lat"] for item in observations]
    longitudes = sorted((item["lon"] + 360) % 360 for item in observations)
    if len(longitudes) == 1:
        west = east = longitudes[0]
    else:
        gaps = [(longitudes[(index + 1) % len(longitudes)] - value) % 360 for index, value in enumerate(longitudes)]
        cut = gaps.index(max(gaps))
        west, east = longitudes[(cut + 1) % len(longitudes)], longitudes[cut]
    normalize = lambda value: value - 360 if value > 180 else value
    return [normalize(west), min(lats), normalize(east), max(lats)]


def export(input_root: Path, output: Path) -> dict[str, Any]:
    observations, coverages = read_presence(input_root)
    days: dict[str, dict[str, Any]] = {}
    def day(date: str) -> dict[str, Any]:
        return days.setdefault(date, {"date": date, "covered": set(), "observations": [], "vessels": {}})
    for coverage in coverages.values():
        cursor, end = hour(coverage["start"]), hour(coverage["end"])
        while cursor < end:
            day(cursor.date().isoformat())["covered"].add(cursor.hour); cursor = datetime.fromtimestamp(cursor.timestamp() + 3600, timezone.utc)
    for item in observations.values():
        observation, vessel, rank = item["observation"], item["vessel"], item["rank"]
        target = day(observation["ts"][:10]); target["observations"].append(observation)
        previous = target["vessels"].get(vessel["id"])
        chosen = previous if previous and previous["rank"] > rank else {**vessel, "rank": rank}
        target["vessels"][vessel["id"]] = {**chosen, "firstObservedAt": min(previous["firstObservedAt"], observation["ts"]) if previous else observation["ts"], "lastObservedAt": max(previous["lastObservedAt"], observation["ts"]) if previous else observation["ts"], "observationCount": (previous["observationCount"] if previous else 0) + 1}
    output.mkdir(parents=True, exist_ok=True); catalog_days = []
    for date, target in sorted(days.items()):
        values = sorted(target["observations"], key=lambda entry: (entry["ts"], entry["id"])); counts = [0] * 24
        for value in values: counts[hour(value["ts"]).hour] += 1
        vessels = [{key: value for key, value in entry.items() if key != "rank"} for _, entry in sorted(target["vessels"].items())]
        observation_payload, vessel_payload = {"date": date, "observations": values}, {"date": date, "vessels": vessels}
        observations_url = f"{date}.observations.{sha(observation_payload)}.json"
        vessels_url = f"{date}.vessels.{sha(vessel_payload)}.json"
        write_json(output / observations_url, observation_payload); write_json(output / vessels_url, vessel_payload)
        catalog_days.append({"date": date, "observationsUrl": observations_url, "vesselsUrl": vessels_url, "bounds": circular_bounds(values), "coveredHours": sorted(target["covered"]), "hourlyCounts": counts, "observationCount": len(values), "vesselCount": len(vessels)})
    content = {"schemaVersion": 1, "source": "Global Fishing Watch", "positionSemantics": "gfw_presence_grid_center_hourly", "coverage": sorted(coverages.values(), key=lambda entry: json.dumps(entry, sort_keys=True)), "days": catalog_days, "observationCount": len(observations), "coveredHourCount": sum(len(entry["coveredHours"]) for entry in catalog_days)}
    catalog = {**content, "revision": sha(content), "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}
    temporary = output / f".catalog-{os.getpid()}.tmp"; temporary.write_text(json.dumps(catalog, indent=2)); os.replace(temporary, output / "catalog.json")
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, default=DEFAULT_INPUT); parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        result = export(args.input.resolve(), args.output.resolve())
        print(f"Exported {result['observationCount']:,} observations across {result['coveredHourCount']} covered hours ({len(result['days'])} UTC days).")
    except Exception as error:
        print(error, file=sys.stderr); raise SystemExit(1)
