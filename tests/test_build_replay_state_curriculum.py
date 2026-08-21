import unittest

from rl.build_replay_state_curriculum import collect_episode, market_summary


def observation(step, own_money, opponent_money):
    farm = lambda money: {
        "money": money,
        "farmer": [0, 0],
        "hands": [],
        "hires_today": 0,
        "tiles": [],
        "unlocked_quadrants": [],
    }
    return {
        "step": step,
        "day": 0,
        "hour": step,
        "player": 0,
        "farms": [farm(own_money), farm(opponent_money)],
        "private": {"shed": {}, "seeds": {}, "inventories": []},
        "market": {"prices": {}, "inventory": {}},
        "town": {"unlocked_shops": []},
    }


class ReplayStateCurriculumTests(unittest.TestCase):
    def test_market_summary_counts_quantities(self):
        report = market_summary({"market": [["SELL", "WHEAT", 3], ["HIRE"]]})
        self.assertEqual(report["operations"], {"HIRE": 1, "SELL": 1})
        self.assertEqual(report["quantities"]["SELL:WHEAT"], 3)

    def test_collects_largest_negative_gap_swing(self):
        payload = {
            "info": {"EpisodeId": 1, "TeamNames": ["ours", "opp"], "seed": 7},
            "rewards": [90, 110],
            "steps": [
                [
                    {"observation": observation(0, 100, 100), "action": None},
                    {"observation": observation(0, 100, 100), "action": None},
                ],
                [
                    {"observation": observation(1, 90, 110), "action": {"market": []}},
                    {"observation": observation(1, 110, 90), "action": {"market": []}},
                ],
            ],
        }
        report = collect_episode(payload, "ours", top_k=1)
        self.assertEqual(report["recorded_margin"], -20)
        self.assertEqual(report["strata"][0]["gap_delta"], -20)
        self.assertIn("negative_gap_swing", report["strata"][0]["tags"])


if __name__ == "__main__":
    unittest.main()
