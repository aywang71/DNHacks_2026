# wake.ai data inventory and needs

Snapshot: 2026-09-05. Sizes and counts below are measured in this checkout. Git status refers to tracked paths, not whether a file is a suitable analytical input.

## Layers and evidence meaning

| Layer | Purpose and evidence limit |
| --- | --- |
| `data/raw/` | Holds source archives and upstream configuration. The disabling-events CSV is one row per derived disabling event, not raw AIS messages. |
| `data/bronze/` | Holds immutable GFW API pages and manifests. GAP pages expose provider-derived off/on endpoints and event metadata; they do not show motion inside a gap. Presence reports are preserved API responses, but their coordinates are hourly grid-cell centres, not raw AIS fixes. |
| `data/silver/` | Holds normalized Parquet plus manifests. `gfw_gap_endpoints` contains provider-reported gap endpoints, not a message stream; `gfw_presence_hourly` retains the grid-centre semantics. |
| `data/derived/` | Holds GapPair working outputs. Pair geometry and feasible or inferred meeting locations are analytical inferences, not observations. |
| `data/reference/` | Holds static lookup tables and coastline geometry used by the GapPair pipeline and the Atlantes experiment. |
| `code/frontend/public/data/` | Holds generated static viewer assets. The presence assets are a browser export of Bronze Presence reports and remain grid-centre observations. |

The progression is raw → Bronze → Silver → derived. Reference data is an input beside that progression. The frontend assets are a generated delivery surface, not a source layer.

## Inventory

### `data/raw/`

