# Verification guide

Use this checklist after changing a pipeline stage, static export, or viewer
consumer. A zero process exit code is not enough: confirm that the expected
artifact was written, contains the expected corpus, and satisfies its contract.

## 1. Establish the change boundary

```bash
git status --short
git diff --check
git diff --name-only
```

Review both staged and unstaged changes before treating a test result as
belonging to the work under review. Do not include unrelated generated files or
large data changes without an explicit decision.

## 2. Verify the Python and pipeline layers

From the repository root, run the relevant focused tests first, then the
broader Python suite when the changed area warrants it:

```bash
.venv/bin/python -m pytest -q tests/test_pipeline_features.py tests/test_pipeline_score.py
.venv/bin/python -m pytest -q tests/test_pipeline_export.py
.venv/bin/python -m pytest -q tests/
```

The static-artifact test validates the complete committed S8 queue (434
reference-corpus records) and its embedded GeoJSON. Do not exclude paths from
test discovery when using the full suite as a release gate.

For a full reference-corpus rebuild, run the stages in dependency order. This
is intentionally explicit so an operator can see which artifact changed:

```bash
.venv/bin/python -m pipeline.run --stage reference --stage load --stage pair \
  --stage feasibility --stage context --stage null --draws 20 \
  --stage corroborate --stage features --stage score --stage export
```

Use the configured null-draw count for a production-quality run; the smaller
draw count above is a fast, reproducible smoke check. A different corpus may
have a different number of candidates, so record its corpus and run parameters
with the result.

## 3. Inspect the published candidate export

The following check validates every exported record using the backend validator
and makes the current reference-corpus expectations explicit. For the
2017–2019 CSV reference corpus, the expected queue has 434 records and lacks
behavioral corroboration; `scores.beh` must therefore remain `null` rather than
being fabricated as zero.

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

from pipeline.export import validate_record

path = Path('code/frontend/public/data/risk-events.json')
records = json.loads(path.read_text(encoding='utf-8'))
assert len(records) == 434, f'expected 434 reference records, got {len(records)}'
for record in records:
    validate_record(record)
assert all(record['scores']['beh'] is None for record in records)
print(f'validated {len(records)} records; behavior component is honestly unavailable')
PY
```

If the corpus, scoring policy, or evidence availability has deliberately
changed, update the assertion and the corresponding live documentation in the
same review. Do not silently preserve an old count merely because it was once
expected.

Also inspect the generated methods metadata and evidence ledger when their
inputs changed. Their weights, null-model values, and headline counts must
agree with the exported records and stage checkpoints.

## 4. Verify the browser consumer

```bash
npm --prefix code/backend test
npm --prefix code/frontend ci
npm --prefix code/frontend test
npm --prefix code/frontend run build
```

Then load the viewer against the published static assets. Confirm that it has a
clear failure state if the asset is absent or invalid; it must not quietly swap
in mock records. On the map, confirm that endpoint observations and estimated
projections/reachable geometry use visually distinct treatments.

## 5. Verify the independent ship-suspicion snapshot

Regenerate the asset only from its documented precomputed model artifacts, then
check that its small browser contract is internally consistent:

```bash
.venv/bin/python scripts/export_ship_suspicion.py
.venv/bin/python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('code/frontend/public/data/ship-suspicion.json').read_text())
assert payload['schemaVersion'] == 1
assert payload['vessels']
assert [vessel['rank'] for vessel in payload['vessels']] == list(range(1, len(payload['vessels']) + 1))
assert all(0 <= vessel['score'] <= 1 for vessel in payload['vessels'])
assert payload['model']['caveat']
print(f"validated {len(payload['vessels'])} ship-suspicion records")
PY
```

An empty `topFeatures` list is allowed when the saved model cannot be safely
loaded by the export runtime. It is not a reason to manufacture an explanation.

## 6. Complete the documentation pass

Before handoff, update the documents affected by the result:

- [status.md](status.md) for verified behavior, current counts, and remaining
  limitations.
- [candidate-pipeline.md](candidate-pipeline.md) for a completed stage,
  scoring definition, output, or command change.
- [architecture.md](architecture.md) when the producer/consumer boundary or
  data flow changes.
- [data.md](data.md) when artifact provenance, coverage, or evidence semantics
  change.

Record evidence limits plainly. A successful build, valid JSON, or high score
does not turn inferred geometry or grid-centre presence into raw AIS evidence.
