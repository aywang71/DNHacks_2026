# AIS-first Dark Rendezvous build plan

## Decision

Build an **AIS-first, post-event candidate-triage system**. Its first release
identifies pairs of completed AIS gaps that are jointly feasible, locally
unusual, and worth analyst review. It does not claim to observe a transfer,
reconstruct an exact meeting point, or identify illegal conduct.

Satellite imagery is deliberately an optional evidence layer, not a dependency
of candidate generation. This gives us a useful, reproducible product with the
public GFW gap corpus and avoids downloading or training on multi-terabyte
imagery before the AIS logic is validated.

The system produces:

- a deterministic set of pair candidates;
- a feasible joint region, not an inferred track;
- a transparent score and alternative-explanation flags;
- an evidence ledger that can later include imagery observations; and
- an analyst-ready assessment labelled as a *candidate*.

## Product boundary

There are two related workstreams that must stay separate:

| Workstream | Unit of analysis | Earliest input | Claim |
| --- | --- | --- | --- |
| Dark Rendezvous | Pair of closed AIS-off events | Public GFW gap corpus | A pair merits analyst review |
| Fernández methodological reimplementation | Raw AIS trips, then vessel-year | Licensed/global point-level AIS plus reference data | A tanker-year resembles the paper's risk cluster |

The public gap corpus has endpoints and times, which is enough for the first
workstream. It does **not** contain the raw heading, speed, draft, port-trip,
or tanker history needed to reproduce Fernández-Villaverde et al.'s trip and
vessel-year model. Fernández output may later become a time-valid context
feature for a pair; it must not be used to label a pair as an actual transfer.

## Target architecture

    GFW gap events ────────────────┐
    GFW vessel identity/history ───┼──> source adapters ─> canonical tables
    optional raw AIS provider ─────┘                │
                                                     v
                                             quality + provenance
                                                     │
                                                     v
                       Atlantes-inspired segmentation/features (optional)
                                                     │
     fixed two-ended candidate rule ────────────────┤
     leave-one-out local context + graph class ─────┤
     Fernández feasible-water geometry ─────────────┤
                                                     v
                                         AIS candidate assessment
                                                     │
                       ┌─────────────────────────────┴──────────────────────────┐
                       v                                                        v
             analyst queue / API                                  later imagery adapters
                                                              VIIRS / SAR / Sentinel-2

The only persistent cross-layer contract is an immutable candidate/evidence
schema. Imagery adapters consume a candidate's time window and feasible region
and return observations; they do not alter candidate eligibility.

## AIS-first implementation sequence

### Phase 0 — reproducible public-data baseline

**Goal:** Produce the current demo-grade system entirely from the frozen,
public AIS-disabling corpus.

1. Ingest the source CSV without modifying it; record the source URL, retrieval
   time, SHA-256, row count, and schema version.
2. Normalize records into the project gap-event contract. Preserve raw MMSI,
   source duration, source identifiers, and all missing values.
3. Validate coordinates, UTC timestamps, positive durations, and identity
   format. Quarantine bad records with an explicit reason rather than silently
   coercing them.
4. Form pairs using the fixed two-ended rule: start endpoints close in both
   time and space, return endpoints close in both time and space, and a
   non-zero dark-interval overlap.
5. Compute leave-one-out local gap density and graph components. Route large
   contemporaneous clusters to fleet-cluster or regional-blackout queues before
   bilateral ranking.
6. Run a regional/month-conditioned permutation null. The comparison unit is a
   pair candidate, never a claim of an actual rendezvous.
7. Write candidate, feature, assessment, and source-manifest artifacts. A
   rerun from an identical manifest must be deterministic.

**Exit criteria:** an analyst can reproduce the candidate set from a single
run ID, inspect its contributing gap rows, and distinguish bilateral candidates
from fleet-wide dark activity.

### Phase 1 — feasible-region enrichment

**Goal:** Replace endpoint coincidence alone with a conservative physical
feasibility test.

For each vessel v at time t in the shared dark interval, compute:

    R_v(t) = water_mask
             intersect reachable_from_off_endpoint(v, t)
             intersect reachable_to_on_endpoint(v, t)

Use vessel-class-specific conservative maximum speeds, with a documented
fallback class. At a regular time grid, retain:

    F_AB = union over t of (R_A(t) intersect R_B(t))

