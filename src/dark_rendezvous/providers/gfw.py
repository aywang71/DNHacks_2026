"""Auditable client for Global Fishing Watch derived event and identity lookups."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd


GFW_GAP_ENDPOINT_COLUMNS: tuple[str, ...] = (
    "endpoint_id",
    "event_id",
    "endpoint_role",
    "ts",
    "lat",
    "lon",
    "vessel_id",
    "gfw_vessel_id",
    "mmsi",
    "vessel_name",
    "flag_state",
    "vessel_type",
    "duration_hours",
    "implied_speed_knots",
    "positions_12h_before_sat",
    "positions_per_day_sat_reception",
    "intentional_disabling",
    "gap_is_closed",
    "source",
    "dataset_version",
    "source_uri",
    "ingested_at",
    "raw_payload_hash",
    "quality_flags",
    "is_valid_endpoint",
)


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalize_gap_endpoints(
    payload: dict[str, Any],
    *,
    source_uri: str,
    raw_payload_hash: str,
    dataset_version: str,
) -> pd.DataFrame:
    """Expand each derived GFW GAP event into one off and one on endpoint row.

    These rows satisfy the ts/lat/lon/vessel_id analytical shape but are not
    raw AIS positions. They contain exactly the two observations GFW exposes
    for a completed gap and remain in a distinct gfw_gap_endpoints table.
    """
    rows: list[dict[str, Any]] = []
    ingested_at = datetime.now(timezone.utc).isoformat()
    for event in payload.get("entries", []):
        gap = event.get("gap") or {}
        vessel = event.get("vessel") or {}
        gfw_vessel_id = vessel.get("id")
        mmsi = vessel.get("ssvid")
        vessel_id = (
            f"gfw:{gfw_vessel_id}"
            if gfw_vessel_id
            else f"mmsi:{mmsi}"
            if mmsi
            else None
        )
        common = {
            "event_id": event.get("id"),
            "vessel_id": vessel_id,
            "gfw_vessel_id": gfw_vessel_id,
            "mmsi": str(mmsi) if mmsi is not None else None,
            "vessel_name": vessel.get("name"),
            "flag_state": vessel.get("flag"),
            "vessel_type": vessel.get("type"),
            "duration_hours": _float_or_none(gap.get("durationHours")),
            "implied_speed_knots": _float_or_none(gap.get("impliedSpeedKnots")),
            "positions_12h_before_sat": _float_or_none(gap.get("positions12HoursBeforeSat")),
            "positions_per_day_sat_reception": _float_or_none(gap.get("positionsPerDaySatReception")),
            "intentional_disabling": gap.get("intentionalDisabling"),
            "gap_is_closed": event.get("end") is not None,
            "source": "global_fishing_watch_events",
            "dataset_version": dataset_version,
            "source_uri": source_uri,
            "ingested_at": ingested_at,
            "raw_payload_hash": raw_payload_hash,
        }
        endpoint_specs = [("off", "start", "offPosition")]
        if event.get("end") is not None:
            endpoint_specs.append(("on", "end", "onPosition"))
        for endpoint_role, ts_key, position_key in endpoint_specs:
            position = gap.get(position_key) or {}
            rows.append(
                {
                    **common,
                    "endpoint_id": f"{event.get('id')}:{endpoint_role}",
                    "endpoint_role": endpoint_role,
                    "ts": event.get(ts_key),
                    "lat": _float_or_none(position.get("lat")),
                    "lon": _float_or_none(position.get("lon")),
                }
            )
    output = pd.DataFrame(rows, columns=GFW_GAP_ENDPOINT_COLUMNS)
    if not output.empty:
        output["ts"] = pd.to_datetime(output["ts"], errors="coerce", utc=True)
        valid_ts = output["ts"].notna()
        valid_coordinates = output["lat"].between(-90, 90) & output["lon"].between(-180, 180)
        valid_identity = output["vessel_id"].notna()
        flags = pd.Series("", index=output.index, dtype="string")
        flags = flags.mask(~valid_ts, flags + "missing_or_invalid_ts;")
        flags = flags.mask(~valid_coordinates, flags + "invalid_coordinates;")
        flags = flags.mask(~valid_identity, flags + "missing_vessel_id;")
        output["quality_flags"] = flags.str.rstrip(";").mask(flags.eq(""), "[]")
        output["is_valid_endpoint"] = valid_ts & valid_coordinates & valid_identity
    return output


class GfwClient:
    """Use GFW V3 derived-data endpoints, never as a raw-AIS message feed."""

    base_url = "https://gateway.api.globalfishingwatch.org/v3"
    identity_dataset = "public-global-vessel-identity:latest"
    gaps_dataset = "public-global-gaps-events:latest"
    tracks_dataset = "public-global-fishing-tracks:latest"
    presence_dataset = "public-global-presence:latest"

    def __init__(self, token: str, *, timeout_seconds: float = 30.0) -> None:
        if not token:
            raise ValueError("GFW API token is required.")
        self._token = token
        self._timeout_seconds = timeout_seconds
        self.last_dataset_version: str | None = None

    def _get(self, path: str, params: Any, *, extra_headers: dict[str, str] | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self._token}"}
        if extra_headers:
            headers.update(extra_headers)
        response = httpx.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        self.last_dataset_version = response.headers.get("x-datasets")
        return response.json()

    def _post(self, path: str, *, params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}{path}",
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        self.last_dataset_version = response.headers.get("x-datasets")
        return response.json()

    def search_identity(self, query: str) -> dict[str, Any]:
        """Return the provider's unmodified identity response for an IMO/MMSI/name."""
        return self._get(
            "/vessels/search",
            {
                "query": query,
                "datasets[0]": self.identity_dataset,
                "includes[0]": "MATCH_CRITERIA",
                "includes[1]": "OWNERSHIP",
                "limit": 50,
            },
        )

    def gap_events(
        self,
        *,
        start_date: str,
        end_date: str,
        offset: int = 0,
        limit: int = 100,
        time_filter_mode: str = "OVERLAP",
        intentional_disabling: bool | None = None,
    ) -> dict[str, Any]:
        """Fetch one documented page of derived GFW GAP events."""
        body: dict[str, Any] = {
            "datasets": [self.gaps_dataset],
            "types": ["GAP"],
            "startDate": start_date,
            "endDate": end_date,
            "timeFilterMode": time_filter_mode,
        }
        if intentional_disabling is not None:
            body["gapIntentionalDisabling"] = intentional_disabling
        return self._post(
            "/events",
            params={"offset": offset, "limit": limit},
            body=body,
        )

    def track_lines(
        self,
        *,
        vessel_id: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Fetch GFW's JSON, non-binary vessel-track representation.

        This is a provider-derived track representation, not an AIS-message
        endpoint. Deliberately omit server-side thinning so the API returns its
        greatest available native detail; a separate view can downsample it to
        hourly points for frontend use.
        """
        params: list[tuple[str, str]] = [
            ("dataset", self.tracks_dataset),
            ("start-date", start_date),
            ("end-date", end_date),
            ("format", "LINES"),
            ("binary", "false"),
            ("fields[0]", "LONLAT"),
            ("fields[1]", "TIMESTAMP"),
            ("fields[2]", "SPEED"),
            ("fields[3]", "COURSE"),
        ]
        return self._get(f"/vessels/{vessel_id}/tracks", params)

    def presence_report(
        self,
        *,
        start: str,
        end: str,
        region_id: int | None = None,
        region_dataset: str = "public-eez-areas",
        spatial_resolution: str = "HIGH",
        temporal_resolution: str = "HOURLY",
        geojson: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch one GFW 4Wings AIS-Presence report for a bounded region/time.

        The API serializes reports per user. This method intentionally makes a
        single request, rather than hiding a broad global backfill behind a
        retry loop. Existing GFW context-layer regions use GET; a custom
        GeoJSON geometry must use POST, per the provider's API contract.
        """
        if (region_id is None) == (geojson is None):
            raise ValueError("Specify exactly one of region_id or geojson for a GFW Presence report.")
        params = {
            "datasets[0]": self.presence_dataset,
            "date-range": f"{start},{end}",
            "format": "JSON",
            "group-by": "VESSEL_ID",
            "temporal-resolution": temporal_resolution,
            "spatial-resolution": spatial_resolution,
            "spatial-aggregation": "false",
        }
        if geojson is not None:
            return self._post("/4wings/report", params=params, body={"geojson": geojson})
        return self._get(
            "/4wings/report",
            {
                **params,
                "region-id": region_id,
                "region-dataset": region_dataset,
            },
            extra_headers={"Content-Language": "en-EN"},
        )

    def last_presence_report(self) -> dict[str, Any]:
        """Return this account's last generated 4Wings report for explicit recovery."""
        return self._get("/4wings/last-report", {})
