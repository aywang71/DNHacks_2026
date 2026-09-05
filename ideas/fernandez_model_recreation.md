# Recreating the Fernández-Villaverde et al. model for Dark Rendezvous

## Decision

Build **two related but distinct products** on one versioned data platform:

1. `fernandez_tanker_risk`: a faithful reproduction of the paper's annual,
   vessel-level dark-tanker classifier. It needs raw, point-level AIS data for
   crude-oil tankers.
2. `dark_rendezvous`: the project's post-event, pair-level assessment of two
   AIS-off events. It can bootstrap from the public GFW 2017--2019 gap corpus.

Do not force either output to stand in for the other. The paper answers
"which tanker-year resembles the high-risk cluster?" Dark Rendezvous answers
"which completed pair of gaps deserves an analyst's attention?" A `dark`
vessel label is not proof of a rendezvous, and a pair candidate does not
require the vessel to be in the paper's dark-tanker cluster.

## What the paper actually implements

The supplied paper is the 46-page main text. It refers to an online appendix
for the operative algorithms. The reproduction target below follows that
appendix (Algorithms A.1--A.4), not just the abstract's description.

### Unit of analysis and time grain

| Stage | Unit | Recompute |
| --- | --- | --- |
| AIS cleaning and trip construction | AIS position / trip | source batch |
| Levels 1--3 | trip | vessel-year |
| final cluster | vessel | calendar year |
| Dark Rendezvous | pair of closed gaps | as-of assessment time |

### Paper pipeline

1. Start with satellite AIS positions for crude-oil tankers: vessel identifier,
   UTC timestamp, latitude, longitude, speed, heading, and draft. Supplement
   it with a port catalogue, vessel age, operator fleet size, and annual Paris
   MoU flag-state rank.
2. Remove AIS positions with `draft < 0` or `speed > 20 kn`. Infer port
   entry/exit from a crossing of 1 kn; discard short (<3 h) port-state
   fluctuations; find a nearby port in a 2-degree box and require the closest
   port to be <50 km. Segment the remaining position sequence into trips.
   Mark an idle trip when average speed is <=1 kn for 14 consecutive days.
3. **Level 1 -- sanctioned port:** after the country-specific sanction start,
   give a trip `trip_score = 1` if its origin or destination is a listed
   sanctioned-country port.
4. **Level 2 -- AIS gaps:** define a long gap separately for each vessel as a
   time difference above that vessel's 99th percentile. For every long gap:
   - calculate the least endpoint-to-sanctioned-port-to-endpoint distance,
     divide it by gap hours, and score `1 - percentile(required_speed)`;
   - find overlapping long gaps from other vessels; project rays using the
     pre-gap headings; retain a forward intersection; calculate the lowest
     speed required to reach that point at the overlapping-gap midpoint and to
     return to the on-AIS endpoint; score `1 - percentile(required_speed)`.
   The maximum gap score becomes the trip's port and STS features. Min-max
   normalize both and run `KMeans(n_clusters=2, max_iter=300)`; the cluster
   high on both dimensions is the gap-anomaly flag.
5. **Level 3 -- kinematics:** calculate trip mean speed, speed standard
   deviation, and detour factor (sum of consecutive Haversine distances /
   Haversine distance from trip start to end). Normalize, run two-cluster
   K-means, and label the cluster with low mean speed, high variability, and
   high detour as the kinematic-anomaly flag.
6. For trips not already scored 1 by Level 1, assign `0`, `.5`, or `1` for
   neither / exactly one / both anomaly flags. Average trip score by
   vessel-year and calculate idle-trip ratio.
7. Min-max normalize five vessel-year features: average trip score,
   idle-trip ratio, vessel age, operator fleet size (reverse its risk
   direction), and flag-state rank. Run a two-cluster K-means per calendar
   year; the high-risk centroid is `paper_dark_cluster`.

The paper's published model does **not** disclose its random seed, source AIS
vendor/extract, exact trip-boundary code, or final operator-size label
reassignment. Exact cluster membership and its reported 83.3% external check
are therefore not reproducible from the paper alone. Our reproduction must
publish those choices and a fixed seed; call the result a *methodological
reimplementation*, not a numerical replication.

## Public-data discovery (5 September 2026)

### Model artefacts

No publicly indexed source repository, trained-model file, centroids, feature
scaler bounds, tanker classifications, or prediction table was found. This is
not a neural model with reusable weights: its fitted artefacts would be the
annual K-means centroids, min-max bounds, label-to-centroid mapping, and the
vessel-year feature table. None is attached to the paper's NBER, Oxford, SSRN,
CESifo, or author pages. The SSRN record now shows a July 2026 revision, but
still offers the paper rather than a replication package.

