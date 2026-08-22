import unittest

from tools.analyze_replay_meta import (
    analyze_player,
    pearson,
    quantity,
    tile_counts,
    vector_difference,
)


class AnalyzeReplayMetaTests(unittest.TestCase):
    def test_quantity_defaults_and_rejects_negative(self):
        self.assertEqual(quantity(["HIRE"]), 1)
        self.assertEqual(quantity(["SELL", "MILK", 7]), 7)
        self.assertEqual(quantity(["SELL", "MILK", -2]), 0)

    def test_tile_counts_separates_crops_and_animals(self):
        counts = tile_counts(
            {
                "tiles": [
                    [
                        {"kind": "PLANT", "crop": "MELON", "watered_today": False},
                        {"kind": "PASTURE", "animal": "COW", "fed_today": True},
                    ]
                ]
            }
        )
        self.assertEqual(counts["crop_MELON"], 1)
        self.assertEqual(counts["animal_COW"], 1)
        self.assertEqual(counts["unwatered"], 1)

    def test_vector_math_for_matched_comparisons(self):
        self.assertEqual(
            vector_difference({"a": 3.0, "b": 2.0}, {"a": 1.0, "c": 4.0}),
            {"a": 2.0, "b": 2.0, "c": -4.0},
        )
        self.assertAlmostEqual(pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]), 1.0)
        self.assertIsNone(pearson([1.0, 1.0], [2.0, 3.0]))

    def test_replay_action_is_shifted_to_pre_action_observation(self):
        farm0 = {
            "money": 3000,
            "farmer": [0, 0],
            "hands": [],
            "unlocked_quadrants": ["NW"],
            "tiles": [[None]],
        }
        farm1 = dict(farm0)
        observation0 = {
            "day": 0,
            "hour": 0,
            "farms": [farm0, farm1],
            "market": {"prices": {"WHEAT": 25}},
            "private": {"shed": {}, "inventories": [{}]},
        }
        observation1 = {
            **observation0,
            "hour": 1,
            "farms": [{**farm0, "money": 2975}, farm1],
        }
        replay = {
            "info": {
                "EpisodeId": 123,
                "seed": 99,
                "Agents": [{"Name": "A"}, {"Name": "B"}],
            },
            "rewards": [4000, 3500],
            "steps": [
                [
                    {"observation": observation0, "action": {"farmer": ["PASS"]}},
                    {"observation": observation0, "action": {"farmer": ["PASS"]}},
                ],
                [
                    {
                        "observation": observation1,
                        "action": {
                            "farmer": ["PLANT", "WHEAT"],
                            "hands": [],
                            "market": [["BUY_SEED", "WHEAT", 1], ["HIRE"]],
                        },
                    },
                    {"observation": observation1, "action": {"farmer": ["PASS"]}},
                ],
            ],
        }
        result = analyze_player(replay, 0)
        self.assertEqual(result["first_steps"]["field_PLANT"], 0)
        self.assertEqual(result["first_steps"]["market_BUY_SEED"], 0)
        self.assertEqual(result["seed_buys"]["WHEAT"], 1)
        self.assertEqual(result["total_hires"], 1)
        self.assertEqual(result["final_bank"], 4000)


if __name__ == "__main__":
    unittest.main()
