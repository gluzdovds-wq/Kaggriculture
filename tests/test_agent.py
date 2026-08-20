import math
import unittest

from kaggle_environments import make

from main import agent


class AgentTests(unittest.TestCase):
    def test_full_game_finishes_with_finite_reward(self):
        env = make("kaggriculture", configuration={"seed": 12345}, debug=False)
        env.run([agent, "starter"])
        final = env.steps[-1]
        self.assertEqual([state["status"] for state in final], ["DONE", "DONE"])
        self.assertTrue(math.isfinite(float(final[0]["reward"])))

    def test_agent_returns_submission_shape(self):
        env = make("kaggriculture", configuration={"seed": 7}, debug=False)
        env.reset(2)
        obs = env.steps[0][0]["observation"]
        action = agent(obs)
        self.assertEqual(set(action), {"farmer", "hands", "market"})
        self.assertIsInstance(action["farmer"], list)
        self.assertIsInstance(action["hands"], list)
        self.assertIsInstance(action["market"], list)
        self.assertLessEqual(len(action["market"]), 10)


if __name__ == "__main__":
    unittest.main()

