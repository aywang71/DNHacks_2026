"""S5: within-cell permutation null model for paired dark periods."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .geo import cell_id, haversine_km
from .pair_t0 import pair_events


DERIVED = config.DERIVED
_BROAD_RULE = dict(start_km=50.0, start_h=24.0, both_ends=False)


def _valid_mask(ev: pd.DataFrame) -> np.ndarray:
    """Return the eligibility mask used by :func:`pair_events`."""

    if "mmsi_valid" not in ev:
        return np.zeros(len(ev), dtype=bool)
    return ev["mmsi_valid"].fillna(False).astype(bool).to_numpy(dtype=bool)


def _cell_month(cell: pd.Series, times: pd.Series) -> pd.Series:
    """Build ``<5-degree-cell>-YYYY-MM`` without pandas' slow strftime path."""

    month = times.dt.year.astype("string") + "-" + times.dt.month.astype("string").str.zfill(2)
    return cell.astype("string") + "-" + month


def permute_within_cell(ev: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Permute valid events' shutoff times independently within each 5-degree cell.

    Positions and each event's gap duration remain attached to the event.  The
    returned frame is a copy; both ``t1`` and ``cell_month`` reflect the newly
    assigned shutoff time.
    """

    out = ev.copy()
    if out.empty or "mmsi_valid" not in out:
        return out
    required = {"t0", "t1", "lat0", "lon0"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(f"events missing columns required for permutation: {sorted(missing)}")
    if "cell" not in out:
        out["cell"] = cell_id(out["lat0"], out["lon0"])

    duration = out["t1"] - out["t0"]
    valid_positions = np.flatnonzero(_valid_mask(out))
    if valid_positions.size:
        cells = out["cell"].to_numpy(copy=False)
        sorted_positions = valid_positions[np.argsort(cells[valid_positions], kind="stable")]
        sorted_cells = cells[sorted_positions]
        boundaries = np.r_[
            0,
            np.flatnonzero(np.diff(sorted_cells)) + 1,
            len(sorted_positions),
        ]

        # ``asi8`` is in the dtype's native unit (microseconds for this
        # project).  It is used only to move exact timestamps, never for a
        # duration calculation.
        values = out["t0"].array.asi8.copy()
        for lower, upper in zip(boundaries[:-1], boundaries[1:]):
            positions = sorted_positions[lower:upper]
            values[positions] = values[positions][rng.permutation(len(positions))]
        unit = getattr(out["t0"].dtype, "unit", "us") or "us"
        out["t0"] = pd.to_datetime(values, unit=unit, utc=True)

    out["t1"] = out["t0"] + duration
    out["cell_month"] = _cell_month(out["cell"], out["t0"])
    return out


def _ordered_valid(ev: pd.DataFrame) -> pd.DataFrame:
    """Mirror pair_t0's positional ordering without relying on its private API."""

    return ev.loc[_valid_mask(ev)].copy().sort_values("t0", kind="stable").reset_index(drop=True)


def _a_positions(ordered: pd.DataFrame, pairs: pd.DataFrame) -> np.ndarray:
    """Return canonical-A pair positions (earlier t0; lower gap_id on a tie)."""

    if pairs.empty:
        return np.empty(0, dtype=np.int64)
    i = pairs["i"].to_numpy(dtype=np.int64)
    j = pairs["j"].to_numpy(dtype=np.int64)
    t0_i = ordered["t0"].iloc[i].reset_index(drop=True)
    t0_j = ordered["t0"].iloc[j].reset_index(drop=True)
    gap_i = ordered["gap_id"].iloc[i].astype("string").reset_index(drop=True)
    gap_j = ordered["gap_id"].iloc[j].astype("string").reset_index(drop=True)
    swap = t0_i.gt(t0_j).to_numpy(dtype=bool) | (
        t0_i.eq(t0_j).to_numpy(dtype=bool) & gap_i.gt(gap_j).to_numpy(dtype=bool)
    )
    return np.where(swap, j, i)


def _cell_month_counts(ev: pd.DataFrame, pairs: pd.DataFrame) -> dict[str, int]:
    """Count operating pairs by the canonical A event's current cell-month."""

    if pairs.empty:
        return {}
    ordered = _ordered_valid(ev)
    a = _a_positions(ordered, pairs)
    months = ordered["cell_month"].iloc[a].astype("string")
    return {str(key): int(value) for key, value in months.value_counts().items()}


def _counts_from_broad_pairs(ev: pd.DataFrame) -> dict[str, int]:
    """Evaluate every ladder rule from its common 50 km / 24 h superset.

    The operating count itself is still obtained with ``pair_events(...,
    **config.OPERATING)`` for every null draw.  This helper prevents seven
    redundant scans of the same draw merely to report the diagnostic ladder.
    """

    names_and_rules = [*config.LADDER, ("loose", config.LOOSE)]
    broad = pair_events(ev, **_BROAD_RULE)
    counts = {name: 0 for name, _ in names_and_rules}
    if broad.empty:
        return counts

    ordered = _ordered_valid(ev)
    i = broad["i"].to_numpy(dtype=np.int64)
    j = broad["j"].to_numpy(dtype=np.int64)
    t0_i = ordered["t0"].iloc[i].reset_index(drop=True)
    t0_j = ordered["t0"].iloc[j].reset_index(drop=True)
    t1_i = ordered["t1"].iloc[i].reset_index(drop=True)
    t1_j = ordered["t1"].iloc[j].reset_index(drop=True)
    start_h = ((t0_j - t0_i) / pd.Timedelta(hours=1)).to_numpy(dtype=float)
    end_h = ((t1_i - t1_j).abs() / pd.Timedelta(hours=1)).to_numpy(dtype=float)
    start_km = haversine_km(
        ordered["lat0"].iloc[i], ordered["lon0"].iloc[i], ordered["lat0"].iloc[j], ordered["lon0"].iloc[j]
    )
    end_km = haversine_km(
        ordered["lat1"].iloc[i], ordered["lon1"].iloc[i], ordered["lat1"].iloc[j], ordered["lon1"].iloc[j]
    )

    for name, rule in names_and_rules:
        matched = (start_km <= float(rule["start_km"])) & (start_h <= float(rule["start_h"]))
        if rule.get("both_ends", True):
            matched &= (end_km <= float(rule.get("end_km", rule["start_km"]))) & (
                end_h <= float(rule.get("end_h", rule["start_h"]))
            )
        counts[name] = int(np.count_nonzero(matched))
    return counts


def _metric(values: list[int], observed: int) -> dict[str, int | float | None]:
    """Return the compact scalar form used for a ladder rung in JSON."""

    if not values:
        return {"observed": int(observed), "null_mean": None, "lift": None}
    mean = float(np.mean(values))
    return {
        "observed": int(observed),
        "null_mean": mean,
        "lift": float(observed / mean) if mean > 0 else None,
    }


def run_null(
    ev: pd.DataFrame,
    cands: pd.DataFrame,
    draws: int = config.NULL_DRAWS,
    ladder_draws: int = config.LADDER_DRAWS,
    seed: int = config.SEED,
) -> dict:
    """Run the seeded within-cell null and return the S5 JSON payload."""

    draws = int(draws)
    ladder_draws = int(ladder_draws)
    if draws < 1:
        raise ValueError("draws must be at least one")
    if ladder_draws < 0:
        raise ValueError("ladder_draws must be non-negative")
    if "cell_month" not in cands:
        raise ValueError("candidates must contain cell_month")

    observed = int(len(cands))
    observed_cells = {
        str(key): int(value)
        for key, value in cands["cell_month"].astype("string").value_counts().sort_index().items()
    }
    null_cells: dict[str, list[int]] = {key: [] for key in observed_cells}
    per_draw: list[int] = []
    ladder_n = min(draws, ladder_draws)
    names_and_rules = [*config.LADDER, ("loose", config.LOOSE)]
    ladder_values: dict[str, list[int]] = {name: [] for name, _ in names_and_rules}

    observed_ladder = _counts_from_broad_pairs(ev)
    operating_name = next(name for name, rule in config.LADDER if rule == config.OPERATING)
    if observed_ladder[operating_name] != observed:
        raise ValueError(
            "candidates do not match the operating pairing count "
            f"({observed} candidates vs {observed_ladder[operating_name]} pairs)"
        )

    rng = np.random.default_rng(seed)
    for draw_index in range(draws):
        permuted = permute_within_cell(ev, rng)
        operating_pairs = pair_events(permuted, **config.OPERATING)
        total = int(len(operating_pairs))
        per_draw.append(total)

        per_cell = _cell_month_counts(permuted, operating_pairs)
        for key in per_cell:
            if key not in null_cells:
                null_cells[key] = [0] * draw_index
        for key, values in null_cells.items():
            values.append(int(per_cell.get(key, 0)))

        if draw_index < ladder_n:
            ladder_counts = _counts_from_broad_pairs(permuted)
            if ladder_counts[operating_name] != total:
                raise AssertionError("broad ladder evaluation disagrees with pair_events operating count")
            for name, _ in names_and_rules:
                ladder_values[name].append(ladder_counts[name])

        if (draw_index + 1) % 10 == 0:
            print(
                f"[null] draw={draw_index + 1}/{draws} last={total} "
                f"mean={float(np.mean(per_draw)):.2f}"
            )

    null_mean = float(np.mean(per_draw))
    null_sd = float(np.std(per_draw, ddof=1 if draws > 1 else 0))
    if null_mean <= 0:
        raise AssertionError("null_mean must be positive")
    lift = float(observed / null_mean)
    if abs(lift - 1.0) <= 0.01:
        raise AssertionError("null lift is indistinguishable from 1.0")

    payload = {
        "name": config.NULL_MODEL_NAME,
        "cell_deg": int(config.CELL_DEG),
        "draws": draws,
        "seed": int(seed),
        "observed": observed,
        "null_mean": null_mean,
        "null_sd": null_sd,
        "lift": lift,
        "per_draw": per_draw,
        "ladder": {
            name: _metric(ladder_values[name], observed_ladder[name]) for name, _ in names_and_rules
        },
        "cell_month_null_counts": {key: null_cells[key] for key in sorted(null_cells)},
        "observed_cell_month_counts": {key: observed_cells[key] for key in sorted(observed_cells)},
    }
    probabilities = p_cell(cands, payload)
    lower = 1.0 / (draws + 1.0)
    if len(probabilities) != len(cands) or not probabilities.between(lower, 1.0).all():
        raise AssertionError("every candidate must receive a bounded p_cell")
    return payload


def p_cell(cands: pd.DataFrame, null: dict) -> pd.Series:
    """Return each candidate's pseudo-counted cell-month null probability."""

    if "cell_month" not in cands:
        raise ValueError("candidates must contain cell_month")
    draws = int(null["draws"])
    observed = {str(key): int(value) for key, value in null["observed_cell_month_counts"].items()}
    counts = null["cell_month_null_counts"]
    values: list[float] = []
    for cell_month in cands["cell_month"].astype("string"):
        key = str(cell_month)
        if key not in observed or key not in counts:
            raise ValueError(f"null result lacks observed cell-month {key!r}")
        per_draw = counts[key]
        if len(per_draw) != draws:
            raise ValueError(f"null counts for {key!r} have {len(per_draw)} draws, expected {draws}")
        k = sum(int(value) >= observed[key] for value in per_draw)
        values.append((1.0 + k) / (1.0 + draws))
    return pd.Series(values, index=cands.index, name="p_cell", dtype="float64")


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(draws: int = config.NULL_DRAWS) -> dict:
    """Materialise ``null_results.json`` and ``p_cell.parquet`` for S6."""

    events = pd.read_parquet(DERIVED / "gap_events.parquet")
    candidates = pd.read_parquet(DERIVED / "candidates_t0.parquet")
    result = run_null(events, candidates, draws=draws)
    probabilities = p_cell(candidates, result)
    lower = 1.0 / (int(draws) + 1.0)
    if len(probabilities) != len(candidates) or not probabilities.between(lower, 1.0).all():
        raise AssertionError("every candidate must receive a bounded p_cell")

    _write_json(result, DERIVED / "null_results.json")
    pd.DataFrame({"pair_id": candidates["pair_id"], "p_cell": probabilities}).to_parquet(
        DERIVED / "p_cell.parquet", index=False
    )
    print(
        f"[null] observed={result['observed']} null_mean={result['null_mean']:.2f} "
        f"lift={result['lift']:.2f} draws={result['draws']}"
    )
    return result
