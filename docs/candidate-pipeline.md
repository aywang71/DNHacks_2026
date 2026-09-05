# GapPair candidate pipeline

## Purpose and claim

GapPair is backend scaffolding for wake.ai. It builds a ranked, auditable queue
of paired-dark candidates from AIS disabling events. It does not establish that
a transfer, rendezvous, or crime occurred.

The design has three visibility tiers. T0 is paired dark: two vessels have
overlapping AIS gaps and an inferred joint reachable area. T1 is one-sided
dark: a carrier loitering event is paired with a fishing-vessel gap. T2 is
standard: an observed encounter is ingested and ranked. Only T0 is built.

## Stage status

All verified counts below are from the 2017–2019 CSV reference run unless the
row says otherwise. A missing stage has no module or output.

| Stage | Module | Reads | Writes | Status | Verified numbers | Test file |
|---|---|---|---|---|---|---|
| S0 | pipeline/reference.py | data/reference/ tables | validated in-memory tables | complete | static tables validate | tests/test_pipeline_reference.py |
| S1 | pipeline/load.py | data/raw/disabling_events.csv | gap_events.parquet, exclusions.json | complete | 55,368 rows; 54,553 valid MMSIs; 815 invalid; 702 blank flags; 484 dateline | tests/test_pipeline_load.py |
| S1′ | pipeline/enrich_api.py | complete 2017–2019 GAP bronze | GFW enrichment parquet | missing | no 2017-02 through 2019-12 bronze is present | none |
| S3 | pipeline/pair_t0.py | gap_events.parquet | candidates_t0.parquet, pair_grid_counts.json, queue_mmsis.txt | complete | 434 operating pairs; 26 cross-flag; 212 queue MMSIs; ladder 101,901 / 1,230 / 5,630 / 434 / 103 / 3; loose 18,775 | tests/test_pipeline_pair.py |
| S2 | pipeline/feasibility.py | gap events and T0 candidates | feasibility.parquet, loose_feasibility.json | complete | 433 of 434 feasible; showcase τ 38.564 h, required speed 0.919 kn, p* (162.000, 42.775); loose 18,735 feasible | tests/test_pipeline_feasibility.py |
| S4 | pipeline/context.py | gap events and T0 candidates | local_context.parquet, components.parquet | complete | 237 bilateral; 183 strict identity twins; 173 sequential MMSIs | tests/test_pipeline_context.py |
| S5 | pipeline/nulls.py | gap events and T0 candidates | null_results.json, p_cell.parquet | complete | 20 draws on disk; null mean 12.4; lift 35.0× | tests/test_pipeline_nulls.py |
| S6 | pipeline/features.py, pipeline/score.py | S0–S5 and optional enrichment | features.parquet, scores.parquet | missing | not verified | none |
| S7 | pipeline/corroborate.py | T0 candidates and optional VIIRS input | corroboration.parquet | default hook complete; real VIIRS join not implemented | 434 default no_coverage rows; no VIIRS | tests/test_pipeline_corroborate.py |
| S8 | pipeline/export.py | S2, S6, S7 and candidates | risk-events.json, tracks, methods, ledger, summary | scaffold only | fixture-level export test passes; no full export has run because S6 is missing | tests/test_pipeline_export.py |
| S9 | pipeline/narrate.py, pipeline/verify.py | S8 outputs | narratives.json | missing | not verified | none |
| T10 | pipeline/load_api.py | Andrew's 2021 API corpus | normalized API gap_events.parquet | missing | 2021 probe has 66,306 valid-MMSI events and 465 operating fishing-plus-carrier pairs | none |
| T11 | pipeline/presence_bridge.py | API candidates and candidate-window presence | viewer candidates.json bridge | missing | 28 in-EEZ 2021 pairs have presence days in the probe; 12 are high-seas pairs | none |

S3 appears before S2 in the runner because S2 evaluates the pairs produced by
S3. S6 and S9 are designed stages, not implemented stages.

## Run the implemented reference path

Run commands from the repository root. The runner accepts repeatable --stage
flags and runs selected stages in its fixed order.

    .venv/bin/python -m pipeline.run --stage reference
    .venv/bin/python -m pipeline.run --stage load
    .venv/bin/python -m pipeline.run --stage pair
    .venv/bin/python -m pipeline.run --stage feasibility
    .venv/bin/python -m pipeline.run --stage context
    .venv/bin/python -m pipeline.run --stage null --draws 20
    .venv/bin/python -m pipeline.run --stage corroborate

