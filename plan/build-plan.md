# GapPair — backend design

**Scope:** detection, scoring, corroboration, and the data contract the frontend consumes. UI is owned separately (see `frontend-notes.md`). Research and references are in `research-notes.md`.

**Claim we build toward:** GapPair turns AIS behaviour and AIS silence into a ranked, auditable queue of rendezvous candidates across three visibility tiers, with every score component shown and a calibrated chance baseline for the tiers where the meeting is inferred rather than observed. It never asserts that a transfer or a crime occurred.

---

## 1. Detection tiers: divide the cases by what AIS can see

A rendezvous involves two vessels. At the time of the meeting each is either broadcasting or dark, which gives three cases. Each case has a different observable signature, a different documented rule to cite, and a different meeting-point status.

| Tier | Visible | Signature | Documented rule we cite | Candidate source | Meeting point |
|---|---|---|---|---|---|
| **T2 Standard** | both | proximity, low speed, sustained duration | GFW encounter: 500 m, ≥2 h, median <2 kn, ≥10 km from anchorage (Miller et al. 2018). Skylight: 250 m, ≥30 min, <4 kn, >10 km from coast | GFW `ENCOUNTER` events; our own rule if raw tracks arrive | observed |
| **T1 Dark, one-sided** | one | the visible vessel loiters as if meeting; another vessel has a gap whose reachable set covers that place and time | Skylight Dark Rendezvous: ≥15 min rendezvous-like behaviour, not within 100 km of shore. GFW loitering: <2 kn, ≥20 nm from shore | GFW `LOITERING` events joined to gap events by kinematic feasibility | observed (the loiterer's position) |
| **T0 Paired dark** | neither | two gaps that start together and end together, with a joint reachable set | none published. Oxford Dark Shipping Alg. A.2 is the only precedent for two simultaneously dark vessels | gap × gap pairing | inferred (joint reachable set) |
| T1u Unpaired loiter | one | loitering with no gap partner found | Skylight Dark Rendezvous | GFW `LOITERING` with no feasible gap join | observed, partner unknown |

T2 is Skylight's Standard Rendezvous, T1 is its Dark Rendezvous, T0 is the row Skylight does not have. Skylight builds its one-sided model by taking two-sided events and hiding one vessel (the `create_osr_dataset.py` recipe in `allenai/atlantes`). We go one step further in the same direction and calibrate T0 against the same two-sided events. That lineage is the pitch.

Within each tier, candidates are further split by **component class** (bilateral, fleet cluster, regional blackout, unresolved) and **role pair** (fishing–carrier is the transshipment archetype; fishing–fishing is fleet coordination or fuel, crew, catch consolidation; carrier–carrier is rare; unknown when identity is unresolved). The 2017–2019 disabling corpus is fishing-only, so any fishing–carrier candidate in T0 or T1 requires carrier gap events from GFW (data item D2).

---

## 2. Data requirements

What we need and why, not how it is obtained. Priority P0 blocks the core queue, P1 makes the queue credible, P2 is upside.

| # | Data | Fields needed | Used by | Priority |
|---|---|---|---|---|
| D1 | AIS disabling events 2017–2019 (**on disk**, 55,368) | mmsi, class, flag, off/on time, off/on lat/lon, distance from shore both ends, gap hours, length, tonnage | T0, T1, all features | P0 |
| D2 | GFW gap events for **carriers, reefers, support vessels**, same years, same regions | same shape as D1 plus vessel type | fishing–carrier candidates in T0 and T1 | P1 |
| D3 | GFW `ENCOUNTER` events, 2017–2019, for corpus vessels and their regions | both vessel ids, start/end, position, median distance, median speed, vessel types | T2 queue; known-partners feature; T0 calibration | P0 |
| D4 | GFW `LOITERING` events, same scope | vessel id, start/end, start and end position, mean speed, distance from shore | T1 join; behaviour feature for T0 | P0 |
| D5 | GFW `PORT_VISIT` events, same scope | vessel id, port name, port country, anchorage id, start/end | port context, A.1 risk-port reach, `port_after_gap` | P0 |
| D6 | GFW `FISHING` events, same scope | vessel id, start/end, position | fishing-ground alternative explanation; coarse heading proxy | P1 |
| D7 | GFW vessel identity for all ~5,300 corpus MMSIs (and D2 vessels) | gfw vessel id, all MMSI/IMO/callsign aliases with date ranges, vessel type and gear, flag history, owner, build year, **public RFMO authorizations with dates** | identity resolution, role pair, Level 1 context, A.4 features | P0 |
| D8 | Static geography | EEZ polygons, RFMO convention areas, GFW anchorages or Natural Earth ports, PSMA party list | `eez_entry_while_dark`, RFMO check, A.1 port reach, jurisdiction label | P0 |
| D9 | Risk lists | EU IUU carding history (flag, card colour, start, end), combined RFMO IUU vessel list (name, MMSI, IMO, listing dates), Tokyo MoU flag list | `context_risk` | P0 |
| D10 | Reception quality | GFW satellite reception model raster (positions/day expected), monthly, both AIS classes | `coverage_quality` penalty | P1 |
| D11 | VIIRS boat detections (NOAA EOG VBD) for the nights and boxes of the top ~30 candidates | lat, lon, timestamp, radiance, quality flag, cloud flag | corroboration | P1 |
| D12 | AIS presence for the same nights and boxes (GFW presence raster or broadcasting positions) | cell or position, timestamp, vessel count | AIS-correlation test for VIIRS lights | P1 |
| D13 | Raw AIS tracks for the top ~20 candidate vessels, ±7 days around each window | mmsi, timestamp, lat, lon, sog, cog, nav status | T2 rule run by us; kinematic features; last heading before gap; optional ATLAS run | P2 |
| D14 | SAR detections (GFW Sentinel-1 dataset) for top candidates | lat, lon, timestamp, length, AIS-matched flag, scores | corroboration, expected mostly "no coverage" on the high seas | P2 |

Two questions for the data owner decide the shape of T1 and the fishing–carrier story: does GFW's gap dataset include carriers (D2), and can we get any raw tracks at all (D13)?

---

## 3. Shared primitives

### 3.1 Reachable set and dwell time (the core geometric object)

For a gap `G` with shutoff `(p0, t0)`, reappearance `(p1, t1)`, and class maximum speed `V`:

```
L(p)      = D(p0, p) + D(p, p1)                 detour distance through p
dwell(p)  = (t1 − t0) − L(p) / V                longest stay possible at p
arrive(p) = t0 + D(p0, p) / V                   earliest arrival at p
depart(p) = t1 − D(p, p1) / V                   latest departure from p
```

`p` is feasible for a rendezvous of minimum length `τ_min` iff `dwell(p) ≥ τ_min`. The reachable set is `{p : dwell(p) ≥ τ_min}`, a lens around the straight line from `p0` to `p1`. Everything below is built from these four numbers. This generalises Oxford Alg. A.2: their required speed at the overlap midpoint is the special case `L(p) / (t1 − t0)` with zero dwell.

Defaults: `τ_min = 1 h` (between Skylight's 30 min and GFW's 2 h; both shown in the methods drawer). `V` by class: squid jigger 12 kn, drifting longline 12, trawler 13, tuna purse seine 16, other fishing 14, carrier or reefer 18, unknown 16. Speeds are conservative upper bounds and live in `config.py`.

### 3.2 Joint feasibility for two vessels

For vessels A and B and a point `p`: joint dwell `τ_AB(p) = min(depart_A(p), depart_B(p)) − max(arrive_A(p), arrive_B(p))`. The pair is kinematically feasible iff `max_p τ_AB(p) ≥ τ_min`. `p* = argmax_p τ_AB(p)` is the **feasible meeting point**, found by a coarse grid over the bounding box of the four endpoints with margin, then a local refinement. Outputs: `p*`, `joint_dwell_hours`, `required_speed_kn = max_v L_v(p*) / ((t1 − t0)_v − τ_min)`, and the reachable-set polygon for display.

### 3.3 Kinematic plausibility

Two forms, both reported: `kin_plausibility = clip(1 − required_speed_kn / V, 0, 1)` and the Oxford form `kin_percentile = 1 − percentile(required_speed_kn | corpus implied-speed distribution)`, where implied speed is `D(p0, p1) / (t1 − t0)` across all gaps of that class.

### 3.4 Local context

Computed per event and per pair, excluding the pair's own two events: `local_dark_count` and `local_unique_vessels` within 200 km and ±1 h at shutoff and separately at reappearance; `local_same_flag_share`, `local_sequential_share`; graph components over operating T0 pairs giving `component_size` and `component_class`; `coverage_quality` from D10 at the shutoff cell and month; `gap_unusualness` as the gap's percentile within the vessel's own gap history; `repeat_rate` as the vessel's gaps per year and the share of its gaps that pair.

### 3.5 Null models

- **T0 within-cell permutation.** Permute gap start times among events in the same 5° cell, keep durations and positions, rerun the pairing, 100 draws. Reports lift and an empirical p for the count at each threshold. Per candidate, a local version: permute start times among the events in its 200 km / ±24 h neighbourhood and record how often a both-ended match at that threshold appears, giving `local_null_p`.
- **T1 time-shift.** Shift each loitering event by a random offset of ±3 to ±30 days within the same cell and rerun the feasibility join, 100 draws. Gives the expected number of chance joins and, per candidate, `shift_null_p` as the fraction of draws in which that gap still joins some loiterer.
- **T2.** No null; the encounter is observed. `historical_pair_count` says whether it is routine for these two vessels.

A lift of exactly 1.00× is the signature of a broken null and fails the run.

---

## 4. Candidate generation

### 4.1 T2 Standard (both visible)

Ingest D3 as-is; GFW has already applied the 500 m, 2 h, 2 kn, 10 km rule. Deduplicate mirrored records (each encounter appears once per vessel). If D13 arrives, run the same rule ourselves with `pipe-encounters` parameter names so the two agree, and add Skylight's tighter 250 m / 30 min variant as a flag.

### 4.2 T1 Dark, one-sided (one visible)

For each loitering event `L` (vessel `v_L`, window `[l1, l2]`, positions `q1, q2`) and each gap `G` of a different vessel whose interval overlaps `[l1, l2]`:

1. Spatial gate: `D(p0_G, q1) ≤ V_G × (l2 − t0_G)` and `D(q2, p1_G) ≤ V_G × (t1_G − l1)`; skip otherwise.
2. Feasibility: `overlap = min(depart_G(q), l2) − max(arrive_G(q), l1)` at `q` = the loitering centroid; keep if `overlap ≥ τ_min`.
3. Emit a T1 candidate `(v_L, v_G)` with `overlap_hours`, `required_speed_kn` for the gap vessel to reach `q`, and the loiterer's own event fields.

Loitering events with no feasible join become T1u records with low priority. A gap that joins many loiterers is a density signal, not many meetings; `t1_join_count` feeds the density penalty.

### 4.3 T0 Paired dark (neither visible)

Operating rule, deterministic and pre-registered: different MMSIs, both valid; shutoffs within 10 km and 1 h; reappearances within 10 km and 1 h; dark intervals overlap. Blocked by a sliding window on shutoff time plus vectorised haversine; validated against brute force on a subsample. Canonical `pair_id` from the sorted gap ids.

Loose rule for recall: intervals overlap, shutoffs within 50 km and 6 h, reappearances within 50 km and 6 h, **and** joint feasibility from 3.2 holds. Loose-only candidates are ranked below operating candidates unless corroborated.

Threshold ladder reported for the methods drawer: start-only 50 km / 24 h and 5 km / 1 h; both-ends 25 km / 3 h, 10 km / 1 h, 5 km / 1 h, 2 km / 30 min. Prior run: 437 operating pairs at ~35× the within-cell null, 27 cross-flag at ~22×. These numbers are re-run, not quoted.

---

## 5. Features and scoring

Every candidate, regardless of tier, gets the same feature families. Missing inputs yield nulls, never zeros, and the explanation says what was missing.

| Family | Features | Tiers |
|---|---|---|
| Geometry and synchrony | start/end distance and delta, overlap hours, duration ratio, `local_null_p` or `shift_null_p` | T0, T1 |
| Kinematics | `p*`, `joint_dwell_hours`, `required_speed_kn`, `kin_plausibility`, `kin_percentile` | T0, T1 |
| Behaviour | `loiter_bracket` (loitering by either vessel within ±24 h and 50 km), `encounter_bracket`, `known_partners` (prior T2 encounter between the same two), `fishing_ground_context` (fishing events by either vessel at the same spot within ±24 h), `port_after_gap` with country and risk flag | all |
| Context (Oxford Level 1 adapted) | `flag_card_a/b` at date, `rfmo_area`, `rfmo_authorized_a/b`, `iuu_listed_a/b`, `port_risk`, `role_pair`, `eez_entry_while_dark` | all |
| Risk-port reach (Oxford A.1, paper's sign) | `risk_port_reach` = max dwell at the nearest risk port from 3.1 with `τ_min = 2 h`; `possible_port_transit` flag for a generic port | T0, T1 |
| Corroboration | `viirs_state`, `viirs_uncorrelated_count`, `viirs_min_km_to_p*`, `sar_state` | T0, T1 |
| Confounders | `local_dark_count`, `component_class`, `local_same_flag_share`, `sequential_mmsi`, `coverage_quality`, `gap_unusualness`, `repeat_rate`, `t1_join_count` | T0, T1 |

**Score.** A log-odds scorecard, weights documented in config, every term shown on the card:

```
logit = b_tier
      + w_geom · S_geom      T0: clip(−log10(local_null_p), 0, 3)/3 ; T1: same with shift_null_p ; T2: 1
      + w_kin  · S_kin       kin_plausibility (T2: not applicable, 0 weight)
      + w_beh  · S_beh       weighted sum of behaviour features, role_pair fishing–carrier counts most
      + w_ctx  · S_ctx       context risk incl. risk_port_reach
      + w_cor  · S_cor       uncorrelated VIIRS or SAR in the reachable set during the window
      − w_den  · S_den       local density, t1_join_count
      − w_flt  · S_flt       fleet component, same-flag share, sequential MMSI
      − w_cov  · S_cov       poor reception quality, low gap unusualness (habitual gaps)
priority = sigmoid(logit)      labelled "analyst priority", never a probability of wrongdoing
```

Proposed defaults: `w_geom 0.30, w_kin 0.15, w_beh 0.20, w_ctx 0.15, w_cor 0.20, w_den 0.15, w_flt 0.20, w_cov 0.10`, `b_tier` = 0 for T0, +0.2 for T1, +0.4 for T2. There are no labels, so weights are choices and the methods drawer says so. The `analyst_disposition` field the frontend sends back is the first label we collect.

**Labels** (from the dominant term): `investigate` when priority ≥ 0.6, component bilateral, no penalty dominant; `coordinated-fleet-pattern` when the fleet term dominates; `likely-coverage-or-cluster-artifact` when density or coverage dominates; `possible-port-transit` when the generic-port geometry holds and a port visit follows; `insufficient-evidence` when identity is unresolved or required fields are missing.

**Evidence tier** (separate from priority, monotone in what has been checked): `coincidence_or_artifact` → `coordinated_fleet_activity` → `bilateral_rendezvous_plausible` → `behaviour_corroborated` (T2, or T0/T1 with a bracket) → `imagery_corroborated`.

---

## 6. Corroboration layer

For each top candidate, join D11 and D12 to the reachable set (T0: joint set around `p*`; T1: a 20 km disc around the loiterer) during the dark window. A light counts only if no broadcasting vessel explains it. Output is three-state and coverage-aware: `uncorrelated_detection`, `correlated_only`, `clear_no_detection`, `no_coverage`. For squid jiggers, `clear_no_detection` is itself anomalous and is reported as "lights off", never as absence. SAR from D14 gets the same treatment and will mostly read `no_coverage` on the high seas; that result is shown, not hidden.

---

## 7. Pipeline stages and files

Backend is Python in `pipeline/`, messy is fine, every stage reruns from files.

| Stage | Module | Reads | Writes |
|---|---|---|---|
| S1 normalise | `load.py`, `events.py`, `identity.py` | D1–D9 | `gap_events.parquet`, `behaviour_events.parquet`, `vessels.parquet`, `exclusions.json` |
| S2 feasibility | `feasibility.py` | gap events | `feasibility.parquet` (implied speed, V, reachable-set params) |
| S3 candidates | `pair_t0.py`, `join_t1.py`, `ingest_t2.py` | S1, S2 | `candidates_t0.parquet`, `_t1`, `_t2`, `pair_grid_counts.json` |
| S4 context | `context.py` | S1, S3 | `local_context.parquet`, `components.parquet` |
| S5 nulls | `nulls.py` | S1, S3 | `null_results.json`, per-candidate `local_null_p`, `shift_null_p` |
| S6 features + score | `features.py`, `score.py` | S1–S5, D8, D9 | `features.parquet`, `scores.parquet` |
| S7 corroboration | `corroborate.py` | D11, D12, D14, S6 | `corroboration.parquet` |
| S8 export | `export.py` | S6, S7 | `candidates.json`, `evidence_ledger.parquet`, `summary.md` |
| S9 narrate + verify | `narrate.py`, `verify.py` | `candidates.json` | `narratives.json` |

Existing: `load.py` done and verified (815 invalid MMSIs quarantined); `pair.py` written, not run.

---

## 8. Output contract (what the frontend and the narrator consume)

`candidates.json` is a list of objects with this shape. Field names are stable; the frontend owner builds against this.

```json
{
  "candidate_id": "t0-3f9a1c2b7d4e",
  "tier": 0,                         // 0 paired-dark, 1 one-sided, 2 standard, "1u" unpaired loiter
  "label": "investigate",
  "evidence_tier": "bilateral_rendezvous_plausible",
  "priority": 0.87,
  "vessels": [
    {"mmsi": "412331147", "flag": "CHN", "class": "squid_jigger", "role": "fishing",
     "identity_confidence": "resolved", "flag_card": "none", "rfmo_authorized": true, "iuu_listed": false},
    {"mmsi": "416004105", "flag": "TWN", "class": "squid_jigger", "role": "fishing",
     "identity_confidence": "resolved", "flag_card": "yellow", "rfmo_authorized": true, "iuu_listed": false}
  ],
  "window": {"start": "2017-07-01T04:12:05Z", "end": "2017-07-02T22:00:48Z", "overlap_hours": 41.8},
  "geometry": {
    "endpoints": [{"mmsi": "412331147", "off": [42.71, 162.03], "on": [42.55, 162.41]},
                  {"mmsi": "416004105", "off": [42.66, 162.09], "on": [42.58, 162.38]}],
    "meeting_point": {"lat": 42.64, "lon": 162.2, "kind": "inferred"},   // "observed" for T1/T2
    "reachable_set": {"type": "Polygon", "coordinates": []},
    "jurisdiction": {"zone": "high_seas", "rfmo": "NPFC", "eez_entry_while_dark": false}
  },
  "scores": {"geom": 0.92, "kin": 0.81, "beh": 0.35, "ctx": 0.40, "cor": 0.60,
             "den": 0.10, "flt": 0.00, "cov": 0.05},
  "features": {"start_distance_km": 6.6, "start_delta_min": 0.08, "end_distance_km": 4.1,
               "end_delta_min": 0.72, "required_speed_kn": 2.3, "joint_dwell_hours": 36.4,
               "local_null_p": 0.002, "local_dark_count": 3, "component_class": "bilateral",
               "sequential_mmsi": false, "risk_port_reach_hours": 0, "known_partners": 0},
  "corroboration": {"viirs_state": "uncorrelated_detection", "viirs_uncorrelated_count": 2,
                    "viirs_min_km_to_meeting_point": 3.1, "sar_state": "no_coverage"},
  "neighbours": [{"mmsi": "577101000", "flag": "VUT", "delta_min": 41, "distance_km": 88}],
  "explanations": ["Both vessels ceased AIS within 5 s at 6.6 km separation.",
                   "Only 3 other vessels dark within 200 km and 1 h; local null p = 0.002.",
                   "Taiwan held an EU IUU yellow card on this date."],
  "sources": [{"claim": "off_time_a", "value": "2017-07-01T04:12:05Z", "source": "GFW disabling corpus", "as_of": "2022-08-08"}],
  "analyst_disposition": null
}
```

`evidence_ledger.parquet` holds one row per claim with source, retrieval time, and tolerance, and is what the verifier checks against.

---

## 9. Narration and verification (agent-trust feature)

An LLM writes the per-candidate assessment from the candidate object only. A verifier extracts every factual span (identifier, timestamp, position, distance, duration, count, score, null name) and checks it against the evidence ledger with tolerances measured from the corpus: ±1000 m on shore distance, ±0.017 h on duration, "estimated" badge required on length and tonnage. Each span renders `verified`, `contradicted`, or `unverifiable`, with eight `unverifiable` reason codes. A statistical claim that does not name its null is `unverifiable`. Adversarial mode corrupts the record, not the prompt, and the verifier must catch it. Narratives for the top 20 are precomputed; the live button runs one on demand.

---

## 10. Limits stated in the product

- Fishing vessels only in D1; carriers only if D2 arrives. No tankers. The method is the Oxford paper's; the tanker evidence is theirs.
- No coordinate-level ground truth. WCPFC found 78% of AIS-only transshipment candidates unsubstantiated; the number is shown.
- T0's meeting point is inferred and drawn as a heuristic. T1 and T2 meeting points are observed.
- Detection is retrospective for T0 and T1: both gaps must close before a pair can form.
- Level 3 kinematics from the paper (detour, speed variability) need tracks and are absent unless D13 arrives.

---

## 11. Open questions for the team

1. Does GFW's gap dataset cover carriers and reefers (D2)? This decides whether fishing–carrier candidates exist at all.
2. Are raw tracks obtainable for even the top 20 vessels (D13)? This decides whether T2 is ingested or computed, and whether kinematic features exist.
3. Years in scope: 2017–2019 only, or also recent years through the GFW API with separate versioning?
4. Which LLM for narration, and is the verifier in scope for the pitch?
5. Should T1u (loitering without a partner) appear in the queue at all, or only as map context?
