# Maritime Risk Intelligence API contract

The frontend defaults to `VITE_DATA_MODE=mock`, which is offline-safe. Set `VITE_DATA_MODE=api` and `VITE_API_BASE_URL=https://api.example.org` to use this API.

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
