"""Normalize the documented JSON line representation of GFW vessel tracks."""

from __future__ import annotations

from numbers import Number
from typing import Any

import pandas as pd

from ..contract import CANONICAL_POSITION_COLUMNS, canonicalize_positions


TRACK_SOURCE = "global_fishing_watch_track"


def _timestamp(value: object) -> object:
    """Decode GFW's numeric timestamps without treating seconds as nanoseconds."""
    if isinstance(value, Number) and not isinstance(value, bool):
        magnitude = abs(float(value))
        if magnitude >= 100_000_000_000:
            return pd.to_datetime(value, unit="ms", utc=True)
        if magnitude >= 1_000_000_000:
            return pd.to_datetime(value, unit="s", utc=True)
    return value


def _coordinate_value(properties: dict[str, Any], names: tuple[str, ...], index: int) -> object:
    for name in names:
        values = properties.get(name)
        if isinstance(values, list) and index < len(values):
            return values[index]
    return None


def normalize_track_lines(
    payload: dict[str, Any],
    *,
    gfw_vessel_id: str,
    source_uri: str,
    raw_payload_hash: str,
    dataset_version: str,
) -> pd.DataFrame:
    """Turn a GeoJSON-style GFW line payload into canonical per-point rows.

    The documented frontend consumes a FeatureCollection of line segments and
    aligns `coordinateProperties` arrays with each coordinate. Rows preserve
    exact returned timestamps and fields; no interpolation or hourly resample
    is performed here.
    """
    rows: list[dict[str, object]] = []
    features = payload.get("features", []) if isinstance(payload, dict) else []
    for segment_index, feature in enumerate(features):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        properties = feature.get("properties") or {}
        coordinate_properties = properties.get("coordinateProperties") or properties
        if geometry.get("type") == "MultiLineString":
            coordinate_groups = coordinates
        else:
            coordinate_groups = [coordinates]
        point_offset = 0
        for coordinate_group in coordinate_groups:
            for point_index, coordinate in enumerate(coordinate_group):
                if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
                    continue
                aligned_index = point_offset + point_index
                rows.append(
                    {
                        "source_record_id": f"{gfw_vessel_id}:{segment_index}:{aligned_index}",
                        "timestamp": _timestamp(
                            _coordinate_value(coordinate_properties, ("times", "timestamp", "timestamps"), aligned_index)
                        ),
                        "longitude": coordinate[0],
                        "latitude": coordinate[1],
                        "speed": _coordinate_value(coordinate_properties, ("speed", "speeds"), aligned_index),
                        "course": _coordinate_value(coordinate_properties, ("course", "courses"), aligned_index),
                    }
                )
            point_offset += len(coordinate_group)
    frame = pd.DataFrame(
        rows,
        columns=("source_record_id", "timestamp", "longitude", "latitude", "speed", "course"),
    )
    return canonicalize_positions(
        frame,
        source=TRACK_SOURCE,
        source_uri=source_uri,
        raw_payload_hash=raw_payload_hash,
        dataset_version=dataset_version,
        collection_mode="mixed",
        position_semantics="gfw_derived_track",
        vessel_id_override=f"gfw:{gfw_vessel_id}",
    ).loc[:, CANONICAL_POSITION_COLUMNS]
