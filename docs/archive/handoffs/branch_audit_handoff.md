> **Archived 2026-09-05.** Historical planning/handoff document for wake.ai. Superseded by [docs/candidate-pipeline.md](../../candidate-pipeline.md), [docs/status.md](../../status.md) and [docs/data.md](../../data.md). Status claims, branch advice and any schedules in this file are stale and must not be acted on.

# Branch audit handoff — GapPair repository

Generated: 2026-09-05 17:57:32 EDT  
Workspace examined: `/Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026`  
Audit method: read-only Git inspection only; no refs moved, no checkout, fetch, merge, or source edits.

## Executive decision

Do **not** merge `origin/main`, `origin/andrew-dev`, or `origin/will-dev` wholesale into `Tanner-dev` while the
GapPair backend is being built. They contain a separate vessel-presence replay feature and millions of lines of raw
retrieval artifacts. The useful code is selectively reusable, but its data contracts are not the current GapPair
candidate contract.

Local `main` and local `andrew-dev` are already contained in `Tanner-dev`; the remote tracking branches are the
relevant unmerged work.

## Current topology

```text
local main       63a2796  ── ancestor of Tanner-dev (stale)
local andrew-dev f08ad5a  ── ancestor of Tanner-dev (stale)

Tanner-dev       2960871  ── current backend worktree
       │
       ├── diverged from origin/main       1636ce7
       │       ├── contains origin/will-dev   27daf29
       │       └── contains origin/andrew-dev dce16e1
       │
       └── common history includes older Andrew ingestion/presence work
```

`Tanner-dev` and `origin/main` have a criss-cross merge topology: their best merge bases are both `0ef2af4` and
`2840612`. Do not reason about their relationship from a single plain `git merge-base` result.

| Ref | Tip | Relative to `Tanner-dev` | Key conclusion |
|---|---|---|---|
| `main` | `63a2796` | ancestor / already merged | stale planning + early UI work only |
| `andrew-dev` | `f08ad5a` | ancestor / already merged | stale local pointer |
| `origin/main` | `1636ce7` | diverged; not merged | cumulative presence frontend/backend plus Andrew artifacts |
| `origin/andrew-dev` | `dce16e1` | diverged; not merged | 5 remote-only commits, mostly raw GFW artifacts |
| `origin/will-dev` | `27daf29` | diverged; not merged | one focused presence-replay commit |

Useful reproduction commands:

```bash
git branch -a --no-color
git merge-base --all Tanner-dev origin/main
git rev-list --left-right --count Tanner-dev...origin/main
git rev-list --left-right --count Tanner-dev...origin/andrew-dev
git rev-list --left-right --count Tanner-dev...origin/will-dev
git show --stat --summary 27daf29
git show --stat --summary d490c82
git show --stat --summary dce16e1
```

## `main` / `origin/main`

### State

- Local `main` at `63a2796` is already ancestrally merged into `Tanner-dev` and is reported as 24 commits behind
  `origin/main`.
- `origin/main` at `1636ce7` is not merged into `Tanner-dev`; `git rev-list --left-right --count
  Tanner-dev...origin/main` reports `5 9`.
- `origin/main` contains both `origin/will-dev` and `origin/andrew-dev`.

### What remote main adds

The remote-only sequence includes the presence replay UI and its supporting Node backend contract:

- `27daf29`: vessel-presence import, timeline/replay UI, MapLibre integration, provider/types and Node tests.
- `d490c82`: moves presence preparation, schemas, static export and tests into `code/backend`.
- `dce16e1` and preceding Andrew commits: identity/presence/GAP raw artifacts and experimental positioning outputs.
- `1636ce7`: merge of the presence backend/frontend and Andrew data line.

### GapPair compatibility

This is **not** the current GapPair output model.

- GapPair emits pair candidates (`risk-events.json`, `vessels[]`, `evidence[]`, `timeline[]`, scores, inferred
  meeting point, candidate tracks) with map coordinates `[lon, lat]`.
- Remote main’s active app is a vessel-presence replay. Its core observation schema uses separate `lat` / `lon`,
  `vesselId`, timestamp, coverage and presence-hours fields.
- `code/backend/README.md` on remote main describes the historical risk API as not implemented; the source package
  normalizes individual AIS positions rather than pair candidates.

### Risks

- Replacing the app would replace the GapPair investigation UX with presence replay and provides no adapter from a
  candidate to a presence record.
- Coordinate order and endpoint naming are a likely integration hazard.
- The raw-data delta is enormous: comparison shows roughly 287 changed files / 3.09 million inserted lines against
  remote main, much of it data artifacts. Blind integration risks repository bloat and conflicts.

### Recommendation

Treat remote main as an adjacent feature. If it becomes needed, define a versioned GapPair candidate schema and an
explicit adapter first. Selectively port only reusable import/export components after that decision.

## `andrew-dev` / `origin/andrew-dev`

### State

- Local `andrew-dev` (`f08ad5a`, `jan 2017`) is already merged into `Tanner-dev` and is stale.
- `origin/andrew-dev` (`dce16e1`) is not merged. It has five unique commits after the shared history:
  `dbb6898`, `afba353`, `9ef83eb`, `14a8b62`, and `dce16e1`.
- `git rev-list --left-right --count Tanner-dev...origin/andrew-dev` is `24 5`.
- Its cumulative remote-only diff is about 257 files and 3,086,571 insertions, almost entirely raw artifacts.

