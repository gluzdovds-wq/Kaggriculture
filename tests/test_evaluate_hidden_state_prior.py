import unittest

import numpy as np

from rl.evaluate_hidden_state_prior import (
    SHED_ITEMS,
    SEED_ITEMS,
    evaluate_checkpoint,
    gross_value,
    hidden_target,
    prediction_metrics,
    random_particle_coverage,
    standardized_distances,
)


class HiddenStatePriorTests(unittest.TestCase):
    def test_hidden_target_has_stable_shed_seed_order(self):
        vector, carried = hidden_target(
            {
                "shed": {"WHEAT": 2, "COW": 1},
                "seeds": {"MELON": 3},
                "inventories": [{"MILK": 4}],
            }
        )
        self.assertEqual(vector[list(SHED_ITEMS).index("WHEAT")], 2)
        self.assertEqual(vector[list(SHED_ITEMS).index("COW")], 1)
        self.assertEqual(vector[len(SHED_ITEMS) + list(SEED_ITEMS).index("MELON")], 3)
        self.assertEqual(carried, 4)

    def test_gross_value_and_metrics(self):
        target = np.zeros(len(SHED_ITEMS) + len(SEED_ITEMS))
        target[list(SHED_ITEMS).index("MILK")] = 2
        target[len(SHED_ITEMS) + list(SEED_ITEMS).index("WHEAT")] = 3
        self.assertEqual(gross_value(target, {"MILK": 160}), 350)
        metrics = prediction_metrics(np.zeros_like(target), target, {"MILK": 160})
        self.assertEqual(metrics["item_l1"], 5)
        self.assertEqual(metrics["gross_value_abs_error"], 350)

    def test_standardization_ignores_constant_features(self):
        train = np.asarray([[1.0, 0.0], [1.0, 10.0]])
        distances = standardized_distances(train, np.asarray([1.0, 9.0]))
        self.assertLess(distances[1], distances[0])

    def test_random_particle_coverage_is_reproducible(self):
        size = len(SHED_ITEMS) + len(SEED_ITEMS)
        targets = np.zeros((3, size))
        targets[:, 0] = (0.0, 2.0, 10.0)
        target = np.zeros(size)
        target[0] = 3.0
        first = random_particle_coverage(
            targets, target, {"WHEAT": 25}, 2, 20, np.random.default_rng(7)
        )
        second = random_particle_coverage(
            targets, target, {"WHEAT": 25}, 2, 20, np.random.default_rng(7)
        )
        self.assertEqual(first, second)

    def test_grouped_evaluation_never_uses_same_episode_neighbor(self):
        examples = []
        size = len(SHED_ITEMS) + len(SEED_ITEMS)
        for episode_id, value in enumerate((0.0, 1.0, 9.0, 10.0), start=1):
            target = np.zeros(size)
            target[0] = value
            examples.append(
                {
                    "episode_id": episode_id,
                    "checkpoint": 72,
                    "target_seat": 0,
                    "features": {"legal_signal": value},
                    "target": target,
                    "hidden_carried_units": 0,
                    "prices": {"WHEAT": 25},
                }
            )
        report = evaluate_checkpoint(examples, (1, 2), particle_draws=4)
        self.assertEqual(report["same_episode_neighbor_violations"], 0)
        self.assertEqual(report["hidden_carried_nonzero_cases"], 0)
        self.assertIn("public_knn_2", report["methods"])
        self.assertIn("checkpoint_random_2", report["particle_coverage"])


if __name__ == "__main__":
    unittest.main()
