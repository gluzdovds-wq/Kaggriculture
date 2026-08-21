import unittest

from rl.fit_route_policy_tree import Family, evaluate, fit_stump, predict


def family(name, signal, x_outcome, moon_outcome):
    return Family(
        name=name,
        features={"signal": float(signal)},
        metrics={
            "x544": {"outcome": float(x_outcome), "margin": 0.0},
            "moon": {"outcome": float(moon_outcome), "margin": 0.0},
        },
    )


class RoutePolicyTreeTests(unittest.TestCase):
    def test_learns_a_transparent_split(self):
        rows = [
            family("a", 0, 1, 0),
            family("b", 0, 1, 0),
            family("c", 1, 0, 1),
            family("d", 1, 0, 1),
        ]
        model = fit_stump(rows)
        self.assertEqual(model["kind"], "stump")
        self.assertEqual(model["feature"], "signal")
        self.assertEqual(predict(model, {"signal": 0}), "x544")
        self.assertEqual(predict(model, {"signal": 1}), "moon")
        report = evaluate(model, rows)
        self.assertEqual(report["exact_route_accuracy"], 1.0)
        self.assertEqual(report["outcome_optimal_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
