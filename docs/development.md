# Developer guide

This guide is the starting point for a change that crosses the ingestion,
candidate-pipeline, or viewer boundary. It identifies the canonical owners of
each concern and the artifacts that must be regenerated rather than edited.

## Repository responsibilities

| Area | Canonical path | Responsibility | Do not use it for |
| --- | --- | --- | --- |
| Ingestion | `src/dark_rendezvous/` | Provider-neutral acquisition, normalization, and storage contracts. | Candidate ranking or browser UI behavior. |
| GapPair | `pipeline/` | Paired dark-gap preparation, scoring, export, and analytical provenance. | Live API serving or raw-AIS claims. |
| Viewer | `code/frontend/` | Static-asset loading, visual distinction between observations and inferences, and analyst-facing interaction. | Recomputing analytical scores in the browser. |
| Presence importer | `code/backend/` | Validation and static publication of GFW Presence replay assets. | A runtime HTTP API. |
| Input and derived data | `data/` | Source lineage, reproducible intermediate stages, and reference tables. | Hand-edited frontend state. |

The three implementation areas are deliberately decoupled. A change should
cross an area only through a documented file contract; importing another
area's internal helper is not a substitute for that contract.

## Source, derived, and published data

| Category | Locations | Rule |
| --- | --- | --- |
| Source/provenance | `data/raw/`, `data/bronze/` | Preserve exactly as acquired. Do not edit API pages, manifests, or source archives in place. |
| Normalized data | `data/silver/` | Regenerate through the ingestion command that produced it. Retain the source semantics in the normalized fields. |
| Pipeline intermediates | `data/derived/` | Treat Parquet and checkpoint files as stage outputs. Rerun the producing stage after changing a stage contract. |
| Published static assets | `code/frontend/public/data/` | Generate through the appropriate exporter. The browser consumes these assets; it is not their source of truth. |
| Model experiment outputs | `output/models/` | Keep training/evaluation artifacts separate from the published viewer contract until an explicit exporter promotes them. |

Presence coordinates are hourly grid-cell centres, not raw AIS fixes. Gap
endpoints and estimated meeting geometry are likewise not observations during a
dark period. Keep those distinctions in names, copy, evidence fields, and map
styles.

## GapPair export contract

`pipeline/export.py` owns the runtime validation of a candidate record;
`code/frontend/src/types.ts` is its browser-facing TypeScript mirror. Make a
contract change in both places, then regenerate the static export.

The compatibility rules are:

- Keep required fields and their meanings stable. Additive fields are allowed;
  renames and removals require a coordinated consumer change.
- Use ISO-8601 UTC strings for times and `[lon, lat]` for GeoJSON positions.
- Use JSON `null` for unavailable evidence or score components. Do not convert
  unavailable evidence into zero merely to make a visualization simpler.
- Mark inferred projections, meeting points, and reachable geometry with
  `observationStatus: "estimated"`; observed endpoints remain
  `observationStatus: "observed"`.
- Treat a score as a transparent ranking aid, not proof of a rendezvous,
  transfer, intentional disabling, or crime.

The configured scoring weights live in `pipeline/config.py`. Exported methods
metadata should be regenerated whenever those weights or a score definition
changes.

## Pipeline dependency path

The runner in `pipeline/run.py` is the canonical stage registry. A normal
reference-corpus rebuild follows this order:

```text
reference → load → pair → feasibility → context → null → corroborate
          → features → score → export
```

Selected stages can be run individually, so the operator is responsible for
ensuring their upstream files exist and come from the intended corpus. The
`narrate` stage is intentionally separate from the analytical export path.

## Safe working agreement

Before editing, inspect `git status --short` and limit a change to its owned
paths. In particular:

- Do not manually edit generated presence shards, `risk-events.json`, methods
  metadata, or pipeline Parquet outputs to make a screen appear correct.
- Do not delete, unstaged, rename, or bulk-normalize existing files as a side
  effect of an unrelated feature. Make a reviewed target list first.
- Keep credentials outside the repository. `GFW_API_TOKEN` is an environment
  secret and must not appear in a log, fixture, manifest, or committed file.
- Preserve the distinction between a failed command and a successful result:
  inspect expected artifacts and their contents after an exporter runs.

## Documentation maintenance

Use the docs according to their purpose:

| Need | Source of truth |
| --- | --- |
| Current verified behavior and open gaps | [status.md](status.md) |
| System boundary and consumer contracts | [architecture.md](architecture.md) |
| Pipeline stages, definitions, and output semantics | [candidate-pipeline.md](candidate-pipeline.md) |
| Input coverage, provenance, and evidence limits | [data.md](data.md) |
| Repeatable release checks | [verification.md](verification.md) |

Update the relevant live document in the same change as a material behavior,
contract, command, or evidence-semantics change. Move superseded planning
material to `docs/archive/` rather than leaving competing instructions in live
documentation.
