from __future__ import annotations

import pandas as pd

from pipeline.corroborate import OUTPUT_COLUMNS, run


def test_run_writes_one_default_row_for_each_candidate_pair(tmp_path) -> None:
    candidates_path = tmp_path / "candidates_t0.parquet"
    out = tmp_path / "corroboration.parquet"
    pd.DataFrame({"pair_id": ["t0-first", "t0-second"]}).to_parquet(candidates_path, index=False)

    run(candidates_path=candidates_path, out=out)

    result = pd.read_parquet(out)
    assert result.columns.tolist() == list(OUTPUT_COLUMNS)
    assert result["pair_id"].tolist() == ["t0-first", "t0-second"]
    assert result["viirs_state"].tolist() == ["no_coverage", "no_coverage"]
    assert result["viirs_uncorrelated_count"].tolist() == [0, 0]
    assert result["viirs_min_km_to_p_star"].isna().all()
    assert result["viirs_detections"].tolist() == ["[]", "[]"]
    assert result["presence_source"].tolist() == ["corpus_endpoints", "corpus_endpoints"]
