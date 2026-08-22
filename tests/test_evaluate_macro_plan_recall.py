import tempfile
import unittest
from pathlib import Path

import numpy as np

from rl.evaluate_macro_plan_recall import (
    example_particles,
    export_replay_trace,
    score_case,
)


class MacroPlanRecallTest(unittest.TestCase):
    def test_cpp_branches_use_reactive_opponent_not_future_tape(self):
        source = (
            Path(__file__).parents[1] / "fast_sim" / "macro_plan_eval.cpp"
        ).read_text(encoding="utf-8")
        rollout = source.split("static void emit_rollout", 1)[1].split(
            "int main", 1
        )[0]
        planner = source.split("static Action reactive_action", 1)[1].split(
            "static double item_unit_value", 1
        )[0]
        self.assertNotIn("turns[step].action", rollout)
        self.assertIn("reactive_action(branch, 1 - seat", rollout)
        self.assertNotIn("farms[1 - seat]", planner)

    def test_particle_selection_rejects_same_episode(self):
        train = [
            {
                "episode_id": 7,
                "features": {"money": 1.0},
                "target": np.zeros(17),
            }
        ]
        test = {
            "episode_id": 7,
            "features": {"money": 2.0},
            "target": np.ones(17),
        }
        with self.assertRaisesRegex(ValueError, "same EpisodeId"):
            example_particles(train, test, 1, "features")

    def test_history_ranking_recovers_oracle_best_and_zero_regret(self):
        oracle = {"a": 10.0, "b": 8.0, "c": 6.0, "d": 4.0}
        method_scores = {
            "blank": {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0},
            "marginal": {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0},
            "snapshot": {"a": 2.0, "b": 3.0, "c": 4.0, "d": 1.0},
            "history": {"a": 5.0, "b": 4.0, "c": 3.0, "d": 2.0},
        }
        rows = []
        for plan, value in oracle.items():
            rows.append(
                {
                    "scenario": "oracle",
                    "horizon": 24,
                    "plan": plan,
                    "score": value,
                }
            )
        for method, scores in method_scores.items():
            for plan, value in scores.items():
                rows.append(
                    {
                        "scenario": method + "_0",
                        "horizon": 24,
                        "plan": plan,
                        "score": value,
                    }
                )
        result = score_case(rows, 24)
        self.assertEqual(result["oracle_best"], "a")
        self.assertEqual(result["methods"]["history"]["top1"], "a")
        self.assertTrue(result["methods"]["history"]["oracle_best_in_top3"])
        self.assertEqual(result["methods"]["history"]["oracle_regret"], 0.0)
        self.assertEqual(result["methods"]["marginal"]["oracle_regret"], 6.0)

    def test_trace_export_uses_action_on_resulting_state(self):
        observation = {
            "farms": [{"money": 3000}, {"money": 3000}],
            "market": {"inventory": {item: 10000 for item in (
                "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
                "EGG", "MILK", "WOOL", "FERTILIZER",
            )}},
        }
        empty = {"action": None, "observation": observation}
        replay = {
            "configuration": {
                "episodeSteps": 720,
                "boardSize": 10,
                "startingMoney": 3000,
                "maxMarketOrdersPerTurn": 10,
                "turnsPerDay": 24,
                "shedCapacity": 100,
                "weedSpawnChance": 0.005,
                "townShopUnlockInterval": 3,
                "townShopSellInterval": 4,
                "townCenterSellInterval": 24,
                "farmHandCostMult": 1,
            },
            "info": {"seed": 123},
            "steps": [
                [dict(empty), dict(empty)],
                [
                    {
                        "action": {
                            "farmer": ["EAST"],
                            "hands": [],
                            "market": [["SELL", "WHEAT", 2]],
                        },
                        "observation": observation,
                    },
                    {
                        "action": {"farmer": ["PASS"], "hands": [], "market": []},
                        "observation": observation,
                    },
                ],
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trace.txt"
            export_replay_trace(replay, output)
            lines = output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "123 1")
        self.assertEqual(lines[2], "1 1 3 0 1 6 0 2")
        self.assertEqual(lines[3], "1 0 0 0 1")


if __name__ == "__main__":
    unittest.main()
