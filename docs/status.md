# Final archive snapshot

This is the completed 2026 DNHacks repository, preserved as a research
prototype rather than an active product.

## Included and verified

- The React/Vite frontend contains the frozen 434-record GapPair queue,
  candidate geometry, methods metadata, and the independent ship-suspicion
  snapshot.
- The Node backend tests passed: 32 tests. The frontend tests passed: 16 tests.
  The frontend production build completed successfully on Node 24.18.0.
- Python ingestion, pipeline, and model source remain available for review.
  On Python 3.13, the archive suite passes 45 tests and skips 15 tests that
  explicitly require local source/derived data.

## Intentionally not included

Raw GFW API retrievals, normalized Parquet tables, operator logs, model-training
artifacts, temporary research captures, and Presence replay shards are excluded
from the archive tip. This makes the final tree a practical source-and-demo
archive and avoids redistributing bulk upstream material. Existing Git history
still contains the former bulk blobs; reducing clone size or removing that
history requires a separate, owner-approved history rewrite.

## Known boundaries

- The GapPair queue is an analytical triage surface, not an allegation engine.
- It is based on a 2017-2019 fishing-vessel corpus and cannot establish a
  rendezvous, transfer, intent, or crime.
- The optional Presence workspace has no committed dataset; it visibly reports
  unavailable data in a fresh clone.
- The ship-suspicion snapshot is experimental and has no deployment claim.
- Historic plans and handoffs are retained under `docs/archive/` for context;
  they are not current instructions.

See [ARCHIVE.md](../ARCHIVE.md) for release and GitHub-finalization steps, and
[data policy](data.md) for source and licensing boundaries.
