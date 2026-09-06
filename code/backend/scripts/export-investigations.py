"""Backend batch inference and static investigation queue publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
sys.path.insert(0, str(REPO / 'src'))


def score_model(spec, frame, root):
    artifact = (root / spec['artifact']).resolve()
    if not artifact.is_relative_to(root.resolve()):
        raise ValueError('Artifact must be inside models directory')
    if spec['adapter'] == 'splitmix64':
        config = json.loads(artifact.read_text())
        keys = frame[['vessel_id', 'anchor_date']].copy()
        keys['anchor_date'] = pd.to_datetime(keys['anchor_date'], utc=True)
        z = pd.util.hash_pandas_object(keys.astype(str), index=False).to_numpy(dtype=np.uint64)
        with np.errstate(over='ignore'):
            z = (z ^ np.uint64(config['seed_selected_on_training_labels'])) + np.uint64(0x9E3779B97F4A7C15)
            z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
            z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
            z = z ^ (z >> np.uint64(31))
        scores = 1 - z.astype(float) / float(2**64 - 1)
    elif spec['adapter'] == 'joblib_probability':
        import joblib
        bundle = joblib.load(artifact)
        features = bundle['features']
        if {'target', 'flag_state', 'flag'} & set(features):
            raise ValueError('Target and flag fields cannot be inference features')
        classes = list(bundle['model'].classes_)
        if 1 not in classes:
            raise ValueError('Model must expose positive class 1')
        scores = bundle['model'].predict_proba(frame[features])[:, classes.index(1)]
    else:
        raise ValueError(f"Unknown adapter: {spec['adapter']}")
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (len(frame),) or not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError(f"Invalid scores from {spec['id']}")
    return scores, hashlib.sha256(artifact.read_bytes()).hexdigest()


def ensemble(frame, registry, root):
    if registry.get('version') != 1 or registry['ensemble']['method'] != 'weighted_mean':
        raise ValueError('Unsupported registry or ensemble version')
    threshold = registry['ensemble']['threshold']
    if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise ValueError('Threshold must be in [0,1]')
    specs = [m for m in registry['models'] if m['enabled']]
    if not specs or len({m['id'] for m in specs}) != len(specs):
        raise ValueError('Enable at least one model with unique IDs')
    weights = np.array([m['weight'] for m in specs], dtype=float)
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('Enabled weights must be finite and positive')
    outputs, manifest = [], []
    for spec in specs:
        scores, digest = score_model(spec, frame, root)
        outputs.append(scores)
        manifest.append({**spec, 'sha256': digest})
    matrix = np.column_stack(outputs)
    return matrix @ (weights / weights.sum()), matrix, manifest


def publish(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(payload, stream, allow_nan=False, separators=(',', ':'))
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=REPO / 'output/models/ship_suspicion/training_examples.parquet')
    parser.add_argument('--registry', type=Path, default=BACKEND / 'models/registry.json')
    parser.add_argument('--output', type=Path, default=BACKEND.parent / 'frontend/public/data/investigations/queue.json')
    args = parser.parse_args()
    frame = pd.read_parquet(args.input).drop(columns=['target'], errors='ignore')
    frame['anchor_date'] = pd.to_datetime(frame['anchor_date'], utc=True)
    if frame.empty or frame.duplicated(['vessel_id', 'anchor_date']).any():
        raise ValueError('Input must have unique, nonempty vessel-window rows')
    if frame[['vessel_id', 'anchor_date']].isna().any().any():
        raise ValueError('Missing scoring keys')
    frame = frame.sort_values(['anchor_date', 'vessel_id']).reset_index(drop=True)
    registry = json.loads(args.registry.read_text())
    scores, matrix, models = ensemble(frame, registry, args.registry.parent)
    batches = []
    for anchor, group in frame.groupby('anchor_date'):
        items = []
        for i, row in group.iterrows():
            if scores[i] < registry['ensemble']['threshold']:
                continue
            items.append({
                'id': f"{row['vessel_id']}@{anchor.isoformat()}",
                'vesselId': str(row['vessel_id']),
                'mmsi': None if pd.isna(row.get('mmsi')) else str(row['mmsi']),
                'vesselType': str(row.get('vessel_type', 'unknown')),
                'score': float(scores[i]),
                'modelScores': [{'id': model['id'], 'version': model['version'], 'score': float(matrix[i, k])} for k, model in enumerate(models)],
            })
        items.sort(key=lambda item: (-item['score'], item['vesselId']))
        batches.append({'asOf': anchor.isoformat(), 'windowStart': (anchor - pd.Timedelta(days=7)).isoformat(), 'windowEnd': (anchor + pd.Timedelta(days=7)).isoformat(), 'scoredVessels': len(group), 'items': items})
    payload = {'schemaVersion': 1, 'models': models, 'ensemble': registry['ensemble'], 'inputSha256': hashlib.sha256(args.input.read_bytes()).hexdigest(), 'batches': batches}
    publish(args.output, payload)
    print(f"Published {len(batches)} batches / {sum(len(b['items']) for b in batches)} queue entries to {args.output}")


if __name__ == '__main__':
    main()
