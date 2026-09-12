"""Archive-aware pytest configuration.

The final public archive omits generated Parquet intermediates and the extracted
source CSV. Tests that validate those local pipeline stages stay available, but
are skipped until an operator prepares their declared inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
RAW_CSV = REPOSITORY / "data" / "raw" / "disabling_events.csv"
DERIVED = REPOSITORY / "data" / "derived"

RAW_CSV_TESTS = {"test_pipeline_load.py", "test_pipeline_pair.py"}
DERIVED_INPUTS = {
    "test_pipeline_context.py": ("gap_events.parquet", "candidates_t0.parquet"),
    "test_pipeline_feasibility.py": ("gap_events.parquet", "candidates_t0.parquet"),
    "test_pipeline_features.py": (
        "gap_events.parquet",
        "candidates_t0.parquet",
        "feasibility.parquet",
        "local_context.parquet",
        "components.parquet",
        "corroboration.parquet",
        "p_cell.parquet",
    ),
    "test_pipeline_nulls.py": ("gap_events.parquet", "candidates_t0.parquet"),
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip only integration tests whose ignored local inputs are absent."""

    missing_raw = not RAW_CSV.exists()
    for item in items:
        filename = Path(str(item.fspath)).name
        required_derived = DERIVED_INPUTS.get(filename, ())
        missing_derived = any(not (DERIVED / path).exists() for path in required_derived)
        if filename in RAW_CSV_TESTS and missing_raw:
            item.add_marker(pytest.mark.local_data)
            item.add_marker(
                pytest.mark.skip(
                    reason="requires ignored data/raw/disabling_events.csv; extract data/raw/disabling_events.zip first",
                )
            )
        elif required_derived and missing_derived:
            item.add_marker(pytest.mark.local_data)
            item.add_marker(
                pytest.mark.skip(
                    reason="requires ignored derived Parquet; run the documented pipeline stages first",
                )
            )
