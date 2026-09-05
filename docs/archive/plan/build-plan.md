> **Archived 2026-09-05.** Historical planning/handoff document for wake.ai. Superseded by [docs/candidate-pipeline.md](../../candidate-pipeline.md), [docs/status.md](../../status.md) and [docs/data.md](../../data.md). Status claims, branch advice and any schedules in this file are stale and must not be acted on.

# GapPair — backend design

**Scope:** detection, scoring, corroboration, and the data contract the frontend consumes. UI is owned separately (`frontend-notes.md`). Research and references are in `research-notes.md`.

**Claim we build toward:** GapPair turns AIS silence and AIS behaviour into a ranked, auditable queue of rendezvous candidates across three visibility tiers, with every score component shown and a calibrated chance baseline where the meeting is inferred rather than observed. It never asserts that a transfer or a crime occurred.

**Repo status (accurate as of this revision):** no backend module exists. The earlier `pipeline/` scaffold was deleted. `data/raw/disabling_events.csv` is on disk; `data/derived/exclusions.json` is a checkpoint from the deleted loader; everything else in `data/derived/` is stale and gitignored. The venv has pandas 3.0.5, numpy, pyarrow, scipy, scikit-learn, and no HTTP client or geometry library. No GFW token, no EOG account.

---

## 0. Build scope

What ships for the demo, and what is designed but not built. Everything in the second column is still specified below so the pitch can describe it honestly and the next build can pick it up.

| Ships | Designed, not built |
|---|---|
| **T0 paired-dark** from the on-disk corpus, operating rule plus loose rule | T1 one-sided (needs GFW loitering events and a token) |
| **One null**: within-cell permutation, 200 draws | T2 standard (needs GFW encounters and a token) |
| Local context, components, identity-twin check from corpus fields | Level 1 context from GFW identity (authorizations, owner, build year); flag carding and IUU list are static tables and **do** ship |
| Scorecard, labels, evidence tiers, explanations | Reception-quality penalty (D10), raw tracks (D13), SAR (D14) |
| **Precomputed** `risk-events.json` served statically; no live API | Live `/risk-events` endpoint |
| **VIIRS for the showcase pair only**, after coverage is verified | VIIRS for the full top-30 |
| Narration + verifier for the top 20, precomputed, one live adversarial run | |

---

## 1. Detection tiers: divide the cases by what AIS can see

