# Reference tables

These wake.ai static inputs support GapPair validation and enrichment. `pipeline/reference.py` loads the first four tables. The coastline file is not a GapPair reference-table input: `prepare-atlantes-presence` reads it through `src/dark_rendezvous/atlantes_adapter.py` for the experimental Presence-to-Atlantes adapter. `psma_parties.csv` is header-only, so PSMA status is unknown. See [docs/data.md](../../docs/data.md) for inventory and evidence limits.

| File | Source | Row count | Consumer |
| --- | --- | ---: | --- |
| `class_speeds.json` | Local values required to match `pipeline.config.V_KN` | 8 values | `pipeline/reference.py` |
| `eu_iuu_cards.csv` | Curated EU IUU-card history; its `source_url` column is unpopulated | 21 | `pipeline/reference.py` |
| `psma_parties.csv` | Optional local PSMA-party table | 0; header only | `pipeline/reference.py` |
| `rfmo_names.json` | Local RFMO code-to-name lookup | 13 values | `pipeline/reference.py` |
| `ne_10m_coastline.geojson` | Natural Earth 1:10m coastline, public domain | 1 GeoJSON feature collection | Experimental Atlantes ingestion |
