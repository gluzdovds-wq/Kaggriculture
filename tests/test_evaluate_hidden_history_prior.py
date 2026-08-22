import copy
import unittest

from rl.evaluate_hidden_history_prior import (
    combined_history_features,
    public_history_features,
    target_observation_stream,
)


def farm(money, tile=None, hands=None, quadrants=None):
    return {
        "money": money,
        "tiles": [[tile]],
        "farmer": [0, 0],
        "hands": hands or [],
        "hires_today": len(hands or []),
        "unlocked_quadrants": quadrants or ["NW"],
    }


def observation(step, target_money, opponent_money, opponent_tile=None):
    return {
        "player": 0,
        "day": step // 24,
        "hour": step % 24,
        "farms": [farm(target_money), farm(opponent_money, opponent_tile)],
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": {
            "inventory": {"WHEAT": 10000 - step},
            "prices": {"WHEAT": 25 + step},
        },
        "town": {"unlocked_shops": []},
    }


def replay_from(observations):
    steps = []
    for obs in observations:
        other = copy.deepcopy(obs)
        other["player"] = 1
        other["private"] = {"shed": {"WHEAT": 99}, "seeds": {}, "inventories": [{}]}
        steps.append(
            [
                {"observation": copy.deepcopy(obs), "action": {"secret": "left"}},
                {"observation": other, "action": {"secret": "right"}},
            ]
        )
    return {"info": {"EpisodeId": 7, "seed": 123}, "steps": steps}


class HiddenHistoryPriorTests(unittest.TestCase):
    def test_visible_plant_and_money_history_are_counted(self):
        empty = observation(0, 3000, 3000)
        planted = observation(
            1,
            2990,
            2975,
            {"kind": "PLANT", "crop": "WHEAT", "yield_units": 0},
        )
        features = public_history_features([empty, planted], 0)
        self.assertEqual(features["opponent_plant_started_wheat"], 1)
        self.assertEqual(features["opponent_money_negative_total"], 25)
        self.assertEqual(features["market_inventory_down_wheat"], 1)

    def test_history_is_invariant_to_actions_metadata_and_other_private(self):
        payload = replay_from([observation(0, 3000, 3000), observation(1, 3010, 2990)])
        baseline = combined_history_features(payload, 0, 1, {"snapshot": 1.0})
        changed = copy.deepcopy(payload)
        changed["info"] = {"EpisodeId": 999, "seed": 888, "TeamNames": ["x", "y"]}
        for state in changed["steps"]:
            state[0]["action"] = {"leak": 1}
            state[1]["action"] = {"leak": 2}
            state[1]["observation"]["private"] = {
                "shed": {"WOOL": 9999},
                "seeds": {"MELON": 9999},
                "inventories": [{"MILK": 9999}],
            }
        self.assertEqual(
            baseline,
            combined_history_features(changed, 0, 1, {"snapshot": 1.0}),
        )

    def test_target_stream_stops_at_checkpoint(self):
        payload = replay_from(
            [observation(0, 3000, 3000), observation(1, 3000, 3000), observation(2, 3000, 3000)]
        )
        stream = target_observation_stream(payload, 0, 1)
        self.assertEqual(len(stream), 2)


if __name__ == "__main__":
    unittest.main()
