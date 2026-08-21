import unittest

from tools.make_terminal_route_variant import OVERLAY


class TerminalRouteVariantTests(unittest.TestCase):
    def test_drop_and_same_turn_sale_are_emitted(self):
        self.assertIn('orders[index] = ["DROP"]', OVERLAY)
        self.assertIn("_h21_add_sales(action, inventory)", OVERLAY)

    def test_kaggle_loader_alias_is_fresh_and_last(self):
        self.assertIn("h21_kaggle_entrypoint = agent", OVERLAY)

    def test_route_and_pressure_gates_precede_overrides(self):
        self.assertIn('globals().get("_SELECTED_ROUTE") == _H21_ROUTE', OVERLAY)
        self.assertIn("total >= _H21_MIN_TOTAL", OVERLAY)
        self.assertIn("if not _H21_ACTIVE[seat]", OVERLAY)


if __name__ == "__main__":
    unittest.main()
