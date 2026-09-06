"""S8: export the scored paired-dark queue as static, auditable artifacts.

The pipeline deliberately keeps this module at the boundary between pandas and
JSON.  All pandas/NumPy missing values are converted to JSON ``null`` here,
all display rounding happens here, and :func:`validate_record` guards the
frontend contract before any file is replaced.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from . import config as pipeline_config


DERIVED = pipeline_config.DERIVED
FRONTEND_DATA = pipeline_config.FRONTEND_PUBLIC / "data"

LABELS = frozenset(
    {
        "insufficient-evidence",
        "identity-twin",
        "coordinated-fleet-pattern",
        "likely-coverage-or-cluster-artifact",
        "possible-port-transit",
        "investigate",
    }
)
EVIDENCE_TIERS = (
    "imagery_corroborated",
    "behaviour_corroborated",
    "bilateral_rendezvous_plausible",
    "coordinated_fleet_activity",
    "coincidence_or_artifact",
)
RISK_LEVELS = frozenset({"high", "review", "watch"})
CORROBORATION_STATES = frozenset(
    {"no_coverage", "clear_no_detection", "correlated_only", "uncorrelated_detection"}
)


def _missing(value: object) -> bool:
    """Return true for scalar pandas/NumPy missing values without ambiguity."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(result) if isinstance(result, (bool, np.bool_)) else False


def _mapping(value: object) -> dict[str, object]:
    """Turn a Series/mapping into a plain mapping, retaining falsey values."""

    if value is None:
        return {}
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "_asdict"):
        return dict(value._asdict())
    raise TypeError(f"expected a mapping or Series, got {type(value).__name__}")


def _lookup(sources: Iterable[Mapping[str, object]], *names: str, default: object = None) -> object:
    """Find the first non-missing alias across the supplied source mappings."""

    for source in sources:
        for name in names:
            if name in source and not _missing(source[name]):
                return source[name]
    return default


def _number(value: object, *, default: float | None = None) -> float | None:
    if _missing(value):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _integer(value: object, *, default: int | None = None) -> int | None:
    number = _number(value)
    if number is None:
        return default
    return int(round(number))


def _boolean(value: object, *, default: bool = False) -> bool:
    if _missing(value):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _clean_string(value: object, *, default: str | None = None) -> str | None:
    if _missing(value):
        return default
    return str(value).strip()


def _round(value: object, digits: int) -> float | None:
    number = _number(value)
    return None if number is None else round(number, digits)


def _normalise_lon(value: object) -> float | None:
    lon = _number(value)
    if lon is None:
        return None
    normalised = ((lon + 180.0) % 360.0) - 180.0
    # Preserve the conventional positive anti-meridian when it was supplied
    # as exactly +180 rather than surprising a reader with -180.
    if normalised == -180.0 and lon > 0:
        normalised = 180.0
    return normalised


def _coordinates(lon: object, lat: object, *, digits: int = 6) -> list[float] | None:
    normalised_lon = _normalise_lon(lon)
    numeric_lat = _number(lat)
    if normalised_lon is None or numeric_lat is None:
        return None
    return [round(normalised_lon, digits), round(numeric_lat, digits)]


def _iso(value: object, *, required: bool = False) -> str | None:
    """Format an instant as the contract's second-resolution UTC ISO string."""

    if _missing(value):
        if required:
            raise ValueError("required timestamp is missing")
        return None
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            raise ValueError("timestamp is NaT")
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError) as error:
        if required:
            raise ValueError(f"invalid required timestamp: {value!r}") from error
        return None
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp(value: object) -> pd.Timestamp | None:
    if _missing(value):
        return None
    try:
        output = pd.Timestamp(value)
        if pd.isna(output):
            return None
        return output.tz_localize("UTC") if output.tzinfo is None else output.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError):
        return None


def _json_value(value: object) -> object:
    """Recursively make values JSON-safe, turning every missing scalar into null."""

    if value is None or _missing(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, np.datetime64)):
        return _iso(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray, pd.Series)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, set):
        return [_json_value(item) for item in sorted(value, key=str)]
    return value


def _loads_list(value: object, *, default: list[object] | None = None) -> list[object]:
    if _missing(value):
        return [] if default is None else list(default)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [] if default is None else list(default)
    return list(value) if isinstance(value, (list, tuple, np.ndarray, pd.Series)) else ([] if default is None else list(default))


def _loads_object(value: object, *, default: dict[str, object] | None = None) -> dict[str, object]:
    if _missing(value):
        return {} if default is None else dict(default)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {} if default is None else dict(default)
    return dict(value) if isinstance(value, Mapping) else ({} if default is None else dict(default))


def _display_class(value: object) -> str:
    cleaned = _clean_string(value, default="unknown") or "unknown"
    return cleaned.replace("_", " ")


def _display_flag(value: object) -> str:
    return _clean_string(value, default="unknown") or "unknown"


def _vessel_role(vessel_class: object, explicit_role: object) -> str:
    role = _clean_string(explicit_role)
    if role is not None:
        return role
    text = (_clean_string(vessel_class, default="") or "").lower()
    return "carrier" if text in {"carrier", "reefer"} else "fishing"


def _coordinate_detail(coordinates: list[float]) -> str:
    lon, lat = coordinates
    return f"{abs(lat):.3f}{'N' if lat >= 0 else 'S'} {abs(lon):.3f}{'E' if lon >= 0 else 'W'}"


def _seconds_text(minutes: object) -> str:
    seconds = _number(minutes)
    if seconds is None:
        return "unknown"
    rounded = round(seconds * 60.0)
    return f"{rounded} s"


def _source_date(timestamp: object) -> str:
    return _iso(timestamp, required=True) or ""


def _score_value(sources: list[Mapping[str, object]], name: str) -> float | None:
    aliases = (f"s_{name}", f"score_{name}", name)
    return _round(_lookup(sources, *aliases), 2)


def _get_pair_count(ctx: Mapping[str, object], which: str) -> int:
    return _integer(
        _lookup([ctx], f"pairs_in_queue_{which}", f"pair_count_{which}", default=1), default=1
    ) or 0


def _flag_card(value: object, flag: object) -> str:
    card = _clean_string(value)
    if card in {"none", "yellow", "red", "unknown"}:
        return card
    return "unknown" if _missing(flag) else "none"


def _make_vessel(
    which: str,
    sources: list[Mapping[str, object]],
    ctx: Mapping[str, object],
) -> dict[str, object]:
    mmsi = _clean_string(_lookup(sources, f"mmsi_{which}"), default="unknown") or "unknown"
    flag = _display_flag(_lookup(sources, f"flag_{which}"))
    vessel_class = _clean_string(_lookup(sources, f"class_{which}", f"vessel_class_{which}"), default="unknown") or "unknown"
    identity_status = _clean_string(_lookup(sources, f"identity_status_{which}", "identity_status"), default="unresolved")
    return {
        "mmsi": mmsi,
        "imo": _clean_string(_lookup(sources, f"imo_{which}")),
        "name": _clean_string(_lookup(sources, f"vessel_name_{which}", f"name_{which}")),
        "flag": flag,
        "vesselClass": vessel_class,
        "role": _vessel_role(vessel_class, _lookup(sources, f"role_{which}")),
        "identityStatus": identity_status or "unresolved",
        "flagCard": _flag_card(_lookup(sources, f"flag_card_{which}"), flag),
        "rfmoAuthorized": _json_value(_lookup(sources, f"rfmo_authorized_{which}")),
        "iuuListed": _json_value(_lookup(sources, f"iuu_listed_{which}")),
        "lengthM": _round(_lookup(sources, f"length_{which}", f"length_m_{which}"), 2),
        "tonnageGt": _round(_lookup(sources, f"tonnage_{which}", f"tonnage_gt_{which}"), 2),
        "lengthEstimated": _boolean(_lookup(sources, f"length_estimated_{which}", "length_estimated"), default=True),
        "tonnageEstimated": _boolean(_lookup(sources, f"tonnage_estimated_{which}", "tonnage_estimated"), default=True),
        "gapsInCorpus": _integer(_lookup(sources, f"n_gaps_vessel_{which}", f"gaps_in_corpus_{which}")),
        "pairsInQueue": _get_pair_count(ctx, which),
    }