Store the geometry, time grid, water-mask version, speed assumption, and
geometry-engine version. Features include feasible-overlap duration,
feasible-area size, and minimum physically feasible separation. The UI may
show F_AB as an uncertainty region but must never show it as a reconstructed
route or exact meeting location.

**Exit criteria:** synthetic tests cover impossible, land-crossing, boundary,
and fully feasible cases; every geometry has a reproducible assumptions record.

### Phase 2 — explainable AIS prioritization

**Goal:** Rank candidates without pretending that an unverified event is a
binary training label.

Start with a versioned weighted score rather than a black-box classifier:

| Feature family | Example signal | Direction |
| --- | --- | --- |
| Endpoint coincidence | start/end distance and time deltas | closer is stronger |
| Joint feasibility | feasible overlap duration and area | non-zero is required; compact is stronger |
| Pair specificity | isolated component, low leave-one-out density | stronger when isolated |
| Role/history context | time-valid vessel roles, prior pair history | context only |
| Behavior context | pre-/post-gap speed/course changes and segmentation | supporting evidence |
| Alternative explanations | port, anchorage, coverage hole, fleet cluster | reduces priority |

Adopt Atlantes' public design where useful: clean and segment trajectories,
derive speed/course/distance-to-coast features, then classify behavior. Its
code is a design and integration reference, not a drop-in public rendezvous
model: public documentation indicates that local inference requires GCP
credentials and the production data/model artifacts are not published as a
self-contained checkpoint.

Only after blinded analyst dispositions accumulate should a learning-to-rank
model be trained. Its target is analyst disposition, not confirmed illegal
activity. Use time-forward, geographic, vessel, and owner-group holdouts.

**Exit criteria:** every score has a feature-level explanation; a candidate
cannot score highly solely due to being in a dense fleet event.

### Phase 3 — current-source AIS adapter

**Goal:** Replace the frozen demo input with versioned, time-valid data without
changing event semantics.

Implement GFW API adapters behind the same canonical contracts. Cache raw
responses, respect source terms and rate limits, retain response hashes, and
make all source/dataset versions part of a run manifest. Add vessel identity,
encounter, loitering, port-visit, and AIS-presence context only when its
effective time is on or before the assessment's as-of time.

**Exit criteria:** frozen-corpus and API runs both produce the same canonical
schemas, with no current identity values leaked into historical events.

### Phase 4 — Fernández workstream

**Goal:** Build a separate methodological reimplementation once an appropriate
point-level tanker AIS source is licensed.

This track needs a raw AIS adapter, trip construction, port catalogue,
sanction-rule tables, annual flag-risk data, and time-valid vessel/operator
history. It runs trip-level and annual vessel-level features separately from
Dark Rendezvous. Its output can later be joined as:

    fernandez_context = {model_version, model_year, risk_cluster, availability}

Missing raw-AIS inputs must be represented as unavailable, never as low risk.

**Exit criteria:** recorded raw-data manifest, fixed random seed/scaler/cluster
mapping, trip-level unit tests, and wording that calls the result a
methodological reimplementation rather than numerical replication.

### Phase 5 — satellite evidence adapters

**Goal:** Corroborate a small, valuable candidate subset; do not scan the
world or retrain imagery models initially.

Each adapter receives:

    candidate_id, as_of_time, acquisition window, F_AB geometry,
    coverage policy, adapter/model version

and returns zero or more immutable evidence rows:

    evidence_id, candidate_id, source, observed_at, geometry,
    coverage_status, detection_confidence, join_result, artifact_uri

Join an observation only when its acquisition time lies in the shared dark
interval and its uncertainty geometry intersects F_AB at that time. Record
usable coverage separately from no detection. An unmatched vessel detection
corroborates presence in the region; it does not identify vessel A or B.

Recommended order:

1. **VIIRS** for inexpensive, low-latency night-light corroboration. Its
   official service is CPU-only and designed for at least 4 GB RAM, but it
   observes illuminated vessels only.
2. **Sentinel-1 SAR** using the public AI2 Skylight xView3 model as a
   corroborating detector. SAR is the priority high-value adapter because it
   works at night and through cloud.
3. **rslearn_projects Sentinel-2** detection and attributes for clear-day
   scene-level evidence. The project provides a public checkpoint and
   scene-download prediction pipeline.
