# wake.ai status

## Snapshot

**As of 2026-09-05.** Commit: `304745b`. `origin/main` and `Tanner-dev`
point to that commit. `will-dev` and `andrew-dev` are merged. Local
`main` is fast-forwarded.

| Contributor in `git shortlog -sn --all` | Area |
| --- | --- |
| Andrew Wang (`aywang71`) — 27 commits | Dark Rendezvous ingestion, GFW pulls, Bronze and Silver data. |
| Tanner Shah (`tannershah`) — 16 commits | GapPair pipeline scaffolding and derived candidate work. |
| Will Pallan (`gurubazawada`) — 11 commits; William Pallan — 3 commits | Presence viewer and Node importer. |

The product is **wake.ai**. Its current product surface is Will's presence
viewer. GapPair is backend scaffolding that is not integrated with the viewer.

## What runs today

| Command | Result | Evidence |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q tests/` | Partial | 49 passed and 1 failed. The failure is the timing assertion in `tests/test_pipeline_nulls.py`: 13.8 s observed against a 10 s bound. It is not a correctness failure. |
| `npm --prefix code/backend test` | Done | 21 of 21 tests pass. |
| `npm --prefix code/frontend test` | Done | 12 of 12 tests pass. |
| `npm --prefix code/frontend ci && npm --prefix code/frontend run build` | Done | The build succeeds. Vite warns about one 1.3 MB chunk. |
| `npm --prefix code/backend run import:presence` | Done | Exports 1,019,256 observations across 817 covered hours and 35 UTC days. It writes ignored assets under `code/frontend/public/data/presence/`. All coverage is for `public-eez-areas` region 5690, the Russian EEZ. |

The focused check `.venv/bin/python -m pytest -q tests/test_pipeline_geo.py`
also passes: 5 tests pass.

## Subsystem status

Markers: **Done** means the named behavior works. **Partial** means only part
of the intended behavior works. **Missing** means no implementation exists.

### Will's presence viewer — **Partial**

- **Done:** The Vite, React, and MapLibre app reads the static presence catalog,
  daily observation shards, and vessel indexes produced by the Node importer.
  It renders positions and trails, supports date ranges and hourly playback,
  and provides vessel search and details. The region-5690 presence data works
  end to end. See [the viewer data flow](../code/backend/DATA_FLOW.md).
- **Partial:** The viewer only presents GFW hourly grid-cell-centre presence.
  It does not present candidates, raw tracks, inferred meeting points,
  reachable rings, or areas of interest.
- **Partial:** These files are not imported by `App.tsx`:
  `code/frontend/src/components/InvestigationPanel.tsx`,
  `code/frontend/src/components/InvestigationPanel.css`,
  `code/frontend/src/data/provider.ts`, and
  `code/frontend/src/data/mockData.ts`. The handmade three-record GapPair
  fixture at `code/frontend/public/data/{risk-events,methods,narratives}.json`
  is also unused by the React app.
- **Partial:** The product name is wake.ai, while the frontend still displays
  “Maritime Risk Intelligence” and the HTML title says “Vessel presence ·
  Maritime Risk Intelligence.” This is a naming inconsistency to resolve in a
  later code change.

### Dark Rendezvous ingestion — **Partial**

- **Done:** `src/dark_rendezvous` implements the documented `ingest-noaa`,
  `normalize-file`, `gfw-gaps`, `gfw-gaps-pull`, `gfw-presence`,
  `gfw-identity`, and `gfw-track` commands. The canonical raw-AIS contract
  and coverage boundary are documented in [AIS ingestion](ais-ingestion.md).
- **Done:** GFW GAP Bronze includes the January 2017 probe, complete 2021,
  partial 2022, partial early 2026, and complete August 2026 retrievals.

  | Retrieval | Coverage and state |
  | --- | --- |
  | `20260905T193330Z` | January 2017 probe. 4,658 events and 20 files. No pull manifest. Andrew's notes mark the window complete. |
  | `20260905T200519Z` | Complete 2021. 343,857 events, 695 pages, and 1,391 files. |
  | `20260905T202100Z` | Partial 2022. Complete windows end at 2022-10-07. No manifest. |
  | `20260905T210211Z` | Partial 2026. Complete windows end at 2026-03-04. No manifest. |
  | `20260905T210748Z` | Complete August 2026. 29,538 events, 60 pages, and 121 files. |

  No Bronze covers February 2017 through December 2019.
- **Partial:** GFW Presence Bronze has 72 report and manifest files. It is
  `public-global-presence:v4.0` at HIGH 0.01° resolution for region 5690.
  It is one hourly grid-cell-centre position per vessel-hour. It is not raw
  AIS and it is not rendezvous evidence. The 56 identity batches cover the
  2026 presence population, not the 2021 candidate population.
- **Missing:** The GFW per-vessel track route returns 404 for the configured
  token because the application lacks the tracks permission. Raw AIS vectors
  are not in the repository.
- **Partial:** Andrew holds the only `GFW_API_TOKEN` on a Windows Python 3.13
  environment. The repository venv is Python 3.14.2. The package pins do not
  match that venv; see known issues.

### GapPair pipeline — **Partial**

Run stages with `.venv/bin/python -m pipeline.run --stage <name>`.

| Stage | State | Current result |
| --- | --- | --- |
| S0 `reference.py` | Done | Static references load. |
| S1 `load.py` | Done | The CSV run normalizes 55,368 rows; 54,553 MMSIs are valid. |
| S1′ `enrich_api.py` | Missing | No module. It needs complete 2017–2019 GFW GAP Bronze. |
| S2 `feasibility.py` | Done | 433 of 434 operating pairs are feasible. |
| S3 `pair_t0.py` | Done | 434 operating pairs, 26 cross-flag pairs, and 212 queue MMSIs. |
| S4 `context.py` | Done | 237 bilateral, 183 strict identity twins, and 173 sequential pairs. The methods figures are corrected in [decisions](decisions.md). |
| S5 `nulls.py` | Partial | A 20-draw run is materialized: null mean 12.4 and lift 35.0x. The written design calls for 200 draws. |
| S6 `features.py` and `score.py` | Missing | No files. |
| S7 `corroborate.py` | Done | 434 default `no_coverage` rows. No VIIRS data is present. |
| S8 `export.py` | Partial | The fixture-level unit test passes. A real full export has not run because S6 is missing. |
| S9 `narrate.py` and `verify.py` | Missing | No files. Narration also needs a selected LLM and a key. |

`scripts/pull_queue_events.py` is implemented and has seven mocked tests. It
has not run against live GFW. The 2017–2019 CSV remains the verified validation
corpus. The complete 2021 API corpus has the GFW vessel IDs required by the
viewer, but its loader and bridge are not implemented.

### Presentation — **Partial**

- **Done:** [The Slidev deck](../presentation/slides.md) contains eight slides
  titled “Wake AI — Making dark shipping visible.”
- **Partial:** It is not wired to repository data. It uses oil-tanker and
  sanctions framing while the verified corpus and GapPair fixture concern
  fishing vessels.
- **Partial:** Slide 7 says “DETAIL TO BE ADDED.” The deck imports Google
  Fonts remotely.

## Known issues

| Severity | Issue | Owner to decide |
| --- | --- | --- |
| Medium | `tests/test_pipeline_nulls.py` fails only its performance bound: 13.8 s versus 10 s. | Tanner Shah |
| High | `pyproject.toml` and `requirements.txt` pin Python `<3.14`, pandas `<3`, and PyArrow `<22`, while the working venv is Python 3.14.2, pandas 3.0.5, and PyArrow 25.0.1. | Tanner Shah and Andrew Wang |
| Low | The viewer retains unreferenced risk-panel, provider, and mock-data files. | Will Pallan |
| Medium | wake.ai and the frontend's Maritime Risk Intelligence strings differ. | User and Will Pallan |
| Low | About 2 GB of Bronze data remains tracked in Git. This is accepted; no history rewrite is planned. | User |
| Medium | `data/reference/psma_parties.csv` has only its header row. | Tanner Shah |
| Medium | S4's explicit union neighbor definition produces 7 / 35 / 16 for median / p90 / zeros, and its strict twin rule produces 183 pairs. Older asserted figures describe a different count or exclude two valid pairs. | Tanner Shah |
| Medium | The deck's oil-tanker and sanctions framing does not match the fishing-pair corpus. | Will Pallan and user |
| Low | The deck depends on remote Google Fonts. | Will Pallan |
| High | Complete 2017–2019 GAP Bronze is absent. | Andrew Wang |
| High | Presence coverage is only for Russian-EEZ region 5690, not the 2021 candidate windows. | Andrew Wang |
| High | Existing identity batches target the 2026 presence population, not the 2021 candidates or queue. | Andrew Wang |
| Medium | `data/derived/candidate_windows_probe.json` has 28 in-EEZ and 12 high-seas windows, but it is unscored. | Tanner Shah |

## Integration work not started

- `pipeline/load_api.py` for the 2021 corpus is not implemented. See [the candidate-pipeline reference](candidate-pipeline.md) and [archived handoff prompts §14](archive/plan/handoff-prompts.md).
- `pipeline/presence_bridge.py` and `candidates.json` are not implemented. See [archived handoff prompts §14](archive/plan/handoff-prompts.md).
- Presence acquisition per candidate window is not done. See [data needs](data.md) and [archived handoff prompts §14](archive/plan/handoff-prompts.md).
- The viewer's Candidates panel, candidate selection behavior, and candidate geometry layers are not implemented. See [archived handoff prompts §14](archive/plan/handoff-prompts.md).
- S6 feature assembly and scoring are not implemented. See [the candidate-pipeline reference](candidate-pipeline.md).
- The real S8 export is not run. See [the candidate-pipeline reference](candidate-pipeline.md).
- S9 narration and verification are not implemented. See [the candidate-pipeline reference](candidate-pipeline.md) and [data needs](data.md).

## Reproduce this snapshot

Run these commands from the repository root. The importer replaces ignored
viewer assets. It does not modify Bronze inputs.

```bash
git status --short
.venv/bin/python -m pytest -q tests/
npm --prefix code/backend test
npm --prefix code/frontend ci
npm --prefix code/frontend test
npm --prefix code/frontend run build
npm --prefix code/backend run import:presence
```

For a fast environment check, run:

```bash
.venv/bin/python -m pytest -q tests/test_pipeline_geo.py
```
