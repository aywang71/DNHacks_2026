# GapPair / Dark Rendezvous — whole-project status handoff

Snapshot: 2026-09-05 18:19:10 EDT  
Workspace: `/Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026`  
Branch / HEAD: `Tanner-dev` / `2960871`  
Purpose: give a new agent an accurate status of the **entire current project**, not merely its branch history.

## Executive state

The repository contains two related but currently unintegrated products:

1. **Dark Rendezvous ingestion / vessel-presence infrastructure** in `src/dark_rendezvous/`, existing frontend
   source, and optional GFW data artifacts.
2. **GapPair**, the newly built Python pipeline that turns the 2017–2019 AIS-disabling corpus into explainable
   paired-dark candidates and static frontend artifacts.

GapPair has completed its inputs, pairing, feasibility, context, permutation-null, references, and default
corroboration stages. Feature/scoring and export are actively being implemented; narration/verifier and frontend
integration are not started. The frontend still renders mock data by default, not the generated GapPair data.

## Current workspace and Git state

```text
Current branch: Tanner-dev
Current HEAD:   2960871
Tracked diff:   data/derived/exclusions.json only (provenance update)
Untracked:      new pipeline/reference/data/test artifacts, generated frontend public data,
                handoff documents, pull script, and plan files
git diff --check: clean at snapshot time
```

The worktree is intentionally dirty because the backend implementation is in progress. Do **not** reset, clean,
switch branches, or blindly merge another branch into it.

For branch topology and remote-branch recommendations, read
[`branch_audit_handoff.md`](branch_audit_handoff.md). In short: local `main` and `andrew-dev` are already merged and
stale; do not wholesale merge `origin/main`, `origin/andrew-dev`, or `origin/will-dev`.

## Backend / pipeline status

### Completed stages and outputs

| Stage | Module / primary outputs | State | Evidence / notes |
|---|---|---|---|
| S0 reference | `pipeline/reference.py`, `data/reference/*` | complete | card tables, RFMO map, class speeds; 6 targeted tests pass |
| S1 load | `pipeline/load.py`, `gap_events.parquet`, `exclusions.json` | complete | 55,368 rows; 54,553 valid MMSIs; 484 dateline rows |
| S3 pair | `pipeline/pair_t0.py`, `candidates_t0.parquet`, queue list | complete | 434 operating pairs; 212 queue MMSIs; independent review passed |
| S2 feasibility | `pipeline/feasibility.py`, `feasibility.parquet`, `loose_feasibility.json` | complete | showcase tau 38.564h / speed .919kn; loose 18,775 / 18,735 feasible |
| S4 context | `pipeline/context.py`, `local_context.parquet`, `components.parquet` | complete with plan conflict | component / sequential metrics match; two supplied acceptance figures conflict with the written definition (details below) |
| S5 null | `pipeline/nulls.py`, `null_results.json`, `p_cell.parquet` | complete | 20 draws: null mean 12.4, lift 35.0x, 30.2s including ladder |
| S7 default corroboration | `pipeline/corroborate.py`, `corroboration.parquet` | complete | 434 default `no_coverage` rows; no network access |
| T9 GFW pull helper | `scripts/pull_queue_events.py` | complete / unrun against live GFW | 7 mocked tests pass; safe dry-run/resume/retry behavior; requires Andrew's token to pull real data |

### In progress

| Stage | Owner status | Dependency |
|---|---|---|
| S6 features + score | `pipeline/features.py`, `pipeline/score.py`, `features.parquet`, `scores.parquet` being implemented | consumes S0/S2/S3/S4/S5/S7 outputs |
| S8 export | `pipeline/export.py`, export tests being implemented | full materialization waits for S6 `scores.parquet` |

### Not started / intentionally conditional

| Stage | Reason |
|---|---|
| S1′ GFW gap enrichment | blocked until a **complete 2017–2019** GAP Bronze retrieval exists; remote raw pages do not satisfy this condition automatically |
| S9 narration + verifier | not started; requires an API key/network decision and is outside the offline critical path |
| Frontend GapPair integration | not started; static P0 artifacts exist, but React source has not been wired to them |

