import pandas as pd

from pipeline.load import GAP_EVENT_COLUMNS, load_gap_events


def test_load_gap_events_acceptance_contract():
    events = load_gap_events()

    assert list(events.columns) == GAP_EVENT_COLUMNS
    assert len(events) == 55_368
    assert str(events["t0"].dtype) == "datetime64[us, UTC]"
    assert int(events["mmsi_valid"].sum()) == 54_553
    assert int((~events["mmsi_valid"]).sum()) == 815
    assert int(events["dateline"].sum()) == 484
    assert events["mmsi"].str.fullmatch(r"\d{9}").all()
    assert ((events["gap_hours_exact"] - events["gap_hours_source"]).abs() <= 0.017).all()
    assert not events["gap_id"].duplicated().any()
    assert ((events["t1"] - events["t0"]) > pd.Timedelta(0)).all()
