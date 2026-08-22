import unittest

from rl.evaluate_factorized_macro_shortlist import (
    evaluate_scope,
    rank_macro_labels,
)


def row(task: str, market: str, x: float = 0.0) -> dict:
    return {
        "features": {"x": x},
        "label": {"task_macro": task, "market_macro": market},
    }


class FactorizedMacroShortlistTest(unittest.TestCase):
    def test_ranker_reconstructs_model_and_removes_other(self):
        report = {
            "labels": ["left", "right", "__OTHER__"],
            "model": {
                "feature_names": ["x"],
                "center": [0.0],
                "scale": [1.0],
                "weights": [[-1.0, 1.0, 0.0]],
                "bias": [0.0, 0.0, 2.0],
            },
        }
        rankings = rank_macro_labels([row("left", "none", -3.0), row("right", "none", 3.0)], report)
        self.assertEqual(rankings[0], ["left", "right"])
        self.assertEqual(rankings[1], ["right", "left"])

    def test_scope_measures_cartesian_and_seen_pair_shortlists(self):
        rows = [row("a", "x"), row("b", "y"), row("rare", "x")]
        task_rankings = [["a", "b"], ["a", "b"], ["a", "b"]]
        market_rankings = [["x", "y"], ["x", "y"], ["x", "y"]]
        seen_pairs = {("a", "x"), ("b", "y")}
        report = evaluate_scope(
            rows,
            task_rankings,
            market_rankings,
            seen_pairs,
            configurations=((1, 1), (2, 2)),
        )
        self.assertEqual(report["representable_joint_rate"], 2 / 3)
        self.assertEqual(report["pair_seen_in_train_rate"], 2 / 3)
        self.assertEqual(report["configurations"]["task1_market1"]["joint_recall"], 1 / 3)
        wide = report["configurations"]["task2_market2"]
        self.assertEqual(wide["joint_recall"], 2 / 3)
        self.assertEqual(wide["seen_pair_filtered_recall"], 2 / 3)
        self.assertEqual(wide["cartesian_candidate_count"]["mean"], 4)
        self.assertEqual(wide["seen_pair_candidate_count"]["mean"], 2)

    def test_shape_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_scope([row("a", "x")], [], [], set(), configurations=((1, 1),))


if __name__ == "__main__":
    unittest.main()
