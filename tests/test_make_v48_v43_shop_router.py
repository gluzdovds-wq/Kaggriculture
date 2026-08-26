import tempfile
import unittest
from pathlib import Path

from tools.make_v48_v43_shop_router import render_router


V48 = '''CALLS = 0
def agent(obs, configuration=None):
    global CALLS
    CALLS = 0 if obs.get("step") == 0 else CALLS
    CALLS += 1
    branch = "common" if obs.get("step", 0) < 72 else "v48"
    return {"farmer": ["PASS", branch, CALLS], "hands": [], "market": []}
'''

V43 = '''CALLS = 0
def agent(obs, configuration=None):
    global CALLS
    CALLS = 0 if obs.get("step") == 0 else CALLS
    CALLS += 1
    branch = "common" if obs.get("step", 0) < 72 else "v43"
    return {"farmer": ["PASS", branch, CALLS], "hands": [], "market": []}
'''


class V48V43ShopRouterTests(unittest.TestCase):
    def load(self, *, v43_source=V43):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        v48 = root / "v48.py"
        v43 = root / "v43.py"
        v48.write_text(V48, encoding="utf-8")
        v43.write_text(v43_source, encoding="utf-8")
        source = render_router(
            v48,
            v43,
            expected_v48_sha256=None,
            expected_v43_sha256=None,
        )
        namespace = {"__name__": "generated_test_router"}
        exec(compile(source, "generated_test_router.py", "exec"), namespace)
        return namespace

    @staticmethod
    def obs(step, shops=()):
        return {
            "step": step,
            "player": 0,
            "farms": [{"hands": []}, {"hands": []}],
            "town": {"unlocked_shops": list(shops)},
        }

    def test_shadow_runs_both_and_routes_only_after_first_shop(self):
        namespace = self.load()
        agent = namespace["agent"]
        self.assertEqual(agent(self.obs(0))["farmer"][1:], ["common", 1])
        self.assertEqual(agent(self.obs(71))["farmer"][1:], ["common", 2])
        action = agent(self.obs(72, ["FARMERS_MARKET"]))
        self.assertEqual(action["farmer"][1:], ["v43", 3])
        self.assertEqual(agent.telemetry["calls"], {"v48": 3, "v43": 3})
        self.assertTrue(agent.telemetry["compatible_prefix"])

    def test_first_shop_choice_is_sticky_and_step_zero_resets_it(self):
        namespace = self.load()
        agent = namespace["agent"]
        agent(self.obs(0))
        first = agent(self.obs(72, ["BAKERY"]))
        later = agent(self.obs(144, ["BAKERY", "ICE_CREAM_SHOP"]))
        self.assertEqual(first["farmer"][1], "v48")
        self.assertEqual(later["farmer"][1], "v48")
        self.assertEqual(agent.telemetry["first_shop"], "BAKERY")
        reset = agent(self.obs(0))
        selected = agent(self.obs(72, ["ICE_CREAM_SHOP"]))
        self.assertEqual(reset["farmer"][1:], ["common", 1])
        self.assertEqual(selected["farmer"][1:], ["v43", 2])

    def test_any_full_action_prefix_mismatch_latches_v48(self):
        namespace = self.load(
            v43_source='''CALLS = 0
def agent(obs, configuration=None):
    global CALLS
    CALLS = 0 if obs.get("step") == 0 else CALLS
    CALLS += 1
    branch = "different" if obs.get("step") == 5 else (
        "common" if obs.get("step", 0) < 72 else "v43"
    )
    return {"farmer": ["PASS", branch, CALLS], "hands": [], "market": []}
'''
        )
        agent = namespace["agent"]
        agent(self.obs(0))
        mismatch = agent(self.obs(5))
        selected = agent(self.obs(72, ["FARMERS_MARKET"]))
        self.assertEqual(mismatch["farmer"][1], "common")
        self.assertEqual(selected["farmer"][1], "v48")
        self.assertFalse(agent.telemetry["compatible_prefix"])
        self.assertEqual(agent.telemetry["prefix_mismatches"], 1)

    def test_invalid_v43_action_fails_closed_to_v48_shape(self):
        namespace = self.load(
            v43_source='''def agent(obs, configuration=None):
    return {"not": "an action"}
'''
        )
        agent = namespace["agent"]
        first = agent(self.obs(0))
        action = agent(self.obs(72, ["FARMERS_MARKET"]))
        self.assertEqual(first["farmer"][1], "common")
        self.assertEqual(set(action), {"farmer", "hands", "market"})
        self.assertEqual(action["farmer"][1], "v48")
        self.assertEqual(agent.telemetry["v43_invalid_actions"], 2)
        self.assertFalse(agent.telemetry["compatible_prefix"])
        self.assertEqual(agent.telemetry["prefix_mismatches"], 1)

    def test_v43_prefix_error_latches_v48(self):
        namespace = self.load(
            v43_source='''def agent(obs, configuration=None):
    raise RuntimeError("broken shadow")
'''
        )
        agent = namespace["agent"]
        agent(self.obs(0))
        selected = agent(self.obs(72, ["ICE_CREAM_SHOP"]))
        self.assertEqual(selected["farmer"][1], "v48")
        self.assertFalse(agent.telemetry["compatible_prefix"])
        self.assertEqual(agent.telemetry["prefix_mismatches"], 1)
        self.assertEqual(agent.telemetry["v43_errors"], 2)


if __name__ == "__main__":
    unittest.main()
