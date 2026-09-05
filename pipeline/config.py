"""Single source of truth for thresholds, speeds, weights and paths.

Every value here is documented in methods.json at export. Do not change a
value without updating docs/candidate-pipeline.md.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "disabling_events.csv"
DERIVED = ROOT / "data" / "derived"
REFERENCE = ROOT / "data" / "reference"
BRONZE_GAPS = ROOT / "data" / "bronze" / "gfw_gaps"
FRONTEND_PUBLIC = ROOT / "code" / "frontend" / "public"
OUT_DATA = FRONTEND_PUBLIC / "data"

OPERATING = dict(start_km=10.0, start_h=1.0, end_km=10.0, end_h=1.0)
LADDER = [
    ("start-only 50 km / 24 h", dict(start_km=50.0, start_h=24.0, both_ends=False)),
    ("start-only 5 km / 1 h", dict(start_km=5.0, start_h=1.0, both_ends=False)),
    ("both ends 25 km / 3 h", dict(start_km=25.0, start_h=3.0, end_km=25.0, end_h=3.0)),
    ("both ends 10 km / 1 h", OPERATING),
    ("both ends 5 km / 1 h", dict(start_km=5.0, start_h=1.0, end_km=5.0, end_h=1.0)),
    ("both ends 2 km / 30 min", dict(start_km=2.0, start_h=0.5, end_km=2.0, end_h=0.5)),
]
LOOSE = dict(start_km=50.0, start_h=6.0, end_km=50.0, end_h=6.0)  # methods drawer only, never a queue
TAU_MIN_H = 1.0
V_KN = {
    "squid_jigger": 12.0,
    "drifting_longlines": 12.0,
    "trawlers": 13.0,
    "tuna_purse_seines": 16.0,
    "other": 14.0,
    "carrier": 18.0,
    "reefer": 18.0,
    "unknown": 16.0,
}
KM_PER_KN_H = 1.852
EARTH_R_KM = 6371.0
CELL_DEG = 5
NULL_DRAWS = 200
LADDER_DRAWS = 20
SEED = 20260905
LOCAL_KM = 200.0
LOCAL_H = 1.0
NEIGHBOURS_MAX = 8
SAME_FLAG_MIN_VESSELS = 3
SEQ_MMSI_MAX_DELTA = 10
TWIN_LEN_M = 0.5
TWIN_TON_GT = 1.0
MIN_GAPS_FOR_HISTORY = 3
MMSI_VALID = dict(lo=100_000_000, hi=999_999_999, mid_lo=201, mid_hi=775)
WEIGHTS = dict(geom=0.30, kin=0.15, beh=0.20, ctx=0.15, cor=0.20, den=-0.15, flt=-0.20, hab=-0.10)
SIGMOID_K = 6.0
SIGMOID_MID = 0.30
INVESTIGATE_MIN_PRIORITY = 0.5
PENALTY_DOMINANT = 0.5
FLEET_CLUSTER_MIN_SIZE = 3
BLACKOUT_MIN_SIZE = 5
BLACKOUT_LOCAL_COUNT = 20
PORT_TRANSIT_KM = 50.0
FISHERY_RFMOS = {"NPFC", "WCPFC", "IATTC", "ICCAT", "IOTC", "SPRFMO", "SIOFA", "CCAMLR", "NAFO", "NEAFC", "SEAFO", "GFCM", "CCSBT"}
ATTRIBUTION = "Data: Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0"
NULL_MODEL_NAME = "within-cell permutation v1"

SHOWCASE = dict(mmsi_a="412331147", mmsi_b="416004105", t0_date="2017-07-01")


def class_speed_kn(vessel_class) -> float:
    """Class maximum speed in knots; unknown or missing class → V_KN['unknown']."""
    if vessel_class is None:
        return V_KN["unknown"]
    return V_KN.get(str(vessel_class), V_KN["unknown"])


def as_dict() -> dict:
    """Config values for methods.json (paths excluded)."""
    return {
        k: v
        for k, v in globals().items()
        if k.isupper() and not isinstance(v, Path)
    }
