# Architecture

## Subsystem overview

```mermaid
flowchart LR
    S["GFW API / NOAA"] --> I["Dark Rendezvous ingestion"]
    I --> D["data/bronze + data/silver"]
    D --> N["Node presence importer"]
    N --> P["public/data/presence"]
    P --> V["Will's presence viewer"]
    D --> G["GapPair pipeline<br/>CSV corpus today"]
    A["2021 API corpus (planned)"] -.-> G
    G --> R["data/derived"]
    R -.-> C["risk-events.json / candidates.json<br/>(planned)"]
    C -.-> CP["Viewer Candidates panel<br/>(planned)"]
```

Dark Rendezvous writes and retrieves the source material. The Node importer independently turns GFW Presence reports into static viewer assets. GapPair independently processes the 2017–2019 CSV today. The proposed 2021 loader and viewer bridge are not implemented.

## Data contracts

| Presence contract | GapPair candidate record | Planned bridge |
| --- | --- | --- |
| Defined in [`code/backend/contracts/presence.ts`](../code/backend/contracts/presence.ts). `Observation` has `vesselId` as `gfw:<id>`, ISO UTC `ts`, separate numeric `lat` and `lon`, `presenceHours`, dataset version, and grid resolution. `catalog.json` declares coverage and daily shards; each day has observation and vessel-index URLs plus covered hours. | The GapPair `risk-events.json` contract has `id`, `tier`, `label`, `priority`, `riskScore`, two `vessels` with MMSI, `window`, `meetingPoint`, `scores`, `features`, `evidence[]`, `timeline[]`, and a track GeoJSON `FeatureCollection`. Coordinates use `[lon, lat]`; times are ISO-8601 UTC. | `candidates.json` is planned. Each candidate would add each vessel's `gfwId`, `presenceDays`, and `presenceCoverage`, then carry the candidate window, geometry, scores, evidence, and timeline into the viewer. |
| Semantics: one hourly grid-cell-centre position per vessel-hour. It is not raw AIS. Coverage records queried hours, including covered-empty hours. Assets are daily, content-hashed static shards. | `meetingPoint` and projections can be inferred. The track collection is expected to contain observed endpoints, estimated projections, an estimated meeting point, and estimated reachable rings. | `presenceDays` covers the candidate window with adjacent UTC days. `presenceCoverage` would be `full`, `partial`, or `none` from the presence catalog. |

Two integration hazards are explicit:

- Identity key: GapPair starts with MMSI while the viewer selects `gfw:<vesselId>`. The 2017–2019 CSV corpus has no GFW IDs.
- Coordinate order: the presence contract exposes separate `lat`/`lon` fields; GapPair GeoJSON and MapLibre geometry use `[lon, lat]`.

## Observed vs estimated

Estimated geometry carries `observationStatus: "estimated"` and is never presented as an observed AIS position. GFW Presence grid centres are not raw AIS and are not rendezvous evidence. Observed endpoint features remain distinct from inferred projections, inferred meeting points, and reachable rings.

## Naming map

| Name | Meaning | Current state |
| --- | --- | --- |
| `wake.ai` | Product name. | Current product name. |
| Presence viewer / `Maritime Risk Intelligence` | Will's browser viewer and its current frontend brand string. | The string remains in the frontend and should be renamed later. |
| GapPair | Tanner's paired-dark-gap candidate pipeline. | Incomplete and not integrated. |
| Dark Rendezvous | Andrew's ingestion package and `dark-rendezvous` CLI. | Used for NOAA and GFW ingestion. |
| `Wake AI` | Slidev deck name. | Existing deck naming. |

## Ownership and independent operation

| Owner | Code and data boundary | Runs independently today |
| --- | --- | --- |
| Will Pallan (`gurubazawada`) | `code/frontend` and `code/backend` | Node builds GFW Presence assets; Vite serves the browser viewer. |
| Andrew Wang (`aywang71`) | `src/dark_rendezvous` and `scripts/*.ps1` | Python CLI ingests NOAA and retrieves GFW data. GFW access needs Andrew's token. |
| Tanner Shah (`tannershah`) | `pipeline`, `tests/test_pipeline_*`, `data/reference`, `data/derived` | Python stages process the CSV corpus and write derived artifacts. |

## Integration boundary

For the viewer to show candidates, these items must exist. Each is not started:

| Needed item | Status |
| --- | --- |
| 2021-corpus loader with GFW vessel IDs | Not started. |
| Bridge export that writes `candidates.json` | Not started. |
| GFW Presence pulled per candidate window | Not started. |
| Viewer Candidates panel and candidate geometry layers | Not started. |

The three-record `risk-events.json` fixture is hand-made and the React app does not read it. The original detailed prompts are retained in [archived handoff prompts](archive/plan/handoff-prompts.md), section 14. See [data needs](data.md) for the missing inputs.
