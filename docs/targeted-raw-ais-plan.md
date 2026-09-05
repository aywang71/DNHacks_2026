# Targeted raw-AIS acquisition plan

## Decision

Use the existing GFW-derived collections to find and rank candidate windows,
then acquire **actual AIS position observations only for those windows**. This
avoids a global raw-AIS backfill while making close-approach analysis possible
where a compatible raw provider covers the location.

The first implementation target is NOAA Marine Cadastre data. It is public,
U.S.-coastal, terrestrial-receiver AIS and is therefore a validation corpus,
not evidence for high-seas or global claims. The project's NOAA adapter uses
the published daily product: NOAA's 2018-2023 compressed CSV archive and the
later GeoParquet archive. It labels the observations
`terrestrial_ais_minute_downsampled`. It is not a source of global,
second-by-second satellite AIS.

## Source boundary

| Source | What it provides | What it cannot establish |
| --- | --- | --- |
| GFW Presence | One derived position per vessel-hour, snapped to a grid cell | Exact path, speed/course at a meeting, or close approach |
| GFW GAP | Derived AIS-off/on endpoints and gap metrics | Any movement within the gap |
| NOAA Marine Cadastre | Observed U.S.-coastal AIS broadcast points, minute-downsampled in this adapter | Global coverage or a finding that an offshore gap was intentional |
| Licensed satellite/terrestrial AIS | Potentially denser raw observations, depending on contract | Must be separately licensed and audited for coverage/reception bias |
| Synthetic trajectories | UI, test, and load-test data only | Training labels, model evaluation, or operational evidence |

Global Fishing Watch describes AIS Vessel Presence as a derived product that
takes one AIS position per vessel per hour, and explicitly notes that it is
not a vessel track. The 4Wings API also distinguishes it from SAR detections.
See [GFW 4Wings API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings).

