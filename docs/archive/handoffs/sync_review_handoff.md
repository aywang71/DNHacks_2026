> **Archived 2026-09-05.** Historical planning/handoff document for wake.ai. Superseded by [docs/candidate-pipeline.md](../../candidate-pipeline.md), [docs/status.md](../../status.md) and [docs/data.md](../../data.md). Status claims, branch advice and any schedules in this file are stale and must not be acted on.

# Review-and-sync checkpoint — GapPair backend

Checkpoint time: 2026-09-05 18:29:15 EDT  
Branch / HEAD: `Tanner-dev` / `2960871`  
Intent: **reviewable backend checkpoint, not a demo-complete product**.

## What this checkpoint is

This checkpoint provides a tested, reproducible core pipeline through candidate generation, feasibility, context,
within-cell null estimation, and default corroboration. It intentionally stops before feature assembly/scoring and
real full-queue export. No frontend source integration, narration, API enrichment, branch merge, commit, or push was
performed.

## Verified checkpoint

### Core pipeline run

The following completed successfully at the checkpoint:

```bash
.venv/bin/python -m pipeline.run \
  --stage reference --stage load --stage pair --stage feasibility \
  --stage context --stage corroborate
```

Observed output:

```text
reference: 0.4 s
load: 55,368 rows; 54,553 valid; 815 invalid; 702 blank flags; 484 dateline
pair: 434 operating candidates; 26 cross-flag; 212 queue MMSIs
feasibility: 434 operating; 433 feasible; 18,775 loose; 18,735 loose feasible
context: 434 pairs; 237 bilateral; 183 twins; 173 sequential
corroborate: 434 default no_coverage rows
```

The seeded 20-draw null stage was also materialized immediately before this checkpoint:

```text
observed=434; null_mean=12.4; lift=35.0x; showcase p_cell=1/21
runtime including ladder ≈30.2 s
```

### Test status

```bash
.venv/bin/python -m pytest -q \
  tests/test_pipeline_geo.py \
  tests/test_pipeline_reference.py \
  tests/test_pipeline_load.py \
  tests/test_pipeline_pair.py \
  tests/test_pipeline_feasibility.py \
  tests/test_pipeline_context.py \
  tests/test_pipeline_nulls.py \
  tests/test_pipeline_corroborate.py \
  tests/test_pipeline_export.py \
  tests/test_pull_queue_events.py
```

Result: **36 passed in 27.66s**.

The pre-existing ingestion-package tests also passed separately: **11 passed in 0.77s**
(`test_contract`, `test_gfw`, `test_gfw_pull`, `test_noaa`).

## Reviewable source set

These new/untracked files are the primary code review set:

```text
pipeline/reference.py
pipeline/load.py
pipeline/pair_t0.py
pipeline/feasibility.py
pipeline/context.py
pipeline/nulls.py
pipeline/corroborate.py
pipeline/export.py                  # unit-tested only; full run intentionally deferred
tests/test_pipeline_reference.py
tests/test_pipeline_load.py
tests/test_pipeline_pair.py
tests/test_pipeline_feasibility.py
tests/test_pipeline_context.py
tests/test_pipeline_nulls.py
tests/test_pipeline_corroborate.py
tests/test_pipeline_export.py
data/reference/README.md
data/reference/class_speeds.json
data/reference/eu_iuu_cards.csv
data/reference/psma_parties.csv
data/reference/rfmo_names.json
scripts/pull_queue_events.py
tests/test_pull_queue_events.py
```

Optional static-review fixtures (not wired into the React source):

```text
code/frontend/public/data/risk-events.json
code/frontend/public/data/methods.json
code/frontend/public/data/narratives.json
```

`pipeline/export.py` is present and its fixture-level contract test passes, but it must **not** be claimed as a
complete export: `pipeline/features.py` and `pipeline/score.py` were intentionally not completed, so there is no
`features.parquet`, `scores.parquet`, all-record export, track directory, or real `methods.json` materialization.

## Intentionally deferred work

| Deferred item | Reason for stopping here |
|---|---|
| S6 `features.py` and `score.py` | next incremental reviewable unit; needed before real final export |
| S8 full `export.run()` | blocked by intentional absence of S6 outputs; do not overwrite P0 fixture yet |
| S1′ GFW enrichment | requires complete 2017–2019 Bronze manifest; not currently validated/present |
| S9 narration/verifier | API key/network-dependent and not needed for a sync checkpoint |
| React/static-provider/map integration | separate frontend work; current UI still uses mocks |
| Presentation alignment/build | separate presentation work; deck does not yet match fishing-pair data |
| Any merge/cherry-pick | explicitly deferred pending branch review / human decision |

## Important known issue: S4 plan vs. data conflict

The context implementation follows the written S4 definition, but two handoff acceptance figures conflict with it:

- Unioning off- and on-endpoint neighbor events (with both pair events excluded) gives local-density median/p90/zero
  **7 / 35 / 16**. The handoff asserts **3 / 25 / 37**, which exactly matches shutoff-only counting instead.
- The written strict twin predicate gives **183** twins, not asserted 181. The two extra valid matches are
  `t0-fcb811bbca42` and `t0-15e5ad8fc1ce`, each with `.025m` length difference and equal tonnage.

Do not alter code merely to force those stale values. Decide whether the product intends union or shutoff-only density,
then update the specification/methods claim and any affected downstream scoring deliberately.

## Generated artifacts: do not sync blindly

The following are derived/rerunnable and should generally **not** be copied/merged by hand:

```text
data/derived/gap_events.parquet
data/derived/candidates_t0.parquet
data/derived/feasibility.parquet
data/derived/local_context.parquet
data/derived/components.parquet
data/derived/null_results.json
data/derived/p_cell.parquet
data/derived/corroboration.parquet
data/derived/loose_feasibility.json
data/derived/pair_grid_counts.json
data/derived/queue_mmsis.txt
data/derived/candidate_windows_probe.json
```

`data/derived/exclusions.json` is a tracked modified file; it adds run provenance and should receive normal review.

## Branch-sync guidance

- **Do not** wholesale merge `origin/main`, `origin/andrew-dev`, or `origin/will-dev` into this dirty worktree.
- Local `main` and local `andrew-dev` are already merged and stale.
- Remote branches contain a separate presence-replay product plus millions of lines of raw data artifacts.
- Read `data/derived/branch_audit_handoff.md` before any branch operation.
- There is no commit for this checkpoint by design. A human should review the explicit source set above, decide which
  generated fixtures belong in version control, then create a focused commit from a clean/intentional staging set.

## Safe handoff commands

```bash
# Confirm exact current state
git branch --show-current
git status --short
git diff --check

# Review untracked sources explicitly (Git diff alone will not display them)
git diff --no-index -- /dev/null pipeline/load.py
git diff --no-index -- /dev/null pipeline/pair_t0.py
git diff --no-index -- /dev/null pipeline/feasibility.py
git diff --no-index -- /dev/null pipeline/context.py
git diff --no-index -- /dev/null pipeline/nulls.py

# Reproduce the checkpoint validation
.venv/bin/python -m pytest -q tests/test_pipeline_*.py tests/test_pull_queue_events.py
.venv/bin/python -m pipeline.run --stage reference --stage load --stage pair --stage feasibility --stage context --stage corroborate
.venv/bin/python -m pipeline.run --stage null --draws 20
```

## Related documents

- `data/derived/project_status_handoff.md` — whole-project status, including frontend, presentation, data and packaging.
- `data/derived/branch_audit_handoff.md` — branch topology and remote work audit.
- `data/derived/orchestrator_log.md` — chronological orchestration/task record.
