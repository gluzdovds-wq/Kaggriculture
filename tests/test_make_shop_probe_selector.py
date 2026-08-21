import unittest

from tools.make_shop_probe_selector import shop_probe_selector_source


SOURCE = '''def _selector_call(namespace, obs, configuration):
    return namespace["agent"](obs)


def agent(obs, configuration=None):
    global _SELECTED_ROUTE
    return {}


agent.telemetry = _SELECTOR_TELEMETRY
__version__ = "base"
'''


class ShopProbeSelectorTests(unittest.TestCase):
    def test_renders_moon_probe_and_public_response_rule(self):
        generated = shop_probe_selector_source(
            SOURCE,
            aggressive_min_hands=4,
            label="n42",
        )
        self.assertIn("_PROBE_RESPONSE_STEP = 73", generated)
        self.assertIn("return moon_action", generated)
        self.assertIn("hands >= _PROBE_AGGRESSIVE_MIN_HANDS", generated)
        self.assertIn('__version__ = "base-n42"', generated)
        compile(generated, "generated.py", "exec")

    def test_rejects_invalid_threshold(self):
        with self.assertRaises(ValueError):
            shop_probe_selector_source(
                SOURCE,
                aggressive_min_hands=0,
                label="bad",
            )

    def test_rejects_non_h22_source(self):
        with self.assertRaises(ValueError):
            shop_probe_selector_source(
                "def agent(obs): return {}",
                aggressive_min_hands=4,
                label="bad",
            )


if __name__ == "__main__":
    unittest.main()
