from datetime import date

from dark_rendezvous.gfw_pull import date_windows, pull_gap_windows


def _event(identifier: str, start: str, end: str) -> dict[str, object]:
    return {
        "id": identifier,
        "start": start,
        "end": end,
        "vessel": {"id": f"vessel-{identifier}", "ssvid": "123456789"},
        "gap": {
            "offPosition": {"lat": 1.0, "lon": 2.0},
            "onPosition": {"lat": 3.0, "lon": 4.0},
            "intentionalDisabling": True,
        },
    }


class FakeGfwClient:
    gaps_dataset = "public-global-gaps-events:latest"
    last_dataset_version = "public-global-gaps-events:test"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def gap_events(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        offset = kwargs["offset"]
        if offset == 0:
            return {"entries": [_event("one", "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z")], "total": 2, "nextOffset": 1}
        return {"entries": [_event("two", "2024-01-02T00:00:00Z", "2024-01-03T00:00:00Z")], "total": 2, "nextOffset": None}


def test_date_windows_are_non_overlapping_and_end_exclusive() -> None:
    assert list(date_windows(date(2024, 1, 1), date(2024, 1, 6), 2)) == [
        (date(2024, 1, 1), date(2024, 1, 3)),
        (date(2024, 1, 3), date(2024, 1, 5)),
        (date(2024, 1, 5), date(2024, 1, 6)),
    ]


def test_pull_writes_page_partitioned_raw_and_normalized_artifacts(tmp_path) -> None:
    client = FakeGfwClient()
    summary = pull_gap_windows(
        client,  # type: ignore[arg-type]
        start=date(2024, 1, 1),
        end=date(2024, 1, 3),
        bronze_root=tmp_path / "bronze",
        silver_root=tmp_path / "silver",
        page_size=2,
        retrieval_id="test-run",
    )

    assert summary.complete is True
    assert summary.pages_written == 2
    assert summary.events_written == 2
    assert summary.endpoints_written == 4
    assert [call["time_filter_mode"] for call in client.calls] == ["START-DATE", "START-DATE"]
    assert (tmp_path / "bronze/gfw_gaps/retrieval_id=test-run/window_start=2024-01-01/window_end=2024-01-03/offset=000000000/response.json").exists()
    assert (tmp_path / "silver/gfw_gap_endpoints/retrieval_id=test-run/pull_manifest.json").exists()
