import unittest

from rl.fit_replay_route_tree import evaluate, fit_stump, paired_rows


def context(money):
    farm = {
        "money": 10,
        "farmer": [4, 4],
        "hands": [],
        "hires_today": 0,
        "unlocked_quadrants": ["NW"],
        "tile_kinds": {},
        "crops": {},
        "animals": {},
    }
    opponent = dict(farm)
    opponent["money"] = money
    return {
        "step": 72,
        "shops": ["BAKERY"],
        "market_inventory": {},
        "market_prices": {},
        "candidate": farm,
        "opponent": opponent,
    }


def report(diverge=False):
    candidates = {"X": {"matches": []}, "M": {"matches": []}}
    for episode in range(12):
        low = episode < 6
        for name, route in (("X", "x544"), ("M", "moon")):
            current = context(episode)
            if diverge and name == "M" and episode == 0:
                current = context(99)
            outcome = float((route == "x544") == low)
            candidates[name]["matches"].append(
                {
                    "episode_id": episode,
                    "candidate_seat": 0,
                    "outcome": outcome,
                    "margin": 10 if outcome else -10,
                    "public_context_checkpoints": [current],
                }
            )
    return {"candidates": candidates}


class ReplayRouteTreeTests(unittest.TestCase):
    def test_stump_learns_public_money_split(self):
        rows = paired_rows(report(), "X", "M", 72)
        model = fit_stump(rows, min_leaf=3)
        self.assertEqual(model["kind"], "stump")
        self.assertIn(model["feature"], {"opponent.money", "delta.money"})
        result = evaluate(model, rows)
        self.assertEqual(result["predicted_outcome"], 12)
        self.assertEqual(result["route_counts"], {"x544": 6, "moon": 6})

    def test_rejects_divergent_predecision_context(self):
        with self.assertRaisesRegex(ValueError, "diverge before decision"):
            paired_rows(report(diverge=True), "X", "M", 72)


if __name__ == "__main__":
    unittest.main()
