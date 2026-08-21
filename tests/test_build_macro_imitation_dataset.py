import unittest

from rl.build_macro_imitation_dataset import macro_label


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


if __name__ == "__main__":
    unittest.main()
