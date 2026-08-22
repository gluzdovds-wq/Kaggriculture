import copy
import unittest

import numpy as np

from rl.evaluate_leaf_value import (
    examples_from_replay,
    group_folds,
    legal_value_features,
    ridge_fit,
    ridge_predict,
    select_ridge,
)


def observation(player=0, left_money=3000, right_money=3000, wheat=0):
    farms = [
        {
            "money": left_money,
            "farmer": [4, 4],
            "hands": [],
            "hires_today": 0,
            "tiles": [],
            "unlocked_quadrants": ["NW"],
        },
        {
            "money": right_money,
            "farmer": [4, 4],
            "hands": [],
            "hires_today": 0,
            "tiles": [],
            "unlocked_quadrants": ["NW"],
        },
    ]
    return {
        "player": player,
        "step": 0,
        "day": 0,
        "hour": 0,
        "farms": farms,
        "private": {
            "shed": {"WHEAT": wheat},
            "seeds": {},
            "inventories": [{}],
        },
        "market": {
            "prices": {"WHEAT": 25},
            "inventory": {"WHEAT": 10000},
        },
        "town": {"unlocked_shops": []},
    }


class LeafValueEvaluationTests(unittest.TestCase):
    def test_legal_features_ignore_offline_metadata_and_actions(self):
        clean = observation(wheat=2)
        contaminated = copy.deepcopy(clean)
        contaminated.update(
            {
                "episode_id": 17,
                "source_seed": 99,
                "opponent_private": {"shed": {"WHEAT": 999}},
                "action": {"market": [["SELL", "WHEAT", 99]]},
            }
        )
        self.assertEqual(
            legal_value_features(clean), legal_value_features(contaminated)
        )
        features = legal_value_features(clean)
        self.assertEqual(features["shed_wheat"], 2.0)
        self.assertGreater(features["own_private_marked_value"], 0.0)

    def test_replay_targets_are_shifted_forward_without_action_features(self):
        steps = []
        for step in range(49):
            left = observation(0, 3000 + 10 * step, 3000 + 4 * step)
            right = observation(1, 3000 + 10 * step, 3000 + 4 * step)
            for item in (left, right):
                item["step"] = step
                item["day"], item["hour"] = divmod(step, 24)
            steps.append(
                [
                    {"observation": left, "action": {"farmer": ["NORTH"]}},
                    {"observation": right, "action": {"farmer": ["SOUTH"]}},
                ]
            )
        rows = examples_from_replay(
            {"info": {"EpisodeId": 7}, "steps": steps}, (24,)
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["targets"]["margin_24"], 288.0)
        self.assertEqual(rows[0]["targets"]["final_margin"], 288.0)
        self.assertEqual(rows[1]["targets"]["margin_24"], -288.0)
        self.assertFalse(
            any("action" in name.casefold() for name in rows[0]["features"])
        )

    def test_group_folds_keep_both_seats_and_checkpoints_together(self):
        rows = [
            {"episode_id": episode, "checkpoint": checkpoint, "seat": seat}
            for episode in range(10)
            for checkpoint in (24, 48)
            for seat in (0, 1)
        ]
        folds = group_folds(rows, 5)
        for episode in range(10):
            indices = [
                index
                for index, row in enumerate(rows)
                if row["episode_id"] == episode
            ]
            memberships = [
                fold for fold, mask in enumerate(folds) if mask[indices[0]]
            ]
            self.assertEqual(len(memberships), 1)
            self.assertTrue(folds[memberships[0]][indices].all())

    def test_ridge_residual_recovers_offset_that_features_cannot_encode(self):
        rows = [
            {"episode_id": episode}
            for episode in range(10)
            for _seat in (0, 1)
        ]
        folds = group_folds(rows, 5)
        x = np.zeros((len(rows), 1), dtype=np.float64)
        offset = np.asarray(
            [episode * 1000.0 for episode in range(10) for _seat in (0, 1)]
        )
        y = offset + 7.0
        _, direct = select_ridge(x, y, np.zeros_like(offset), folds, (1.0,))
        _, residual = select_ridge(x, y, offset, folds, (1.0,))
        self.assertGreater(direct["1.0"], 1000.0)
        self.assertAlmostEqual(residual["1.0"], 0.0, places=9)
        model = ridge_fit(x, y - offset, 1.0)
        np.testing.assert_allclose(offset + ridge_predict(model, x), y)


if __name__ == "__main__":
    unittest.main()
