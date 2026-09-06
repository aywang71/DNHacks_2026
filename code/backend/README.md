# Maritime Risk Intelligence backend

The backend owns Silver presence validation, deduplication, static export, and the data contracts consumed by the frontend. It runs as an offline Python/Parquet pipeline; no HTTP API is required by the viewer.

From this directory:

```bash
npm run import:presence
npm run export:investigations
npm test
```

Install the project Python dependencies (including `pyarrow`) before importing. The importer reads normalized `data/silver/gfw_presence_hourly` Parquet and publishes into the frontend's `public/data/presence` directory. Bronze remains acquisition provenance and is not read by the viewer. The frontend's `npm run import:presence` command remains a shortcut to this backend CLI.

See [DATA_FLOW.md](DATA_FLOW.md) for the full flow, schemas, commands, and future API integration boundary.

```text
backend/
  contracts/presence.ts         Browser-safe data types
  scripts/export-presence.mjs   CLI arguments and reporting
  scripts/export-presence.py    Silver discovery, validation, deduplication, and publication
  src/presence/geometry.mjs     Dateline-aware bounds for exported days
  tests/                       Import, publication, and bounds checks
```

## Gemini AI service

`npm run dev` runs the local AI server with file watching; `npm start` serves the built portal and API at `http://127.0.0.1:3001`. Node 22+ is required. The entrypoint loads the repository-root `.env`; existing environment variables take precedence. Set `GEMINI_API_KEY` and optionally `GEMINI_MODEL` (default `gemini-3.6-flash`). Never prefix secrets with `VITE_`. No extra runtime packages are required.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/ai/status` | Return whether credentials are configured and the model name, never the key. |
| `POST /api/ai/context` | Preview the authoritative ship context without calling Gemini. |
| `POST /api/ai/report` | Generate a structured, readable vessel evidence brief. |
| `POST /api/ai/chat` | Answer a ship question with recent conversation history. |

POST bodies contain `vesselId`, optional `caseId`, `start`/`end` for presence-mode requests, optional `notes`, and `messages` for chat. Date boundaries are UTC midnight, start inclusive and end exclusive, with a 90-day maximum. For a queue case, the server looks up the matching vessel and scoring window and disregards client-supplied dates, scores, identity, or demo flags. Notes are limited to 8,000 characters. Chat accepts alternating user/assistant messages with a final user question; the frontend sends the latest five exchanges plus that question.

Context is assembled from `code/frontend/public/data`: source-reported identity, exact record counts, imported and missing coverage, up to 24 evenly sampled positions, queue score meanings, and separately labelled analyst notes. Missing files fail visibly; missing data is never silently treated as zero activity. Source references in generated output must match the provided source IDs. Output is rendered as escaped text, including in downloadable and printable report snapshots. Editing notes marks an existing report stale until regenerated. Chat and report state reset when switching ships or presence date ranges.

The service uses Gemini's [generateContent API](https://ai.google.dev/api/generate-content) with a JSON output schema and a server-side `x-goog-api-key` header. It has a 60-second provider timeout, a 64 KiB request limit, two concurrent requests, and a shared limit of 20 context/generation requests per minute. Abandoned browser requests cancel the provider call. Provider errors are mapped to actionable messages without exposing upstream request contents or credentials. Tests mock Gemini and require no key.

This is a local, single-user server bound to loopback. For a hosted deployment, put it behind your authenticated application gateway and configure `AI_ALLOWED_ORIGINS` as a comma-separated list of exact frontend origins. This service does not implement user accounts or per-user billing limits.

## Model registry and investigation queue

The active viewer now consumes the exported model queue. Models are stored in
`models/`, with configurable ensemble weights and a queue threshold in
`models/registry.json`. See [MODELS.md](MODELS.md) for inference commands,
dependencies, adding models, score contracts, and frontend integration.

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
