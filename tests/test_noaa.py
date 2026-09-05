from datetime import date
from pathlib import Path

import pandas as pd
from shapely import Point, to_wkb

from dark_rendezvous.providers.noaa import DownloadedObject, NoaaMarineCadastreProvider


def test_noaa_daily_url_is_date_partitioned() -> None:
    url = NoaaMarineCadastreProvider().url_for(date(2024, 1, 1))
    assert url == (
        "https://ocmgeodatastor1.blob.core.windows.net/"
        "marinecadastre/ais2024/ais-2024-01-01.parquet"
    )


def test_noaa_normalizer_decodes_wkb_points(monkeypatch) -> None:
    raw_frame = pd.DataFrame(
        {
            "mmsi": [123456789],
            "base_date_time": ["2024-01-01T00:00:00Z"],
            "sog": [9.5],
            "cog": [180.0],
            "heading": [180],
            "vessel_name": ["TEST VESSEL"],
            "imo": ["1234567"],
            "call_sign": ["TEST"],
            "status": [0],
            "transceiver": ["Class A"],
            "geometry": [to_wkb(Point(-74.0, 35.0))],
        }
    )
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: raw_frame)
    result = NoaaMarineCadastreProvider().normalize(
        DownloadedObject(Path("2024/ais-2024-01-01.parquet"), "https://example.test/file", "hash")
    )

    assert result.loc[0, "ts"].isoformat() == "2024-01-01T00:00:00+00:00"
    assert result.loc[0, "lon"] == -74.0
    assert result.loc[0, "lat"] == 35.0
    assert result.loc[0, "vessel_id"] == "imo:1234567"