Use --draws 200 for the configured null-model draw count. S0 validates the
reference tables. S1 writes the normalized event corpus to data/derived/. S3,
S2, S4, S5, and S7 write the files named in the table. S6 blocks a full score
and export path. --all is not a usable full reference command while the
missing stages remain missing.

The session-wide pipeline test run has 49 passes and one failure. The failing
test is the timing assertion in tests/test_pipeline_nulls.py: 13.8 seconds
observed against a 10-second bound. It is a performance failure, not a
correctness failure.

The active .venv runs Python 3.14.2, pandas 3.0.5, numpy 2.5.2, pyarrow
25.0.1, and shapely 2.1.2. pyproject.toml and requirements.txt instead pin
Python below 3.14, pandas below 3, and pyarrow below 22. This is an environment
mismatch. It is documented here and not fixed.

## Method reference

### Reachability and feasibility

For a gap with endpoints (p0, t0) and (p1, t1), maximum class speed V in
knots, and V_km = 1.852 · V:

    L(p)      = D(p0, p) + D(p, p1)
    dwell(p)  = (t1 − t0) − L(p) / V_km
    arrive(p) = t0 + D(p0, p) / V_km
    depart(p) = t1 − D(p, p1) / V_km

p is reachable for a minimum dwell τ_min when dwell(p) ≥ τ_min. The reachable
set is the ellipse {p : L(p) ≤ V_km · (t1 − t0 − τ_min)}. Rings are sampled in
a local planar frame. The configured τ_min is 1 h.

For two vessels, joint dwell is:

    τ_AB(p) = min(depart_A(p), depart_B(p)) − max(arrive_A(p), arrive_B(p))

The pair is feasible when max_p τ_AB(p) ≥ τ_min. The maximizing p* is the
inferred meeting point. The pipeline also records the zero-dwell
required_speed_kn and kin_plausibility = clip(1 − required_speed_kn / V, 0, 1).
Kinematics is a gate and a loose-rule feature. It is not affirmative evidence
for an operating T0 pair.

### Candidate rules and context

The operating T0 rule requires different valid MMSIs, overlapping gaps,
shutoffs within 10 km and 1 h, and reappearances within 10 km and 1 h. Its
ladder is the configuration table below. The loose rule uses 50 km and 6 h at
both ends plus joint feasibility. It is a methods-drawer value, not a queue
source.

Local context excludes the pair's own two events. It considers neighbours
within 200 km and ±1 h at both shutoff and reappearance, components over the
operating-pair graph, sequential MMSIs, strict identity twins, gap
unusualness, and repeat rate. Local density is a penalty, not a null model.

The null model permutes gap start times within a 5° cell while preserving the
event positions and durations. For a candidate cell-month:

    p_cell = (1 + draws with pair count ≥ observed count) / (1 + N)

The pseudo-count prevents log(0). A null lift of exactly 1.00× fails the run
because it indicates a broken null.

### Designed features, score, labels, and evidence tiers

S6 is not implemented. Its specified features are geometry, kinematics,
behaviour, context, corroboration, and confounders. Missing inputs stay null;
they are not converted to observed evidence.

    S_geom = clip(−log10(p_cell), 0, 2) / 2
    S_beh  = 0.5·bracket + 0.3·(role_pair == fishing–carrier) + 0.2·port_after_gap_risk
    S_ctx  = 0.3·cross_flag + 0.3·flag_card(any) + 0.2·not_authorized(any)
             + 0.1·iuu_listed(any) + 0.1·port_risk
    S_cor  = 1.0 if viirs_state == uncorrelated_detection else 0
    S_kin  = kin_plausibility for loose pairs and T1
    S_den  = clip(log10(1 + local_dark_count) / 2, 0, 1)
    S_flt  = max(fleet_cluster, sequential_mmsi, identity_twin, local_same_flag_share > 0.8)
    S_hab  = 1 − gap_unusualness

    raw      = 0.30·S_geom + 0.15·S_kin + 0.20·S_beh + 0.15·S_ctx + 0.20·S_cor
               − 0.15·S_den − 0.20·S_flt − 0.10·S_hab
    priority = sigmoid(6 · (raw − 0.30))

