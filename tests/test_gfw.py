from dark_rendezvous.providers.gfw import GFW_GAP_ENDPOINT_COLUMNS, normalize_gap_endpoints
from dark_rendezvous.providers.gfw_presence import (
    GFW_PRESENCE_COLUMNS,
    PRESENCE_POSITION_SEMANTICS,
    normalize_presence_report,
    report_dataset_version,
)
from dark_rendezvous.providers.gfw_tracks import normalize_track_lines


def test_gap_events_expand_to_two_distinct_endpoint_rows() -> None:
    payload = {
        "entries": [
            {
                "id": "event-1",
                "start": "2024-01-01T00:00:00.000Z",
                "end": "2024-01-01T12:00:00.000Z",
                "vessel": {"id": "gfw-vessel-1", "ssvid": "123456789", "name": "Example"},
                "gap": {
                    "durationHours": "12",
                    "impliedSpeedKnots": "4.5",
                    "offPosition": {"lat": "1.25", "lon": "2.5"},
                    "onPosition": {"lat": "3.75", "lon": "4.0"},
                },
            }
        ]
    }
    result = normalize_gap_endpoints(
        payload,
        source_uri="https://example.test/events",
        raw_payload_hash="hash",
        dataset_version="test",
    )

    assert tuple(result.columns) == GFW_GAP_ENDPOINT_COLUMNS
    assert result[["endpoint_id", "endpoint_role", "ts", "lat", "lon", "vessel_id"]].to_dict("records") == [
        {
            "endpoint_id": "event-1:off",
            "endpoint_role": "off",
            "ts": result.loc[0, "ts"],
            "lat": 1.25,
            "lon": 2.5,
            "vessel_id": "gfw:gfw-vessel-1",
        },
        {
            "endpoint_id": "event-1:on",
            "endpoint_role": "on",
            "ts": result.loc[1, "ts"],
            "lat": 3.75,
            "lon": 4.0,
            "vessel_id": "gfw:gfw-vessel-1",
        },
    ]


def test_track_line_coordinates_and_aligned_properties_become_canonical_points() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[2.5, 1.25], [4.0, 3.75]]},
                "properties": {
                    "coordinateProperties": {
                        "times": [1704067200000, 1704070800000],
                        "speed": [4.5, 5.0],
                        "course": [90.0, 91.0],
                    }
                },
            }
        ],
    }
    result = normalize_track_lines(
        payload,
        gfw_vessel_id="gfw-vessel-1",
        source_uri="https://example.test/tracks",
        raw_payload_hash="hash",
        dataset_version="test",
    )

    assert result[["ts", "lat", "lon", "vessel_id", "sog_kn", "cog_deg", "position_semantics"]].to_dict("records") == [
        {
            "ts": result.loc[0, "ts"],
            "lat": 1.25,
            "lon": 2.5,
            "vessel_id": "gfw:gfw-vessel-1",
            "sog_kn": 4.5,
            "cog_deg": 90.0,
            "position_semantics": "gfw_derived_track",
        },
        {
            "ts": result.loc[1, "ts"],
            "lat": 3.75,
            "lon": 4.0,
            "vessel_id": "gfw:gfw-vessel-1",
            "sog_kn": 5.0,
            "cog_deg": 91.0,
            "position_semantics": "gfw_derived_track",
        },
    ]
    assert result["is_valid_position"].all()


def test_presence_report_becomes_hourly_grid_centre_positions() -> None:
    payload = {
        "entries": [
            {
                "public-global-presence:v4.0": [
                    {
                        "date": "2022-01-01 00:00",
                        "entryTimestamp": "2022-01-01T00:00:00Z",
                        "lat": 53.03,
                        "lon": 158.64,
                        "vesselId": "gfw-vessel-1",
                        "mmsi": "273294510",
                        "shipName": "VICTORIA",
                        "callsign": "ABCD",
                        "imo": "9075840",
                        "flag": "RUS",
                        "vesselType": "CARRIER",
                        "hours": 1,
                    }
                ]
            }
        ]
    }

    result = normalize_presence_report(
        payload,
        source_uri="https://example.test/4wings/report",
        raw_payload_hash="hash",
        requested_dataset="public-global-presence:latest",
        spatial_resolution="HIGH",
    )

    assert tuple(result.columns) == GFW_PRESENCE_COLUMNS
    assert result.loc[0, "vessel_id"] == "gfw:gfw-vessel-1"
    assert result.loc[0, "mmsi"] == "273294510"
    assert result.loc[0, "vessel_name"] == "VICTORIA"
    assert result.loc[0, "position_semantics"] == PRESENCE_POSITION_SEMANTICS
    assert result.loc[0, "presence_hours"] == 1
    assert result.loc[0, "grid_resolution_degrees"] == 0.01
    assert result.loc[0, "report_dataset"] == "public-global-presence:v4.0"
    assert result.loc[0, "is_valid_position"]
    assert report_dataset_version(payload, "fallback") == "public-global-presence:v4.0"
