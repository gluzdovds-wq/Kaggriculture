import unittest

from macro_router_runtime import (
    MACRO_HORIZON,
    reactive_macro_action,
    select_frozen_plan,
    wrap_agent,
)
from tools.make_macro_router_switch import render


def observation(step=360, money=10_000, milk=10_000, wool=10_000):
    farm = {
        "money": money,
        "tiles": [[None] + ["LOCKED"] * 9] + [["LOCKED"] * 10 for _ in range(9)],
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
    }
    return {
        "step": step,
        "day": step // 24,
        "hour": step % 24,
        "player": 0,
        "farms": [farm, {**farm, "money": 9_000}],
        "private": {
            "shed": {},
            "seeds": {},
            "inventories": [{}],
        },
        "market": {
            "inventory": {"MILK": milk, "WOOL": wool},
            "prices": {},
        },
    }


class MacroRouterRuntimeTests(unittest.TestCase):
    def test_frozen_thresholds_and_late_external_fallback(self):
        self.assertEqual(select_frozen_plan(observation(milk=9_990), 360), "cow_lean")
        self.assertEqual(
            select_frozen_plan(observation(milk=10_000), 360),
            "strawberry_hold_land",
        )
        self.assertEqual(
            select_frozen_plan(observation(step=600, wool=10_040), 600),
            "maintain_workers",
        )
        self.assertEqual(
            select_frozen_plan(observation(step=600, wool=10_050), 600),
            "strawberry_hold_land",
        )
        self.assertEqual(
            select_frozen_plan(observation(step=648), 648), "maintain_workers"
        )

    def test_reactive_action_has_valid_shape_and_order_cap(self):
        obs = observation()
        obs["farms"][0]["tiles"][0][0] = {
            "kind": "PLANT",
            "crop": "WHEAT",
            "planted_day": 14,
            "yield_units": 0,
            "watered_today": False,
            "fertilized_until_day": -1,
        }
        action = reactive_macro_action(obs, "strawberry_hold_land")
        self.assertEqual(set(action), {"farmer", "hands", "market"})
        self.assertIsInstance(action["farmer"][0], str)
        self.assertEqual(action["hands"], [])
        self.assertLessEqual(len(action["market"]), 10)

    def test_wrapper_uses_only_frozen_48_turn_windows(self):
        calls = []

        def base(obs, _configuration=None):
            calls.append(obs["step"])
            return {"farmer": ["BASE"], "hands": [], "market": []}

        routed = wrap_agent(base, checkpoints=(360,))
        self.assertEqual(routed(observation(step=359))["farmer"], ["BASE"])
        self.assertNotEqual(routed(observation(step=360))["farmer"], ["BASE"])
        self.assertNotEqual(
            routed(observation(step=360 + MACRO_HORIZON - 1))["farmer"], ["BASE"]
        )
        self.assertEqual(
            routed(observation(step=360 + MACRO_HORIZON))["farmer"], ["BASE"]
        )
        self.assertEqual(calls, [359, 360, 407, 408])

    def test_generator_appends_versioned_entrypoint(self):
        generated = render("def agent(obs):\n    return {}\n", (360, 600))
        self.assertIn("checkpoints=(360, 600)", generated)
        self.assertIn('__version__ = "macro-router-e109-cp360-600"', generated)


if __name__ == "__main__":
    unittest.main()
