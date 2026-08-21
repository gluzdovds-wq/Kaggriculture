import unittest

from rl.evaluate_safe_route_mixture import (
    evaluate_mixture,
    fit_robust_mixture,
)
from rl.fit_route_policy_tree import Family


def family(name, pastures, x_outcome, moon_outcome, x_margin=0, moon_margin=0):
    return Family(
        name=name,
        features={"pastures": float(pastures)},
        metrics={
            "x544": {"outcome": x_outcome, "margin": x_margin},
            "moon": {"outcome": moon_outcome, "margin": moon_margin},
        },
    )


class SafeRouteMixtureTests(unittest.TestCase):
    def test_expected_outcome_is_linear_mixture(self):
        rows = [family("pasture", 1, 0.0, 1.0)]
        report = evaluate_mixture(
            rows,
            no_pasture_moon_probability=0.0,
            pasture_moon_probability=0.95,
        )
        self.assertAlmostEqual(report["mean_expected_outcome"], 0.95)
        self.assertAlmostEqual(report["mean_outcome_regret"], 0.05)

    def test_robust_fit_keeps_dominating_selector(self):
        rows = [
            family("plain", 0, 1.0, 0.5, 100, -100),
            family("pasture", 1, 0.0, 1.0, -100, 100),
        ]
        fitted = fit_robust_mixture(rows, step=0.05)
        self.assertEqual(fitted["no_pasture_moon_probability"], 0.0)
        self.assertEqual(fitted["pasture_moon_probability"], 1.0)
        self.assertEqual(fitted["worst_family_expected_outcome"], 1.0)

    def test_rejects_invalid_probability(self):
        with self.assertRaises(ValueError):
            evaluate_mixture(
                [family("x", 0, 1.0, 0.0)],
                no_pasture_moon_probability=-0.1,
                pasture_moon_probability=1.0,
            )


if __name__ == "__main__":
    unittest.main()
