"""NOAA Marine Cadastre daily broadcast-point ingestion."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from shapely import from_wkb, get_x, get_y

from ..contract import canonicalize_positions
from ..storage import sha256_file


@dataclass(frozen=True)
class DownloadedObject:
    path: Path
    source_uri: str
    sha256: str


class NoaaMarineCadastreProvider:
    """Fetch public daily U.S. AIS broadcast points and normalize them."""

    source_columns = (
        "mmsi",
        "base_date_time",
        "sog",
        "cog",
        "heading",
        "vessel_name",
        "imo",
        "call_sign",
        "status",
        "transceiver",
        "geometry",
    )

    legacy_csv_columns = frozenset(
        {
            "mmsi",
            "basedatetime",
            "lat",
            "lon",
            "latitude",
            "longitude",
            "sog",
            "cog",
            "heading",
            "vesselname",
            "imo",
            "callsign",
            "status",
            "transceiverclass",
            "transceiver",
        }
    )

    def url_for(self, day: date) -> str:
        if 2018 <= day.year <= 2023:
            return (
                "https://noaaocm.blob.core.windows.net/"
                f"ais/csv2/csv{day.year}/ais-{day.isoformat()}.csv.zst"
            )
        return (
            "https://ocmgeodatastor1.blob.core.windows.net/"
            f"marinecadastre/ais{day.year}/ais-{day.isoformat()}.parquet"
        )

    def download(self, day: date, bronze_root: Path) -> DownloadedObject:
        source_uri = self.url_for(day)
        filename = source_uri.rsplit("/", maxsplit=1)[-1]
        destination = bronze_root / "noaa_marine_cadastre" / str(day.year) / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_suffix(".part")
            request = Request(source_uri, headers={"User-Agent": "dark-rendezvous/0.1"})
            with urlopen(request, timeout=120) as response, temporary.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
            temporary.replace(destination)
        return DownloadedObject(destination, source_uri, sha256_file(destination))

    @staticmethod
    def _legacy_csv_coordinates(frame: pd.DataFrame) -> tuple[str, str]:
        lookup = {"".join(character for character in column.lower() if character.isalnum()): column for column in frame.columns}
        try:
            lat_column = lookup.get("lat") or lookup.get("latitude")
            lon_column = lookup.get("lon") or lookup.get("longitude")
            if lat_column is None or lon_column is None:
                raise KeyError("lat/lon")
            return lat_column, lon_column
        except KeyError as error:
            raise ValueError("NOAA legacy CSV is missing LAT or LON") from error

    def _normalize_legacy_csv(
        self,
        raw: DownloadedObject,
        bbox: tuple[float, float, float, float] | None,
    ) -> pd.DataFrame:
        if bbox is None:
            raise ValueError(
                "NOAA legacy CSV pulls require --bbox to avoid materializing a nationwide daily file."
            )
        min_lon, min_lat, max_lon, max_lat = bbox
        chunks: list[pd.DataFrame] = []
        reader = pd.read_csv(
            raw.path,
            compression="zstd",
            low_memory=False,
            chunksize=250_000,
            usecols=lambda column: "".join(character for character in column.lower() if character.isalnum())
            in self.legacy_csv_columns,
        )
        for chunk in reader:
            lat_column, lon_column = self._legacy_csv_coordinates(chunk)
            clipped = chunk.loc[
                pd.to_numeric(chunk[lon_column], errors="coerce").between(min_lon, max_lon)
                & pd.to_numeric(chunk[lat_column], errors="coerce").between(min_lat, max_lat)
            ]
            if not clipped.empty:
                chunks.append(clipped)
        if chunks:
            frame = pd.concat(chunks, ignore_index=True)
        else:
            frame = pd.DataFrame(columns=["MMSI", "BaseDateTime", "LAT", "LON"])
        return canonicalize_positions(
            frame,
            source="noaa_marine_cadastre",
            source_uri=raw.source_uri,
            raw_payload_hash=raw.sha256,
            dataset_version=str(raw.path.parent.name),
            collection_mode="terrestrial",
            position_semantics="terrestrial_ais_minute_downsampled",
        )

    def normalize(
        self,
        raw: DownloadedObject,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> pd.DataFrame:
        if raw.path.name.endswith(".csv.zst"):
            return self._normalize_legacy_csv(raw, bbox)
        frame = pd.read_parquet(raw.path, columns=list(self.source_columns))
        geometry = from_wkb(frame.pop("geometry").to_numpy())
        frame["longitude"] = get_x(geometry)
        frame["latitude"] = get_y(geometry)
        return canonicalize_positions(
            frame,
            source="noaa_marine_cadastre",
            source_uri=raw.source_uri,
            raw_payload_hash=raw.sha256,
            dataset_version=raw.path.parent.name,
            collection_mode="terrestrial",
            position_semantics="terrestrial_ais_minute_downsampled",
        )
