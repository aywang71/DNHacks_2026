# Dark Rendezvous repository map

This is the navigation and data-location reference for the repository. Read it
before treating a file as raw AIS, a vessel track, or evidence of a rendezvous.
The current implementation is an AIS/GFW ingestion and visualization baseline;
candidate detection remains planned work.

## Start here

| If you need to... | Go to... |
| --- | --- |
| Install and run a Python loader | [README.md](README.md) |
| Understand provider boundaries and the canonical position schema | [docs/ais-ingestion.md](docs/ais-ingestion.md) |
| Run a Bronze-only GFW GAP backfill | [docs/bronze-backfill-runbook.md](docs/bronze-backfill-runbook.md) |
| Acquire a narrow raw-AIS window for a candidate | [docs/targeted-raw-ais-plan.md](docs/targeted-raw-ais-plan.md) |
| Use the implemented presence-map data flow | [code/backend/DATA_FLOW.md](code/backend/DATA_FLOW.md) |
| Find the initial detection design and research record | [docs/ais-first-rendezvous-plan.md](docs/ais-first-rendezvous-plan.md), [plan/build-plan.md](plan/build-plan.md), and [plan/research-notes.md](plan/research-notes.md) |

The two documents under `plan/` are historical design and research material.
They are useful for methods and sources, but this map and the implementation
documents above are authoritative for current code and on-disk data.

## Code and product layout

```text
src/dark_rendezvous/       Python CLI, provider adapters, schemas, storage
tests/                     Python contract and loader tests
scripts/                   Long-running GFW backfill helpers
docs/                      Operational documentation and acquisition plans
data/                      Provider inputs, derived tables, reference geometry, run state
code/backend/              Node importer: Bronze Presence -> static browser assets
code/frontend/             Vite/React hourly-presence viewer
presentation/              Presentation application and deployment settings
plan/                      Historical product, detection, and research proposals
background/                Cloned/research artifacts; not a runtime dependency
```

The Python CLI is the source of truth for acquisition and normalization. The
Node backend does not call GFW: it validates existing GFW Presence Bronze
reports and publishes static assets for the frontend.

## Data locations and meaning

### Provider and reference data

| Location | Contents | Resolution and intended use |
| --- | --- | --- |
| `data/disabling_events.zip` | Frozen Global Fishing Watch AIS-disabling research corpus | 55,368 derived GAP events (2017-2019), with off/on endpoints; not raw message-level AIS. |
| `data/gfw_config.py` | Upstream corpus filter configuration | Reference only; it is not invoked by the current CLI. |
| `data/exclusions.json` | Historical corpus-loader quarantine checkpoint | Legacy provenance, not an input to the current pipeline. |
| `data/reference/ne_10m_coastline.geojson` | Natural Earth coastline | Optional coast-distance feature input for the experimental Atlantes adapter. |

### Bronze: retain provider responses unchanged

| Location | Contents | Important boundary |
| --- | --- | --- |
| `data/bronze/gfw_gaps/retrieval_id=*/.../response.json` | Paginated GFW Events API GAP responses | Derived GAP events. Read `pull_manifest.json` to determine the exact request window and completion status. |
| `data/bronze/gfw_presence/retrieval_id=*/region_dataset=*/region_id=*/report.json` | GFW 4Wings Presence responses and sibling manifests | One vessel/grid-cell/hour at the requested 0.01 or 0.1 degree resolution. This is not raw AIS. |
| `data/bronze/gfw_identity_ytd/retrieval_id=*/` | GFW Vessels API identity responses and manifest | Vessel identity/enrichment records, not positions. |
| `data/bronze/gfw_tracks/gfw_vessel_id=*/start=*/end=*/track.lines.json` | Created by `gfw-track` when used | GFW's returned, derived track representation for one vessel/window; preserve its manifest and do not describe it as raw AIS. |
| `data/bronze/noaa_marine_cadastre/YYYY/ais-YYYY-MM-DD.csv.zst` or `.parquet` | Created by `ingest-noaa` when used | Public U.S. terrestrial broadcast-point AIS. 2018-2023 uses NOAA's legacy compressed CSV objects; later adapter support uses GeoParquet. The source is minute-downsampled and is suitable for development/validation, not global high-seas coverage. |
| Licensed raw-AIS export (external path) | Input to `normalize-file` | The current command reads an operator-supplied CSV or Parquet path directly. Retain a provider-approved raw copy and its license/provenance before normalizing it. |