4. **Marine infrastructure / port filters** before raising imagery-based
   priority, to eliminate platforms, turbines, anchorages, and other
   stationary explanations.

The AllenAI Sentinel repository documents a global Skylight production
deployment, but its full Sentinel-1 training imagery is about 3.5 TB. That is
a training resource, not a prerequisite for candidate-level inference.

## Proposed repository structure

Use one Python monorepo with packages organized around stable domain contracts,
not around providers or individual models. Large data, credentials, model
weights, and cloned external repositories stay outside Git.

    dark-rendezvous/
      README.md
      pyproject.toml
      uv.lock                         # or another single locked environment
      .env.example                    # names only; no secrets
      .gitignore
      Makefile
      docs/
        ais-first-rendezvous-plan.md
        data-contracts.md
        decision-log/
        runbooks/
      configs/
        base.yaml
        pairing/
          v1.yaml
        feasibility/
          v1.yaml
        scoring/
          v1.yaml
        sources/
          gfw_frozen_2017_2019.yaml
          gfw_api.yaml
        imagery/                      # present but inactive in AIS-first runs
          viirs.yaml
          sentinel1_sar.yaml
          sentinel2.yaml
      src/dark_rendezvous/
        domain/
          models.py                   # typed canonical records
          enums.py
          validation.py
        provenance/
          manifests.py
          ledger.py
          hashing.py
        adapters/
          gfw_gaps/
          gfw_identity/
          gfw_context/
          raw_ais/                    # provider-neutral protocol + future adapters
          imagery/                    # optional; no imports in AIS core
            base.py
            viirs.py
            sentinel1_sar.py
            sentinel2.py
        ais/
          normalize.py
          quality.py
          identity_history.py
          segmentation.py
          local_context.py
        candidates/
          blocking.py
          pairing.py
          components.py
          null_model.py
        feasibility/
          speed_policy.py
          water_mask.py
          joint_region.py
          spatial_join.py
        assessment/
          features.py
          rules_score.py
          explanations.py
          evidence_tiers.py
        fernandez/
          trips.py
          port_features.py
          gap_features.py
          clustering.py
        storage/
          parquet.py
          geoparquet.py
          catalog.py
        workflows/
          ingest.py
          build_candidates.py
          assess.py
          enrich_imagery.py
        api/
          app.py
          routes/
      tests/
        unit/
        contract/
        integration/
        fixtures/                     # tiny, synthetic, non-sensitive
      notebooks/
        00_data_profile.ipynb
        01_candidate_audit.ipynb
        02_null_calibration.ipynb
      scripts/
        run_local.ps1
        verify_manifest.py
      data/                           # Git-ignored; described below
        raw/
        normalized/
        derived/
        reference/
        artifacts/
        scratch/

### Non-negotiable module boundaries

- **domain** contains schemas and validation only. It imports no client,
  geospatial engine, cloud SDK, or model framework.
- **adapters** translate external data/model outputs to domain records; no
  pairing or scoring logic belongs in an adapter.
- **candidates** has deterministic pair and null-model logic. It does not
  know whether imagery is available.
- **feasibility** owns all geometry and speed assumptions. It emits
  uncertainty regions, never tracks.
- **assessment** reads features/evidence and produces an auditable score. It
  cannot make a source query.
- **fernandez** has its own entry point and artifacts. It may depend on
  canonical raw-AIS/identity contracts but not on pair-ranking internals.
- **imagery** is a plugin boundary. An unavailable satellite dependency must
  result in coverage_status=unknown, not a failed AIS assessment.

## Storage policy

Keep a source ledger and append-only derived artifacts. Do not overwrite an
assessment that might need to be reconstructed.

    data/raw/<source>/<dataset_version>/<retrieval_id>/
    data/normalized/gap_events/dataset_version=<version>/
    data/normalized/ais_positions/event_date=YYYY-MM-DD/
    data/reference/<dataset>/<version>/
    data/derived/pair_candidates/rules_version=<version>/
    data/derived/feasible_regions/geometry_version=<version>/
    data/derived/assessments/run_id=<run_id>/
    data/artifacts/imagery/<candidate_id>/<source>/

