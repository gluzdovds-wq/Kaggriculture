import unittest

from rl.evaluate_shop_route_selector import n36_route, paired_rows, summary


def match(*, route_outcome, margin, pasture, shop):
    return {
        "seed": 7,
        "candidate_seat": 0,
        "outcome": route_outcome,
        "margin": margin,
        "opponent_public_checkpoints": [
            {"step": 1, "opponent": {"tile_kinds": {"PASTURE": pasture}}}
        ],
        "shop_unlock_events": [
            {"step": 72, "new_shops": [shop]}
        ],
    }


class ShopRouteSelectorTests(unittest.TestCase):
    def test_n36_rule(self):
        self.assertEqual(n36_route(False, ("PET_CAFE",)), "x544")
        self.assertEqual(n36_route(True, ("YARN_STORE",)), "x544")
        self.assertEqual(n36_route(True, ("BAKERY",)), "moon")

    def test_paired_report_computes_zero_regret(self):
        x = {"opponents": {"A": {"matches": [match(route_outcome=0, margin=-2, pasture=1, shop="BAKERY")]}}}
        moon = {"opponents": {"A": {"matches": [match(route_outcome=1, margin=2, pasture=1, shop="BAKERY")]}}}
        rows = paired_rows(x, moon)
        result = summary(rows)
        self.assertEqual(rows[0]["predicted"], "moon")
        self.assertEqual(result["outcome_optimal_rate"], 1.0)
        self.assertEqual(result["mean_outcome_regret"], 0.0)


if __name__ == "__main__":
    unittest.main()
