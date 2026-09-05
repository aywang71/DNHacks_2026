"""Reader for licensed provider exports in CSV or Parquet form."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_export(path: Path) -> pd.DataFrame:
    """Read a delimited or Parquet AIS export without changing its columns."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path, low_memory=False)
    raise ValueError(f"Unsupported AIS export format: {path.suffix}. Use CSV or Parquet.")