Bronze must be treated as immutable after a successful retrieval. GFW response
collections retain sibling manifests with request parameters, row counts,
hashes, and retrieval time. NOAA's Silver manifest records the source URI and
raw-object hash for its retained Bronze object.

### Silver: normalized and purpose-specific outputs

| Location | Contents | Do not interpret as... |
| --- | --- | --- |
| `data/silver/gfw_gap_endpoints/` | Normalized off/on rows from GFW GAP events | A vessel's path during a gap. There are normally two endpoint rows per closed event. |
| `data/silver/gfw_presence_hourly/` | Normalized GFW Presence rows | Exact raw AIS positions. Coordinates are grid-cell centers at hourly cadence. |
| `data/silver/gfw_track_points/gfw_vessel_id=*/start=*/end=*/points.parquet` | Normalized output from `gfw-track` | A raw AIS message stream. It retains the GFW-derived-track provenance and native returned spacing. |
| `data/silver/atlantes_presence_experimental/` | ATLAS-compatible tracks and experimental activity output from Presence | Ground truth, raw AIS, or rendezvous evidence. It is an adapter experiment. |
| `data/silver/ais_positions/event_date=YYYY-MM-DD/positions.parquet` | Default canonical output from the NOAA adapter | A global corpus. The directory is created by each NOAA day pull. |
| `data/silver/ais_positions/source=noaa_marine_cadastre/request_id=*/event_date=*/positions.parquet` | Request-isolated NOAA output | A global corpus. This is the required layout for a targeted raw-AIS pull. |
| `data/silver/ais_positions/source=<provider>/positions.parquet` | Canonical output from `normalize-file` | A global corpus. This is the present output shape for a licensed point-level export. |

The canonical raw-position fields are `ts`, `lat`, `lon`, and `vessel_id`.
Additional source, identity, motion, quality, and provenance fields are defined
in [docs/ais-ingestion.md](docs/ais-ingestion.md). Do not mix `gfw_gap_endpoints`
or hourly Presence into `ais_positions` without preserving their source-specific
semantics.

### Operational and non-canonical locations

| Location | Purpose |
| --- | --- |
| `data/logs/` | Resumable backfill logs and state. Useful for operations, not analysis. |
| `data/requests/raw_ais/<request_id>/request.json` and `result.json` | Immutable human- and machine-readable targeted acquisition request and completion record | A data result or a finding. They define the trigger, time, area, aliases, provider, evidence boundary, and retained-object hashes. |
| `data/scratch/` | Temporary local work. Nothing here is a supported input. |
| `data/raw/` and `data/derived/` | Legacy corpus-era directories. Do not add new pipeline outputs here; use Bronze/Silver paths above. |
| `code/frontend/public/data/presence/` | Generated static browser assets from the Node importer. Rebuild from Bronze rather than editing them. |

## Data lineage

```text
NOAA or licensed raw AIS -> bronze raw object -> silver/ais_positions
GFW GAP Events API       -> bronze/gfw_gaps -> silver/gfw_gap_endpoints
GFW 4Wings Presence API  -> bronze/gfw_presence -> silver/gfw_presence_hourly
                                          -> frontend static presence assets
GFW Vessel Tracks API    -> bronze/gfw_tracks -> silver/gfw_track_points
GFW Vessels API          -> bronze/gfw_identity_ytd -> enrichment joins
```

Only the first path is point-level AIS. GFW GAP data supplies endpoints and
derived gap attributes; GFW Presence supplies hourly, gridded vessel presence.
Neither can reconstruct an unobserved route or establish that a rendezvous
occurred.

## Common operations

```powershell
# Show Python acquisition commands
.\.venv313\Scripts\python.exe -m dark_rendezvous.cli --help

# Validate Python implementation
.\.venv313\Scripts\python.exe -m pytest -q

# Publish browser assets from locally retained GFW Presence Bronze reports
npm --prefix code/backend test
npm --prefix code/backend run import:presence
```

For a new GFW acquisition, supply `GFW_API_TOKEN` only through the active shell
or a secret manager. Never place a token in source, a manifest, a log, or this
repository.

## Naming rules for new data

1. Put a provider response and its manifest in `data/bronze/<provider>/`.
2. Put a reproducible normalized table in `data/silver/<dataset>/`, partitioned
   by source/time where appropriate.
3. Record provider, source URL/request, retrieval time, version, and hashes.
4. Keep generated frontend assets and experiments separate from analytical
   Silver tables.
5. Add the new location and its observational semantics to this document.
