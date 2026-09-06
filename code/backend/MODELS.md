# Models and investigation queue

The current model lives in `models/fifty_fifty/model.json`. This is the seed-110
deterministic 50/50 demo from the modelling experiment. It needs vessel ID and
anchor timestamp, and does not load training labels. Its scores are demo
priorities. The original measured 50% TPR / 49.9988% FPR apply to the original
42,245 windows, not arbitrary future data.

## Generate the queue

From `code/backend`:

```sh
npm run export:investigations
```

The launcher uses `.venv-model/bin/python` at the repository root. Set
`MODEL_PYTHON` to another Python executable if needed. Python requires pandas
2.2 and PyArrow 21 (older PyArrow fails on existing input Parquets), plus NumPy.
The joblib adapter additionally requires joblib and scikit-learn compatible
with the saved estimator. The existing `.venv-model` has these packages.

Optional arguments:

```sh
npm run export:investigations -- --input /absolute/path/features.parquet --registry /absolute/path/registry.json --output /absolute/path/queue.json
```

The default input is `output/models/ship_suspicion/training_examples.parquet`.
It must have a unique `(vessel_id, anchor_date)` per row and the enabled models'
features. Anchor dates are normalized to UTC. The exporter drops `target` before
scoring, does not train or tune, and publishes atomically only after all models
succeed. A failed model fails the export; weights are never silently changed.

The output is `code/frontend/public/data/investigations/queue.json`. This is a
static batch workflow, not a running HTTP service. Regenerate after changing
models, inputs, weights, or thresholds; rebuild/deploy the frontend to publish
the new asset. Nothing is fetched from GFW automatically.

## Ensemble registry

`models/registry.json` lists enabled models, stable IDs, versions, adapters,
artifact paths, and positive weights. The ensemble is:

`score = sum(weight * model_score) / sum(weight)`

All scores must be finite and within `[0, 1]`. The default queue threshold is
0.5. Each batch contains at most one entry per vessel, sorted by score descending
then vessel ID. Every entry preserves individual model scores and versions;
the envelope records model artifact hashes and the input hash.

## Add another model

1. Put the trusted artifact under `models/<model-id>/`.
2. For a sklearn model, save a joblib dictionary with `model` (implementing
   `predict_proba`) and `features` (ordered input column names). The positive
   class must be label 1. Include required preprocessing in the estimator.
3. Add an entry to `registry.json`, for example:

```json
{"id":"behavior","version":"1","adapter":"joblib_probability","artifact":"behavior/model.joblib","enabled":true,"weight":1,"scoreMeaning":"future gap risk"}
```

4. Supply the required columns in the input feature table and rerun the export.

For other formats, add an adapter in `score_model` in
`scripts/export-investigations.py`. Its contract is one score per input row,
same order. Artifact paths must stay inside the registry directory. Only load
trusted joblib artifacts: loading pickle-based files executes Python code.

Before combining a trained model with this demo, disable the demo or set weights
based on evaluation: averaging a random score with a useful model can weaken
the useful model. Matching numeric ranges does not establish score calibration.

## Frontend behavior

The active Presence viewer loads the static queue and displays the newest batch
available at the replay cursor whose seven-day forecast horizon has not expired.
Future batches are never shown early. When no batch covers the cursor, the queue
offers “Open latest scored date.” Clicking an entry selects that GFW vessel in
the existing map/details flow; no position is fabricated for absent vessels.
Thirty entries are shown initially, with pagination. Names come from the active
Presence vessel index, falling back to MMSI or GFW ID. Errors and empty batches
are explicit, without replacing results with mock vessels.

Queue data does not create or modify analyst cases. Model ranking and case
workflow can evolve independently. The old `InvestigationPanel` is unused by
the active app; `ModelQueue` supplies the current investigation queue.

## Verify

From repository root:

```sh
.venv-model/bin/python -m unittest discover -s code/backend/tests -p 'test_models.py'
```

This checks historical model score parity, label-free scoring, weighted ensemble
arithmetic, and rejection of invalid weights. Run frontend `npm run build` and
backend `npm test` as well.