The priority is an analyst-priority value, not a probability of wrongdoing.
The designed labels are investigate, coordinated-fleet-pattern, identity-twin,
likely-coverage-or-cluster-artifact, possible-port-transit, and
insufficient-evidence. Evidence tiers are coincidence_or_artifact,
coordinated_fleet_activity, bilateral_rendezvous_plausible,
behaviour_corroborated, and imagery_corroborated.

### Correctness rules

- Pandas 3 timestamps are datetime64[us, UTC]. Compute durations with
  timedeltas, not an unlabelled integer timestamp conversion.
- Distances are km, speeds are knots, and durations are hours. Use
  km = kn · h · 1.852 and haversine radius 6,371 km.
- Wrap 5° longitude cells at the dateline. Normalize exported longitudes to
  [-180, 180]. Mark dateline geometry and omit its ring polygon.
- Keep raw MMSI separate from any resolved identity. Quarantine invalid MMSIs.
- Use pseudo-counts for probabilities. Do not take log(0).
- Keep Global Fishing Watch attribution and the CC BY-NC 4.0 notice with an
  exported record.

## Configuration reference

pipeline/config.py is the single source of truth. Values below reproduce its
current configuration.

| Setting | Value |
|---|---|
| RAW_CSV | data/raw/disabling_events.csv |
| DERIVED | data/derived |
| REFERENCE | data/reference |
| BRONZE_GAPS | data/bronze/gfw_gaps |
| FRONTEND_PUBLIC | code/frontend/public |
| OUT_DATA | code/frontend/public/data |
| OPERATING | start 10.0 km / 1.0 h; end 10.0 km / 1.0 h |
| LADDER | start-only 50 km / 24 h; start-only 5 km / 1 h; both ends 25 km / 3 h; both ends 10 km / 1 h; both ends 5 km / 1 h; both ends 2 km / 30 min |
| LOOSE | start 50.0 km / 6.0 h; end 50.0 km / 6.0 h |
| TAU_MIN_H | 1.0 |
| V_KN | squid jigger 12.0; drifting longlines 12.0; trawlers 13.0; tuna purse seines 16.0; other 14.0; carrier 18.0; reefer 18.0; unknown 16.0 |
| KM_PER_KN_H; EARTH_R_KM | 1.852; 6371.0 |
| CELL_DEG; NULL_DRAWS; LADDER_DRAWS; SEED | 5; 200; 20; 20260905 |
| LOCAL_KM; LOCAL_H; NEIGHBOURS_MAX; SAME_FLAG_MIN_VESSELS | 200.0; 1.0; 8; 3 |
| SEQ_MMSI_MAX_DELTA; TWIN_LEN_M; TWIN_TON_GT; MIN_GAPS_FOR_HISTORY | 10; 0.5; 1.0; 3 |
| MMSI_VALID | MMSI 100,000,000–999,999,999; MID 201–775 |
| WEIGHTS | geom 0.30; kin 0.15; beh 0.20; ctx 0.15; cor 0.20; den −0.15; flt −0.20; hab −0.10 |
| SIGMOID_K; SIGMOID_MID | 6.0; 0.30 |
| INVESTIGATE_MIN_PRIORITY; PENALTY_DOMINANT | 0.5; 0.5 |
| FLEET_CLUSTER_MIN_SIZE; BLACKOUT_MIN_SIZE; BLACKOUT_LOCAL_COUNT | 3; 5; 20 |
| PORT_TRANSIT_KM | 50.0 |
| FISHERY_RFMOS | NPFC, WCPFC, IATTC, ICCAT, IOTC, SPRFMO, SIOFA, CCAMLR, NAFO, NEAFC, SEAFO, GFCM, CCSBT |
| NULL_MODEL_NAME | within-cell permutation v1 |
| SHOWCASE | MMSIs 412331147 and 416004105; T0 date 2017-07-01 |
| ATTRIBUTION | Data: Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0 |

## Output contract

S8 specifies a static risk-events.json array and one GeoJSON track per
candidate. This is an intended contract. A full export is not present because
S6 is missing.

