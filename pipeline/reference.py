"""Static, time-valid reference tables used by the GapPair pipeline.

The EU card history uses half-open calendar-date intervals: a row is active
from ``start_date`` inclusive through ``end_date`` exclusive.  This lets a
yellow-to-red transition recorded on the same date be represented without an
overlap.  Dates supplied to the public helpers are evaluated in UTC.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from . import config


CARD_COLUMNS = (
    "flag_iso3",
    "colour",
    "start_date",
    "end_date",
    "source_url",
    "confidence",
)
PSMA_COLUMNS = ("flag_iso3", "party_since")
CARD_COLOURS = frozenset({"yellow", "red"})


def _is_missing(value: object) -> bool:
    """Return whether a scalar flag/class input is missing or blank."""
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    try:
        if bool(missing):
            return True
    except (TypeError, ValueError):
        # Arrays are not scalar inputs to these public helpers; leave them
        # alone rather than treating an ambiguous truth value as missing.
        pass
    return isinstance(value, str) and not value.strip()


def _normalise_code(value: object) -> str | None:
    if _is_missing(value):
        return None
    return str(value).strip().upper()


def _calendar_day(at: object) -> pd.Timestamp | None:
    """Turn an instant into its UTC calendar day, or return None if absent."""
    if _is_missing(at):
        return None
    try:
        timestamp = pd.Timestamp(at)
        if pd.isna(timestamp):
            return None
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC").tz_localize(None)
        return timestamp.normalize()
    except (TypeError, ValueError, OverflowError):
        return None


def _read_csv(path: Path, required_columns: tuple[str, ...]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"reference table not found: {path}")
    frame = pd.read_csv(path, dtype="string")
    missing = set(required_columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {sorted(missing)}")
    return frame.loc[:, list(required_columns)].copy()


def load_cards(path: Path | None = None) -> pd.DataFrame:
    """Load and validate the EU IUU card history.

    Returned ``start_date``/``end_date`` values are naive, normalised UTC
    calendar dates.  An empty end date represents an open-ended interval.
    """
    path = path or config.REFERENCE / "eu_iuu_cards.csv"
    cards = _read_csv(path, CARD_COLUMNS)
    cards["flag_iso3"] = cards["flag_iso3"].str.strip().str.upper()
    cards["colour"] = cards["colour"].str.strip().str.lower()
    if cards["flag_iso3"].isna().any() or (cards["flag_iso3"] == "").any():
        raise ValueError("eu_iuu_cards.csv has a missing flag_iso3")
    if not cards["colour"].isin(CARD_COLOURS).all():
        invalid = sorted(cards.loc[~cards["colour"].isin(CARD_COLOURS), "colour"].dropna().unique())
        raise ValueError(f"eu_iuu_cards.csv has invalid colour values: {invalid}")

    raw_start = cards["start_date"]
    raw_end = cards["end_date"]
    if raw_start.isna().any() or (raw_start.str.strip() == "").any():
        raise ValueError("eu_iuu_cards.csv has a missing start_date")
    try:
        parsed_start = pd.to_datetime(raw_start, errors="raise")
        end_values = raw_end.mask(raw_end.isna() | (raw_end.str.strip() == ""))
        parsed_end = pd.to_datetime(end_values, errors="raise")
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("eu_iuu_cards.csv contains an invalid date") from error
    # pandas accepts a literal "NaT" under errors="raise".  Only an original
    # blank end date is permitted to parse as NaT; a start date never is.
    if parsed_start.isna().any() or (parsed_end.isna() & end_values.notna()).any():
        raise ValueError("eu_iuu_cards.csv contains an invalid date")
    cards["start_date"] = parsed_start.dt.normalize()
    cards["end_date"] = parsed_end.dt.normalize()

    if (cards["end_date"].notna() & (cards["end_date"] <= cards["start_date"])).any():
        raise ValueError("EU card end_date must be later than start_date")

    # Intervals are [start_date, end_date).  Equality is permitted so the
    # outgoing and incoming card can change on the same calendar date.
    for flag, group in cards.sort_values(["flag_iso3", "start_date"]).groupby("flag_iso3", sort=False):
        prior_end: pd.Timestamp | None = None
        for row in group.itertuples(index=False):
            start = row.start_date
            if prior_end is None and len(group) > 1:
                # An open interval must be the final interval for its flag.
                earlier_open = group.loc[group["start_date"] < start, "end_date"].isna().any()
                if earlier_open:
                    raise ValueError(f"EU card intervals overlap for {flag}")
            if prior_end is not None and start < prior_end:
                raise ValueError(f"EU card intervals overlap for {flag}")
            prior_end = row.end_date if pd.notna(row.end_date) else None

    return cards.sort_values(["flag_iso3", "start_date"], kind="stable").reset_index(drop=True)


def load_psma_parties(path: Path | None = None) -> pd.DataFrame:
    """Load the optional PSMA-party table and validate populated rows."""
    path = path or config.REFERENCE / "psma_parties.csv"
    parties = _read_csv(path, PSMA_COLUMNS)
    if parties.empty:
        return parties
    parties["flag_iso3"] = parties["flag_iso3"].str.strip().str.upper()
    if parties["flag_iso3"].isna().any() or (parties["flag_iso3"] == "").any():
        raise ValueError("psma_parties.csv has a missing flag_iso3")
    try:
        parties["party_since"] = pd.to_datetime(parties["party_since"], errors="raise").dt.normalize()
    except (TypeError, ValueError) as error:
        raise ValueError("psma_parties.csv contains an invalid party_since date") from error
    if parties.duplicated("flag_iso3").any():
        raise ValueError("psma_parties.csv contains duplicate flag_iso3 values")
    return parties.sort_values("flag_iso3", kind="stable").reset_index(drop=True)


def load_rfmo_names(path: Path | None = None) -> dict[str, str]:
    """Load the RFMO code-to-name lookup."""
    path = path or config.REFERENCE / "rfmo_names.json"
    if not path.exists():
        raise FileNotFoundError(f"reference table not found: {path}")
    with path.open(encoding="utf-8") as handle:
        names = json.load(handle)
    if not isinstance(names, dict) or not names:
        raise ValueError("rfmo_names.json must contain a non-empty object")
    normalised: dict[str, str] = {}
    for code, name in names.items():
        clean_code = _normalise_code(code)
        if clean_code is None or not isinstance(name, str) or not name.strip():
            raise ValueError("rfmo_names.json must map non-empty codes to non-empty names")
        if clean_code in normalised:
            raise ValueError(f"rfmo_names.json contains duplicate code {clean_code}")
        normalised[clean_code] = name.strip()
    return normalised


def load_class_speeds(path: Path | None = None) -> dict[str, float]:
    """Load the vessel-class speed lookup and keep it aligned with config."""
    path = path or config.REFERENCE / "class_speeds.json"
    if not path.exists():
        raise FileNotFoundError(f"reference table not found: {path}")
    with path.open(encoding="utf-8") as handle:
        speeds = json.load(handle)
    if not isinstance(speeds, dict):
        raise ValueError("class_speeds.json must contain an object")
    try:
        normalised = {str(key): float(value) for key, value in speeds.items()}
    except (TypeError, ValueError) as error:
        raise ValueError("class_speeds.json values must be numeric") from error
    if set(normalised) != set(config.V_KN):
        raise ValueError("class_speeds.json keys must match config.V_KN")
    expected = {key: float(value) for key, value in config.V_KN.items()}
    if normalised != expected:
        raise ValueError("class_speeds.json values must match config.V_KN")
    if any(speed <= 0 for speed in normalised.values()):
        raise ValueError("class_speeds.json speeds must be positive")
    return normalised


@lru_cache(maxsize=1)
def _default_cards() -> pd.DataFrame:
    """Cached default table for callers that need the validated dataframe."""
    return load_cards()


@lru_cache(maxsize=1)
def _default_psma_parties() -> pd.DataFrame:
    return load_psma_parties()


@lru_cache(maxsize=1)
def _default_rfmo_names() -> dict[str, str]:
    return load_rfmo_names()


@lru_cache(maxsize=1)
def _default_class_speeds() -> dict[str, float]:
    return load_class_speeds()


@lru_cache(maxsize=1)
def _default_card_intervals() -> dict[str, tuple[tuple[pd.Timestamp, pd.Timestamp | None, str], ...]]:
    """Compact lookup representation for scalar ``flag_card`` calls."""
    intervals: dict[str, tuple[tuple[pd.Timestamp, pd.Timestamp | None, str], ...]] = {}
    for flag, group in _default_cards().groupby("flag_iso3", sort=False):
        intervals[str(flag)] = tuple(
            (row.start_date, row.end_date if pd.notna(row.end_date) else None, str(row.colour))
            for row in group.itertuples(index=False)
        )
    return intervals


@lru_cache(maxsize=1)
def _default_psma_since() -> dict[str, pd.Timestamp]:
    parties = _default_psma_parties()
    return {str(row.flag_iso3): row.party_since for row in parties.itertuples(index=False)}


def flag_card(flag: str | None, at: pd.Timestamp | str | None) -> str:
    """Return the active EU IUU-card colour for ``flag`` at a UTC date.

    A missing flag or unavailable timestamp is deliberately ``"unknown"``;
    ``"none"`` is reserved for a known flag with no active card record.
    """
    code = _normalise_code(flag)
    day = _calendar_day(at)
    if code is None or day is None:
        return "unknown"
    for start, end, colour in _default_card_intervals().get(code, ()):
        if start <= day and (end is None or day < end):
            return colour
    return "none"


def psma_party(flag: str | None, at: pd.Timestamp | str | None) -> bool | None:
    """Return PSMA party status, or None when the optional table is unfilled."""
    party_since = _default_psma_since()
    if not party_since:
        return None
    code = _normalise_code(flag)
    day = _calendar_day(at)
    if code is None or day is None:
        return None
    since = party_since.get(code)
    if since is None:
        return False
    return bool(since <= day)


def rfmo_name(code: str | None) -> str:
    """Expand a known RFMO code; preserve an unknown non-empty code verbatim."""
    clean_code = _normalise_code(code)
    if clean_code is None:
        return ""
    return _default_rfmo_names().get(clean_code, clean_code)


def class_speed_kn(vessel_class: str | None) -> float:
    """Return the configured maximum vessel speed, defaulting to ``unknown``."""
    speeds = _default_class_speeds()
    if _is_missing(vessel_class):
        return speeds["unknown"]
    key = str(vessel_class).strip().lower()
    return speeds.get(key, speeds["unknown"])


def run(**_: Any) -> dict[str, int]:
    """Load and validate every S0 reference table for the stage runner."""
    cards = load_cards()
    parties = load_psma_parties()
    rfmos = load_rfmo_names()
    speeds = load_class_speeds()
    # A direct stage run deliberately validates files as they are now.  Make
    # later convenience lookups reload that freshly validated default state.
    _default_cards.cache_clear()
    _default_psma_parties.cache_clear()
    _default_rfmo_names.cache_clear()
    _default_class_speeds.cache_clear()
    _default_card_intervals.cache_clear()
    _default_psma_since.cache_clear()
    return {
        "eu_iuu_cards": len(cards),
        "psma_parties": len(parties),
        "rfmo_names": len(rfmos),
        "class_speeds": len(speeds),
    }
