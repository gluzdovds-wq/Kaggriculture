import unittest

import numpy as np

from rl.train_macro_residual import evaluate, softmax


class MacroResidualTests(unittest.TestCase):
    def test_softmax_rows_sum_to_one(self):
        values = softmax(np.asarray([[1.0, 2.0], [1000.0, 1000.0]]))
        np.testing.assert_allclose(values.sum(axis=1), [1.0, 1.0])

    def test_reports_top_k_and_critical_recall(self):
        scores = np.asarray([[3.0, 1.0], [0.0, 2.0]])
        report = evaluate(scores, np.asarray([0, 1]), ["service", "move"], "task_macro")
        self.assertEqual(report["accuracy"], 1.0)
        self.assertEqual(report["critical_macro_detection"]["service"]["recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
