# Maritime Risk Intelligence backend

The backend owns presence report validation, normalization, deduplication, static export, and the data contracts consumed by the frontend. It currently runs as an offline Node pipeline; no HTTP API is required by the viewer.

From this directory:

```bash
npm run import:presence
npm test
```

No backend dependencies need installing. The importer reads `data/bronze/gfw_presence` and publishes into the frontend's `public/data/presence` directory. That output stays with the frontend so both Vite and the production static build can serve it. The frontend's `npm run import:presence` command remains a shortcut to this backend CLI.

See [DATA_FLOW.md](DATA_FLOW.md) for the full flow, schemas, commands, and future API integration boundary.

```text
backend/
  contracts/presence.ts         Browser-safe data types
  scripts/export-presence.mjs   CLI arguments and reporting
  src/presence/source.mjs       Bronze discovery, validation, normalization, deduplication
  src/presence/export.mjs       Daily aggregation and atomic asset publication
  src/presence/geometry.mjs     Dateline-aware bounds for exported days
  tests/                       Import, publication, and bounds checks
```

## Historical risk API proposal — not implemented

The following is the earlier risk/investigation API proposal. The active presence viewer does not call these endpoints or use `VITE_DATA_MODE`/`VITE_API_BASE_URL`. Keep future risk work separate from the presence contract above.

| Endpoint | Purpose |
| --- | --- |
| `GET /risk-events` | Active queue entries with vessel summary and evidence |
| `GET /vessels/:imo` | Vessel profile and risk summary |
| `GET /vessels/:imo/track` | Observed and estimated track `FeatureCollection` |
| `GET /aois` | Monitored areas as GeoJSON `FeatureCollection` |
| `POST /cases` | Create a case (`vesselImo`, `eventIds`, optional `notes`) |
| `PATCH /cases/:id` | Update status, notes, analyst or evidence selection |
| `GET /cases/:id/report` | Case report JSON, or PDF when negotiated via `Accept` |

Track, AOI and event-geometry responses use GeoJSON `FeatureCollection`. Every evidence object must provide `source`, ISO-8601 `observedAt`, `confidence` (`high`, `medium`, or `low`), and a human-readable `claim`. Estimated geometry must include `properties.observationStatus: "estimated"`; it must never be represented as an observed AIS position.

```json
{"type":"Feature","properties":{"observationStatus":"estimated","confidence":"low","source":"inference model"},"geometry":{"type":"LineString","coordinates":[[25.18,34.51],[26.12,35.04]]}}
```

API errors should return `{ "message": "plain language explanation", "code": "MACHINE_CODE" }`. The client should retain mock replay as a graceful fallback when requested by an operator; never silently treat unavailable live data as an observation.
