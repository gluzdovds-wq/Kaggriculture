import tempfile
import unittest
from pathlib import Path

from arena import timed_agent


class ArenaTests(unittest.TestCase):
    def test_instrumentation_preserves_two_argument_agent_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.py"
            path.write_text(
                "def agent(obs, configuration=None):\n"
                "    return {'marker': configuration.get('marker')}\n",
                encoding="utf-8",
            )
            wrapped, timings = timed_agent(path, "two_args")
            self.assertEqual(wrapped({}, {"marker": 17}), {"marker": 17})
            self.assertEqual(wrapped._arena_signature, "(obs, configuration=None)")
            self.assertTrue(wrapped._arena_accepts_configuration)
            self.assertEqual(len(timings), 1)

    def test_instrumentation_still_supports_one_argument_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.py"
            path.write_text(
                "def agent(obs):\n"
                "    return {'marker': obs.get('marker')}\n",
                encoding="utf-8",
            )
            wrapped, timings = timed_agent(path, "one_arg")
            self.assertEqual(wrapped({"marker": 23}, {"ignored": True}), {"marker": 23})
            self.assertEqual(wrapped._arena_signature, "(obs)")
            self.assertFalse(wrapped._arena_accepts_configuration)
            self.assertEqual(len(timings), 1)


if __name__ == "__main__":
    unittest.main()
