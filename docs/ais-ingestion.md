# AIS ingestion architecture

## Outcome

The implemented data contract is intentionally small at its core:

| Required analytical field | Meaning |
| --- | --- |
| ts | UTC timestamp at which AIS reported the position |
| lat, lon | WGS84 position |
| vessel_id | Stable internal key, preferring IMO and falling back to MMSI |

The pipeline retains the accompanying fields needed to assess whether a missing
position is a meaningful discontinuity rather than a collection failure.

## Pipeline

    NOAA daily broadcast points or licensed AIS export
                         |
                         v
              bronze: immutable raw provider object
                         |
                         v
              silver: canonical ais_positions Parquet
                         |
       +-----------------+-------------------+
       |                                     |
       v                                     v
  identity observations                coverage cells
       |                                     |
       +-----------------+-------------------+
                         v
              gold: gaps -> pairs -> feasible regions -> assessments

The implemented CLI covers bronze-to-silver ingestion and separately retrieves
derived GFW gaps plus GFW identity records. Gap classification, pairing, and
feasible-region construction consume the stable silver contract next; they
never depend on a provider-specific column name.

## Canonical ais_positions schema

| Group | Columns |
| --- | --- |
| Core | position_id, ts, lat, lon, vessel_id |
| Source lineage | source, source_record_id, dataset_version, source_uri, ingested_at, raw_payload_hash |
| Identity aliases | mmsi, imo, callsign, vessel_name |
| Movement | sog_kn, cog_deg, heading_deg, nav_status, transceiver_class |
| Collection/quality | collection_mode, quality_flags, is_valid_position |

All timestamps are normalized to UTC. MMSI is stored as text, never an integer,
so its original representation is preserved. A row with invalid time,
coordinates, or vessel identity is retained with quality flags rather than
silently discarded.

## Sources

### NOAA Marine Cadastre: implemented raw-AIS adapter

The ingest-noaa command downloads a daily public broadcast-point GeoParquet
object, decodes its WGS84 point geometry to longitude/latitude, normalizes
provider fields, and can clip the normalized result to a bounding box. Use it
to exercise raw-ping ordering, kinematics, identity aliasing, and coverage
logic.

NOAA is land-based U.S.-waters data and is minute-downsampled. An AIS gap in
this source can reflect receiver coverage, propagation, or collection
interruption; it must not be labelled intentional disabling without coverage
evidence.

