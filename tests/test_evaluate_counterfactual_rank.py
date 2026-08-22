import json
from pathlib import Path
import unittest

from rl.evaluate_counterfactual_rank import (
    confidence_winner,
    pairwise_tournament,
    router_field,
    terminal_oracle,
)


ROOT = Path(__file__).parents[1]


def row(
    plan,
    money,
    rank,
    *,
    scenario="history_0",
    seed=1,
    response="maintain",
    horizon=24,
    phase="mid",
):
    return {
        "scenario": scenario,
        "future_seed": seed,
        "horizon": horizon,
        "plan": plan,
        "response": response,
        "score": money,
        "money_delta": money,
        "branch_step": 384,
        "leaf_money_margin": money,
        "leaf_legal_margin": money,
        "leaf_rank_score": rank,
        "rank_phase": phase,
    }


class CounterfactualRankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads(
            (ROOT / "rl" / "frozen_pairwise_rank_e105.json").read_text(
                encoding="utf-8"
            )
        )

    def test_confidence_gate_can_override_only_close_pair(self):
        phase = {
            "rank": {"margin_threshold": 100.0, "confidence_threshold": 0.5}
        }
        left = row("a", 10.0, -1.0)
        right = row("b", 0.0, 1.0)
        winner, override = confidence_winner(left, right, phase, 0.0)
        self.assertEqual(winner, -1)
        self.assertTrue(override)
        left["leaf_money_margin"] = 1000.0
        winner, override = confidence_winner(left, right, phase, 0.0)
        self.assertEqual(winner, 1)
        self.assertFalse(override)

    def test_tournament_is_scenario_complete_and_deterministic(self):
        rows = []
        # Rank score orders c > b > a even though money does the reverse.  The
        # real mid phase allows all three close differences and has confidence
        # threshold 0.2.
        for seed in (1, 2):
            rows.extend(
                [
                    row("a", 20.0, -2.0, seed=seed),
                    row("b", 10.0, 0.0, seed=seed),
                    row("c", 0.0, 2.0, seed=seed),
                ]
            )
        result = pairwise_tournament(rows, "history", 24, 360, self.model)
        self.assertEqual(result["selected"], "c")
        self.assertEqual(result["ranking"], ["c", "b", "a"])
        self.assertEqual(result["scenario_count"], 2)
        self.assertEqual(result["pair_comparisons"], 6)
        self.assertEqual(result["override_count"], 6)

    def test_terminal_oracle_uses_q25_final_money(self):
        rows = []
        for seed, a, b in ((1, 100.0, 90.0), (2, 0.0, 80.0)):
            rows.append(
                row(
                    "a", a, 0.0, scenario="oracle_terminal", seed=seed,
                    horizon=359,
                )
            )
            rows.append(
                row(
                    "b", b, 0.0, scenario="oracle_terminal", seed=seed,
                    horizon=359,
                )
            )
        result = terminal_oracle(rows)
        self.assertEqual(result["horizon"], 359)
        self.assertEqual(result["best"], "b")
        self.assertAlmostEqual(result["scores"]["a"], 25.0)
        self.assertAlmostEqual(result["scores"]["b"], 82.5)

    def test_frozen_router_uses_marked_then_terminal_money(self):
        router = json.loads(
            (ROOT / "fast_sim" / "frozen_search_router_e108.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(router["horizon"], 48)
        self.assertEqual(router_field(router, 360), "leaf_legal_margin")
        self.assertEqual(router_field(router, 600), "leaf_legal_margin")
        self.assertEqual(router_field(router, 648), "leaf_money_margin")
        self.assertEqual(router_field(router, 719), "leaf_money_margin")
        with self.assertRaises(ValueError):
            router_field(router, 0)


if __name__ == "__main__":
    unittest.main()
