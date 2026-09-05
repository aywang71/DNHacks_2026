"""Provider-independent bronze-to-silver ingestion workflows."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .contract import canonicalize_positions
from .providers.generic import read_export
from .providers.noaa import NoaaMarineCadastreProvider
from .storage import sha256_file, write_manifest, write_parquet


def _clip_to_bbox(frame: pd.DataFrame, bbox: tuple[float, float, float, float] | None) -> pd.DataFrame:
    if bbox is None:
        return frame
    min_lon, min_lat, max_lon, max_lat = bbox
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("bbox must be min_lon,min_lat,max_lon,max_lat")
    return frame.loc[
        frame["lon"].between(min_lon, max_lon) & frame["lat"].between(min_lat, max_lat)
    ].copy()


def ingest_noaa_day(
    *,
    day: date,
    bronze_root: Path,
    silver_root: Path,
    bbox: tuple[float, float, float, float] | None = None,
) -> Path:
    provider = NoaaMarineCadastreProvider()
    raw = provider.download(day, bronze_root)
    positions = _clip_to_bbox(provider.normalize(raw), bbox)
    output = silver_root / "ais_positions" / f"event_date={day.isoformat()}" / "positions.parquet"
    write_parquet(positions, output)
    write_manifest(
        output.with_name("manifest.json"),
        {
            "source": "noaa_marine_cadastre",
            "source_uri": raw.source_uri,
            "raw_payload_sha256": raw.sha256,
            "raw_path": str(raw.path),
            "normalized_path": str(output),
            "row_count": len(positions),
            "valid_position_count": int(positions["is_valid_position"].sum()),
            "bbox": bbox,
        },
    )
    return output


def normalize_file(
    *,
    input_path: Path,
    source: str,
    silver_root: Path,
    collection_mode: str,
    dataset_version: str = "unknown",
) -> Path:
    frame = read_export(input_path)
    payload_hash = sha256_file(input_path)
    positions = canonicalize_positions(
        frame,
        source=source,
        source_uri=input_path.resolve().as_uri(),
        raw_payload_hash=payload_hash,
        dataset_version=dataset_version,
        collection_mode=collection_mode,
    )
    output = silver_root / "ais_positions" / f"source={source}" / "positions.parquet"
    write_parquet(positions, output)
    write_manifest(
        output.with_name("manifest.json"),
        {
            "source": source,
            "source_uri": input_path.resolve().as_uri(),
            "raw_payload_sha256": payload_hash,
            "normalized_path": str(output),
            "row_count": len(positions),
            "valid_position_count": int(positions["is_valid_position"].sum()),
        },
    )
    return output

