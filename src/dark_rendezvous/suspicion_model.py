"""Fast weakly-supervised ship risk model from GFW Presence and GAP events.

The target is deliberately narrow: whether a vessel has a GFW event marked as
intentional AIS disabling in the seven days after a seven-day observation
window.  Unmatched vessels are weak negatives, not verified lawful examples.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neighbors import BallTree
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler


EARTH_RADIUS_KM = 6371.0088

NUMERIC_FEATURES = [
    "observation_count",
    "observed_hours_fraction",
    "active_days",
    "unique_grid_cells",
    "internal_gap_count",
    "max_internal_gap_hours",
    "median_speed_knots",
    "p90_speed_knots",
    "speed_sd_knots",
    "stationary_fraction",
    "movement_distance_km",
    "net_displacement_km",
    "tortuosity",
    "turn_variability_deg",
    "spatial_radius_km",
    "night_observation_fraction",
    "nearest_port_min_km",
    "near_port_20km_fraction",
    "near_port_50km_fraction",
    "nearest_liquid_port_min_km",
    "near_liquid_port_50km_fraction",
    "mean_local_vessel_density",
    "p90_local_vessel_density",
    "mean_region_vessel_count",
    "max_shared_gap_end_count",
    "shared_gap_end_fraction",
    "has_imo",
    "has_callsign",
]
CATEGORICAL_FEATURES = ["vessel_type"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


@dataclass(frozen=True)
class TrainingConfig:
    lookback_days: int = 7
    horizon_days: int = 7
    maximum_segment_hours: float = 2.0
    random_state: int = 17
    cross_validation_folds: int = 3
    top_review_fraction: float = 0.01


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_parquet_files(paths: Sequence[Path], columns: Sequence[str]) -> pd.DataFrame:
    """Read files directly so Hive-like path components are not merged into schemas."""
    frames = []
    for path in paths:
        table = pq.ParquetFile(path).read(columns=list(columns))
        if table.num_rows:
            frames.append(table.to_pandas())
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def load_presence(paths: Sequence[Path]) -> pd.DataFrame:
    columns = [
        "position_id", "ts", "vessel_id", "gfw_vessel_id", "mmsi", "imo",
        "callsign", "lat", "lon", "gfw_vessel_type", "is_valid_position",
    ]
    frame = _read_parquet_files(paths, columns)
    if frame.empty:
        raise ValueError("No non-empty Presence rows were found")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame[frame["is_valid_position"].fillna(False)].copy()
    frame = frame.drop_duplicates("position_id", keep="last")
    frame["mmsi"] = frame["mmsi"].astype("string").str.strip()
    frame["gfw_vessel_id"] = frame["gfw_vessel_id"].astype("string").str.strip()
    return frame.sort_values(["vessel_id", "ts"]).reset_index(drop=True)


def load_gap_events(retrieval_roots: Sequence[Path]) -> tuple[pd.DataFrame, list[tuple[date, date]]]:
    """Load deduplicated intentional events and complete manifest label intervals."""
    rows: list[dict[str, object]] = []
    intervals: list[tuple[date, date]] = []
    for root in retrieval_roots:
        manifest_path = root / "pull_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("complete") or not manifest.get("intentional_disabling"):
            raise ValueError(f"Label retrieval must be complete and intentional-only: {root}")
        intervals.append((date.fromisoformat(manifest["request_start"]), date.fromisoformat(manifest["request_end"])))
        for response_path in sorted(root.rglob("response.json")):
            payload = json.loads(response_path.read_text(encoding="utf-8"))
            for event in payload.get("entries", []):
                gap = event.get("gap") or {}
                vessel = event.get("vessel") or {}
                if gap.get("intentionalDisabling") is not True:
                    continue
                rows.append(
                    {
                        "event_id": event.get("id"),
                        "event_start": event.get("start"),
                        "gfw_vessel_id": vessel.get("id"),
                        "mmsi": vessel.get("ssvid"),
                    }
                )
    events = pd.DataFrame(rows).drop_duplicates("event_id", keep="last")
    events["event_start"] = pd.to_datetime(events["event_start"], errors="coerce", utc=True)
    events["gfw_vessel_id"] = events["gfw_vessel_id"].astype("string").str.strip()
    events["mmsi"] = events["mmsi"].astype("string").str.strip()
    return events.dropna(subset=["event_id", "event_start"]), intervals


def load_ports(path: Path) -> tuple[np.ndarray, np.ndarray]:
    ports = pd.read_csv(path, low_memory=False)
    required = {"Latitude", "Longitude", "Facilities - Oil Terminal", "Facilities - Liquid Bulk"}
    missing = required.difference(ports.columns)
    if missing:
        raise ValueError(f"Port file is missing columns: {sorted(missing)}")
    valid = ports["Latitude"].between(-90, 90) & ports["Longitude"].between(-180, 180)
    ports = ports.loc[valid].copy()
    all_coordinates = ports[["Latitude", "Longitude"]].to_numpy(dtype=float)
    liquid = (
        ports["Facilities - Oil Terminal"].astype("string").str.strip().eq("Yes")
        | ports["Facilities - Liquid Bulk"].astype("string").str.strip().eq("Yes")
    )
    liquid_coordinates = ports.loc[liquid, ["Latitude", "Longitude"]].to_numpy(dtype=float)
    if len(all_coordinates) == 0 or len(liquid_coordinates) == 0:
        raise ValueError("Port file does not contain usable general and liquid-bulk coordinates")
    return all_coordinates, liquid_coordinates


def _covered_days(presence: pd.DataFrame) -> set[date]:
    hourly = presence[["ts"]].drop_duplicates()
    counts = hourly.groupby(hourly["ts"].dt.date)["ts"].nunique()
    return set(counts[counts >= 24].index)


def eligible_anchors(
    presence: pd.DataFrame,
    label_intervals: Sequence[tuple[date, date]],
    config: TrainingConfig,
) -> list[pd.Timestamp]:
    covered = _covered_days(presence)
    anchors: list[pd.Timestamp] = []
    for interval_start, interval_end in label_intervals:
        current = interval_start
        while current < interval_end:
            history_days = {current - timedelta(days=offset) for offset in range(1, config.lookback_days + 1)}
            target_end = current + timedelta(days=config.horizon_days)
            if history_days.issubset(covered) and target_end <= interval_end:
                anchors.append(pd.Timestamp(current, tz="UTC"))
            current += timedelta(days=1)
    return sorted(set(anchors))


def haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    lat1r, lon1r, lat2r, lon2r = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    value = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(value, 0, 1)))


def _bearing_degrees(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    lat1r, lat2r = np.radians(lat1), np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    y = np.sin(dlon) * np.cos(lat2r)
    x = np.cos(lat1r) * np.sin(lat2r) - np.sin(lat1r) * np.cos(lat2r) * np.cos(dlon)
    return (np.degrees(np.arctan2(y, x)) + 360) % 360


def add_port_distances(
    presence: pd.DataFrame,
    all_ports: np.ndarray,
    liquid_ports: np.ndarray,
) -> pd.DataFrame:
    result = presence.copy()
    points = np.radians(result[["lat", "lon"]].to_numpy(dtype=float))
    all_tree = BallTree(np.radians(all_ports), metric="haversine")
    liquid_tree = BallTree(np.radians(liquid_ports), metric="haversine")
    result["nearest_port_km"] = all_tree.query(points, k=1, return_distance=True)[0][:, 0] * EARTH_RADIUS_KM
    result["nearest_liquid_port_km"] = liquid_tree.query(points, k=1, return_distance=True)[0][:, 0] * EARTH_RADIUS_KM
    local_hour = (result["ts"].dt.hour + result["lon"] / 15.0) % 24
    result["is_night"] = ((local_hour >= 20) | (local_hour < 6)).astype(float)
    return result


def add_reception_context(presence: pd.DataFrame, maximum_segment_hours: float) -> pd.DataFrame:
    """Add past-only local density and simultaneous gap-ending context.

    A one-degree cell is intentionally coarse: Presence coordinates are grid
    centres, and a reception interruption can affect vessels across nearby
    high-resolution cells. A gap-ending cluster is evidence against treating a
    single vessel's absence as uniquely suspicious.
    """
    result = presence.sort_values(["vessel_id", "ts"]).copy()
    result["context_lat_bin"] = np.floor(result["lat"])
    result["context_lon_bin"] = np.floor(result["lon"])
    keys = ["ts", "context_lat_bin", "context_lon_bin"]
    result["local_vessel_density"] = result.groupby(keys)["vessel_id"].transform("nunique")
    result["region_vessel_count"] = result.groupby("ts")["vessel_id"].transform("nunique")
    previous = result.groupby("vessel_id")["ts"].shift()
    elapsed = (result["ts"] - previous).dt.total_seconds() / 3600
    gap_ended = elapsed > maximum_segment_hours
    result["shared_gap_end_count"] = 0.0
    if gap_ended.any():
        simultaneous = result.loc[gap_ended].groupby(keys)["vessel_id"].transform("nunique")
        result.loc[gap_ended, "shared_gap_end_count"] = simultaneous.astype(float)
    return result


def _mode_or_unknown(values: pd.Series) -> str:
    cleaned = values.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned.ne("")]
    return cleaned.mode().iloc[0] if not cleaned.empty else "unknown"


def _vessel_window_features(group: pd.DataFrame, config: TrainingConfig) -> dict[str, object]:
    group = group.sort_values("ts")
    lat = group["lat"].to_numpy(float)
    lon = group["lon"].to_numpy(float)
    times = group["ts"]
    dt = times.diff().dt.total_seconds().to_numpy() / 3600
    segment_distance = np.full(len(group), np.nan)
    bearing = np.full(len(group), np.nan)
    if len(group) > 1:
        segment_distance[1:] = haversine_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
        bearing[1:] = _bearing_degrees(lat[:-1], lon[:-1], lat[1:], lon[1:])
    valid_segment = (dt > 0) & (dt <= config.maximum_segment_hours)
    speed = segment_distance[valid_segment] / dt[valid_segment] / 1.852
    valid_distances = segment_distance[valid_segment]
    valid_bearings = bearing[valid_segment]
    if len(valid_bearings) > 1:
        turn = np.abs(((np.diff(valid_bearings) + 180) % 360) - 180)
        turn_variability = float(np.nanmedian(turn))
    else:
        turn_variability = np.nan
    net = float(haversine_km(np.array([lat[0]]), np.array([lon[0]]), np.array([lat[-1]]), np.array([lon[-1]]))[0])
    movement = float(np.nansum(valid_distances))
    center_lat, center_lon = np.nanmedian(lat), np.nanmedian(lon)
    radius = haversine_km(lat, lon, np.full(len(lat), center_lat), np.full(len(lon), center_lon))
    return {
        "vessel_id": group["vessel_id"].iloc[0],
        "gfw_vessel_id": _mode_or_unknown(group["gfw_vessel_id"]),
        "mmsi": _mode_or_unknown(group["mmsi"]),
        "observation_count": len(group),
        "observed_hours_fraction": min(len(group) / (24 * config.lookback_days), 1.0),
        "active_days": times.dt.date.nunique(),
        "unique_grid_cells": group[["lat", "lon"]].drop_duplicates().shape[0],
        "internal_gap_count": int(np.sum(dt > config.maximum_segment_hours)),
        "max_internal_gap_hours": float(np.nanmax(dt)) if len(group) > 1 else 0.0,
        "median_speed_knots": float(np.nanmedian(speed)) if len(speed) else np.nan,
        "p90_speed_knots": float(np.nanpercentile(speed, 90)) if len(speed) else np.nan,
        "speed_sd_knots": float(np.nanstd(speed)) if len(speed) else np.nan,
        "stationary_fraction": float(np.mean(speed <= 1.0)) if len(speed) else np.nan,
        "movement_distance_km": movement,
        "net_displacement_km": net,
        "tortuosity": min(movement / net, 100.0) if net > 0.1 else np.nan,
        "turn_variability_deg": turn_variability,
        "spatial_radius_km": float(np.nanpercentile(radius, 90)),
        "night_observation_fraction": float(group["is_night"].mean()),
        "nearest_port_min_km": float(group["nearest_port_km"].min()),
        "near_port_20km_fraction": float((group["nearest_port_km"] <= 20).mean()),
        "near_port_50km_fraction": float((group["nearest_port_km"] <= 50).mean()),
        "nearest_liquid_port_min_km": float(group["nearest_liquid_port_km"].min()),
        "near_liquid_port_50km_fraction": float((group["nearest_liquid_port_km"] <= 50).mean()),
        "mean_local_vessel_density": float(group["local_vessel_density"].mean()),
        "p90_local_vessel_density": float(group["local_vessel_density"].quantile(0.90)),
        "mean_region_vessel_count": float(group["region_vessel_count"].mean()),
        "max_shared_gap_end_count": float(group["shared_gap_end_count"].max()),
        "shared_gap_end_fraction": float((group["shared_gap_end_count"] >= 2).mean()),
        "has_imo": float(group["imo"].notna().any()),
        "has_callsign": float(group["callsign"].notna().any()),
        "vessel_type": _mode_or_unknown(group["gfw_vessel_type"]),
    }


def build_training_examples(
    presence: pd.DataFrame,
    events: pd.DataFrame,
    anchors: Sequence[pd.Timestamp],
    config: TrainingConfig,
) -> pd.DataFrame:
    examples: list[pd.DataFrame] = []
    for anchor in anchors:
        history_start = anchor - pd.Timedelta(days=config.lookback_days)
        history = presence[(presence["ts"] >= history_start) & (presence["ts"] < anchor)]
        if history.empty:
            continue
        feature_rows = [_vessel_window_features(group, config) for _, group in history.groupby("vessel_id", sort=False)]
        frame = pd.DataFrame(feature_rows)
        future_end = anchor + pd.Timedelta(days=config.horizon_days)
        future = events[(events["event_start"] >= anchor) & (events["event_start"] < future_end)]
        positive_gfw = set(future["gfw_vessel_id"].dropna().astype(str))
        positive_mmsi = set(future["mmsi"].dropna().astype(str))
        frame["target"] = (
            frame["gfw_vessel_id"].astype(str).isin(positive_gfw)
            | frame["mmsi"].astype(str).isin(positive_mmsi)
        ).astype(int)
        frame["anchor_date"] = anchor
        examples.append(frame)
    if not examples:
        raise ValueError("No eligible training examples could be constructed")
    return pd.concat(examples, ignore_index=True)


class PriorCorrectedClassifier(ClassifierMixin, BaseEstimator):
    """Correct class-balanced probabilities back to the observed prevalence.

    This monotonic correction preserves ranking. It avoids unstable fold-wise
    calibration when only a handful of distinct positive vessels are present.
    """

    def __init__(self, estimator: object):
        self.estimator = estimator

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "PriorCorrectedClassifier":
        self.estimator_ = clone(self.estimator)
        self.estimator_.fit(X, y)
        self.prevalence_ = float(np.mean(y))
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        balanced_probability = np.clip(self.estimator_.predict_proba(X)[:, 1], 1e-9, 1 - 1e-9)
        balanced_odds = balanced_probability / (1 - balanced_probability)
        prior_odds = self.prevalence_ / (1 - self.prevalence_)
        corrected = balanced_odds * prior_odds
        positive = corrected / (1 + corrected)
        return np.column_stack([1 - positive, positive])


def build_estimator(random_state: int) -> PriorCorrectedClassifier:
    preprocessing = ColumnTransformer(
        [
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", RobustScaler())]), NUMERIC_FEATURES),
            ("category", OneHotEncoder(handle_unknown="ignore", min_frequency=5), CATEGORICAL_FEATURES),
        ]
    )
    classifier = LogisticRegression(
        class_weight="balanced",
        C=0.5,
        max_iter=2000,
        solver="liblinear",
        random_state=random_state,
    )
    base = Pipeline([("preprocessing", preprocessing), ("classifier", classifier)])
    return PriorCorrectedClassifier(base)


def _top_fraction_metrics(
    y: np.ndarray,
    scores: np.ndarray,
    fraction: float,
    strata: Sequence[object] | None = None,
) -> dict[str, float | int]:
    """Evaluate the review budget in each scoring batch, not across mixed dates."""
    if strata is None:
        strata = np.zeros(len(scores), dtype=int)
    chosen_parts = []
    stratum_values = pd.Series(strata).drop_duplicates().tolist()
    for value in stratum_values:
        indices = np.flatnonzero(np.asarray(strata) == value)
        count = max(1, math.ceil(len(indices) * fraction))
        chosen_parts.append(indices[np.argsort(-scores[indices])[:count]])
    chosen = np.concatenate(chosen_parts)
    count = len(chosen)
    positives = int(y.sum())
    true_positives = int(y[chosen].sum())
    return {
        "review_count": count,
        "true_positives": true_positives,
        "precision": true_positives / count,
        "recall": true_positives / positives if positives else 0.0,
    }


def train_and_evaluate(examples: pd.DataFrame, config: TrainingConfig) -> tuple[object, pd.DataFrame, dict[str, object]]:
    y = examples["target"].to_numpy(dtype=int)
    groups = examples["vessel_id"].astype(str).to_numpy()
    if y.sum() < config.cross_validation_folds:
        raise ValueError("Too few positive examples for cross-validation")
    outer = StratifiedGroupKFold(
        n_splits=config.cross_validation_folds,
        shuffle=True,
        random_state=config.random_state,
    )
    oof = np.full(len(examples), np.nan)
    fold_ids = np.full(len(examples), -1)
    for fold, (train_index, test_index) in enumerate(outer.split(examples, y, groups)):
        estimator = build_estimator(config.random_state + fold)
        estimator.fit(examples.iloc[train_index][FEATURES], y[train_index])
        oof[test_index] = estimator.predict_proba(examples.iloc[test_index][FEATURES])[:, 1]
        fold_ids[test_index] = fold
    metrics: dict[str, object] = {
        "examples": len(examples),
        "unique_vessels": int(examples["vessel_id"].nunique()),
        "positive_examples": int(y.sum()),
        "positive_vessels": int(examples.loc[examples["target"].eq(1), "vessel_id"].nunique()),
        "prevalence": float(y.mean()),
        "random_ranking_average_precision": float(y.mean()),
        "random_ranking_roc_auc": 0.5,
        "constant_prevalence_brier_score": float(np.mean((y - y.mean()) ** 2)),
        "constant_prevalence_log_loss": float(
            -(y.mean() * np.log(y.mean()) + (1 - y.mean()) * np.log(1 - y.mean()))
        ),
        "average_precision": float(average_precision_score(y, oof)),
        "roc_auc": float(roc_auc_score(y, oof)),
        "brier_score": float(brier_score_loss(y, oof)),
        "log_loss": float(log_loss(y, oof, labels=[0, 1])),
        "top_1_percent_per_anchor": _top_fraction_metrics(
            y,
            oof,
            config.top_review_fraction,
            examples["anchor_date"].astype(str).to_numpy(),
        ),
        "evaluation": "out-of-fold predictions grouped by vessel",
    }
    scored = examples[["vessel_id", "gfw_vessel_id", "mmsi", "anchor_date", "target"]].copy()
    scored["suspicion_score"] = oof
    scored["cv_fold"] = fold_ids

    final_model = build_estimator(config.random_state)
    final_model.fit(examples[FEATURES], y)
    return final_model, scored, metrics


def train_from_paths(
    presence_paths: Sequence[Path],
    gap_retrieval_roots: Sequence[Path],
    ports_path: Path,
    output_dir: Path,
    config: TrainingConfig = TrainingConfig(),
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    presence = load_presence(presence_paths)
    events, intervals = load_gap_events(gap_retrieval_roots)
    all_ports, liquid_ports = load_ports(ports_path)
    presence = add_port_distances(presence, all_ports, liquid_ports)
    presence = add_reception_context(presence, config.maximum_segment_hours)
    anchors = eligible_anchors(presence, intervals, config)
    examples = build_training_examples(presence, events, anchors, config)
    model, scored, metrics = train_and_evaluate(examples, config)

    examples_path = output_dir / "training_examples.parquet"
    model_path = output_dir / "ship_suspicion_model.joblib"
    metrics_path = output_dir / "metrics.json"
    predictions_path = output_dir / "out_of_fold_predictions.csv"
    top_path = output_dir / "top_1_percent_predictions.csv"
    manifest_path = output_dir / "training_manifest.json"

    examples.to_parquet(examples_path, index=False)
    scored.to_csv(predictions_path, index=False)
    review_rows = []
    for _, batch in scored.groupby("anchor_date"):
        review_count = max(1, math.ceil(len(batch) * config.top_review_fraction))
        review_rows.append(batch.nlargest(review_count, "suspicion_score"))
    pd.concat(review_rows, ignore_index=True).to_csv(top_path, index=False)
    bundle = {
        "model": model,
        "features": FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "config": asdict(config),
        "target_definition": "GFW intentional AIS-disabling event starting in the next 7 days",
        "negative_definition": "no matched event in the horizon (weak negative)",
    }
    joblib.dump(bundle, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    inputs = list(presence_paths) + list(gap_retrieval_roots) + [ports_path]
    manifest = {
        "config": asdict(config),
        "anchors": [str(anchor.date()) for anchor in anchors],
        "presence_rows": len(presence),
        "deduplicated_label_events": len(events),
        "features": FEATURES,
        "excluded_features": ["flag_state", "vessel identifiers", "GAP event attributes"],
        "input_paths": [str(path) for path in inputs],
        "input_hashes": {
            str(path): file_sha256(path)
            for path in list(presence_paths) + [root / "pull_manifest.json" for root in gap_retrieval_roots] + [ports_path]
        },
        "limitations": [
            "unmatched vessels are weak negatives",
            "Presence positions are hourly grid-cell centres in Russian EEZ region 5690",
            "score predicts a GFW label, not illegality",
            "2021 Presence has fewer than seven consecutive covered history days and is ineligible",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {"metrics": metrics, "anchors": anchors, "output_dir": output_dir}
