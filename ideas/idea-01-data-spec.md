# Dark Rendezvous — data and prediction specification

## 1. Purpose and operational boundary

Dark Rendezvous is a **maritime domain awareness (MDA)** system that turns AIS
silence into a ranked, auditable queue of events for an analyst. Its initial
use is post-event intelligence: identify dark periods that merit imagery review,
vessel-history review, or referral to the appropriate maritime authority.

It is **not** an assertion that a transfer occurred, a finding of illegal
activity, or a real-time maritime interdiction cue. The two-vessel hypothesis
cannot be formed until both vessels return to AIS. SAR and other enrichment may
arrive later still.

The operational claim is deliberately narrower:

> Given two qualifying AIS-off events, how strongly does the available,
> time-valid evidence support prioritising this pair as a possible bilateral
> dark rendezvous rather than a coincident gap, fleet-level coordinated dark
> activity, or a reception artefact?

That creates an MDA product now and a defensible foundation for a later,
separate, one-ended alerting model. The latter would need live collection,
patrol/sensor availability, and outcome labels; it must not be implied by the
retrospective model.

## 2. Define the unit before defining the model

There are three different records. They must not be conflated.

| Record | Grain | Meaning | Is it a prediction? |
| --- | --- | --- | --- |
| `gap_event` | one vessel, one AIS-off interval | A GFW-qualified intentional AIS disabling event | No — source observation/estimate |
| `pair_candidate` | two gap events | A pair satisfying a pre-registered two-ended timing and distance rule | No — detection rule |
| `rendezvous_assessment` | one pair candidate, versioned at an as-of time | Evidence, uncertainty, and analyst priority for a possible bilateral rendezvous | Yes — ranking/assessment |

The model predicts on `pair_candidate`, not on individual AIS pings and not on
an imagined exact meeting coordinate. Its output is:

```
analyst_priority_score ∈ [0, 1]
evidence_tier ∈ {coincidence_or_artifact, coordinated_fleet_activity,
                 bilateral_rendezvous_plausible, imagery_corroborated}
```

`imagery_corroborated` means imagery supports the candidate; it does **not**
mean that a transshipment or any crime was confirmed. Spelling in the physical
schema is **`imagery_corroborated`**.

## 3. The hypothesis and the “intersection” question

The only direct observation is this:

```
vessel A: last AIS at a0 ---- dark ---- first AIS at a1
vessel B: last AIS at b0 ---- dark ---- first AIS at b1
```

The system must never render an exact point of contact. Instead it constructs a
**feasible joint rendezvous region**: water each vessel could plausibly have
reached after switching off *and* departed in time to make its first subsequent
AIS position.

For vessel `v` and candidate time `t`, define the feasible region:

```
R_v(t) = water_mask ∩ disk(start_v, Vmax_v × (t - t_off_v))
                   ∩ disk(end_v,   Vmax_v × (t_on_v - t))
```

where `Vmax_v` is a conservative vessel-specific upper speed, clipped to a
documented fallback by vessel class. Calculate this over a time grid (for
example, every 30 minutes), and take the union of overlaps:

```
F_AB = union_t [ R_A(t) ∩ R_B(t) ]
```

`F_AB` is the correct object to call the possible-intersection area. It is a
geographic uncertainty polygon, often large. Features derived from it include:

- `feasible_overlap_hours`: number of time steps with non-zero overlap;
- `min_feasible_distance_km`: closest approach permitted by the two envelopes;
- `feasible_area_km2` and `feasible_area_fraction_of_local_ocean`;
- `centerline_separation_km`: separation of straight-line interpolations,
  labelled clearly as a visual heuristic, never a reconstructed track;
- `sar_in_feasible_region`: a time-and-space join to a radar observation;
- `land_or_restricted_water_fraction`: geometry quality / implausibility flag.

The current baseline detector remains simpler and reproducible: start positions
within 10 km and 1 hour, return positions within 10 km and 1 hour, then
cross-flag and local-density conditioning. Feasibility geometry is an
enrichment and ranking signal; it should not silently replace that calibrated
baseline.

