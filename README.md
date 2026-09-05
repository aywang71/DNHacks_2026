# Dark Rendezvous

This repository starts with a real, provider-neutral AIS ingestion layer.
It downloads raw NOAA Marine Cadastre broadcast-point data or normalizes an
export from a licensed AIS provider into one canonical table centered on:

    ts, lat, lon, vessel_id

The canonical table retains movement, identity, coverage, and provenance fields
needed to responsibly detect AIS discontinuities later. It does not infer a
vessel's hidden route or call a gap intentional disabling.

## Quick start

    py -3.13 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -e .[dev]
    dark-rendezvous ingest-noaa --date 2024-01-01

The command downloads the requested public NOAA daily GeoParquet object to a
bronze directory, writes normalized positions to silver Parquet,
and records a SHA-256 manifest. NOAA is U.S. terrestrial AIS for development
and validation, not high-seas claims.

For a commercial export with equivalent raw fields:

    dark-rendezvous normalize-file --input C:\data\provider_export.parquet --source spire

To retrieve derived GFW gap events or vessel identity after creating an API
token:

    $env:GFW_API_TOKEN = "<token kept outside the repository>"
    dark-rendezvous gfw-gaps --start-date 2024-01-01 --end-date 2024-01-31
    dark-rendezvous gfw-gaps-pull --start-date 2017-01-01 --end-date 2017-02-01
    dark-rendezvous gfw-presence --start 2022-01-01T00:00:00Z --end 2022-01-01T01:00:00Z --region-id 5690
    dark-rendezvous gfw-track --vessel-id <gfw-vessel-id> --start-date 2017-01-01 --end-date 2017-02-01
    dark-rendezvous gfw-identity --query 9175717

See [AIS ingestion architecture](docs/ais-ingestion.md) for source boundaries,
the schema, and commands; see the [Bronze backfill runbook](docs/bronze-backfill-runbook.md)
for a separate-agent ingestion handoff. The [targeted raw-AIS plan](docs/targeted-raw-ais-plan.md)
defines the candidate-driven minute-level acquisition workflow and the
synthetic-data boundary. [REPO_MAP.md](REPO_MAP.md) is the authoritative
navigator for code, data locations, lineage, and legacy directories.
