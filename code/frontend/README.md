# wake.ai frontend

The Vite application has two separate analytical workspaces:

- **Presence** replays imported GFW hourly Presence grid-cell centres.
- **Investigation queue** reads the static GapPair paired-dark export and the
  independent ship-suspicion snapshot.

They share a shell, but not an identity bridge. A CSV-reference GapPair record
is keyed by MMSI and does not become a GFW Presence replay simply because it is
shown in the same application.

## Run locally

From the repository root:

```bash
npm --prefix code/frontend ci
npm --prefix code/frontend run dev
npm --prefix code/frontend test
npm --prefix code/frontend run build
```

The backend Presence importer is needed only when regenerating Presence assets:

```bash
npm --prefix code/backend run import:presence
```

## Static asset contracts

| Asset | Producer | Frontend consumer | Semantics |
| --- | --- | --- | --- |
| `public/data/presence/catalog.json` and daily shards | `code/backend` Presence importer | `src/presence/` and the Presence workspace | GFW hourly grid-cell centres, not raw AIS fixes. |
| `public/data/risk-events.json` | S8 `pipeline.export` | `src/data/provider.ts`, `InvestigationPanel` | Ranked paired dark-gap screening records. The browser does not silently fall back to mock candidates. |
| `public/data/tracks/<id>.geojson` | S8 `pipeline.export` | Embedded track is used by the candidate map; files are audit artifacts | Observed endpoints and estimated projections/rings are distinguished by `observationStatus`. |
| `public/data/ship-suspicion.json` | `scripts/export_ship_suspicion.py` | `ShipSuspicionPanel` | Experimental top-200 individual-vessel scores, separate from GapPair. |

`src/types.ts` mirrors the static contracts. `pipeline/export.py` is the
authoritative runtime validator for a GapPair record. Additive contract fields
are compatible; renaming or removing a required field needs coordinated changes
to the exporter and this frontend.

## UI behavior that must remain explicit

- Solid endpoint points are observed; dashed gap projections, meeting points,
  and reachable sets are estimated. Do not render an inferred route as an AIS
  observation.
- GapPair score sliders are a local analyst view. They re-rank the queue but do
  not mutate the exported score, label, evidence tier, or record.
- A `null` score component is unavailable evidence, not a zero-valued score.
- The ship-suspicion model can legitimately have no feature-contribution list
  when its saved model cannot be safely loaded. Do not synthesize one.
- Cases, watchlists, and notes are local demo state; no case API is called.

## Before changing the UI

1. Read [the architecture](../../docs/architecture.md) and [the developer
   guide](../../docs/development.md).
2. Regenerate an asset through its producer instead of editing it by hand.
3. Run the frontend test and build commands above.
4. If a contract or evidence-semantic change is made, update
   [the verification guide](../../docs/verification.md) and the relevant live
   documentation.

See [the viewer data flow](../backend/DATA_FLOW.md) for Presence-specific asset
details, [the candidate-pipeline reference](../../docs/candidate-pipeline.md)
for GapPair, and [the ship-suspicion model notes](../../docs/ship-suspicion-model.md)
for the independent model.
