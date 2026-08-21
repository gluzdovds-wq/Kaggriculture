import unittest

from tools.make_delayed_route_selector import delayed_selector_source


SOURCE = '''def _selector_call(namespace, obs, configuration):
    return namespace["agent"](obs)


def agent(obs, configuration=None):
    global _SELECTED_ROUTE
    return {}


agent.telemetry = _SELECTOR_TELEMETRY
__version__ = "base"
'''


class DelayedRouteSelectorTests(unittest.TestCase):
    def test_replaces_selector_and_updates_final_version(self):
        generated = delayed_selector_source(
            SOURCE,
            decision_step=112,
            moon_min_hands=4,
            label="n32",
        )
        self.assertIn("_DELAYED_DECISION_STEP = 112", generated)
        self.assertIn("hands >= _DELAYED_MOON_MIN_HANDS", generated)
        self.assertIn('__version__ = "base-n32"', generated)

    def test_rejects_invalid_checkpoint(self):
        with self.assertRaises(ValueError):
            delayed_selector_source(
                SOURCE,
                decision_step=0,
                moon_min_hands=4,
                label="bad",
            )

    def test_rejects_non_h22_source(self):
        with self.assertRaises(ValueError):
            delayed_selector_source(
                "def agent(obs): return {}",
                decision_step=112,
                moon_min_hands=4,
                label="bad",
            )


if __name__ == "__main__":
    unittest.main()
