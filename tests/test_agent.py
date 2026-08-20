import math
import unittest
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.agent import get_last_callable

from main import agent


class AgentTests(unittest.TestCase):
    def test_kaggle_file_loader_selects_agent_wrapper(self):
        path = Path(__file__).resolve().parents[1] / "main.py"
        loaded = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
        self.assertEqual(loaded.__name__, "agent")
        self.assertIn(loaded.__code__.co_argcount, (1, 2))

    def test_full_game_finishes_with_finite_reward(self):
        env = make("kaggriculture", configuration={"seed": 12345}, debug=False)
        path = Path(__file__).resolve().parents[1] / "main.py"
        env.run([str(path), "starter"])
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
