import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rl.evaluate_replay_league import ReplayCase, load_case, parse_named_path, run_task, summarize


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

    @patch("rl.evaluate_replay_league.play")
    def test_run_task_keeps_public_selector_context(self, mocked_play):
        mocked_play.return_value = {
            "candidate_bank": 10,
            "opponent_bank": 9,
            "margin": 1,
            "outcome": 1.0,
            "candidate_artifact": {"sha256": "abc"},
            "candidate_latency": {"max_ms": 2},
            "candidate_telemetry": {},
            "shop_unlock_events": [{"step": 72, "new_shops": ["BAKERY"]}],
            "opponent_public_checkpoints": [{"step": 72, "opponent": {}}],
            "public_context_checkpoints": [{"step": 72, "shops": ["BAKERY"]}],
        }
        case = ReplayCase(1, "r.json", 2, 0, "opponent", "tape.py", 10, 9)
        row = run_task(("candidate", "candidate.py", case))
        self.assertEqual(row["shop_unlock_events"][0]["step"], 72)
        self.assertEqual(row["opponent_public_checkpoints"][0]["step"], 72)
        self.assertEqual(row["public_context_checkpoints"][0]["shops"], ["BAKERY"])


if __name__ == "__main__":
    unittest.main()
