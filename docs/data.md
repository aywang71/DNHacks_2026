# Data policy and provenance

## Public archive boundary

This repository is a lightweight final archive, not a distribution point for
bulk API responses or model-training material. The committed files fall into
three groups:

| Material | Location | Archive status |
| --- | --- | --- |
| Source event archive and reference inputs | `data/raw/`, `data/reference/` | Committed when compact and attributable. |
| GapPair methods, queue, and maps | `data/derived/*.json`, `code/frontend/public/data/` | Committed as the frozen demonstration snapshot. |
| GFW retrievals, Parquet, operational logs, Presence replay, and model outputs | `data/bronze/`, `data/silver/`, `data/logs/`, `code/frontend/public/data/presence/`, `output/` | Local-only and ignored. |

Local-only material is not available after a fresh clone. It must be acquired
again from its upstream source by an authorized operator; it must never be
replaced with fabricated data simply to make the Presence workspace appear
populated.

## Retained snapshot

The static GapPair assets are derived from the **Global Fishing Watch
AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0**. The committed
`methods.json` supplies browser-visible attribution, source descriptions, and
method configuration. The 434-record queue is a retrospective screening export
for fishing vessels in 2017-2019.

`data/raw/disabling_events.zip` is the compact source archive. Extract it with:

```bash
unzip -o data/raw/disabling_events.zip -d data/raw
```

The extracted CSV and all Parquet outputs are ignored. `data/reference/`
contains local lookups and Natural Earth 1:10m coastline geography; the
coastline is public-domain data.

## Evidence semantics

- Source corpus rows are derived disabling-event records, not raw AIS messages.
- Gap endpoints are observations reported by the source corpus. An AIS gap does
  not observe a vessel's path during the gap.
- Meeting points, reachable sets, and gap projections are heuristic estimates.
- Presence exports, when an operator generates them locally, are hourly
  grid-cell centres rather than raw AIS fixes.
- No asset in this project establishes a transfer, intent, wrongdoing, or a
  hidden route.

## Reacquisition and retention

The source code preserves ingestion and exporter commands for transparency, but
they are not a promise that historical API data is still available or that an
operator has permission to retrieve it. Use a secret manager or local ignored
`.env` for provider credentials. Before publishing any regenerated output,
review its upstream terms, attribution, sensitivity, size, and whether it is
actually needed for the static demo.
