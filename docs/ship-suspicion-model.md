# Ship suspicion model

## Objective

Predict whether a vessel observed in GFW hourly Presence will have a GFW event
marked as intentional AIS disabling in the following seven days. Each example
uses the preceding seven complete days. The output is named
`suspicion_score`; it is not an estimate of illegal conduct.

## Training cohort

- 42,245 vessel-window examples
- 4,504 distinct vessels
- 14 daily anchors from 2026-08-12 through 2026-08-25
- 36 positive examples from 9 distinct vessels
- 0.0852% positive prevalence
- 2021 Presence excluded because it provides only two consecutive covered days

The inputs are hourly 0.01-degree GFW Presence grid centres for Russian EEZ
region 5690, complete intentional-only GFW GAP pulls, and the supplied World
Port Index CSV. Unmatched vessels are weak negatives. Flag state, all vessel
identifiers, and GAP-event attributes are excluded from model inputs.

## Features and estimator

The 24 features describe observation coverage, approximate movement between
consecutive hourly cells, spatial spread, night activity, general/liquid-bulk
port proximity, identity completeness, and broad vessel type. Numeric inputs
use median imputation and robust scaling. Vessel type is one-hot encoded.

The estimator is class-weighted logistic regression with sigmoid calibration.
Evaluation uses three-fold stratified cross-validation grouped by vessel, so a
vessel cannot appear in both training and validation within a fold.

## Results

| Metric | Model | Non-informative baseline |
| --- | ---: | ---: |
| Average precision | 0.001571 | 0.000852 |
| ROC-AUC | 0.6690 | 0.5000 |
| Brier score (lower is better) | 0.002238 | 0.000851 |
| Log loss (lower is better) | 0.017799 | 0.006875 |
| Top 1% per-anchor precision / recall | 0 / 430 reviewed; 0 / 36 positives | - |

This model does not clear a useful deployment threshold. Its ranking metrics
are above the non-informative baseline, but calibration metrics are worse and
the operational top-1% review set finds none of the held-out positives. The
most likely causes are the nine-vessel positive sample, coarse/region-bounded
Presence data, weak negatives, and the fact that a global future gap need not
be behaviorally visible in the prior Russian-EEZ window.

The trained artifact is retained as a reproducible baseline and as a working
training/scoring pipeline. Do not promote it to an alerting system based on
these metrics.

## Deliberate overfit demonstration

`scripts/train_overfit_demo.py` adds vessel identity and anchor date as
memorization features and fits unrestricted Extra Trees. It reaches 1.000
training average precision, 1.000 training ROC-AUC, and 100% training top-1%
recall. With vessels held out, it falls to 0.000852 average precision, 0.4803
ROC-AUC, and 0% top-1% recall. This artifact demonstrates leakage and is saved
separately; it is not a replacement for the candidate model.

`scripts/train_fifty_fifty_demo.py` provides an explicit no-skill control. It
selects a deterministic hash seed on the training labels and produces 50%
true-positive rate and 49.9988% false-positive rate. Its balanced accuracy is
50.0006%, as expected for random classification.

## Static viewer export

`scripts/export_ship_suspicion.py` publishes the 200 highest precomputed
latest-anchor scores to `code/frontend/public/data/ship-suspicion.json`. The
browser reads that static snapshot; the exporter does not retrain or rescore a
model at page load.

The envelope has `schemaVersion`, `generatedAt`, `model`, and `vessels` keys.
`model` records the feature order, flattened evaluation metrics, version,
training timestamp, and caveat. Each vessel has `mmsi`, nullable display
identity fields, `vesselClass`, a [0, 1] score, a stable rank, and optional
signed `topFeatures` contributions.

The current model artifact can be incompatible with the local scikit-learn
runtime used for export. In that case the exporter leaves `topFeatures` empty
rather than inventing an explanation; an empty contribution list is an honest
compatibility limitation, not a zero contribution. The current training source
also deliberately excludes flag identity, so a missing flag in the static
asset is not a claim that a vessel has no flag.

This independent vessel score is separate from the GapPair paired-dark score.
Neither score is a probability of wrongdoing or evidence of an event.

## Reproduce

```bash
/usr/local/bin/python3.12 -m venv --system-site-packages .venv-model
.venv-model/bin/python -m pip install 'scikit-learn>=1.6,<1.7' 'joblib>=1.4,<2'
PYTHONPATH=src .venv-model/bin/python scripts/train_ship_suspicion.py
```

Score a compatible feature table:

```bash
PYTHONPATH=src .venv-model/bin/python scripts/score_ship_suspicion.py \
  --features output/models/ship_suspicion/training_examples.parquet \
  --anchor-date 2026-08-25 \
  --output output/models/ship_suspicion/latest_anchor_scores.csv
```

Publish the static snapshot after the training and score artifacts are present:

```bash
.venv/bin/python scripts/export_ship_suspicion.py
```
