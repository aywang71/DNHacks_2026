from dark_rendezvous.providers.gfw import GFW_GAP_ENDPOINT_COLUMNS, normalize_gap_endpoints


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
