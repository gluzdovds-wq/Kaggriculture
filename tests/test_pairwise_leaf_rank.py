import unittest

import numpy as np

from rl.pairwise_leaf_rank import (
    accuracy,
    antisymmetric_ridge_fit,
    confidence_decision,
    paired_examples,
)
from rl.phase_leaf_value import serialize_ridge, serialized_ridge_predict


class PairwiseLeafRankTests(unittest.TestCase):
    def test_pair_features_are_controlled_view_difference(self):
        rows = [
            {
                "episode_id": 7,
                "checkpoint": 360,
                "seat": 0,
                "features": {"money_delta": 5.0, "legal_marked_margin": 8.0},
                "targets": {"final_margin": 12.0},
            },
            {
                "episode_id": 7,
                "checkpoint": 360,
                "seat": 1,
                "features": {"money_delta": -5.0, "legal_marked_margin": -7.0},
                "targets": {"final_margin": -12.0},
            },
        ]
        pairs = paired_examples(rows, ("money_delta", "legal_marked_margin"))
        self.assertEqual(len(pairs), 1)
        np.testing.assert_array_equal(pairs[0]["x"], np.asarray([10.0, 15.0]))
        self.assertEqual(pairs[0]["label"], 1.0)
        self.assertEqual(pairs[0]["current_margin"], 5.0)

    def test_augmented_ridge_is_antisymmetric(self):
        x = np.asarray([[2.0, -1.0], [-0.5, 3.0], [1.0, 1.0]])
        y = np.asarray([1.0, -1.0, 1.0])
        model = serialize_ridge(antisymmetric_ridge_fit(x, y, 10.0))
        prediction = serialized_ridge_predict(model, x)
        reversed_prediction = serialized_ridge_predict(model, -x)
        np.testing.assert_allclose(
            reversed_prediction, -prediction, rtol=0, atol=1e-12
        )

    def test_confidence_gate_overrides_only_close_confident_disagreement(self):
        current = np.asarray([100.0, 2000.0, 100.0, -100.0])
        learned = np.asarray([-0.8, -0.9, -0.1, -0.7])
        decision, override = confidence_decision(
            current, learned, margin_threshold=500.0, confidence_threshold=0.4
        )
        np.testing.assert_array_equal(override, [True, False, False, False])
        np.testing.assert_array_equal(np.sign(decision), [-1.0, 1.0, 1.0, -1.0])

    def test_accuracy_uses_order_sign(self):
        score = np.asarray([10.0, -3.0, 0.0, 2.0])
        truth = np.asarray([1.0, -1.0, 1.0, -1.0])
        self.assertEqual(accuracy(score, truth), 0.5)

    def test_tied_replay_is_excluded_from_pair_labels(self):
        base = {
            "episode_id": 8,
            "checkpoint": 360,
            "features": {"money_delta": 0.0},
            "targets": {"final_margin": 0.0},
        }
        rows = [{**base, "seat": 0}, {**base, "seat": 1}]
        self.assertEqual(paired_examples(rows, ("money_delta",)), [])


if __name__ == "__main__":
    unittest.main()