| Area | Record fields |
|---|---|
| Identity and display | id, name, imo, flag, vesselType, vessels[] |
| Classification | tier, label, evidenceTier, priority, riskScore, riskLevel, eventKind, eventLabel |
| Time and place | location, lastSeen, coordinates, window, meetingPoint, jurisdiction |
| Method | scores, features, corroboration, nullModel, neighbours, explanations |
| Evidence | evidence[], timeline[], sources[], attribution, analystDisposition |
| Geometry | embedded track FeatureCollection and tracks/<id>.geojson |

Coordinates use [lon, lat]. Timestamps are ISO-8601 UTC strings. JSON missing
values are null, never a sentinel number. riskScore is round(100 · priority).

| Tier | eventKind |
|---|---|
| paired-dark | dark-period |
| one-sided | loitering |
| standard | encounter |

| Label | riskLevel |
|---|---|
| investigate | high |
| coordinated-fleet-pattern, identity-twin, possible-port-transit | review |
| likely-coverage-or-cluster-artifact, insufficient-evidence | watch |

The track FeatureCollection has four observed endpoint Point features. It has
two estimated dashed LineString projections, each from a shutoff through the
inferred meeting point to a reappearance. The meeting point is an estimated
Point. Each reachable ring is an estimated Polygon. All estimated features
carry observationStatus: estimated; observed endpoints carry
observationStatus: observed. Omit ring polygons when the geometry crosses the
dateline.

The current presence viewer does not read risk-events.json, tracks,
methods.json, or narratives.json.

## Open definitions and decisions

| Topic | Decision |
|---|---|
| local_dark_count | Keep the code definition: the union of shutoff and reappearance neighbours, excluding the pair's own events. It has median 7, p90 35, and 16 zeros. The shutoff-only count has median 3, p90 25, and 37 zeros. Methods claims use the union definition. |
| Identity twins | Keep the strict rule and its 183 pairs. The two additional valid TWN squid-jigger pairs remain included. |

The figures “181” identity twins and “3 neighbours” in archived
[build-plan.md](archive/plan/build-plan.md) §5 are superseded.

## Two corpora

| Corpus | Use | Join properties | Current state |
|---|---|---|---|
| 2017–2019 disabling-events CSV | Validation and reference run. It supplies all verified pipeline counts, the null lift, and the showcase pair CHN 412331147 × TWN 416004105 on 2017-07-01. | It has no GFW vessel IDs. | Complete reference path through S7 default corroboration. |
| Andrew's 2021 GFW API pull | Demo-capable corpus for the viewer integration. | It has GFW vessel IDs, names, flags, EEZ/RFMO IDs, and shore/port distances. The viewer key is gfw:<vesselId>. | Complete pull exists; T10 loader is not implemented. |

S2 through S8 are corpus-agnostic when given a compatible gap_events.parquet.
The 2021 loader and the viewer bridge are still needed. The CSV corpus remains
the validation reference; it does not become viewable by identity key without
further enrichment.

## Designed but not built

| Item | Missing work or input |
|---|---|
| T1 one-sided | Carrier loitering events, fishing-gap join, and score implementation. |
| T2 standard | Encounter-event ingest and ranking. |
| S1′ enrichment | Complete 2017–2019 GAP bronze and the enrich_api.py module. |
| S6 features and score | features.py and score.py. |
| S8 full export | S6 outputs, then a real export and validation run. |
| S9 narration and verification | An LLM decision, an API key, narrator, and verifier modules. |
| T10 API loader | Normalization of the 2021 API corpus. |
| T11 presence bridge | Candidate asset for the presence viewer and targeted presence windows. |
| VIIRS | EOG coverage and detections for candidate windows; current status is unknown. |
| Reception-quality penalty | A reception-quality source and its feature implementation. |
| Raw tracks | Per-message AIS vectors. The available GFW track route returns 404 for the token application. |
| SAR | A detection source and candidate-window join. |

The archived [handoff prompts](archive/plan/handoff-prompts.md) retain the
original implementation prompts. [Data needs](data.md) lists the required data
and inputs.

## Frontend fixture

code/frontend/public/data/risk-events.json, methods.json, and narratives.json
are hand-made three-record P0 fixtures in the GapPair contract. They are not
generated from a completed S8 run. The React app does not read them.

