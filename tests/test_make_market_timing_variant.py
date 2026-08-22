import unittest

from rl.augment_forward_features import MARKET_PARAMS as REFERENCE_MARKET_PARAMS
from rl.augment_forward_features import SHOPS as REFERENCE_SHOPS
from tools.make_market_timing_variant import MARKET_PARAMS, SHOPS, TEMPLATE, parse_item_caps


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

    def test_embedded_market_contract_matches_forward_features(self):
        self.assertEqual(MARKET_PARAMS, REFERENCE_MARKET_PARAMS)
        self.assertEqual(SHOPS, REFERENCE_SHOPS)

    def test_price_gated_template_compiles(self):
        rendered = TEMPLATE.format(
            items=("WOOL",),
            caps={"WOOL": 10},
            start=120,
            stop=715,
            x544_lead=2,
            moon_lead=2,
            moon_window_lead=3,
            moon_window_start=480,
            moon_window_stop=715,
            opening="keep",
            price_gate_ratio=0.98,
            market_params=MARKET_PARAMS,
            shops=SHOPS,
            label="test",
        )
        compile("def agent(obs, configuration=None): return {}\n" + rendered, "generated.py", "exec")
        self.assertIn("_MT_PRICE_GATE_RATIO = 0.98", rendered)

    def test_price_gate_rejects_a_sale_before_known_demand(self):
        rendered = TEMPLATE.format(
            items=("WOOL",),
            caps={"WOOL": 10},
            start=120,
            stop=715,
            x544_lead=2,
            moon_lead=2,
            moon_window_lead=3,
            moon_window_start=480,
            moon_window_stop=715,
            opening="keep",
            price_gate_ratio=1.0,
            market_params=MARKET_PARAMS,
            shops=SHOPS,
            label="test",
        )
        namespace = {}
        exec("def agent(obs, configuration=None): return {}\n" + rendered, namespace)
        observation = {
            "market": {"inventory": {"WOOL": 10000}},
            "town": {"unlocked_shops": ["YARN_STORE"]},
        }
        self.assertFalse(
            namespace["_mt_should_advance"](
                observation, "WOOL", 10, 0, step=100, horizon=2
            )
        )
        self.assertEqual(namespace["_MT_TELEMETRY"]["gate_rejected"], {"WOOL": 10})


if __name__ == "__main__":
    unittest.main()
