# Archived data policy

This public repository keeps only compact materials needed to understand the
prototype and run the frozen GapPair browser demonstration:

- `raw/disabling_events.zip`: the cited 2017-2019 AIS-disabling event corpus
  archive; extract it locally when running the Python pipeline.
- `reference/`: compact lookup tables and Natural Earth coastline geometry.
- `derived/*.json` and `derived/*.txt`: small, inspectable pipeline
  checkpoints and the exported-summary evidence.

The following are intentionally local and ignored by Git:

- `bronze/`: raw GFW API retrievals and manifests;
- `silver/`: normalized Parquet output;
- `logs/`: operational pull state and logs;
- `derived/*.parquet`: regenerable intermediate tables.

They can be recreated only by an operator with the appropriate upstream access
and credentials. Do not add them, private tokens, or large result sets to this
archived repository. The frontend's optional Presence replay assets follow the
same policy under `code/frontend/public/data/presence/`.

The retained browser-facing GapPair snapshot includes its own attribution and
method limits in `code/frontend/public/data/methods.json`. See
[docs/data.md](../docs/data.md) for provenance and interpretation boundaries.
