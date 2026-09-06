import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('exporter', BACKEND / 'scripts/export-investigations.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ModelTests(unittest.TestCase):
    def test_saved_demo_parity_and_target_independence(self):
        repo = BACKEND.parents[1]
        source = repo / 'output/models/ship_suspicion/fifty_fifty_demo/fifty_fifty_predictions.csv'
        if not source.exists():
            self.skipTest('Local historical predictions unavailable')
        frame = pd.read_csv(source)
        scores, _ = exporter.score_model({'adapter': 'splitmix64', 'artifact': 'fifty_fifty/model.json'}, frame.drop(columns='target'), BACKEND / 'models')
        np.testing.assert_allclose(scores, frame.random_score, atol=1e-14)

    def test_weighted_mean_and_invalid_weights(self):
        registry = {'version': 1, 'ensemble': {'method': 'weighted_mean', 'threshold': .5}, 'models': [
            {'id': 'a', 'enabled': True, 'weight': 1}, {'id': 'b', 'enabled': True, 'weight': 3}]}
        with patch.object(exporter, 'score_model', side_effect=[(np.array([.2, .4]), 'a'), (np.array([.8, .6]), 'b')]):
            scores, _, _ = exporter.ensemble(pd.DataFrame(index=[0, 1]), registry, BACKEND)
        np.testing.assert_allclose(scores, [.65, .55])
        registry['models'][0]['weight'] = -1
        with self.assertRaises(ValueError):
            exporter.ensemble(pd.DataFrame(), registry, BACKEND)


if __name__ == '__main__':
    unittest.main()
