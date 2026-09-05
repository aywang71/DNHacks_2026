import pandas as pd

from dark_rendezvous.contract import CANONICAL_POSITION_COLUMNS, canonicalize_positions


def test_canonicalizer_prefers_imo_and_preserves_invalid_rows() -> None:
    raw = pd.DataFrame(
        {
            "MMSI": ["123456789", "987654321"],
            "IMO": ["1234567", None],
            "BaseDateTime": ["2024-01-01T00:00:00Z", "bad-timestamp"],
            "LAT": [1.5, 91.0],
            "LON": [2.5, 3.0],
            "SOG": [10.0, 4.0],
        }
    )
    result = canonicalize_positions(
        raw,
        source="test_source",
        source_uri="test://raw",
        raw_payload_hash="abc",
        collection_mode="terrestrial",
    )

    assert tuple(result.columns) == CANONICAL_POSITION_COLUMNS
    assert result.loc[0, "vessel_id"] == "imo:1234567"
    assert result.loc[0, "is_valid_position"]
    assert not result.loc[1, "is_valid_position"]
    assert "missing_or_invalid_ts" in result.loc[1, "quality_flags"]
    assert "invalid_coordinates" in result.loc[1, "quality_flags"]

