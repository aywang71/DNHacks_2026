import json

import pandas as pd
import pytest

from dark_rendezvous.atlantes_adapter import (
    ATLANTES_ADAPTER_COLUMNS,
    adapt_gfw_presence_for_atlantes,
    coastline_distance_m,
)


def _presence_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "position_id": [f"point-{index}" for index in range(4)],
            "vessel_id": ["gfw:vessel-1"] * 4,
            "ts": pd.date_range("2026-08-01T00:00:00Z", periods=4, freq="h"),
            "lat": [10.0, 10.01, 10.02, 10.03],
            "lon": [20.0, 20.0, 20.0, 20.0],
            "position_semantics": ["gfw_presence_grid_center_hourly"] * 4,
            "mmsi": ["123456789"] * 4,
            "vessel_name": ["EXAMPLE"] * 4,
            "flag_state": ["USA"] * 4,
        }
    )


def test_presence_adapter_derives_explicitly_labelled_atlas_fields() -> None:
    result = adapt_gfw_presence_for_atlantes(
        _presence_rows(),
        dist2coast_m=pd.Series([1000.0, 1000.0, 1000.0, 1000.0]),
        min_points=3,
    )

    assert tuple(result.columns) == ATLANTES_ADAPTER_COLUMNS
    # The first point has no predecessor, so it cannot have derived motion.
    assert len(result) == 3
    assert result["trackId"].eq("gfw_presence:gfw:vessel-1:segment=0").all()
    assert result["sog"].gt(0).all()
    assert result["cog"].between(0, 360).all()
    assert result["nav"].eq(15).all()
    assert result["category"].eq(0).all()
    assert result["sog_semantics"].eq("derived_from_successive_hourly_grid_centres").all()


def test_presence_adapter_rejects_non_presence_semantics() -> None:
    presence = _presence_rows()
    presence.loc[0, "position_semantics"] = "raw_ais_position"

    with pytest.raises(ValueError, match="gfw_presence_grid_center_hourly"):
        adapt_gfw_presence_for_atlantes(
            presence,
            dist2coast_m=pd.Series([1000.0] * len(presence)),
            min_points=3,
        )


def test_coastline_distance_preserves_a_filtered_frame_index(tmp_path) -> None:
    coastline = tmp_path / "coastline.geojson"
    coastline.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": [[20, 10], [20, 11]]},
                        "properties": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    indexed_frame = pd.DataFrame({"lat": [10.0, 10.0], "lon": [20.0, 21.0]}, index=[5, 9])

    result = coastline_distance_m(indexed_frame, coastline)

    assert result.index.tolist() == [5, 9]
    assert result.iloc[0] == pytest.approx(0.0)
    assert result.iloc[1] > 100_000