### Already present in Tanner-dev

The earlier Andrew ingestion work is already available:

- Bronze-first GFW GAP pulls, optional Silver generation, manifests and resume state.
- Canonical-position `position_semantics`.
- GFW Presence normalization and its explicit semantic label `gfw_presence_grid_center_hourly`.
- CLI/provider/runbook/test work around GFW data handling.

### Remote-only work

- `dbb6898` / `afba353`: large sets of raw GFW GAP page/manifest files and a resume note that expressly documents
  incomplete ranges. Their existence does **not** establish 2017–2019 coverage.
- `9ef83eb`: experimental GFW Presence → Atlantes activity adapter, runner, CLI subcommand, tests, coastline
  reference and documentation.
- `14a8b62` / `dce16e1`: raw identity batches, logs and experimental activity predictions; no production identity
  normalization or GapPair join.

### GapPair relevance and limits

- The existing GFW contract is useful for optional enrichment, but presence IDs are `gfw:<vessel id>`, not MMSI/IMO.
  Any GapPair join needs an auditable identity-resolution bridge.
- Atlantes is an optional, low-trust activity prior only. It derives motion from hourly grid centers, is marked
  experimental/not raw AIS/not rendezvous evidence, requires at least 100 points by default, and must not alter the
  primary paired-dark inference or scoring without a separate decision.
- The committed experiment manifest uses machine-specific Windows paths and the runner expects a separate Atlantes
  checkout/environment (documented Python 3.10 expectation), so it is not portable production infrastructure.

### Recommendation

Do not merge the remote branch. Preserve the already merged GFW ingestion pieces. If an activity-prior experiment is
needed, selectively reimplement or port the small `9ef83eb` adapter/test/doc slice behind an optional enrichment
boundary with provenance, coverage gating and identity resolution. Regenerate raw data locally rather than importing
the remote Bronze/log payloads.

## `origin/will-dev`

### State

- No local `will` branch exists; inspect `origin/will-dev`.
- Tip `27daf29` is a single unique commit, *Add vessel presence timeline, data import, and tests*.
- It is not merged into `Tanner-dev`; `git rev-list --left-right --count Tanner-dev...origin/will-dev` is `10 1`.
- It is already an ancestor of `origin/main`.

### What it adds

`27daf29` changes 21 frontend/documentation files (`+1039/-91`):

- Static GFW Presence importer that recursively reads Bronze report/manifest pairs and writes
  `public/data/presence/{catalog,daily-observations,daily-vessels}` assets.
- Presence provider/types, UTC-safe timeline functions, deterministic deduplication and metadata selection,
  day caching, coverage semantics and trails.
- Reworked `App.tsx` / `MapPanel.tsx`, new `Timeline` / `VesselPanel`, and static browser replay UI.
- Node tests for import, provider and timeline behavior; `npm run import:presence`.
- `code/backend/DATA_FLOW.md`, which explicitly says this is static-browser-only and has no backend service.

### GapPair relevance and risks

- It does not produce or consume GapPair candidate IDs, scores, tracks, narratives or `risk-events.json`.
- It has a future reusable seam in `PresenceDataProvider`, but must remain separate from the candidate contract.
- Its one real-data test is stale against Tanner’s expanded Bronze snapshot: it hardcodes 33,452 observations / 25
  covered hours / 2 days, while Will’s ref has 6 report/manifest files and Tanner has 72. The importer discovers all
  reports recursively, so the test must be regenerated or changed to fixture/invariant assertions.
- Import is intentionally strict: a discovered report without a sibling manifest or compatible metadata blocks
  publication rather than silently yielding partial output.
- Generated presence assets are ignored; they must be produced locally. The active worktree already has untracked
  frontend public data from the GapPair P0 fixture, so never apply source changes directly into this dirty worktree.

### Recommendation

If the team wants the replay feature, use a clean isolated worktree and cherry-pick the single commit rather than
merging a branch. Then update the snapshot-specific test, run `npm ci`, `npm run import:presence`, `npm test`, and
`npm run build`. Do not treat this as a replacement for the GapPair backend.

## Recommended integration order for another agent

1. Keep `Tanner-dev` as the authoritative GapPair backend worktree; do not merge a remote branch during the current
   implementation pass.
2. Finish the paused GapPair Wave 1 re-reviews before advancing its dependency graph.
3. Decide whether the product needs vessel-presence replay in addition to pair investigation. If yes, agree on one
   versioned boundary/adaptor first; preserve `[lon, lat]` vs separate `lat`/`lon` semantics explicitly.
4. For a presence replay experiment, use a clean worktree and cherry-pick Will’s one commit, then update its
   snapshot-dependent test for the present Bronze corpus.
5. For optional activity priors, treat Andrew’s Atlantes work as experimental enrichment with no authority over
   rendezvous conclusions; avoid importing its raw data/log artifacts.

## Current backend-orchestration context

At the time of this audit, GapPair implementation remains intentionally paused at the user’s request:

- T1 (load + T0 pairing) passed independent red-team review: 55,368 events, 434 operating pairs, 212 queue MMSIs.
- T2 (references + P0 fixture) and T9 (queue pull script) completed repair round 1 and are awaiting fresh
  re-reviews; no later wave has started.
- T8 remains conditional on a complete 2017–2019 GAP Bronze manifest; the audited remote raw data must not be
  mistaken for that condition.