| Path | Producer (command/script) | Coverage | Size / file count | Tracked in git? | Manifest / complete? | Consumer | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data/raw/disabling_events.zip` | Downloaded GFW AIS-disabling corpus | 2017–2019 fishing-vessel disabling events | 4.1 MB / 1 archive | Yes | n/a | `pipeline.load` after extraction | Welch et al. 2022 corpus. |
| `data/raw/disabling_events.csv` | `unzip data/raw/disabling_events.zip -d data/raw` | Same corpus; 55,369 lines including header | 11 MB / 55,369 lines | No; `data/raw/*.csv` is ignored | n/a | `pipeline.load` | 55,368 event rows. This is not raw AIS. |
| `data/raw/gfw_config.py` | Upstream corpus configuration, retained locally | 2017–2019 analysis settings | 4 KB / 1 file | Yes | n/a | Human reference | Includes the upstream gap filters; it is not executed by GapPair. |

### `data/bronze/`

All Bronze GFW objects are tracked by decision. Do not edit an API page or manifest after it is written.

| Path | Producer (command/script) | Coverage | Size / file count | Tracked in git? | Manifest / complete? | Consumer | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data/bronze/gfw_gaps/response.json` | `dark-rendezvous gfw-gaps` probe | One unmanifested Events API page; response metadata requests 2024-01-01 to 2024-01-02 | 1.9 KB / 1 file | Yes | No sibling manifest; completeness unknown | Root `gfw_gap_endpoints/endpoints.parquet` | Kept as a probe, not a corpus pull. |
| `data/bronze/gfw_gaps/retrieval_id=20260905T193330Z/` | `dark-rendezvous gfw-gaps-pull` | 2017-01-01 to 2017-02-01; 4,658 intentional GAP events | 7.5 MB / 20 files | Yes | Each page has a manifest; no `pull_manifest.json`. The page window is complete. | Jan 2017 Silver endpoints | Ten 500-event pages. |
| `data/bronze/gfw_gaps/retrieval_id=20260905T200519Z/` | `dark-rendezvous gfw-gaps-pull --bronze-only` | 2021-01-01 to 2022-01-01; 343,857 intentional GAP events | 557 MB / 1,391 files | Yes | `pull_manifest.json`; complete, 695 pages | Candidate-window probe source; future 2021 loader | Uses `START-DATE` filtering and 500 events per page. |
| `data/bronze/gfw_gaps/retrieval_id=20260905T202100Z/` | `dark-rendezvous gfw-gaps-pull --bronze-only` | 2022-01-01 through complete windows ending 2022-10-07 | 618 MB / 1,534 files | Yes | No pull manifest. First incomplete window starts 2022-10-07. | No current application consumer | Preserve partial pages; use a new retrieval for a replacement pull. |
| `data/bronze/gfw_gaps/retrieval_id=20260905T210211Z/` | `dark-rendezvous gfw-gaps-pull --bronze-only` | 2026-01-01 through complete windows ending 2026-03-04 | 152 MB / 386 files | Yes | No pull manifest. First incomplete window starts 2026-03-04. | No current application consumer | Preserve partial pages; use a new retrieval for a replacement pull. |
| `data/bronze/gfw_gaps/retrieval_id=20260905T210748Z/` | `dark-rendezvous gfw-gaps-pull --bronze-only` | 2026-08-01 to 2026-09-01; 29,538 intentional GAP events | 46 MB / 121 files | Yes | `pull_manifest.json`; complete, 60 pages | No current application consumer | Uses `START-DATE` filtering and 500 events per page. |
| `data/bronze/gfw_presence/` | `dark-rendezvous gfw-presence`; `scripts/run_gfw_presence_backfill.ps1` | 36 report/manifest pairs, all `public-eez-areas` region `5690` (Russian EEZ), `HIGH` 0.01° grid: 2021-09-05 and 2021-09-06; the 2022-01-01 00:00–01:00 UTC request twice; 2026-08-01; and 2026-08-05 through 2026-09-04 | 679 MB / 72 files | Yes | A matching report and manifest exist for each request. There is no pull-wide completion marker. 2026-09-02 through 2026-09-04 are covered-empty reports. | Node presence importer; Silver presence normalizer | One hourly grid-cell-centre position per vessel-hour. It is not raw AIS or rendezvous evidence. |
| `data/bronze/gfw_identity_ytd/retrieval_id=identity_local_presence_2026_20260905T213508Z/` | GFW Vessels API batch pull | Identity for vessels in the locally cached 2026 Presence population | 8.1 MB / 56 files | Yes | One manifest plus 55 batches; 5,478 entries. It is not a global or 2021 candidate identity set. | Human inspection; future candidate enrichment | The manifest identifies 5,448 distinct input vessel IDs and 5,505 found IDs. |

The GAP Bronze tree contains 3,453 tracked files: 1 root probe response, 1,725 page responses, 1,725 page manifests, and 2 pull manifests. The Presence and identity trees contain 72 and 56 tracked files respectively.

### `data/silver/`

| Path | Producer (command/script) | Coverage | Size / file count | Tracked in git? | Manifest / complete? | Consumer | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data/silver/gfw_gap_endpoints/endpoints.parquet` and `manifest.json` | `dark-rendezvous gfw-gaps` | One 2024-01-01 probe event; 2 endpoint rows | 32 KB / 2 files | Yes | Sibling manifest; one probe page only | No current GapPair or viewer consumer | Each closed event supplies an off and on endpoint. |
| `data/silver/gfw_gap_endpoints/retrieval_id=20260905T193330Z/` | `dark-rendezvous gfw-gaps-pull` without Bronze-only mode | Jan 2017; 4,658 events and 9,316 endpoint rows | Included in 1.3 MB / 21 files for this retrieval | Yes | Ten page manifests and Parquet files plus one pull manifest; Jan window complete | No current GapPair or viewer consumer | This is normalized endpoint data, not raw AIS. |
| `data/silver/gfw_presence_hourly/` | `dark-rendezvous gfw-presence`; Presence backfill script | Mirrors the 36 Bronze Presence requests for region `5690`, `HIGH` 0.01° | 51 MB / 72 files | Yes | One Parquet file and manifest per Bronze report | Identity selection and analysis; not the Node importer | The Node importer reads Bronze reports directly. Rows retain `gfw_presence_grid_center_hourly` semantics. |
| `data/silver/atlantes_presence_experimental/` | `dark-rendezvous prepare-atlantes-presence`; `scripts/run_atlantes_activity_experiment.py` | 671 grid-centre-derived track rows for the Berezina experiment | 80 KB / 3 files | Yes | `manifest.json` describes input and coastline hashes | No production consumer | `berezina_activity_predictions.json` is experimental activity output. It is not raw AIS or rendezvous evidence. |

### `data/logs/`

| Path | Producer (command/script) | Coverage | Size / file count | Tracked in git? | Manifest / complete? | Consumer | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data/logs/gfw_presence_public-eez-areas_region_5690_high.{log,state.json}` | `scripts/run_gfw_presence_backfill.ps1` | Region `5690`, `HIGH` Presence backfill | 36 KB / 2 files | Yes | State records `complete`; this is an operational state file, not a data manifest | Backfill operator | The state points to a Windows-local log path. |

### `data/derived/`

Parquet outputs are ignored by `data/derived/*.parquet`. JSON and text checkpoints are tracked. No file in this table is consumed by the current React presence viewer.

| Path | Producer (command/script) | Coverage | Size / file count | Tracked in git? | Manifest / complete? | Consumer | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data/derived/gap_events.parquet` | S1, `python -m pipeline.run --stage load` | 2017–2019 CSV corpus; 55,368 rows | 6.2 MB / 55,368 rows | No | n/a | S3, S2, S4, S5, S7 | Normalized one-row-per-gap source. |
| `data/derived/exclusions.json` | S1, `load` | Same corpus; 815 invalid MMSIs, 702 blank flags | 428 B / 1 file | Yes | Checkpoint, not a manifest | Human review | Records the source hash and loader quality counts. |
| `data/derived/candidates_t0.parquet` | S3, `pair` | 434 operating paired-gap candidates from 2017–2019 | 104 KB / 434 rows | No | n/a | S2, S4, S5, S7 | Pair candidates are not confirmed encounters. |
| `data/derived/pair_grid_counts.json` | S3, `pair` | 2017–2019 pairing ladder and cell-month counts | 2.1 KB / 1 file | Yes | Checkpoint, not a manifest | Methods and export code | Records 434 operating and 18,775 loose pairs. |
| `data/derived/queue_mmsis.txt` | S3, `pair` | MMSIs represented in operating candidates | 2.1 KB / 212 lines | Yes | n/a | `scripts/pull_queue_events.py` | The live GFW queue pull has not run. |
| `data/derived/feasibility.parquet` | S2, `feasibility` | 434 operating candidates | 1.3 MB / 434 rows | No | n/a | S6 and S8 | 433 of 434 are feasible under the current rule. |
| `data/derived/loose_feasibility.json` | S2, `feasibility` | 18,775 loose pairs; 18,735 feasible at the minimum overlap | 53 B / 1 file | Yes | Checkpoint, not a manifest | Methods and export code | The loose rule is not a queue. |
| `data/derived/local_context.parquet` | S4, `context` | 434 operating candidates | 80 KB / 434 rows | No | n/a | S6 and S8 | Local density, identity, and history features. |
| `data/derived/components.parquet` | S4, `context` | 434 operating candidates | 11 KB / 434 rows | No | n/a | S6 and S8 | Compact component classification table. |
| `data/derived/null_results.json` | S5, `null --draws 20` | 2017–2019 operating rule; 20 draws on disk | 21 KB / 1 file | Yes | Checkpoint, not a manifest | Methods and export code | The configured design is 200 draws; this stored run has 20. |
| `data/derived/p_cell.parquet` | S5, `null --draws 20` | 434 operating candidates | 8 KB / 434 rows | No | n/a | S6 and S8 | Per-pair cell probability output. |
| `data/derived/corroboration.parquet` | S7, `corroborate` | 434 operating candidates | 10 KB / 434 rows | No | n/a | S6 and S8 | Every default row is `no_coverage`; no VIIRS data is present. |
| `data/derived/features.parquet` | S6a, `features` | 434 operating candidates | 1.6 MB / 434 rows and 106 columns | No | n/a | S6b and S8 | Complete keyed feature surface; absent enrichment fields remain null. |
| `data/derived/scores.parquet` | S6b, `score` | 434 operating candidates | 193 KB / 434 rows and 17 columns | No | n/a | S8 | Bounded score terms, labels, and row-level provenance; behavior is null in this corpus. |
| `data/derived/evidence_ledger.parquet` and `summary.md` | S8, `export` | 2017–2019 reference export | 2,170 ledger rows and one summary | Ledger: No; summary: generated release artifact | Auditor and human review | The ledger preserves the exported evidence claims; the summary states headline counts and limits. |
| `data/derived/candidate_windows_probe.json` | One-off 2021 API-corpus probe; not a stage in `pipeline.run` | 28 in-EEZ and 12 high-seas unscored pairs from the complete 2021 GAP pull | 68 KB / 40 candidate records | Yes | Status is `PROBE, unscored`; not a manifest | Planned targeted Presence and raw-AIS requests | Carries GFW vessel IDs. A future bridge replaces this file. |

### `data/reference/`

| Path | Producer (command/script) | Coverage | Size / file count | Tracked in git? | Manifest / complete? | Consumer | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data/reference/class_speeds.json` | Maintained to match `pipeline.config.V_KN` | Eight vessel-class speed values | 179 B / 8 values | Yes | n/a | `pipeline.reference` | Local configuration lookup; no external source URL is recorded. |
| `data/reference/eu_iuu_cards.csv` | Curated static table | 21 EU IUU-card intervals | 799 B / 21 data rows | Yes | n/a | `pipeline.reference` | `source_url` column is present but unpopulated in every row. |
| `data/reference/psma_parties.csv` | Placeholder static table | No populated parties | 22 B / header only, 0 data rows | Yes | n/a | `pipeline.reference` | Optional table. `psma_party` returns unknown while it is empty. |
| `data/reference/rfmo_names.json` | Maintained static lookup | 13 RFMO code-to-name mappings | 764 B / 13 values | Yes | n/a | `pipeline.reference` | No external source URL is recorded. |
| `data/reference/ne_10m_coastline.geojson` | Natural Earth source material | Global 1:10m coastline geometry | 9.7 MB / 1 file | Yes | n/a | `prepare-atlantes-presence`, via `src/dark_rendezvous/atlantes_adapter.py` | Natural Earth is public domain. It is not read by `pipeline.reference`. |
| `data/reference/README.md` | Local documentation | This directory | 1 file | Yes | n/a | Human reader | See the directory README for the compact reference-table index. |

### Frontend public assets

| Path | Producer (command/script) | Coverage | Size / file count | Tracked in git? | Manifest / complete? | Consumer | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `code/frontend/public/data/presence/` | `npm --prefix code/backend run import:presence` | 35 UTC dates, region `5690`; 1,019,256 observations across 817 covered hours | 313 MB / 71 files | No; ignored by `code/frontend/.gitignore` | `catalog.json` plus immutable daily shards | React presence viewer | Generated from Bronze Presence reports. It must not be edited by hand. |
| `code/frontend/public/data/risk-events.json` and `methods.json` | S8, `pipeline.export` | 2017–2019 CSV reference corpus; 434 candidate records | 11.3 MB risk export and 7.5 KB methods metadata | Release-controlled generated assets | Static GapPair provider (`risk-events`) and methods review | Every record passes `validate_record`; `beh` is null for this corpus. |
| `code/frontend/public/data/tracks/` | S8, `pipeline.export` | One GeoJSON track per reference candidate | 434 GeoJSON files | Release-controlled generated assets | Investigation geometry view | Observed endpoints and estimated geometry share the record contract but remain visually and semantically distinct. |
| `code/frontend/public/data/narratives.json` | Earlier P0 fixture | Three fixture records | Small JSON file | Yes | No S9 output exists | No current static-provider consumer | Retained only until a narrated/verifier-backed stage is implemented. |
| `code/frontend/public/data/ship-suspicion.json` | `scripts/export_ship_suspicion.py` | Top 200 latest-anchor individual vessel scores | 40 KB / 200 ranked vessels | Release-controlled generated asset | Independent vessel-model panel | Experimental model snapshot; it is not a GapPair event score or evidence of wrongdoing. |

## Schemas

### Canonical `ais_positions`

`src/dark_rendezvous/contract.py` defines the canonical position-column order. It preserves invalid rows with quality flags instead of dropping them.

| Group | Columns |
| --- | --- |
| Identifier | `position_id` |
| Provider lineage | `source`, `source_record_id`, `dataset_version`, `source_uri`, `ingested_at`, `raw_payload_hash` |
| Time and identity | `ts`, `vessel_id`, `mmsi`, `imo`, `callsign`, `vessel_name` |
| Position and movement | `lat`, `lon`, `sog_kn`, `cog_deg`, `heading_deg`, `nav_status`, `transceiver_class` |
| Semantics and quality | `position_semantics`, `collection_mode`, `quality_flags`, `is_valid_position` |

`ais_positions` is the contract for actual position feeds such as NOAA or licensed AIS exports. GFW GAP endpoints stay in their own endpoint table. GFW Presence is normalized to compatible columns but retains grid-centre semantics.

### GFW GAP event page

GAP pages are JSON envelopes with `entries`, pagination fields such as `nextOffset`, and dataset metadata. The useful event shape is:

| Area | Fields |
| --- | --- |
| Event identity and time | `event.id`, `event.type`, `event.start`, `event.end` |
| Vessel | `event.vessel.ssvid`, `type`, `flag`, `name`, `id` |
| GAP payload | `event.gap.offPosition`, `onPosition`, `durationHours`, `intentionalDisabling`, plus reception and implied-speed fields when present |
| Jurisdiction | `event.regions.eez`, `rfmo`, `highSeas`, `fao`, `mpa` |
| Distance metadata | `event.distances.*` when supplied by the API corpus |

The normalizer emits the off endpoint for every GAP and the on endpoint only for a closed GAP. These are provider-reported endpoint fields, not AIS messages before, during, or after the gap.

### GFW Presence report row

| Area | Fields |
| --- | --- |
| Envelope | `entries: [{ "public-global-presence:v4.0": [rows] }]` |
| Hour and vessel | `date`, `vesselId`, `hours` |
| Position | `lat`, `lon` |
| Profile | `shipName`, `mmsi`, `imo`, `flag`, `vesselType` |

Rows can also include `callsign` and report-wide transmission metadata. `date` is the playback hour. `entryTimestamp` and `exitTimestamp` describe the report interval, not an individual observation. At `HIGH`, each coordinate is a 0.01° grid-cell centre.

### GapPair `gap_events.parquet`

S1 in `pipeline/load.py` writes this 27-column table.

| Group | Columns |
| --- | --- |
| Event and vessel | `gap_id`, `mmsi`, `mmsi_int`, `mid`, `mmsi_valid`, `vessel_class`, `flag` |
| Vessel attributes | `length_m`, `tonnage_gt`, `length_estimated`, `tonnage_estimated` |
| Gap endpoints | `t0`, `t1`, `lat0`, `lon0`, `lat1`, `lon1` |
| Gap metrics | `shore_off_km`, `shore_on_km`, `gap_hours_source`, `gap_hours_exact` |
| Pairing support | `cell`, `cell_month`, `dateline`, `v_kn`, `v_kmh`, `n_gaps_vessel` |

## Provenance, licensing, and secrets

The pipeline uses this attribution text from `pipeline/config.py`:

> Data: Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0

The corpus archive source recorded in the prior `data/README.md` is [Global Fishing Watch AIS-disabling high seas](https://github.com/GlobalFishingWatch/AIS-disabling-high-seas). NOAA Marine Cadastre data is public domain. Natural Earth coastline data is public domain.

`GFW_API_TOKEN` belongs only in Andrew Wang's active environment or secret manager. It must never be committed, added to a repository file, emitted in logs, or copied into a manifest. Andrew holds the available token. The configured token receives `404` from the GFW per-vessel tracks route because it lacks the required tracks permission.

## Coverage gaps

The GAP backfill uses intentional disabling events, `START-DATE` filtering, and 500 events per page. The following resume boundaries come from [the Bronze resume notes](gfw-bronze-backfill-resume-notes.md).

| Retrieval | Valid complete windows | First incomplete window | Resume boundary |
| --- | --- | --- | --- |
| `20260905T202100Z` | 2022-01-01 through 2022-10-07 | 2022-10-07 to 2022-11-07; 62 pages, next offset 31,000 of 41,397 | 2022-10-07 |
| `20260905T210211Z` | 2026-01-01 through 2026-03-04 | 2026-03-04 to 2026-04-04; 60 pages, next offset 30,000 of 33,561 | 2026-03-04 |

| GAP interval | State |
| --- | --- |
| 2017-02 through 2019-12 | No GAP Bronze exists in this repository. |
| 2022-10-07 through 2022-12-31 | Incomplete or absent. |
| 2023-01-01 through 2025-12-31 | Not pulled. |
| 2026-03-04 through 2026-07-31 | Incomplete or absent. |
| 2026-08-01 through 2026-08-31 | Complete through retrieval `20260905T210748Z`. |
| 2026-09-01 onward | Not pulled by the GAP backfill. |

Presence exists only for `public-eez-areas` region `5690`. It does not provide global coverage, candidate-window coverage, or raw AIS evidence.

## What we need

Priority is ordered by the dependency needed to turn candidates into an auditable viewer investigation.

| Priority | What | Why / consumer | Candidate source or acquisition path | Who can obtain it | Blocker or unknown |
| --- | --- | --- | --- | --- | --- |
| 1 | Raw AIS position vectors for each candidate window: per-message position, timestamp, speed over ground, course, heading, and MMSI for both vessels. | Close-approach and rendezvous assessment need actual paths and movement. The planned candidate layer needs observed paths beside its estimated geometry. | GFW tracks permission; Spire, exactEarth, or ORBCOMM commercial S-AIS; NOAA Marine Cadastre for U.S.-coastal candidates. | Andrew for GFW access; a licensed-data holder for commercial data; NOAA is public. | Nothing on disk substitutes for this. Presence is hourly grid-centre output, and GAP data supplies only endpoints; neither provides message-rate vectors or movement inside a gap. The configured GFW tracks route returns `404`; NOAA is U.S. terrestrial coverage and only 2 of 465 2021 pairs involve a U.S.-flag vessel. |
| 2 | GFW GAP Bronze from 2017-02 through 2019-12. | The CSV corpus needs GFW regions, distances, names, and GFW vessel IDs for enrichment. | GFW Events API with the existing Bronze puller. | Andrew, because it needs the token. | The interval is absent. Andrew's token-time estimate is unverified. |
| 3 | GFW 4Wings Presence for the 28 in-EEZ windows in `data/derived/candidate_windows_probe.json`, plus confirmation whether 4Wings accepts RFMO or FAO region IDs for the 12 high-seas windows. | The future viewer bridge needs candidate-window Presence, not region-month coverage. | GFW 4Wings report API, one small region-window request at a time. | Andrew, because it needs the token. | One report runs per account; larger requests can time out. High-seas region support is unknown. |
| 4 | GFW identity records for 2021 candidate and queue vessels: names, aliases, authorizations, and owner fields. | The 2021 candidate loader and viewer detail panel need identity metadata for their GFW IDs. | GFW Vessels API. | Andrew, because it needs the token. | Current identity batches cover the 2026 Presence population only. |
| 5 | GFW `ENCOUNTER`, `LOITERING`, and `PORT_VISIT` events for the 212 queue MMSIs. | S7 corroboration needs independent GFW event context. | `scripts/pull_queue_events.py`. | Andrew, because it needs the token. | The script has mocked tests only; it has not run against live GFW. |
| 6 | VIIRS boat detections from NOAA EOG VBD for 2017-07-01 through 2017-07-03 in the 41–44°N, 160–164°E box. | S7 corroboration needs a source for the 2017 showcase night. | NOAA Earth Observation Group Visible Infrared Imaging Radiometer Suite Boat Detection data. | A project operator with access to the source. | Coverage is unknown. |
| 7 | EEZ, RFMO, or high-seas jurisdiction for every event. | Jurisdiction filters and targeted Presence requests need a region identifier. | The 2021 API corpus `regions` field; polygons or the missing 2017–2019 GAP Bronze for the CSV corpus. | Andrew for API-derived fields; a project operator for polygon work. | The CSV corpus has no jurisdiction fields. |
| 8 | An `ANTHROPIC_API_KEY` or another LLM key, and a decision on the LLM. | S9 narration is not implemented and needs a selected provider. | Project secret manager and a product decision. | A key holder and the project owner. | No key or model choice is present. |
| 9 | Complete 2022–2026 GAP coverage for a recent-data story. | A recent candidate corpus needs contiguous GAP data. | GFW Events API with the documented resume boundaries. | Andrew, because it needs the token. | Partial and absent intervals remain; see [the Bronze resume notes](gfw-bronze-backfill-resume-notes.md). |

## Regeneration

Generated outputs can be rebuilt from their documented inputs. Regeneration does not make a derived source become raw AIS.

### Local derived files

Extract the tracked source archive before running S1:

```bash
unzip -o data/raw/disabling_events.zip -d data/raw
```

Run implemented GapPair stages in dependency order. The stored null result uses 20 draws. The configured design uses 200.

```bash
.venv/bin/python -m pipeline.run --stage reference
.venv/bin/python -m pipeline.run --stage load
.venv/bin/python -m pipeline.run --stage pair
.venv/bin/python -m pipeline.run --stage feasibility
.venv/bin/python -m pipeline.run --stage context
.venv/bin/python -m pipeline.run --stage null --draws 20
.venv/bin/python -m pipeline.run --stage corroborate
.venv/bin/python -m pipeline.run --stage features
.venv/bin/python -m pipeline.run --stage score
.venv/bin/python -m pipeline.run --stage export
```

`narrate`, the 2021 API loader, and the viewer bridge are not implemented.
The S8 reference export currently has 434 records and 434 tracks; validate it
with the commands in [the verification guide](verification.md) after a rerun.
`candidate_windows_probe.json` is a one-off, unscored probe rather than a
`pipeline.run` stage; its checked-in regeneration command is unknown.

Regenerate the separate ship-suspicion static asset only after its model,
training manifest, metrics, latest-anchor score file, and training examples are
present:

```bash
.venv/bin/python scripts/export_ship_suspicion.py
```

### Presence assets

The Node importer discovers complete Bronze Presence report/manifest pairs and writes ignored viewer assets:

```bash
npm --prefix code/backend run import:presence
```

See [the viewer data flow](../code/backend/DATA_FLOW.md) for importer validation and static asset contracts. The importer does not need Silver Presence files.

### GFW acquisition

The GAP Bronze helper writes only new, uniquely identified Bronze pages and manifests:

```powershell
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2022-10-07 -EndDate 2023-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2023-01-01 -EndDate 2024-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2024-01-01 -EndDate 2025-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2025-01-01 -EndDate 2026-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2026-03-04 -EndDate 2026-08-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2026-09-01
```

For daily Presence acquisition, use the resumable script with a region and UTC date range, for example:

```powershell
.\scripts\run_gfw_presence_backfill.ps1 -StartDate 2021-09-05 -EndDate 2026-09-05 -RegionId 5690 -RegionDataset public-eez-areas -SpatialResolution HIGH
```

Set `GFW_API_TOKEN` only in the active process or a secret manager. Never regenerate Bronze pages, reports, or manifests by hand, overwrite an existing retrieval, or fabricate a manifest. Bronze objects are immutable provenance records.
