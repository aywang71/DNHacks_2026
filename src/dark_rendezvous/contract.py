"""Canonical AIS position contract and provider-field normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import pandas as pd


CANONICAL_POSITION_COLUMNS: tuple[str, ...] = (
    "position_id",
    "source",
    "source_record_id",
    "dataset_version",
    "source_uri",
    "ingested_at",
    "ts",
    "vessel_id",
    "mmsi",
    "imo",
    "callsign",
    "vessel_name",
    "lat",
    "lon",
    "sog_kn",
    "cog_deg",
    "heading_deg",
    "nav_status",
    "transceiver_class",
    "collection_mode",
    "raw_payload_hash",
    "quality_flags",
    "is_valid_position",
)


def clean_identifier(values: pd.Series) -> pd.Series:
    """Return nullable text identifiers without CSV-added decimal suffixes."""
    cleaned = values.astype("string").str.strip()
    cleaned = cleaned.str.replace(r"^([0-9]+)\.0$", r"\1", regex=True)
    return cleaned.mask(cleaned.isin(["", "nan", "None", "<NA>"]))


def _column_lookup(frame: pd.DataFrame) -> dict[str, str]:
    return {
        "".join(character for character in column.lower() if character.isalnum()): column
        for column in frame.columns
    }


def _field(
    frame: pd.DataFrame,
    aliases: Sequence[str],
    *,
    default: object = pd.NA,
) -> pd.Series:
    lookup = _column_lookup(frame)
    for alias in aliases:
        normalized = "".join(character for character in alias.lower() if character.isalnum())
        column = lookup.get(normalized)
        if column is not None:
            return frame[column]
    return pd.Series(default, index=frame.index)


def canonicalize_positions(
    frame: pd.DataFrame,
    *,
    source: str,
    source_uri: str,
    raw_payload_hash: str,
    dataset_version: str = "unknown",
    collection_mode: str = "unknown",
) -> pd.DataFrame:
    """Map raw AIS rows to the project-wide provenance-preserving schema.

    Invalid rows are retained and flagged. This permits later audit and
    coverage analysis rather than silently changing provider history.
    """
    ts = pd.to_datetime(
        _field(frame, ("observed_at", "timestamp", "base_date_time", "basedatetime", "time", "ts")),
        errors="coerce",
        utc=True,
    )
    mmsi = clean_identifier(_field(frame, ("mmsi", "maritime_mobile_service_identity")))
    imo = clean_identifier(_field(frame, ("imo", "imo_number")))
    callsign = clean_identifier(_field(frame, ("callsign", "call_sign")))
    vessel_name = clean_identifier(_field(frame, ("vesselname", "vessel_name", "name", "shipname")))
    lat = pd.to_numeric(_field(frame, ("lat", "latitude")), errors="coerce")
    lon = pd.to_numeric(_field(frame, ("lon", "longitude", "lng")), errors="coerce")

    vessel_id = pd.Series(pd.NA, index=frame.index, dtype="string")
    vessel_id = vessel_id.mask(imo.notna(), "imo:" + imo)
    vessel_id = vessel_id.mask(vessel_id.isna() & mmsi.notna(), "mmsi:" + mmsi)

    valid_ts = ts.notna()
    valid_coordinates = lat.between(-90, 90) & lon.between(-180, 180)
    valid_identity = vessel_id.notna()
    flags = pd.Series("", index=frame.index, dtype="string")
    flags = flags.mask(~valid_ts, flags + "missing_or_invalid_ts;")
    flags = flags.mask(~valid_coordinates, flags + "invalid_coordinates;")
    flags = flags.mask(~valid_identity, flags + "missing_vessel_id;")
    flags = flags.str.rstrip(";").mask(flags.eq(""), "[]")

    source_record_id = clean_identifier(
        _field(frame, ("source_record_id", "record_id", "message_id", "id"))
    )
    source_record_id = source_record_id.fillna(
        mmsi.fillna("unknown")
        + "|"
        + ts.astype("string").fillna("unknown")
        + "|"
        + lat.astype("string").fillna("unknown")
        + "|"
        + lon.astype("string").fillna("unknown")
    )

    key_frame = pd.DataFrame(
        {"source": source, "record": source_record_id, "ts": ts.astype("string"), "lat": lat, "lon": lon}
    )
    position_hash = pd.util.hash_pandas_object(key_frame, index=False).astype("uint64")
    position_id = source + ":" + position_hash.map(lambda value: f"{value:016x}")

    output = pd.DataFrame(
        {
            "position_id": position_id,
            "source": source,
            "source_record_id": source_record_id,
            "dataset_version": dataset_version,
            "source_uri": source_uri,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "ts": ts,
            "vessel_id": vessel_id,
            "mmsi": mmsi,
            "imo": imo,
            "callsign": callsign,
            "vessel_name": vessel_name,
            "lat": lat,
            "lon": lon,
            "sog_kn": pd.to_numeric(_field(frame, ("sog", "speed", "speed_over_ground")), errors="coerce"),
            "cog_deg": pd.to_numeric(_field(frame, ("cog", "course", "course_over_ground")), errors="coerce"),
            "heading_deg": pd.to_numeric(_field(frame, ("heading", "true_heading")), errors="coerce"),
            "nav_status": clean_identifier(_field(frame, ("status", "nav_status", "navigation_status"))),
            "transceiver_class": clean_identifier(_field(frame, ("transceiver", "transceiver_class", "transceiverclass", "ais_class"))),
            "collection_mode": collection_mode,
            "raw_payload_hash": raw_payload_hash,
            "quality_flags": flags,
            "is_valid_position": valid_ts & valid_coordinates & valid_identity,
        }
    )
    return output.loc[:, CANONICAL_POSITION_COLUMNS]

