import unittest

from rl.distill_macro_router import best_plan, fit_tree, metrics, predict


def example(episode, signal, a_score, b_score):
    scores = {"a": float(a_score), "b": float(b_score)}
    ranking = sorted(scores, key=lambda plan: (-scores[plan], plan))
    return {
        "episode_id": episode,
        "checkpoint": 360,
        "seat": episode % 2,
        "features": {"signal": float(signal)},
        "scores": scores,
        "oracle_ranking": ranking,
        "search_router_plan": ranking[0],
    }


class DistillMacroRouterTests(unittest.TestCase):
    def test_cost_sensitive_tree_learns_counterfactual_split(self):
        rows = [
            example(1, 0, 10, 0),
            example(2, 0, 8, 0),
            example(3, 1, 0, 20),
            example(4, 1, 0, 18),
        ]
        tree = fit_tree(rows, ("signal",), depth=1, min_leaf=2)
        self.assertEqual(tree["feature"], "signal")
        self.assertEqual(predict(tree, {"signal": 0}), "a")
        self.assertEqual(predict(tree, {"signal": 1}), "b")
        report = metrics(
            rows, [predict(tree, row["features"]) for row in rows]
        )
        self.assertEqual(report["top1_recall"], 1.0)
        self.assertEqual(report["mean_terminal_money_regret"], 0.0)

    def test_leaf_plan_minimizes_summed_regret_not_vote_count(self):
        rows = [
            example(1, 0, 2, 0),
            example(2, 0, 2, 0),
            example(3, 0, 0, 100),
        ]
        plan, regret = best_plan(rows)
        self.assertEqual(plan, "b")
        self.assertEqual(regret, 4.0)


if __name__ == "__main__":
    unittest.main()
