import unittest

from tools.make_shop_aware_selector import shop_aware_selector_source


SOURCE = '''def _selector_call(namespace, obs, configuration):
    return namespace["agent"](obs)


def agent(obs, configuration=None):
    global _SELECTED_ROUTE
    return {}


agent.telemetry = _SELECTOR_TELEMETRY
__version__ = "base"
'''


class ShopAwareSelectorTests(unittest.TestCase):
    def test_replaces_selector_with_public_shop_rule(self):
        generated = shop_aware_selector_source(SOURCE, label="n36")
        self.assertIn('_SHOP_DECISION_STEP = 72', generated)
        self.assertIn('_SHOP_COUNTER = "YARN_STORE"', generated)
        self.assertIn('not _SHOP_OPENING_PASTURE or yarn_counter', generated)
        self.assertIn('if step == 1:', generated)
        self.assertIn('__version__ = "base-n36"', generated)

    def test_rejects_non_h22_source(self):
        with self.assertRaises(ValueError):
            shop_aware_selector_source("def agent(obs): return {}", label="bad")


if __name__ == "__main__":
    unittest.main()
