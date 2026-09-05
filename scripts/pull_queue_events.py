#!/usr/bin/env python3
"""Pull GFW identity and behaviour events for the paired-dark queue.

This is intentionally a standalone script.  It is designed to be run by the
team member who has the GFW API token, and does not import the project package
or depend on a local editable install.  Every successful (and HTTP-error)
response is retained as bronze JSON before its small, useful subset is written
to the two reference parquet tables.

Examples (from the repository root)::

    python scripts/pull_queue_events.py
    python scripts/pull_queue_events.py --only identity
    python scripts/pull_queue_events.py --resume
    python scripts/pull_queue_events.py --dry-run

``--dry-run`` is deliberately a live, two-request schema probe: it requests
the showcase MMSI identity and one ENCOUNTER page, then prints their first
entries.  It is not a no-network option.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import httpx
import pandas as pd


# Verified against the GFW v3 Events API documentation on 2026-09-05.
BASE_URL = "https://gateway.api.globalfishingwatch.org/v3"
IDENTITY_DATASET = "public-global-vessel-identity:latest"
ENCOUNTER_DATASET = "public-global-encounters-events:latest"
LOITERING_DATASET = "public-global-loitering-events:latest"
PORT_VISIT_DATASET = "public-global-port-visits-events:latest"
EVENT_DATASETS: dict[str, str] = {
    "ENCOUNTER": ENCOUNTER_DATASET,
    "LOITERING": LOITERING_DATASET,
    "PORT_VISIT": PORT_VISIT_DATASET,
}

START_DATE = "2017-01-01"
END_DATE = "2019-12-31"
EVENT_PAGE_SIZE = 500
EVENT_BATCH_SIZE = 50
PAUSE_SECONDS = 0.2
MAX_RETRIES = 5
SHOWCASE_MMSI = "412331147"

IDENTITY_COLUMNS = (
    "mmsi",
    "gfw_vessel_id",
    "name",
    "imo",
    "callsign",
    "flag",
    "vessel_type",
    "gear_type",
    "length_m",
    "tonnage_gt",
    "built_year",
    "owner",
    "authorizations_json",
    "first_transmission",
    "last_transmission",
    "match_rank",
    "dataset_version",
    "retrieved_at",
)

EVENT_COLUMNS = (
    "event_type",
    "event_id",
    "gfw_vessel_id",
    "mmsi",
    "start",
    "end",
    "lat",
    "lon",
    "partner_gfw_vessel_id",
    "partner_mmsi",
    "partner_type",
    "median_distance_km",
    "median_speed_kn",
    "port_name",
    "port_country",
    "regions_json",
    "dataset_version",
    "retrieved_at",
)


class GfwPullError(RuntimeError):
    """Base exception whose messages are safe to show without a token."""


class GfwRequestError(GfwPullError):
    """A transport failure or exhausted retry budget."""


class GfwHttpError(GfwPullError):
    """An HTTP response that the caller must handle explicitly."""

    def __init__(
        self,
        status_code: int,
        method: str,
        path: str,
        response_bytes: bytes,
        response_headers: Mapping[str, str],
    ) -> None:
        self.status_code = int(status_code)
        self.method = method
        self.path = path
        self.response_bytes = response_bytes
        self.response_headers = dict(response_headers)
        super().__init__(f"GFW returned HTTP {self.status_code} for {method} {path}.")


class AuthenticationError(GfwHttpError):
    """401/403 response; retrying with the same credential cannot help."""

    def __init__(
        self,
        status_code: int,
        method: str,
        path: str,
        response_bytes: bytes,
        response_headers: Mapping[str, str],
    ) -> None:
        super().__init__(status_code, method, path, response_bytes, response_headers)
        self.args = (
            "GFW authentication or authorization failed "
            f"(HTTP {self.status_code}). Check that GFW_API_TOKEN is valid and permitted for this dataset.",
        )


@dataclass
class ApiResponse:
    """A decoded response plus exactly the bronze bytes returned by GFW."""

    payload: dict[str, Any]
    response_bytes: bytes
    headers: dict[str, str]
    status_code: int


@dataclass
class IdentityPullResult:
    frame: pd.DataFrame
    resolved_by_mmsi: dict[str, str]
    unresolved_mmsis: list[str]
    dataset_4xx: list[dict[str, Any]]
    first_entry: dict[str, Any] | None


@dataclass
class EventBatchResult:
    frame: pd.DataFrame
    dataset_4xx: list[dict[str, Any]]
    first_entry: dict[str, Any] | None
    skipped: bool
    complete: bool


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a stable ``Z`` suffix."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_retrieval_id() -> str:
    """Return the compact UTC retrieval identifier used in bronze paths."""

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _as_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_mapping_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return not bool(pd.isna(value))
    except (TypeError, ValueError):
        return True


def _first_value(*values: object) -> object | None:
    for value in values:
        if _nonempty(value):
            return value
    return None


def _field(mapping: Mapping[str, Any], *names: str) -> object | None:
    for name in names:
        value = mapping.get(name)
        if _nonempty(value):
            return value
    return None


def _json_string(value: object) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None


def _string_or_none(value: object) -> str | None:
    if not _nonempty(value):
        return None
    return str(value).strip()


def _float_or_none(value: object) -> float | None:
    if not _nonempty(value):
        return None
    try:
        number = float(value)  # GFW emits some numerics as strings.
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def normalise_lon(value: object) -> float | None:
    """Coerce a longitude to [-180, 180], returning None for invalid input."""

    number = _float_or_none(value)
    if number is None:
        return None
    normalised = ((number + 180.0) % 360.0) - 180.0
    # Keep a supplied +180 as +180 rather than silently changing hemisphere
    # representation. Both endpoints remain within the promised interval.
    if normalised == -180.0 and number > 0:
        return 180.0
    return normalised


def _valid_lat(value: object) -> float | None:
    number = _float_or_none(value)
    if number is None or not -90.0 <= number <= 90.0:
        return None
    return number


def _parse_datetime(value: object) -> pd.Timestamp | None:
    if not _nonempty(value):
        return None
    if isinstance(value, Mapping) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    ):
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isinstance(parsed, pd.Timestamp):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def transmission_overlaps_2017_2019(first: object, last: object) -> bool:
    """Whether a (possibly open-ended) transmission interval overlaps the corpus."""

    first_time = _parse_datetime(first)
    last_time = _parse_datetime(last)
    if first_time is None and last_time is None:
        return False
    window_start = pd.Timestamp("2017-01-01T00:00:00Z")
    window_end = pd.Timestamp("2019-12-31T23:59:59.999999Z")
    if first_time is not None and first_time > window_end:
        return False
    if last_time is not None and last_time < window_start:
        return False
    return True


def _first_named_value(value: object) -> str | None:
    """Return a useful scalar from GFW's list-of-traits identity fields."""

    if isinstance(value, str):
        return _string_or_none(value)
    if isinstance(value, Mapping):
        return _string_or_none(_field(value, "name", "value", "type"))
    for item in _as_mapping_list(value):
        named = _string_or_none(_field(item, "name", "value", "type"))
        if named is not None:
            return named
    return None