def _endpoint(feature_sources: list[Mapping[str, object]], vessel: str, role: str) -> tuple[list[float], str, str]:
    suffix = "0" if role == "off" else "1"
    coordinates = _coordinates(
        _lookup(feature_sources, f"lon{suffix}_{vessel}", f"lon_{role}_{vessel}", f"{vessel}_lon{suffix}"),
        _lookup(feature_sources, f"lat{suffix}_{vessel}", f"lat_{role}_{vessel}", f"{vessel}_lat{suffix}"),
    )
    if coordinates is None:
        raise ValueError(f"missing endpoint coordinates for vessel {vessel.upper()} {role}")
    timestamp = _iso(
        _lookup(feature_sources, f"t{suffix}_{vessel}", f"time_{role}_{vessel}", f"{vessel}_t{suffix}"),
        required=True,
    )
    mmsi = _clean_string(_lookup(feature_sources, f"mmsi_{vessel}"), default="unknown") or "unknown"
    return coordinates, timestamp or "", mmsi


def _ring(value: object) -> list[list[float]] | None:
    raw = _loads_list(value)
    if len(raw) < 3:
        return None
    output: list[list[float]] = []
    for point in raw:
        if not isinstance(point, (list, tuple, np.ndarray)) or len(point) != 2:
            return None
        coordinate = _coordinates(point[0], point[1])
        if coordinate is None:
            return None
        output.append(coordinate)
    if output[0] != output[-1]:
        output.append(list(output[0]))
    return output


def build_track(record: dict, feas: dict | pd.Series) -> dict:
    """Build an explicit GeoJSON track with observed and estimated geometry tagged.

    ``feas`` may be a feasibility row alone or a merged record row.  The
    latter is what :func:`build_record` supplies so this public function also
    remains convenient for focused unit fixtures.
    """

    sources = [_mapping(feas)]
    endpoint_a_off = _endpoint(sources, "a", "off")
    endpoint_b_off = _endpoint(sources, "b", "off")
    endpoint_a_on = _endpoint(sources, "a", "on")
    endpoint_b_on = _endpoint(sources, "b", "on")
    meeting = record.get("meetingPoint", {}).get("coordinates")
    if not isinstance(meeting, list) or len(meeting) != 2:
        raise ValueError("record is missing an inferred meetingPoint")

    # The points are ordered by observed event time within their role groups,
    # matching the readable timeline and avoiding a silent A/B coordinate swap.
    off_points = [("A", "off", *endpoint_a_off), ("B", "off", *endpoint_b_off)]
    on_points = [("A", "on", *endpoint_a_on), ("B", "on", *endpoint_b_on)]
    off_points.sort(key=lambda item: (item[3], item[0]))
    on_points.sort(key=lambda item: (item[3], item[0]))
    features: list[dict[str, object]] = []
    for vessel, role, coordinates, timestamp, mmsi in [*off_points, *on_points]:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "vessel": vessel,
                    "role": role,
                    "observationStatus": "observed",
                    "time": timestamp,
                    "mmsi": mmsi,
                },
                "geometry": {"type": "Point", "coordinates": coordinates},
            }
        )

    endpoint_by_vessel = {
        "A": (endpoint_a_off, endpoint_a_on),
        "B": (endpoint_b_off, endpoint_b_on),
    }
    for vessel, (off, on) in endpoint_by_vessel.items():
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "vessel": vessel,
                    "observationStatus": "estimated",
                    "confidence": "low",
                    "source": "reachable-set heuristic",
                    "lineStyle": "dashed",
                },
                "geometry": {"type": "LineString", "coordinates": [off[0], list(meeting), on[0]]},
            }
        )
    features.append(
        {
            "type": "Feature",
            "properties": {"observationStatus": "estimated", "kind": "meetingPoint"},
            "geometry": {"type": "Point", "coordinates": list(meeting)},
        }
    )

    dateline = _boolean(_lookup(sources, "dateline"), default=False)
    if not dateline:
        for vessel, alias in (("A", "ring_a"), ("B", "ring_b")):
            ring = _ring(_lookup(sources, alias))
            # A non-dateline but geometrically impossible side has no
            # reachable ellipse.  Omit it honestly rather than inventing an
            # observed-looking shape; normal operating rows have both rings.
            if ring is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "vessel": vessel,
                        "observationStatus": "estimated",
                        "kind": "reachableSet",
                    },
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            )

    return {
        "type": "FeatureCollection",
        "properties": {"dateline": bool(dateline)},
        "features": features,
    }


def _parse_explanations(value: object) -> list[str]:
    raw = _loads_list(value)
    return [str(item) for item in raw if isinstance(item, str) and item.strip()]


_SCORE_COMPONENTS = ("geom", "kin", "beh", "ctx", "cor", "den", "flt", "hab")


