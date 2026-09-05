# GapPair — backend implementation plan

**Status**

- Written Sat 2026-09-05 ~17:00 EDT on branch `Tanner-dev`. Realises `plan/build-plan.md` (the design); this file is the build order, the module specs, and the contract.
- Owners: Tanner = pipeline S1–S9 and export. Andrew = GFW API pulls (he holds the only token), reference tables, VIIRS attempt. Frontend owner (`gurubazawada`) = consumes `code/frontend/public/data/`.
- First real `risk-events.json` to the frontend: **Sat 20:30**. Full enrichment pass: **Sat 23:30**. Freeze: **Sun 09:30**.
- Everything is precomputed and served as static files. No live API except one optional narration button with a recorded fallback.
- Every number below marked *verified* was reproduced today on the on-disk corpus in the project venv (pure numpy/pandas, no shapely).
- **Revised Sat 16:45 EDT** after merging `origin/andrew-dev` (ec33b4c: presence + track commands, bronze-only backfill, 2021 and partial-2022 GAP bronze) and `origin/main` (ee6253e: prop-less offline `MapPanel`, logo, Slidev deck) into `Tanner-dev`. Changed: §1, §2.9, §2.11, §4 S1′ / S1′′ / S7, §6.1 `corroboration`, §6.4.5, §8, §11, §12, new §13. Nothing in the pipeline specs S1–S6, S8, S9 changed.

---

## 0. Summary

The backend turns the 55,368-event GFW AIS-disabling corpus into a ranked, explainable queue of **T0 paired-dark candidates**: two fishing vessels whose AIS gaps start together and end together. It ships the operating rule (both ends within 10 km and 1 h, dark intervals overlap), one within-cell permutation null with 200 draws, joint reachable-set geometry with an inferred meeting point, local-context and fleet confounders, a static context layer (EU IUU carding, RFMO area, jurisdiction), a transparent scorecard with labels and evidence tiers, an evidence ledger, and an LLM narration whose every factual span is verified against that ledger. Output is `risk-events.json` (all 434 candidates), one GeoJSON track per candidate, `narratives.json`, and `methods.json`, written into the frontend's `public/data/` folder.

Designed but not built (build-plan §0): T1 one-sided and T2 standard tiers, reception-quality penalty, raw tracks, SAR. Behaviour features (loitering, encounters, port visits) and identity fields are **null until Andrew's API pulls land**, and the score treats null as zero contribution with the omission named in the explanation. VIIRS corroboration is a time-boxed attempt for the showcase pair only.

Verified headline numbers: 434 operating pairs, 26 cross-flag, 237 in bilateral components, lift ≈ 36× over the within-cell null, pairing < 1 s, one null draw ≈ 1.1 s, joint feasibility over 18,775 loose pairs 0.3 s. The showcase pair (CHN 412331147 × TWN 416004105, 2017-07-01) is present.

---

## 1. What we have / what we need

