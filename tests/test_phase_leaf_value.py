import unittest

import numpy as np

from rl.evaluate_leaf_value import group_folds, ridge_fit, ridge_predict
from rl.phase_leaf_value import (
    current_anchor_safe,
    phase_for_checkpoint,
    ridge_oof,
    serialize_ridge,
    serialized_ridge_predict,
    strongest_gate,
)


def paired_rows(checkpoints=(360, 600, 648)):
    return [
        {
            "episode_id": checkpoint,
            "checkpoint": checkpoint,
            "seat": seat,
            "features": {
                "money_delta": 10.0 if seat == 0 else -10.0,
                "legal_marked_margin": 8.0 if seat == 0 else -8.0,
            },
        }
        for checkpoint in checkpoints
        for seat in (0, 1)
    ]


class PhaseLeafValueTests(unittest.TestCase):
    def test_serialized_ridge_is_prediction_exact(self):
        x = np.asarray(
            [[0.0, 1.0, 4.0], [1.0, 1.0, 2.0], [2.0, 1.0, 0.0]]
        )
        y = np.asarray([2.0, 4.0, 8.0])
        fitted = ridge_fit(x, y, 10.0)
        expected = ridge_predict(fitted, x)
        actual = serialized_ridge_predict(serialize_ridge(fitted), x)
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)

    def test_grouped_ridge_oof_recovers_legal_offset(self):
        rows = [
            {"episode_id": episode}
            for episode in range(10)
            for _seat in (0, 1)
        ]
        folds = group_folds(rows, 5)
        x = np.zeros((20, 1), dtype=np.float64)
        offset = np.asarray(
            [episode * 100.0 for episode in range(10) for _seat in (0, 1)]
        )
        truth = offset + 3.0
        prediction = ridge_oof(x, truth, offset, folds, 10.0)
        np.testing.assert_allclose(prediction, truth, rtol=0, atol=1e-12)

    def test_anchor_safety_rejects_mae_and_winner_regression(self):
        rows = paired_rows()
        truth = np.asarray([12.0, -12.0] * 3)
        current = np.asarray([10.0, -10.0] * 3)
        safe, checks = current_anchor_safe(rows, current, truth, current)
        self.assertTrue(safe)
        self.assertTrue(all(row["pass"] for row in checks.values()))
        reversed_prediction = -current
        safe, checks = current_anchor_safe(
            rows, reversed_prediction, truth, current
        )
        self.assertFalse(safe)
        self.assertFalse(checks["648"]["pass"])

    def test_strongest_gate_requires_strict_overall_lift(self):
        rows = paired_rows()
        truth = np.asarray([12.0, -12.0] * 3)
        current = np.asarray([10.0, -10.0] * 3)
        legal = np.asarray([8.0, -8.0] * 3)
        zero = np.zeros(6)
        baselines = {
            "current_money": current,
            "legal_marked": legal,
            "zero": zero,
        }
        tied = strongest_gate(
            rows, current, truth, baselines, strict_overall=True
        )
        self.assertFalse(tied["pass"])
        improved = np.asarray([11.0, -11.0] * 3)
        passed = strongest_gate(
            rows, improved, truth, baselines, strict_overall=True
        )
        self.assertTrue(passed["pass"])

    def test_phase_lookup_covers_registered_boundaries(self):
        model = {
            "phases": {
                "early": {"start": 24, "stop": 192},
                "mid": {"start": 216, "stop": 480},
                "late": {"start": 504, "stop": 576},
                "terminal": {"start": 600, "stop": 648},
            }
        }
        self.assertEqual(phase_for_checkpoint(model, 24)[0], "early")
        self.assertEqual(phase_for_checkpoint(model, 360)[0], "mid")
        self.assertEqual(phase_for_checkpoint(model, 600)[0], "terminal")
        self.assertEqual(phase_for_checkpoint(model, 648)[0], "terminal")
        with self.assertRaisesRegex(ValueError, "outside frozen phases"):
            phase_for_checkpoint(model, 0)


if __name__ == "__main__":
    unittest.main()
