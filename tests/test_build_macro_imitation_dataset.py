import unittest

from rl.build_macro_imitation_dataset import feature_vector, macro_label, observation_forward_features


class MacroImitationDatasetTests(unittest.TestCase):
    def test_summarizes_joint_action_without_raw_state(self):
        label = macro_label(
            {
                "farmer": ["WATER"],
                "hands": [["NORTH"], ["HARVEST"]],
                "market": [["SELL", "WHEAT", 3], ["HIRE"]],
            }
        )
        self.assertEqual(label["task_macro"], "harvest+move+service")
        self.assertEqual(label["market_macro"], "hire+sell")
        self.assertEqual(label["field_operations"]["WATER"], 1)

    def test_full_observation_features_include_geometry_and_object_clocks(self):
        obs = {
            "player": 0,
            "step": 71,
            "day": 2,
            "hour": 23,
            "farms": [
                {
                    "farmer": [0, 0],
                    "hands": [[4, 4]],
                    "tiles": [
                        [
                            {
                                "kind": "PLANT",
                                "crop": "WHEAT",
                                "planted_day": 0,
                                "watered_today": False,
                                "consecutive_unwatered": 1,
                                "yield_units": 3,
                                "max_lifespan_step": 120,
                                "fertilized_until_day": -1,
                            },
                            {"kind": "WEED"},
                        ]
                    ],
                },
                {"farmer": [4, 4], "hands": [], "tiles": []},
            ],
            "private": {"inventories": [{"WHEAT": 2}, {}]},
            "market": {"prices": {"WHEAT": 25}},
        }
        features = observation_forward_features(obs)
        self.assertEqual(features["forward_service_targets"], 1.0)
        self.assertEqual(features["forward_service_eta_min"], 1.0)
        self.assertEqual(features["forward_ready_yield_units"], 3.0)
        self.assertEqual(features["forward_ready_yield_value"], 75.0)
        self.assertEqual(features["forward_weed_eta_min"], 2.0)
        self.assertEqual(features["forward_critical_plants"], 1.0)
        self.assertEqual(features["forward_carried_units"], 1.0)
        self.assertEqual(features["forward_carried_to_shed_eta_min"], 9.0)

    def test_feature_vector_derives_step_from_shared_clock(self):
        obs = {
            "player": 1,
            "step": 0,
            "day": 2,
            "hour": 5,
            "farms": [
                {"money": 1, "tiles": [], "farmer": [4, 4], "hands": [], "unlocked_quadrants": ["NW"]},
                {"money": 1, "tiles": [], "farmer": [4, 4], "hands": [], "unlocked_quadrants": ["NW"]},
            ],
            "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
            "market": {"prices": {}, "inventory": {}},
            "town": {"unlocked_shops": []},
        }
        self.assertEqual(feature_vector(obs)["step"], 53.0)


if __name__ == "__main__":
    unittest.main()