def _score_provenance(
    sources: list[Mapping[str, object]],
    scores: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Return materialised S6 provenance, with a useful fixture fallback.

    Full S6 runs supply the JSON ``score_provenance`` column.  The fallback
    keeps older focused S8 fixtures valid without pretending their hand-made
    values had row-level derivation metadata.
    """

    supplied = _loads_object(_lookup(sources, "score_provenance", "scoreProvenance"))
    provenance: dict[str, dict[str, object]] = {}
    for name in _SCORE_COMPONENTS:
        item = _loads_object(supplied.get(name))
        value = _json_value(item.get("value", scores.get(name)))
        provenance[name] = {
            "value": value,
            "weight": _number(item.get("weight"), default=pipeline_config.WEIGHTS[name]),
            "inputs": _json_value(_loads_object(item.get("inputs"))),
            "reason": _clean_string(
                item.get("reason"),
                default="No per-component provenance was materialized for this fixture.",
            )
            or "No per-component provenance was materialized for this fixture.",
            "available": _boolean(item.get("available"), default=value is not None),
        }
    return provenance


def _available_score_components(
    sources: list[Mapping[str, object]],
    scores: Mapping[str, object],
) -> list[str]:
    """Read S6's availability list, retaining a backwards-compatible fallback."""

    supplied = _loads_list(_lookup(sources, "available_components", "availableScoreComponents"))
    available = [str(value) for value in supplied if str(value) in _SCORE_COMPONENTS]
    if available:
        return list(dict.fromkeys(available))
    return [name for name in _SCORE_COMPONENTS if scores.get(name) is not None]


def _build_explanations(
    sources: list[Mapping[str, object]],
    scores: Mapping[str, object],
    corr: Mapping[str, object],
    start_delta: float | None,
    start_distance: float | None,
    end_delta: float | None,
    end_distance: float | None,
    overlap: float | None,
    null_meta: Mapping[str, object],
) -> list[str]:
    supplied = _parse_explanations(_lookup(sources, "explanations"))
    if supplied:
        return supplied

    explanation: list[str] = []
    if None not in {start_delta, start_distance, end_delta, end_distance, overlap}:
        explanation.append(
            f"Both shutoffs {_seconds_text(start_delta)} and {start_distance:.1f} km apart; both reappearances "
            f"{_seconds_text(end_delta)} and {end_distance:.1f} km apart after {overlap:.1f} h."
        )
    p_cell = _number(_lookup(sources, "p_cell"))
    if p_cell is not None:
        draws = _integer(_lookup([null_meta], "draws"), default=0) or 0
        explanation.append(
            f"Within-cell permutation null ({draws} draws): p_cell = {p_cell:.4f}."
        )
    if _boolean(_lookup(sources, "cross_flag")):
        explanation.append("Cross-flag pair; flag-history context is shown where available.")
    neighbours = _integer(_lookup(sources, "local_dark_count"), default=0) or 0
    explanation.append(f"{neighbours} other vessel{'s' if neighbours != 1 else ''} dark within 200 km and ±1 h.")
    if scores.get("beh") is None:
        explanation.append("Behaviour term not available: GFW loitering, encounter and port-visit events not pulled for these vessels.")
    state = _clean_string(_lookup([corr], "viirs_state", "viirsState"), default="no_coverage")
    if state == "no_coverage":
        explanation.append("Imagery: no VIIRS coverage checked for this window.")
    elif state == "clear_no_detection":
        explanation.append("Imagery: coverage showed no qualifying detection inside the inferred reachable sets.")
    elif state == "correlated_only":
        explanation.append("Imagery detections were correlated with known corpus endpoint activity.")
    elif state == "uncorrelated_detection":
        explanation.append("Imagery contained an uncorrelated detection inside the inferred reachable sets.")
    return explanation


def _card_evidence(vessels: list[dict[str, object]], observed_at: str) -> dict[str, object] | None:
    carded = [(index, vessel) for index, vessel in enumerate(vessels) if vessel["flagCard"] in {"yellow", "red"}]
    if not carded:
        return None
    _, vessel = carded[0]
    return {
        "id": "card",
        "claim": f"{vessel['flag']} held an EU IUU {vessel['flagCard']} card at the gap date",
        "source": "EU carding history (hand-made table)",
        "observedAt": observed_at,
        "confidence": "high",
    }


def build_record(
    pair_id: str,
    f: pd.Series | Mapping[str, object],
    ctx: dict | pd.Series | None,
    feas: dict | pd.Series | None,
    corr: dict | pd.Series | None,
    null_meta: dict | None,
) -> dict:
    """Build one frontend record from an S6 feature row and its stage joins.

    The public inputs intentionally accept both dictionaries and Series.  It
    lets stage ``run`` use parquet rows directly, while retaining a small,
    explicit fixture surface for validation tests and future enrichment joins.
    """

    feature = _mapping(f)
    context = _mapping(ctx)
    feasibility = _mapping(feas)
    corroboration = _mapping(corr)
    null_meta = _mapping(null_meta)
    sources = [feature, context, feasibility, corroboration]
    pair_id = _clean_string(pair_id, default=None)
    if pair_id is None:
        raise ValueError("pair_id is required")

    vessels = [_make_vessel("a", sources, context), _make_vessel("b", sources, context)]
    names = [vessel["name"] or vessel["mmsi"] for vessel in vessels]
    name = f"{names[0]} ({vessels[0]['flag']}) × {names[1]} ({vessels[1]['flag']})"

    t0_a = _timestamp(_lookup(sources, "t0_a"))
    t0_b = _timestamp(_lookup(sources, "t0_b"))
    t1_a = _timestamp(_lookup(sources, "t1_a"))
    t1_b = _timestamp(_lookup(sources, "t1_b"))
    if any(value is None for value in (t0_a, t0_b, t1_a, t1_b)):
        raise ValueError(f"{pair_id}: all four observed endpoint timestamps are required")
    assert t0_a is not None and t0_b is not None and t1_a is not None and t1_b is not None
    start = min(t0_a, t0_b)
    end = max(t1_a, t1_b)
    overlap_start = _timestamp(_lookup(sources, "overlap_start")) or max(t0_a, t0_b)
    overlap_end = _timestamp(_lookup(sources, "overlap_end")) or min(t1_a, t1_b)

    meeting_coordinates = _coordinates(
        _lookup(sources, "lon_star", "meeting_lon"), _lookup(sources, "lat_star", "meeting_lat")
    )
    dateline = _boolean(_lookup(sources, "dateline"), default=False)
    if meeting_coordinates is None:
        # Dateline rows may not have a drawable inferred point.  The public
        # contract uses the four-endpoint centroid instead of a made-up one.
        endpoints = [
            _endpoint(sources, "a", "off")[0],
            _endpoint(sources, "a", "on")[0],
            _endpoint(sources, "b", "off")[0],
            _endpoint(sources, "b", "on")[0],
        ]
        if dateline:
            anchor = endpoints[0][0]
            lons = [anchor + ((point[0] - anchor + 180.0) % 360.0) - 180.0 for point in endpoints]
            meeting_coordinates = _coordinates(sum(lons) / len(lons), sum(point[1] for point in endpoints) / len(endpoints))
        else:
            meeting_coordinates = _coordinates(
                sum(point[0] for point in endpoints) / len(endpoints),
                sum(point[1] for point in endpoints) / len(endpoints),
            )
    if meeting_coordinates is None:
        raise ValueError(f"{pair_id}: unable to establish display coordinates")

    start_distance = _round(_lookup(sources, "start_km", "start_distance_km"), 2)
    start_delta = _round(_lookup(sources, "start_delta_min"), 3)
    end_distance = _round(_lookup(sources, "end_km", "end_distance_km"), 2)
    end_delta = _round(_lookup(sources, "end_delta_min"), 3)
    overlap_h = _round(_lookup(sources, "overlap_h", "overlap_hours"), 2)
    p_cell = _round(_lookup(sources, "p_cell"), 4)
    priority = _round(_lookup(sources, "priority"), 2)
    if priority is None:
        raw_for_priority = _number(_lookup(sources, "raw"))
        priority = round(1.0 / (1.0 + math.exp(-pipeline_config.SIGMOID_K * (raw_for_priority - pipeline_config.SIGMOID_MID))), 2) if raw_for_priority is not None else 0.0
    risk_score = _integer(_lookup(sources, "risk_score", "riskScore"), default=None)
    if risk_score is None:
        risk_score = int(round(100.0 * priority))

    scores = {
        "geom": _score_value(sources, "geom"),
        "kin": _score_value(sources, "kin"),
        "beh": _score_value(sources, "beh"),
        "ctx": _score_value(sources, "ctx"),
        "cor": _score_value(sources, "cor"),
        "den": _score_value(sources, "den"),
        "flt": _score_value(sources, "flt"),
        "hab": _score_value(sources, "hab"),
        # Raw remains more precise than the bounded display terms so analysts
        # can reproduce the sigmoid priority from the exported scorecard.
        "raw": _round(_lookup(sources, "raw"), 3),
    }
    score_provenance = _score_provenance(sources, scores)
    available_score_components = _available_score_components(sources, scores)

    label = _clean_string(_lookup(sources, "label"), default="insufficient-evidence") or "insufficient-evidence"
    risk_level = _clean_string(_lookup(sources, "risk_level", "riskLevel"))
    if risk_level not in RISK_LEVELS:
        risk_level = {
            "investigate": "high",
            "coordinated-fleet-pattern": "review",
            "identity-twin": "review",
            "possible-port-transit": "review",
        }.get(label, "watch")
    evidence_tier = _clean_string(_lookup(sources, "evidence_tier", "evidenceTier"), default=None)
    if evidence_tier not in EVIDENCE_TIERS:
        if _score_value(sources, "cor") == 1.0:
            evidence_tier = "imagery_corroborated"
        elif _boolean(_lookup(sources, "loiter_bracket")) or _boolean(_lookup(sources, "encounter_bracket")):
            evidence_tier = "behaviour_corroborated"
        elif label == "investigate":
            evidence_tier = "bilateral_rendezvous_plausible"
        elif label in {"identity-twin", "coordinated-fleet-pattern"}:
            evidence_tier = "coordinated_fleet_activity"
        else:
            evidence_tier = "coincidence_or_artifact"

    zone = _clean_string(_lookup(sources, "zone"), default="unknown") or "unknown"
    rfmo = _clean_string(_lookup(sources, "rfmo_area", "rfmo"))
    shore_distance = _round(_lookup(sources, "shore_off_km", "shore_distance_km"), 2)
    shore_phrase = "unknown" if shore_distance is None else f"{shore_distance:g}"
    location = f"{zone or 'unknown waters'}{', ' + rfmo + ' area' if rfmo else ''}, {shore_phrase} km from shore"

    viirs_detections = _loads_list(_lookup(sources, "viirs_detections", "viirsDetections"))
    corr_state = _clean_string(_lookup(sources, "viirs_state", "viirsState"), default="no_coverage") or "no_coverage"
    if corr_state not in CORROBORATION_STATES:
        corr_state = "no_coverage"
    corroboration_record = {
        "viirsState": corr_state,
        "viirsUncorrelatedCount": _integer(_lookup(sources, "viirs_uncorrelated_count", "viirsUncorrelatedCount"), default=0) or 0,
        "viirsMinKmToMeetingPoint": _round(_lookup(sources, "viirs_min_km_to_p_star", "viirsMinKmToMeetingPoint"), 2),
        "viirsDetections": _json_value(viirs_detections),
        "presenceSource": _clean_string(_lookup(sources, "presence_source", "presenceSource"), default="corpus_endpoints") or "corpus_endpoints",
    }
    null_record = {
        "name": _clean_string(_lookup([null_meta], "name"), default=pipeline_config.NULL_MODEL_NAME) or pipeline_config.NULL_MODEL_NAME,
        "draws": _integer(_lookup([null_meta], "draws"), default=0) or 0,
        "cellDeg": _integer(_lookup([null_meta], "cell_deg", "cellDeg"), default=pipeline_config.CELL_DEG) or pipeline_config.CELL_DEG,
        "observed": _integer(_lookup([null_meta], "observed"), default=0) or 0,
        "nullMean": _round(_lookup([null_meta], "null_mean", "nullMean"), 2),
        "lift": _round(_lookup([null_meta], "lift"), 2),
    }

    neighbours: list[dict[str, object]] = []
    for neighbour in _loads_list(_lookup(sources, "neighbours")):
        if not isinstance(neighbour, Mapping):
            continue
        neighbours.append(
            {
                "mmsi": _clean_string(neighbour.get("mmsi"), default="unknown") or "unknown",
                "flag": _display_flag(neighbour.get("flag")),
                "deltaMin": _round(neighbour.get("deltaMin", neighbour.get("delta_min")), 3),
                "distanceKm": _round(neighbour.get("distanceKm", neighbour.get("distance_km")), 2),
            }
        )

    features = {
        "startDistanceKm": start_distance,
        "startDeltaMin": start_delta,
        "endDistanceKm": end_distance,
        "endDeltaMin": end_delta,
        "durationRatio": _round(_lookup(sources, "duration_ratio"), 4),
        "requiredSpeedKn": _round(_lookup(sources, "required_speed_kn"), 2),
        "jointDwellHours": _round(_lookup(sources, "tau_h", "joint_dwell_hours"), 2),
        "kinPlausibility": _round(_lookup(sources, "kin_plausibility"), 2),
        "pCell": p_cell,
        "localDarkCount": _integer(_lookup(sources, "local_dark_count"), default=0) or 0,
        "localUniqueVessels": _integer(_lookup(sources, "local_unique_vessels"), default=0) or 0,
        "localSameFlagShare": _round(_lookup(sources, "local_same_flag_share"), 2),
        "componentSize": _integer(_lookup(sources, "component_size"), default=0) or 0,
        "componentClass": _clean_string(_lookup(sources, "component_class"), default="unresolved") or "unresolved",
        "sequentialMmsi": _boolean(_lookup(sources, "sequential_mmsi")),
        "identityTwin": _boolean(_lookup(sources, "identity_twin")),
        "crossFlag": _boolean(_lookup(sources, "cross_flag")),
        "gapUnusualness": _round(_lookup(sources, "gap_unusualness"), 2),
        "knownPartners": _integer(_lookup(sources, "known_partners")),
        "loiterBracket": _json_value(_lookup(sources, "loiter_bracket")),
        "encounterBracket": _json_value(_lookup(sources, "encounter_bracket")),
        "portAfterGapRisk": _json_value(_lookup(sources, "port_after_gap_risk")),
        "possiblePortTransit": _json_value(_lookup(sources, "possible_port_transit")),
    }

    on_points = [
        ("A", _endpoint(sources, "a", "on")),
        ("B", _endpoint(sources, "b", "on")),
    ]
    on_points.sort(key=lambda item: item[1][1])
    timeline: list[dict[str, object]] = []
    for vessel, role, endpoint in [
        ("A", "off", _endpoint(sources, "a", "off")),
        ("B", "off", _endpoint(sources, "b", "off")),
        *[(vessel, "on", endpoint) for vessel, endpoint in on_points],
    ]:
        coordinates, timestamp, mmsi = endpoint
        item: dict[str, object] = {
            "time": timestamp,
            "title": f"{mmsi} {'last AIS position' if role == 'off' else 'reappears'}",
            "detail": _coordinate_detail(coordinates),
        }
        if vessel == "B" and role == "off":
            item["emphasis"] = True
        timeline.append(item)

    observed_at = _source_date(overlap_start)
    evidence: list[dict[str, object]] = [
        {
            "id": "sync-off",
            "claim": f"Both vessels ceased AIS {_seconds_text(start_delta)} apart, {start_distance if start_distance is not None else 'unknown'} km apart",
            "source": "GFW disabling corpus",
            "observedAt": observed_at,
            "confidence": "high",
        },
        {
            "id": "sync-on",
            "claim": f"Both reappeared {_seconds_text(end_delta)} apart, {end_distance if end_distance is not None else 'unknown'} km apart, after {overlap_h if overlap_h is not None else 'unknown'} h",
            "source": "GFW disabling corpus",
            "observedAt": _source_date(end),
            "confidence": "high",
        },
        {
            "id": "null",
            "claim": f"Within-cell permutation null, {null_record['draws']} draws: p_cell = {p_cell if p_cell is not None else 'unknown'}",
            "source": "GapPair null model v1",
            "observedAt": _source_date(start),
            "confidence": "medium",
        },
    ]
    card = _card_evidence(vessels, _source_date(start))
    if card is not None:
        evidence.append(card)
    evidence.extend(
        [
            {
                "id": "density",
                "claim": f"{features['localDarkCount']} other vessel{'s' if features['localDarkCount'] != 1 else ''} dark within 200 km and ±1 h",
                "source": "GapPair local context",
                "observedAt": _source_date(start),
                "confidence": "high",
            },
            {
                "id": "geometry",
                "claim": f"Feasible meeting point {meeting_coordinates[0]:.2f}E {meeting_coordinates[1]:.2f}N; joint dwell {features['jointDwellHours'] if features['jointDwellHours'] is not None else 'unknown'} h; required speed {features['requiredSpeedKn'] if features['requiredSpeedKn'] is not None else 'unknown'} kn",
                "source": "Reachable-set heuristic (estimated)",
                "observedAt": _source_date(overlap_start),
                "confidence": "low",
            },
        ]
    )

    record: dict[str, object] = {
        "id": pair_id,
        "tier": "paired-dark",
        "label": label,
        "evidenceTier": evidence_tier,
        "priority": priority,
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "eventKind": "dark-period",
        "eventLabel": "Paired AIS dark period",
        "name": name,
        "imo": f"MMSI {vessels[0]['mmsi']} × {vessels[1]['mmsi']}",
        "flag": f"{vessels[0]['flag']} / {vessels[1]['flag']}",
        "vesselType": f"{_display_class(vessels[0]['vesselClass'])} / {_display_class(vessels[1]['vesselClass'])}",
        "location": location,
        "lastSeen": _source_date(end),
        "coordinates": meeting_coordinates,
        "vessels": vessels,
        "window": {
            "start": _source_date(start),
            "end": _source_date(end),
            "overlapStart": _source_date(overlap_start),
            "overlapEnd": _source_date(overlap_end),
            "overlapHours": overlap_h,
        },
        "meetingPoint": {
            "coordinates": meeting_coordinates,
            "kind": "inferred",
            "method": "argmax joint dwell, 15×15 grid + refinement",
        },
        "jurisdiction": {
            "zone": zone,
            "eez": _json_value(_lookup(sources, "eez")),
            "rfmo": rfmo,
            "eezEntryWhileDark": _json_value(_lookup(sources, "eez_entry_while_dark")),
            "shoreDistanceKm": shore_distance,
            "portDistanceKm": _round(_lookup(sources, "port_distance_km"), 2),
        },
        "scores": scores,
        "availableScoreComponents": available_score_components,
        "scoreProvenance": score_provenance,
        "features": features,
        "corroboration": corroboration_record,
        "nullModel": null_record,
        "neighbours": neighbours,
        "explanations": _build_explanations(
            sources, scores, corroboration, start_delta, start_distance, end_delta, end_distance, overlap_h, null_meta
        ),
        "evidence": evidence,
        "timeline": timeline,
        "sources": [
            {
                "claim": "window.start",
                "value": _source_date(start),
                "source": "GFW disabling corpus",
                "asOf": "2022-08-08",
            }
        ],
        "attribution": pipeline_config.ATTRIBUTION,
        "analystDisposition": None,
    }
    record["track"] = build_track(record, {**feature, **context, **feasibility, "dateline": dateline})
    return _json_value(record)  # type: ignore[return-value]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_no_nan(value: object, path: str = "record") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} contains non-finite number")
    if isinstance(value, np.floating) and not math.isfinite(float(value)):
        raise ValueError(f"{path} contains non-finite number")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_no_nan(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_no_nan(child, f"{path}[{index}]")


def _validate_iso(value: object, path: str) -> None:
    _require(isinstance(value, str) and value.endswith("Z"), f"{path} must be a UTC ISO-8601 Z string")
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{path} is not ISO-8601") from error
    _require(not pd.isna(parsed) and parsed.tzinfo is not None, f"{path} is not timezone-aware ISO-8601")


def _validate_position(value: object, path: str) -> None:
    _require(isinstance(value, list) and len(value) == 2, f"{path} must be [lon, lat]")
    lon, lat = value
    _require(isinstance(lon, (int, float)) and isinstance(lat, (int, float)), f"{path} coordinates must be numeric")
    _require(math.isfinite(float(lon)) and math.isfinite(float(lat)), f"{path} coordinates must be finite")
    _require(-180.0 <= float(lon) <= 180.0 and -90.0 <= float(lat) <= 90.0, f"{path} must use [lon, lat] within bounds")


def _validate_geometry(geometry: object, path: str) -> None:
    _require(isinstance(geometry, Mapping), f"{path}.geometry must be an object")
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        _validate_position(coordinates, f"{path}.geometry.coordinates")
    elif geometry_type == "LineString":
        _require(isinstance(coordinates, list) and len(coordinates) >= 2, f"{path} LineString needs two positions")
        for index, point in enumerate(coordinates):
            _validate_position(point, f"{path}.geometry.coordinates[{index}]")
    elif geometry_type == "Polygon":
        _require(isinstance(coordinates, list) and coordinates, f"{path} Polygon needs rings")
        for ring_index, ring in enumerate(coordinates):
            _require(isinstance(ring, list) and len(ring) >= 4, f"{path} Polygon ring needs four positions")
            for point_index, point in enumerate(ring):
                _validate_position(point, f"{path}.geometry.coordinates[{ring_index}][{point_index}]")
            _require(ring[0] == ring[-1], f"{path} Polygon ring must close")
    else:
        raise ValueError(f"{path}.geometry.type must be Point, LineString, or Polygon")


def validate_record(record: dict) -> None:
    """Raise ``ValueError`` when a record cannot safely meet the static UI contract."""

    _require(isinstance(record, Mapping), "record must be an object")
    _validate_no_nan(record)
    required = {
        "id", "tier", "label", "evidenceTier", "priority", "riskScore", "riskLevel", "eventKind", "eventLabel",
        "name", "imo", "flag", "vesselType", "location", "lastSeen", "coordinates", "vessels", "window",
        "meetingPoint", "jurisdiction", "scores", "features", "corroboration", "nullModel", "neighbours",
        "explanations", "evidence", "timeline", "track", "sources", "attribution", "analystDisposition",
    }
    missing = sorted(required - set(record))
    _require(not missing, f"record is missing required keys: {missing}")
    _require(isinstance(record["id"], str) and record["id"].startswith("t0-"), "id must be a t0 pair id")
    _require(record["tier"] == "paired-dark", "tier must be paired-dark")
    _require(record["label"] in LABELS, "label is not in the export enum")
    _require(record["evidenceTier"] in EVIDENCE_TIERS, "evidenceTier is not in the export enum")
    _require(record["riskLevel"] in RISK_LEVELS, "riskLevel is not in the export enum")
    _require(record["eventKind"] == "dark-period", "eventKind must be dark-period")
    _require(isinstance(record["priority"], (int, float)) and 0.0 <= float(record["priority"]) <= 1.0, "priority must be [0, 1]")
    _require(isinstance(record["riskScore"], int) and 0 <= record["riskScore"] <= 100, "riskScore must be an integer [0, 100]")
    _require(isinstance(record["attribution"], str) and record["attribution"].strip(), "attribution is required")
    _validate_iso(record["lastSeen"], "lastSeen")
    _validate_position(record["coordinates"], "coordinates")

    vessels = record["vessels"]
    _require(isinstance(vessels, list) and len(vessels) == 2, "vessels must contain exactly two vessels")
    vessel_required = {"mmsi", "flag", "vesselClass", "role", "identityStatus", "flagCard", "lengthEstimated", "tonnageEstimated"}
    for index, vessel in enumerate(vessels):
        _require(isinstance(vessel, Mapping), f"vessels[{index}] must be an object")
        _require(not (vessel_required - set(vessel)), f"vessels[{index}] is missing contract fields")
        _require(isinstance(vessel["mmsi"], str) and vessel["mmsi"], f"vessels[{index}].mmsi is required")
        _require(vessel["flagCard"] in {"none", "yellow", "red", "unknown"}, f"vessels[{index}].flagCard is invalid")

    window = record["window"]
    _require(isinstance(window, Mapping), "window must be an object")
    for key in ("start", "end", "overlapStart", "overlapEnd"):
        _require(key in window, f"window.{key} is required")
        _validate_iso(window[key], f"window.{key}")
    _require(isinstance(window.get("overlapHours"), (int, float)), "window.overlapHours must be numeric")
    meeting = record["meetingPoint"]
    _require(isinstance(meeting, Mapping) and meeting.get("kind") == "inferred", "meetingPoint must be inferred")
    _validate_position(meeting.get("coordinates"), "meetingPoint.coordinates")
    _require(record["coordinates"] == meeting["coordinates"], "coordinates must equal meetingPoint.coordinates")

    scores = record["scores"]
    _require(isinstance(scores, Mapping), "scores must be an object")
    for key in ("geom", "kin", "beh", "ctx", "cor", "den", "flt", "hab"):
        _require(key in scores, f"scores.{key} is required")
        value = scores[key]
        _require(value is None or (isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0), f"scores.{key} must be null or [0, 1]")
    _require(scores.get("raw") is None or isinstance(scores.get("raw"), (int, float)), "scores.raw must be numeric or null")

    # These S6 fields are additive by contract.  Validate them when supplied
    # without making historical fixtures (which legitimately omit them) fail.
    if "availableScoreComponents" in record:
        available_score_components = record["availableScoreComponents"]
        _require(isinstance(available_score_components, list), "availableScoreComponents must be a list")
        _require(
            all(isinstance(name, str) and name in _SCORE_COMPONENTS for name in available_score_components),
            "availableScoreComponents contains an invalid component",
        )
        _require(len(set(available_score_components)) == len(available_score_components), "availableScoreComponents must be unique")
    if "scoreProvenance" in record:
        score_provenance = record["scoreProvenance"]
        _require(isinstance(score_provenance, Mapping), "scoreProvenance must be an object")
        _require(set(_SCORE_COMPONENTS).issubset(score_provenance), "scoreProvenance is missing a component")
        for name in _SCORE_COMPONENTS:
            item = score_provenance[name]
            _require(isinstance(item, Mapping), f"scoreProvenance.{name} must be an object")
            _require({"value", "weight", "inputs", "reason", "available"}.issubset(item), f"scoreProvenance.{name} is incomplete")
            value = item.get("value")
            _require(
                value is None or (isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0),
                f"scoreProvenance.{name}.value must be null or [0, 1]",
            )
            _require(isinstance(item.get("weight"), (int, float)), f"scoreProvenance.{name}.weight must be numeric")
            _require(isinstance(item.get("inputs"), Mapping), f"scoreProvenance.{name}.inputs must be an object")
            _require(isinstance(item.get("reason"), str) and item["reason"], f"scoreProvenance.{name}.reason is required")
            _require(isinstance(item.get("available"), bool), f"scoreProvenance.{name}.available must be boolean")

    features = record["features"]
    _require(isinstance(features, Mapping), "features must be an object")
    feature_required = {"startDistanceKm", "startDeltaMin", "endDistanceKm", "endDeltaMin", "pCell", "componentClass"}
    _require(not (feature_required - set(features)), "features is missing required exported values")
    p_cell = features.get("pCell")
    _require(p_cell is None or (isinstance(p_cell, (int, float)) and 0.0 <= float(p_cell) <= 1.0), "features.pCell must be null or [0, 1]")

    corr = record["corroboration"]
    _require(isinstance(corr, Mapping), "corroboration must be an object")
    _require(corr.get("viirsState") in CORROBORATION_STATES, "corroboration.viirsState is invalid")
    _require(isinstance(corr.get("viirsDetections"), list), "corroboration.viirsDetections must be a list")
    null_model = record["nullModel"]
    _require(isinstance(null_model, Mapping) and isinstance(null_model.get("name"), str) and null_model["name"], "nullModel.name is required")

    evidence = record["evidence"]
    _require(isinstance(evidence, list) and evidence, "evidence must be a non-empty list")
    for index, item in enumerate(evidence):
        _require(isinstance(item, Mapping), f"evidence[{index}] must be an object")
        _require(isinstance(item.get("id"), str) and item["id"], f"evidence[{index}].id is required")
        _require(isinstance(item.get("claim"), str) and item["claim"], f"evidence[{index}].claim is required")
        _require(isinstance(item.get("source"), str) and item["source"], f"evidence[{index}].source is required")
        _validate_iso(item.get("observedAt"), f"evidence[{index}].observedAt")

    timeline = record["timeline"]
    _require(isinstance(timeline, list) and len(timeline) == 4, "timeline must contain four endpoint events")
    for index, item in enumerate(timeline):
        _require(isinstance(item, Mapping) and isinstance(item.get("detail"), str), f"timeline[{index}] is malformed")
        _validate_iso(item.get("time"), f"timeline[{index}].time")

    track = record["track"]
    _require(isinstance(track, Mapping) and track.get("type") == "FeatureCollection", "track must be a FeatureCollection")
    track_properties = track.get("properties")
    _require(isinstance(track_properties, Mapping) and isinstance(track_properties.get("dateline"), bool), "track.properties.dateline is required")
    track_features = track.get("features")
    _require(isinstance(track_features, list), "track.features must be a list")
    observed: list[Mapping[str, object]] = []
    lines: list[Mapping[str, object]] = []
    meetings: list[Mapping[str, object]] = []
    rings: list[Mapping[str, object]] = []
    for index, item in enumerate(track_features):
        _require(isinstance(item, Mapping) and item.get("type") == "Feature", f"track.features[{index}] must be a Feature")
        properties = item.get("properties")
        _require(isinstance(properties, Mapping), f"track.features[{index}].properties must be an object")
        _validate_geometry(item.get("geometry"), f"track.features[{index}]")
        geometry_type = item["geometry"]["type"]  # validated Mapping above
        status = properties.get("observationStatus")
        if status == "observed":
            _require(geometry_type == "Point", "observed track geometry must be Point")
            observed.append(item)
        elif geometry_type == "LineString":
            _require(status == "estimated" and properties.get("lineStyle") == "dashed", "projection must be estimated and dashed")
            lines.append(item)
        elif properties.get("kind") == "meetingPoint":
            _require(status == "estimated" and geometry_type == "Point", "meeting point must be estimated Point")
            meetings.append(item)
        elif geometry_type == "Polygon":
            _require(status == "estimated" and properties.get("kind") == "reachableSet", "reachable rings must be estimated")
            rings.append(item)
        else:
            raise ValueError("estimated geometry must not be presented as an observed AIS position")
    _require(len(observed) == 4, "track must have four observed endpoint Points")
    endpoint_roles = {(item["properties"].get("vessel"), item["properties"].get("role")) for item in observed}
    _require(endpoint_roles == {("A", "off"), ("A", "on"), ("B", "off"), ("B", "on")}, "track endpoint roles are incomplete")
    _require(len(lines) == 2, "track must have two dashed projections")
    _require(len(meetings) == 1, "track must have one inferred meeting point")
    if track_properties["dateline"]:
        _require(not rings, "dateline track must omit reachable-set rings")
    else:
        # An impossible individual ellipse is omitted honestly; standard
        # feasible records have two.  Never create fake geometry just to make
        # this count pass.
        _require(len(rings) <= 2, "track may contain at most two reachable-set rings")


def _sort_records(records: Iterable[dict]) -> list[dict]:
    rank = {tier: index for index, tier in enumerate(EVIDENCE_TIERS)}
    return sorted(
        records,
        key=lambda record: (
            rank.get(str(record.get("evidenceTier")), len(rank)),
            -float(record.get("priority", 0.0)),
            str(record.get("id", "")),
        ),
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_value(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_outputs(records: list[dict], out_dir: Path = FRONTEND_DATA) -> None:
    """Validate, sort, and write the queue plus a byte-equivalent track per id."""

    clean = [_json_value(record) for record in records]
    for record in clean:
        validate_record(record)  # type: ignore[arg-type]
    ordered = _sort_records(clean)  # type: ignore[arg-type]
    _write_json(out_dir / "risk-events.json", ordered)
    tracks = out_dir / "tracks"
    tracks.mkdir(parents=True, exist_ok=True)
    for record in ordered:
        _write_json(tracks / f"{record['id']}.geojson", record["track"])


def _read_json(path: Path, default: dict[str, object] | None = None) -> dict[str, object]:
    if not path.exists():
        return {} if default is None else dict(default)
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else ({} if default is None else dict(default))


def _corpus_metrics() -> dict[str, object]:
    path = DERIVED / "gap_events.parquet"
    if not path.exists():
        return {"events": 0, "vessels": 0, "flags": 0, "years": []}
    events = pd.read_parquet(path)
    years = sorted(int(value) for value in pd.to_datetime(events["t0"], utc=True).dt.year.dropna().unique()) if "t0" in events else []
    return {
        "events": int(len(events)),
        "vessels": int(events["mmsi"].nunique(dropna=True)) if "mmsi" in events else 0,
        "flags": int(events["flag"].nunique(dropna=True)) if "flag" in events else 0,
        "years": years,
    }


def _default_sources() -> list[dict[str, str]]:
    return [
        {"name": "Global Fishing Watch AIS-disabling corpus", "detail": "Welch et al. 2022 event corpus used for endpoint observations.", "license": "CC BY-NC 4.0"},
        {"name": "Skylight threshold guidance", "detail": "Context for transparent temporal and spatial screening thresholds."},
        {"name": "Global Fishing Watch encounter rule", "detail": "Potential enrichment source for behaviour evidence."},
        {"name": "Oxford A.1/A.2 kinematic formulation", "detail": "Reachable-set and required-speed heuristic basis."},
        {"name": "WCPFC AIS-only transshipment review", "detail": "Source of the 78% unsubstantiated-after-triangulation precision caveat."},
    ]


def write_methods(
    null: dict,
    ladder: dict,
    config: dict,
    sources: list[dict],
    *,
    records: list[dict] | None = None,
    out: Path | None = None,
) -> None:
    """Write the compact methods drawer payload required by §6.3."""

    output = out or FRONTEND_DATA / "methods.json"
    metrics = _corpus_metrics()
    records = records or []
    ladder_payload = ladder or _mapping(null).get("ladder", {})
    ladder_items: list[dict[str, object]] = []
    if isinstance(ladder_payload, Mapping):
        for rung, values in ladder_payload.items():
            value = _mapping(values)
            ladder_items.append(
                {
                    "rung": str(rung),
                    "observed": _integer(value.get("observed"), default=0) or 0,
                    "nullMean": _round(value.get("null_mean", value.get("nullMean")), 2),
                    "lift": _round(value.get("lift"), 2),
                    "draws": _integer(value.get("draws"), default=_integer(_mapping(null).get("draws"), default=0)) or 0,
                }
            )
    observed_ladder = _read_json(DERIVED / "pair_grid_counts.json")
    for item in ladder_items:
        if not item["observed"] and item["rung"] in observed_ladder:
            item["observed"] = _integer(observed_ladder[item["rung"]], default=0) or 0
    loose_feasibility = _read_json(DERIVED / "loose_feasibility.json")
    labels = pd.Series([record.get("label") for record in records], dtype="string").value_counts().sort_index().to_dict()
    components = pd.Series(
        [record.get("features", {}).get("componentClass") for record in records], dtype="string"
    ).value_counts().sort_index().to_dict()
    count = lambda predicate: sum(1 for record in records if predicate(record))
    payload = {
        "corpus": {
            **metrics,
            "source": "Global Fishing Watch AIS-disabling corpus (Welch et al. 2022)",
            "license": "CC BY-NC 4.0",
        },
        "operatingRule": {
            "startKm": pipeline_config.OPERATING["start_km"],
            "startHours": pipeline_config.OPERATING["start_h"],
            "endKm": pipeline_config.OPERATING["end_km"],
            "endHours": pipeline_config.OPERATING["end_h"],
            "requiresOverlap": True,
            "description": "Two vessel gaps must begin within 10 km and 1 h, end within 10 km and 1 h, and overlap.",
        },
        "ladder": ladder_items,
        "loose": {
            "observed": _integer(observed_ladder.get("loose"), default=0) or 0,
            "feasibleAtTauMin": _integer(loose_feasibility.get("feasible"), default=None),
            "startKm": pipeline_config.LOOSE["start_km"],
            "startHours": pipeline_config.LOOSE["start_h"],
            "endKm": pipeline_config.LOOSE["end_km"],
            "endHours": pipeline_config.LOOSE["end_h"],
            "description": "Methods-only loose rule; it is not a queue source.",
        },
        "null": {
            "name": _clean_string(_mapping(null).get("name"), default=pipeline_config.NULL_MODEL_NAME),
            "cellDeg": _integer(_mapping(null).get("cell_deg", _mapping(null).get("cellDeg")), default=pipeline_config.CELL_DEG),
            "draws": _integer(_mapping(null).get("draws"), default=0),
            "seed": _integer(_mapping(null).get("seed"), default=pipeline_config.SEED),
            "observed": _integer(_mapping(null).get("observed"), default=len(records)),
            "nullMean": _round(_mapping(null).get("null_mean", _mapping(null).get("nullMean")), 2),
            "nullSd": _round(_mapping(null).get("null_sd", _mapping(null).get("nullSd")), 2),
            "lift": _round(_mapping(null).get("lift"), 2),
        },
        "classSpeedsKn": dict(pipeline_config.V_KN),
        "weights": dict(pipeline_config.WEIGHTS),
        "labelRules": [
            "insufficient-evidence: unresolved identity or missing operating evidence.",
            "identity-twin: identity twin or sequential MMSI.",
            "coordinated-fleet-pattern: dominant fleet confounder.",
            "likely-coverage-or-cluster-artifact: dominant density confounder or regional blackout.",
            "possible-port-transit: a qualifying post-gap port transit.",
            "investigate: priority at least 0.50, bilateral, and no dominant penalty.",
        ],
        "labelHistogram": {str(key): int(value) for key, value in labels.items()},
        "componentHistogram": {str(key): int(value) for key, value in components.items()},
        "counts": {
            "crossFlag": count(lambda r: bool(r.get("features", {}).get("crossFlag"))),
            "sequentialMmsi": count(lambda r: bool(r.get("features", {}).get("sequentialMmsi"))),
            "identityTwin": count(lambda r: bool(r.get("features", {}).get("identityTwin"))),
            "bilateral": count(lambda r: r.get("features", {}).get("componentClass") == "bilateral"),
            "zeroNeighbour": count(lambda r: r.get("features", {}).get("localDarkCount") == 0),
        },
        "caveats": [
            "WCPFC found that 78% of 77 AIS-only transshipment candidates were unsubstantiated after triangulation.",
            "Detection is retrospective because both AIS gaps must close before a pair can be assessed.",
            "The corpus covers fishing vessels only; it does not provide coordinate-level ground truth for a transfer.",
            "Meeting points and reachable-set rings are inferred heuristics, never observed AIS positions.",
            "Kinematic plausibility is a reachability screen, not proof of a rendezvous or wrongdoing.",
        ],
        "sources": sources or _default_sources(),
        "attribution": pipeline_config.ATTRIBUTION,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": _json_value(config),
    }
    _write_json(output, payload)


_LEDGER_FIELDS = ("pair_id", "claim_id", "claim_key", "value", "unit", "source", "retrieved_at", "tolerance")


def _ledger_claim(record: Mapping[str, object], evidence: Mapping[str, object]) -> tuple[str, object, str, float | int | None]:
    evidence_id = str(evidence.get("id", ""))
    features = _mapping(record.get("features"))
    mapping: dict[str, tuple[str, object, str, float | int | None]] = {
        "sync-off": ("features.startDistanceKm", features.get("startDistanceKm"), "km", 1.0),
        "sync-on": ("features.endDistanceKm", features.get("endDistanceKm"), "km", 1.0),
        "null": ("features.pCell", features.get("pCell"), "probability", 0.0005),
        "density": ("features.localDarkCount", features.get("localDarkCount"), "count", 0),
        "geometry": ("meetingPoint.coordinates", _mapping(record.get("meetingPoint")).get("coordinates"), "lon_lat", 1.0),
    }
    if evidence_id == "card":
        vessels = record.get("vessels", [])
        if isinstance(vessels, list):
            for index, vessel in enumerate(vessels):
                if isinstance(vessel, Mapping) and vessel.get("flagCard") in {"yellow", "red"}:
                    return (f"vessels.{index}.flagCard", vessel.get("flagCard"), "category", 0)
        return ("vessels.0.flagCard", None, "category", 0)
    return mapping.get(evidence_id, (f"evidence.{evidence_id}", evidence.get("claim"), "text", None))


def write_evidence_ledger(records: list[dict], *, out: Path | None = None) -> None:
    """Write one provenance row for each exported evidence claim."""

    rows: list[dict[str, object]] = []
    for record in records:
        for evidence in record.get("evidence", []):
            if not isinstance(evidence, Mapping):
                continue
            claim_key, value, unit, tolerance = _ledger_claim(record, evidence)
            rows.append(
                {
                    "pair_id": record.get("id"),
                    "claim_id": evidence.get("id"),
                    "claim_key": claim_key,
                    # The ledger holds scalar and coordinate claims in one
                    # typed parquet column.  A JSON scalar keeps that column
                    # consistently textual while retaining each claim's
                    # original number/list/null representation for auditors.
                    "value": json.dumps(_json_value(value), sort_keys=True, allow_nan=False),
                    "unit": unit,
                    "source": evidence.get("source"),
                    "retrieved_at": evidence.get("observedAt"),
                    "tolerance": tolerance,
                }
            )
    destination = out or DERIVED / "evidence_ledger.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=list(_LEDGER_FIELDS)).to_parquet(destination, index=False)


def _showcase(records: list[dict]) -> dict | None:
    for record in records:
        vessels = record.get("vessels", [])
        if isinstance(vessels, list) and {v.get("mmsi") for v in vessels if isinstance(v, Mapping)} == {
            pipeline_config.SHOWCASE["mmsi_a"],
            pipeline_config.SHOWCASE["mmsi_b"],
        }:
            return record
    return None


def write_summary(records: list[dict], null: dict, *, out: Path | None = None) -> None:
    """Write every judge-facing §10 figure, using the current materialized run."""

    metrics = _corpus_metrics()
    showcase = _showcase(records)
    candidates = _read_json(DERIVED / "pair_grid_counts.json")
    ladder = _mapping(null).get("ladder", {})
    ladder_values = []
    if isinstance(ladder, Mapping):
        for name, value in ladder.items():
            entry = _mapping(value)
            ladder_values.append(f"{name}: {entry.get('observed', candidates.get(name, 0))}")
    speed_values = [
        _number(_mapping(record.get("features")).get("requiredSpeedKn"))
        for record in records
    ]
    plausibility_values = [
        _number(_mapping(record.get("features")).get("kinPlausibility"))
        for record in records
    ]
    speed_values = [value for value in speed_values if value is not None]
    plausibility_values = [value for value in plausibility_values if value is not None]
    lines = [
        "# GapPair export summary",
        "",
        "## Judge-facing numbers",
        "",
        f"- Corpus: {metrics['events']:,} deliberate disabling events, {metrics['vessels']:,} vessels, {metrics['flags']:,} flags, {', '.join(map(str, metrics['years']))}; fishing vessels only.",
        f"- Operating rule: both endpoints within 10 km and 1 h with overlapping gaps: {len(records):,} candidates.",
        f"- Null: within-cell permutation ({_mapping(null).get('draws', 0)} draws), mean {_number(_mapping(null).get('null_mean')) or 0:.2f}, lift {_number(_mapping(null).get('lift')) or 0:.2f}×.",
        f"- Ladder: {'; '.join(ladder_values) if ladder_values else 'not available'}.",
        f"- Loose rule: {candidates.get('loose', 0):,} pairs; feasibility retained {_read_json(DERIVED / 'loose_feasibility.json').get('feasible', 'not available')}.",
        f"- Structure: {sum(record.get('features', {}).get('componentClass') == 'bilateral' for record in records)} bilateral; {sum(bool(record.get('features', {}).get('sequentialMmsi')) for record in records)} sequential-MMSI; {sum(bool(record.get('features', {}).get('identityTwin')) for record in records)} identity twins; {sum(bool(record.get('features', {}).get('crossFlag')) for record in records)} cross-flag; {sum(record.get('features', {}).get('localDarkCount') == 0 for record in records)} zero-neighbour.",
        f"- Kinematics: median required speed {float(np.median(speed_values)) if speed_values else float('nan'):.2f} kn; median plausibility {float(np.median(plausibility_values)) if plausibility_values else float('nan'):.2f}.",
    ]
    if showcase is not None:
        features = _mapping(showcase.get("features"))
        jurisdiction = _mapping(showcase.get("jurisdiction"))
        lines.append(
            "- Showcase: "
            f"{features.get('startDeltaMin')} min / {features.get('startDistanceKm')} km at shutoff, "
            f"{features.get('endDeltaMin')} min / {features.get('endDistanceKm')} km at reappearance, "
            f"{_mapping(showcase.get('window')).get('overlapHours')} h overlap, "
            f"{jurisdiction.get('shoreDistanceKm')} km offshore, "
            f"{features.get('localDarkCount')} neighbour(s), p_cell {features.get('pCell')}."
        )
    lines.extend(
        [
            "",
            "## Honest limits",
            "",
            "- Fishing vessels only; no coordinate-level ground truth establishes a transfer.",
            "- Meeting points and reachable sets are inferred heuristics, never observed AIS positions.",
            "- Detection is retrospective because both gaps must close; AIS gaps can also reflect reception conditions.",
            "- The score is an analyst-priority aid, not a probability of wrongdoing.",
            "- WCPFC reported that 78% of 77 AIS-only transshipment candidates were unsubstantiated after triangulation.",
            "",
            f"Attribution: {pipeline_config.ATTRIBUTION}",
        ]
    )
    destination = out or DERIVED / "summary.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _join_on_pair(base: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """Left-join a stage output while safely filling duplicate column names."""

    if extra.empty:
        return base
    if "pair_id" not in extra:
        raise ValueError("stage output is missing pair_id")
    if extra["pair_id"].duplicated().any():
        raise ValueError("stage output has duplicate pair_id values")
    output = base.copy()
    additions = extra.set_index("pair_id", drop=False)
    for column in additions.columns:
        if column == "pair_id":
            continue
        aligned = additions[column].reindex(output["pair_id"]).reset_index(drop=True)
        if column in output:
            output[column] = aligned.where(~aligned.isna(), output[column])
        else:
            output[column] = aligned
    return output


def _endpoint_frame(events: pd.DataFrame, candidates: pd.DataFrame, side: str) -> pd.DataFrame:
    event_columns = ["gap_id", "lat0", "lon0", "lat1", "lon1", "n_gaps_vessel", "length_estimated", "tonnage_estimated"]
    available = [column for column in event_columns if column in events]
    lookup = events.loc[:, available].drop_duplicates("gap_id").set_index("gap_id")
    ids = candidates[f"gap_id_{side}"].astype("string")
    selected = lookup.reindex(ids)
    selected.index = candidates.index
    selected = selected.drop(columns=["gap_id"], errors="ignore")
    return selected.rename(columns={column: f"{column}_{side}" for column in selected.columns})


def run() -> list[dict]:
    """Materialize S8 only after S6 has written its scored queue."""

    required = [
        DERIVED / "candidates_t0.parquet",
        DERIVED / "gap_events.parquet",
        DERIVED / "feasibility.parquet",
        DERIVED / "features.parquet",
        DERIVED / "scores.parquet",
        DERIVED / "null_results.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("export is waiting for upstream artifacts: " + ", ".join(missing))

    candidates = pd.read_parquet(DERIVED / "candidates_t0.parquet")
    events = pd.read_parquet(DERIVED / "gap_events.parquet")
    features = pd.read_parquet(DERIVED / "features.parquet")
    scores = pd.read_parquet(DERIVED / "scores.parquet")
    feasibility = pd.read_parquet(DERIVED / "feasibility.parquet")
    merged = _join_on_pair(candidates, features)
    merged = _join_on_pair(merged, scores)
    merged = _join_on_pair(merged, feasibility)
    for optional in ("local_context.parquet", "components.parquet", "p_cell.parquet", "corroboration.parquet"):
        path = DERIVED / optional
        if path.exists():
            merged = _join_on_pair(merged, pd.read_parquet(path))
    for side in ("a", "b"):
        endpoint = _endpoint_frame(events, candidates, side).reset_index(drop=True)
        for column in endpoint.columns:
            if column in merged:
                merged[column] = merged[column].where(~merged[column].isna(), endpoint[column])
            else:
                merged[column] = endpoint[column]
    pair_counts = pd.concat([candidates["mmsi_a"], candidates["mmsi_b"]], ignore_index=True).value_counts()
    null_meta = _read_json(DERIVED / "null_results.json")
    records: list[dict] = []
    for _, row in merged.iterrows():
        context = {
            "pairs_in_queue_a": int(pair_counts.get(row["mmsi_a"], 0)),
            "pairs_in_queue_b": int(pair_counts.get(row["mmsi_b"], 0)),
        }
        # ``row`` contains all stage fields, including endpoint geometry; use
        # it as the flexible feature source while retaining named inputs for
        # callers and future provenance joins.
        record = build_record(str(row["pair_id"]), row, context, row, row, null_meta)
        validate_record(record)
        records.append(record)

    write_outputs(records)
    write_evidence_ledger(records)
    write_methods(null_meta, _mapping(null_meta).get("ladder", {}), pipeline_config.as_dict(), _default_sources(), records=records)
    write_summary(records, null_meta)
    risk_path = FRONTEND_DATA / "risk-events.json"
    methods_path = FRONTEND_DATA / "methods.json"
    tracks_size = sum(path.stat().st_size for path in (FRONTEND_DATA / "tracks").glob("*.geojson"))
    print(
        f"[export] records={len(records)} risk_events={risk_path.stat().st_size}B "
        f"methods={methods_path.stat().st_size}B tracks={tracks_size}B"
    )
    return records
