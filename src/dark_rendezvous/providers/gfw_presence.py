"""Normalize GFW 4Wings Presence report rows without calling them raw AIS."""

from __future__ import annotations

from typing import Any, Iterator

import pandas as pd

from ..contract import CANONICAL_POSITION_COLUMNS, canonicalize_positions, clean_identifier


PRESENCE_SOURCE = "global_fishing_watch_presence"
PRESENCE_POSITION_SEMANTICS = "gfw_presence_grid_center_hourly"
GFW_PRESENCE_COLUMNS: tuple[str, ...] = (
    *CANONICAL_POSITION_COLUMNS,
    "gfw_vessel_id",
    "flag_state",
    "gfw_vessel_type",
    "presence_hours",
    "report_dataset",
    "grid_resolution_degrees",
)


def _presence_rows(payload: dict[str, Any]) -> Iterator[tuple[str | None, dict[str, Any]]]:
    """Yield rows from the API's dataset-keyed report envelope.

    A 4Wings report has the form ``entries: [{"dataset:version": [rows]}]``.
    Supporting direct row entries as well keeps the normalizer resilient to a
    future response-envelope simplification.
    """
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        nested = False
        for dataset, records in entry.items():
            if not isinstance(records, list):
                continue
            nested = True
            for record in records:
                if isinstance(record, dict):
                    yield dataset, record
        if not nested and "vesselId" in entry:
            yield None, entry


def report_dataset_version(payload: dict[str, Any], fallback: str) -> str:
    """Return the concrete Presence dataset version named by the report."""
    for dataset, _ in _presence_rows(payload):
        if dataset and dataset.startswith("public-global-presence:"):
            return dataset
    return fallback


def normalize_presence_report(
    payload: dict[str, Any],
    *,
    source_uri: str,
    raw_payload_hash: str,
    requested_dataset: str,
    spatial_resolution: str,
) -> pd.DataFrame:
    """Map a GFW Presence report to canonical, hourly grid-centre positions.

    The preserved Bronze response is the provider's raw API response. GFW has
    already selected an AIS position per vessel-hour and reports the centre of
    a spatial grid cell, so Silver rows explicitly retain those semantics.
    """
    records: list[dict[str, Any]] = []
    for row_index, (dataset, row) in enumerate(_presence_rows(payload)):
        records.append(
            {
                **row,
                "source_record_id": "|".join(
                    str(value)
                    for value in (
                        row.get("vesselId", "unknown"),
                        row.get("entryTimestamp", row.get("date", "unknown")),
                        row.get("lat", "unknown"),
                        row.get("lon", "unknown"),
                        row_index,
                    )
                ),
                "report_dataset": dataset or requested_dataset,
            }
        )
    frame = pd.DataFrame(records)
    if frame.empty:
        return pd.DataFrame(columns=GFW_PRESENCE_COLUMNS)

    gfw_vessel_id = clean_identifier(frame["vesselId"] if "vesselId" in frame else pd.Series(pd.NA, index=frame.index))
    gfw_vessel_override = ("gfw:" + gfw_vessel_id).where(gfw_vessel_id.notna(), pd.NA)
    result = canonicalize_positions(
        frame,
        source=PRESENCE_SOURCE,
        source_uri=source_uri,
        raw_payload_hash=raw_payload_hash,
        dataset_version=report_dataset_version(payload, requested_dataset),
        collection_mode="mixed",
        position_semantics=PRESENCE_POSITION_SEMANTICS,
        vessel_id_override=gfw_vessel_override,
    )
    result["gfw_vessel_id"] = gfw_vessel_id
    result["flag_state"] = clean_identifier(frame["flag"] if "flag" in frame else pd.Series(pd.NA, index=frame.index))
    result["gfw_vessel_type"] = clean_identifier(
        frame["vesselType"] if "vesselType" in frame else pd.Series(pd.NA, index=frame.index)
    )
    result["presence_hours"] = pd.to_numeric(
        frame["hours"] if "hours" in frame else pd.Series(pd.NA, index=frame.index), errors="coerce"
    )
    result["report_dataset"] = frame["report_dataset"].astype("string")
    result["grid_resolution_degrees"] = {"HIGH": 0.01, "LOW": 0.1}.get(spatial_resolution.upper())
    return result.loc[:, GFW_PRESENCE_COLUMNS]
