> **Archived 2026-09-05.** Historical planning/handoff document for wake.ai. Superseded by [docs/candidate-pipeline.md](../../candidate-pipeline.md), [docs/status.md](../../status.md) and [docs/data.md](../../data.md). Status claims, branch advice and any schedules in this file are stale and must not be acted on.

# GapPair backend — handoff prompts (terra vs Claude)

Written Sat 2026-09-05 16:55 EDT, revised 17:15 EDT after pulling Andrew's 16:45–17:05 commits and `main`. Foundation already in the repo on `Tanner-dev`: `pipeline/config.py`, `pipeline/geo.py`, `pipeline/run.py`, `tests/test_pipeline_geo.py` (5 tests green; 16 green repo-wide). Everything below builds on it.

State at 17:15: the 2017–2019 GAP bronze is **still absent** (Andrew's loop is on 2022 and 2026, and a daily presence backfill for the Russian EEZ), so T8 stays blocked and T9 was added so the identity and behaviour pulls need only one command from Andrew. `data/` is now about 2 GB in the working tree; nothing below reads it except T8.

> **If you are an agent reading this file: read §0, then execute. Do not ask for further instructions unless §0.7 says to stop.**

## 0. Orchestrator instructions (read first, then execute)

### 0.1 Orchestration

If you are the orchestrator for the GapPair backend build: You do not implement stages yourself. You (1) run the preflight, (2) dispatch  **implementer** subagents per task, (3) dispatch  **red-team reviewer** subagents per delivered task, (4) route fixes back, (5) integrate, (6) report to the human. Everything a subagent needs is in this file plus `plan/backend-implementation-plan.md`; do not invent requirements, and do not relax an acceptance number to make a task pass.

If your harness cannot run subagents, do each task yourself in the same order, and still run the red-team checklist as a separate pass with a fresh context before declaring a task done.

### 0.2 Preflight (5 minutes, do it once)

```
git branch --show-current          # must print Tanner-dev
.venv/bin/python -c "import pandas, numpy, pyarrow; print(pandas.__version__)"           # 3.0.x
.venv/bin/python -m pytest -q tests/test_pipeline_geo.py                                  # 5 passed
ls pipeline/config.py pipeline/geo.py pipeline/run.py data/raw/disabling_events.csv       # all present
wc -l data/raw/disabling_events.csv                                                       # 55369 (header + 55,368)
git status --short | grep -v '^??' | wc -l                                                # 0 tracked changes
```

If any line fails, stop and report (§0.7). Then create `data/derived/orchestrator_log.md` with the start time and the preflight output. Append to that log after every task; it is the audit trail the human reads.

Dependencies you may find missing; each is handled by skipping, not by waiting:
- 2017–2019 GAP bronze (`data/bronze/gfw_gaps/retrieval_id=*/window_start=2017-*` … `2019-*` with `pull_manifest.json` `complete: true`) → T8 runs only if present.
- `ANTHROPIC_API_KEY` → C2 is not yours; never attempt S9.
- `GFW_API_TOKEN` → never needed; T9 only writes a script, it does not run it.

### 0.3 Dependency graph and waves

```
Wave 1:  T1  ∥  T2  ∥  T9          (disjoint files; T9 writes a script, it needs nothing)
Wave 2:  T3  ∥  T4  ∥  T5          (each reads T1's parquet, writes only its own module/parquet/test)
Wave 3:  T6                        (reads T2–T5 outputs)
Wave 4:  T7                        (reads T6; overwrites the T2 fixture in risk-events.json and methods.json)
Cond.:   T8                        (only if 2017–2019 bronze exists; else log "skipped: bronze absent")
```

A wave starts only when every task of the previous wave has a PASS from its reviewer (§0.5). Inside a wave, run tasks in parallel if your harness supports isolated subagents; otherwise run them sequentially in the listed order. Time targets: Wave 1 done by 18:30 EDT, Wave 2 by 19:45, Wave 4 by 20:30 (the first real file to the frontend).

### 0.4 Dispatching an implementer

Prompt = the COMMON CONTEXT block (verbatim) + the task block (verbatim) + this footer:

```
ORCHESTRATION FOOTER
- You own only these paths: <list the module(s), test file(s) and data/derived or data/reference or
  code/frontend/public/data outputs named in your task>. Touch nothing else. Never edit pipeline/config.py,
  pipeline/geo.py or pipeline/run.py; if you believe one of them has a bug, describe it in your report and stop.
- Do not run stages other than your own (other agents may be writing their outputs right now).
- Read only plan §3, the §4 subsection for your stage, §6 if your task names it, and Appendix C. Do not read
  data/bronze/ unless you are T8.
- Finish with the DELIVERABLE report from the COMMON CONTEXT. Put the acceptance table first.
```

Give the implementer one attempt plus at most two fix rounds (§0.5). Keep the same subagent context for fix rounds when your harness allows it.

### 0.5 Red-team review of every delivered task

Spawn a **fresh** reviewer subagent (new context, it must not see the implementer's reasoning) with:

```
You are red-teaming a delivered pipeline stage. Repo /Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026, branch Tanner-dev,
interpreter .venv/bin/python. The task spec is <paste the task block>. The implementer's report is <paste it>.
Do not trust the report; verify.
1. Run `.venv/bin/python -m pytest -q tests/test_pipeline_*.py` and `.venv/bin/python -m pipeline.run --stage <stage>`;
   record runtime.
2. Recompute at least three acceptance numbers from scratch in a throwaway script (e.g. count rows of the parquet,
   filter the showcase pair by config.SHOWCASE and print its row, recount a histogram). Compare with the spec
   tolerances; anything outside is a FAIL.
3. Rule check: `git status --short` and `git diff --stat` show only the task's allowed paths; `grep -rn shapely
   pipeline/` is empty; `git diff pipeline/config.py pipeline/geo.py pipeline/run.py` is empty.
4. Spec-drift check, stage specific (see checklist below): units, pandas 3 timestamps, dateline, nulls, seeds.
5. Adversarial probes: write 3–5 small inputs designed to break the code (empty frame, one row, a dateline pair,
   duplicate MMSIs, NaN in an optional column) and run the stage's public functions on them. A crash on a
   plausible input is a FAIL; a crash on an impossible input is a note.
Report: verdict PASS or FAIL; a table of numbers observed vs expected; a numbered fix list for FAIL, each item
with file, line, what is wrong, and the minimal change. Do not fix code yourself.
```

Stage checklists for step 4:
- **T1** — `t0.dtype == "datetime64[us, UTC]"`; MMSI kept as 9-char text; `pair_events` never pairs equal MMSIs; every pair's intervals overlap; side A really is the earlier shutoff; `make_pair_id(a,b) == make_pair_id(b,a)`; brute force rerun with a different seed also matches.
- **T2** — `flag_card` time validity at the interval edges; missing flag → `"unknown"`; fixture: every `coordinates` is `[lon, lat]` (lon of the showcase ≈ 162, lat ≈ 42.7), every evidence claim's numbers appear in `features`, ring polygons close (first vertex == last), no NaN, `json.load` succeeds on all three files.
- **T3** — showcase p* within 0.05° of (161.958, 42.752); required speed uses the max over the two vessels; `reachable_ring` returns `None` when `a ≤ c`; a synthetic ±180° pair gives `dateline=True` and no ring; `tau_h` ≤ min gap duration for every pair.
- **T4** — own two events excluded from every neighbour count; `local_same_flag_share` is NA when unique vessels < 3; component sizes sum to the number of distinct events in operating pairs; twins are never cross-flag.
- **T5** — the permutation preserves, per cell, the multiset of durations and the event count; `lift` printed to 2 dp is not 1.00; `p_cell` min is `1/(draws+1)`; rerunning with the same seed reproduces `null_results.json` byte for byte except timestamps.
- **T6** — every term NA or in [0, 1]; a NA term contributes 0 and appears in `explanations`; no `identity-twin`/`sequential` pair labelled `investigate`; label rule order respected (build a row that matches rules 2 and 6 simultaneously and confirm rule 2 wins).
- **T7** — every record passes `validate_record`; the showcase `timeline[]` lat/lon strings agree with the `track` observed points (order swapped correctly); embedded `track` equals `tracks/<id>.geojson`; file sizes within §7; `attribution` on every record; sort order is tier, then priority desc, then id.
- **T9** — no network in tests; token never logged (grep the script for `print(` near `token`); pagination stops on `nextOffset: null`; `--resume` idempotent.

Routing: PASS → log it, mark the task done. FAIL → send the fix list to the implementer (fix round); re-review with a fresh reviewer. After two fix rounds still FAIL → stop that task and escalate (§0.7); continue other tasks that do not depend on it.

### 0.6 File-safety and concurrency rules (you enforce these)

- Only one agent may ever hold `pipeline/config.py`, `pipeline/geo.py`, `pipeline/run.py`: nobody. Bugs there come to you; fix them yourself only if the fix is a defect, never a value change, and rerun `tests/test_pipeline_geo.py` after.
- Parallel implementers must own disjoint paths (the task blocks guarantee this). If your harness offers git worktrees, give each Wave-2 agent its own and merge their files back yourself; `data/derived/` outputs are regenerated by rerunning the stage, so never merge parquet files by hand.
- Never `git commit`, `git push`, `git stash`, `git checkout -- <file>`, or `git clean`. The human commits.
- Never write outside `pipeline/`, `tests/test_pipeline_*.py`, `tests/test_pull_queue_events.py`, `scripts/pull_queue_events.py`, `data/derived/`, `data/reference/`, `code/frontend/public/data/`.
- Never install packages. If a task claims it needs one, that is a FAIL of the task, not a reason to install.

### 0.7 Stop and escalate to the human when

- a preflight line fails;
- a task fails review twice;
- a subagent reports that `config.py` or `geo.py` needs a value change to hit an acceptance number (the numbers were verified with these values; the bug is elsewhere);
- an acceptance number disagrees and the reviewer's independent recomputation confirms the code rather than the spec (report both numbers, do not edit the plan);
- anything would require the GFW token, an Anthropic key, network access, or a package install.

Escalation = write the situation into `orchestrator_log.md`, finish the tasks that do not depend on it, then end with the final report (§0.8). Do not idle waiting for a reply.

### 0.8 Final report (your last message, and `data/derived/handoff_report.md`)

1. One line per task: PASS / FAIL / SKIPPED, rounds used, runtime.
2. The acceptance table for every PASSed task (observed vs expected).
3. `git status --short` output and the list of files created.
4. Open items for the human: escalations, T8/C2 skips, and any place the reviewer flagged a spec ambiguity.
5. Exact commands to reproduce end to end: `.venv/bin/python -m pipeline.run --all --draws 20` then `--stage null --draws 200` then `--stage score --stage export`, and the test command.

The message must stand alone for a reader who did not watch the run.

---

## Who does what

| # | Task | Do it with | Effort | Why |
|---|---|---|---|---|
| T1 | S1 `load.py` + S3 `pair_t0.py` | **terra** | medium–high | Fully specified, every acceptance number verified; objective pass/fail. |
| T2 | S0 reference tables + P0 frontend fixture | **terra** | low–medium | Copy work from the plan's appendices and §6.1. |
| T3 | S2 `feasibility.py` | **terra** | high | Planar geometry, dateline, argmax refinement; still fully specified with checks. |
| T4 | S4 `context.py` | **terra** | medium–high | Union-find, neighbour sets; acceptance counts known. |
| T5 | S5 `nulls.py` | **terra** | medium–high | Permutation loop; acceptance lift known; must be fast. |
| T6 | S6 `features.py` + `score.py` | **terra** | medium | Arithmetic + ordered label rules; worked example known. |
| T7 | S8 `export.py` + `corroborate.py` stub + `methods.json` + `summary.md` | **terra** | medium–high | Contract is written out in §6; validator catches drift. |
| T8 | S1′ `enrich_api.py` | **terra** | medium | Blocked until Andrew commits the 2017–2019 bronze. Prompt ready. |
| T9 | `scripts/pull_queue_events.py` (identity + ENCOUNTER / LOITERING / PORT_VISIT for the 212 queue MMSIs) | **terra** | medium–high | Standalone httpx script Andrew runs once with his token; unblocks D3–D5 and D7 without waiting on his lane. Needs T1's MMSI list to run, not to write. |
| C1 | Acceptance gate after T1, after T3–T5, after T7 | **Claude Sonnet 5**, low effort | — | Run tests, diff numbers against §4, spot-check the showcase record. Escalate to Fable only on disagreement. |
| C2 | S9 `narrate.py` + `verify.py` | **Claude Sonnet 5** with the `claude-api` skill, medium effort | — | Anthropic structured-output call must match the live API reference; the verifier design is the agent-trust story. Needs `ANTHROPIC_API_KEY`. |
| C3 | Final integration, `summary.md` numbers, README run notes | **Claude Fable** (this session), low effort | — | Holds the plan and merge context; small token cost. |
| F1 | Frontend §6.4 changes | frontend owner, or **terra** medium if they want an agent | — | React/TS, well specified in §6.4. |

Run order and parallelism (formal version in §0.3): **T1 ∥ T2 ∥ T9** → **T3 ∥ T4 ∥ T5** → **T6** → **T7** → T8 only if the 2017–2019 bronze exists. Under a terra orchestrator the red-team reviewer in §0.5 replaces C1; run C1 on Claude only as a second opinion. C2 stays on Claude when a key exists. If terra sessions share one working tree, never let two sessions edit `pipeline/run.py` or `config.py`; none of the prompts below needs to.

Send T1's `data/derived/queue_mmsis.txt` to Andrew as soon as it exists; his identity and event pulls wait on it.

---

## COMMON CONTEXT — paste this block at the top of every terra prompt

```
You are working in the git repo at /Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026 on branch Tanner-dev.
Project: GapPair, a hackathon backend that turns a corpus of 55,368 AIS-disabling events (fishing vessels, 2017-2019)
into a ranked, explainable queue of "paired-dark" candidates: two vessels whose AIS gaps start together and end together.

THE SPEC IS plan/backend-implementation-plan.md. Read §3 (layout, config), §4 (your stage; also the "Conventions" paragraph
at the top of §4), §6 (output contract) and Appendix C (acceptance tests) before writing code. plan/build-plan.md is design
background; read it only if §4 refers to it.

ENVIRONMENT
- Python: use .venv/bin/python (Python 3.14.2, pandas 3.0.5, numpy 2.5, pyarrow 25, scipy 1.18). No other interpreter.
- Tests: .venv/bin/python -m pytest -q tests/test_pipeline_*.py   (the "python -m" form puts the repo root on sys.path).
- Run a stage: .venv/bin/python -m pipeline.run --stage <name>   (see pipeline/run.py for stage names; each stage module
  must expose run(**kwargs) and read/write files under data/derived/ via pipeline.config paths).
- Already present, do not modify values: pipeline/config.py (all thresholds, speeds, weights, paths, SEED, SHOWCASE),
  pipeline/geo.py (haversine_km, cell_id, local_frame, to_local, from_local, normalise_lon, crosses_dateline),
  pipeline/run.py, tests/test_pipeline_geo.py.
- Corpus: data/raw/disabling_events.csv, 55,368 rows. Columns: gap_id, mmsi, vessel_class, flag, vessel_length_m,
  vessel_tonnage_gt, gap_start_timestamp, gap_start_lat, gap_start_lon, gap_start_distance_from_shore_m,
  gap_end_timestamp, gap_end_lat, gap_end_lon, gap_end_distance_from_shore_m, gap_hours.

HARD RULES
- pandas 3 parses timestamps to datetime64[us, UTC]. Durations: (t1 - t0) / pd.Timedelta(hours=1). Never divide an
  int64 view of a datetime by a constant.
- Units: km, knots, hours. km = kn * h * 1.852. Haversine with R = 6371 km (use pipeline.geo).
- Pure numpy/pandas. No shapely, no geopandas, no scikit-learn, no new dependencies.
- Longitudes normalised to [-180, 180] on every output. Dateline pairs must not crash; follow §4.
- No log(0): every probability carries a pseudo-count. Nulls are pandas NA / JSON null, never 0 or "n/a".
- Seed every random draw from pipeline.config.SEED. Round only at export (§6.1 rounding rules).
- Vectorise; the whole corpus must process in seconds, not minutes (timings are given per stage in §4).

DO NOT
- modify src/dark_rendezvous/, plan/, pyproject.toml, requirements.txt, .gitignore, code/frontend/src/, scripts/ (T9 adds
  one new file there), or anything under data/bronze/, data/silver/ or data/logs/;
- read the ~2 GB data/bronze/ tree (only the enrich task does);
- change any value in pipeline/config.py (adding a new constant the spec names is fine);
- commit, push, or create branches.

DELIVERABLE
- The module(s), the test file(s), and at the end a report with: files created; a table of acceptance numbers observed
  vs expected (from §4 / Appendix C); runtime of run(); any deviation from the spec and why. If an acceptance number
  does not match, do not "fix" the number by loosening the rule; report the discrepancy with your best diagnosis.
```

---

## T1 — S1 `load.py` and S3 `pair_t0.py`  (terra, medium–high)

```
TASK: implement stages S1 and S3 from plan/backend-implementation-plan.md §4 ("S1 load.py" and "S3 pair_t0.py").

Create pipeline/load.py:
- load_gap_events(csv_path=config.RAW_CSV) -> DataFrame with exactly the columns and rules in the §4 S1 table
  (gap_id, mmsi as zero-padded 9-char text, mmsi_int, mid, mmsi_valid, vessel_class, flag with blank -> NA,
  length_m, tonnage_gt, length_estimated=True, tonnage_estimated=True, t0, t1 as datetime64[us, UTC],
  lat0, lon0, lat1, lon1, shore_off_km, shore_on_km (metres / 1000), gap_hours_source, gap_hours_exact,
  cell via geo.cell_id(lat0, lon0), cell_month f"{cell}-{t0:%Y-%m}", dateline = abs(lon0 - lon1) > 180,
  v_kn via config.class_speed_kn, v_kmh = v_kn * 1.852, n_gaps_vessel).
- write_gap_events(df, out=config.DERIVED / "gap_events.parquet"); write_exclusions(df, out=config.DERIVED / "exclusions.json")
  reproducing the keys in the existing data/derived/exclusions.json plus created_at, source SHA-256, row count.
- run(): load -> write both files, print the acceptance numbers.
Acceptance (all verified on this corpus): 55,368 rows; t0.dtype == "datetime64[us, UTC]"; 54,553 mmsi_valid; 815 invalid;
702 blank flags; 484 dateline; gap_hours_exact within 0.017 h of gap_hours_source on every row; 0 duplicate gap_id;
0 negative-or-zero durations.

Create pipeline/pair_t0.py with the functions and signatures in §4 S3:
- pair_events(ev, *, start_km, start_h, end_km=None, end_h=None, both_ends=True) -> DataFrame of (i, j) positions in
  ev sorted by t0, using the blocking described there (sort by t0; hi = searchsorted(t0, t0 + start_h); vectorised
  haversine on shutoffs; different MMSI; interval overlap min(t1) - max(t0) > 0; then reappearance distance and
  |t1_i - t1_j| when both_ends). Only mmsi_valid rows take part. Keep the Python-outer/numpy-inner loop; do not optimise past ~1 s.
- build_candidates(ev) -> DataFrame with every column listed in §4 S3 ("Canonical ordering" paragraph): side A is
  the earlier shutoff (tie -> smaller gap_id); pair_id = "t0-" + sha1("|".join(sorted([gap_id_a, gap_id_b]))).hexdigest()[:12].
- ladder_counts(ev) -> dict over config.LADDER names plus "loose" (config.LOOSE, both ends).
- brute_force_check(ev, n_sample=1500, seed=config.SEED): O(n^2) recomputation on a random subsample; raise AssertionError on mismatch.
- make_pair_id(a, b) symmetric.
- run(): reads gap_events.parquet, writes candidates_t0.parquet, pair_grid_counts.json (ladder counts, loose count,
  per-cell-month observed operating-pair counts keyed like "6826-2017-07"), and data/derived/queue_mmsis.txt (the
  distinct MMSIs in the 434 pairs, one per line; expected 212). Runs brute_force_check.
Acceptance (verified): 434 operating pairs; 26 cross_flag; ladder = 101,901 / 1,230 / 5,630 / 434 / 103 / 3 in config.LADDER
order; loose = 18,775; the showcase pair (config.SHOWCASE: 412331147 x 416004105 starting 2017-07-01) present with
start_km 6.60, start_delta_min 0.083, end_km 8.99, end_delta_min 0.717, overlap_h 41.76, duration_ratio 0.9997,
cell_month "6826-2017-07"; pairing < 1 s; brute-force check passes.

Tests: tests/test_pipeline_load.py and tests/test_pipeline_pair.py covering Appendix C items 2 and 3 (row counts, dtype,
54,553 valid, 484 dateline; 434 pairs, showcase numbers within the tolerances above, ladder counts, brute-force
subsample equality, make_pair_id symmetric). Tests may read the real CSV (it loads in ~1 s).
```

## T2 — S0 reference tables and the P0 frontend fixture  (terra, low–medium)

```
TASK: (a) implement stage S0 and its static tables; (b) write the P0 fixture files the frontend builds against.
Spec: plan/backend-implementation-plan.md §4 "S0 reference.py", Appendix A, Appendix B, §6.1, §6.2, §6.3, §6.4.

(a) Create data/reference/ with:
- eu_iuu_cards.csv (columns flag_iso3, colour, start_date, end_date, source_url, confidence) holding every Appendix A row;
  end_date empty when null; source_url empty (Andrew fills it).
- rfmo_names.json: the Appendix B code -> name map.
- class_speeds.json: pipeline.config.V_KN written out.
- psma_parties.csv: header only (flag_iso3, party_since) plus a README line in data/reference/README.md saying it is
  optional and unfilled.
Create pipeline/reference.py with flag_card(flag, at) -> "none"|"yellow"|"red"|"unknown" (time-valid; missing flag ->
"unknown", never "none"; corpus flags with no card in 2017-2019 -> "none"), psma_party(flag, at) -> bool|None (None while
the table is empty), rfmo_name(code), class_speed_kn(vessel_class), and run() that loads and validates the tables
(dates parse, colours in {yellow, red}, no overlapping intervals per flag). Test: tests/test_pipeline_reference.py
(TWN on 2017-07-01 -> "yellow"; TWN on 2019-07-01 -> "none"; None -> "unknown"; KHM 2018 -> "red").

(b) Fixture. Create code/frontend/public/data/ with:
- risk-events.json: a JSON array of three records. Record 1 is the §6.1 showcase record copied exactly, except that
  "track" must be a real GeoJSON FeatureCollection per §6.2: four observed Point features from the timeline coordinates
  (note the timeline prints "lat N lon E"; GeoJSON is [lon, lat]), two dashed LineString projections p0 -> meeting point
  -> p1 per vessel, the meeting Point, and two 64-vertex ellipse Polygon rings (foci at each vessel's own endpoints,
  semi-major axis a = v_kmh * (gap_hours - 1) / 2 with v_kmh = 12 * 1.852, computed in a local planar frame with
  111.32*cos(lat) km/deg lon and 110.57 km/deg lat, then converted back). Records 2 and 3 are hand-built variants with
  internally consistent numbers: a coordinated-fleet pair (two CHN squid jiggers with sequential MMSIs 412xxxxx0/1, label
  "coordinated-fleet-pattern", riskLevel "review", evidenceTier "coordinated_fleet_activity", scores.flt 1.0,
  features.sequentialMmsi true, componentClass "fleet_cluster", componentSize 4) and a coverage-artifact pair (label
  "likely-coverage-or-cluster-artifact", riskLevel "watch", evidenceTier "coincidence_or_artifact", localDarkCount 30,
  localUniqueVessels 22, scores.den 0.74, componentClass "regional_blackout"). Every evidence[] claim and explanations[]
  sentence must match that record's own numbers. All coordinates [lon, lat]; timestamps ISO-8601 UTC; nulls as null.
- narratives.json: keyed by the showcase id, in the §4 S9 shape (segments with kind/text/claimKey/value/unit/estimated/
  nullName/status, recommendation, caveat, verifierSummary, and an "adversarial" block with two contradicted segments).
  Every claimKey must be a real dotted path into the showcase record (e.g. "features.startDeltaMin").
- methods.json: every key listed in §6.3 filled from §3 config values and §10 numbers (ladder table, null definition
  with draws 200, weights, label rules as prose, caveats, sources, attribution, generatedAt).
Validate: all three files json.load, no NaN, coordinates in range, attribution present on every record.
Do not edit anything under code/frontend/src/.
```

## T3 — S2 `feasibility.py`  (terra, high)

```
TASK: implement stage S2 from plan/backend-implementation-plan.md §4 "S2 feasibility.py" (dataclasses Endpoints and
JointFeasibility, joint_feasibility, reachable_ring, dwell_at) exactly as specified there, including the six-step
algorithm, the ellipse construction, and the dateline rule (ring -> None and dateline = True when crosses_dateline).
Use pipeline.geo for frames and distances. Inputs: data/derived/gap_events.parquet and candidates_t0.parquet from S1/S3.
run(): (1) joint feasibility for all operating candidates -> data/derived/feasibility.parquet keyed by pair_id with
tau_h, lon_star, lat_star, required_speed_kn, kin_plausibility, feasible, ring_a, ring_b (JSON-encoded [[lon, lat], ...]
lists or null), dateline; (2) the loose-rule methods number: rebuild the loose pairs with pipeline.pair_t0.pair_events
and config.LOOSE, run joint_feasibility over them (no rings), and write data/derived/loose_feasibility.json
{"loose": N, "feasible_at_tau_min": M}.
Acceptance (verified): showcase tau_h 38.6 (+/- 0.3), required_speed_kn 0.92 (+/- 0.05), p* within 0.05 deg of
(161.958, 42.752); over the 434 pairs tau min 0.4 h, median 14.0 h, required-speed median 0.65 kn, kin_plausibility
median 0.95; loose 18,775 with 18,735 feasible; joint feasibility over the loose set in well under 5 s.
Tests: tests/test_pipeline_feasibility.py per Appendix C item 4 (two identical gaps -> tau == T; a synthetic pair that
needs 40 kn -> infeasible; a synthetic pair across +/-180 -> dateline True and no ring; showcase numbers above).
```

## T4 — S4 `context.py`  (terra, medium–high)

```
TASK: implement stage S4 from plan/backend-implementation-plan.md §4 "S4 context.py": local_context, components,
identity_flags, vessel_history, with every definition in that section (neighbour sets at shutoff and reappearance
within config.LOCAL_KM and LOCAL_H, own two events excluded; neighbours[] up to config.NEIGHBOURS_MAX nearest at shutoff
with mmsi, flag, deltaMin signed relative to A, distanceKm; local_same_flag_share null when local_unique_vessels <
config.SAME_FLAG_MIN_VESSELS; union-find components over operating pairs with component_class rules; sequential_mmsi
(same MID and |delta| <= config.SEQ_MMSI_MAX_DELTA); identity_twin (config.TWIN_LEN_M, TWIN_TON_GT); identity_status;
gap_unusualness, repeat_rate, prior_pair_count).
Inputs: gap_events.parquet, candidates_t0.parquet. run() writes data/derived/local_context.parquet (per pair_id,
neighbours as a JSON string column) and components.parquet (pair_id, component_id, component_size, component_class).
Use a time-sorted searchsorted window then vectorised haversine for the neighbour search; runtime about 1 s.
Acceptance (verified): 295 components of size > 1 with size histogram {2: 237, 3: 44, 4: 9, 5: 3, 6: 1, 14: 1};
237 pairs bilateral; 55 pairs in components of size >= 5; local_dark_count median 3, p90 25, 37 pairs with zero;
181 identity twins; 173 sequential; showcase: component size 2, exactly one neighbour 412329634 (CHN, +1.4 min,
9.7 km at shutoff), gap_unusualness_a 0.54 and _b 0.70, both vessels in exactly one pair.
Tests: tests/test_pipeline_context.py per Appendix C item 5.
```

## T5 — S5 `nulls.py`  (terra, medium–high)

```
TASK: implement stage S5 from plan/backend-implementation-plan.md §4 "S5 nulls.py": permute_within_cell (shuffle t0
among events in the same 5-degree cell with rng, keep durations and positions, t1 = t0 + duration; only mmsi_valid rows),
run_null(ev, cands, draws, ladder_draws, seed) that reruns pipeline.pair_t0.pair_events with config.OPERATING per draw
and records the total and the per-cell-month count (cell-month of the A event, same key format as
pair_grid_counts.json), plus ladder rungs and the loose rule with ladder_draws draws; p_cell(cands, null) =
(1 + k) / (1 + N). Write data/derived/null_results.json in exactly the shape shown in §4 S5. Assertions: null_mean > 0;
abs(lift - 1.0) > 0.01; every candidate gets a p_cell in [1/(N+1), 1].
run(draws=config.NULL_DRAWS): accepts --draws from pipeline.run; also write data/derived/p_cell.parquet (pair_id, p_cell).
Acceptance (verified with 10-50 draws): null mean about 12, lift about 36x; showcase cell-month "6826-2017-07" observed 1
with zero null hits in 50 draws -> p_cell = 1/51 at 50 draws; about 1.1 s per draw (a 20-draw run must finish in < 40 s
including the ladder). Print a one-line progress every 10 draws.
Tests: tests/test_pipeline_nulls.py per Appendix C item 6 (5 draws in < 10 s; lift != 1.00; p_cell bounds; the
permutation preserves per-cell multiset of durations and the per-cell count of events).
```

## T6 — S6 `features.py` and `score.py`  (terra, medium)

```
TASK: implement stage S6 from plan/backend-implementation-plan.md §4 "S6 features.py + score.py".
features.py: run() joins candidates_t0.parquet, feasibility.parquet, local_context.parquet, components.parquet,
p_cell.parquet, the S0 reference tables (pipeline.reference) and, only if present, data/reference/gfw_gap_enrichment.parquet
and gfw_events_queue.parquet, into data/derived/features.parquet with every column in the §4 S6 family table. Missing
sources leave their columns NA (behaviour family, rfmo_authorized, iuu_listed, port_risk, zone -> "unknown" when no
enrichment, viirs_state "no_coverage"). flag_card_a/b via reference.flag_card at t0_a.
score.py: the term formulas, raw, priority, riskScore, the ordered label rules (first match wins), riskLevel mapping and
evidence tier exactly as written in §4 S6; null terms contribute 0 to raw and stay null in the output; one explanations[]
sentence per null term naming the missing input (use the wording in §6.1 "explanations"). Write
data/derived/scores.parquet (pair_id, the eight terms, raw, priority, risk_score, label, risk_level, evidence_tier,
explanations as JSON string). Print the label histogram.
Acceptance: all priorities in [0, 1]; every term in [0, 1] or NA; no identity-twin or sequential pair labelled
"investigate"; showcase (with the S5 p_cell from the run you have): S_geom = clip(-log10(p_cell), 0, 2)/2, S_ctx 0.6,
S_cor 0, S_den 0.15, S_flt 0, S_hab 0.38 (+/- 0.02), and with p_cell = 1/201: raw 0.329, priority 0.54, riskScore 54,
label "investigate", tier "bilateral_rendezvous_plausible" (+/- 0.02 on raw and priority).
Tests: tests/test_pipeline_score.py per Appendix C item 7, using a hand-built feature row for the showcase and one
twin pair.
```

## T7 — S8 `export.py`, S7 stub, `methods.json`, `summary.md`  (terra, medium–high)

```
TASK: implement stage S8 from plan/backend-implementation-plan.md §4 "S8 export.py" against the contract in §6.1, §6.2,
§6.3, and a default-only S7.
corroborate.py: run() writes data/derived/corroboration.parquet with viirs_state "no_coverage",
viirs_uncorrelated_count 0, viirs_min_km_to_p_star null, viirs_detections "[]", presence_source "corpus_endpoints" for
every pair_id; leave a documented hook for the real VIIRS join described in §4 S7 (function signature only).
export.py: build_record, build_track, write_outputs, write_methods, write_evidence_ledger, write_summary, and
validate_record (about 40 lines: required keys, types, enums, coordinate ranges, [lon, lat] order, ISO timestamps,
no NaN, attribution present). Field rules and rounding are in §6.1 ("Field rules" paragraph); track composition and the
dateline omission rule in §6.2; methods.json keys in §6.3; sort order and size budget in §4 S8 and §7. name uses MMSIs
unless a vessel_name column exists in features. location string per §6.1. Evidence ids and claim wording follow the
showcase example (sync-off, sync-on, null, card, density, geometry); omit "card" when neither flag is carded.
run(): writes code/frontend/public/data/risk-events.json (all 434 records, embedded track), tracks/<id>.geojson,
methods.json, data/derived/evidence_ledger.parquet, data/derived/summary.md (every number in §10, filled from the run).
Overwrite the P0 fixture in risk-events.json/methods.json but do NOT touch narratives.json.
Acceptance: json round-trip; 434 records; every record passes validate_record; showcase record's evidence[] and
timeline[] match §6.1 (numbers may differ only where the 200-draw null changes p_cell); risk-events.json <= 5 MB,
methods.json <= 50 KB, tracks/ <= 4 MB; no coordinate out of range; no NaN anywhere.
Tests: tests/test_pipeline_export.py per Appendix C item 8 (build one record from the showcase feature row and validate
it; validate_record rejects a NaN, a [lat, lon] swap, and a missing attribution).
```

## T8 — S1′ `enrich_api.py`  (terra, medium) — run only after 2017–2019 bronze is committed

```
TASK: implement stage S1' from plan/backend-implementation-plan.md §4 "S1' enrich_api.py", including every reading rule
and verified fact in that section (retrieval selection by window_start year and pull_manifest.json complete: true;
dedupe on event.id keeping the latest retrieval_id; pd.to_numeric on string-typed fields; high_seas = eez == [];
drop ACAP/IWC/IPHC; fishery RFMOs from config.FISHERY_RFMOS). build_enrichment(bronze_root=config.BRONZE_GAPS) ->
DataFrame with the columns listed there; run() writes data/reference/gfw_gap_enrichment.parquet and prints coverage:
events read, events matched to gap_events.parquet by gap_id, share of 2017-2019 corpus rows enriched. Stream the JSON
page by page (each response.json holds 500 events); never load the whole tree into memory at once. Skip retrievals
whose windows are outside 2017-2019 without opening their pages. Expected: Jan 2017 gives 1,194 matches of 1,195;
full 2017-2019 should match > 99 % of the 55,368 rows.
Test: tests/test_pipeline_enrich.py with a two-page synthetic bronze tree in tmp_path (one string-typed onPosition,
one event with eez [], ACAP+WCPFC rfmo) asserting the derived columns.
```

## T9 — `scripts/pull_queue_events.py`: identity and behaviour events for the queue vessels  (terra, medium–high)

```
TASK: write ONE standalone script, scripts/pull_queue_events.py, that Andrew runs on his Windows machine (Python 3.13,
pandas 2.x, httpx, pyarrow; write 3.11-compatible code, no 3.14-only syntax) with the only GFW API token. It must not
import dark_rendezvous. Spec context: plan/backend-implementation-plan.md §4 "S1'' Andrew's API pulls" and §1 rows D3-D5, D7.

Inputs: data/derived/queue_mmsis.txt (one 9-digit MMSI per line, about 212; produced by stage S3). Token: env
GFW_API_TOKEN, else the GFW_API_TOKEN= line of an untracked .env at the repo root; never print, log or write it.
Base URL https://gateway.api.globalfishingwatch.org/v3, header Authorization: Bearer <token>.

Step 1, identity: for each MMSI GET /vessels/search with query=<mmsi>, datasets[0]=public-global-vessel-identity:latest,
includes[0]=MATCH_CRITERIA, includes[1]=OWNERSHIP, includes[2]=AUTHORIZATIONS, limit=50. Save every raw response to
data/bronze/gfw_identity/retrieval_id=<UTC id>/mmsi=<mmsi>/response.json plus a manifest.json (request, sha256, row
count, retrieved_at). Parse to data/reference/vessel_identity.parquet: mmsi, gfw_vessel_id, name, imo, callsign, flag,
vessel_type, gear_type, length_m, tonnage_gt, built_year, owner, authorizations_json, first_transmission,
last_transmission, match_rank, dataset_version, retrieved_at. Choose the entry whose ssvid equals the MMSI and whose
transmission dates overlap 2017-2019; keep all candidates with match_rank so the choice is auditable.

Step 2, events: POST /events?offset=<k>&limit=500 with body {"datasets": [<one dataset>], "types": [<one type>],
"startDate": "2017-01-01", "endDate": "2019-12-31", "timeFilterMode": "OVERLAP", "vessels": [<up to 50 gfw ids>]}
for the pairs (public-global-encounters-events:latest, ENCOUNTER), (public-global-loitering-events:latest, LOITERING),
(public-global-port-visits-events:latest, PORT_VISIT). Verify these dataset names in the GFW v3 events docs and make them
constants at the top of the file. Follow nextOffset until null. Save every page to
data/bronze/gfw_events/retrieval_id=<id>/type=<TYPE>/batch=<n>/offset=<k>/response.json plus manifest.json.
Parse to data/reference/gfw_events_queue.parquet: event_type, event_id, gfw_vessel_id, mmsi, start, end (UTC), lat, lon,
partner_gfw_vessel_id, partner_mmsi, partner_type, median_distance_km, median_speed_kn, port_name, port_country,
regions_json, dataset_version, retrieved_at. Parse defensively: the bronze keeps everything, so a missing field becomes
NA, never a crash.

Behaviour: --dry-run makes exactly one identity call (MMSI 412331147) and one ENCOUNTER page for that vessel id and
prints the pretty-printed first entry of each so field paths can be corrected in minutes; --only identity|events;
--resume skips MMSIs and (type, batch) combinations that already have a manifest. Pause 0.2 s between calls; on 429 or
5xx retry up to 5 times with exponential backoff; on 401/403 stop with a clear message. Write
data/reference/gfw_queue_pull_manifest.json at the end: counts per type, MMSIs resolved / unresolved, retrieval ids,
and which datasets returned 4xx (so methods.json can say what landed). Expected runtime: about 2 minutes for identity,
a few minutes for events.

Tests: tests/test_pull_queue_events.py using httpx.MockTransport: pagination follows nextOffset; identity choice picks
the ssvid match overlapping 2017-2019; the parsers turn a synthetic ENCOUNTER, LOITERING and PORT_VISIT entry into the
parquet columns; --resume skips a batch whose manifest exists. No network in tests.
```

---

## Claude-side prompts

### C1 — acceptance gate (Sonnet 5, low effort; run after T1, after T3–T5, after T7)

```
In /Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026 on Tanner-dev: run `.venv/bin/python -m pytest -q tests/test_pipeline_*.py`
and `.venv/bin/python -m pipeline.run --stage <the stages just delivered>`. Compare every printed number with the
"Acceptance" lines for those stages in plan/backend-implementation-plan.md §4 and with Appendix C. Open
data/derived/candidates_t0.parquet (or the stage's output) and print the showcase row (config.SHOWCASE). Check the three
DO-NOT rules: no edits under src/dark_rendezvous/, plan/, pyproject.toml; no shapely import anywhere under pipeline/;
no value changed in pipeline/config.py (git diff). Report: pass/fail per acceptance number, any rule violation, and the
one-paragraph verdict "merge as is" or "send back with these fixes". Do not fix code yourself.
```

### C2 — S9 narration and verifier (Sonnet 5 + `claude-api` skill, medium effort; needs ANTHROPIC_API_KEY)

```
Implement plan/backend-implementation-plan.md §4 "S9 narrate.py + verify.py" exactly: SEGMENT_SCHEMA, flatten,
allowed_keys, narrate (claude-opus-5, output_config effort low + json_schema format, max_tokens 2000, no temperature),
verify with the TOLERANCES table and the four unverifiable rules, adversarial mode, and run(top=20) writing
code/frontend/public/data/narratives.json in the §4 S9 shape (top 20 by priority plus every "investigate" record;
adversarial for the showcase pair and two others). Load the claude-api skill first and confirm the structured-output
call shape against it before writing narrate.py. Tests: tests/test_pipeline_verify.py per Appendix C item 9, with no
network. Also add pipeline/serve.py (POST /narrate, about 40 lines, http.server is fine) with a /health route.
```

---

## 14. Product integration decided 18:25 EDT: Andrew's data → GapPair candidates → Will's presence viewer

The team's target is one product: candidates computed from Andrew's GFW pulls, replayed in Will's presence viewer. Measured on the pulls in the repo (`scripts` not needed, numbers from a probe run of `pipeline.pair_t0` on the bronze):

| Corpus | Valid-MMSI events | Operating pairs (fishing + carrier) | Both ends inside one EEZ | Has GFW vessel ids / names |
|---|---:|---:|---:|---|
| Andrew 2021 pull (`retrieval_id=20260905T200519Z`, complete) | 66,306 | **465** | 28 | yes / yes |
| Andrew Aug-2026 pull (`…T210748Z`, complete) | 6,770 | 13 | 4 | yes / yes |
| Russian EEZ (5690), Aug 2026, where the presence backfill is | 17 | 0 | 0 | — |
| CSV corpus 2017–2019 (the plan's) | 54,553 | 434 | unknown (no regions) | no / no |

Decision: **the demo corpus becomes Andrew's 2021 pull.** It carries the join key Will's viewer uses (`gfw:<vesselId>`), names, flags, EEZ/RFMO ids and shore/port distances, so S1′ enrichment disappears as a separate step. Presence is pulled **per candidate window**, not per region-month: the existing Russian-EEZ presence days stay in the catalog but no candidate lives there. The CSV corpus run stays as the validation story (its verified numbers and null lift go in `methods.json` as the reference run).

Pipeline impact: stages S2–S8 are corpus-agnostic given `gap_events.parquet`; only a second loader and a bridge export are new. The orchestrator finishes Waves 2–4 on the CSV corpus (that is where the acceptance numbers are), then reruns `--all` with `CORPUS=api2021` checking invariants only.

`data/derived/candidate_windows_probe.json` already lists the 28 in-EEZ 2021 pairs with UTC presence days so Andrew can start pulling before the scored list exists.

### T10 — `pipeline/load_api.py` and the corpus switch  (terra, medium; run now, in parallel with Wave 2)

```
TASK: add a second S1 loader that builds the exact gap_events.parquet schema (pipeline/load.py, §4 S1 column table) from
Andrew's GFW GAP bronze, and a corpus switch.
- pipeline/load_api.py: load_gap_events_api(retrieval_ids=("20260905T200519Z",)) reads every
  data/bronze/gfw_gaps/retrieval_id=<id>/window_start=*/window_end=*/offset=*/response.json page by page (500 events
  each; never load the tree at once). Only retrievals with pull_manifest.json complete: true. Mapping: gap_id <- event.id;
  mmsi <- vessel.ssvid (9-char text); vessel_class <- vessel.type (values fishing, carrier, cargo, other, gear, unknown,
  …; class speed via config.class_speed_kn, so fishing -> V_KN["unknown"] unless a finer geartype is known); flag <-
  vessel.flag; t0/t1 <- start/end; lat0/lon0 <- gap.offPosition; lat1/lon1 <- gap.onPosition (strings: pd.to_numeric);
  shore_off_km/shore_on_km <- distances.startDistanceFromShoreKm/endDistanceFromShoreKm; gap_hours_source <-
  gap.durationHours; length_m/tonnage_gt NA (estimated flags True). Extra columns kept: gfw_vessel_id, vessel_name,
  eez_ids (comma-joined MRGIDs), rfmo (comma-joined, ACAP/IWC/IPHC dropped), high_seas = eez_ids == "", port_off_km,
  port_on_km, positions_12h_before_sat, positions_per_day_sat. Drop duplicate gap_id (the Aug-2026 pull has 59 across
  pages; 2021 has 3), keep the first. mmsi_valid additionally requires all four coordinates present. Population filter
  for pairing: vessel_class in {"fishing", "carrier"}; write the rest with mmsi_valid = False and a
  quality_note column saying why.
- pipeline/config.py: add CORPUS = "csv2017" (default) | "api2021" and API_RETRIEVAL_IDS = ("20260905T200519Z",).
  pipeline/run.py stage "load" dispatches on config.CORPUS (an env var PIPELINE_CORPUS overrides). Everything downstream
  reads gap_events.parquet unchanged. Add DERIVED subfolders per corpus: data/derived/<corpus>/ so both runs coexist;
  export writes to code/frontend/public/data/<corpus>/… and a symlink-free copy of the api2021 run at
  code/frontend/public/data/ (the viewer reads that one).
Acceptance (from the probe): 2021 → 343,854 events after dedupe, 66,306 valid-MMSI, pairing population (fishing+carrier,
valid) ≈ 25,400, and pipeline.pair_t0.build_candidates on it gives 465 pairs, 102 cross-flag; runtime < 3 min for the
load, < 1 s for pairing. Test: tests/test_pipeline_load_api.py with a two-page synthetic bronze tree in tmp_path
(string-typed onPosition, a duplicate event id across pages, a gear event, an event missing onPosition).
```

### T11 — `pipeline/presence_bridge.py`: the viewer contract  (terra, medium–high; develop against the P0 fixture now, rerun after T7)

```
TASK: write the bridge from GapPair's risk-events.json (§6.1 contract) to the assets Will's presence viewer needs, and
the work list for Andrew's presence pulls. Read code/backend/contracts/presence.ts and code/backend/DATA_FLOW.md on
origin/main (git show origin/main:<path>) for the viewer's vessel id convention ("gfw:<vesselId>"), day assets and
coverage semantics. Do not modify anything under code/frontend/src or code/backend.
Outputs of run():
1. code/frontend/public/data/candidates.json — {"schemaVersion": 1, "generatedAt", "corpus", "attribution",
   "candidates": [...]} sorted like risk-events.json. Each candidate: id, label, riskLevel, riskScore, priority,
   evidenceTier, vessels[2] {gfwId: "gfw:<id>" or null, mmsi, name, flag, vesselClass, role}, window {start, end,
   overlapStart, overlapEnd, overlapHours}, presenceDays (UTC dates covering [start - 24 h, end + 24 h]),
   region {eezIds, rfmo, zone}, meetingPoint, geometry (the §6.2 track FeatureCollection, [lon, lat]), scores,
   features (the §6.1 subset), explanations, evidence, timeline. Nulls stay null.
2. data/derived/<corpus>/candidate_windows.json — for Andrew: eezCandidates[] {id, regionDataset: "public-eez-areas",
   regionId (int, the EEZ shared by both events, else the A event's), days, gfwIds, mmsis} for every candidate with a
   label of investigate or review, plus highSeasCandidates[] {id, rfmo, days, gfwIds} for the rest. Same shape as the
   existing data/derived/candidate_windows_probe.json.
3. data/derived/<corpus>/queue_vessel_ids.txt — distinct GFW vessel ids of all candidates (for the identity batch).
4. A coverage check: read code/frontend/public/data/presence/catalog.json if present and mark each candidate
   presenceCoverage: "full" | "partial" | "none" from its presenceDays against catalog.days[].date, so the viewer can
   grey out candidates without replay data.
Tests: tests/test_pipeline_presence_bridge.py on the three-record fixture: ids and vessel ids preserved, presenceDays
correct across a month boundary, coverage classification with a synthetic catalog, JSON round-trip, [lon, lat] order.
```

### A1 — Andrew (token holder), in this order

1. `data/derived/candidate_windows_probe.json` (push `Tanner-dev` or send the file): for each `eezCandidates` entry, run `gfw-presence` for each day in `presenceDays` with `--region-dataset public-eez-areas --region-id <eezIds[0]>`. Start with the first 10 entries; the rest in the background. Will's importer discovers every complete report + manifest under `data/bronze/gfw_presence` automatically.
2. Test whether 4Wings accepts a high-seas region (`--region-dataset public-rfmo` or `public-fao-areas` with an id): if yes, pull the `highSeasCandidates` too; if no, say so and those candidates ship without replay.
3. Rerun the batch identity puller (the one that produced `gfw_identity_ytd`) on `queue_vessel_ids.txt` when T10 writes it; commit the batches under `data/bronze/gfw_identity_queue/`.
4. Stop committing bronze for 2022–2026 GAP windows and for presence days no candidate needs.

### F2 — Will (viewer), can start against the fixture-derived `candidates.json`

1. Fetch `${BASE_URL}data/candidates.json` next to the presence catalog. Add a "Candidates" list (id, both vessel names or MMSIs, flags, riskScore, label, presenceCoverage) to the vessel panel or a new panel.
2. Selecting a candidate: set the date range to `presenceDays`, put the cursor on the hour of `window.start`, select vessel A (`vessels[0].gfwId`) and highlight B; add one GeoJSON source from `geometry` (observed endpoints as dots, dashed projections, meeting point as a hollow square, reachable rings as translucent polygons, every feature tagged `observationStatus` estimated or observed). Fit bounds to the four endpoints once.
3. Show `evidence[]`, `scores`, `explanations[]` and `timeline[]` in the detail panel; the existing `InvestigationPanel.tsx` markup and CSS can be reused. Show the attribution line.
4. Candidates with `presenceCoverage: "none"` still render their geometry; the timeline shows the viewer's existing "No imported data" state.

### Orchestrator note

T10 and T11 start now, in parallel with Wave 2 (new files only; T11 against the fixture). After T7 passes: rerun T11, then `PIPELINE_CORPUS=api2021 .venv/bin/python -m pipeline.run --all --draws 20`, then `--stage null --draws 200`, `--stage score --stage export`, `--stage bridge`. The CSV acceptance numbers do not apply to the api2021 run; the reviewer checks invariants (§0.5 checklists) and the probe numbers above.

### §14 addendum, 18:40 EDT — after the full branch survey (origin/main b60db32)

Facts that hold: nobody on any branch has written pairing, candidate or scoring code; GapPair's pipeline is the only implementation. `types.ts`, `provider.ts`, `InvestigationPanel.tsx` are byte-identical on `origin/main`, so F2 can reuse them without conflict. `App.tsx` on `main` is presence-only. Presence exists only for region 5690. Identity batches cover the 2026 presence population, not the 2021 corpus. No 2017–2019 bronze anywhere.

Convergence: Andrew's `docs/targeted-raw-ais-plan.md` (17:57) is the same architecture as §14, written from the data side: rank candidate windows from GFW-derived data, then pull observations only for those windows, with NOAA Marine Cadastre raw AIS as a first source for U.S.-coastal candidates and a coverage gate that reports `insufficient_coverage_evidence`. Adopt his request-record schema for the window file so his tooling reads it unchanged.

**T11 amendment.** `candidate_windows.json` entries use Andrew's §1 record: `candidate_id, trigger_type ("gfw_gap_pair"), trigger_source_ids [gap_id_a, gap_id_b], window_start_utc / window_end_utc (gap window ± 6 h), bbox_wgs84 (endpoints ± 0.5°), vessel_aliases [{mmsi, imo, gfw_vessel_id, name, flag}], region {kind, eez_ids, presence_region_dataset, presence_region_id}, presence_days_utc, provider_hints ["gfw_presence", "noaa_marine_cadastre" when either flag is USA or the EEZ is a U.S. one], coverage_hypothesis, request_reason`. `data/derived/candidate_windows_probe.json` is already in this shape (28 in-EEZ, 12 high-seas; only 2 of the 465 pairs involve a U.S.-flag vessel, so the NOAA pilot has two candidates at most).

**A1 amendment.** (1) unchanged: presence per `presence_days_utc`. (1b) For entries with `noaa_marine_cadastre` in `provider_hints`, run `ingest-noaa --date <day> --bbox <bbox_wgs84>` for the window's UTC days; that is the pilot your plan describes, with a real candidate. (5) The Atlantes activity experiment is off the critical path until presence for the top ten candidates and identity for the queue vessels are in the repo.

**S7 amendment (pipeline).** When a candidate has NOAA silver positions inside its window, `corroborate.py` may add `rawAis: {"state": "observed_close_approach" | "observed_no_close_approach" | "insufficient_coverage_evidence", "minSeparationKm", "sampleCount", "largestGapMin", "collectionMode": "terrestrial_ais_minute_downsampled"}` computed only from observed rows, never from presence grid centres. Optional; default `insufficient_coverage_evidence`.
