import json
import tempfile
import unittest
from pathlib import Path

from rl.evaluate_replay_league import load_case, parse_named_path, summarize


class ReplayLeagueTests(unittest.TestCase):
    def test_load_case_finds_seats_and_writes_tape(self):
        payload = {
            "info": {
                "EpisodeId": 123,
                "TeamNames": ["opponent", "ours"],
                "seed": 789,
            },
            "rewards": [20, 10],
            "steps": [
                [{"action": None}, {"action": None}],
                [
                    {"action": {"farmer": ["NORTH"]}},
                    {"action": {"farmer": ["SOUTH"]}},
                ],
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            replay = root / "replay.json"
            replay.write_text(json.dumps(payload), encoding="utf-8")
            case = load_case(replay, "ours", root / "agents")
            self.assertEqual(case.candidate_seat, 1)
            self.assertEqual(case.opponent_name, "opponent")
            self.assertEqual(case.recorded_candidate_bank, 10)
            self.assertTrue(Path(case.opponent_tape).exists())

    def test_summary_counts_outcome_changes(self):
        baseline = {
            1: {"outcome": 0.0, "margin": -10},
            2: {"outcome": 1.0, "margin": 20},
        }
        rows = [
            {"episode_id": 1, "outcome": 1.0, "margin": 5, "max_action_ms": 2},
            {"episode_id": 2, "outcome": 0.0, "margin": -5, "max_action_ms": 3},
        ]
        report = summarize(rows, baseline)
        self.assertEqual(report["outcome_improvements"], 1)
        self.assertEqual(report["outcome_regressions"], 1)
        self.assertEqual(report["average_margin_delta_vs_baseline"], -5)

    def test_requires_named_path(self):
        with self.assertRaises(ValueError):
            parse_named_path("missing")


if __name__ == "__main__":
    unittest.main()
