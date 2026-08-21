import unittest

from tools.make_fixed_route_variant import SELECTOR_BLOCK, freeze_route


class FixedRouteVariantTests(unittest.TestCase):
    def source(self):
        return (
            '__version__ = "embedded-base"\n'
            + "def choose():\n"
            + SELECTOR_BLOCK
            + "__version__ = \"market-timing-new-route\"\n"
        )

    def test_freezes_only_route_choice(self):
        frozen = freeze_route(self.source(), "moon")
        self.assertIn("pasture_opening = _selector_opponent_has_opening_pasture(obs)", frozen)
        self.assertIn("_SELECTED_ROUTE = 'moon'", frozen)
        self.assertNotIn('"moon" if pasture_opening else "x544"', frozen)
        self.assertIn('__version__ = "embedded-base"', frozen)
        self.assertIn('market-timing-new-route-fixed-moon', frozen)

    def test_rejects_missing_selector(self):
        with self.assertRaises(ValueError):
            freeze_route('__version__ = "market-timing-n13_fert10"\n', "x544")


if __name__ == "__main__":
    unittest.main()
