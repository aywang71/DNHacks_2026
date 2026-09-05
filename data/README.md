# Data directory

The repository-wide data catalog and lineage guide is
[REPO_MAP.md](../REPO_MAP.md). It distinguishes raw AIS from GFW-derived GAP
events and hourly Presence, and it identifies every supported Bronze, Silver,
reference, and operational location.

## Frozen research corpus

`disabling_events.zip` is the Global Fishing Watch AIS-disabling corpus (Welch
et al. 2022): 55,368 derived GAP events for 2017-2019. It contains event
endpoints and attributes, not the underlying continuous AIS message stream.
Source: https://github.com/GlobalFishingWatch/AIS-disabling-high-seas (branch
`master`, `data/disabling_events.zip`). Its license is CC BY-NC 4.0; attribute
GFW in any UI or other reuse.

`gfw_config.py` is the upstream corpus filter configuration (12-hour minimum
gap and more than 50 nautical miles from shore at the off endpoint). The
current loader does not execute it. `exclusions.json` is a historical
quarantine checkpoint from a previous corpus loader, not a current input.

New work belongs in `bronze/` and `silver/`, not legacy `raw/` or `derived/`.
Use [docs/ais-ingestion.md](../docs/ais-ingestion.md) for the active schema and
commands.