| # | Input | Status on disk | Owner | Action |
|---|---|---|---|---|
| D1 | GFW disabling corpus, 55,368 events | `data/raw/disabling_events.csv` (unzipped, gitignored; zip committed) | — | none |
| D1′ | Same events via GFW Events API | Three bronze retrievals are committed: Jan 2017 probe `retrieval_id=20260905T193330Z` (4,658 events, `complete: true`; 1,194/1,195 CSV Jan ids match on `event.id == gap_id`, every match is `vessel.type == "fishing"`); **2021 full year** `…T200519Z` (343,857 events, 695 pages, `complete: true`, bronze-only); **2022 Jan → May** `…T202100Z` (335 pages, no `pull_manifest.json`, still running when committed at 20:31 Z). **Feb 2017 → Dec 2019 is not in the repo.** The timing (probe 19:33 Z, 2021 run starting 20:05 Z) fits the runbook's year loop having pulled 2017–2020 on Andrew's machine in between without committing them. | Andrew | **Commit the 2017–2019 bronze** (or rerun `scripts/run_gfw_bronze_backfill.ps1 -StartDate 2017-01-01 -EndDate 2020-01-01`, ≈ 10 min at the observed 1.3 s/page). `enrich_api.py` reads only retrievals whose windows fall in 2017–2019 and whose `pull_manifest.json` says `complete: true` (§4 S1′). The 2021–2022 bronze is schema evidence and a stretch corpus (§11.7), not an input to the demo queue. |
| D2 | Carrier/reefer gaps | **Answered: the API gap dataset includes `carrier`, `cargo`, `bunker`, `support`, `seismic_vessel`, `passenger` types** (46 carrier events in Jan 2017; 0.13 % carrier and 1.8 % cargo in a 17,500-event sample of 2021). `gear` (buoys, MMSI 99x) is 51 % of Jan 2017 and 87 % of 2021; the MID 201–775 validity rule quarantines it without new code. | Andrew | Comes free with the 2017–2019 pull. Fishing–carrier T0 pairs become possible; keep as stretch (§4 S1′, §11.6). |
| D3–D5 | GFW ENCOUNTER / LOITERING / PORT_VISIT events for queue vessels | none | Andrew | Pull for the 212 queue MMSIs only, after S3 emits the list (§4.10). |
| D7 | GFW vessel identity (names, aliases, authorizations, owner) | none | Andrew | `/vessels/search?query=<mmsi>` for the 212 queue MMSIs; cache raw JSON. |
| D8 | EEZ / RFMO / high-seas / port distance | **Replaced by the API's per-event `regions` and `distances`.** Verified on all 4,658 Jan-2017 events and 17,500 sampled 2021 events: `regions.eez` holds Marine Regions MRGID strings (e.g. `"8463"`); `regions.highSeas` is **empty on every event** (not populated in this dataset version); `regions.rfmo` carries `ACAP` and `IWC` on every event; `distances` gives shore and port km at both ends. No polygon download. | Andrew | 2017–2019 pull as above. Rules: `high_seas = (eez == [])`; drop `ACAP`, `IWC`, `IPHC` from `rfmo`; MRGID → name via a static table, else show the MRGID. Fallback: `regions` missing → `jurisdiction.zone = "unknown"`. |
| D9 | EU IUU carding history; PSMA parties; RFMO IUU lists | none | Andrew | Hand-made CSVs in `data/reference/` (§4.0, Appendix A). Carding table is 30 min; PSMA and IUU lists are optional. |
| D11 | VIIRS boat detections for the showcase night | none; coverage unknown | Andrew | 90-minute time box (§4.7). Default output is `no_coverage`. |
| D12 | AIS presence for VIIRS correlation | **New: `gfw-presence` command** (4Wings `public-global-presence:v4.0`, one AIS position per vessel-hour reported as a 0.01° grid-cell centre, bounded by a region id, `--reuse-last-report` for timeouts). Smoke-tested on the Russian EEZ (region 5690): one hour of 2022-01-01 → 1,975 rows; one day of 2026-08-01 → 31,477 rows with MMSI, IMO, name, flag and `vesselType` (`FISHING`, `CARRIER`, `CARGO`, …). Silver rows are labelled `position_semantics = gfw_presence_grid_center_hourly`. | Andrew | Only if S7 obtains real VIIRS detections: one report for the showcase window 2017-07-01 → 07-03 over the NPFC or WCPFC region (`--region-dataset public-rfmo`; confirm the region id and that v4.0 reaches 2017 while the token is live). One report per account at a time; large windows time out. Default stays the build-plan §6 fallback: corpus endpoints within ±1 h and 5 km. |
| D13 | Raw tracks | `gfw-track` exists (`/vessels/{id}/tracks`, LINES format, no thinning) but the token's application has **no `public-global-fishing-tracks` permission: the route returns 404** (`docs/ais-ingestion.md`). | — | Stays deferred; the reachable-set heuristic is the only track geometry in the demo. |
| Code | `src/dark_rendezvous/` (GFW client, paginated pull with `--bronze-only` / `--all-gaps`, presence and track normalisers, `position_semantics` on every canonical row, manifests) | merged (ec33b4c), **not installed**. `pyproject.toml` still pins `python<3.14`, `pandas<3` and requires `shapely`; `providers/__init__.py` imports the NOAA provider, which imports `shapely` at module level, so even `from dark_rendezvous.providers.gfw import normalize_gap_endpoints` fails without it. With `shapely` 2.1.2 in `.venv`, **all 9 tests pass on Python 3.14 / pandas 3.0.5** (run 16:41 EDT with `PYTHONPATH=src`), so the pins are merely tight. Andrew runs it from `.venv313` on Windows. | Andrew | Relax pins to `>=3.11` and `pandas>=2.2,<4`; move the `shapely` import inside `NoaaMarineCadastreProvider` or make the package `__init__` lazy. Until then the pipeline **does not import** `dark_rendezvous`; `enrich_api.py` parses the bronze JSON itself (§2.9). |
| Env | `.venv` Python 3.14.2, pandas 3.0.5, numpy 2.5.2, pyarrow 25, scipy 1.18 | `httpx`, `pytest` and `shapely` 2.1.2 installed 16:40 EDT during this review (shapely only to run Andrew's tests); still no anthropic, fastapi | Tanner | `pip install anthropic` before S9. **The pipeline never imports shapely**; its presence in the venv does not change that rule. |
| Token | `GFW_API_TOKEN` | only on Andrew's machine | Andrew | Never commit; API-dependent stages run on his machine and commit outputs. |
| Key | `ANTHROPIC_API_KEY` | none | Tanner | Needed for S9 precompute (~$1 total). |
| Frontend | React/Vite app; `types.ts` and `provider.ts` unchanged (`mock` / `api` modes only); `MapPanel` on `main` (ee6253e) takes **no props** and draws an offline Natural Earth basemap (`world-atlas` + `topojson-client`) with no vessel layer; `App.tsx` no longer passes `vessels/selected/onSelectVessel`; `presentation/slides.md` is a Slidev deck with placeholder numbers ("AIS GAP 14h 22m") | `origin/main` **merged into `Tanner-dev`** (dd7e94e) | Frontend owner | Restore the three `MapPanel` props and the point + track layers on top of the `land` source (§6.4.5); add the `static` provider mode; feed §10 into the deck at freeze. |

---

## 2. Decisions this plan makes (deviations from build-plan.md, with reasons)

1. **The loose rule (50 km / 6 h) is a methods-drawer number, not a queue source.** *Verified:* joint feasibility (§3.2) keeps 18,735 of 18,775 loose pairs at τ_min = 1 h, so "loose plus feasibility" is ~18,300 candidates, not a queue. The queue is the 434 operating pairs. Kinematics is still computed for every operating pair (rings, p*, required speed) because the map drawing needs it.
2. **Jurisdiction comes from the GFW API `regions` field, not from polygons.** The Jan-2017 pull already shows `eez`, `rfmo`, `highSeas`, `fao`, `mpa` per event plus shore and port distances. A full pull is ~10 minutes of Andrew's time and removes D8 entirely.
3. **All 434 candidates are exported**, sorted by evidence tier then priority. The frontend filters by label. Size ≈ 1.5 MB without tracks.
4. **Each record embeds its own `track` FeatureCollection** and the same geometry is also written to `tracks/<id>.geojson`. One fetch for the UI; the per-file contract from `code/backend/README.md` still holds.
5. **`imo` is emitted as a display string** (`"MMSI 412331147 × 416004105"`) because the UI renders and searches it today (`InvestigationPanel.tsx`, `App.tsx`). All coordinates `[lon, lat]`; all timestamps ISO-8601 UTC; the UI formats.
6. **Null score terms contribute zero and are named in `explanations[]`.** This reproduces build-plan §5's worked range exactly (showcase 0.51 with no VIIRS, 0.77 with an uncorrelated light) and needs no weight renormalisation.
7. **Same-flag-share fleet rule needs at least 3 neighbouring vessels.** With one neighbour the share is trivially 1.0 and would mark the showcase pair as a fleet. Below 3 neighbours the sub-term is null.
8. **Sequential MMSI = same MID (first three digits) and |Δ| ≤ 10.** *Verified:* 173 of 434 pairs (build-plan quoted 173 for "sequential", which matches this definition).
9. **Package layout is a top-level `pipeline/`**, per build-plan §8, not a subpackage of `src/dark_rendezvous/`: that package is not installed, pins an incompatible Python, and only the optional enrichment stage needs it. The merge reinforced this: its `providers/__init__.py` drags in `shapely`, and Andrew runs it from a Python 3.13 venv on Windows. `enrich_api.py` therefore reads the bronze JSON directly instead of calling `normalize_gap_endpoints`.
10. **Narration model is `claude-opus-5` at `effort: "low"`** with structured outputs, per the current Claude API reference; OpenAI is a 15-line provider shim if the team wants sponsor points (§4.9).
11. **The demo corpus stays the 2017–2019 CSV.** The 2021 and partial-2022 API pulls are not merged into the queue: every verified number, the null and the showcase depend on the corpus, and the API population is 87 % gear buoys carrying GFW's own disabling classification. They serve to confirm the API schema (§4 S1′) and are a stretch (§11.7).

---

## 3. Repository layout and how to run

```
pipeline/
  __init__.py
  config.py        thresholds, speeds, weights, paths — the single source of truth
  geo.py           haversine, 5° cells, local planar frame, ellipse ring, dateline helpers
  reference.py     S0  static tables: EU carding, PSMA, RFMO names, class speeds
  load.py          S1  CSV → gap_events.parquet + exclusions.json (+ optional API enrichment join)
  enrich_api.py    S1′ bronze GFW JSON → gfw_gap_enrichment.parquet (regions, distances, names, types); complete 2017–2019 retrievals only
  feasibility.py   S2  reachable sets, joint feasibility, rings
  pair_t0.py       S3  operating rule, ladder, brute-force check
  context.py       S4  local density, components, identity flags, vessel history
  nulls.py         S5  within-cell permutation null, p_cell
  features.py      S6a feature table
  score.py         S6b terms, raw, priority, label, evidence tier, explanations
  corroborate.py   S7  VIIRS three-state join (default no_coverage)
  export.py        S8  risk-events.json, tracks/, methods.json, evidence_ledger.parquet, summary.md
  narrate.py       S9a LLM narration with tagged spans
  verify.py        S9b deterministic span verifier + adversarial mode
  serve.py         optional 40-line FastAPI for the live narration button
  run.py           orchestrator: python -m pipeline.run --all | --stage <name> [--draws N]
tests/
  test_pipeline_geo.py  test_pipeline_pair.py  test_pipeline_score.py  test_pipeline_verify.py
data/reference/        committed: eu_iuu_cards.csv, psma_parties.csv, rfmo_names.json, class_speeds.json, gfw_gap_enrichment.parquet
data/derived/          gitignored parquet/json intermediates (rerun from files)
code/frontend/public/data/   committed outputs: risk-events.json, tracks/<id>.geojson, narratives.json, methods.json
```

Run from the repo root:

```bash
.venv/bin/pip install anthropic                          # httpx, pytest (and shapely, for Andrew's tests) already installed 16:40 EDT
.venv/bin/python -m pipeline.run --all --draws 20      # first end-to-end, ~1 min
.venv/bin/python -m pipeline.run --stage null --draws 200   # ~5 min, run in background
.venv/bin/python -m pipeline.run --stage score --stage export
.venv/bin/python -m pipeline.run --stage narrate --top 20    # needs ANTHROPIC_API_KEY
.venv/bin/python -m pytest tests/test_pipeline_*.py
```

Every stage reads and writes files under `data/derived/`; `run.py` is a plain ordered list of stage functions with a `--stage` filter, no framework. Seed everything with `config.SEED = 20260905`.

### `config.py` (values, all documented in `methods.json`)

```python
OPERATING = dict(start_km=10.0, start_h=1.0, end_km=10.0, end_h=1.0)
LADDER = [("start-only 50 km / 24 h", dict(start_km=50, start_h=24, both_ends=False)),
          ("start-only 5 km / 1 h",   dict(start_km=5,  start_h=1,  both_ends=False)),
          ("both ends 25 km / 3 h",   dict(start_km=25, start_h=3,  end_km=25, end_h=3)),
          ("both ends 10 km / 1 h",   OPERATING),
          ("both ends 5 km / 1 h",    dict(start_km=5,  start_h=1,  end_km=5,  end_h=1)),
          ("both ends 2 km / 30 min", dict(start_km=2,  start_h=0.5, end_km=2, end_h=0.5))]
LOOSE = dict(start_km=50.0, start_h=6.0, end_km=50.0, end_h=6.0)   # methods drawer only
TAU_MIN_H = 1.0
V_KN = {"squid_jigger": 12, "drifting_longlines": 12, "trawlers": 13, "tuna_purse_seines": 16,
        "other": 14, "carrier": 18, "reefer": 18, "unknown": 16}
KM_PER_KN_H = 1.852; EARTH_R_KM = 6371.0
CELL_DEG = 5; NULL_DRAWS = 200; LADDER_DRAWS = 20; SEED = 20260905
LOCAL_KM = 200.0; LOCAL_H = 1.0; NEIGHBOURS_MAX = 8; SAME_FLAG_MIN_VESSELS = 3
SEQ_MMSI_MAX_DELTA = 10; TWIN_LEN_M = 0.5; TWIN_TON_GT = 1.0; MIN_GAPS_FOR_HISTORY = 3
MMSI_VALID = dict(lo=100_000_000, hi=999_999_999, mid_lo=201, mid_hi=775)
WEIGHTS = dict(geom=0.30, kin=0.15, beh=0.20, ctx=0.15, cor=0.20, den=-0.15, flt=-0.20, hab=-0.10)
SIGMOID_K = 6.0; SIGMOID_MID = 0.30
INVESTIGATE_MIN_PRIORITY = 0.5; PENALTY_DOMINANT = 0.5
FLEET_CLUSTER_MIN_SIZE = 3; BLACKOUT_MIN_SIZE = 5; BLACKOUT_LOCAL_COUNT = 20
PORT_TRANSIT_KM = 50.0
ATTRIBUTION = "Data: Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0"
```

---

## 4. Stage specifications

Conventions for every stage: distances km, speeds knots, durations hours, `km = kn · h · 1.852`, haversine with R = 6371 km. Timestamps are `datetime64[us, UTC]` under pandas 3; **never divide an int64 view by a constant** — use `(t1 - t0) / pd.Timedelta(hours=1)` or `values.astype('datetime64[us]').astype('int64') / 3.6e9` with the unit written out. Longitudes normalised to [−180, 180] on output. No `log(0)`: every probability carries a pseudo-count.

### `geo.py` — shared primitives (0.5 h)

```python
def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray            # vectorised, R = 6371
def cell_id(lat, lon, deg=5) -> np.ndarray[int]                    # floor((lon+180)/deg) % (360/deg) * 100 + floor((lat+90)/deg); wraps at ±180
def local_frame(lat_c, lon_c) -> tuple[float, float]               # km per degree: kx = 111.32·cos(lat_c), ky = 110.57
def to_local(lat, lon, lat_c, lon_c) -> tuple[np.ndarray, np.ndarray]   # lon unwrapped: lon_c + ((lon − lon_c + 180) % 360 − 180)
def from_local(x, y, lat_c, lon_c) -> tuple[np.ndarray, np.ndarray]     # lon normalised to [−180, 180]
def crosses_dateline(lons: np.ndarray) -> bool                     # max(lon) − min(lon) > 180 after normalisation
```

Unit tests: haversine(0,0,0,1) ≈ 111.19 km; cell_id wraps (lon 179.9 and −179.9 differ by one cell index, not 71); to_local/from_local round-trip across ±180.

### S0 `reference.py` — static tables (Andrew, 0.5–1 h)

Reads `data/reference/*.csv|json`, returns dataframes with time validity. Functions:

```python
def flag_card(flag: str | None, at: pd.Timestamp) -> str        # "none" | "yellow" | "red" | "unknown" (flag missing)
def psma_party(flag: str | None, at: pd.Timestamp) -> bool | None
def rfmo_name(code: str) -> str
def class_speed_kn(vessel_class: str | None) -> float
```

`eu_iuu_cards.csv` columns: `flag_iso3, colour, start_date, end_date, source_url, confidence`. Seed rows are in Appendix A; Andrew verifies against the Commission press releases before the pitch. `TWN` is the flag code used by the corpus. Missing flag → `"unknown"`, never `"none"`.

### S1 `load.py` — normalise the corpus (1 h)

```python
def load_gap_events(csv_path: Path = config.RAW_CSV) -> pd.DataFrame
def write_gap_events(df: pd.DataFrame, out: Path = DERIVED / "gap_events.parquet") -> None
def write_exclusions(df: pd.DataFrame, out: Path = DERIVED / "exclusions.json") -> None
```

Output columns of `gap_events.parquet` (one row per gap, all 55,368 kept, invalid rows flagged):

| column | type | rule |
|---|---|---|
| `gap_id` | str | source primary key |
| `mmsi` | str | zero-padded 9 digits, kept as text |
| `mmsi_int`, `mid` | int | for arithmetic; `mid = mmsi_int // 1_000_000` |
| `mmsi_valid` | bool | `100000000 ≤ mmsi ≤ 999999999` and `201 ≤ mid ≤ 775` → *verified 54,553 valid, 815 invalid* |
| `vessel_class` | str | as source |
| `flag` | str or null | blank → null (702 rows) |
| `length_m`, `tonnage_gt` | float | as source; **both are GFW estimates** → `length_estimated = tonnage_estimated = True` |
| `t0`, `t1` | datetime64[us, UTC] | `pd.to_datetime(..., utc=True)` |
| `lat0, lon0, lat1, lon1` | float | as source |
| `shore_off_km`, `shore_on_km` | float | source metres / 1000 |
| `gap_hours_source` | float | as source (never overwritten) |
| `gap_hours_exact` | float | `(t1 − t0) / Timedelta(hours=1)` |
| `cell` | int | `geo.cell_id(lat0, lon0)` |
| `cell_month` | str | `f"{cell}-{t0:%Y-%m}"` |
| `dateline` | bool | `abs(lon0 − lon1) > 180` → *verified 484* |
| `v_kn`, `v_kmh` | float | class speed; `v_kmh = v_kn · 1.852` |
| `n_gaps_vessel` | int | gaps for this MMSI in the corpus |

`exclusions.json` reproduces the existing checkpoint (`invalid_mmsi: 815`, `n_valid_for_pairing: 54553`, `blank_flag: 702`, `negative_or_zero_duration: 0`, `duplicate_gap_id: 0`) plus the run's `created_at`, source SHA-256, and row count.

Acceptance: 55,368 rows; `t0.dtype == "datetime64[us, UTC]"`; 54,553 valid; 484 dateline; `gap_hours_exact` within 0.017 h of `gap_hours_source` for all rows.

### S1′ `enrich_api.py` — GFW API enrichment (Andrew, 1 h incl. the pull)

Reads every `data/bronze/gfw_gaps/**/response.json`, extracts per event:

```python
def build_enrichment(bronze_root: Path) -> pd.DataFrame
# columns: gap_id, gfw_vessel_id, vessel_name, vessel_type, flag_api,
#          eez_start (list[str] MRGIDs), rfmo (list[str]), high_seas (bool), fao (list[str]), mpa (list[str]),
#          shore_off_km_api, shore_on_km_api, port_off_km, port_on_km, dataset_version, retrieval_id
```

Written to `data/reference/gfw_gap_enrichment.parquet` (committed; a few MB for 36 months). `load.py` left-joins it on `gap_id` when present.

Reading rules, from the bronze layout Andrew's pull writes (`data/bronze/gfw_gaps/retrieval_id=*/window_start=*/window_end=*/offset=*/response.json`, a `manifest.json` beside each page, and one `pull_manifest.json` per retrieval **written only when the run finishes**):

- Read every retrieval whose `window_start` falls in 2017-01 → 2019-12. Skip retrievals with no `pull_manifest.json` or with `complete: false` (the 2022 run has neither) and skip 2020+ windows. Deduplicate on `event.id`, keeping the latest `retrieval_id`.
- Facts verified on the merged bronze (all 4,658 Jan-2017 events; 17,500 sampled 2021 events): `event.id` equals the CSV `gap_id` (1,194/1,195 Jan matches, all `vessel.type == "fishing"`); `gap.onPosition.lat/lon`, `gap.distanceKm`, `gap.impliedSpeedKnots` and `gap.positions12HoursBeforeSat` arrive as **strings** on most events while `offPosition` is numeric → `pd.to_numeric(..., errors="coerce")` on every numeric field; `regions.highSeas` is **empty on every event** → `high_seas = (len(eez) == 0)`; `regions.eez` is a list of MRGID strings; `regions.rfmo` always includes `ACAP` and `IWC`; `vessel.flag` is null on 84 % of 2021 events (gear); every event is closed and has `intentionalDisabling: true` because the pull filters on it (`--all-gaps` widens the population).
- Still to confirm from the GFW docs while the token is live: whether `regions` describe the event centroid (`position`) or both endpoints (assume centroid; `eez_entry_while_dark` then needs the endpoint-level `eez12Nm`/`eez` semantics — if unclear, set `eezEntryWhileDark: null` and say so in `methods.json`), and the MRGID → country name mapping (GFW's `/datasets/public-eez-areas/context-layers` or a static Marine Regions table; fallback: show the MRGID). Keep only fishery RFMOs: NPFC, WCPFC, IATTC, ICCAT, IOTC, SPRFMO, SIOFA, CCAMLR, NAFO, NEAFC, SEAFO, GFCM, CCSBT.

The carrier finding (D2) means the same pull yields carrier gaps. If time allows, `pair_t0.py` can be re-run over fishing ∪ carrier events to produce fishing–carrier T0 pairs (`rolePair = "fishing-carrier"`), which would light up the `S_beh` role term (§4.6). Stretch only.

### S2 `feasibility.py` — reachable sets and joint feasibility (1.5 h)

Build-plan §3.1–3.3. Pure functions over numpy arrays; called per candidate batch from S3.

```python
@dataclass
class Endpoints:            # arrays of equal length P (one entry per pair side)
    lat0: np.ndarray; lon0: np.ndarray; t0_h: np.ndarray
    lat1: np.ndarray; lon1: np.ndarray; t1_h: np.ndarray
    v_kmh: np.ndarray

@dataclass
class JointFeasibility:
    tau_h: np.ndarray            # max_p τ_AB(p), hours (may be negative → infeasible)
    lon_star: np.ndarray; lat_star: np.ndarray
    required_speed_kn: np.ndarray
    kin_plausibility: np.ndarray # clip(1 − required_speed / min(v_a, v_b) in kn, 0, 1)
    feasible: np.ndarray         # tau_h ≥ TAU_MIN_H

def joint_feasibility(a: Endpoints, b: Endpoints, n_grid: int = 15, tau_min: float = 1.0) -> JointFeasibility
def reachable_ring(lat0, lon0, t0_h, lat1, lon1, t1_h, v_kmh, tau_min=1.0, n=64) -> np.ndarray | None  # (n, 2) [lon, lat]
def dwell_at(point_lon, point_lat, side: Endpoints) -> np.ndarray   # (t1−t0) − (D(p0,p)+D(p,p1))/v
```

Algorithm for `joint_feasibility` (*verified: 0.3 s for 18,775 pairs*):
1. Local frame per pair around the mean of the four endpoints; unwrap longitudes relative to the first endpoint so a dateline pair does not straddle.
2. Grid: `n_grid × n_grid` points over the endpoints' bounding box padded by `0.25 · max(extent) + 20 km`.
3. `arrive_v(p) = t0_v + D(p0_v, p)/v_v`, `depart_v(p) = t1_v − D(p, p1_v)/v_v` with planar `D`; `τ_AB(p) = min(depart_A, depart_B) − max(arrive_A, arrive_B)`.
4. `p* = argmax τ_AB`; refine once on a grid of the same size spanning ± one coarse cell around `p*`.
5. `required_speed_kn = max_v (D(p0_v,p*) + D(p*,p1_v)) / (t1_v − t0_v) / 1.852` (Oxford A.2 zero-dwell form).
6. Convert `p*` back to lon/lat; normalise.

`reachable_ring`: ellipse with foci p0, p1 in the local frame, `2a = v_kmh · (T − τ_min)`, `c = D(p0,p1)/2`; if `a ≤ c` return `None`; `b = sqrt(a² − c²)`; sample 64 angles; rotate by `atan2(y1−y0, x1−x0)`; translate to the midpoint; convert back. If `crosses_dateline` on the result, return `None` and set `geometry.dateline = true` downstream (build-plan §7: omit rather than draw).

Output `feasibility.parquet` keyed by `pair_id`: `tau_h, lon_star, lat_star, required_speed_kn, kin_plausibility, feasible, ring_a (JSON list or null), ring_b, dateline`.

Acceptance (*verified*): showcase τ = 38.6 h, required speed 0.92 kn, p* ≈ (161.958, 42.752); over the 434 operating pairs τ min 0.4 h, median 14.0 h, required-speed median 0.65 kn, kin_plausibility median 0.95. Unit tests: two identical gaps → τ = T; a pair whose endpoints require 40 kn → infeasible; a synthetic pair across 180° returns `dateline = True` and no ring.

### S3 `pair_t0.py` — candidate generation (1 h)

```python
def pair_events(ev: pd.DataFrame, *, start_km, start_h, end_km=None, end_h=None, both_ends=True) -> pd.DataFrame  # columns i, j (positions in ev sorted by t0)
def build_candidates(ev: pd.DataFrame) -> pd.DataFrame          # operating rule + geometry features + pair_id
def ladder_counts(ev: pd.DataFrame) -> dict[str, int]
def brute_force_check(ev: pd.DataFrame, n_sample=1500, seed=SEED) -> None   # asserts equality, raises otherwise
def make_pair_id(gap_id_a: str, gap_id_b: str) -> str            # "t0-" + sha1("|".join(sorted([a, b]))).hexdigest()[:12]
```

Blocking: sort valid events by `t0`; `hi = searchsorted(t0, t0 + start_h)`; for each `i`, candidates `j ∈ (i, hi[i])` with different MMSI; vectorised haversine on shutoffs ≤ `start_km`; overlap `min(t1) − max(t0) > 0`; then reappearance distance ≤ `end_km` and `|t1_i − t1_j| ≤ end_h`. The Python loop over 54k rows with numpy inner work runs in 0.8 s; do not optimise further.

Canonical ordering: side A is the earlier shutoff (tie → smaller `gap_id`). Candidate columns:

`pair_id, gap_id_a, gap_id_b, mmsi_a, mmsi_b, flag_a, flag_b, class_a, class_b, t0_a, t1_a, t0_b, t1_b, start_km, start_delta_min, end_km, end_delta_min, overlap_h, overlap_start, overlap_end, duration_ratio (min/max), duration_delta_h, cross_flag (both flags present and differ), same_flag, flag_missing, cell (A's), cell_month (A's), dateline (either event or bbox), shore_off_km (mean), shore_on_km (mean), length_a, tonnage_a, length_b, tonnage_b`.

Writes `candidates_t0.parquet` and `pair_grid_counts.json` (ladder counts, loose count, per-cell-month observed counts).

Acceptance (*verified*): 434 pairs; 26 cross-flag; showcase present with `start_km 6.60, start_delta_min 0.083, end_km 8.99, end_delta_min 0.717, overlap_h 41.76, duration_ratio 0.9997`; ladder = start-only 50 km/24 h 101,901 · start-only 5 km/1 h 1,230 · both 25 km/3 h 5,630 · both 10 km/1 h 434 · both 5 km/1 h 103 · both 2 km/30 min 3; loose 18,775; brute-force check passes.

### S4 `context.py` — confounders (1.5 h)

```python
def local_context(ev, cands) -> pd.DataFrame     # per pair_id
def components(cands) -> pd.DataFrame            # component_id, component_size, component_class
def identity_flags(ev, cands) -> pd.DataFrame    # sequential_mmsi, identity_twin, identity_status
def vessel_history(ev, cands) -> pd.DataFrame    # gap_unusualness_a/b, repeat_rate_a/b, prior_pair_count
```

Definitions (own two events always excluded):
- Neighbour set at shutoff: events with `|t0 − t0_a| ≤ 1 h` and `haversine(p0_a, p0) ≤ 200 km`; at reappearance: same with `t1`, `p1`. `local_dark_count_off`, `local_dark_count_on`, `local_dark_count = |union|`, `local_unique_vessels = |unique MMSI in union|`.
- `neighbours[]`: up to 8 nearest at shutoff: `mmsi, flag, deltaMin (signed, relative to A), distanceKm`.
- `local_same_flag_share`: share of unique neighbouring vessels whose flag equals `flag_a` or `flag_b`; **null when `local_unique_vessels < 3`**.
- `local_sequential_share`: share of neighbours sequential to either vessel.
- Components: union-find over operating pairs (edges). `component_size` = events in the component. `component_class`: `bilateral` if size 2; else `fleet_cluster` if (same-flag share within the component ≥ 0.8 or sequential share ≥ 0.5); else `regional_blackout` if size ≥ 5 or `local_dark_count ≥ 20`; else `unresolved`.
- `sequential_mmsi`: same MID and `|mmsi_a − mmsi_b| ≤ 10`. `identity_twin`: same class, same flag, `|Δlength| < 0.5 m`, `|Δtonnage| < 1 GT`. `identity_status`: `resolved` if both MMSIs valid and not twin; `identity-twin` if twin; `unresolved` if either invalid or flag missing.
- `gap_unusualness_v` = fraction of the vessel's other gaps shorter than this one (null if `n_gaps_vessel < 3`); pair-level `gap_unusualness = mean` of the two non-null values (null if both null). `repeat_rate_v` = operating pairs containing the vessel / its gap count. `prior_pair_count` = operating pairs of the same MMSI pair with earlier `t0`.

Acceptance (*verified*): 295 components of size > 1 with size distribution {2: 237, 3: 44, 4: 9, 5: 3, 6: 1, 14: 1}; 237 pairs bilateral; 55 pairs in components ≥ 5; local_dark_count median 3, p90 25, 37 pairs with zero; 181 identity twins; 173 sequential; showcase: component size 2, one neighbour (`412329634`, CHN, +1.4 min, 9.7 km at shutoff; +28.9 min, 25.3 km at reappearance), `gap_unusualness_a 0.54, _b 0.70`, both vessels in exactly one pair. Runtime ≈ 1 s.

### S5 `nulls.py` — within-cell permutation null (1 h to write; ~6 min to run)

```python
def permute_within_cell(ev: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame  # shuffles t0 among events in the same 5° cell, keeps durations and positions, t1 = t0 + duration
def run_null(ev, cands, draws=200, ladder_draws=20, seed=SEED) -> dict
def p_cell(cands: pd.DataFrame, null: dict) -> pd.Series
```

Per draw: rerun `pair_events` with the operating rule; record the total and the count per `cell_month` (of the A event). Ladder rungs and the loose rule use `ladder_draws` draws. `null_results.json`:

```json
{"name": "within-cell permutation v1", "cell_deg": 5, "draws": 200, "seed": 20260905,
 "observed": 434, "null_mean": 12.0, "null_sd": 2.4, "lift": 36.2, "per_draw": [11, 17, ...],
 "ladder": {"both ends 10 km / 1 h": {"observed": 434, "null_mean": 12.0, "lift": 36.2}, ...},
 "cell_month_null_counts": {"6826-2017-07": [0, 0, 1, ...]}, "observed_cell_month_counts": {"6826-2017-07": 1}}
```

`p_cell = (1 + k) / (1 + N)` where `k` = draws whose count in the candidate's cell-month ≥ the observed count there; minimum 1/201 = 0.00498. Assertions: `null_mean > 0`; `abs(lift − 1.0) > 0.01` (a lift of exactly 1.00× is a broken null, build-plan §3.5); every candidate gets a p_cell.

Acceptance (*verified with 10–50 draws*): null mean ≈ 12, lift ≈ 36×; showcase cell-month `6826-2017-07` observed 1, zero null hits in 50 draws → p_cell = 1/51 with 50 draws, expected 1/201 with 200. Runtime 1.1 s per draw.

`--draws 20` for the first end-to-end run; rerun with 200 in the background and re-export.

### S6 `features.py` + `score.py` — features, terms, score, labels (1.5 h)

`features.parquet`: one row per `pair_id` joining S3, S2, S4, S5, S0/S1′ and, when present, Andrew's event pulls. Columns grouped as in build-plan §5:

| family | columns |
|---|---|
| geometry | `start_km, start_delta_min, end_km, end_delta_min, overlap_h, duration_ratio, p_cell` |
| kinematics | `lon_star, lat_star, tau_h, required_speed_kn, kin_plausibility, dateline` |
| behaviour (null until D3–D5) | `loiter_bracket, encounter_bracket, known_partners, port_after_gap_risk, fishing_ground_context, role_pair` |
| context | `cross_flag, flag_card_a, flag_card_b, rfmo_area, rfmo_authorized_a/b (null until D7), iuu_listed_a/b (null until list), port_risk (null until PSMA), zone ("high_seas" / "eez:<name>" / "unknown"), eez_entry_while_dark (bool or null)` |
| risk-port reach | `risk_port_reach_hours, possible_port_transit` (null without port distances; with API `port_on_km ≤ 50` → `possible_port_transit = True`) |
| corroboration | `viirs_state, viirs_uncorrelated_count, viirs_min_km_to_p_star` |
| confounders | `local_dark_count, local_unique_vessels, local_same_flag_share, local_sequential_share, component_size, component_class, sequential_mmsi, identity_twin, identity_status, gap_unusualness, repeat_rate_a/b, prior_pair_count` |

Behaviour definitions for when D3–D5 arrive: `loiter_bracket` = any LOITERING event of either vessel intersecting `[t0 − 24 h, t1 + 24 h]` within 100 km of p*; `encounter_bracket` same for ENCOUNTER; `known_partners` = count of prior ENCOUNTER events between the two vessels; `port_after_gap_risk` = 1 if the first PORT_VISIT of either vessel within 7 days after `t1` is in a carded or non-PSMA state, else 0.

Terms, each in [0, 1], null when inputs are missing (`score.py`):

```python
S_geom = clip(-log10(p_cell), 0, 2) / 2
S_beh  = 0.5*bracket + 0.3*(role_pair == "fishing-carrier") + 0.2*port_after_gap_risk   # null if all inputs null
S_ctx  = 0.3*cross_flag + 0.3*(flag_card_any in {yellow, red}) + 0.2*not_authorized_any + 0.1*iuu_listed_any + 0.1*port_risk   # null sub-terms contribute 0; ctx is null only if every sub-term is null
S_cor  = 1.0 if viirs_state == "uncorrelated_detection" else 0.0   # clear_no_detection and no_coverage score 0 and are explained
S_kin  = kin_plausibility     # weight applied only for loose or T1 candidates; 0 weight for operating T0 (rolePair unchanged)
S_den  = clip(log10(1 + local_dark_count) / 2, 0, 1)
S_flt  = max(component_class == "fleet_cluster", sequential_mmsi, identity_twin, (local_same_flag_share or 0) > 0.8)
S_hab  = 1 - gap_unusualness  # null if gap_unusualness null
raw    = 0.30*S_geom + 0.15*S_kin*is_loose + 0.20*S_beh + 0.15*S_ctx + 0.20*S_cor - 0.15*S_den - 0.20*S_flt - 0.10*S_hab
priority = 1 / (1 + exp(-6 * (raw - 0.30)))
riskScore = round(100 * priority)
```

Null terms contribute 0 to `raw` and are reported as `null` in `scores`; `explanations[]` gets one sentence per null term naming the missing input ("Behaviour term not available: GFW loitering/encounter events not pulled for these vessels").

Label, evaluated in this order, first match wins:
1. `insufficient-evidence` — `identity_status == "unresolved"` or any of `p_cell, start_km, end_km, overlap_h` missing.
2. `identity-twin` — `identity_twin or sequential_mmsi`.
3. `coordinated-fleet-pattern` — `S_flt` is the largest penalty term and ≥ 0.5.
4. `likely-coverage-or-cluster-artifact` — `S_den` is the largest penalty term and ≥ 0.5, or `component_class == "regional_blackout"`.
5. `possible-port-transit` — `possible_port_transit is True`.
6. `investigate` — `priority ≥ 0.5` and `component_class == "bilateral"` and no penalty term > 0.5.
7. `insufficient-evidence` — otherwise (bilateral but weak; the explanation says "no corroboration and weak geometry").

`riskLevel`: investigate → `high`; coordinated-fleet-pattern, identity-twin, possible-port-transit → `review`; likely-coverage-or-cluster-artifact, insufficient-evidence → `watch`.

Evidence tier (monotone): `imagery_corroborated` if `S_cor == 1`; else `behaviour_corroborated` if `loiter_bracket or encounter_bracket`; else `bilateral_rendezvous_plausible` if label is `investigate`; else `coordinated_fleet_activity` if label in {identity-twin, coordinated-fleet-pattern}; else `coincidence_or_artifact`.

Worked showcase values with today's inputs (no API pulls, no VIIRS): `S_geom 1.0` (p_cell 1/201), `S_kin` unweighted, `S_beh null`, `S_ctx 0.6` (cross-flag, TWN yellow card), `S_cor 0`, `S_den 0.15` (one neighbour), `S_flt 0` (bilateral, different MID, not twin, same-flag share null with one neighbour), `S_hab 0.38` (unusualness mean 0.62) → `raw 0.329`, `priority 0.54`, `riskScore 54`, label `investigate`, tier `bilateral_rendezvous_plausible`. With an uncorrelated VIIRS light: `raw 0.529`, `priority 0.80`.

Acceptance: all priorities in [0, 1]; no `identity-twin` pair labelled `investigate`; label histogram printed to `summary.md`; showcase within ±0.02 of the values above once the 200-draw null is in.

### S7 `corroborate.py` — VIIRS (Andrew, 90-minute box; Tanner 0.5 h for the join)

```python
def viirs_state(cand_row, detections: pd.DataFrame | None, ring_a, ring_b, ev) -> dict
# → {"viirsState": "no_coverage" | "clear_no_detection" | "correlated_only" | "uncorrelated_detection",
#    "viirsUncorrelatedCount": int, "viirsMinKmToMeetingPoint": float | None, "viirsDetections": [{lon, lat, time, radiance, quality}],
#    "presenceSource": "corpus_endpoints" | "gfw_presence_grid_center_hourly"}
```

Default (no detections file): every candidate gets `no_coverage` and the UI says so. If Andrew obtains an EOG VIIRS Boat Detection nightly CSV for 2017-07-02 and 2017-07-03 covering 41–44°N, 160–164°E (free account at eogdata.mines.edu; confirm the product actually covers that box before spending more than 30 minutes; expected columns include `Lat_DNB, Lon_DNB, Date_Mscan, Rad_DNB, QF_Detect`; treat `QF_Detect == 1` as a strong detection): keep detections whose timestamp falls inside `[overlap_start, overlap_end]` and whose point lies inside the intersection of the two rings (point-in-polygon by ray casting on the 64-point rings in the local frame); a detection is *correlated* if any corpus broadcasting endpoint (any event's `p0` within ±1 h of its `t0`, or `p1` within ±1 h of its `t1`) lies within 5 km; the state is `uncorrelated_detection` if any uncorrelated detection remains, `correlated_only` if all are correlated, `clear_no_detection` if the file covers the box and window but holds no detection inside the rings. For squid jiggers the UI wording for `clear_no_detection` is "lights off during the window", never "absent".

Correlation source: by default the corpus endpoints above (`presenceSource: "corpus_endpoints"`). If Andrew's `gfw-presence` report for the showcase window lands (§1 D12), a detection is also *correlated* when a presence grid-cell centre (0.01°, ≈ 1.1 km) for the same hour lies within 5 km, and the record says `presenceSource: "gfw_presence_grid_center_hourly"`. Presence rows are grid-cell centres, never exact fixes; `methods.json` says so.

Fallback if the product does not cover the box: `no_coverage`, and the pitch says so.

### S8 `export.py` — the contract (1.5 h)

```python
def build_record(pair_id: str, f: pd.Series, ctx: dict, feas: dict, corr: dict, null_meta: dict) -> dict
def build_track(record: dict, feas: dict) -> dict          # GeoJSON FeatureCollection
def write_outputs(records: list[dict], out_dir: Path = FRONTEND_PUBLIC / "data") -> None
def write_methods(null: dict, ladder: dict, config: dict, sources: list[dict]) -> None
def write_evidence_ledger(records) -> None                  # evidence_ledger.parquet: one row per claim
def write_summary(records, null) -> None                    # summary.md with the judge-facing numbers
```

Sort order of `risk-events.json`: evidence tier (imagery > behaviour > bilateral > fleet > artifact), then `priority` desc, then `pair_id`. Full record schema is in §6. `methods.json` carries thresholds, the ladder with null means and lifts, the null definition, class speeds, weights, label rules, sources (GFW corpus, Skylight thresholds, GFW encounter rule, Oxford A.1/A.2, WCPFC 78%), the attribution string, and the label histogram. `summary.md` prints every number in §10.

Size budget: records without tracks ≈ 1.5 MB; with embedded tracks (two 64-point rings + 4 points + 2 lines each) ≈ 4 MB total; `tracks/` files ≈ 8 KB each. All under `code/frontend/public/data/` and committed.

Acceptance: `json.load` round-trips; 434 records; every record validates against §6 (a 40-line `validate_record()` in `export.py`); the showcase record's `evidence[]` and `timeline[]` match the worked example; `attribution` present on every record; no coordinate outside [−180, 180]/[−90, 90]; no `NaN` in the file (write `null`).

### S9 `narrate.py` + `verify.py` — narration and span verification (2–3 h)

Principle: the narrator sees one record and must cite a ledger path for every fact; the verifier sees only the segments and the untouched record. Their independence is the agent-trust story.

**Install and auth:** `pip install anthropic` (1.x, built on `httpx2`); `export ANTHROPIC_API_KEY=…` (or `ant auth login`; the zero-arg client picks up either). Model `claude-opus-5`; thinking is adaptive by default; set `output_config={"effort": "low", "format": {...}}`; `max_tokens=2000`; never pass `temperature` or `budget_tokens` (rejected on Opus 5). Cost ≈ $0.03 per call, ≈ $1 for 20 precomputed + 3 adversarial + a dozen dev runs.

```python
# narrate.py
SEGMENT_SCHEMA = {"type": "object", "additionalProperties": False,
  "required": ["segments", "recommendation", "caveat"],
  "properties": {
    "segments": {"type": "array", "items": {"type": "object", "additionalProperties": False,
       "required": ["kind", "text", "claimKey", "value", "unit", "estimated", "nullName"],
       "properties": {"kind": {"type": "string", "enum": ["text", "claim"]},
                      "text": {"type": "string"}, "claimKey": {"type": "string"},
                      "value": {"type": "string"}, "unit": {"type": "string"},
                      "estimated": {"type": "boolean"}, "nullName": {"type": "string"}}}},
    "recommendation": {"type": "string", "enum": ["investigate", "review", "dismiss"]},
    "caveat": {"type": "string"}}}

def flatten(record: dict) -> dict[str, object]           # dotted paths: "features.startDeltaMin", "vessels.1.flag", "neighbours.0.distanceKm"
def allowed_keys(record: dict) -> list[tuple[str, str, str]]   # (path, type, unit) from a suffix table: *Km→km, *Min→min, *Hours→h, *Kn→kn, pCell→probability, priority/scores.*→score
def narrate(record: dict, client: anthropic.Anthropic, model="claude-opus-5") -> dict
    # system: role (assistant to a fisheries-compliance analyst), ~120 words, never asserts a transfer or crime,
    # rules: every number/identifier/timestamp/flag/class/zone/score/count/statistical statement is its own "claim" segment
    #        with claimKey from ALLOWED KEYS; plain prose segments contain no digits; length/tonnage claims set estimated=true
    #        and say "estimated"; any claim about pCell/lift/S_geom sets nullName = record.nullModel.name; unknown facts → claimKey "unsourced".
    # user: "RECORD:\n<json without sources/attribution/analystDisposition>\n\nALLOWED KEYS (path : type : unit):\n<list>"
    # call: client.messages.create(model=model, max_tokens=2000, system=SYSTEM, messages=[...],
    #        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SEGMENT_SCHEMA}})
    # parse: json.loads(next(b.text for b in response.content if b.type == "text")); check response.stop_reason == "end_turn"
```

```python
# verify.py  (no LLM, no NLP beyond a digit regex)
TOLERANCES = {"km": 1.0, "m": 1000.0, "h": 0.017, "min": 1.0, "kn": 0.1, "probability": 0.0005, "score": 0.01, "count": 0, "id": 0, "iso8601": 60.0 /*seconds*/}
def verify(segments: list[dict], record: dict) -> list[dict]
    # for each claim segment: look up flatten(record)[claimKey]; missing key or "unsourced" → "unverifiable";
    # numeric: parse value, normalise unit (m→km, s→min…), compare within tolerance → "verified" | "contradicted";
    # strings/ids/timestamps: exact (timestamps within 60 s); length/tonnage without estimated=true → "contradicted" (badge rule);
    # statistical claim (claimKey startswith "features.pCell" or "scores.geom" or "nullModel") without nullName == record.nullModel.name → "unverifiable";
    # any "text" segment containing a digit → "unverifiable" (untagged number).
def adversarial(record: dict, rng) -> tuple[dict, list[str]]
    # corrupt 2–3 fields in a COPY of the record given to the narrator (e.g. features.startDistanceKm × 3, window.overlapHours + 10, swap vessels[1].flag),
    # re-narrate, verify against the ORIGINAL record → the perturbed spans render "contradicted". Returns the corrupted record and the list of corrupted keys.
```

`narratives.json` (separate static file, keyed by candidate id; the frontend joins client-side):

```json
{"t0-3f9a1c2b7d4e": {
   "model": "claude-opus-5", "promptVersion": "v1", "generatedAt": "2026-09-05T23:10:00Z",
   "recommendation": "investigate", "caveat": "AIS absence does not establish a transfer; the meeting point is inferred.",
   "segments": [{"kind": "text", "text": "Both vessels ceased AIS "}, {"kind": "claim", "text": "5 s apart", "claimKey": "features.startDeltaMin", "value": "0.083", "unit": "min", "estimated": false, "nullName": "", "status": "verified"}, ...],
   "verifierSummary": {"verified": 11, "contradicted": 0, "unverifiable": 1},
   "adversarial": {"corruptedKeys": ["features.startDistanceKm", "window.overlapHours"], "segments": [...], "verifierSummary": {"verified": 9, "contradicted": 2, "unverifiable": 1}}}}
```

Precompute the top 20 by priority plus every `investigate` candidate; run adversarial for the showcase pair and two others. Live button: `serve.py` exposes `POST /narrate {"id": "...", "adversarial": false}` and returns the same shape (40 lines of FastAPI or `http.server`). If the key or network is missing at demo time, the UI shows the precomputed run and labels it "replay".

Unit tests (`test_pipeline_verify.py`): a hand-written segment list against the showcase record yields all `verified`; changing one value by more than tolerance yields `contradicted`; a missing `nullName` on a `pCell` claim yields `unverifiable`; an untagged digit in a text segment yields `unverifiable`.

### S1′′ Andrew's API pulls (for D3–D5, D7) — extension of `src/dark_rendezvous/providers/gfw.py`

`GfwClient.gap_events` hard-codes `datasets=[gaps_dataset]` and `types=["GAP"]`. Add one general method and reuse `pull_gap_windows`' page/manifest pattern:

```python
def events(self, *, datasets: list[str], types: list[str], start_date: str, end_date: str,
           vessels: list[str] | None = None, offset: int = 0, limit: int = 500,
           time_filter_mode: str = "START-DATE", **extra) -> dict[str, Any]
# datasets: "public-global-encounters-events:latest", "public-global-loitering-events:latest",
#           "public-global-port-visits-events:latest", "public-global-fishing-events:latest"  (verify names in the v3 docs while the token is live)
# body: {"datasets": [...], "types": [...], "startDate": ..., "endDate": ..., "timeFilterMode": ..., "vessels": [gfw vessel ids]}
```

What the 16:31 merge delivered (ec33b4c): `gfw-gaps-pull --bronze-only` and `--all-gaps`; `gfw-presence` (4Wings hourly presence by region id, `--reuse-last-report` after a timeout); `gfw-track` (implemented; the token has no tracks permission → 404); `scripts/run_gfw_bronze_backfill.ps1` (year-by-year bronze loop, Windows, `.venv313`); `position_semantics` on every canonical row; `docs/bronze-backfill-runbook.md`. **Not delivered:** the general `events()` method above, identity pulls (no `data/bronze/gfw_identity/`), ENCOUNTER / LOITERING / PORT_VISIT pulls, relaxed `pyproject` pins, 2017–2019 bronze beyond January 2017.

Order of work with the token (everything cached as bronze JSON + one parquet each): (0) **commit the 2017–2019 GAP bronze** (probably already on disk from the 19:35 Z backfill; otherwise `run_gfw_bronze_backfill.ps1 -StartDate 2017-01-01 -EndDate 2020-01-01`, ≈ 10 min) and let the 2022+ loop run on in the background, it is not needed for the demo; (1) `enrich_api.py` → `gfw_gap_enrichment.parquet` (Tanner runs it once the bronze is in the repo; no token needed); (2) identity search for the 212 queue MMSIs → `gfw_vessel_id`, names, registry authorizations (`data/reference/vessel_identity.parquet`); (3) ENCOUNTER, LOITERING, PORT_VISIT for those vessel ids, 2017-01-01 → 2019-12-31 (`data/reference/gfw_events_queue.parquet` with `event_type, vessel_id, mmsi, start, end, lat, lon, partner_vessel_id, median_distance_km, median_speed_kn, port_name, port_country`); (4) optional FISHING events; (5) optional presence report for the showcase window (§4 S7). Mark in `methods.json` which of these landed. Attribution and the CC BY-NC 4.0 notice go into every record and into `methods.json`.

Repo hygiene: the merge added 834 MB of bronze JSON (2,080 files, ≈ 120 MB packed) under `data/bronze/gfw_gaps/`, against the earlier "commit only the enrichment parquet" rule, and `docs/ais-ingestion.md` still says `data/` is git-ignored (only `data/raw/*.csv` and `data/derived/*.parquet` are). Do not rewrite shared history. Going forward: commit the 2017–2019 bronze once, keep 2020+ bronze local, and correct the doc line.

---

## 5. Stage order, first end-to-end, and what each pass adds

| Pass | Stages | Adds | Target |
|---|---|---|---|
| P0 fixture | hand-edit the §6 showcase record ×3 (showcase, a fleet pair, an artifact pair) | frontend can build the pair header, score bars and track layers | Sat 17:45 |
| P1 first real file | S1, S3, S2, S4, S5 (20 draws), S6, S8 | all 434 records, geometry, context, labels; behaviour/identity null | Sat 20:30 |
| P2 null and narration | S5 (200 draws), S9 top 20 + adversarial | final p_cell, `narratives.json` | Sat 22:00 |
| P3 enrichment | S1′, S0, S6 rerun, S8 rerun | jurisdiction, RFMO, carding, names, behaviour terms if events landed | Sat 23:30 |
| P4 corroboration | S7 | showcase VIIRS state (or an honest `no_coverage`) | Sun 08:30 |
| Freeze | tests, `summary.md`, README | | Sun 09:30 |

---

## 6. Output contract

### 6.1 `risk-events.json` record

Every field the UI renders today is kept (`id, name, imo, flag, vesselType, riskScore, riskLevel, eventKind, eventLabel, location, lastSeen, coordinates, evidence[], timeline[]`); everything else is additive. Real values for the showcase pair with today's inputs:

```json
{
  "id": "t0-<sha1 12>",
  "tier": "paired-dark",
  "label": "investigate",
  "evidenceTier": "bilateral_rendezvous_plausible",
  "priority": 0.54,
  "riskScore": 54,
  "riskLevel": "high",
  "eventKind": "dark-period",
  "eventLabel": "Paired AIS dark period",
  "name": "412331147 (CHN) × 416004105 (TWN)",
  "imo": "MMSI 412331147 × 416004105",
  "flag": "CHN / TWN",
  "vesselType": "squid jigger / squid jigger",
  "location": "NW Pacific high seas, 892 km from shore",
  "lastSeen": "2017-07-03T12:19:32Z",
  "coordinates": [161.958, 42.752],
  "vessels": [
    {"mmsi": "412331147", "imo": null, "name": null, "flag": "CHN", "vesselClass": "squid_jigger", "role": "fishing",
     "identityStatus": "resolved", "flagCard": "none", "rfmoAuthorized": null, "iuuListed": null,
     "lengthM": 69.9, "tonnageGt": 1408.0, "lengthEstimated": true, "tonnageEstimated": true, "gapsInCorpus": 63, "pairsInQueue": 1},
    {"mmsi": "416004105", "imo": null, "name": null, "flag": "TWN", "vesselClass": "squid_jigger", "role": "fishing",
     "identityStatus": "resolved", "flagCard": "yellow", "rfmoAuthorized": null, "iuuListed": null,
     "lengthM": 72.8, "tonnageGt": 962.0, "lengthEstimated": true, "tonnageEstimated": true, "gapsInCorpus": 46, "pairsInQueue": 1}
  ],
  "window": {"start": "2017-07-01T18:33:00Z", "end": "2017-07-03T12:19:32Z",
             "overlapStart": "2017-07-01T18:33:05Z", "overlapEnd": "2017-07-03T12:18:49Z", "overlapHours": 41.76},
  "meetingPoint": {"coordinates": [161.958, 42.752], "kind": "inferred", "method": "argmax joint dwell, 15×15 grid + refinement"},
  "jurisdiction": {"zone": "high_seas", "eez": null, "rfmo": null, "eezEntryWhileDark": null, "shoreDistanceKm": 892.0, "portDistanceKm": null},
  "scores": {"geom": 1.0, "kin": null, "beh": null, "ctx": 0.6, "cor": 0.0, "den": 0.15, "flt": 0.0, "hab": 0.38, "raw": 0.329},
  "features": {"startDistanceKm": 6.6, "startDeltaMin": 0.083, "endDistanceKm": 8.99, "endDeltaMin": 0.717,
               "durationRatio": 0.9997, "requiredSpeedKn": 0.92, "jointDwellHours": 38.6, "kinPlausibility": 0.95,
               "pCell": 0.005, "localDarkCount": 1, "localUniqueVessels": 1, "localSameFlagShare": null,
               "componentSize": 2, "componentClass": "bilateral", "sequentialMmsi": false, "identityTwin": false,
               "crossFlag": true, "gapUnusualness": 0.62, "knownPartners": null, "loiterBracket": null, "encounterBracket": null,
               "portAfterGapRisk": null, "possiblePortTransit": null},
  "corroboration": {"viirsState": "no_coverage", "viirsUncorrelatedCount": 0, "viirsMinKmToMeetingPoint": null, "viirsDetections": [], "presenceSource": "corpus_endpoints"},
  "nullModel": {"name": "within-cell permutation v1", "draws": 200, "cellDeg": 5, "observed": 434, "nullMean": 12.0, "lift": 36.2},
  "neighbours": [{"mmsi": "412329634", "flag": "CHN", "deltaMin": 1.4, "distanceKm": 9.7}],
  "explanations": [
    "Both shutoffs 5 s and 6.6 km apart; both reappearances 43 s and 9.0 km apart after 41.8 h.",
    "Within-cell permutation null (200 draws) produced no pair in this cell-month: p_cell = 0.005.",
    "Cross-flag pair; Taiwan held an EU IUU yellow card on this date.",
    "One other vessel went dark within 200 km and ±1 h (412329634, CHN).",
    "Behaviour term not available: GFW loitering, encounter and port-visit events not pulled for these vessels.",
    "Imagery: no VIIRS coverage checked for this window."
  ],
  "evidence": [
    {"id": "sync-off", "claim": "Both vessels ceased AIS 5 s apart, 6.6 km apart", "source": "GFW disabling corpus", "observedAt": "2017-07-01T18:33:05Z", "confidence": "high"},
    {"id": "sync-on", "claim": "Both reappeared 43 s apart, 9.0 km apart, after 41.8 h", "source": "GFW disabling corpus", "observedAt": "2017-07-03T12:19:32Z", "confidence": "high"},
    {"id": "null", "claim": "Within-cell permutation null, 200 draws: p_cell = 0.005", "source": "GapPair null model v1", "observedAt": "2017-07-01T18:33:00Z", "confidence": "medium"},
    {"id": "card", "claim": "Taiwan held an EU IUU yellow card on this date (2015-10-01 to 2019-06-27)", "source": "EU carding history (hand-made table)", "observedAt": "2017-07-01T18:33:00Z", "confidence": "high"},
    {"id": "density", "claim": "1 other vessel dark within 200 km and ±1 h", "source": "GapPair local context", "observedAt": "2017-07-01T18:33:00Z", "confidence": "high"},
    {"id": "geometry", "claim": "Feasible meeting point 161.96E 42.75N; joint dwell 38.6 h; required speed 0.9 kn", "source": "Reachable-set heuristic (estimated)", "observedAt": "2017-07-02T15:00:00Z", "confidence": "low"}
  ],
  "timeline": [
    {"time": "2017-07-01T18:33:00Z", "title": "412331147 last AIS position", "detail": "42.749N 161.983E"},
    {"time": "2017-07-01T18:33:05Z", "title": "416004105 last AIS position", "detail": "42.795N 162.034E", "emphasis": true},
    {"time": "2017-07-03T12:18:49Z", "title": "416004105 reappears", "detail": "42.340N 161.423E"},
    {"time": "2017-07-03T12:19:32Z", "title": "412331147 reappears", "detail": "42.399N 161.347E"}
  ],
  "track": {"type": "FeatureCollection", "features": ["… see 6.2 …"]},
  "sources": [{"claim": "window.start", "value": "2017-07-01T18:33:00Z", "source": "GFW disabling corpus", "asOf": "2022-08-08"}],
  "attribution": "Data: Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0",
  "analystDisposition": null
}
```

Field rules: `name` uses GFW vessel names when the enrichment parquet has them (`"LURONGYUANYU202 (CHN) × …"`), else MMSIs. `location` is built as `"{zone or 'unknown waters'}{', ' + rfmo + ' area' if rfmo}, {shore} km from shore"`. `coordinates` = meeting point, or the centroid of the four endpoints when `dateline` is true. `lastSeen` = later reappearance. Numbers rounded: km 2 dp, minutes 3 dp, hours 2 dp, probabilities 4 dp, scores 2 dp. Nulls are JSON `null`, never `0` or `"n/a"`.

### 6.2 `track` / `tracks/<id>.geojson`

FeatureCollection with, in order: four `Point` features (`{"vessel": "A"|"B", "role": "off"|"on", "observationStatus": "observed", "time": iso, "mmsi": ...}`), two dashed `LineString` projections per vessel (`p0 → p* → p1`, `{"vessel", "observationStatus": "estimated", "confidence": "low", "source": "reachable-set heuristic"}`), the meeting `Point` (`{"observationStatus": "estimated", "kind": "meetingPoint"}`), and two `Polygon` rings (`{"vessel", "observationStatus": "estimated", "kind": "reachableSet"}`), omitted when `dateline` is true (then `properties.dateline: true` on the collection). Matches the rule in `code/backend/README.md`: estimated geometry is never presented as an observed AIS position.

### 6.3 `methods.json`, `narratives.json`, `evidence_ledger.parquet`

`methods.json` keys: `corpus {events, vessels, flags, years, source, license}`, `operatingRule`, `ladder[] {rung, observed, nullMean, lift, draws}`, `loose {observed, feasibleAtTauMin}`, `null {name, cellDeg, draws, seed, observed, nullMean, nullSd, lift}`, `classSpeedsKn`, `weights`, `labelRules[]`, `labelHistogram`, `componentHistogram`, `counts {crossFlag, sequentialMmsi, identityTwin, bilateral, zeroNeighbour}`, `caveats[]` (WCPFC 78 %, retrospective, fishing only, inferred meeting point, kinematics unscored), `sources[]`, `attribution`, `generatedAt`. `narratives.json` as in §4.9. `evidence_ledger.parquet`: `pair_id, claim_id, claim_key, value, unit, source, retrieved_at, tolerance`.

### 6.4 Frontend changes the UI owner must make (so the demo looks good)

1. `provider.ts`: add a `static` mode that fetches `/data/risk-events.json` (and `/data/narratives.json`, `/data/methods.json`); default to it. Keep `mock` as the fallback.
2. `types.ts`: extend `Vessel` with the additive fields (`vessels[]`, `window`, `meetingPoint`, `scores`, `features`, `corroboration`, `nullModel`, `neighbours`, `explanations`, `track`, `attribution`). Nothing existing changes type.
3. Header: pair name, both flags, both classes, `riskScore` badge, `label` chip, `evidenceTier` text.
4. Score bars: one bar per term in `scores` (`geom, kin, beh, ctx, cor` positive; `den, flt, hab` drawn negative); null → "not available" with the matching sentence from `explanations[]`.
5. Map: `origin/main` is already merged into `Tanner-dev` (dd7e94e). Its `MapPanel` takes no props and draws only the offline `land` source, and `App.tsx` no longer passes `vessels`, `selected` or `onSelectVessel`. Restore those three props and the queue's point layer from `coordinates` above the coastlines, then on select draw `track`: filled dots for observed endpoints (vessel A red, vessel B blue), dashed lines for projections, hollow red square for the meeting point, semi-transparent ring polygons; grey dots for `neighbours[]`; fit bounds to the four endpoints.
6. Neighbours list, "gaps in corpus" counts, timeline (format ISO to `DD MMM · HH:mm`), evidence with confidence chips.
7. Assessment panel: render `narratives[id].segments` with `status` badges (verified green, contradicted red, unverifiable grey); buttons "Run live" (POST to `serve.py`, falls back to replay) and "Adversarial replay".
8. Methods drawer from `methods.json` (ladder table, null definition, caveats, sources) and the attribution line on every screen (CC BY-NC 4.0 requires it).
9. Thumbs up/down writes `analystDisposition` into local state (no backend write needed for the demo).

---

## 7. Static serving

Outputs are committed under `code/frontend/public/data/` so `vite dev` and `vite build` both serve them at `/data/...` with no server. Regenerate with `python -m pipeline.run --stage export` and commit. Budget: `risk-events.json` ≤ 5 MB, `narratives.json` ≤ 200 KB, `methods.json` ≤ 50 KB, `tracks/` ≤ 4 MB. Offline behaviour: the app works with no network at all once built; only the optional narration button needs `serve.py` and a key, and it degrades to replay.

---

## 8. Schedule (Sat 17:00 → Sun 10:00)

| Time | Tanner (pipeline) | Andrew (data, API, references) | Frontend owner |
|---|---|---|---|
| 17:00–17:30 | `pip install anthropic`; `pipeline/` skeleton, `config.py`, `geo.py` + tests | **Commit the 2017–2019 GAP bronze** (rerun the backfill for those years if it is not on disk); relax `pyproject` pins and move the `shapely` import; start `enrich_api.py` | `origin/main` is merged; read §6; restore the `MapPanel` props (§6.4.5) |
| 17:30–17:45 | Write the P0 fixture (three hand-edited records) into `public/data/risk-events.json` | | Build against the fixture |
| 17:45–18:45 | S1 `load.py`, S3 `pair_t0.py`, ladder, brute-force check; **send the 212 queue MMSIs to Andrew** | `enrich_api.py` → `gfw_gap_enrichment.parquet`; `eu_iuu_cards.csv` (Appendix A) | Pair header, score bars |
| 18:45–19:45 | S2 `feasibility.py` (+ ring tests), S4 `context.py` | Identity search for the 212 MMSIs → `vessel_identity.parquet`; EOG account + coverage check (30-min cap) | Track layers |
| 19:45–20:30 | S5 (20 draws), S6 features + score, S8 export → **P1 file to frontend 20:30** | ENCOUNTER / LOITERING / PORT_VISIT pulls for the 212 vessel ids | Swap fixture for P1 |
| 20:30–21:00 | Start the 200-draw null in the background; `validate_record`, `summary.md` | Finish event pulls → `gfw_events_queue.parquet` | Neighbours, timeline, evidence |
| 21:00–22:30 | S9 `narrate.py` + `verify.py`; precompute top 20 + 3 adversarial → `narratives.json` | Join enrichment + identity + events into S6 inputs (jurisdiction, names, behaviour terms); PSMA table if time | Assessment panel with badges |
| 22:30–23:30 | Re-export with the 200-draw null and Andrew's joins → **P3 file 23:30**; `methods.json` | VIIRS download for the showcase nights if covered (then one `gfw-presence` report for the showcase window, §4 S7); otherwise write `no_coverage` rationale into `methods.json` | Methods drawer, attribution |
| 23:30–00:30 | Tests green; README run instructions; buffer | S7 join if data landed | Polish |
| 00:30–07:00 | sleep | sleep | sleep |
| 07:00–08:30 | Final numbers into `summary.md`; rehearse the adversarial run; record a fallback video of it | Verify the carding table sources; fishing–carrier stretch if the pull has carriers | Final layout pass |
| 08:30–09:30 | Freeze outputs; commit; tag `demo-freeze` | | Build `vite build`; test offline |
| 09:30–10:00 | Submission text from `summary.md` | | |

Critical path: S1 → S3 → S4/S2 → S6 → S8 (Tanner, ~3.5 h). Andrew's lane is independent until the 23:30 re-export; nothing in Tanner's lane waits on the token.

---

## 9. Cut list and demo-day checklist

Drop in this order if behind: (1) VIIRS (`no_coverage` is honest and already wired); (2) GFW behaviour events (`S_beh` null); (3) identity/authorizations (`rfmoAuthorized` null); (4) live narration button (replay only); (5) null draws 200 → 50 (p_cell floor becomes 1/51, say so in `methods.json`); (6) per-file `tracks/` (embedded `track` suffices); (7) `evidence_ledger.parquet` (the `evidence[]` arrays remain). Never drop: the operating pairs, the null lift, components and identity flags, the showcase record, the attribution.

Demo-day checklist (run at 12:30 and again at 15:30): `vite build` output opens from disk with wifi off; queue shows 434 with the label filter; showcase pair opens with rings and meeting point; score bars show two nulls with explanations; narration badges render from `narratives.json`; adversarial replay shows red badges; methods drawer shows the ladder; attribution visible; the live button is disabled unless `serve.py` responds to a health check.

---

## 10. Judge-facing numbers and honest limits

Numbers the backend must print in `summary.md` and `methods.json` (all reproduced today unless marked):

| Claim | Value |
|---|---|
| Corpus | 55,368 deliberate disabling events, 5,269 vessels, 101 flags, 2017–2019, fishing vessels only |
| Operating rule | both ends within 10 km and 1 h, intervals overlap → **434 candidates** (≈ 145 per year) |
| Null | within-cell permutation, 200 draws: mean ≈ 12 → **lift ≈ 36×** (rerun quotes the exact value) |
| Ladder | 101,901 · 1,230 · 5,630 · 434 · 103 · 3 across the six rungs, each with its own null lift |
| Loose rule | 18,775 pairs; joint feasibility keeps 18,735 → shown as a methods number, never as a queue |
| Structure | 237 bilateral pairs; 173 sequential-MMSI; 181 identity twins; 26 cross-flag; 37 pairs with zero neighbours |
| Showcase | 5 s / 6.6 km at shutoff, 43 s / 9.0 km at reappearance, 41.8 h, 892 km offshore, one neighbour, p_cell 0.005 |
| Kinematics | median required speed 0.65 kn, median plausibility 0.95 → uninformative at the operating rule, so unscored |
| Precision caveat | WCPFC: 78 % of 77 AIS-only transshipment candidates were unsubstantiated after triangulation |

Honest limits to state in the product and the pitch: fishing vessels only (carriers arrive only with the API pull; no tankers ever); no coordinate-level ground truth; the meeting point is inferred and drawn as a heuristic; detection is retrospective (both gaps must close); AIS is cooperative and a contested-signal environment produces gaps this method cannot distinguish from disabling without the reception-quality layer (D10, deferred); the score is an analyst priority, not a probability of wrongdoing; the LLM narrative is checked span by span and anything unverifiable is shown as such.

---

## 11. Open decisions for the team

1. **Queue scope** — export all 434 (recommended; the UI filters by label) vs. top 50.
2. **2017–2019 GAP bronze into the repo now** — yes (recommended); it retires D8 and adds vessel names to the cards. The committed 2021 and partial-2022 pulls do not substitute for it: the corpus, the null and the showcase are 2017–2019.
3. **Narration provider** — `claude-opus-5` at low effort (recommended; structured outputs, ~$1 total) vs. OpenAI for sponsor points via a provider shim; the verifier is provider-agnostic either way.
4. **VIIRS attempt** — 90-minute time box for Andrew (recommended) vs. skip and show `no_coverage`.
5. **Commit generated JSON** into `code/frontend/public/data/` (recommended) vs. build-time generation.
6. **Fishing–carrier stretch** — only if the 2017–2019 pull lands by 21:00 and the frontend is ahead of schedule.
7. **2021 recent-year queue (stretch)** — the complete 2021 API pull holds ≈ 29,000 fishing and ≈ 450 carrier gaps with names, regions and distances; S3 and S4 would run on it unchanged (the MID filter drops the 87 % gear). Recommended: no, unless P3 lands by 23:30 with slack. The null and every verified number are 2017–2019 and would need a rerun, and the API's disabling classification is GFW's, not the paper's.

---

## 12. Statements in `build-plan.md` that are now stale

- "no backend module exists … no HTTP client" → Andrew's `src/dark_rendezvous/` exists with an httpx GFW client and paginated pulls (not installed; pins need relaxing).
- "No GFW token" → Andrew has one (his machine only).
- "Dependencies to add: `httpx`" → also `anthropic`; both have Python 3.14 wheels.
- Open question 1 (carriers in the gap dataset) → answered yes from the Jan-2017 pull.
- D8 "point-in-polygon on endpoints" → replaced by the API's `regions` and `distances`.
- §4.1 "loose-only candidates rank below operating candidates" → the loose rule is not a queue source (feasibility does not prune it).
- §9 worked example: `overlapHours 41.75, requiredSpeedKn 2.3, jointDwellHours 36.4, localDarkCount 3, neighbour 577101000` → computed values are 41.76, 0.92, 38.6, 1 and neighbour 412329634 (CHN).
- "434–437 operating pairs, 27 cross-flag" → 434 and 26 after the MMSI validity filter.
- D12 "AIS presence … P1" with no source → `gfw-presence` exists and was smoke-tested (§1 D12); the corpus-endpoint fallback remains the default.
- D13 "raw tracks, deferred" → still deferred, now for a concrete reason: the token has no tracks permission (§1 D13).
- This plan's first revision, §1 D1′ "Jan 2017 only" → superseded: 2021 complete and 2022 partial are committed, 2017–2019 still missing (§1 D1′).
- §2 "no HTTP client" → `httpx` is installed in `.venv` (16:40 EDT).

---

## 13. Merge review, Sat 16:37 EDT (what changed on `andrew-dev` and `main`, and what it means)

Merged cleanly into `Tanner-dev`: `origin/andrew-dev` ec33b4c (7d5788f) and `origin/main` ee6253e (dd7e94e). No conflicts; `plan/` untouched by either side.

| Change | Effect on this plan |
|---|---|
| 2021 GAP bronze complete (343,857 events), 2022 partial, both bronze-only | Not demo inputs (§2.11). Confirms the API schema at scale: `highSeas` empty, `ACAP`/`IWC` everywhere, string-typed numerics, 87 % gear (§4 S1′). |
| 2017-02 → 2019-12 GAP bronze absent | **Blocks S1′ enrichment (names, jurisdiction, port distance).** Ask Andrew to commit it; likely already pulled (§1 D1′). Nothing in Tanner's critical path S1 → S3 → S4/S2 → S6 → S8 waits on it. |
| `gfw-presence` (4Wings hourly presence, grid-cell centres) | Gives D12 a real source for VIIRS correlation; optional, showcase window only (§4 S7). |
| `gfw-track` implemented, token lacks permission (404) | D13 stays deferred. |
| `position_semantics` column; `--bronze-only`; runbook + PowerShell backfill | Provenance is better; the pipeline does not consume the canonical positions table, so no contract change. |
| `pyproject` still pins `python<3.14`, `pandas<3`, `shapely`; package `__init__` imports shapely | Pipeline stays independent (§2.9). Andrew's 9 tests pass on 3.14 / pandas 3 once shapely is installed, so relaxing the pins is safe. |
| 834 MB bronze committed; docs claim `data/` is git-ignored | Hygiene note in §4 S1′′; no history rewrite. |
| `MapPanel` prop-less offline basemap; `types.ts`, `provider.ts` unchanged | Output contract (§6.1) unaffected. Frontend must restore the props and layers (§6.4.5). |
| Slidev deck with placeholder numbers; logos | Feed §10 into `presentation/slides.md` at freeze. |

Asks for Andrew, in priority order: (1) commit 2017–2019 GAP bronze (or the enrichment parquet); (2) relax pins and move the `shapely` import; (3) identity search for the 212 queue MMSIs once S3 emits them; (4) `events()` for ENCOUNTER / LOITERING / PORT_VISIT; (5) EU carding CSV (Appendix A); (6) VIIRS time box, then presence for the showcase window only if VIIRS lands; (7) fix the `data/` git-ignore sentence in `docs/ais-ingestion.md`.

**17:15 update** (five more `andrew-dev` commits 16:45–17:05 and `main` 2840612 merged; 16 tests green): GAP bronze now also covers 2022 Jan → Oct and 2026 Jan → Mar, both still running and without `pull_manifest.json`; **2017-02 → 2019-12 is still absent**. A new `scripts/run_gfw_presence_backfill.ps1` pulled daily presence for the Russian EEZ (region 5690) for 2021-09-05/06 and 2026-08-05 → 09-04 (33 days, ≈ 30,000 rows a day, the last three days empty from data latency; 679 MB of bronze). This is not in the plan: it serves Andrew's parallel `docs/ais-first-rendezvous-plan.md` (same product idea, its own repo layout) and cannot touch the 2017 NW-Pacific showcase. The CLI now reads the token from an untracked `.env` as a fallback and gives presence reports a 180 s timeout; `data/logs/` is committed. Checked: no token in the logs, state file or history; `.env` is ignored. `main` only merged Andrew's earlier code, no frontend change. Ask (1) is unchanged and now the only thing blocking S1′; T9 in `plan/handoff-prompts.md` turns asks (3) and (4) into one script Andrew runs.

## Appendix A — EU IUU carding seed table (`data/reference/eu_iuu_cards.csv`)

Hand-compiled from memory of the Commission's carding decisions; **Andrew verifies each row against the DG MARE press releases before the pitch** (search "Commission IUU yellow card <country>"). Rows outside 2017–2019 are included so the join is time-valid.

| flag_iso3 | colour | start_date | end_date | confidence |
|---|---|---|---|---|
| TWN | yellow | 2015-10-01 | 2019-06-27 | high |
| THA | yellow | 2015-04-21 | 2019-01-08 | high |
| VNM | yellow | 2017-10-23 | null | high |
| KHM | red | 2014-03-24 | null | high |
| COM | yellow | 2015-10-01 | 2017-05-23 | medium |
| COM | red | 2017-05-23 | null | medium |
| VCT | yellow | 2014-12-12 | 2017-05-23 | medium |
| VCT | red | 2017-05-23 | null | medium |
| TTO | yellow | 2016-04-21 | null | medium |
| KIR | yellow | 2016-04-21 | 2020-12-17 | medium |
| SLE | yellow | 2016-04-21 | null | medium |
| LBR | yellow | 2017-05-23 | null | medium |
| TUV | yellow | 2014-12-12 | 2018-07-04 | medium |
| CUW | yellow | 2013-11-26 | 2017-02-24 | medium |
| SLB | yellow | 2014-12-12 | 2017-02-24 | medium |
| ECU | yellow | 2019-10-30 | null | high |
| PAN | yellow | 2019-12-17 | null | medium |
| LKA | red | 2014-10-14 | 2016-06-21 | high |
| GIN | red | 2013-11-26 | 2016-10-20 | medium |
| PHL | yellow | 2014-06-10 | 2015-04-21 | high |
| KOR | yellow | 2013-11-26 | 2015-04-21 | high |

Corpus flags with no card in 2017–2019 (CHN, ESP, USA, FRA, JPN, VUT, RUS, PRT, SYC, ARG, AUS, FSM, ZAF, NZL) map to `none`; a missing flag maps to `unknown`.

## Appendix B — RFMO code names (`rfmo_names.json`)

`NPFC` North Pacific Fisheries Commission · `WCPFC` Western and Central Pacific Fisheries Commission · `IATTC` Inter-American Tropical Tuna Commission · `ICCAT` International Commission for the Conservation of Atlantic Tunas · `IOTC` Indian Ocean Tuna Commission · `SPRFMO` South Pacific RFMO · `SIOFA` Southern Indian Ocean Fisheries Agreement · `CCAMLR` Commission for the Conservation of Antarctic Marine Living Resources · `NAFO` Northwest Atlantic Fisheries Organization · `NEAFC` North East Atlantic Fisheries Commission · `SEAFO` South East Atlantic Fisheries Organisation · `GFCM` General Fisheries Commission for the Mediterranean · `CCSBT` Commission for the Conservation of Southern Bluefin Tuna. Non-fishery codes returned by GFW (`ACAP`, `IWC`, `IPHC`) are dropped from `jurisdiction.rfmo`.

## Appendix C — Acceptance test list (`tests/test_pipeline_*.py`)

1. `geo`: haversine, cell wrap at ±180, local frame round-trip.
2. `load`: row counts, dtype `datetime64[us, UTC]`, 54,553 valid, 484 dateline.
3. `pair`: 434 operating pairs; showcase present with the §6 numbers; ladder counts; brute-force subsample equality; `make_pair_id` symmetric.
4. `feasibility`: showcase τ ≈ 38.6 h and required speed ≈ 0.92 kn; infeasible synthetic pair; dateline pair has no ring.
5. `context`: 237 bilateral; showcase has one neighbour `412329634`; 181 twins; 173 sequential.
6. `nulls`: 5 draws run in < 10 s; lift ≠ 1.00; p_cell ∈ [1/(N+1), 1].
7. `score`: worked showcase values within ±0.02; twin pairs never `investigate`; every term in [0, 1] or null.
8. `export`: every record passes `validate_record`; no NaN; coordinates in range; attribution present.
9. `verify`: verified / contradicted / unverifiable cases as in §4.9.