The full-paper appendix is public and gives the algorithm, but it says that
complete pseudocode and technical specifications are available *on request*.
The 330m-row satellite AIS supplier is not named. It does name two proprietary
supplements: Lloyd's List Intelligence Seasearcher for vessel age/operator
fleet size, and mostly Lloyd's List port data.

### Useful sources we can actually obtain

| Need | Source | Fit / limitation |
| --- | --- | --- |
| Demo-ready gap events, encounters, loitering, port visits, identity, SAR | [GFW APIs](https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/key-concepts) | Best public source for Dark Rendezvous; requires an API token and explicit dataset version pinning. GAP is a prototype product. |
| Frozen project bootstrap | [Welch et al. GFW disabling corpus](https://github.com/GlobalFishingWatch/AIS-disabling-high-seas) | Public 2017--2019, fishing-only, endpoint events rather than raw tracks. |
| Global raw point AIS | Commercial source still required | The paper's input is not publicly released. [Kpler's historical position API](https://servicedocs-sm.kpler.com/historical-positions-api/) documents satellite/terrestrial positions with heading and speed, but is commercial, marked discontinued, and starts 2018-12-07; it cannot reproduce 2017--2018. |
| Open raw AIS for pipeline testing | [NOAA/USCG AccessAIS](https://coast.noaa.gov/digitalcoast/tools/ais.html) | Point data, 2009--2025, but U.S. coverage only. Use this to exercise the raw-AIS/trip code, never to claim global tanker replication. |
| Public global port catalogue | [NGA World Port Index](https://msi.nga.mil/Publications/WPI) | Official, global coordinates and port attributes, downloadable in CSV/GeoJSON/etc.; version it because it is updated monthly. |
| Annual flag-risk feature | [Paris MoU annual reports](https://parismou.org/year-report/year-report-2025/) | Historical White/Grey/Black lists are published in annual reports; extract the list effective for each model year. |

GFW's global AIS-presence dataset is helpful for local density and coverage
context, but is explicitly one position per vessel per hour and does not
provide individual tracks. It cannot supply the paper's raw-ping trip,
heading-ray, or detour inputs.

## Why the current project data cannot run that model

The public `disabling_events.csv` has 55,368 already-qualified gap events. Its
15 fields include gap endpoints/times, MMSI, flag, fishing vessel class,
estimated length/tonnage, and source gap duration. It does **not** contain the
continuous AIS position sequence, pre-gap heading, speed observations, draft,
trip/port history, tanker type, operator history, or annual flag-risk rank.

Consequences:

- It supports the project's deterministic two-ended pair detector and its
  conditioned nulls.
- It supports a **conservative endpoint feasibility region** for a candidate
  pair, as specified in `idea-01-data-spec.md`.
- It cannot calculate the paper's per-vessel 99th-percentile gaps, ray-heading
  intersections, trip detours, idle-trip ratio, or five-feature vessel K-means.
- The paper's straight-ray `intersection point` must never be used as a
  rendered meeting point in Dark Rendezvous. Retain `F_AB`, the feasible
  water-region union in the project specification, as the analyst-facing
  geometry.

The bootstrap corpus is also fishing-only, while the paper's claim is about
crude-oil tankers and sanctions. A tanker model needs a tanker-capable raw AIS
source and its own separate evaluation cohort.

## Canonical input contracts

Keep the source adapter responsible for mapping a provider's fields to these
contracts. Every row must retain `source_name`, `source_record_id`,
`retrieved_at`, `source_dataset_version`, `raw_object_uri`, and a raw-payload
hash in the source ledger.

### `ais_positions`

Required for the Fernández track; partition by `event_date` and a stable
`vessel_partition`.

| Field | Type | Rule |
| --- | --- | --- |
| `vessel_id`, `imo`, `mmsi_raw` | string | Preserve all source identifiers; identity resolution is separate |
| `observed_at` | UTC timestamp | Strictly ordered per source/vessel before feature construction |
| `lat`, `lon` | float | WGS84; reject out-of-range values to quarantine |
| `speed_kn`, `heading_deg`, `draft_m` | float nullable | Preserve missingness; do not turn missing heading into zero |
| `nav_status`, `source_quality` | string nullable | Provider-specific provenance, not a model replacement |
| source-ledger fields | mixed | Required as above |

Do not use a gridded AIS-presence product as a substitute: it is appropriate
for density context, but cannot supply the individual pings, headings, drafts,
or trip geometry required by the paper.

### `vessel_identity_history`

`vessel_id`, effective start/end, IMO/MMSI/callsign aliases, vessel class,
deadweight tonnage, build year, flag, commercial operator, and identity
confidence. Resolve every feature using the record effective at the trip or
gap time; never backfill later ownership/flag changes into old records.

### `ports` and `sanction_rules`

`ports` needs a stable port ID, name, coordinates, country, source/version,
and validity interval. `sanction_rules` is a hand-reviewed, versioned table:
country, commodity, sanctioning authority, effective start/end, and citation.
It must be separated from port geometry so that an update to sanctions does
not mutate historical geography.

### Project enrichment inputs

| Input | Product use | Minimum retention |
| --- | --- | --- |
| GFW gap Events API / frozen corpus | pair generation | event payload and dataset version |
| GFW vessel identity | time-valid role/aliases | response payload + effective dates |
| GFW encounters, loitering, port visits | independent context | event payload + retrieval time |
| SAR detections and coverage | corroboration, not identity | detection/coverage query and geometry/time result |
| local gap aggregates | reception/fleet alternative | calculation version and leave-one-out rules |

## Ingestion and storage layout

```text
data/
  raw/<source>/<dataset_version>/<retrieval_id>/       # immutable payloads
  ledger/source_objects.parquet                         # hashes and retrieval metadata
  normalized/ais_positions/event_date=YYYY-MM-DD/       # canonical pings
  normalized/gap_events/dataset_version=.../
  reference/ports/version=.../
  reference/sanction_rules/version=.../
  derived/trips/model_input_version=.../
  derived/fernandez_trip_features/year=YYYY/
  derived/fernandez_vessel_scores/year=YYYY/
  derived/pair_candidates/rules_version=.../
  derived/assessments/as_of_date=YYYY-MM-DD/
```

Each pipeline run writes a manifest containing input object hashes, row counts,
quarantine counts, configuration, package/git version, UTC start/end, and
output hashes. Derived tables are append-only by `run_id`; do not overwrite a
result that might be needed to reconstruct an old assessment.

## Build order

### Phase 0 -- immediate, no new vendor

1. Ingest the GFW `disabling_events.csv` unchanged into `raw/`; validate the
   15-column source contract and record its SHA-256.
2. Normalize it to the project `gap_events` contract; preserve the raw MMSI as
   text, derive exact duration, and retain rounded `gap_hours` separately.
3. Implement the fixed, both-end candidate rule, leave-one-out density/context,
   connected components, regional permutation null, and output contracts from
   `idea-01-data-spec.md`.

This makes the live demo and the existing evidence reproducible. It is not
the paper model.

### Phase 1 -- raw AIS foundation

1. Select and license/obtain a global, point-level AIS source covering crude
   tankers. Require the `ais_positions` fields above, historical coverage,
   documented delivery latency, and permission to retain derived data.
2. Build one source adapter, a raw-object cache, a normalizer, duplicate/order
   handling, and a quarantine table before implementing features.
3. Ingest independently versioned vessel/operator history, ports, Paris MoU
   annual lists, and reviewed sanction rules.

### Phase 2 -- methodological reimplementation

1. Implement paper-compatible trip segmentation and feature extraction as
   pure functions with synthetic tests for every threshold and geometry case.
2. Implement the annual K-means stages with a fixed `random_state`, recorded
   scaler bounds, explicit centroid-to-risk mapping, and cluster-stability
   checks across seeds.
3. Publish feature distributions and input missingness per year before showing
   any `paper_dark_cluster` label. Evaluate only against an independently
   sourced, time-valid external list.

### Phase 3 -- Dark Rendezvous integration

Join the tanker-risk result to a pair only as an explainable *context feature*
(`a_paper_dark_cluster`, `b_paper_dark_cluster`, model/version/year). Keep
candidate eligibility, pair score, component class, local null, and feasible
geometry entirely separate. No outcome or post-assessment human disposition
may enter the S1/S2 feature set.

## Acceptance tests

- Re-running an identical raw-object manifest gives byte-identical normalized
  tables and deterministic model outputs.
- A record with missing heading cannot yield a paper-style STS ray score; it
  is `unavailable`, not zero risk.
- A port/sanction rule effective after a trip cannot affect that trip.
- Changing an operator/flag in a later identity interval cannot change a
  historical vessel-year feature.
- The GFW corpus loader validates all 15 known input columns and isolates bad
  identifiers rather than coercing them into valid vessel identities.
- Project UI labels the pair result "candidate" and the geometry "feasible
  region"; no screen calls either a confirmed transfer or exact meeting point.
- A large contemporaneous component routes to `fleet_cluster` or
  `regional_blackout`, not `bilateral` merely because one pair within it passes
  an endpoint threshold.

## Recommended first implementation boundary

Start with Phase 0 plus the source-ledger and canonical-contract code. It
produces a usable Dark Rendezvous system against public data immediately, and
it prevents a later raw-AIS connector from changing model semantics. Begin the
paper's Phase 1/2 path only after choosing a raw tanker AIS source; no current
file in this repository satisfies that dependency.
