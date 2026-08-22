import unittest

from rl.audit_hidden_state import (
    extract_checkpoint_rows,
    hidden_metrics,
    summarize,
)


def observation(player, private):
    return {
        "player": player,
        "step": 72,
        "day": 3,
        "hour": 0,
        "farms": [{"money": 1000}, {"money": 2000}],
        "market": {
            "prices": {"WHEAT": 25, "MILK": 160, "FERTILIZER": 100}
        },
        "town": {"unlocked_shops": ["BAKERY"]},
        "private": private,
    }


class HiddenStateAuditTests(unittest.TestCase):
    def test_hidden_metrics_marks_products_animals_and_seeds(self):
        metrics = hidden_metrics(
            {
                "shed": {"WHEAT": 2, "COW": 1},
                "seeds": {"MELON": 3},
                "inventories": [{"MILK": 2}, {"FERTILIZER": 1}],
            },
            {"WHEAT": 25, "MILK": 160, "FERTILIZER": 100},
        )
        self.assertEqual(metrics["hidden_shed_units"], 3)
        self.assertEqual(metrics["hidden_seed_units"], 3)
        self.assertEqual(metrics["hidden_carried_units"], 3)
        self.assertEqual(metrics["hidden_total_units"], 9)
        self.assertEqual(metrics["hidden_gross_value"], 1110)

    def test_extract_uses_other_seat_private_as_audit_label(self):
        left = observation(0, {"shed": {"WHEAT": 1}, "seeds": {}, "inventories": [{}]})
        right = observation(1, {"shed": {"WHEAT": 4}, "seeds": {}, "inventories": [{}]})
        replay = {
            "info": {"EpisodeId": 7, "TeamNames": ["left", "right"], "seed": 99},
            "steps": [
                [
                    {"observation": {**left, "step": step}},
                    {"observation": {**right, "step": step}},
                ]
                for step in range(73)
            ],
        }
        rows = extract_checkpoint_rows(replay, (72,))
        self.assertEqual(rows[0]["target_seat"], 0)
        self.assertEqual(rows[0]["hidden_shed_units"], 4)
        self.assertEqual(rows[1]["hidden_shed_units"], 1)
        self.assertFalse(rows[0]["observation_seed_present"])

    def test_rejects_divergent_shared_views(self):
        left = observation(0, {})
        right = observation(1, {})
        right["farms"] = [{"money": 999}, {"money": 2000}]
        replay = {
            "info": {"EpisodeId": 8},
            "steps": [[{"observation": left}, {"observation": right}]],
        }
        with self.assertRaises(ValueError):
            extract_checkpoint_rows(replay, (72,))

    def test_summary_reports_seed_visibility_and_nonzero_fraction(self):
        base = {
            "episode_id": 1,
            "checkpoint": 72,
            "target_seat": 0,
            "target_name": "a",
            "opponent_name": "b",
            "hidden_shed": {},
            "hidden_seeds": {},
            "hidden_carried": {},
            "replay_seed_present_offline": True,
            "observation_seed_present": False,
        }
        rows = []
        for value in (0, 10):
            rows.append(
                {
                    **base,
                    "hidden_shed_units": value,
                    "hidden_seed_units": 0,
                    "hidden_carried_units": 0,
                    "hidden_total_units": value,
                    "hidden_gross_value": value * 25,
                    "hidden_nonzero_item_types": int(value > 0),
                }
            )
        report = summarize(rows, 1, (72,))
        metric = report["by_checkpoint"]["72"]["metrics"]["hidden_total_units"]
        self.assertEqual(metric["fraction_nonzero"], 0.5)
        self.assertEqual(report["source_seed_visibility"]["present_in_legal_observation_fraction"], 0)


if __name__ == "__main__":
    unittest.main()
