from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from pipeline import config
from pipeline.nulls import p_cell, permute_within_cell, run_null


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return pd.read_parquet(config.DERIVED / "gap_events.parquet")


@pytest.fixture(scope="module")
def candidates() -> pd.DataFrame:
    return pd.read_parquet(config.DERIVED / "candidates_t0.parquet")


def test_permutation_preserves_per_cell_event_counts_and_durations(events: pd.DataFrame) -> None:
    shuffled = permute_within_cell(events, np.random.default_rng(config.SEED))
    assert len(shuffled) == len(events)
    assert shuffled["t0"].dtype == events["t0"].dtype
    assert shuffled["t1"].dtype == events["t1"].dtype
    assert shuffled.groupby("cell").size().equals(events.groupby("cell").size())

    original_duration = (events["t1"] - events["t0"]).dt.total_seconds().sort_values().to_numpy()
    shuffled_duration = (shuffled["t1"] - shuffled["t0"]).dt.total_seconds().sort_values().to_numpy()
    assert np.array_equal(original_duration, shuffled_duration)
    for cell, original in events.groupby("cell"):
        new = shuffled.loc[shuffled["cell"] == cell]
        assert np.array_equal(
            np.sort((original["t1"] - original["t0"]).dt.total_seconds().to_numpy()),
            np.sort((new["t1"] - new["t0"]).dt.total_seconds().to_numpy()),
        )


def test_five_draw_null_is_fast_and_probabilities_are_bounded(
    events: pd.DataFrame, candidates: pd.DataFrame
) -> None:
    started = time.perf_counter()
    result = run_null(events, candidates, draws=5, ladder_draws=5, seed=config.SEED)
    elapsed = time.perf_counter() - started
    probabilities = p_cell(candidates, result)

    assert elapsed < 10.0
    assert result["null_mean"] > 0
    assert round(result["lift"], 2) != 1.00
    assert len(probabilities) == len(candidates)
    assert probabilities.between(1.0 / 6.0, 1.0).all()
