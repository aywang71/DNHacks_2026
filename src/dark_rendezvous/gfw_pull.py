"""Pagination and append-only storage for GFW GAP-event windows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from .cli_support import json_hash, write_json
from .providers.gfw import GfwClient, normalize_gap_endpoints
from .storage import write_manifest, write_parquet


SOURCE_URI = "https://gateway.api.globalfishingwatch.org/v3/events"


@dataclass(frozen=True)
class GapPullSummary:
    retrieval_id: str
    request_start: str
    request_end: str
    window_days: int
    page_size: int
    intentional_disabling: bool | None
    time_filter_mode: str
    pages_written: int
    events_written: int
    endpoints_written: int
    complete: bool
    next_window_start: str | None
    next_offset: int | None
    bronze_output_root: str
    silver_output_root: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def date_windows(start: date, end: date, window_days: int) -> Iterator[tuple[date, date]]:
    """Yield non-overlapping, end-exclusive calendar windows."""
    if start >= end:
        raise ValueError("start date must be before end date")
    if window_days < 1:
        raise ValueError("window_days must be positive")
    cursor = start
    while cursor < end:
        next_cursor = min(cursor + timedelta(days=window_days), end)
        yield cursor, next_cursor
        cursor = next_cursor


def _retrieval_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def pull_gap_windows(
    client: GfwClient,
    *,
    start: date,
    end: date,
    bronze_root: Path,
    silver_root: Path,
    window_days: int = 31,
    page_size: int = 500,
    intentional_disabling: bool | None = True,
    max_pages: int | None = None,
    retrieval_id: str | None = None,
    write_silver: bool = True,
) -> GapPullSummary:
    """Fetch GAP pages by event-start window and store immutable page artifacts.

    GFW's documented default is overlap matching. Using its accepted
    ``START-DATE`` mode prevents long events from appearing in several calendar
    windows. A stopped ``max_pages`` pull is explicitly marked incomplete.
    """
    if page_size < 1:
        raise ValueError("page_size must be positive")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when supplied")

    run_id = retrieval_id or _retrieval_id()
    pages_written = 0
    events_written = 0
    endpoints_written = 0
    complete = True
    next_window_start: str | None = None
    next_offset: int | None = None
    bronze_run_root = bronze_root / "gfw_gaps" / f"retrieval_id={run_id}"
    silver_run_root = (
        silver_root / "gfw_gap_endpoints" / f"retrieval_id={run_id}"
        if write_silver
        else None
    )

    for window_start, window_end in date_windows(start, end, window_days):
        offset = 0
        while True:
            if max_pages is not None and pages_written >= max_pages:
                complete = False
                next_window_start = window_start.isoformat()
                next_offset = offset
                break

            response = client.gap_events(
                start_date=window_start.isoformat(),
                end_date=window_end.isoformat(),
                offset=offset,
                limit=page_size,
                time_filter_mode="START-DATE",
                intentional_disabling=intentional_disabling,
            )
            payload_hash = json_hash(response)
            page_root = (
                bronze_root
                / "gfw_gaps"
                / f"retrieval_id={run_id}"
                / f"window_start={window_start.isoformat()}"
                / f"window_end={window_end.isoformat()}"
                / f"offset={offset:09d}"
            )
            raw_path = page_root / "response.json"
            write_json(raw_path, response)

            dataset_version = client.last_dataset_version or client.gaps_dataset
            endpoints = None
            normalized_path = None
            if silver_run_root is not None:
                endpoints = normalize_gap_endpoints(
                    response,
                    source_uri=SOURCE_URI,
                    raw_payload_hash=payload_hash,
                    dataset_version=dataset_version,
                ).sort_values(["vessel_id", "ts", "endpoint_role"], na_position="last")
                normalized_path = (
                    silver_run_root
                    / f"window_start={window_start.isoformat()}"
                    / f"window_end={window_end.isoformat()}"
                    / f"offset={offset:09d}"
                    / "endpoints.parquet"
                )
                write_parquet(endpoints, normalized_path)
            page_manifest = {
                "source": "global_fishing_watch_events",
                "source_uri": SOURCE_URI,
                "retrieval_id": run_id,
                "request": {
                    "datasets": [client.gaps_dataset],
                    "types": ["GAP"],
                    "startDate": window_start.isoformat(),
                    "endDate": window_end.isoformat(),
                    "timeFilterMode": "START-DATE",
                    "gapIntentionalDisabling": intentional_disabling,
                    "offset": offset,
                    "limit": page_size,
                },
                "raw_response_path": str(raw_path),
                "raw_response_sha256": payload_hash,
                "normalized_path": str(normalized_path) if normalized_path else None,
                "event_count": len(response.get("entries", [])),
                "endpoint_count": len(endpoints) if endpoints is not None else None,
                "reported_total_for_window": response.get("total"),
                "next_offset": response.get("nextOffset"),
                "dataset_version": dataset_version,
            }
            write_manifest(page_root / "manifest.json", page_manifest)
            if normalized_path is not None:
                write_manifest(normalized_path.with_name("manifest.json"), page_manifest)

            pages_written += 1
            events_written += len(response.get("entries", []))
            endpoints_written += len(endpoints) if endpoints is not None else 0
            next_offset_from_api = response.get("nextOffset")
            if next_offset_from_api is None:
                break
            offset = int(next_offset_from_api)
        if not complete:
            break

    summary = GapPullSummary(
        retrieval_id=run_id,
        request_start=start.isoformat(),
        request_end=end.isoformat(),
        window_days=window_days,
        page_size=page_size,
        intentional_disabling=intentional_disabling,
        time_filter_mode="START-DATE",
        pages_written=pages_written,
        events_written=events_written,
        endpoints_written=endpoints_written,
        complete=complete,
        next_window_start=next_window_start,
        next_offset=next_offset,
        bronze_output_root=str(bronze_run_root),
        silver_output_root=str(silver_run_root) if silver_run_root else None,
    )
    write_manifest(bronze_run_root / "pull_manifest.json", summary.to_dict())
    if silver_run_root is not None:
        write_manifest(silver_run_root / "pull_manifest.json", summary.to_dict())
    return summary
