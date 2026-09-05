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
Git-ignored bronze directory, writes normalized positions to silver Parquet,
and records a SHA-256 manifest. NOAA is U.S. terrestrial AIS for development
and validation, not high-seas claims.

For a commercial export with equivalent raw fields:

    dark-rendezvous normalize-file --input C:\data\provider_export.parquet --source spire

To retrieve derived GFW gap events or vessel identity after creating an API
token:

    $env:GFW_API_TOKEN = "<token kept outside the repository>"
    dark-rendezvous gfw-gaps --start-date 2024-01-01 --end-date 2024-01-31
    dark-rendezvous gfw-gaps-pull --start-date 2017-01-01 --end-date 2017-02-01
    dark-rendezvous gfw-identity --query 9175717

See [AIS ingestion architecture](docs/ais-ingestion.md) for source boundaries,
the schema, and commands.
