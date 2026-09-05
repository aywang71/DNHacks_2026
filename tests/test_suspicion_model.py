from datetime import date

import pandas as pd

from dark_rendezvous.suspicion_model import TrainingConfig, build_training_examples, eligible_anchors


def test_eligible_anchor_requires_complete_history_and_future_labels():
    timestamps = pd.date_range("2026-08-01", "2026-08-14 23:00", freq="h", tz="UTC")
    presence = pd.DataFrame({"ts": timestamps})
    anchors = eligible_anchors(
        presence,
        [(date(2026, 8, 1), date(2026, 8, 20))],
        TrainingConfig(),
    )
    assert anchors[0] == pd.Timestamp("2026-08-08", tz="UTC")
    assert anchors[-1] == pd.Timestamp("2026-08-13", tz="UTC")


def test_target_uses_only_events_after_anchor():
    timestamps = pd.date_range("2026-08-01", "2026-08-07 23:00", freq="h", tz="UTC")
    presence = pd.DataFrame(
        {
            "position_id": [f"p{i}" for i in range(len(timestamps))],
            "ts": timestamps,
            "vessel_id": "gfw:v1",
            "gfw_vessel_id": "v1",
            "mmsi": "123456789",
            "imo": "1234567",
            "callsign": "TEST",
            "lat": 50.0,
            "lon": 10.0,
            "gfw_vessel_type": "cargo",
            "nearest_port_km": 10.0,
            "nearest_liquid_port_km": 20.0,
            "is_night": 0.0,
            "local_vessel_density": 1.0,
            "region_vessel_count": 1.0,
            "shared_gap_end_count": 0.0,
        }
    )
    events = pd.DataFrame(
        {
            "event_id": ["before", "future"],
            "event_start": pd.to_datetime(["2026-08-07", "2026-08-10"], utc=True),
            "gfw_vessel_id": ["v1", "v1"],
            "mmsi": ["123456789", "123456789"],
        }
    )
    examples = build_training_examples(
        presence,
        events,
        [pd.Timestamp("2026-08-08", tz="UTC")],
        TrainingConfig(),
    )
    assert examples.loc[0, "target"] == 1
