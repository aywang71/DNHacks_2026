"""S1: load and normalise the AIS-disabling event corpus.

The raw CSV is deliberately retained as a one-row-per-gap source.  Rows with
an unusable MMSI are marked rather than dropped so downstream stages can make
their eligibility decision explicitly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .geo import cell_id, normalise_lon


DERIVED = config.DERIVED

GAP_EVENT_COLUMNS = [
    "gap_id",
    "mmsi",
    "mmsi_int",
    "mid",
    "mmsi_valid",
    "vessel_class",
    "flag",
    "length_m",
    "tonnage_gt",
    "length_estimated",
    "tonnage_estimated",
    "t0",
    "t1",
    "lat0",
    "lon0",
    "lat1",
    "lon1",
    "shore_off_km",
    "shore_on_km",
    "gap_hours_source",
    "gap_hours_exact",
    "cell",
    "cell_month",
    "dateline",
    "v_kn",
    "v_kmh",
    "n_gaps_vessel",
]

_SOURCE_PATH_ATTR = "gap_pair_source_csv"


def _integer_mmsi(raw_mmsi: pd.Series) -> pd.Series:
    """Return nullable integers, treating non-integral text as missing.

    The supplied corpus has integral MMSIs throughout, but retaining this
    guard makes invalid source values unambiguously ineligible for pairing.
    """

    numeric = pd.to_numeric(raw_mmsi, errors="coerce")
    integral = numeric.notna() & np.isfinite(numeric) & numeric.mod(1).eq(0)
    return numeric.where(integral, pd.NA).astype("Int64")


def _float_column(source: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(source[name], errors="coerce").astype("float64")


def load_gap_events(csv_path: Path = config.RAW_CSV) -> pd.DataFrame:
    """Load the raw gap CSV into the stable S1 schema.

    ``mmsi`` remains a nine-character text identifier for joins and exports;
    arithmetic uses ``mmsi_int`` and ``mid``.  All timestamps are explicitly
    parsed as UTC so pandas 3 keeps the required ``datetime64[us, UTC]``
    dtype.
    """

    csv_path = Path(csv_path)
    source = pd.read_csv(
        csv_path,
        dtype={
            "gap_id": "string",
            "mmsi": "string",
            "vessel_class": "string",
            "flag": "string",
        },
    )

    gap_id = source["gap_id"].astype("string")
    raw_mmsi = source["mmsi"].astype("string").str.strip()
    nullable_mmsi_int = _integer_mmsi(raw_mmsi)
    # Keep ordinary integer columns for the corpus while still being robust to
    # a malformed custom CSV, where nullable integers are necessary.
    if nullable_mmsi_int.isna().any():
        mmsi_int = nullable_mmsi_int
    else:
        mmsi_int = nullable_mmsi_int.astype("int64")
    mid = mmsi_int // 1_000_000
    mmsi = mmsi_int.astype("string").str.zfill(9)

    valid_range = mmsi_int.between(config.MMSI_VALID["lo"], config.MMSI_VALID["hi"])
    valid_mid = mid.between(config.MMSI_VALID["mid_lo"], config.MMSI_VALID["mid_hi"])
    mmsi_valid = (valid_range & valid_mid).fillna(False).astype(bool)

    vessel_class = source["vessel_class"].astype("string")
    flag = source["flag"].astype("string").str.strip()
    flag = flag.mask(flag.eq(""), pd.NA)

    t0 = pd.to_datetime(source["gap_start_timestamp"], utc=True)
    t1 = pd.to_datetime(source["gap_end_timestamp"], utc=True)
    lat0 = _float_column(source, "gap_start_lat")
    lat1 = _float_column(source, "gap_end_lat")
    lon0 = pd.Series(normalise_lon(_float_column(source, "gap_start_lon")), index=source.index, dtype="float64")
    lon1 = pd.Series(normalise_lon(_float_column(source, "gap_end_lon")), index=source.index, dtype="float64")

    length_m = _float_column(source, "vessel_length_m")
    tonnage_gt = _float_column(source, "vessel_tonnage_gt")
    shore_off_km = _float_column(source, "gap_start_distance_from_shore_m") / 1000.0
    shore_on_km = _float_column(source, "gap_end_distance_from_shore_m") / 1000.0
    gap_hours_source = _float_column(source, "gap_hours")
    gap_hours_exact = (t1 - t0) / pd.Timedelta(hours=1)

    cell = pd.Series(cell_id(lat0, lon0), index=source.index, dtype="int64")
    cell_month = cell.astype("string") + "-" + t0.dt.strftime("%Y-%m").astype("string")
    dateline = (lon0.sub(lon1).abs() > 180.0).astype(bool)
    v_kn = vessel_class.map(config.class_speed_kn).astype("float64")
    v_kmh = v_kn * config.KM_PER_KN_H
    n_gaps_vessel = mmsi.groupby(mmsi, dropna=False).transform("size").astype("int64")

    events = pd.DataFrame(
        {
            "gap_id": gap_id,
            "mmsi": mmsi,
            "mmsi_int": mmsi_int,
            "mid": mid,
            "mmsi_valid": mmsi_valid,
            "vessel_class": vessel_class,
            "flag": flag,
            "length_m": length_m,
            "tonnage_gt": tonnage_gt,
            "length_estimated": True,
            "tonnage_estimated": True,
            "t0": t0,
            "t1": t1,
            "lat0": lat0,
            "lon0": lon0,
            "lat1": lat1,
            "lon1": lon1,
            "shore_off_km": shore_off_km,
            "shore_on_km": shore_on_km,
            "gap_hours_source": gap_hours_source,
            "gap_hours_exact": gap_hours_exact,
            "cell": cell,
            "cell_month": cell_month,
            "dateline": dateline,
            "v_kn": v_kn,
            "v_kmh": v_kmh,
            "n_gaps_vessel": n_gaps_vessel,
        }
    )[GAP_EVENT_COLUMNS]
    events.attrs[_SOURCE_PATH_ATTR] = str(csv_path)
    return events


def write_gap_events(df: pd.DataFrame, out: Path = DERIVED / "gap_events.parquet") -> None:
    """Write the S1 event table without a pandas index."""

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quality_counts(df: pd.DataFrame) -> dict[str, int]:
    return {
        "invalid_mmsi": int((~df["mmsi_valid"]).sum()),
        "n_valid_for_pairing": int(df["mmsi_valid"].sum()),
        "blank_flag": int(df["flag"].isna().sum()),
        "negative_or_zero_duration": int((df["gap_hours_exact"] <= 0).fillna(False).sum()),
        "duplicate_gap_id": int(df["gap_id"].duplicated().sum()),
    }


def write_exclusions(df: pd.DataFrame, out: Path = DERIVED / "exclusions.json") -> None:
    """Write the pairing-exclusion checkpoint plus source provenance."""

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    source_path = Path(df.attrs.get(_SOURCE_PATH_ATTR, config.RAW_CSV))
    counts = _quality_counts(df)
    n_total = int(len(df))
    payload = {
        "n_total_rows": n_total,
        "excluded_from_pairing": {"invalid_mmsi": counts["invalid_mmsi"]},
        "n_valid_for_pairing": counts["n_valid_for_pairing"],
        "other_data_quality_notes": {
            "negative_or_zero_duration": counts["negative_or_zero_duration"],
            "duplicate_gap_id": counts["duplicate_gap_id"],
            "blank_flag": counts["blank_flag"],
        },
        "invalid_mmsi_share": round(counts["invalid_mmsi"] / n_total, 4) if n_total else 0.0,
        "created_at": pd.Timestamp.now(tz="UTC").isoformat().replace("+00:00", "Z"),
        "source_sha256": _sha256(source_path),
        "row_count": n_total,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run() -> None:
    """Materialise the normalised corpus and its data-quality checkpoint."""

    events = load_gap_events()
    write_gap_events(events)
    write_exclusions(events)
    counts = _quality_counts(events)
    max_gap_hours_delta = float((events["gap_hours_exact"] - events["gap_hours_source"]).abs().max())
    print(
        "[load] "
        f"rows={len(events)} valid={counts['n_valid_for_pairing']} "
        f"invalid={counts['invalid_mmsi']} blank_flag={counts['blank_flag']} "
        f"dateline={int(events['dateline'].sum())} "
        f"max_gap_hours_delta={max_gap_hours_delta:.6f} "
        f"duplicate_gap_id={counts['duplicate_gap_id']} "
        f"nonpositive_duration={counts['negative_or_zero_duration']}"
    )
