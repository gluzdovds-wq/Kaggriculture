import unittest

from tools.evaluate_top_replay_counterfactuals import parse_named_path, summarize


class EvaluateTopReplayCounterfactualsTests(unittest.TestCase):
    def test_parse_named_path_requires_existing_file(self):
        with self.assertRaises(ValueError):
            parse_named_path("missing")
        name, path = parse_named_path("N39=main.py")
        self.assertEqual(name, "N39")
        self.assertTrue(path.endswith("main.py"))

    def test_summary_counts_donor_outcome_changes(self):
        donor = {
            (1, 0): {"candidate_bank": 100, "margin": 10, "outcome": 1.0},
            (2, 1): {"candidate_bank": 80, "margin": -5, "outcome": 0.0},
        }
        rows = [
            {
                "episode_id": 1,
                "target_seat": 0,
                "candidate_bank": 90,
                "margin": -1,
                "outcome": 0.0,
                "max_action_ms": 4,
            },
            {
                "episode_id": 2,
                "target_seat": 1,
                "candidate_bank": 85,
                "margin": 2,
                "outcome": 1.0,
                "max_action_ms": 5,
            },
        ]
        result = summarize(rows, donor)
        self.assertEqual(result["outcome_improvements"], 1)
        self.assertEqual(result["outcome_regressions"], 1)
        self.assertEqual(result["average_bank_delta_vs_donor"], -2.5)


if __name__ == "__main__":
    unittest.main()
