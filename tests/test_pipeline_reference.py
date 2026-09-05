from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from pipeline import config, reference


def test_flag_card_time_validity() -> None:
    assert reference.flag_card("TWN", pd.Timestamp("2017-07-01", tz="UTC")) == "yellow"
    assert reference.flag_card("TWN", pd.Timestamp("2019-07-01", tz="UTC")) == "none"
    assert reference.flag_card(None, pd.Timestamp("2018-01-01", tz="UTC")) == "unknown"
    assert reference.flag_card("KHM", pd.Timestamp("2018-01-01", tz="UTC")) == "red"


def test_static_reference_tables_validate() -> None:
    counts = reference.run()
    assert counts == {"eu_iuu_cards": 21, "psma_parties": 0, "rfmo_names": 13, "class_speeds": 8}
    assert reference.psma_party("TWN", pd.Timestamp("2018-01-01", tz="UTC")) is None
    assert reference.rfmo_name("NPFC") == "North Pacific Fisheries Commission"
    assert reference.class_speed_kn("squid_jigger") == 12.0
    assert reference.class_speed_kn(None) == 16.0


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [("NaT", ""), ("2017-01-01", "NaT")],
)
def test_cards_reject_literal_nat_dates(tmp_path, start_date: str, end_date: str) -> None:
    cards = tmp_path / "cards.csv"
    cards.write_text(
        "flag_iso3,colour,start_date,end_date,source_url,confidence\n"
        f"AAA,yellow,{start_date},{end_date},,high\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid date"):
        reference.load_cards(cards)


def test_invalid_as_of_returns_unknown_or_none(monkeypatch) -> None:
    assert reference.flag_card("TWN", "not-a-date") == "unknown"
    # Populate the scalar lookup so this exercises date parsing in psma_party,
    # rather than its intentional empty-table short circuit.
    monkeypatch.setattr(
        reference,
        "_default_psma_since",
        lambda: {"TWN": pd.Timestamp("2010-01-01")},
    )
    assert reference.psma_party("TWN", "not-a-date") is None


def test_p0_fixture_files_are_valid_and_renderable() -> None:
    """Keep the committed frontend fallback honest before the export stage exists."""
    risk_events = json.loads((config.OUT_DATA / "risk-events.json").read_text(encoding="utf-8"))
    narratives = json.loads((config.OUT_DATA / "narratives.json").read_text(encoding="utf-8"))
    methods = json.loads((config.OUT_DATA / "methods.json").read_text(encoding="utf-8"))

    def assert_no_nan(value: object) -> None:
        if isinstance(value, float):
            assert math.isfinite(value)
        elif isinstance(value, dict):
            for nested in value.values():
                assert_no_nan(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_no_nan(nested)

    def assert_coordinate(point: list[float]) -> None:
        assert -180 <= point[0] <= 180
        assert -90 <= point[1] <= 90

    assert len(risk_events) == 3
    assert_no_nan(risk_events)
    assert_no_nan(narratives)
    assert_no_nan(methods)
    for record in risk_events:
        assert record["attribution"]
        assert_coordinate(record["coordinates"])
        assert record["track"]["type"] == "FeatureCollection"
        for feature in record["track"]["features"]:
            geometry = feature["geometry"]
            if geometry["type"] == "Point":
                assert_coordinate(geometry["coordinates"])
            elif geometry["type"] == "LineString":
                for point in geometry["coordinates"]:
                    assert_coordinate(point)
            elif geometry["type"] == "Polygon":
                for ring in geometry["coordinates"]:
                    assert ring[0] == ring[-1]
                    for point in ring:
                        assert_coordinate(point)
            else:
                raise AssertionError(f"unexpected GeoJSON type: {geometry['type']}")

    showcase = risk_events[0]
    assert showcase["id"] in narratives
    assert len(showcase["track"]["features"]) == 9
    rings = [
        feature["geometry"]["coordinates"][0]
        for feature in showcase["track"]["features"]
        if feature["geometry"]["type"] == "Polygon"
    ]
    assert len(rings) == 2
    # GeoJSON closes a 64-vertex ring by repeating its first coordinate.
    assert all(len(ring) == 65 for ring in rings)
    assert methods["attribution"] == config.ATTRIBUTION

    # T0 gives S_kin a zero weight.  Keep hand-built variants in lock-step
    # with the same raw → sigmoid priority → display-score chain as S6b.
    for record, expected_raw, expected_priority, expected_risk_score in (
        (risk_events[1], 0.0635, 0.1948, 19),
        (risk_events[2], 0.099, 0.2304, 23),
    ):
        scores = record["scores"]
        calculated_raw = (
            0.30 * scores["geom"]
            + 0.20 * (scores["beh"] or 0.0)
            + 0.15 * scores["ctx"]
            + 0.20 * scores["cor"]
            - 0.15 * scores["den"]
            - 0.20 * scores["flt"]
            - 0.10 * scores["hab"]
        )
        calculated_priority = 1 / (1 + math.exp(-6 * (calculated_raw - 0.30)))
        assert scores["raw"] == pytest.approx(expected_raw)
        assert calculated_raw == pytest.approx(expected_raw)
        assert record["priority"] == pytest.approx(expected_priority)
        assert calculated_priority == pytest.approx(expected_priority, abs=0.0001)
        assert record["riskScore"] == expected_risk_score == round(100 * calculated_priority)
