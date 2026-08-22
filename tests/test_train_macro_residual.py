import unittest

import numpy as np

from rl.train_macro_residual import evaluate, select_feature_names, softmax


class MacroResidualTests(unittest.TestCase):
    def test_softmax_rows_sum_to_one(self):
        values = softmax(np.asarray([[1.0, 2.0], [1000.0, 1000.0]]))
        np.testing.assert_allclose(values.sum(axis=1), [1.0, 1.0])

    def test_reports_top_k_and_critical_recall(self):
        scores = np.asarray([[3.0, 1.0], [0.0, 2.0]])
        report = evaluate(scores, np.asarray([0, 1]), ["service", "move"], "task_macro")
        self.assertEqual(report["accuracy"], 1.0)
        self.assertEqual(report["critical_macro_detection"]["service"]["recall"], 1.0)

    def test_feature_prefix_ablation(self):
        rows = [{"features": {"base": 1.0, "forward_eta": 2.0}}]
        self.assertEqual(select_feature_names(rows, ("forward_",)), ["base"])


if __name__ == "__main__":
    unittest.main()