## 4. Source inputs and normalized contracts

All source rows retain source name, source primary key, retrieval timestamp,
dataset version, and raw payload location. We must be able to reproduce an
assessment from exactly the data that was available at its `as_of_time`.

### 4.1 Required: AIS gap-event table

**Bootstrap source:** Global Fishing Watch’s 2017–2019 AIS-disabling corpus.
**Current source:** GFW Events API,
`public-global-gaps-events:latest`, filtered to intentional, closed events.

The raw source qualifies gaps with its own coverage and duration criteria. We
store GFW's `intentional` designation as source provenance, not as independent
ground truth. Current events are valuable but the endpoint is described by GFW
as prototype, so old and new cohorts must be versioned and evaluated separately.

Minimum normalized schema:

| Field | Type | Notes |
| --- | --- | --- |
| `gap_id`, `source_event_id` | string | Stable internal/source identifiers |
| `vessel_id`, `mmsi_raw`, `imo` | string | Keep raw ID and resolved identity separately |
| `off_time`, `on_time` | UTC timestamp | Exact source timestamps, never local time |
| `off_lat`, `off_lon`, `on_lat`, `on_lon` | float | WGS84; preserve precision and source uncertainty |
| `duration_hours_source`, `duration_hours_exact` | float | Do not overwrite the reported/rounded duration |
| `intentional_flag`, `is_closed` | boolean | Source-provided status |
| `vessel_class`, `flag_at_event` | string | Time-valid source values |
| `length_m`, `tonnage_gt`, `field_provenance` | nullable | Mark estimates as estimates |
| `distance_to_shore_off_m`, `distance_to_shore_on_m` | float | Source values if present; derived values separately |
| `dataset_version`, `retrieved_at` | string/timestamp | Reproducibility |

Quarantine malformed/ambiguous MMSIs from identity and pair training, while
keeping them visible to an analyst as `identity_unresolved`.

### 4.2 Required: vessel identity and role

Use GFW Vessel API identity records and public registry fields to resolve
time-valid vessel role and aliases. The model needs roles such as fishing,
carrier, support, bunker, and unknown — not only a current flag.

Key fields: `gfw_vessel_id`, all known MMSIs/IMO/callsigns, vessel type and
gear type, length/tonnage, flag history, registry owner(s), public
authorizations, identity confidence, and effective date ranges.

Join rule: first resolve each `gap_event.vessel_id` to `gfw_vessel_id`; then
select only identity attributes whose effective interval contains `off_time`.
Never join a later owner or flag change backward into training history.

### 4.3 Required for current MDA: local context and alternate explanations

Create spatial-temporal aggregates from the same gap table before joining them
to pairs. This prevents a candidate from looking rare merely because its
neighbours were ignored.

| Derived input | Window / join | Why it matters |
| --- | --- | --- |
| `local_gap_count` | other gaps within 200 km and ±1 h at shutoff/return | Reception hole or fleet-wide dark time |
| `local_unique_vessel_count` | same | Density-normalised pair surprise |
| `same_flag_share`, `sequential_mmsi_share` | same | Fleet clique indicator |
| `component_size` | graph of contemporaneous dark gaps | Separate coordinated fleet activity from a pair |
| `historical_pair_count` | only dates before candidate | Repeated bilateral association |
| `regional_baseline_rate` | spatial cell × month, fitted on prior data | Seasonality and fishing-ground control |

The pair's own two events are excluded from density counts. All aggregate
windows and spatial indexing parameters are configuration, logged with the
model version.

### 4.4 High-value corroboration: SAR vessel detections

Use GFW Sentinel-1 SAR vessel-detection data. The primary signal is an
AIS-unmatched detection, with the acquisition time, point/footprint,
classification, confidence, and matching status retained.

Join rule:

1. Only consider acquisitions whose timestamp falls inside both vessels’ dark
   interval, or record the one-sided case separately.
2. Buffer the detection by documented location uncertainty and test intersection
   with `F_AB` at that acquisition time.