### Critical S4 plan inconsistency

Do not silently change this code merely to force the plan’s numbers. A direct recomputation outside `context.py`
confirmed:

- The written S4 definition says `local_dark_count` is the **union** of shutoff and reappearance neighbor events,
  excluding the pair's two own events. That produces median / p90 / zero counts of **7 / 35 / 16**.
- The handoff's asserted **3 / 25 / 37** exactly corresponds to **shutoff-only** counts (observed p90 24.8).
- Valid-MMSI filtering, unique-vessel instead of event union, duplicate handling, and own-event exclusion do not
  reconcile the two definitions.
- The stated strict twin rule (`same class/flag`, `abs(length) < .5m`, `abs(tonnage) < 1 GT`) produces **183**, not
  asserted 181. The two additional valid pairs are `t0-fcb811bbca42` and `t0-15e5ad8fc1ce`; each is a TWN
  squid-jigger pair with a .025m length delta and equal 998 GT tonnage.

The implementation currently follows the explicit definition, preserves off/on counts for audit, and is suitable for
downstream scoring. A human/product decision is needed before changing the displayed methods claim.

### Key generated artifacts presently on disk

```text
data/derived/gap_events.parquet             55,368 normalized gap events
data/derived/candidates_t0.parquet          434 operating candidates
data/derived/feasibility.parquet            434 joint-feasibility rows
data/derived/local_context.parquet          contextual neighbors / history
data/derived/components.parquet             graph components
data/derived/null_results.json              20-draw run at snapshot time
data/derived/p_cell.parquet                 candidate cell p-values
data/derived/corroboration.parquet          434 default no-coverage rows
data/derived/queue_mmsis.txt                212 distinct queue MMSIs
code/frontend/public/data/*.json            untracked P0 fixture artifacts
```

Generated Parquet/JSON is deliberately not a substitute for a commit. Regenerate it from stages rather than merging
binary outputs by hand.

## Data status

- `data/` is about **2.0 GB**.
- Authoritative GapPair source is `data/raw/disabling_events.csv`: **55,369 lines** including header (55,368 events).
- It covers fishing-vessel AIS disabling events in 2017–2019.
- Large Bronze/Silver trees exist but should not be scanned or treated as validated GapPair input unless a stage
  explicitly consumes a complete manifest.
- Existing GFW Presence data represents coarse hourly grid-center presence, not raw AIS and not rendezvous evidence.
- The GFW identity/events helper is offline-safe in this workspace. Running it requires `GFW_API_TOKEN`; do not put a
  token into source, logs, manifests, or this handoff.

## Existing ingestion package

`src/dark_rendezvous/` provides provider-neutral AIS normalization plus NOAA/GFW pull tooling. Its status:

- Existing modules include canonical contract, CLI, storage, NOAA provider, GFW gaps/presence/tracks providers.
- Its focused existing test suite passed at snapshot time: **11 passed in 0.77s**
  (`test_contract`, `test_gfw`, `test_gfw_pull`, `test_noaa`).
- Top-level README remains ingestion-oriented and deliberately does not claim that gap absence proves intentional
  disabling or a hidden route.

### Environment / packaging mismatch

The active GapPair implementation uses `.venv` with Python 3.14, pandas 3.0.5, NumPy 2.5 and PyArrow 25. In contrast:

- `pyproject.toml` says `requires-python = >=3.11,<3.14`, pandas `<3`, PyArrow `<22`, and includes Shapely.
- `requirements.txt` carries the same older pins.

The new `pipeline/` deliberately avoids Shapely and works in the active environment, but a clean package install using
the manifests will not reproduce it. Do not “fix” this by installing packages during the implementation pass; make a
separate dependency/packaging decision before release.

## Frontend status

### What exists

- `code/frontend/` is a Vite + React + TypeScript + MapLibre application.
- It has search, risk filters, investigation/evidence/timeline panels, local watch/case/notes state, and a printable
  evidence brief.
