"""S7 default VIIRS-corroboration output.

The demo pipeline has no checked-in VIIRS coverage or detection source.  This
module therefore materialises the honest, default state for every operating
candidate: coverage is unknown rather than inferred from an absent file.

The :func:`viirs_state` signature below is intentionally kept as the hand-off
point for the optional real join specified in the implementation plan.  It
does not fetch data, inspect bronze data, or otherwise attempt a VIIRS join.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from . import config


DERIVED = config.DERIVED

OUTPUT_COLUMNS = (
    "pair_id",
    "viirs_state",
    "viirs_uncorrelated_count",
    "viirs_min_km_to_p_star",
    "viirs_detections",
    "presence_source",
)


def _default_hook_result() -> dict[str, object]:
    """Return the S7 contract's camel-case representation of the default."""

    return {
        "viirsState": "no_coverage",
        "viirsUncorrelatedCount": 0,
        "viirsMinKmToMeetingPoint": None,
        "viirsDetections": [],
        "presenceSource": "corpus_endpoints",
    }


def viirs_state(
    cand_row: pd.Series,
    detections: pd.DataFrame | None,
    ring_a: object,
    ring_b: object,
    ev: pd.DataFrame,
) -> dict[str, object]:
    """Reserved hook for the real VIIRS three-state join.

    This signature deliberately matches §4 S7 of the implementation plan.
    A future implementation may use ``cand_row``, the two reachable rings,
    candidate-window detections, and corpus endpoints in ``ev`` to return one
    of ``no_coverage``, ``clear_no_detection``, ``correlated_only``, or
    ``uncorrelated_detection``.  The default-only pipeline must never turn an
    unprocessed detection table into a coverage claim, so it rejects one
    rather than silently fabricating a result.

    No network or file access occurs here.
    """

    del cand_row, ring_a, ring_b, ev  # The real join is intentionally deferred.
    if detections is not None:
        raise NotImplementedError("real VIIRS corroboration has not been implemented")
    return _default_hook_result()


def default_corroboration(pair_ids: Iterable[object]) -> pd.DataFrame:
    """Build one default S7 row per unique, non-empty candidate ``pair_id``."""

    ids = pd.Series(pair_ids, copy=False).reset_index(drop=True)
    if ids.isna().any():
        raise ValueError("candidates_t0.parquet contains a missing pair_id")
    ids = ids.astype("string")
    if ids.str.strip().eq("").any():
        raise ValueError("candidates_t0.parquet contains an empty pair_id")
    if ids.duplicated().any():
        raise ValueError("candidates_t0.parquet contains duplicate pair_id values")

    count = len(ids)
    return pd.DataFrame(
        {
            "pair_id": ids,
            "viirs_state": pd.Series("no_coverage", index=ids.index, dtype="string"),
            "viirs_uncorrelated_count": pd.Series(0, index=ids.index, dtype="int64"),
            "viirs_min_km_to_p_star": pd.Series(pd.NA, index=ids.index, dtype="Float64"),
            "viirs_detections": pd.Series(["[]"] * count, index=ids.index, dtype="string"),
            "presence_source": pd.Series("corpus_endpoints", index=ids.index, dtype="string"),
        },
        columns=list(OUTPUT_COLUMNS),
    )


def run(
    *,
    candidates_path: Path | None = None,
    out: Path | None = None,
) -> None:
    """Write default corroboration rows for all operating candidates.

    Optional paths keep this small stage easy to test; ordinary pipeline use
    is simply ``run()`` and reads/writes under ``data/derived``.
    """

    candidates_path = candidates_path or DERIVED / "candidates_t0.parquet"
    out = out or DERIVED / "corroboration.parquet"
    candidates = pd.read_parquet(candidates_path)
    if "pair_id" not in candidates.columns:
        raise ValueError("candidates_t0.parquet is missing required column: pair_id")

    corroboration = default_corroboration(candidates["pair_id"])
    out.parent.mkdir(parents=True, exist_ok=True)
    corroboration.to_parquet(out, index=False)
    print(f"[corroborate] default_no_coverage={len(corroboration)}")
