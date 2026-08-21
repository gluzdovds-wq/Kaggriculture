import unittest

from tools.extract_replay_agent import actions_by_observation_step, render_agent


class ReplayAgentTests(unittest.TestCase):
    def payload(self):
        return {
            "info": {
                "EpisodeId": 123,
                "TeamNames": ["ours", "opponent"],
                "seed": 456,
            },
            "steps": [
                [{"action": {"farmer": ["PASS"]}}, {"action": None}],
                [
                    {"action": {"farmer": ["NORTH"]}},
                    {"action": {"farmer": ["BUILD_PASTURE"]}},
                ],
                [
                    {"action": {"farmer": ["SOUTH"]}},
                    {"action": {"farmer": ["WEST"]}},
                ],
            ],
        }

    def test_shifts_stored_action_back_to_observation_step(self):
        actions = actions_by_observation_step(self.payload(), 1)
        self.assertEqual(actions[0]["farmer"], ["BUILD_PASTURE"])
        self.assertEqual(actions[1]["farmer"], ["WEST"])

    def test_rendered_agent_is_self_contained_and_selectable(self):
        namespace = {}
        exec(render_agent(self.payload(), 1), namespace)
        self.assertEqual(namespace["agent"]({"step": 0})["farmer"], ["BUILD_PASTURE"])
        self.assertEqual(namespace["agent"]({"step": 1})["farmer"], ["WEST"])
        self.assertEqual(namespace["__source_seed__"], 456)

    def test_rejects_invalid_seat(self):
        with self.assertRaises(ValueError):
            actions_by_observation_step(self.payload(), 2)


if __name__ == "__main__":
    unittest.main()