Parquet/GeoParquet are the canonical analytical formats. Store only compact
thumbnails/crops and immutable source references in Git-adjacent artifacts;
put raw satellite scenes, full raw AIS, and model checkpoints in object storage
or a separately managed volume. Add a retention policy before enabling an
imagery adapter.

## Compute and disk estimates

These are planning ranges, not provider guarantees. They assume columnar
Parquet, no duplicate raw-scene archive, and candidate-triggered imagery rather
than global imagery ingestion.

| Tier | Scope | Compute | Working storage | Why |
| --- | --- | --- | --- | --- |
| Local AIS development | Frozen 55k-event corpus, tests, candidate and geometry runs | 4 CPU cores, 16 GB RAM; GPU not needed | 25–50 GB NVMe | Corpus itself is small; headroom is for Python/geospatial dependencies, intermediate GeoParquet, maps, and run artifacts |
| Shared AIS service | Repeated GFW/API ingestion and regional or annual candidate runs | 8 vCPU, 32 GB RAM; GPU not needed | 100–250 GB NVMe/object cache | Supports raw-response retention, normalized events, feasible regions, and multiple versioned runs |
| Fernández research | Point-level global tanker AIS, trips, annual clustering | 16 vCPU, 64–128 GB RAM; GPU not required | 0.5–2 TB fast storage plus durable object storage | The volume is raw AIS and intermediate trip features, not K-means itself; partition by date/vessel and process incrementally |
| VIIRS enrichment | Candidate-only nighttime requests | 2–4 CPU cores, 4–8 GB RAM; GPU not needed | 50–200 GB cache | AllenAI documents CPU inference with at least 4 GB RAM; cache size depends on image retention |
| SAR/Sentinel inference | Candidate-only Sentinel scenes | 8 vCPU, 32 GB RAM, 12–16 GB VRAM GPU recommended | 0.5–1 TB fast cache | Covers scene downloads, tiling, crops, and repeatable evidence artifacts without retaining all global imagery |
| Sentinel-1 retraining | Reproduce/retrain AllenAI vessel detector | x86, 32+ GB RAM, 16+ GB VRAM GPU | 4+ TB fast storage | AllenAI documents roughly 3.5 TB raw imagery, a 16 GB GPU minimum, and 32 GB RAM; allow operational headroom |

For the hackathon/MVP, provision **16 GB RAM, four CPU cores, and a 50 GB SSD**.
That is sufficient for every AIS-first milestone. Do not buy GPU capacity or
multi-terabyte storage until Phase 5 is approved. If SAR is demonstrated,
rent a 16 GB VRAM GPU only for the batch and retain cropped evidence rather
than whole scenes.

## Implementation backlog

1. Create the Python package, typed gap-event/candidate/evidence schemas, and
   configuration loader.
2. Implement frozen-corpus ingestion plus manifest/ledger creation.
3. Implement pairing, local context, components, and deterministic tests.
4. Implement the conditioned null and candidate audit notebook.
5. Implement feasible-region geometry with a versioned speed policy and
   water-mask adapter.
6. Implement transparent scoring and an assessment JSON/GeoParquet output.
7. Add API/read-only map views only after output contracts are stable.
8. Add the current GFW source adapter, then begin the independent Fernández
   raw-AIS workstream.
9. Add imagery adapters one at a time, beginning with VIIRS or pre-trained SAR.

## External implementation references

- [Atlantes](https://github.com/allenai/atlantes) is the direct Skylight AIS
  reference implementation; its repository documents AIS preprocessing,
  local activity/entity inference, and its Skylight deployment.
- [VIIRS vessel detection](https://github.com/allenai/vessel-detection-viirs)
  documents the CPU-only, 4 GB-RAM minimum service for near-real-time vessel
  detections.
- [AI2 Sentinel-1/2 vessel detection](https://github.com/allenai/vessel-detection-sentinels)
  documents Skylight production use and the approximately 3.5 TB raw
  Sentinel-1 training set, together with its 16 GB GPU / 32 GB RAM training
  recommendation.
- [AI2 SAR vessel detector](https://github.com/allenai/sar_vessel_detect)
  publishes a downloadable xView3-trained model.
- [rslearn Sentinel-2 vessel documentation](https://github.com/allenai/rslearn_projects/blob/master/docs/sentinel2_vessels.md)
  documents public checkpoints and an on-demand scene prediction pipeline.