def _related_records(entry: Mapping[str, Any], keys: Iterable[str], ssvid: str | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key in keys:
        records.extend(_as_mapping_list(entry.get(key)))
    if ssvid is None:
        return records
    matching = [record for record in records if _string_or_none(record.get("ssvid")) == ssvid]
    return matching or records


def _combined_traits(entry: Mapping[str, Any], candidate_id: str | None) -> dict[str, Any]:
    combined = _as_mapping_list(entry.get("combinedSourcesInfo"))
    if candidate_id is not None:
        matching = [item for item in combined if _string_or_none(item.get("vesselId")) == candidate_id]
        if matching:
            combined = matching
    return combined[0] if combined else {}


def _identity_candidate_payloads(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten the identity fields which may be lists or singleton objects."""

    candidates: list[dict[str, Any]] = []
    for key in ("selfReportedInfo", "registryInfo"):
        candidates.extend(_as_mapping_list(entry.get(key)))
    # Some API versions/synthetic probes expose the useful identity directly on
    # the search entry rather than under selfReportedInfo or registryInfo.
    if not candidates:
        candidates.append(dict(entry))
    return candidates


def _identity_record(
    entry: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    fallback_dataset_version: str | None,
    retrieved_at: str,
) -> dict[str, Any]:
    candidate_ssvid = _string_or_none(_first_value(candidate.get("ssvid"), entry.get("ssvid")))
    candidate_id = _string_or_none(
        _first_value(
            _field(candidate, "gfwVesselId", "gfw_vessel_id", "vesselId", "id"),
            _field(entry, "gfwVesselId", "gfw_vessel_id", "vesselId", "id"),
        )
    )
    combined = _combined_traits(entry, candidate_id)
    if candidate_id is None:
        candidate_id = _string_or_none(_field(combined, "vesselId", "id"))

    first_transmission = _first_value(
        _field(candidate, "transmissionDateFrom", "firstTransmission", "first_transmission"),
        _field(entry, "transmissionDateFrom", "firstTransmission", "first_transmission"),
    )
    last_transmission = _first_value(
        _field(candidate, "transmissionDateTo", "lastTransmission", "last_transmission"),
        _field(entry, "transmissionDateTo", "lastTransmission", "last_transmission"),
    )
    owners = _related_records(entry, ("registryOwners", "owners", "ownership"), candidate_ssvid)
    authorizations = _related_records(
        entry,
        ("registryAuthorizations", "registryPublicAuthorizations", "authorizations", "publicAuthorizations"),
        candidate_ssvid,
    )

    return {
        "mmsi": candidate_ssvid,
        "gfw_vessel_id": candidate_id,
        "name": _string_or_none(
            _first_value(_field(candidate, "shipname", "name"), _field(entry, "shipname", "name"))
        ),
        "imo": _string_or_none(_first_value(candidate.get("imo"), entry.get("imo"))),
        "callsign": _string_or_none(_first_value(candidate.get("callsign"), entry.get("callsign"))),
        "flag": _string_or_none(_first_value(candidate.get("flag"), entry.get("flag"))),
        "vessel_type": _first_named_value(
            _first_value(
                _field(candidate, "vesselType", "vessel_type", "type"),
                _field(entry, "vesselType", "vessel_type", "type"),
                combined.get("shiptypes"),
            )
        ),
        "gear_type": _first_named_value(
            _first_value(
                _field(candidate, "gearType", "gear_type", "geartype", "geartypes"),
                _field(entry, "gearType", "gear_type", "geartype", "geartypes"),
                combined.get("geartypes"),
            )
        ),
        "length_m": _float_or_none(_first_value(candidate.get("lengthM"), entry.get("lengthM"))),
        "tonnage_gt": _float_or_none(_first_value(candidate.get("tonnageGt"), entry.get("tonnageGt"))),
        "built_year": _float_or_none(
            _first_value(
                _field(candidate, "builtYear", "yearBuilt", "built_year"),
                _field(entry, "builtYear", "yearBuilt", "built_year"),
            )
        ),
        "owner": _string_or_none(
            _first_value(
                _field(owners[0], "name", "owner", "ownerName") if owners else None,
                _field(entry, "owner", "ownerName"),
            )
        ),
        "authorizations_json": _json_string(authorizations) if authorizations else None,
        "first_transmission": first_transmission,
        "last_transmission": last_transmission,
        "dataset_version": _string_or_none(
            _first_value(entry.get("dataset"), fallback_dataset_version, combined.get("dataset"))
        ),
        "retrieved_at": retrieved_at,
    }


def _normalise_identity_frame(records: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(list(records), columns=IDENTITY_COLUMNS)
    for column in ("mmsi", "gfw_vessel_id", "name", "imo", "callsign", "flag", "vessel_type", "gear_type", "owner", "authorizations_json", "dataset_version", "retrieved_at"):
        frame[column] = frame[column].astype("string")
    for column in ("length_m", "tonnage_gt"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Float64")
    frame["built_year"] = pd.to_numeric(frame["built_year"], errors="coerce").round().astype("Int64")
    frame["match_rank"] = pd.to_numeric(frame["match_rank"], errors="coerce").astype("Int64")
    for column in ("first_transmission", "last_transmission"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce", utc=True)
    return frame.loc[:, IDENTITY_COLUMNS]


def parse_identity_response(
    payload: Mapping[str, Any],
    mmsi: str,
    *,
    retrieved_at: str | None = None,
    dataset_version: str | None = None,
) -> pd.DataFrame:
    """Parse and rank every identity candidate returned for one queried MMSI.

    Rank 1 is an event-queryable candidate whose own ``ssvid`` matches the
    query and whose transmission interval overlaps 2017--2019. The remaining
    response candidates stay in the table, in deterministic order, for
    auditability.
    """

    requested_mmsi = str(mmsi).strip()
    at = retrieved_at or utc_now()
    entries = _as_mapping_list(payload.get("entries"))
    records_with_priority: list[tuple[tuple[int, int, int, int], int, dict[str, Any]]] = []
    ordinal = 0
    for entry_index, entry in enumerate(entries):
        for candidate_index, candidate in enumerate(_identity_candidate_payloads(entry)):
            record = _identity_record(
                entry,
                candidate,
                fallback_dataset_version=dataset_version,
                retrieved_at=at,
            )
            exact_mmsi = record["mmsi"] == requested_mmsi
            overlaps = transmission_overlaps_2017_2019(
                record["first_transmission"], record["last_transmission"]
            )
            # The first tuple element makes exact + temporal candidates rank
            # ahead of near matches. API order then breaks ties.
            priority = (
                0 if exact_mmsi and overlaps else 1,
                0 if exact_mmsi else 1,
                0 if overlaps else 1,
                0 if _nonempty(record["gfw_vessel_id"]) else 1,
            )
            records_with_priority.append((priority, ordinal, record))
            ordinal += 1

    records_with_priority.sort(key=lambda item: (item[0], item[1]))
    records: list[dict[str, Any]] = []
    for rank, (_, _, record) in enumerate(records_with_priority, start=1):
        record["match_rank"] = rank
        records.append(record)
    return _normalise_identity_frame(records)


def choose_identity_candidate(frame: pd.DataFrame, mmsi: str) -> dict[str, Any] | None:
    """Return the eligible rank-one identity candidate used for event pulls."""

    requested_mmsi = str(mmsi).strip()
    if frame.empty:
        return None
    ordered = frame.sort_values("match_rank", kind="stable")
    for _, row in ordered.iterrows():
        row_mmsi = _string_or_none(row.get("mmsi"))
        gfw_id = _string_or_none(row.get("gfw_vessel_id"))
        if (
            row_mmsi == requested_mmsi
            and gfw_id is not None
            and transmission_overlaps_2017_2019(
                row.get("first_transmission"), row.get("last_transmission")
            )
        ):
            return {column: row.get(column) for column in IDENTITY_COLUMNS}
    return None


def selected_identity_map(frame: pd.DataFrame, mmsis: Iterable[str]) -> dict[str, str]:
    """Map queue MMSIs to the single identity ID that is safe to query."""

    selected: dict[str, str] = {}
    for mmsi in mmsis:
        candidate = choose_identity_candidate(frame, str(mmsi))
        if candidate is not None:
            vessel_id = _string_or_none(candidate.get("gfw_vessel_id"))
            if vessel_id is not None:
                selected[str(mmsi)] = vessel_id
    return selected


def _event_detail(entry: Mapping[str, Any], event_type: str) -> dict[str, Any]:
    lower = event_type.lower()
    keys = [lower]
    if event_type == "PORT_VISIT":
        keys.extend(["port_visit", "portVisit", "portvisit"])
    for key in keys:
        value = _as_mapping(entry.get(key))
        if value:
            return value
    return {}


def _port_record(detail: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("port", "endAnchorage", "startAnchorage", "intermediateAnchorage", "anchorage"):
        value = _as_mapping(detail.get(key))
        if value:
            return value
    return {}


def _event_record(
    entry: Mapping[str, Any],
    *,
    event_type: str,
    dataset_version: str | None,
    retrieved_at: str,
    id_to_mmsi: Mapping[str, str] | None,
) -> dict[str, Any]:
    vessel = _as_mapping(entry.get("vessel"))
    detail = _event_detail(entry, event_type)
    position = _as_mapping(_first_value(entry.get("position"), entry.get("location")))
    vessel_id = _string_or_none(_field(vessel, "id", "vesselId", "gfwVesselId"))
    vessel_mmsi = _string_or_none(_field(vessel, "ssvid", "mmsi"))
    if vessel_mmsi is None and vessel_id is not None and id_to_mmsi is not None:
        vessel_mmsi = _string_or_none(id_to_mmsi.get(vessel_id))

    partner = _as_mapping(
        _first_value(
            detail.get("vessel"),
            detail.get("partnerVessel"),
            entry.get("partnerVessel"),
        )
    )
    partner_id = _string_or_none(_field(partner, "id", "vesselId", "gfwVesselId"))
    partner_mmsi = _string_or_none(_field(partner, "ssvid", "mmsi"))
    if partner_mmsi is None and partner_id is not None and id_to_mmsi is not None:
        partner_mmsi = _string_or_none(id_to_mmsi.get(partner_id))

    port = _port_record(detail) if event_type == "PORT_VISIT" else {}
    lat = _valid_lat(_field(position, "lat", "latitude"))
    lon = normalise_lon(_field(position, "lon", "lng", "longitude"))
    if lat is None:
        lon = None

    return {
        "event_type": event_type,
        "event_id": _string_or_none(_field(entry, "id", "eventId")),
        "gfw_vessel_id": vessel_id,
        "mmsi": vessel_mmsi,
        "start": entry.get("start"),
        "end": entry.get("end"),
        "lat": lat,
        "lon": lon,
        "partner_gfw_vessel_id": partner_id,
        "partner_mmsi": partner_mmsi,
        "partner_type": _string_or_none(_field(partner, "type", "vesselType")),
        "median_distance_km": _float_or_none(
            _first_value(
                _field(detail, "medianDistanceKilometers", "medianDistanceKm", "median_distance_km"),
                _field(entry, "medianDistanceKilometers", "medianDistanceKm", "median_distance_km"),
            )
        ),
        "median_speed_kn": _float_or_none(
            _first_value(
                _field(detail, "medianSpeedKnots", "medianSpeedKn", "median_speed_kn"),
                _field(entry, "medianSpeedKnots", "medianSpeedKn", "median_speed_kn"),
            )
        ),
        "port_name": _string_or_none(
            _first_value(_field(port, "name", "portName", "topDestination"), _field(detail, "portName"))
        ),
        "port_country": _string_or_none(
            _first_value(
                _field(port, "country", "countryCode", "flag", "iso3"),
                _field(detail, "portCountry", "country"),
            )
        ),
        "regions_json": _json_string(entry.get("regions")) if entry.get("regions") is not None else None,
        "dataset_version": _string_or_none(_first_value(entry.get("dataset"), dataset_version)),
        "retrieved_at": retrieved_at,
    }


def _normalise_event_frame(records: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(list(records), columns=EVENT_COLUMNS)
    for column in (
        "event_type",
        "event_id",
        "gfw_vessel_id",
        "mmsi",
        "partner_gfw_vessel_id",
        "partner_mmsi",
        "partner_type",
        "port_name",
        "port_country",
        "regions_json",
        "dataset_version",
        "retrieved_at",
    ):
        frame[column] = frame[column].astype("string")
    for column in ("lat", "lon", "median_distance_km", "median_speed_kn"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Float64")
    for column in ("start", "end"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce", utc=True)
    return frame.loc[:, EVENT_COLUMNS]


def parse_events_response(
    payload: Mapping[str, Any],
    event_type: str,
    *,
    retrieved_at: str | None = None,
    dataset_version: str | None = None,
    id_to_mmsi: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Defensively parse one response page into the stable event parquet shape."""

    at = retrieved_at or utc_now()
    records = [
        _event_record(
            entry,
            event_type=event_type,
            dataset_version=dataset_version,
            retrieved_at=at,
            id_to_mmsi=id_to_mmsi,
        )
        for entry in _as_mapping_list(payload.get("entries"))
    ]
    return _normalise_event_frame(records)


# Friendly aliases make the parser intent obvious to callers and small tests.
parse_identity_entries = parse_identity_response
parse_event_entries = parse_events_response


def read_queue_mmsis(path: Path) -> list[str]:
    """Read unique, valid nine-digit queue MMSIs while preserving file order."""

    if not path.exists():
        raise FileNotFoundError(f"Queue MMSI file not found: {path}")
    mmsis: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        mmsi = raw_line.strip()
        if not mmsi:
            continue
        if not (len(mmsi) == 9 and mmsi.isdigit()):
            raise ValueError(f"Invalid MMSI in {path}: {mmsi!r}; expected one 9-digit MMSI per line.")
        if mmsi not in seen:
            seen.add(mmsi)
            mmsis.append(mmsi)
    return mmsis


def load_token(root: Path) -> str:
    """Read the token from the environment first, then the untracked .env file."""

    env_token = os.environ.get("GFW_API_TOKEN", "").strip()
    if env_token:
        return env_token
    dotenv = root / ".env"
    if dotenv.exists():
        for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, separator, value = line.partition("=")
            if separator and key.strip() == "GFW_API_TOKEN":
                token = value.strip()
                if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
                    token = token[1:-1]
                if token:
                    return token
    raise GfwPullError("GFW API token missing. Set GFW_API_TOKEN or add it to the untracked repository-root .env file.")


class GfwApi:
    """Small retrying GFW client that never serializes its Authorization header."""

    def __init__(
        self,
        token: str,
        *,
        client: httpx.Client,
        pause_seconds: float = PAUSE_SECONDS,
        max_retries: int = MAX_RETRIES,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if not token:
            raise ValueError("A non-empty GFW API token is required.")
        self._token = token
        self._client = client
        self._pause_seconds = float(pause_seconds)
        self._max_retries = int(max_retries)
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._last_request_at: float | None = None

    def _wait_for_rate_slot(self) -> None:
        if self._last_request_at is None or self._pause_seconds <= 0:
            return
        remaining = self._pause_seconds - (self._monotonic() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> ApiResponse:
        """Issue one API call, retrying only transient failures up to five times."""

        url = f"{BASE_URL}{path}"
        last_transport_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._wait_for_rate_slot()
            try:
                response = self._client.request(
                    method,
                    url,
                    params=dict(params) if params is not None else None,
                    json=dict(body) if body is not None else None,
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                self._last_request_at = self._monotonic()
            except httpx.RequestError as exc:
                last_transport_error = exc
                if attempt >= self._max_retries:
                    break
                self._sleep(0.5 * (2**attempt))
                continue

            raw = response.content
            headers = dict(response.headers)
            status = response.status_code
            if status in (401, 403):
                raise AuthenticationError(status, method, path, raw, headers)
            if status == 429 or 500 <= status <= 599:
                if attempt >= self._max_retries:
                    raise GfwHttpError(status, method, path, raw, headers)
                retry_after = _float_or_none(response.headers.get("Retry-After"))
                self._sleep(retry_after if retry_after is not None and retry_after >= 0 else 0.5 * (2**attempt))
                continue
            if not 200 <= status <= 299:
                raise GfwHttpError(status, method, path, raw, headers)
            try:
                decoded = response.json()
            except (ValueError, UnicodeDecodeError) as exc:
                raise GfwRequestError(f"GFW returned invalid JSON for {method} {path}.") from exc
            if not isinstance(decoded, Mapping):
                raise GfwRequestError(f"GFW returned a non-object JSON response for {method} {path}.")
            return ApiResponse(dict(decoded), raw, headers, status)

        if last_transport_error is not None:
            raise GfwRequestError(f"GFW request failed after retries for {method} {path}.") from last_transport_error
        raise GfwRequestError(f"GFW request failed after retries for {method} {path}.")

    def identity(self, mmsi: str) -> ApiResponse:
        return self.request(
            "GET",
            "/vessels/search",
            params={
                "query": mmsi,
                "datasets[0]": IDENTITY_DATASET,
                "includes[0]": "MATCH_CRITERIA",
                "includes[1]": "OWNERSHIP",
                "includes[2]": "AUTHORIZATIONS",
                "limit": 50,
            },
        )

    def events(self, dataset: str, event_type: str, vessel_ids: Sequence[str], offset: int) -> ApiResponse:
        return self.request(
            "POST",
            "/events",
            params={"offset": int(offset), "limit": EVENT_PAGE_SIZE},
            body={
                "datasets": [dataset],
                "types": [event_type],
                "startDate": START_DATE,
                "endDate": END_DATE,
                "timeFilterMode": "OVERLAP",
                "vessels": list(vessel_ids),
            },
        )


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NA:
        return None
    raise TypeError(f"Cannot JSON encode {type(value).__name__}")


def write_json(path: Path, value: Mapping[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
        handle.write("\n")
    temporary.replace(path)


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.stem}.tmp{path.suffix}")
    frame.to_parquet(temporary, index=False, engine="pyarrow")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _response_dataset_version(payload: Mapping[str, Any], headers: Mapping[str, str], fallback: str) -> str:
    header_version = headers.get("x-datasets") or headers.get("X-Datasets")
    if _nonempty(header_version):
        return str(header_version)
    metadata = _as_mapping(payload.get("metadata"))
    datasets = metadata.get("datasets")
    if isinstance(datasets, Sequence) and not isinstance(datasets, (str, bytes)) and datasets:
        return str(datasets[0])
    return fallback


def _request_descriptor(
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    descriptor: dict[str, Any] = {"method": method, "path": path}
    if params is not None:
        descriptor["params"] = dict(params)
    if body is not None:
        descriptor["body"] = dict(body)
    # Crucially, no headers are included: that is where the bearer token lives.
    return descriptor


def _response_manifest(
    *,
    request: Mapping[str, Any],
    response_bytes: bytes,
    row_count: int,
    retrieved_at: str,
    status_code: int,
    dataset_version: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "request": dict(request),
        "sha256": hashlib.sha256(response_bytes).hexdigest(),
        "row_count": int(row_count),
        "retrieved_at": retrieved_at,
        "status_code": int(status_code),
    }
    if dataset_version is not None:
        result["dataset_version"] = dataset_version
    if error is not None:
        result["error"] = error
    return result


def _write_error_response(
    directory: Path,
    *,
    request: Mapping[str, Any],
    error: GfwHttpError,
    retrieved_at: str,
) -> None:
    write_bytes(directory / "response.json", error.response_bytes)
    write_json(
        directory / "manifest.json",
        _response_manifest(
            request=request,
            response_bytes=error.response_bytes,
            row_count=0,
            retrieved_at=retrieved_at,
            status_code=error.status_code,
            error=str(error),
        ),
    )


def _manifest_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def _read_raw_payload(path: Path) -> dict[str, Any]:
    return _read_json(path)


def _concat_frames(frames: Iterable[pd.DataFrame], normaliser: Callable[[Iterable[Mapping[str, Any]]], pd.DataFrame]) -> pd.DataFrame:
    materialised = [frame for frame in frames if not frame.empty]
    if not materialised:
        return normaliser([])
    return pd.concat(materialised, ignore_index=True)


def _identity_directory(root: Path, retrieval_id: str, mmsi: str) -> Path:
    return root / "data" / "bronze" / "gfw_identity" / f"retrieval_id={retrieval_id}" / f"mmsi={mmsi}"


def _event_batch_directory(root: Path, retrieval_id: str, event_type: str, batch: int) -> Path:
    return (
        root
        / "data"
        / "bronze"
        / "gfw_events"
        / f"retrieval_id={retrieval_id}"
        / f"type={event_type}"
        / f"batch={batch}"
    )


def _event_page_directory(batch_directory: Path, offset: int) -> Path:
    return batch_directory / f"offset={offset}"


def _page_manifest_dataset_version(page_directory: Path, fallback: str) -> str:
    manifest = _read_json(page_directory / "manifest.json")
    return _string_or_none(manifest.get("dataset_version")) or fallback


def _load_identity_from_directory(directory: Path, mmsi: str) -> pd.DataFrame:
    manifest = _read_json(directory / "manifest.json")
    payload = _read_raw_payload(directory / "response.json")
    if not payload:
        return _normalise_identity_frame([])
    return parse_identity_response(
        payload,
        mmsi,
        retrieved_at=_string_or_none(manifest.get("retrieved_at")) or utc_now(),
        dataset_version=_string_or_none(manifest.get("dataset_version")),
    )


def pull_identities(
    api: GfwApi,
    root: Path,
    retrieval_id: str,
    mmsis: Iterable[str],
    *,
    resume: bool = False,
) -> IdentityPullResult:
    """Fetch or resume every requested identity and return its ranked candidates."""

    requested = [str(mmsi) for mmsi in mmsis]
    frames: list[pd.DataFrame] = []
    frames_by_query: list[tuple[str, pd.DataFrame]] = []
    four_xx: list[dict[str, Any]] = []
    first_entry: dict[str, Any] | None = None

    for mmsi in requested:
        directory = _identity_directory(root, retrieval_id, mmsi)
        manifest_path = directory / "manifest.json"
        if resume and _manifest_exists(manifest_path):
            resumed = _load_identity_from_directory(directory, mmsi)
            frames.append(resumed)
            frames_by_query.append((mmsi, resumed))
            if first_entry is None:
                payload = _read_raw_payload(directory / "response.json")
                entries = _as_mapping_list(payload.get("entries"))
                first_entry = entries[0] if entries else None
            continue

        params = {
            "query": mmsi,
            "datasets[0]": IDENTITY_DATASET,
            "includes[0]": "MATCH_CRITERIA",
            "includes[1]": "OWNERSHIP",
            "includes[2]": "AUTHORIZATIONS",
            "limit": 50,
        }
        request = _request_descriptor("GET", "/vessels/search", params=params)
        retrieved_at = utc_now()
        try:
            response = api.identity(mmsi)
        except GfwHttpError as error:
            _write_error_response(directory, request=request, error=error, retrieved_at=retrieved_at)
            if error.status_code not in (401, 403) and 400 <= error.status_code <= 499:
                four_xx.append(
                    {"dataset": IDENTITY_DATASET, "mmsi": mmsi, "status_code": error.status_code}
                )
                continue
            raise

        version = _response_dataset_version(response.payload, response.headers, IDENTITY_DATASET)
        entries = _as_mapping_list(response.payload.get("entries"))
        write_bytes(directory / "response.json", response.response_bytes)
        write_json(
            manifest_path,
            _response_manifest(
                request=request,
                response_bytes=response.response_bytes,
                row_count=len(entries),
                retrieved_at=retrieved_at,
                status_code=response.status_code,
                dataset_version=version,
            ),
        )
        parsed = parse_identity_response(
            response.payload,
            mmsi,
            retrieved_at=retrieved_at,
            dataset_version=version,
        )
        frames.append(parsed)
        frames_by_query.append((mmsi, parsed))
        if first_entry is None:
            first_entry = entries[0] if entries else None

    frame = _concat_frames(frames, _normalise_identity_frame)
    # Resolve against each response before concatenating candidates. A broad
    # search response can contain another queue MMSI as a lower-ranked alias;
    # letting it leak into a different query's selection would be unsound.
    resolved: dict[str, str] = {}
    for requested_mmsi, queried_frame in frames_by_query:
        candidate = choose_identity_candidate(queried_frame, requested_mmsi)
        vessel_id = _string_or_none(candidate.get("gfw_vessel_id")) if candidate is not None else None
        if vessel_id is not None:
            resolved[requested_mmsi] = vessel_id
    unresolved = [mmsi for mmsi in requested if mmsi not in resolved]
    return IdentityPullResult(frame, resolved, unresolved, four_xx, first_entry)


def _load_event_batch(
    batch_directory: Path,
    *,
    event_type: str,
    dataset: str,
    id_to_mmsi: Mapping[str, str],
) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    frames: list[pd.DataFrame] = []
    first_entry: dict[str, Any] | None = None
    page_paths = sorted(batch_directory.glob("offset=*/response.json"), key=lambda path: path.parent.name)
    for response_path in page_paths:
        payload = _read_raw_payload(response_path)
        if not payload:
            continue
        entries = _as_mapping_list(payload.get("entries"))
        if first_entry is None and entries:
            first_entry = entries[0]
        version = _page_manifest_dataset_version(response_path.parent, dataset)
        manifest = _read_json(response_path.parent / "manifest.json")
        frames.append(
            parse_events_response(
                payload,
                event_type,
                dataset_version=version,
                retrieved_at=_string_or_none(manifest.get("retrieved_at")) or utc_now(),
                id_to_mmsi=id_to_mmsi,
            )
        )
    return _concat_frames(frames, _normalise_event_frame), first_entry


def pull_event_batch(
    api: GfwApi,
    root: Path,
    retrieval_id: str,
    *,
    event_type: str,
    dataset: str,
    batch: int,
    vessel_ids: Sequence[str],
    id_to_mmsi: Mapping[str, str],
    resume: bool = False,
    max_pages: int | None = None,
) -> EventBatchResult:
    """Pull one <=50-vessel event batch, following ``nextOffset`` until null."""

    batch_directory = _event_batch_directory(root, retrieval_id, event_type, batch)
    batch_manifest_path = batch_directory / "manifest.json"
    if resume and _manifest_exists(batch_manifest_path):
        frame, first_entry = _load_event_batch(
            batch_directory,
            event_type=event_type,
            dataset=dataset,
            id_to_mmsi=id_to_mmsi,
        )
        return EventBatchResult(frame, [], first_entry, skipped=True, complete=True)

    body = {
        "datasets": [dataset],
        "types": [event_type],
        "startDate": START_DATE,
        "endDate": END_DATE,
        "timeFilterMode": "OVERLAP",
        "vessels": list(vessel_ids),
    }
    offset = 0
    seen_offsets: set[int] = set()
    frames: list[pd.DataFrame] = []
    page_count = 0
    first_entry: dict[str, Any] | None = None

    while True:
        if offset in seen_offsets:
            raise GfwRequestError(
                f"GFW pagination repeated offset {offset} for {event_type} batch {batch}; stopping to avoid a loop."
            )
        seen_offsets.add(offset)
        params = {"offset": offset, "limit": EVENT_PAGE_SIZE}
        request = _request_descriptor("POST", "/events", params=params, body=body)
        page_directory = _event_page_directory(batch_directory, offset)
        retrieved_at = utc_now()
        try:
            response = api.events(dataset, event_type, vessel_ids, offset)
        except GfwHttpError as error:
            _write_error_response(page_directory, request=request, error=error, retrieved_at=retrieved_at)
            write_json(
                batch_manifest_path,
                {
                    "request": request,
                    "retrieved_at": retrieved_at,
                    "complete": False,
                    "pages": page_count,
                    "row_count": int(sum(len(frame) for frame in frames)),
                    "status_code": error.status_code,
                    "error": str(error),
                },
            )
            if error.status_code not in (401, 403) and 400 <= error.status_code <= 499:
                return EventBatchResult(
                    _concat_frames(frames, _normalise_event_frame),
                    [{"dataset": dataset, "event_type": event_type, "batch": batch, "status_code": error.status_code}],
                    first_entry,
                    skipped=False,
                    complete=False,
                )
            raise

        version = _response_dataset_version(response.payload, response.headers, dataset)
        entries = _as_mapping_list(response.payload.get("entries"))
        write_bytes(page_directory / "response.json", response.response_bytes)
        write_json(
            page_directory / "manifest.json",
            _response_manifest(
                request=request,
                response_bytes=response.response_bytes,
                row_count=len(entries),
                retrieved_at=retrieved_at,
                status_code=response.status_code,
                dataset_version=version,
            ),
        )
        frames.append(
            parse_events_response(
                response.payload,
                event_type,
                retrieved_at=retrieved_at,
                dataset_version=version,
                id_to_mmsi=id_to_mmsi,
            )
        )
        if first_entry is None and entries:
            first_entry = entries[0]
        page_count += 1
        next_offset = response.payload.get("nextOffset")
        stopped_early = max_pages is not None and page_count >= max_pages and next_offset is not None
        if next_offset is None or next_offset == "" or stopped_early:
            frame = _concat_frames(frames, _normalise_event_frame)
            write_json(
                batch_manifest_path,
                {
                    "request": _request_descriptor(
                        "POST",
                        "/events",
                        params={"limit": EVENT_PAGE_SIZE},
                        body=body,
                    ),
                    "retrieved_at": utc_now(),
                    "complete": not stopped_early,
                    "stopped_early": stopped_early,
                    "pages": page_count,
                    "row_count": int(len(frame)),
                    "offsets": sorted(seen_offsets),
                    "dataset_version": version,
                },
            )
            return EventBatchResult(frame, [], first_entry, skipped=False, complete=not stopped_early)
        try:
            offset = int(next_offset)
        except (TypeError, ValueError) as exc:
            raise GfwRequestError(
                f"GFW returned an invalid nextOffset for {event_type} batch {batch}: {next_offset!r}."
            ) from exc


def _batches(values: Sequence[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield list(values[start : start + size])


def pull_events(
    api: GfwApi,
    root: Path,
    retrieval_id: str,
    resolved_by_mmsi: Mapping[str, str],
    *,
    resume: bool = False,
    dry_run: bool = False,
) -> tuple[pd.DataFrame, dict[str, int], list[dict[str, Any]], dict[str, dict[str, Any] | None]]:
    """Pull all three event families for resolved IDs, or one dry-run page."""

    # Preserve the queue order while protecting a query from duplicate vessel IDs.
    vessel_ids = list(dict.fromkeys(resolved_by_mmsi.values()))
    id_to_mmsi = {vessel_id: mmsi for mmsi, vessel_id in resolved_by_mmsi.items()}
    event_types = ["ENCOUNTER"] if dry_run else list(EVENT_DATASETS)
    frames: list[pd.DataFrame] = []
    counts = {event_type: 0 for event_type in EVENT_DATASETS}
    four_xx: list[dict[str, Any]] = []
    first_entries: dict[str, dict[str, Any] | None] = {event_type: None for event_type in EVENT_DATASETS}

    if not vessel_ids:
        return _normalise_event_frame([]), counts, four_xx, first_entries

    batches = [vessel_ids[:1]] if dry_run else list(_batches(vessel_ids, EVENT_BATCH_SIZE))
    for event_type in event_types:
        dataset = EVENT_DATASETS[event_type]
        for batch_index, batch_ids in enumerate(batches):
            result = pull_event_batch(
                api,
                root,
                retrieval_id,
                event_type=event_type,
                dataset=dataset,
                batch=batch_index,
                vessel_ids=batch_ids,
                id_to_mmsi=id_to_mmsi,
                resume=resume and not dry_run,
                max_pages=1 if dry_run else None,
            )
            frames.append(result.frame)
            counts[event_type] += int(len(result.frame))
            four_xx.extend(result.dataset_4xx)
            if first_entries[event_type] is None:
                first_entries[event_type] = result.first_entry

    return _concat_frames(frames, _normalise_event_frame), counts, four_xx, first_entries


def _read_previous_pull_manifest(root: Path) -> dict[str, Any]:
    return _read_json(root / "data" / "reference" / "gfw_queue_pull_manifest.json")


def _discover_retrieval_id(root: Path) -> str | None:
    candidates: list[str] = []
    for relative in (Path("data/bronze/gfw_identity"), Path("data/bronze/gfw_events")):
        base = root / relative
        if not base.exists():
            continue
        candidates.extend(path.name.removeprefix("retrieval_id=") for path in base.glob("retrieval_id=*") if path.is_dir())
    return max(candidates) if candidates else None


def resolve_retrieval_id(root: Path, *, resume: bool, requested: str | None) -> str:
    if requested:
        return requested
    if resume:
        previous = _read_previous_pull_manifest(root)
        saved = _string_or_none(previous.get("retrieval_id"))
        if saved:
            return saved
        discovered = _discover_retrieval_id(root)
        if discovered:
            return discovered
    return new_retrieval_id()


def _load_identity_reference(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Identity reference table not found: {path}. Run without --only events (or run --only identity) first."
        )
    frame = pd.read_parquet(path)
    missing = set(IDENTITY_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Identity reference table is missing required columns: {sorted(missing)}")
    # Reapply parser dtypes because a different pandas/pyarrow version may have
    # loaded nullable strings as object.
    return _normalise_identity_frame(frame.loc[:, IDENTITY_COLUMNS].to_dict("records"))


def _manifest_payload(
    *,
    retrieval_id: str,
    mode: str,
    requested_mmsis: Sequence[str],
    resolved_by_mmsi: Mapping[str, str],
    unresolved_mmsis: Sequence[str],
    counts_per_type: Mapping[str, int],
    datasets_4xx: Sequence[Mapping[str, Any]],
    status: str,
) -> dict[str, Any]:
    return {
        "retrieval_id": retrieval_id,
        "retrieval_ids": {"identity": retrieval_id, "events": retrieval_id},
        "generated_at": utc_now(),
        "status": status,
        "mode": mode,
        "mmsis": {
            "requested_count": len(requested_mmsis),
            "resolved_count": len(resolved_by_mmsi),
            "unresolved_count": len(unresolved_mmsis),
            "resolved": sorted(resolved_by_mmsi),
            "unresolved": sorted(unresolved_mmsis),
        },
        "counts_per_type": {event_type: int(counts_per_type.get(event_type, 0)) for event_type in EVENT_DATASETS},
        "datasets_returned_4xx": [dict(item) for item in datasets_4xx],
    }


def run_pull(
    *,
    root: Path | str | None = None,
    only: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
    retrieval_id: str | None = None,
    token: str | None = None,
    client: httpx.Client | None = None,
    pause_seconds: float = PAUSE_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run the pull and return the final safe-to-write manifest object.

    ``client`` and ``sleep_fn`` are dependency-injection hooks for tests; callers
    normally leave both unset.  No HTTP call is made during module import.
    """

    root_path = Path(root) if root is not None else default_repo_root()
    if only not in (None, "identity", "events"):
        raise ValueError("only must be one of: None, 'identity', or 'events'.")
    active_retrieval_id = resolve_retrieval_id(root_path, resume=resume, requested=retrieval_id)
    owns_client = client is None
    active_client = client or httpx.Client(timeout=httpx.Timeout(30.0))
    active_token = token if token is not None else load_token(root_path)
    api = GfwApi(active_token, client=active_client, pause_seconds=pause_seconds, sleep_fn=sleep_fn)

    identity_path = root_path / "data" / "reference" / "vessel_identity.parquet"
    events_path = root_path / "data" / "reference" / "gfw_events_queue.parquet"
    final_path = root_path / "data" / "reference" / "gfw_queue_pull_manifest.json"
    requested_mmsis: list[str] = [SHOWCASE_MMSI] if dry_run else read_queue_mmsis(root_path / "data" / "derived" / "queue_mmsis.txt")
    needs_identity = dry_run or only in (None, "identity")
    needs_events = dry_run or only in (None, "events")
    identity_result: IdentityPullResult | None = None
    resolved_by_mmsi: dict[str, str] = {}
    unresolved_mmsis: list[str] = []
    counts_per_type = {event_type: 0 for event_type in EVENT_DATASETS}
    datasets_4xx: list[dict[str, Any]] = []
    status = "complete"

    try:
        if needs_identity:
            identity_result = pull_identities(
                api,
                root_path,
                active_retrieval_id,
                requested_mmsis,
                resume=resume and not dry_run,
            )
            write_parquet(identity_path, identity_result.frame)
            resolved_by_mmsi = identity_result.resolved_by_mmsi
            unresolved_mmsis = identity_result.unresolved_mmsis
            datasets_4xx.extend(identity_result.dataset_4xx)
        else:
            identity_frame = _load_identity_reference(identity_path)
            resolved_by_mmsi = selected_identity_map(identity_frame, requested_mmsis)
            unresolved_mmsis = [mmsi for mmsi in requested_mmsis if mmsi not in resolved_by_mmsi]

        if needs_events:
            event_identity_map = resolved_by_mmsi
            if dry_run and not event_identity_map:
                raise GfwPullError(
                    "Dry-run identity response contained no eligible GFW vessel ID for the requested MMSI; "
                    "no ENCOUNTER request was made."
                )
            event_frame, counts_per_type, event_4xx, first_entries = pull_events(
                api,
                root_path,
                active_retrieval_id,
                event_identity_map,
                resume=resume,
                dry_run=dry_run,
            )
            write_parquet(events_path, event_frame)
            datasets_4xx.extend(event_4xx)
            if dry_run:
                _write_dry_run_entries(
                    identity_result.first_entry if identity_result is not None else None,
                    first_entries.get("ENCOUNTER"),
                )

        manifest = _manifest_payload(
            retrieval_id=active_retrieval_id,
            mode="dry-run" if dry_run else only or "all",
            requested_mmsis=requested_mmsis,
            resolved_by_mmsi=resolved_by_mmsi,
            unresolved_mmsis=unresolved_mmsis,
            counts_per_type=counts_per_type,
            datasets_4xx=datasets_4xx,
            status=status,
        )
        write_json(final_path, manifest)
        return manifest
    except GfwPullError:
        status = "failed"
        manifest = _manifest_payload(
            retrieval_id=active_retrieval_id,
            mode="dry-run" if dry_run else only or "all",
            requested_mmsis=requested_mmsis,
            resolved_by_mmsi=resolved_by_mmsi,
            unresolved_mmsis=unresolved_mmsis,
            counts_per_type=counts_per_type,
            datasets_4xx=datasets_4xx,
            status=status,
        )
        write_json(final_path, manifest)
        raise
    finally:
        if owns_client:
            active_client.close()


def _write_dry_run_entries(identity_entry: Mapping[str, Any] | None, encounter_entry: Mapping[str, Any] | None) -> None:
    """Print only public response entries, never headers or credentials."""

    sys.stdout.write("Identity first entry:\n")
    sys.stdout.write(json.dumps(identity_entry, ensure_ascii=False, indent=2, default=_json_default))
    sys.stdout.write("\nENCOUNTER first entry:\n")
    sys.stdout.write(json.dumps(encounter_entry, ensure_ascii=False, indent=2, default=_json_default))
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=("identity", "events"),
        help="Run just identity pulls or just event pulls. Dry-run always makes its two schema-probe calls.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Make exactly one identity call for 412331147 and one ENCOUNTER page, then print first entries.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse the prior retrieval ID and skip identity MMSIs / event batches with manifests.",
    )
    parser.add_argument(
        "--retrieval-id",
        help="Explicit UTC retrieval ID; useful when resuming an interrupted run before its final manifest exists.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Repository root (defaults to the parent of this script); useful for isolated test runs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_pull(
            root=args.root,
            only=args.only,
            dry_run=args.dry_run,
            resume=args.resume,
            retrieval_id=args.retrieval_id,
        )
    except (GfwPullError, FileNotFoundError, ValueError) as exc:
        # The text is deliberately credential-free; do not add response headers
        # or request representations here because they include Authorization.
        sys.stderr.write(f"pull_queue_events: {exc}\n")
        return 2
    sys.stdout.write(
        "Pull complete: "
        + ", ".join(f"{name}={count}" for name, count in manifest["counts_per_type"].items())
        + f"; resolved={manifest['mmsis']['resolved_count']}; unresolved={manifest['mmsis']['unresolved_count']}.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