NOAA's broadcast-point schema includes `MMSI`, full UTC `BaseDateTime`,
latitude, longitude, SOG, COG, heading, vessel name, IMO, callsign, vessel
type, and navigation status. See the [NOAA AIS data dictionary](https://coast.noaa.gov/data/marinecadastre/ais/data-dictionary.pdf).

## Candidate-to-pull workflow

```text
GFW Presence / GAP event
        |
        v
candidate window: time, region, known vessel aliases, reason
        |
        v
coverage gate: can NOAA or a licensed source observe that place and time?
        |
        v
targeted raw-AIS pull: only days overlapping the candidate window
        |
        v
Bronze immutable provider object + retrieval manifest
        |
        v
Silver canonical observed positions
        |
        v
pairwise observed-distance and behaviour features
        |
        v
auditable candidate assessment, never a claim of transfer or wrongdoing
```

### 1. Form a pull request

Every request must be a small record, stored beside its result, containing:

```text
candidate_id
trigger_type                    # gfw_gap, presence_co-location, analyst lead
trigger_source_ids              # event IDs / position IDs
window_start_utc, window_end_utc
bbox_wgs84                      # min_lon, min_lat, max_lon, max_lat
vessel_aliases                  # MMSI, IMO, GFW vessel ID when known
provider
collection_mode                 # terrestrial, satellite, or mixed
coverage_hypothesis
request_reason
```

For the pilot, use a window beginning six hours before the candidate and
ending six hours after it. If the candidate indicates a sustained interaction,
extend the window to include the full interval plus that same buffer. Start
with a 50-km radius around the candidate centre, then widen only when vessel
speed, boundary effects, or uncertainty justify it. These are pull-planning
defaults, not a definition of rendezvous.

### 2. Acquire only the required day objects

NOAA publishes daily files. The current adapter therefore downloads each day
that overlaps the request, then clips the normalized data to the bounding box:

```powershell
dark-rendezvous ingest-noaa `
  --date 2024-01-01 `
  --bbox -75.50,37.00,-74.50,38.00
```

Repeat only for the UTC dates spanned by the request. Bronze retains the
unmodified daily object and its SHA-256; Silver retains only the requested
bounds in the canonical `ais_positions` table. This is deliberately not a
whole-year or whole-country download. NOAA lists 116.7 GB for all of its 2024
daily downloads, which is precisely the scale this targeted strategy avoids.
See the [NOAA 2024 archive](https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/index.html).

For a licensed provider, use `normalize-file` and preserve its original export
unchanged in Bronze. The contract requires, at minimum, observation timestamp,
latitude, longitude, vessel identifier, source/receiver mode, and any supplied
SOG/COG/heading/quality fields.

## Activated Gulf-of-Mexico validation pull

The repository now includes one bounded public-data request at
`data/requests/raw_ais/gulf_2021_09_aet_pair/request.json`. It is a
screening-only pair of GFW GAP events for AET RESPONSIBILITY (MMSI 367530350)
and AET EXCELLENCE (MMSI 367511240): their 2021-09-15/16 dark intervals overlap
for 18.97 hours, and their off/on endpoints are 3.10 km and 6.15 km apart.
That identifies a useful ingestion and coverage-validation window; it does not
establish a rendezvous or an AIS-disabling finding.

The request uses a six-hour buffer and a small northern-Gulf bounding box. It
spans three UTC NOAA objects (2021-09-15 through 2021-09-17). Their compressed
download size is approximately 756 MiB in total before decompression. Run or
resume it with:

```powershell
.\scripts\run_targeted_noaa_minute_pull.ps1 `
  -RequestFile data\requests\raw_ais\gulf_2021_09_aet_pair\request.json
```

Use `-PlanOnly` to print the exact three calls without downloading, and
`-Force` only to replace an existing request-isolated Silver day. The runner
writes Silver to `data/silver/ais_positions/source=noaa_marine_cadastre/`
`request_id=gulf_2021_09_aet_pair/`; it never overwrites the default NOAA path.

The first execution is complete. Its request, object hashes, row counts, and
source-boundary outcome are in
`data/requests/raw_ais/gulf_2021_09_aet_pair/result.json`. The three large
Bronze archive objects were deliberately removed from the working tree after
normalization to keep the repository pushable; the isolated Silver outputs
contain 58,318 valid observations for 280 vessels. NOAA reports a small number
of observations during both GFW-labelled gap intervals, which is the expected
reminder that GFW's derived gap product and a terrestrial receiver archive have
different reception and processing histories. Treat this as a
coverage/provenance result, never as proof for or against a rendezvous.

The current high-latitude Presence corpus is outside NOAA's footprint. For
those priority candidates, prepare the identical request record but fulfil it
with a licensed satellite/terrestrial AIS provider; Global Fishing Watch GAP,
Presence, and track responses remain derived products, not raw message feeds.

### 3. Keep observation semantics intact

All observed rows go through the shared schema:

```text
position_id, ts, lat, lon, vessel_id,
mmsi, imo, callsign, vessel_name,
sog_kn, cog_deg, heading_deg, nav_status, transceiver_class,
source, collection_mode, quality_flags, raw_payload_hash
```

Required rules:

1. `ts` is the provider observation timestamp in UTC; do not replace it with
   an interpolation timestamp.
2. Preserve original received SOG, COG, heading, and receiver/quality metadata
   when provided.
3. Mark the NOAA product as `terrestrial_ais_minute_downsampled`; never call
   it satellite AIS or globally complete.
4. A local absence is a **coverage question**, not intentional disabling.
5. Keep GFW Presence and GAP tables separate from raw `ais_positions`.

## Analysis allowed after a successful raw pull

For a bounded candidate window, calculate only from observed positions:

- time-aligned nearest-pair separation;
- duration under a stated separation threshold;
- relative speed and course convergence/divergence;
- dwell or loitering features;
- pre/post-window continuity and receiver-coverage controls;
- distance from shore, port, anchorage, and other relevant context.

The output should expose the observed sample count, largest timestamp gap,
provider/receiver mode, time alignment tolerance, and all thresholds. A
candidate with insufficient raw coverage is reported as
`insufficient_coverage_evidence`, not as a dark rendezvous.

## Synthetic-data policy

Synthetic positions may support frontend animation, unit tests, and pipeline
load tests. They must live in a separate fixture or simulation dataset and
carry all of the following fields:

```text
is_synthetic=true
synthesis_method
synthetic_scenario_id
derived_from_position_ids        # optional, for a visualization-only trace
```

They must not be inserted into `ais_positions`, joined with observed points,
used for feature/model training, counted as coverage, or displayed as observed
in the UI. In particular, never interpolate the hourly GFW Presence grid
centres and then calculate a rendezvous score from the interpolated result.

## Pilot acceptance criteria

The first pilot is complete when it has:

1. one U.S.-coastal candidate with a documented candidate request;
2. only the necessary NOAA UTC-day objects in Bronze, each hash-manifested;
3. a clipped, observed-only Silver dataset with validated canonical fields;
4. a coverage report and raw-position-count summary;
5. pairwise features that identify their exact input rows and thresholds; and
6. a UI that visibly distinguishes observed points, GFW derived positions,
   gaps, and synthetic fixtures.

After that pilot, decide whether a licensed global provider is justified. The
decision should be based on how often candidate windows fall outside NOAA's
coverage and how much denser observations alter the candidate assessment, not
on synthetic interpolation.
