import unittest

from rl.augment_forward_features import (
    augment_payload,
    fibonacci_hire_cost,
    forward_features,
    market_price,
    projected_inventory,
    sequential_sale_revenue,
)


def base_features() -> dict:
    features = {
        "step": 71.0,
        "day": 2.0,
        "hour": 23.0,
        "hands": 2.0,
        "own_money": 5000.0,
        "unlocked": 2.0,
        "shed_total": 95.0,
        "carried_total": 10.0,
        "shed_wheat": 10.0,
        "own_plants_unwatered": 4.0,
        "own_animals_unfed": 2.0,
        "opponent_plants_unwatered": 3.0,
        "opponent_animals_unfed": 1.0,
        "shop_bakery": 1.0,
    }
    for item in ("wheat", "carrot", "tomato", "strawberry", "melon", "egg", "milk", "wool", "fertilizer"):
        features.setdefault(f"shed_{item}", 0.0)
        features[f"market_{item}"] = 10000.0
        features[f"price_{item}"] = float(market_price(item.upper(), 10000))
    return features


class ForwardFeaturesTest(unittest.TestCase):
    def test_default_market_price_and_sequential_sale(self):
        self.assertEqual(market_price("WHEAT", 10000), 25)
        expected = market_price("WHEAT", 10000) + market_price("WHEAT", 10001)
        self.assertEqual(sequential_sale_revenue("WHEAT", 10000, 2), expected)

    def test_clock_feasibility_and_cost_features(self):
        report = forward_features(base_features())
        self.assertEqual(report["forward_turns_today"], 1.0)
        self.assertEqual(report["forward_turns_to_shop_unlock"], 1.0)
        self.assertEqual(report["forward_service_capacity_today"], 3.0)
        self.assertEqual(report["forward_service_slack_today"], -3.0)
        self.assertEqual(report["forward_eod_storage_overflow"], 5.0)
        self.assertEqual(report["forward_next_hire_cost"], 2.0)
        self.assertEqual(report["forward_next_land_cost"], 2000.0)
        self.assertEqual(report["forward_projection_complete_6"], 0.0)

    def test_known_town_projection_matches_tick_schedule(self):
        features = base_features()
        # Steps 71..76 include BAKERY ticks at 72/76 and a town-center tick at 72.
        self.assertEqual(projected_inventory(features, "WHEAT", 6), 9997)
        # Fertilizer is consumed by neither BAKERY nor town center.
        self.assertEqual(projected_inventory(features, "FERTILIZER", 6), 10000)

    def test_payload_requires_official_price_parity(self):
        payload, contract = augment_payload({"rows": [{"features": base_features()}]})
        self.assertGreater(contract["feature_count"], 20)
        self.assertIn("forward_liquidation_value_now", payload["rows"][0]["features"])
        broken = base_features()
        broken["price_wheat"] = 999.0
        with self.assertRaises(ValueError):
            augment_payload({"rows": [{"features": broken}]})

    def test_fibonacci_hire_cost(self):
        self.assertEqual([fibonacci_hire_cost(n) for n in range(6)], [1, 1, 2, 3, 5, 8])


if __name__ == "__main__":
    unittest.main()
