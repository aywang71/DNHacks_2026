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

    def url_for(self, day: date) -> str:
        return (
            "https://ocmgeodatastor1.blob.core.windows.net/"
            f"marinecadastre/ais{day.year}/ais-{day.isoformat()}.parquet"
        )

    def download(self, day: date, bronze_root: Path) -> DownloadedObject:
        source_uri = self.url_for(day)
        destination = bronze_root / "noaa_marine_cadastre" / str(day.year) / f"ais-{day.isoformat()}.parquet"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_suffix(".part")
            request = Request(source_uri, headers={"User-Agent": "dark-rendezvous/0.1"})
            with urlopen(request, timeout=120) as response, temporary.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
            temporary.replace(destination)
        return DownloadedObject(destination, source_uri, sha256_file(destination))

    def normalize(self, raw: DownloadedObject) -> pd.DataFrame:
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
        )

