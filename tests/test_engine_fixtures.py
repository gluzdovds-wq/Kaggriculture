import contextlib
import io
import unittest

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as kg


PASS = {"farmer": ["PASS"], "hands": [], "market": []}


class EngineFixtureTests(unittest.TestCase):
    def test_only_719_actions_are_executed_in_720_state_episode(self):
        calls = [0, 0]

        def counting_agent(seat):
            def act(obs):
                calls[seat] += 1
                return PASS

            return act

        env = make("kaggriculture", configuration={"seed": 91}, debug=False)
        env.run([counting_agent(0), counting_agent(1)])
        self.assertEqual(len(env.steps), 720)
        self.assertEqual(calls, [719, 719])

    def test_atomic_plant_over_demand_rejects_all_requests(self):
        def probe(obs):
            hour = int(obs.get("hour", 0))
            hands = len(obs["farms"][0].get("hands", []))
            if hour == 0:
                return {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "CARROT", 1], ["HIRE"]]}
            if hour == 1:
                return {"farmer": ["PASS"], "hands": [["WEST"]] * hands, "market": []}
            if hour == 2:
                return {
                    "farmer": ["PLANT", "CARROT"],
                    "hands": [["PLANT", "CARROT"]] * hands,
                    "market": [],
                }
            return {"farmer": ["PASS"], "hands": [["PASS"]] * hands, "market": []}

        env = make(
            "kaggriculture",
            configuration={"seed": 92, "episodeSteps": 5},
            debug=False,
        )
        env.run([probe, "pass"])
        final = env.steps[-1][0]["observation"]
        self.assertIsNone(final["farms"][0]["tiles"][4][4])
        self.assertEqual(final["private"]["seeds"]["CARROT"], 1)

    def test_plant_must_be_watered_on_planting_day(self):
        def grower(water):
            def act(obs):
                hour = int(obs.get("hour", 0))
                if hour == 0:
                    return {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "CARROT", 1]]}
                if hour == 1:
                    return {"farmer": ["PLANT", "CARROT"], "hands": [], "market": []}
                if hour == 2 and water:
                    return {"farmer": ["WATER"], "hands": [], "market": []}
                return PASS

            return act

        watered = make("kaggriculture", configuration={"seed": 93, "episodeSteps": 26}, debug=False)
        dry = make("kaggriculture", configuration={"seed": 93, "episodeSteps": 26}, debug=False)
        watered.run([grower(True), "pass"])
        dry.run([grower(False), "pass"])
        watered_tile = watered.steps[-1][0]["observation"]["farms"][0]["tiles"][4][4]
        dry_tile = dry.steps[-1][0]["observation"]["farms"][0]["tiles"][4][4]
        self.assertEqual(watered_tile.get("kind"), "PLANT")
        self.assertEqual(dry_tile, {"kind": "WEED"})

    def test_end_of_day_drop_obeys_inventory_order_and_capacity(self):
        private = kg._new_private()
        private["inventories"] = [{"WHEAT": 80}, {"MELON": 30}]
        kg._drop_inventories_to_shed(private, 100)
        self.assertEqual(private["shed"]["WHEAT"], 80)
        self.assertEqual(private["shed"]["MELON"], 20)
        self.assertEqual(private["inventories"], [{}, {}])

    def test_buy_sell_round_trip_has_zero_profit_without_external_change(self):
        market = kg._new_market()
        farm = kg._new_farm(10, 3000)
        private = kg._new_private()
        start_money = farm["money"]
        buy_price = kg.market_price("WHEAT", market["inventory"]["WHEAT"] - 1)
        self.assertTrue(kg._commit_unit("BUY_PRODUCT", "WHEAT", buy_price, farm, private, market))
        sell_price = kg.market_price("WHEAT", market["inventory"]["WHEAT"])
        self.assertTrue(kg._commit_unit("SELL", "WHEAT", sell_price, farm, private, market))
        self.assertEqual(farm["money"], start_money)

    def test_animal_produces_on_first_unfed_day_then_escapes_on_second(self):
        farm = kg._new_farm(10, 3000)
        farm["tiles"][0][0] = kg._new_animal("GOOSE", -4)
        kg._daily_refresh_animals(farm, 0)
        first = farm["tiles"][0][0]
        self.assertEqual(first.get("animal"), "GOOSE")
        self.assertEqual(first.get("yield_units"), 1)
        self.assertEqual(first.get("consecutive_unfed"), 1)
        kg._daily_refresh_animals(farm, 1)
        self.assertEqual(farm["tiles"][0][0], {"kind": "COOP"})


if __name__ == "__main__":
    unittest.main()

