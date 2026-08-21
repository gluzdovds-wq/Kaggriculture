import unittest

from tools.make_market_timing_variant import parse_item_caps


class MarketTimingVariantTests(unittest.TestCase):
    def test_parses_premium_product_cap(self):
        self.assertEqual(
            parse_item_caps(["milk=12", "STRAWBERRY=7"]),
            {"MILK": 12, "STRAWBERRY": 7},
        )

    def test_rejects_unknown_product(self):
        with self.assertRaises(ValueError):
            parse_item_caps(["GOLD=10"])

    def test_rejects_negative_cap(self):
        with self.assertRaises(ValueError):
            parse_item_caps(["MILK=-1"])


if __name__ == "__main__":
    unittest.main()
