# Data

This directory holds wake.ai source archives, immutable GFW API records, normalized tables, GapPair outputs, static reference tables, and backfill logs. The full inventory, evidence limits, coverage gaps, and regeneration notes are in [docs/data.md](../docs/data.md).

| Folder | Contents |
| --- | --- |
| `raw/` | The tracked disabling-events ZIP, its ignored extracted CSV, and upstream filter configuration. |
| `bronze/` | Tracked immutable GFW GAP, Presence, and identity API responses with manifests. |
| `silver/` | Tracked normalized Parquet outputs and manifests. |
| `derived/` | GapPair working outputs and checkpoints. |
| `reference/` | Static lookup tables and Natural Earth coastline geometry. |
| `logs/` | Presence-backfill log and resumable state. |

`data/raw/*.csv` and `data/derived/*.parquet` are ignored. Bronze is tracked by decision. Other files follow their existing tracked status.

Extract the source CSV when needed:

```bash
unzip -o data/raw/disabling_events.zip -d data/raw
```

Pandas 3 parses the corpus timestamps as `datetime64[us, UTC]`. Use `Timedelta` arithmetic for durations and retain microsecond precision.