| Tier | Visible | Signature | Documented rule we cite | Candidate source | Meeting point | Status |
|---|---|---|---|---|---|---|
| **T2 standard** | both | proximity, low speed, sustained duration | GFW encounter: 500 m, ≥2 h, median <2 kn, ≥10 km from anchorage (Miller et al. 2018). Skylight: 250 m, ≥30 min, <4 kn, >10 km from coast | GFW `ENCOUNTER` events | observed | designed |
| **T1 dark, one-sided** | one | a **carrier** loiters as if meeting; a fishing vessel has a gap whose reachable set covers that place and time | Skylight Dark Rendezvous: ≥15 min rendezvous-like behaviour, not within 100 km of shore. GFW loitering: <2 kn, ≥20 nm from shore | GFW `LOITERING` (carrier events only) joined to gaps by feasibility | observed (the loiterer's position) | designed |
| **T0 paired dark** | neither | two gaps that start together and end together, with a joint reachable set | none published; Oxford Alg. A.2 is the only precedent for two simultaneously dark vessels | gap × gap pairing | inferred (joint reachable set) | **ships** |

GFW loitering is a carrier-vessel event, so T1 is exactly carrier-loiter × fishing-gap, and the loiter feature is null for every fishing–fishing T0 pair. Loitering events with no feasible gap partner are **not queue items**; they would be every carrier loitering event on earth. They may appear as map context only.

T2 is Skylight's Standard Rendezvous, T1 is its Dark Rendezvous, T0 is the row Skylight does not have. Skylight builds its one-sided model from two-sided events by hiding one vessel (`create_osr_dataset.py` in `allenai/atlantes`); we go one step further and calibrate T0 against the same two-sided events once encounters are available.

Within a tier, candidates split by **component class** (bilateral, fleet cluster, regional blackout, unresolved), **role pair** (fishing–carrier, fishing–fishing, unknown), and **identity status** (resolved, identity-twin, unresolved).

---

## 2. Data requirements

What we need and why. Priority reflects §0.

| # | Data | Fields | Used by | Priority |
|---|---|---|---|---|
| D1 | AIS disabling events 2017–2019 (**on disk**, 55,368) | mmsi, class, flag, off/on time, off/on lat/lon, shore distance both ends, gap hours, length, tonnage | T0, all features | P0 |
| D9 | Risk lists as static tables: EU IUU carding history (flag, colour, start, end), combined RFMO IUU vessel list (name, MMSI, IMO, dates), PSMA party list | joins on `flag` and `mmsi` | `context_risk` | P0 |
| D8 | Static geography: EEZ polygons, RFMO convention areas, a port list (GFW anchorages or Natural Earth) | point-in-polygon on endpoints; nearest port | `eez_entry_while_dark`, RFMO area, A.1 port reach | P0 (RFMO and EEZ), P1 (ports) |
| D11 | VIIRS boat detections (NOAA EOG VBD) for the **showcase night(s)**: 2017-07-01 to 07-03, box 41–44°N, 160–164°E | lat, lon, timestamp, radiance, quality flag, cloud flag | corroboration | P0 for the showcase pair; P1 for top-30 |
| D3 | GFW `ENCOUNTER` events 2017–2019 for corpus vessels | both vessel ids and types, start/end, position, median distance and speed | T2; `known_partners`; T0 calibration | P1 (token) |
| D4 | GFW `LOITERING` events, same scope, carriers | vessel id, start/end, start/end position, mean speed, shore distance | T1 join; `loiter_bracket` | P1 (token) |
| D5 | GFW `PORT_VISIT` events, same scope | vessel id, port, country, start/end | `port_after_gap`, A.1 risk port | P1 (token) |
| D7 | GFW vessel identity for the ~5,100 corpus MMSIs | aliases with dates, type and gear, flag history, owner, build year, RFMO authorizations with dates | identity resolution, role pair, Level 1 | P1 (token; one-time cached job) |
| D2 | GFW gap events for carriers and reefers | as D1 plus type | fishing–carrier T0 | P1, **open**: public docs do not say whether the gap dataset includes carriers; one events call filtered to a known carrier id answers it |
| D12 | AIS presence for VIIRS nights and boxes | cell or position, time, count | AIS-correlation of lights | P1; fallback is the corpus' own broadcasting endpoints within ±1 h |
| D6 | GFW `FISHING` events | vessel id, start/end, position | fishing-ground alternative explanation | P2 |
| D10, D13, D14 | reception quality raster, raw tracks, SAR detections | | coverage penalty, kinematics, SAR corroboration | **deferred** |

GFW terms: CC BY-NC 4.0, attribution must be visible in the UI; limits of 50,000 requests/day and roughly 2,800 vessel ids per events request are not binding for us. VIIRS: EOG VBD has a global product behind a free account, but its page says global coverage is selected areas and South America is redacted. **Download the showcase night before building the layer**; if the box is not covered, the corroboration panel reads `no_coverage` and the pitch says so.

---

## 3. Shared primitives

### 3.1 Reachable set and dwell time

For a gap `G` with shutoff `(p0, t0)`, reappearance `(p1, t1)`, and class maximum speed `V` in knots. All distances in km, all durations in hours, and **`V_km = 1.852 · V`**.

```
L(p)      = D(p0, p) + D(p, p1)                 detour distance through p, km
dwell(p)  = (t1 − t0) − L(p) / V_km             longest possible stay at p, h
arrive(p) = t0 + D(p0, p) / V_km                earliest arrival at p
depart(p) = t1 − D(p, p1) / V_km                latest departure from p
```

`p` is feasible for a rendezvous of minimum length `τ_min` iff `dwell(p) ≥ τ_min`. The reachable set `{p : L(p) ≤ V_km · (t1 − t0 − τ_min)}` is an ellipse with foci `p0`, `p1` in a local planar frame; its boundary is sampled analytically (64 points), so no geometry library is needed. Oxford Alg. A.2's required speed at the overlap midpoint is the special case with zero dwell.

Defaults: `τ_min = 1 h`. `V` by class: squid jigger 12 kn, drifting longline 12, trawler 13, tuna purse seine 16, other fishing 14, carrier or reefer 18, unknown 16. Config, not code.

### 3.2 Joint feasibility for two vessels

`τ_AB(p) = min(depart_A(p), depart_B(p)) − max(arrive_A(p), arrive_B(p))`. Feasible iff `max_p τ_AB(p) ≥ τ_min`; `p* = argmax_p τ_AB(p)` is the **feasible meeting point**, from a coarse grid over the endpoints' bounding box plus margin, then local refinement. Outputs `p*`, `joint_dwell_hours`, `required_speed_kn`, and the two reachable-set rings.

### 3.3 Kinematic plausibility

`kin_plausibility = clip(1 − required_speed_kn / V, 0, 1)` and the Oxford percentile form. **Not used in operating T0 scoring**: at 10 km / 1 h over 12 to 40 h gaps the median plausibility is 0.94 and carries no information. It is a gate and a feature for loose-rule T0 pairs and for T1, where the meeting point is observed and required speed is informative.

### 3.4 Local context

Per pair, excluding its own two events: `local_dark_count` and `local_unique_vessels` within 200 km and ±1 h at shutoff and at reappearance; `local_same_flag_share`, `local_sequential_share`; components over operating pairs giving `component_size` and `component_class`; `gap_unusualness` as the gap's percentile within the vessel's own gap history; `repeat_rate`. Local density is a **penalty only**; it is not a null.

### 3.5 Null model (one, shipped)

**Within-cell permutation.** Permute gap start times among events in the same 5° cell, keep durations and positions, rerun the pairing, `N = 200` draws. Reports the lift at every threshold on the ladder. Per candidate, the geometry term uses the candidate's **cell-month**: `p_cell = (1 + #draws with pair count ≥ observed in that cell-month) / (1 + N)`, with the pseudo-count so the minimum is `1/201`. A crowded ground where the null also produces many pairs gets a weak geometry term; an isolated ground gets a strong one.

Dropped: the per-candidate local permutation. With three events in the neighbourhood the permutation keeps the pair matched in most draws and the most isolated pairs score near zero, which is backwards.

A lift of exactly 1.00× is the signature of a broken null and fails the run.

---

## 4. Candidate generation

### 4.1 T0 paired dark (ships)

Operating rule, deterministic and pre-registered: different MMSIs, both valid (9 digits, MID 201–775); shutoffs within 10 km and 1 h; reappearances within 10 km and 1 h; dark intervals overlap. Blocked by a sliding window on shutoff time plus vectorised haversine; validated against brute force on a 1,500-event subsample. Canonical `pair_id` from the sorted gap ids.

Loose rule for recall: intervals overlap, shutoffs within 50 km and 6 h, reappearances within 50 km and 6 h, **and** joint feasibility from 3.2. Loose-only candidates rank below operating candidates unless corroborated, and their kinematic term is active.

Threshold ladder for the methods drawer: start-only 50 km / 24 h and 5 km / 1 h; both-ends 25 km / 3 h, 10 km / 1 h, 5 km / 1 h, 2 km / 30 min. Prior runs gave 434–437 operating pairs at roughly 35× the within-cell null and 27 cross-flag pairs at roughly 22×; the build re-runs these and the pitch quotes the re-run.

### 4.2 T1 dark, one-sided (designed)

For each carrier loitering event `L` (vessel `v_L`, window `[l1, l2]`, centroid `q`) and each fishing gap `G` of a different vessel with **gap length ≤ 7 days** whose interval overlaps `[l1, l2]`:

1. Spatial gate in km: `D(p0_G, q) ≤ V_km,G · (l2 − t0_G)` and `D(q, p1_G) ≤ V_km,G · (t1_G − l1)`.
2. Feasibility: `overlap = min(depart_G(q), l2) − max(arrive_G(q), l1) ≥ τ_min`.
3. Emit `(v_L, v_G)` with `overlap_hours`, `required_speed_kn`, and the loiterer's event fields.

The 7-day cap exists because over a thousand corpus gaps exceed 30 days and sixty exceed 180; at 12 kn a 30-day gap reaches 16,000 km and joins every loiterer on the planet. `t1_join_count` feeds the density penalty.

### 4.3 T2 standard (designed)

Ingest D3 as-is; GFW already applied the rule. Deduplicate mirrored records. Rank only within T2.

---

## 5. Features and scoring

All tiers share the feature families. Missing inputs are null, never zero, and the explanation names what was missing.

| Family | Features | Ships |
|---|---|---|
| Geometry | start/end distance and delta, overlap hours, duration ratio, `p_cell` | yes |
| Kinematics | `p*`, `joint_dwell_hours`, `required_speed_kn`, `kin_plausibility` | yes (loose pairs only in score) |
| Behaviour | `loiter_bracket`, `encounter_bracket`, `known_partners`, `port_after_gap`, `fishing_ground_context` | needs token; null until then |
| Context | `cross_flag`, `flag_card_a/b`, `rfmo_area`, `rfmo_authorized_a/b`, `iuu_listed_a/b`, `port_risk`, `eez_entry_while_dark`, `role_pair` | cross-flag, carding, IUU list, RFMO area, EEZ: yes; authorizations and role: token |
| Risk-port reach | `risk_port_reach_hours` (3.1 with `τ_min = 2 h` at the nearest risk port), `possible_port_transit` | with D8 ports |
| Corroboration | `viirs_state`, `viirs_uncorrelated_count`, `viirs_min_km_to_p*` | showcase pair |
| Confounders | `local_dark_count`, `component_class`, `local_same_flag_share`, `sequential_mmsi`, `identity_twin`, `gap_unusualness`, `repeat_rate` | yes |

**Term definitions, each in [0, 1]:**

```
S_geom = clip(−log10(p_cell), 0, 2) / 2
S_beh  = 0.5·bracket(loiter or encounter) + 0.3·(role_pair == fishing–carrier) + 0.2·port_after_gap_risk
S_ctx  = 0.3·cross_flag + 0.3·flag_card(any) + 0.2·not_authorized(any) + 0.1·iuu_listed(any) + 0.1·port_risk
S_cor  = 1.0 if viirs_state == uncorrelated_detection else 0     (clear_no_detection is explained, not scored)
S_kin  = kin_plausibility for loose pairs and T1; 0 weight for operating T0
S_den  = clip(log10(1 + local_dark_count) / 2, 0, 1)
S_flt  = max(component_class == fleet_cluster, sequential_mmsi, identity_twin, local_same_flag_share > 0.8)
S_hab  = 1 − gap_unusualness                                     habitual gaps for this vessel
```

**Score.** No tier bias; tiers are ranked separately and the global view sorts by evidence tier, then priority.

```
raw      = 0.30·S_geom + 0.15·S_kin + 0.20·S_beh + 0.15·S_ctx + 0.20·S_cor
         − 0.15·S_den − 0.20·S_flt − 0.10·S_hab
priority = sigmoid(6 · (raw − 0.30))          "analyst priority", never a probability of wrongdoing
```

Worked range with these defaults: the showcase pair with an uncorrelated VIIRS light scores about 0.77; the same pair with no VIIRS coverage about 0.51; a same-flag sequential-MMSI fleet pair on a crowded ground about 0.10. Weights are choices, not fits, and the methods drawer says so. `analyst_disposition` returned by the frontend is the first label we collect.

**Labels** (dominant term, then threshold): `investigate` when priority ≥ 0.5, component bilateral, and no penalty term above 0.5; `coordinated-fleet-pattern` when `S_flt` dominates; `identity-twin` when both sides share class, flag, length, and tonnage or have sequential MMSIs (181 of 434 operating pairs match the former, 173 the latter; these are one hull on two identities until the identity join says otherwise); `likely-coverage-or-cluster-artifact` when `S_den` dominates; `possible-port-transit` when the generic-port geometry holds; `insufficient-evidence` when identity is unresolved or required fields are missing.

**Evidence tier** (what has been checked, monotone): `coincidence_or_artifact` → `coordinated_fleet_activity` → `bilateral_rendezvous_plausible` → `behaviour_corroborated` (T2, or a bracket) → `imagery_corroborated`.

---

## 6. Corroboration (showcase pair first)

Join D11 to the joint reachable set during the dark window. A light counts only if no broadcasting vessel explains it; without D12 the correlation test uses the corpus' own broadcasting endpoints within ±1 h and 5 km. Output is three-state and coverage-aware: `uncorrelated_detection`, `correlated_only`, `clear_no_detection`, `no_coverage`. For squid jiggers, `clear_no_detection` is reported as "lights off", never as absence. Verify EOG coverage of the showcase box before writing any of this. SAR is deferred.

---

## 7. Correctness rules for any new code in this venv

- **pandas 3 timestamps parse to microseconds**, not nanoseconds (`datetime64[us, UTC]` confirmed on the corpus). Never divide an int64 view by a constant; use `(t1 − t0) / pd.Timedelta(hours=1)`.
- **Units.** Speeds in knots, distances in km, durations in hours. `km = kn · h · 1.852`. Haversine with R = 6371 km.
- **Dateline.** 452 events straddle 180°. Build 5° cells with `floor((lon + 180) / 5) mod 72` so the boundary wraps; compute reachable sets in a local frame around the pair midpoint; normalise output longitudes to [−180, 180]; when a pair's bounding box crosses ±180, set `geometry.dateline = true` and omit the polygon rather than draw one. Only one operating pair is affected; the goal is not crashing.
- **Identity.** Quarantine invalid MMSIs; flag identity twins (§5); keep raw MMSI and resolved identity as separate fields.
- **Nulls with pseudo-counts.** No `log(0)`.
- **GFW attribution** text and the CC BY-NC notice go into the exported file so the frontend can render them.

---

## 8. Pipeline stages and files

Python in `pipeline/` (to be created), messy is fine, every stage reruns from files. Dependencies to add: `httpx` for GFW. No shapely.

| Stage | Module | Reads | Writes |
|---|---|---|---|
| S1 normalise | `load.py` (+ `events.py`, `identity.py` when D3–D7 exist) | D1, D8, D9 | `gap_events.parquet`, `exclusions.json` |
| S2 feasibility | `feasibility.py` | S1 | `feasibility.parquet` |
| S3 candidates | `pair_t0.py` (+ `join_t1.py`, `ingest_t2.py`) | S1, S2 | `candidates_t0.parquet`, `pair_grid_counts.json` |
| S4 context | `context.py` | S1, S3 | `local_context.parquet`, `components.parquet` |
| S5 null | `nulls.py` | S1, S3 | `null_results.json` with per-cell-month counts |
| S6 features + score | `features.py`, `score.py` | S1–S5, D8, D9 | `features.parquet`, `scores.parquet` |
| S7 corroboration | `corroborate.py` | D11, S6 | `corroboration.parquet` |
| S8 export | `export.py` | S6, S7 | **`risk-events.json`**, `tracks/<id>.geojson`, `evidence_ledger.parquet`, `summary.md` |
| S9 narrate + verify | `narrate.py`, `verify.py` | S8 | `narratives.json` |

---

## 9. Output contract

Agreed shape for `GET /risk-events` (served as the static file `risk-events.json` for the demo) and `GET /vessels/:id/track`. It keeps every field name the frontend renders today (`id`, `name`, `flag`, `vesselType`, `riskScore`, `riskLevel`, `eventKind`, `eventLabel`, `location`, `lastSeen`, `coordinates`, `evidence[]`, `timeline[]`), so the current UI runs unchanged, and replaces the single-vessel IMO key with a pair. New fields are additive. The frontend adopts them at its own pace.

Conventions: **all coordinates are `[lon, lat]`** (GeoJSON and MapLibre order). All timestamps are ISO-8601 UTC strings; the frontend formats for display. `tier` is a string enum. `riskScore = round(100 · priority)`.

Mapping: `tier` → `eventKind`: `paired-dark` → `dark-period`, `one-sided` → `loitering`, `standard` → `encounter`. `label` → `riskLevel`: `investigate` → `high`; `coordinated-fleet-pattern`, `identity-twin`, `possible-port-transit` → `review`; `likely-coverage-or-cluster-artifact`, `insufficient-evidence` → `watch`.

```json
{
  "id": "t0-3f9a1c2b7d4e",
  "tier": "paired-dark",
  "label": "investigate",
  "evidenceTier": "bilateral_rendezvous_plausible",
  "priority": 0.51,
  "riskScore": 51,
  "riskLevel": "high",
  "eventKind": "dark-period",
  "eventLabel": "Paired AIS dark period",
  "name": "412331147 (CHN) × 416004105 (TWN)",
  "flag": "CHN / TWN",
  "vesselType": "squid jigger / squid jigger",
  "location": "NW Pacific high seas, NPFC area, 892 km from shore",
  "lastSeen": "2017-07-03T12:19:32Z",
  "coordinates": [161.70, 42.57],
  "vessels": [
    {"mmsi": "412331147", "imo": null, "name": null, "flag": "CHN", "vesselClass": "squid_jigger", "role": "fishing",
     "identityStatus": "resolved", "flagCard": "none", "rfmoAuthorized": null, "iuuListed": false},
    {"mmsi": "416004105", "imo": null, "name": null, "flag": "TWN", "vesselClass": "squid_jigger", "role": "fishing",
     "identityStatus": "resolved", "flagCard": "yellow", "rfmoAuthorized": null, "iuuListed": false}
  ],
  "window": {"start": "2017-07-01T18:33:00Z", "end": "2017-07-03T12:19:32Z", "overlapHours": 41.75},
  "meetingPoint": {"coordinates": [161.70, 42.57], "kind": "inferred"},
  "jurisdiction": {"zone": "high_seas", "rfmo": "NPFC", "eezEntryWhileDark": false},
  "scores": {"geom": 1.0, "kin": null, "beh": null, "ctx": 0.6, "cor": 0.0, "den": 0.30, "flt": 0.0, "hab": 0.4},
  "features": {"startDistanceKm": 6.6, "startDeltaMin": 0.08, "endDistanceKm": 9.0, "endDeltaMin": 0.72,
               "requiredSpeedKn": 2.3, "jointDwellHours": 36.4, "pCell": 0.005, "localDarkCount": 3,
               "componentClass": "bilateral", "sequentialMmsi": false, "identityTwin": false,
               "crossFlag": true, "knownPartners": null},
  "corroboration": {"viirsState": "no_coverage", "viirsUncorrelatedCount": 0, "viirsMinKmToMeetingPoint": null},
  "neighbours": [{"mmsi": "577101000", "flag": "VUT", "deltaMin": 41, "distanceKm": 88}],
  "evidence": [
    {"id": "sync-off", "claim": "Both vessels ceased AIS 5 s apart, 6.6 km apart", "source": "GFW disabling corpus", "observedAt": "2017-07-01T18:33:05Z", "confidence": "high"},
    {"id": "sync-on", "claim": "Both reappeared 43 s apart, 9.0 km apart, after 41.8 h", "source": "GFW disabling corpus", "observedAt": "2017-07-03T12:19:32Z", "confidence": "high"},
    {"id": "null", "claim": "Within-cell permutation null, 200 draws: p_cell = 0.005", "source": "GapPair null model v1", "observedAt": "2017-07-01T18:33:00Z", "confidence": "medium"},
    {"id": "card", "claim": "Taiwan held an EU IUU yellow card on this date", "source": "EU carding history", "observedAt": "2017-07-01T18:33:00Z", "confidence": "high"}
  ],
  "timeline": [
    {"time": "2017-07-01T18:33:00Z", "title": "412331147 last AIS position", "detail": "42.749N 161.983E"},
    {"time": "2017-07-01T18:33:05Z", "title": "416004105 last AIS position", "detail": "42.795N 162.034E", "emphasis": true},
    {"time": "2017-07-03T12:18:49Z", "title": "416004105 reappears", "detail": "42.340N 161.423E"},
    {"time": "2017-07-03T12:19:32Z", "title": "412331147 reappears", "detail": "42.399N 161.347E"}
  ],
  "sources": [{"claim": "window.start", "value": "2017-07-01T18:33:00Z", "source": "GFW disabling corpus", "asOf": "2022-08-08"}],
  "attribution": "Data: Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0",
  "analystDisposition": null
}
```

`GET /vessels/:id/track` returns a GeoJSON `FeatureCollection` for the candidate: four `Point` features for the AIS endpoints with `observationStatus: "observed"`; two dashed `LineString` projections from each shutoff to `p*` and on to each reappearance with `observationStatus: "estimated"`, `confidence: "low"`, `source: "reachable-set heuristic"`; the meeting point as a `Point` marked `estimated`; the two reachable-set `Polygon` rings marked `estimated`, omitted when `dateline` is true. This matches the rule already in `code/backend/README.md` that estimated geometry is never presented as an observed AIS position.

`evidence_ledger.parquet` holds one row per claim with source, retrieval time, and tolerance, and is what the verifier checks against.

---

## 10. Narration and verification (agent-trust feature)

An LLM writes the per-candidate assessment from the candidate object only. A verifier extracts every factual span (identifier, timestamp, position, distance, duration, count, score, null name) and checks it against the evidence ledger with tolerances measured from the corpus: ±1000 m on shore distance, ±0.017 h on duration, "estimated" badge required on length and tonnage. Each span renders `verified`, `contradicted`, or `unverifiable`. A statistical claim that does not name its null is `unverifiable`. Adversarial mode corrupts the record, not the prompt. Top 20 precomputed; one live run behind a button.

---

## 11. Limits stated in the product

- Fishing vessels only; no carriers until D2, no tankers ever in this corpus. The method is the Oxford paper's; the tanker evidence is theirs.
- No coordinate-level ground truth. WCPFC found 78% of AIS-only transshipment candidates unsubstantiated; the number is shown.
- T0's meeting point is inferred and drawn as a heuristic. T1 and T2 meeting points would be observed.
- Detection is retrospective: both gaps must close before a pair can form.
- Kinematics is uninformative at the operating threshold and is not scored there.

---

## 12. Open questions

1. Does GFW's gap dataset include carriers (D2)? One events call with a known carrier id answers it once a token exists.
2. Is the showcase box covered by EOG's global VBD product? Download 2017-07-01/02 before building the layer.
3. Which LLM for narration, and is the verifier in scope for the pitch?
