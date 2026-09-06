# wake.ai

wake.ai has two browser workspaces: a replay of Global Fishing Watch (GFW)
vessel-presence data and a static GapPair screening queue. The replay loads
hourly GFW Presence assets for positions, trails, time controls, search, and
vessel details. Presence coordinates are hourly grid-cell centres, not raw AIS
fixes.

GapPair materializes 434 paired dark-gap candidates from the 2017–2019 CSV
reference corpus into a static investigation export with score provenance and
observed-versus-estimated geometry. The two workspaces are deliberately not a
vessel-identity bridge: the CSV candidates have MMSIs but no GFW vessel IDs,
and the locally available Presence export covers a different population.

## Three subsystems

| Subsystem | Path | Owner | Language/runtime | Status | Docs |
| --- | --- | --- | --- | --- | --- |
| Presence and investigation viewer | `code/frontend`, `code/backend` | Will Pallan (`gurubazawada`) | React, Vite, MapLibre, Node | Presence replay plus static GapPair investigation workspace; a future identity/presence bridge is separate | [viewer data flow](code/backend/DATA_FLOW.md) |
| Dark Rendezvous ingestion | `src/dark_rendezvous`, `scripts/*.ps1` | Andrew Wang (`aywang71`) | Python CLI; Windows Python 3.13 venv | Ingests NOAA and retrieves GFW products; token stays on Andrew's machine | [ingestion docs](docs/ais-ingestion.md) |
| GapPair candidate pipeline | `pipeline`, `tests/test_pipeline_*`, `data/reference`, `data/derived` | Tanner Shah (`tannershah`) | Python | CSV reference path is materialized through score and static export; 2021 bridge and narration remain unbuilt | [pipeline reference](docs/candidate-pipeline.md) |

## Quick start

### Presence viewer

From the repository root, build the static presence assets and start Vite:

```bash
npm --prefix code/backend run import:presence
npm --prefix code/frontend ci
npm --prefix code/frontend run dev
```

The verified checks are:

```bash
npm --prefix code/backend test
npm --prefix code/frontend test
npm --prefix code/frontend run build
```

### Dark Rendezvous ingestion

Andrew's Windows PowerShell setup:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
dark-rendezvous ingest-noaa --date 2024-01-01
$env:GFW_API_TOKEN = "<token kept outside the repository>"
dark-rendezvous gfw-gaps --start-date 2024-01-01 --end-date 2024-01-31
dark-rendezvous gfw-gaps-pull --start-date 2017-01-01 --end-date 2017-02-01
dark-rendezvous gfw-presence --start 2022-01-01T00:00:00Z --end 2022-01-01T01:00:00Z --region-id 5690
dark-rendezvous gfw-track --vessel-id <gfw-vessel-id> --start-date 2017-01-01 --end-date 2017-02-01
dark-rendezvous gfw-identity --query 9175717
```

The macOS/Linux equivalent is:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
dark-rendezvous ingest-noaa --date 2024-01-01
export GFW_API_TOKEN='<token kept outside the repository>'
dark-rendezvous gfw-gaps --start-date 2024-01-01 --end-date 2024-01-31
dark-rendezvous gfw-gaps-pull --start-date 2017-01-01 --end-date 2017-02-01
dark-rendezvous gfw-presence --start 2022-01-01T00:00:00Z --end 2022-01-01T01:00:00Z --region-id 5690
dark-rendezvous gfw-track --vessel-id <gfw-vessel-id> --start-date 2017-01-01 --end-date 2017-02-01
dark-rendezvous gfw-identity --query 9175717
```

`gfw-track` currently returns 404 for the configured application. Do not commit `GFW_API_TOKEN`. See [AIS ingestion](docs/ais-ingestion.md) for source limits and output semantics.

### GapPair pipeline

Run the verified CSV-corpus stages from the repository root:

```bash
.venv/bin/python -m pytest -q tests/
.venv/bin/python -m pipeline.run --stage reference --stage load --stage pair \
  --stage feasibility --stage context --stage null --draws 20 \
  --stage corroborate --stage features --stage score --stage export
```

The explicit stage list intentionally excludes unavailable enrichment and
narration. The declared Python package bounds conflict with the installed 3.14
virtual environment; see [current status](docs/status.md). Validate the
published artifacts with the [verification guide](docs/verification.md) rather
than treating a command exit code as proof that an export was written.

The current full Python suite has known cleanup failures from duplicate test
paths and a stale three-record fixture assertion. The focused S6/S8 checks and
the frontend test/build are passing; see [status](docs/status.md) before using
the full-suite result as a release gate.

## Repository map

| Path | Purpose |
| --- | --- |
| `background/` | Background research and experiment logs. |
| `code/` | Will's frontend viewer and Node presence importer. |
| `data/` | Data root; see its `bronze/`, `silver/`, `raw/`, `derived/`, `reference/`, and `logs/` subdirectories. |
| `data/bronze/` | Retained raw GFW API retrievals and manifests. |
| `data/silver/` | Normalized ingestion outputs. |
| `data/raw/` | Source archives and ingestion configuration. |
| `data/derived/` | GapPair outputs and candidate-window probes. |
| `data/reference/` | Static reference tables and geography. |
| `data/logs/` | Presence-backfill log and state. |
| `docs/` | Live project, data, architecture, pipeline, and ingestion documentation. |
| `ideas/` | Earlier ideas and source material. |
| `output/` | Generated reference output. |
| `pipeline/` | Tanner's GapPair Python stages and configuration. |
| `presentation/` | Slidev pitch deck. |
| `scripts/` | Acquisition and experiment helpers. |
| `src/` | Andrew's `dark_rendezvous` package. |
| `tests/` | Ingestion and GapPair tests. |
| `tmp/` | Local reference images and extracted PDFs. |
| `pyproject.toml` | Python project metadata and declared dependency bounds. |
| `requirements.txt` | Python dependency constraints. |
| `.env.example` | Example environment variable names; no live token. |
| `LICENSE` | Repository license. |

The former `plan/` and `research/` directories and the root `report-source.md` were archived under [`docs/archive/`](docs/archive/README.md).

GFW data is CC BY-NC 4.0 and requires UI attribution. A GFW token is never committed.

The system never asserts a hidden route, an intentional disabling, a transfer, or a crime.

## Documentation

Start at the [documentation index](docs/README.md). See the [architecture](docs/architecture.md), [status](docs/status.md), [data inventory](docs/data.md), [candidate pipeline](docs/candidate-pipeline.md), [ship-suspicion model](docs/ship-suspicion-model.md), [developer guide](docs/development.md), [verification guide](docs/verification.md), and [viewer data flow](code/backend/DATA_FLOW.md).
