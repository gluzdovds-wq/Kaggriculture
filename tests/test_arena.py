import tempfile
import unittest
from pathlib import Path

from arena import agent_telemetry, private_storage_totals, public_farm_signature, timed_agent


class ArenaTests(unittest.TestCase):
    def test_storage_totals_exclude_seed_inventory(self):
        observation = {
            "private": {
                "shed": {"WHEAT": 7, "COW": 2},
                "seeds": {"MELON": 50},
                "inventories": [{"WOOL": 3}, {"MILK": 4, "WHEAT": 1}],
            }
        }
        self.assertEqual(private_storage_totals(observation), (9, 8))

    def test_public_farm_signature_excludes_private_state(self):
        farm = {
            "money": 22,
            "farmer": [4, 4],
            "hands": [[4, 4]],
            "hires_today": 1,
            "unlocked_quadrants": ["NW"],
            "tiles": [
                [
                    {"kind": "PASTURE", "animal": "COW"},
                    {"kind": "PLANT", "crop": "WHEAT"},
                    "LOCKED",
                ]
            ],
            "private": {"shed": {"WHEAT": 99}},
        }
        signature = public_farm_signature(farm)
        self.assertEqual(signature["tile_kinds"], {"PASTURE": 1, "PLANT": 1})
        self.assertEqual(signature["crops"], {"WHEAT": 1})
        self.assertEqual(signature["animals"], {"COW": 1})
        self.assertNotIn("private", signature)

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

    def test_instrumentation_exposes_agent_telemetry_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.py"
            path.write_text(
                "def agent(obs):\n"
                "    agent.telemetry['calls'] += 1\n"
                "    return {}\n"
                "agent.telemetry = {'calls': 0}\n",
                encoding="utf-8",
            )
            wrapped, _ = timed_agent(path, "telemetry")
            wrapped({})
            snapshot = agent_telemetry(wrapped)
            self.assertEqual(snapshot, {"calls": 1})
            snapshot["calls"] = 99
            self.assertEqual(agent_telemetry(wrapped), {"calls": 1})

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