Source details: [NOAA Marine Cadastre broadcast-point documentation](https://github.com/ocm-marinecadastre/ais-vessel-traffic/blob/main/data/ais-broadcast-points-2024-readme.md).

### Global Fishing Watch: implemented gap and identity enrichment

The gfw-gaps command calls the official Events API and saves each raw response
page. It also writes gfw_gap_endpoints Parquet, with two rows per closed GAP:
an off endpoint and an on endpoint. Each output row has endpoint_id, ts, lat,
lon, vessel_id, validity flags, the GFW event ID, and gap metrics. An open gap
emits only its off endpoint. The gfw-identity command calls the Vessels API and
saves unmodified identity responses that can be joined to vessel aliases.

This is endpoint-level event data, not raw AIS. It does not include positions
inside the gap or the preceding/following message stream. Timestamps are
returned as ISO-8601 instants with millisecond notation; spatial coordinates
are decimal-degree endpoint values. Do not write these rows to the raw
ais_positions table: retain them as the distinct gfw_gap_endpoints source.

The current API response exposes `gap.offPosition` and `gap.onPosition`, which
the connector normalizes as the two endpoint rows. They are observed response
fields rather than a documented raw-message contract: if either disappears,
the row is retained with quality flags rather than fabricated coordinates. The
manifest records the requested dataset alias and uses the concrete version
from the API response header when GFW supplies it (otherwise it retains the
requested alias). GFW's event date filter defaults to
`OVERLAP`, so a requested month can include an event that began before or ends
after that month; preserve start/end timestamps and apply your analytical
window downstream.

### Paginated, append-only GAP pulls

Use `gfw-gaps-pull` for an inventory or corpus pull rather than the one-page
`gfw-gaps` smoke-test command. It requests GAPs in `START-DATE` mode, so each
event belongs to the calendar window containing its start timestamp, and
follows the API's `nextOffset` until the window is exhausted. The default
keeps only GAPs classified by GFW as intentional disabling; pass `--all-gaps`
to retain the broader population.

    dark-rendezvous gfw-gaps-pull --start-date 2017-01-01 --end-date 2017-02-01 \
        --window-days 31 --page-size 500

Every API page is retained independently, never overwritten:

    data/bronze/gfw_gaps/retrieval_id=<UTC-run-id>/
      window_start=YYYY-MM-DD/window_end=YYYY-MM-DD/offset=000000000/
        response.json
        manifest.json

    data/silver/gfw_gap_endpoints/retrieval_id=<UTC-run-id>/
      window_start=YYYY-MM-DD/window_end=YYYY-MM-DD/offset=000000000/
        endpoints.parquet
        manifest.json
      pull_manifest.json

The Silver page files are ordered by `vessel_id`, timestamp, and endpoint role.
They are an append-only snapshot, so deduplicate a later analysis view by
`event_id`, `endpoint_role`, and dataset version rather than deleting prior
source snapshots. Use `--max-pages` only for a bounded probe: its run manifest
will explicitly record `complete: false` when pagination stops early.

Pass `--bronze-only` for an independent long-running acquisition job. It saves
the response and page manifest but does not write or overwrite any Silver
artifacts. The operational handoff is in
[the Bronze backfill runbook](bronze-backfill-runbook.md).

### GFW per-vessel track points

`gfw-track` targets GFW's documented per-vessel `/tracks` route for a selected
GFW vessel ID and time range. It requests JSON line segments with `LONLAT`,
`TIMESTAMP`, `SPEED`, and `COURSE`, without server-side thinning. The connector
retains the raw response, expands each returned coordinate into the canonical
point schema, and writes a distinct `gfw_track_points` table when the account
has access:

    dark-rendezvous gfw-track --vessel-id <gfw-vessel-id> \
        --start-date 2017-01-01 --end-date 2017-02-01

    data/bronze/gfw_tracks/gfw_vessel_id=<id>/start=YYYY-MM-DD/end=YYYY-MM-DD/track.lines.json
    data/silver/gfw_track_points/gfw_vessel_id=<id>/start=YYYY-MM-DD/end=YYYY-MM-DD/points.parquet

These are labelled `position_semantics=gfw_derived_track`; they must not be
called raw AIS. The track API does not document an hourly sampling parameter,
so preserve native returned points and construct a separate hourly display view
only after retrieval. A frontend should draw returned pre/post-gap points as a
visible path and render the intervening AIS-off interval as uncertainty, never
as interpolated observed motion.

The currently configured GFW application is authenticated but has no
`public-global-fishing-tracks:*` permission, and the documented route returns
`404` under that account. Do not schedule this command for a backfill unless
GFW grants track access and a smoke test succeeds.

### GFW 4Wings hourly Presence: implemented derived-AIS fallback

`gfw-presence` requests a bounded `public-global-presence` 4Wings report,
grouped by vessel and hour. GFW derives this product by selecting one AIS
position per vessel-hour, then reports the centre of the requested spatial
grid cell. Therefore the exact provider response is Bronze but it is **not**
raw AIS; the flattened output is a separate Silver table with explicit grid
semantics.

    dark-rendezvous gfw-presence \
        --start 2022-01-01T00:00:00Z --end 2022-01-01T01:00:00Z \
        --region-id 5690 --region-dataset public-eez-areas \
        --spatial-resolution HIGH

    data/bronze/gfw_presence/retrieval_id=<UTC-run-id>/
      region_dataset=public-eez-areas/region_id=5690/
        report.json
        manifest.json

    data/silver/gfw_presence_hourly/retrieval_id=<UTC-run-id>/
      region_dataset=public-eez-areas/region_id=5690/
        points.parquet
        manifest.json

The Bronze object is the raw API response payload, retained before field
mapping (as a canonical JSON serialization). Silver rows use the shared
position fields (`ts`, `lat`, `lon`, `vessel_id`, MMSI, IMO, name, and callsign)
plus `presence_hours`, GFW vessel type/flag, report dataset, and grid
resolution. They are always labelled
`position_semantics=gfw_presence_grid_center_hourly`.

`HIGH` produces 0.01-degree grid centres (roughly 1.1 km north/south); `LOW`
produces 0.1-degree centres. Treat each coordinate as an uncertainty cell, not
the vessel's exact fix. This makes the table appropriate for global candidate
screening and coarse frontend playback, but raw provider AIS remains required
for a close-approach/rendezvous assessment.

The report API permits only one report per account at a time and may time out
on large regions/windows. Pull small region-time windows serially. If GFW
documents a timeout but has completed the query, `--reuse-last-report` stores
the account's last report as a separately labelled retrieval; verify that it
matches the requested parameters before using it. Use `--bronze-only` for an
acquisition worker that must not write Silver.

GFW's AIS-disabling repository provides useful gap/reception methodology and a
final event dataset, but its raw AIS message tables are license-restricted. It
is a validation and method reference, not a raw-AIS provider.

Source details: [GFW Events API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/events/get-all-events),
[GFW Vessels API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/vessels/get-one-vessel),
[GFW 4Wings Presence and Report API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings),
and the [AIS-disabling method repository](https://github.com/GlobalFishingWatch/AIS-disabling-high-seas).

### Commercial global satellite AIS: supported through normalize-file

Export raw points from a licensed provider such as Spire in CSV or Parquet,
then call normalize-file. The normalizer accepts common aliases such as
BaseDateTime, LAT, LON, MMSI, SOG, COG, and Heading; mapping changes are
isolated to the canonicalizer.

Require these fields in a provider agreement: observed timestamp, latitude,
longitude, MMSI, IMO where available, speed, course, heading, message type,
and collection source (satellite, terrestrial, or mixed). Retain received time
and receiver/quality metadata when available.

## Coverage boundary

Before promoting a discontinuity to a coverage-supported gap, calculate a
separate coverage table by spatial cell and time bucket:

    provider, collection_mode, spatial_cell, bucket_start_utc,
    distinct_vessels, position_count, expected_position_count,
    coverage_ratio, outage_flag, baseline_method_version

The candidate's own vessel is excluded from its local comparator statistics.
If local comparable traffic disappeared as well, the correct output is
insufficient_coverage_evidence, not intentional disabling.

## Commands

    dark-rendezvous ingest-noaa --date 2024-01-01
    dark-rendezvous ingest-noaa --date 2024-01-01 --bbox -75,35,-74,36
    dark-rendezvous normalize-file --input C:\data\provider.csv --source provider_export
    dark-rendezvous gfw-gaps --start-date 2024-01-01 --end-date 2024-01-31
    dark-rendezvous gfw-gaps-pull --start-date 2017-01-01 --end-date 2017-02-01 --page-size 500
    dark-rendezvous gfw-presence --start 2022-01-01T00:00:00Z --end 2022-01-01T01:00:00Z --region-id 5690
    dark-rendezvous gfw-identity --query <IMO-or-MMSI-or-name>

All data land under data/, which is Git-ignored. Every ingestion writes a JSON
manifest recording source location, hash, row counts, output path, and run time.
