"""Central configuration for the AIS dark-gap pairing pipeline.

All thresholds, table constants, and file paths live here so every
pipeline stage (load / pair / null / features / summary) reads the
same numbers.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths ----
ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "disabling_events.csv"
DERIVED = ROOT / "data" / "derived"

GAP_EVENTS_PARQUET = DERIVED / "gap_events.parquet"
EXCLUSIONS_JSON = DERIVED / "exclusions.json"

PAIR_CANDIDATES_PARQUET = DERIVED / "pair_candidates.parquet"
PAIR_CANDIDATES_LOOSE_PARQUET = DERIVED / "pair_candidates_loose.parquet"
PAIR_GRID_JSON = DERIVED / "pair_grid_counts.json"

NULL_RESULTS_JSON = DERIVED / "null_results.json"
NULL_RESULTS_MD = DERIVED / "null_results.md"

PAIR_FEATURES_PARQUET = DERIVED / "pair_features.parquet"
PAIR_FEATURES_LOOSE_PARQUET = DERIVED / "pair_features_loose.parquet"

SUMMARY_MD = DERIVED / "summary.md"

# ------------------------------------------------------------ mmsi rules ----
MMSI_DIGITS = 9
MMSI_MID_MIN = 201
MMSI_MID_MAX = 775

# --------------------------------------------------------- pair thresholds --
# (D_km, T_hours) grid to sweep. "both_ends" thresholds require start AND end
# proximity plus temporal overlap of the two dark intervals; "start_only"
# thresholds only require the start position/time to match.
THRESHOLD_GRID = [
    {"name": "start_only_50_24", "kind": "start_only", "D_km": 50, "T_hours": 24},
    {"name": "start_only_5_1", "kind": "start_only", "D_km": 5, "T_hours": 1},
    {"name": "both_ends_25_3", "kind": "both_ends", "D_km": 25, "T_hours": 3},
    {"name": "both_ends_10_1", "kind": "both_ends", "D_km": 10, "T_hours": 1},
    {"name": "both_ends_5_1", "kind": "both_ends", "D_km": 5, "T_hours": 1},
    {"name": "both_ends_2_0.5", "kind": "both_ends", "D_km": 2, "T_hours": 0.5},
]

# Canonical operating threshold used for feature engineering / summary.
OPERATING_THRESHOLD = {"kind": "both_ends", "D_km": 10, "T_hours": 1}

# Loose threshold: wide net, but overlap of dark intervals is still required.
LOOSE_THRESHOLD = {"kind": "both_ends", "D_km": 50, "T_hours": 6, "require_overlap": True}

# Thresholds nulls are computed for.
NULL_THRESHOLDS = [
    {"name": "both_ends_25_3", "kind": "both_ends", "D_km": 25, "T_hours": 3},
    {"name": "both_ends_10_1", "kind": "both_ends", "D_km": 10, "T_hours": 1},
    {"name": "both_ends_5_1", "kind": "both_ends", "D_km": 5, "T_hours": 1},
    {"name": "start_only_50_24", "kind": "start_only", "D_km": 50, "T_hours": 24},
    {"name": "start_only_5_1", "kind": "start_only", "D_km": 5, "T_hours": 1},
]
CROSS_FLAG_THRESHOLD_NAME = "both_ends_10_1"

N_PERMUTATIONS = 20
NULL_SEED = 42
NULL_CELL_DEGREES = 5.0  # size of the lat/lon grid cell used by Null C

# sequential-MMSI heuristic
SEQUENTIAL_MMSI_MAX_DELTA = 10

# ----------------------------------------------------- feature engineering --
LOCAL_DARK_RADIUS_KM = 200.0
LOCAL_DARK_WINDOW_HOURS = 1.0

# Kinematic feasibility (Fernandez-Villaverde et al., "Dark Shipping", Alg. A.2)
VMAX_KNOTS = {
    "squid_jigger": 12.0,
    "drifting_longlines": 12.0,
    "trawlers": 13.0,
    "tuna_purse_seines": 16.0,
    "other": 14.0,
}
VMAX_DEFAULT = 14.0
MIN_TIME_FLOOR_HOURS = 0.25  # guard against zero/negative elapsed time

EARTH_RADIUS_KM = 6371.0088
KM_TO_NM = 1.0 / 1.852