- The map currently renders local Natural Earth land/coastlines only. It explicitly reports that no vessel data is
  displayed and does not render GapPair candidates, tracks, observed endpoints, inferred geometry, reachable rings,
  or AOIs.
- Default data mode is offline mock. The mock data is oil/shipping-style; GapPair uses fishing vessel pairs.
- API mode only calls `GET /risk-events` and directly casts response JSON to `Vessel[]`; it has no schema adapter or
  validation.

### GapPair integration gap

The new untracked P0 files under `code/frontend/public/data/` (`risk-events.json`, `methods.json`,
`narratives.json`) are structurally useful but **unused** by React source. They contain fishing-pair records and
explainability fields that exceed the current flat `Vessel[]` model:

```text
vessels, window, meetingPoint, jurisdiction, scores, features, nullModel,
neighbours, explanations, corroboration, track, sources, attribution
```

The plan's frontend work remains necessary: add a static provider, type adapter, data-state indication, map layers,
score bars, methods/narrative UI, attribution, and safe ISO-time formatting. `lastSeen` is a display string in mocks
but ISO 8601 in GapPair output.

### Frontend quality/status limits

- No frontend test script or test files are currently configured in the checked-out source.
- `node_modules` is absent, so no frontend build was run for this audit.
- `code/frontend/public/` is untracked, so generated GapPair data will not ship until intentionally added.

## Presentation status

- `presentation/` is an 8-slide Slidev deck with Netlify/Vercel build configuration.
- It is pitch-ready structurally but not wired to live GapPair output.
- It contains illustrative oil-tanker/sanctions framing while the actual corpus/fixture is fishing-pair data.
- Slide 7 still says “DETAIL TO BE ADDED.”
- There are no presentation tests and no `node_modules`; build/export status is unknown.
- The deck imports Google Fonts remotely; this conflicts with an offline-demo goal.

## Branch / integration position

Read [`branch_audit_handoff.md`](branch_audit_handoff.md) before any branch operation. Summary:

- Local `main` and `andrew-dev` are already ancestors of `Tanner-dev` and stale.
- `origin/main` is diverged and includes both remote Will and Andrew work.
- `origin/will-dev` is one presence-replay commit. It is potentially cherry-pickable in a clean worktree, but its
  snapshot-specific real-data test is stale against Tanner's expanded Bronze tree.
- `origin/andrew-dev` has about 3.09M lines of remote-only changes, mostly raw payloads/logs, plus optional Atlantes
  experimentation. Do not merge it wholesale.

## Safe next steps for a new agent

1. Let S6 complete, then run S8 export against the current 20-draw null output.
2. Run the pipeline suite only after no other agent is writing shared derived outputs:

   ```bash
   .venv/bin/python -m pytest -q tests/test_pipeline_*.py tests/test_pull_queue_events.py
   .venv/bin/python -m pipeline.run --stage score --stage export
   ```

3. Decide whether to accept the S4 explicit-definition results or revise the specification/methods claim. Do not
   secretly alter neighbor/twin logic to hit stale acceptance counts.
4. Decide whether to run the GFW pull helper on Andrew's token-bearing machine. It is optional for the offline
   pipeline; never wait on it to export P1.
5. Implement the planned frontend static-data adapter and map/UI work, then install frontend dependencies in a clean
   context and run:

   ```bash
   cd code/frontend && npm ci && npm run build
   cd ../presentation && npm ci && npm run build && npm run export
   ```

6. Make dependency pins/release packaging a deliberate follow-up task; do not edit `pyproject.toml` merely to fit the
   current temporary `.venv` without testing the original ingestion package.

## Audit artifacts

- `data/derived/orchestrator_log.md` — task-level pipeline record and accepted observations.
- `data/derived/branch_audit_handoff.md` — current branch topology, remote-work summary and merge recommendations.
- `data/derived/project_status_handoff.md` — this whole-project snapshot.

