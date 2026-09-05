"""Offline contract tests for the standalone queue-enrichment pull script."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from scripts import pull_queue_events as pull


def _identity_payload(mmsi: str = "412331147", vessel_id: str = "gfw-showcase") -> dict[str, object]:
    return {
        "metadata": {"datasets": ["public-global-vessel-identity:v3.0"]},
        "entries": [
            {
                "dataset": "public-global-vessel-identity:v3.0",
                "selfReportedInfo": [
                    {
                        "id": vessel_id,
                        "ssvid": mmsi,
                        "shipname": "TEST VESSEL",
                        "flag": "CHN",
                        "transmissionDateFrom": "2017-01-01T00:00:00Z",
                        "transmissionDateTo": "2019-12-31T23:59:59Z",
                    }
                ],
            }
        ],
    }


def _encounter(event_id: str) -> dict[str, object]:
    return {
        "id": event_id,
        "start": "2018-06-01T01:00:00Z",
        "end": "2018-06-01T03:00:00Z",
        "position": {"lat": "42.5", "lon": "181.0"},
        "regions": {"eez": [], "rfmo": ["NPFC"]},
        "vessel": {"id": "gfw-showcase", "ssvid": "412331147"},
        "encounter": {
            "vessel": {"id": "gfw-partner", "ssvid": "416004105", "type": "fishing"},
            "medianDistanceKilometers": "1.25",
            "medianSpeedKnots": "0.75",
        },
    }


def _loitering() -> dict[str, object]:
    return {
        "id": "loiter-1",
        "start": "2018-06-01T01:00:00Z",
        "end": "2018-06-01T03:00:00Z",
        "position": {"lat": 42.25, "lon": 161.25},
        "regions": {"eez": ["8463"]},
        "vessel": {"id": "gfw-showcase", "ssvid": "412331147"},
        "loitering": {"averageSpeedKnots": 1.2},
    }


def _port_visit() -> dict[str, object]:
    return {
        "id": "port-1",
        "start": "2018-06-01T01:00:00Z",
        "end": "2018-06-03T03:00:00Z",
        "position": {"lat": 35.1, "lon": 129.0},
        "regions": {"eez": ["1"]},
        "vessel": {"id": "gfw-showcase", "ssvid": "412331147"},
        "port_visit": {
            "startAnchorage": {"name": "BUSAN", "flag": "KOR"},
        },
    }


def test_pagination_follows_next_offset_and_writes_raw_pages(tmp_path: Path) -> None:
    (tmp_path / "data/derived").mkdir(parents=True)
    (tmp_path / "data/derived/queue_mmsis.txt").write_text("412331147\n", encoding="utf-8")
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-token"
        if request.method == "GET":
            assert request.url.path == "/v3/vessels/search"
            assert request.url.params["query"] == "412331147"
            assert request.url.params["datasets[0]"] == pull.IDENTITY_DATASET
            assert request.url.params["includes[2]"] == "AUTHORIZATIONS"
            return httpx.Response(200, json=_identity_payload())

        body = json.loads(request.content)
        dataset = body["datasets"][0]
        event_type = body["types"][0]
        assert body["timeFilterMode"] == "OVERLAP"
        assert body["vessels"] == ["gfw-showcase"]
        offset = int(request.url.params["offset"])
        if event_type == "ENCOUNTER" and offset == 0:
            return httpx.Response(200, json={"entries": [_encounter("encounter-1")], "nextOffset": 500})
        if event_type == "ENCOUNTER" and offset == 500:
            return httpx.Response(200, json={"entries": [_encounter("encounter-2")], "nextOffset": None})
        assert dataset == pull.EVENT_DATASETS[event_type]
        return httpx.Response(200, json={"entries": [], "nextOffset": None})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        manifest = pull.run_pull(
            root=tmp_path,
            token="test-token",
            client=client,
            retrieval_id="pagination-test",
            pause_seconds=0,
            sleep_fn=lambda _: None,
        )
    finally:
        client.close()

    encounter_offsets = [
        int(request.url.params["offset"])
        for request in seen_requests
        if request.method == "POST" and json.loads(request.content)["types"] == ["ENCOUNTER"]
    ]
    assert encounter_offsets == [0, 500]
    assert manifest["counts_per_type"]["ENCOUNTER"] == 2
    assert (
        tmp_path
        / "data/bronze/gfw_events/retrieval_id=pagination-test/type=ENCOUNTER/batch=0/offset=0/response.json"
    ).exists()
    assert (
        tmp_path
        / "data/bronze/gfw_events/retrieval_id=pagination-test/type=ENCOUNTER/batch=0/offset=500/manifest.json"
    ).exists()
    events = pd.read_parquet(tmp_path / "data/reference/gfw_events_queue.parquet")
    assert list(events["event_id"])[:2] == ["encounter-1", "encounter-2"]


def test_identity_choice_requires_matching_ssvid_and_2017_2019_overlap() -> None:
    payload = {
        "entries": [
            {
                "dataset": "public-global-vessel-identity:v3.0",
                "selfReportedInfo": [
                    {
                        "id": "wrong-time",
                        "ssvid": "412331147",
                        "shipname": "OLD VESSEL",
                        "transmissionDateFrom": "2010-01-01T00:00:00Z",
                        "transmissionDateTo": "2016-12-31T23:59:59Z",
                    },
                    {
                        "id": "wrong-mmsi",
                        "ssvid": "999999999",
                        "shipname": "OTHER VESSEL",
                        "transmissionDateFrom": "2017-01-01T00:00:00Z",
                        "transmissionDateTo": "2019-12-31T23:59:59Z",
                    },
                    {
                        "id": "correct",
                        "ssvid": "412331147",
                        "shipname": "RIGHT VESSEL",
                        "transmissionDateFrom": "2017-07-01T00:00:00Z",
                        "transmissionDateTo": "2019-01-01T00:00:00Z",
                    },
                ],
            }
        ]
    }

    candidates = pull.parse_identity_response(
        payload,
        "412331147",
        retrieved_at="2026-09-05T00:00:00Z",
    )
    selected = pull.choose_identity_candidate(candidates, "412331147")

    assert len(candidates) == 3  # Keep all response candidates for audit.
    assert candidates.iloc[0]["gfw_vessel_id"] == "correct"
    assert candidates.iloc[0]["match_rank"] == 1
    assert selected is not None
    assert selected["gfw_vessel_id"] == "correct"


def test_identity_parser_keeps_malformed_transmission_values_nullable() -> None:
    payload = {
        "entries": [
            {
                "selfReportedInfo": [
                    {
                        "id": "malformed-dates",
                        "ssvid": "412331147",
                        "transmissionDateFrom": {"not": "a timestamp"},
                        "transmissionDateTo": ["also", "not", "a timestamp"],
                    }
                ]
            }
        ]
    }

    candidates = pull.parse_identity_response(payload, "412331147")

    assert len(candidates) == 1
    assert candidates.iloc[0]["gfw_vessel_id"] == "malformed-dates"
    assert pd.isna(candidates.iloc[0]["first_transmission"])
    assert pd.isna(candidates.iloc[0]["last_transmission"])


def test_event_parsers_cover_encounter_loitering_and_port_visit_shapes() -> None:
    encounter = pull.parse_events_response(
        {"entries": [_encounter("encounter-1")]},
        "ENCOUNTER",
        dataset_version="encounter-v3",
        retrieved_at="2026-09-05T00:00:00Z",
    )
    loitering = pull.parse_events_response(
        {"entries": [_loitering()]},
        "LOITERING",
        dataset_version="loitering-v3",
        retrieved_at="2026-09-05T00:00:00Z",
    )
    port_visit = pull.parse_events_response(
        {"entries": [_port_visit()]},
        "PORT_VISIT",
        dataset_version="port-v3",
        retrieved_at="2026-09-05T00:00:00Z",
    )

    assert tuple(encounter.columns) == pull.EVENT_COLUMNS
    assert encounter.iloc[0]["partner_gfw_vessel_id"] == "gfw-partner"
    assert encounter.iloc[0]["partner_mmsi"] == "416004105"
    assert encounter.iloc[0]["median_distance_km"] == 1.25
    assert encounter.iloc[0]["lon"] == -179.0
    assert loitering.iloc[0]["event_type"] == "LOITERING"
    assert pd.isna(loitering.iloc[0]["partner_gfw_vessel_id"])
    assert port_visit.iloc[0]["port_name"] == "BUSAN"
    assert port_visit.iloc[0]["port_country"] == "KOR"
    assert all(isinstance(frame["start"].dtype, pd.DatetimeTZDtype) for frame in (encounter, loitering, port_visit))


def test_resume_skips_event_batch_when_manifest_already_exists(tmp_path: Path) -> None:
    batch_dir = tmp_path / "data/bronze/gfw_events/retrieval_id=resume-test/type=ENCOUNTER/batch=0"
    pull.write_json(batch_dir / "manifest.json", {"complete": True, "pages": 0, "row_count": 0})

    def never_call(_: httpx.Request) -> httpx.Response:
        raise AssertionError("--resume should not call an already-manifested batch")

    client = httpx.Client(transport=httpx.MockTransport(never_call))
    try:
        api = pull.GfwApi("test-token", client=client, pause_seconds=0, sleep_fn=lambda _: None)
        result = pull.pull_event_batch(
            api,
            tmp_path,
            "resume-test",
            event_type="ENCOUNTER",
            dataset=pull.ENCOUNTER_DATASET,
            batch=0,
            vessel_ids=["gfw-showcase"],
            id_to_mmsi={"gfw-showcase": "412331147"},
            resume=True,
        )
    finally:
        client.close()

    assert result.skipped is True
    assert result.frame.empty


def test_dry_run_with_empty_identity_fails_without_an_event_request(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={"entries": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(pull.GfwPullError, match="no eligible GFW vessel ID"):
            pull.run_pull(
                root=tmp_path,
                dry_run=True,
                token="test-token",
                client=client,
                retrieval_id="empty-dry-run",
                pause_seconds=0,
                sleep_fn=lambda _: None,
            )
    finally:
        client.close()

    assert [(request.method, request.url.path) for request in calls] == [("GET", "/v3/vessels/search")]
    manifest = json.loads((tmp_path / "data/reference/gfw_queue_pull_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"


def test_dry_run_rejects_nonempty_identity_for_a_different_mmsi(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        return httpx.Response(
            200,
            json={
                "entries": [
                    {
                        "selfReportedInfo": [
                            {
                                "id": "unrelated-vessel",
                                "ssvid": "999999999",
                                "transmissionDateFrom": "2018-01-01T00:00:00Z",
                                "transmissionDateTo": "2019-01-01T00:00:00Z",
                            }
                        ]
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(pull.GfwPullError, match="no eligible GFW vessel ID"):
            pull.run_pull(
                root=tmp_path,
                dry_run=True,
                token="test-token",
                client=client,
                retrieval_id="wrong-mmsi-dry-run",
                pause_seconds=0,
                sleep_fn=lambda _: None,
            )
    finally:
        client.close()

    assert [(request.method, request.url.path) for request in calls] == [("GET", "/v3/vessels/search")]
