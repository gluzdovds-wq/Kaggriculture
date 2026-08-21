import tempfile
import unittest
from pathlib import Path

from tools.make_shadow_shop_selector import render_selector


DEFAULT = '''def agent(obs, configuration=None):
    return {"branch": "common" if obs["step"] < 3 else "default"}
'''

OVERRIDE = '''def agent(obs, configuration=None):
    return {"branch": "common" if obs["step"] < 3 else "override"}
'''


class ShadowShopSelectorTests(unittest.TestCase):
    def render(self, *, default_source=DEFAULT, override_source=OVERRIDE):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        default = root / "default.py"
        override = root / "override.py"
        default.write_text(default_source, encoding="utf-8")
        override.write_text(override_source, encoding="utf-8")
        return render_selector(
            default,
            override,
            shops=["bakery"],
            decision_step=3,
            label="test",
        )

    def test_selects_override_after_compatible_prefix(self):
        namespace = {"__name__": "generated"}
        exec(compile(self.render(), "generated.py", "exec"), namespace)
        agent = namespace["agent"]
        for step in range(3):
            self.assertEqual(
                agent({"step": step, "player": 0, "town": {"unlocked_shops": []}}),
                {"branch": "common"},
            )
        action = agent(
            {"step": 3, "player": 0, "town": {"unlocked_shops": ["BAKERY"]}}
        )
        self.assertEqual(action, {"branch": "override"})
        self.assertEqual(agent.telemetry["selected"], "override")
        self.assertTrue(agent.telemetry["compatible_prefix"])

    def test_falls_back_when_prefix_is_incompatible(self):
        namespace = {"__name__": "generated"}
        source = self.render(
            override_source='''def agent(obs, configuration=None):
    return {"branch": "different" if obs["step"] < 3 else "override"}
'''
        )
        exec(compile(source, "generated.py", "exec"), namespace)
        agent = namespace["agent"]
        agent({"step": 0, "player": 0, "town": {"unlocked_shops": []}})
        action = agent(
            {"step": 3, "player": 0, "town": {"unlocked_shops": ["BAKERY"]}}
        )
        self.assertEqual(action, {"branch": "default"})
        self.assertEqual(agent.telemetry["selected"], "default")
        self.assertFalse(agent.telemetry["compatible_prefix"])

    def test_rejects_invalid_configuration(self):
        missing = Path("missing.py")
        with self.assertRaises(ValueError):
            render_selector(
                missing,
                missing,
                shops=[],
                decision_step=3,
                label="test",
            )
        with self.assertRaises(ValueError):
            render_selector(
                missing,
                missing,
                shops=["BAKERY"],
                decision_step=-1,
                label="test",
            )


if __name__ == "__main__":
    unittest.main()