3. Persist both positive and negative coverage: `sar_observed=true/false` and
   `sar_coverage_quality`. **No detection is not evidence of absence** unless
   there was usable SAR coverage.
4. Do not assign an unmatched SAR point to vessel A or B. It corroborates that
   an unbroadcasting vessel was in the feasible region; it does not identify it.

Useful features are `sar_unmatched_count`, `min_sar_distance_to_feasible_km`,
`sar_time_offset_minutes`, `sar_coverage_quality`, and detection class. Do not
use post-event human labels embedded in a commercial imagery workflow as
features for a model evaluated against those labels.

### 4.5 Behavioral and jurisdictional context

Join GFW event and context layers by vessel ID plus time/geometry:

- prior and subsequent **encounters**, **loitering**, **apparent fishing**, and
  **port visits**;
- EEZ, high-seas, RFMO, MPA, and distance-to-port/anchorage geometry;
- public authorization status where available;
- IUU-list / risk-network indicators, with an effective date before the
  candidate only.

These inputs support both MDA triage and maritime-interdiction planning: the
relevant authority/jurisdiction, vessel role, and likely follow-on port can be
shown to an analyst. They do not establish legal authority or probable cause.

### 4.6 Optional physical-context layer

Add weather, sea state, currents, and daylight only after the core pipeline is
working. They are useful to assess feasibility and explain false positives, but
they will not rescue a weak pair hypothesis. Sample gridded values along
`F_AB`/time rather than treating a gap endpoint as the meeting point.

## 5. Building pair candidates

### 5.1 Eligibility

For each `gap_event` retain only records that are closed, intentional according
to the selected source, outside the source's exclusion zone, within a defined
duration range, and have usable start/end coordinates and valid resolved vessel
identity. Record every exclusion reason.

### 5.2 Blocking and pairing

1. Bucket eligible starts by time (one hour) and spatial cell large enough to
   include the 10 km radius at its latitude.
2. Compare only neighbouring buckets; calculate haversine start distance and
   time difference exactly.
3. For start matches, test the return-position distance and return-time
   difference.
4. Canonicalize the pair as ordered `min(gap_id), max(gap_id)` and generate a
   deterministic `pair_id`.
5. Attach the local context calculated without the pair itself.

The resulting candidate includes source measurements, not inferred tracks:

| Candidate field | Definition |
| --- | --- |
| `start_distance_km`, `start_delta_minutes` | Gap-off endpoint relationship |
| `end_distance_km`, `end_delta_minutes` | Gap-on endpoint relationship |
| `dark_overlap_hours` | Interval intersection length |
| `duration_ratio`, `duration_delta_hours` | Similarity of dark windows |
| `pair_flag_relation` | same / cross / missing, time-valid |
| `pair_role_relation` | fishing–carrier, fishing–fishing, etc. |
| `local_density_features` | Section 4.3 results |
| `baseline_surprise` | Observed frequency relative to a local conditioned null |

### 5.3 Separate candidate classes before ranking

Classify the graph component first:

- `bilateral`: component size 2 or a pair materially isolated from nearby gaps;
- `fleet_cluster`: large same-flag/sequential-MMSI component;
- `regional_blackout`: unusually dense multi-vessel event with weak pair
  specificity;
- `unresolved`: missing identity or insufficient context.

Only `bilateral` and selected `unresolved` candidates enter the bilateral
rendezvous queue. Fleet clusters remain first-class MDA outputs — coordinated
dark activity is itself operationally interesting — but must not be presented
as a vessel-to-vessel meeting.

## 6. Labels: what we can honestly learn

There is no public coordinate-level table of confirmed illicit transshipments.
Therefore **do not train a binary model labelled “actual dark rendezvous.”**
The current corpus supplies observations and a statistical null, not truth.

Use a staged label design:

| Label | Origin | Permitted use |
| --- | --- | --- |
| `candidate_detected` | fixed pair rule | Reproducible baseline only; not a truth label |
| `coordinated_pattern` | graph/density rules + analyst review | Routing between fleet and bilateral queues |
| `sar_corroborated` | pre-specified SAR overlap test | Evidence tier / weak label, not confirmed identity |
| `convergent_behavior` | independently generated event sequence, e.g. carrier loitering | Weak positive evidence |
| `analyst_disposition` | blind human review rubric | Primary supervised ranking label once collected |
| `verified_outcome` | authoritative inspection, imagery, enforcement, or partner report | Gold label, retained with evidence and jurisdiction |

Initial scoring should therefore be a transparent weighted evidence model plus
the calibrated local null. After enough independently reviewed candidates,
train a learning-to-rank model to predict `analyst_disposition`, not a crime.
Hold final outcome labels aside for external evaluation.

Suggested analyst rubric:

- **0 — close / artifact:** coverage or fleet explanation dominates;
- **1 — monitor:** paired gap survives basic checks but lacks corroboration;
- **2 — investigate:** bilateral, locally surprising, physically feasible, and
  at least one independent behavioral or imagery signal;
- **3 — refer:** evidence package meets the receiving authority's documented
  referral threshold. This is a workflow state, not a legal conclusion.

## 7. Time validity and leakage controls

Every assessment has an `as_of_time` and a source ledger. Features must be
available on or before that time.

| Scoring stage | Earliest possible time | Permitted information |
| --- | --- | --- |
| `S0: one vessel goes dark` | first `off_time` | One-ended history only; separate future product |
| `S1: pair formed` | max(A.on_time, B.on_time) | Both gap endpoints, prior history, local density |
| `S2: enriched assessment` | after sensor/API availability | SAR/event/registry data actually retrieved by then |
| `S3: outcome evaluation` | after disposition/outcome | Never fed back into the S1/S2 feature set |

Training and evaluation use chronological splits, then geographic holdouts by
ocean region and vessel/owner-group holdouts. A random row split would leak
repeat vessels, repeated pairings, and seasonal fishing-ground patterns.

The baseline null is fit only on periods preceding the assessment. Its local
permutation preserves month, region, vessel class, and local-density stratum;
the report must state the chosen null model beside every surprise score.

## 8. Deliverables and acceptance checks

1. `gap_events.parquet`: normalized, versioned source table with a data
   dictionary and exclusion ledger.
2. `pair_candidates.parquet`: deterministic pair output, fixed threshold
   configuration, local-density fields, and component class.
3. `feasible_regions.geojson/parquet`: versioned polygons plus the speed and
   water-mask assumptions used to produce them.
4. `evidence_ledger.parquet`: one row per claim/input, source, retrieval time,
   spatial/temporal join result, and uncertainty.
5. `assessments.parquet`: score, evidence tier, explanation, `as_of_time`,
   model/rules version, and analyst disposition when available.

The build is acceptable only if it can demonstrate all of the following:

- rerunning on the frozen 2017–2019 corpus reproduces the fixed pair set and
  local-conditioned null result;
- no display calls `F_AB` a track or a meeting location;
- SAR absence is distinguished from lack of SAR coverage;
- a large local same-fleet component routes to fleet activity rather than a
  bilateral rendezvous;
- an assessment can show exactly which inputs were known at `as_of_time`;
- all model language says *candidate*, *possible*, or *corroborated*, never
  *confirmed transfer* without an authoritative outcome record.

## 9. Source implementation notes

GFW's current Events API exposes gap, encounter, loitering, fishing, and port
visit events; its Vessel API joins AIS and more than 40 public registries. The
SAR product includes AIS-matched/unmatched detections. API access needs a GFW
token and is limited to non-commercial use, so cache raw responses and retain
the data-use terms with the run.

Useful source references:

- [GFW Events API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/events)
- [GFW data caveats for AIS gaps](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/data-caveats)
- [GFW SAR / AIS-presence dataset documentation](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/v3/4wings)
- [GFW Vessel API](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/v3/vessels)
- [GFW IUU-risk dataset](https://zenodo.org/records/20534811)
