"""S6b: transparent, non-learned scoring for paired dark-period candidates.

This module intentionally uses no fitted parameters.  ``geom`` is endpoint
synchrony: the operating-rule-normalised shutoff and reappearance distances
and time deltas, plus a duration-ratio similarity, are averaged.  The
cell-month null probability remains exported evidence, but is not folded into
``geom``: it describes how often a cell produces pairs under permutation, not
how tightly this pair's two observed endpoints agree.

``ctx`` measures how independent a bilateral context is: bilateral components,
unusual gaps, and absence of identity/sequential-MMSI warnings raise it.
``den`` averages event and unique-vessel local-density transforms. ``flt`` is
the largest of component extent, same-flag share, and sequential-MMSI share;
``hab`` is the largest of routine-duration and queue-repeat indicators. These
simple means and maxima avoid hidden sub-model weights while preserving the
configured eight-term linear weights as the only score weights.

``beh`` is always null in this corpus.  It is not set to zero because no
encounter, loitering, or port-visit evidence was collected.  The raw score is
normalised by the *absolute* configured weights of available components.
Absolute-weight normalisation is required because penalties have negative
weights; dividing by signed weights could reverse or explode a score when a
positive component is unavailable.  Each output row records the available
components and plain-English input provenance so an analyst can see this
normalisation rather than mistake it for observed evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from . import config


DERIVED = config.DERIVED
COMPONENTS = tuple(config.WEIGHTS)
_EXPECTED_COMPONENTS = ("geom", "kin", "beh", "ctx", "cor", "den", "flt", "hab")
if COMPONENTS != _EXPECTED_COMPONENTS:  # Guard score ordering as config evolves.
    raise ValueError(f"unexpected score-component order in config.WEIGHTS: {COMPONENTS}")


@dataclass(frozen=True)
class Component:
    """One bounded score term plus the exact source values used to derive it."""

    value: float | None
    inputs: dict[str, object]
    reason: str


def _missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(result) if isinstance(result, (bool, np.bool_)) else False


def _number(value: object) -> float | None:
    if _missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _boolean(value: object) -> bool | None:
    if _missing(value):
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        return None
    return bool(value)


def _string(value: object) -> str | None:
    return None if _missing(value) else str(value).strip()


def _clip01(value: float | None) -> float | None:
    return None if value is None else float(min(1.0, max(0.0, value)))


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return None if not present else float(sum(present) / len(present))


def _row_value(row: Mapping[str, object], name: str) -> object:
    return row[name] if name in row else None


def _json_safe(value: object) -> object:
    """Convert scalar pandas/NumPy values in provenance to valid JSON types."""

    if _missing(value):
        return None
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _geom(row: Mapping[str, object]) -> Component:
    start_km = _number(_row_value(row, "start_km"))
    start_min = _number(_row_value(row, "start_delta_min"))
    end_km = _number(_row_value(row, "end_km"))
    end_min = _number(_row_value(row, "end_delta_min"))
    duration_ratio = _number(_row_value(row, "duration_ratio"))
    inputs = {
        "start_km": start_km,
        "start_delta_min": start_min,
        "end_km": end_km,
        "end_delta_min": end_min,
        "duration_ratio": duration_ratio,
    }
    duration_similarity = None
    if duration_ratio is not None and duration_ratio > 0:
        duration_similarity = min(duration_ratio, 1.0 / duration_ratio, 1.0)
    value = _mean(
        [
            _clip01(1.0 - start_km / config.OPERATING["start_km"]) if start_km is not None else None,
            _clip01(1.0 - start_min / (60.0 * config.OPERATING["start_h"])) if start_min is not None else None,
            _clip01(1.0 - end_km / config.OPERATING["end_km"]) if end_km is not None else None,
            _clip01(1.0 - end_min / (60.0 * config.OPERATING["end_h"])) if end_min is not None else None,
            duration_similarity,
        ]
    )
    return Component(value, inputs, "Rewards close, near-simultaneous endpoints and similarly long dark periods.")


def _kin(row: Mapping[str, object]) -> Component:
    value = _clip01(_number(_row_value(row, "kin_plausibility")))
    return Component(
        value,
        {"kin_plausibility": _number(_row_value(row, "kin_plausibility"))},
        "Uses the reachable-set kinematic plausibility supplied by S2.",
    )


def _beh(row: Mapping[str, object]) -> Component:
    return Component(
        None,
        {
            "loiter_bracket": _row_value(row, "loiter_bracket"),
            "encounter_bracket": _row_value(row, "encounter_bracket"),
            "port_after_gap_risk": _row_value(row, "port_after_gap_risk"),
        },
        "Not available: this corpus has no loitering, encounter, or port-visit corroboration.",
    )


def _ctx(row: Mapping[str, object]) -> Component:
    identity_twin = _boolean(_row_value(row, "identity_twin"))
    sequential_mmsi = _boolean(_row_value(row, "sequential_mmsi"))
    component_class = _string(_row_value(row, "component_class"))
    unusualness = _clip01(_number(_row_value(row, "gap_unusualness")))
    inputs = {
        "identity_twin": identity_twin,
        "sequential_mmsi": sequential_mmsi,
        "component_class": component_class,
        "gap_unusualness": unusualness,
    }
    structural = None if component_class is None else float(component_class == "bilateral")
    independent_identity = None if identity_twin is None else float(not identity_twin)
    independent_mmsi = None if sequential_mmsi is None else float(not sequential_mmsi)
    value = _mean([structural, independent_identity, independent_mmsi, unusualness])
    return Component(
        value,
        inputs,
        "Rewards an independent bilateral context and unusual gaps; identity and sequential-MMSI warnings reduce it.",
    )


def _cor(row: Mapping[str, object]) -> Component:
    state = _string(_row_value(row, "viirs_state"))
    if state == "uncorrelated_detection":
        value = 1.0
    elif state in {"no_coverage", "clear_no_detection", "correlated_only"}:
        value = 0.0
    else:
        value = None
    reason = (
        "An uncorrelated VIIRS detection falls in the inferred reachable area."
        if value == 1.0
        else "No qualifying uncorrelated VIIRS detection was available for this window."
    )
    return Component(value, {"viirs_state": state}, reason)


def _density_term(value: float | None) -> float | None:
    if value is None:
        return None
    return _clip01(math.log10(1.0 + max(0.0, value)) / 2.0)


def _den(row: Mapping[str, object]) -> Component:
    local_dark_count = _number(_row_value(row, "local_dark_count"))
    local_unique_vessels = _number(_row_value(row, "local_unique_vessels"))
    value = _mean([_density_term(local_dark_count), _density_term(local_unique_vessels)])
    return Component(
        value,
        {"local_dark_count": local_dark_count, "local_unique_vessels": local_unique_vessels},
        "Penalises dense nearby dark activity using both event and unique-vessel counts.",
    )


def _flt(row: Mapping[str, object]) -> Component:
    component_size = _number(_row_value(row, "component_size"))
    same_flag_share = _clip01(_number(_row_value(row, "local_same_flag_share")))
    sequential_share = _clip01(_number(_row_value(row, "local_sequential_share")))
    extent = None
    if component_size is not None:
        denominator = max(float(config.BLACKOUT_MIN_SIZE - 2), 1.0)
        extent = _clip01((component_size - 2.0) / denominator)
    values = [value for value in (extent, same_flag_share, sequential_share) if value is not None]
    value = max(values) if values else None
    return Component(
        value,
        {
            "component_size": component_size,
            "local_same_flag_share": same_flag_share,
            "local_sequential_share": sequential_share,
        },
        "Penalises larger components and locally coordinated same-flag or sequential-MMSI activity.",
    )


def _hab(row: Mapping[str, object]) -> Component:
    unusualness = _clip01(_number(_row_value(row, "gap_unusualness")))
    repeat_rate_a = _clip01(_number(_row_value(row, "repeat_rate_a")))
    repeat_rate_b = _clip01(_number(_row_value(row, "repeat_rate_b")))
    routine_duration = None if unusualness is None else 1.0 - unusualness
    values = [value for value in (routine_duration, repeat_rate_a, repeat_rate_b) if value is not None]
    value = max(values) if values else None
    return Component(
        value,
        {
            "gap_unusualness": unusualness,
            "repeat_rate_a": repeat_rate_a,
            "repeat_rate_b": repeat_rate_b,
        },
        "Penalises routine duration patterns or vessels that recur often in the candidate queue.",
    )


def score_components(row: Mapping[str, object]) -> dict[str, Component]:
    """Calculate the eight bounded S6 terms for one feature row."""

    components = {
        "geom": _geom(row),
        "kin": _kin(row),
        "beh": _beh(row),
        "ctx": _ctx(row),
        "cor": _cor(row),
        "den": _den(row),
        "flt": _flt(row),
        "hab": _hab(row),
    }
    for name, component in components.items():
        if component.value is not None and not 0.0 <= component.value <= 1.0:
            raise AssertionError(f"{name} escaped [0, 1]: {component.value}")
    return components


def _priority(raw: float) -> float:
    exponent = max(-700.0, min(700.0, -config.SIGMOID_K * (raw - config.SIGMOID_MID)))
    return 1.0 / (1.0 + math.exp(exponent))


def _truthy(value: object) -> bool:
    parsed = _boolean(value)
    return parsed is True


def _label(row: Mapping[str, object], values: Mapping[str, float | None], priority: float) -> str:
    required = ("p_cell", "start_km", "end_km", "overlap_h")
    identity_status = _string(_row_value(row, "identity_status"))
    if identity_status == "unresolved" or any(_missing(_row_value(row, name)) for name in required):
        return "insufficient-evidence"
    if _boolean(_row_value(row, "feasible")) is False:
        return "insufficient-evidence"
    if _truthy(_row_value(row, "identity_twin")) or _truthy(_row_value(row, "sequential_mmsi")):
        return "identity-twin"

    penalties = {name: values.get(name) for name in ("den", "flt", "hab")}
    present_penalties = {name: value for name, value in penalties.items() if value is not None}
    flt = penalties["flt"]
    den = penalties["den"]
    if flt is not None and flt >= config.PENALTY_DOMINANT and all(flt >= value for value in present_penalties.values()):
        return "coordinated-fleet-pattern"
    if _string(_row_value(row, "component_class")) == "regional_blackout":
        return "likely-coverage-or-cluster-artifact"
    if den is not None and den >= config.PENALTY_DOMINANT and all(den >= value for value in present_penalties.values()):
        return "likely-coverage-or-cluster-artifact"
    if _truthy(_row_value(row, "possible_port_transit")):
        return "possible-port-transit"
    no_dominant_penalty = all(value is None or value <= config.PENALTY_DOMINANT for value in penalties.values())
    if (
        priority >= config.INVESTIGATE_MIN_PRIORITY
        and _string(_row_value(row, "component_class")) == "bilateral"
        and no_dominant_penalty
    ):
        return "investigate"
    return "insufficient-evidence"


def _risk_level(label: str) -> str:
    if label == "investigate":
        return "high"
    if label in {"coordinated-fleet-pattern", "identity-twin", "possible-port-transit"}:
        return "review"
    return "watch"


def _evidence_tier(row: Mapping[str, object], values: Mapping[str, float | None], label: str) -> str:
    if values.get("cor") == 1.0:
        return "imagery_corroborated"
    if _truthy(_row_value(row, "loiter_bracket")) or _truthy(_row_value(row, "encounter_bracket")):
        return "behaviour_corroborated"
    if label == "investigate":
        return "bilateral_rendezvous_plausible"
    if label in {"identity-twin", "coordinated-fleet-pattern"}:
        return "coordinated_fleet_activity"
    return "coincidence_or_artifact"


def score_row(row: Mapping[str, object]) -> dict[str, object]:
    """Score one feature row and return the S6 score/provenance payload."""

    pair_id = _string(_row_value(row, "pair_id"))
    if pair_id is None:
        raise ValueError("features row has no pair_id")
    components = score_components(row)
    values = {name: component.value for name, component in components.items()}
    available = [name for name in COMPONENTS if values[name] is not None]
    normalisation = sum(abs(config.WEIGHTS[name]) for name in available)
    if normalisation <= 0:
        raise ValueError(f"{pair_id}: no score components are available")
    raw = sum(config.WEIGHTS[name] * float(values[name]) for name in available) / normalisation
    priority = _priority(raw)
    label = _label(row, values, priority)
    provenance = {
        name: {
            "value": values[name],
            "weight": config.WEIGHTS[name],
            "inputs": _json_safe(component.inputs),
            "reason": component.reason,
            "available": values[name] is not None,
        }
        for name, component in components.items()
    }
    return {
        "pair_id": pair_id,
        **values,
        "raw": raw,
        "priority": priority,
        "label": label,
        "evidence_tier": _evidence_tier(row, values, label),
        "risk_score": int(round(100.0 * priority)),
        "risk_level": _risk_level(label),
        "available_components": json.dumps(available, separators=(",", ":")),
        "score_provenance": json.dumps(provenance, separators=(",", ":"), allow_nan=False),
    }


SCORE_COLUMNS = (
    "pair_id",
    *COMPONENTS,
    "raw",
    "priority",
    "label",
    "evidence_tier",
    "risk_score",
    "risk_level",
    "available_components",
    "score_provenance",
)


def score_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Score each uniquely keyed feature row without changing pair coverage."""

    if "pair_id" not in features:
        raise ValueError("features.parquet is missing pair_id")
    ids = features["pair_id"].astype("string")
    if ids.isna().any() or ids.str.strip().eq("").any() or ids.duplicated().any():
        raise ValueError("features.parquet must have unique, non-empty pair_id values")
    rows = [score_row(row) for row in features.to_dict(orient="records")]
    output = pd.DataFrame(rows, columns=list(SCORE_COLUMNS))
    if len(output) != len(features) or output["pair_id"].duplicated().any():
        raise AssertionError("S6 scoring changed pair coverage")
    return output


def run(*, features_path: Path | None = None, out: Path | None = None) -> pd.DataFrame:
    """Materialise ``scores.parquet`` from a completed S6 feature table."""

    features_path = features_path or DERIVED / "features.parquet"
    out = out or DERIVED / "scores.parquet"
    scores = score_frame(pd.read_parquet(features_path))
    out.parent.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(out, index=False)
    labels = scores["label"].value_counts().sort_index().to_dict()
    print(f"[score] pairs={len(scores)} labels={labels}")
    return scores


if __name__ == "__main__":
    run()
