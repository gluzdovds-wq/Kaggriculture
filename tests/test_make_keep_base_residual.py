import unittest

from tools.make_keep_base_residual import render


class KeepBaseResidualTests(unittest.TestCase):
    def test_renders_only_idle_water_override(self):
        generated = render(
            "def agent(obs, configuration=None):\n"
            "    return {'farmer':['PASS'],'hands':[],'market':[['HIRE']]}\n",
            start=360,
            stop=600,
            max_per_turn=1,
            repay_harvest=False,
            label="test",
        )
        namespace = {}
        exec(compile(generated, "generated.py", "exec"), namespace)
        obs = {
            "step": 360,
            "player": 0,
            "farms": [{
                "farmer": [0, 0],
                "hands": [],
                "tiles": [[{
                    "kind": "PLANT", "crop": "WHEAT", "watered_today": False,
                }]],
            }],
        }
        action = namespace["agent"](obs)
        self.assertEqual(action["farmer"], ["WATER"])
        self.assertEqual(action["market"], [["HIRE"]])
        self.assertEqual(namespace["agent"].telemetry["watered"], 1)

    def test_preserves_nonpass_and_watered_tiles(self):
        generated = render(
            "def agent(obs, configuration=None):\n"
            "    return {'farmer':['EAST'],'hands':[],'market':[]}\n",
            start=0,
            stop=720,
            max_per_turn=1,
            repay_harvest=False,
            label="test",
        )
        namespace = {}
        exec(compile(generated, "generated.py", "exec"), namespace)
        obs = {
            "step": 1,
            "player": 0,
            "farms": [{
                "farmer": [0, 0],
                "hands": [],
                "tiles": [[{
                    "kind": "PLANT", "crop": "WHEAT", "watered_today": False,
                }]],
            }],
        }
        self.assertEqual(namespace["agent"](obs)["farmer"], ["EAST"])

    def test_rejects_invalid_bounds(self):
        with self.assertRaises(ValueError):
            render(
                "def agent(obs): return {}",
                start=5,
                stop=5,
                max_per_turn=1,
                repay_harvest=False,
                label="x",
            )

    def test_repaid_water_can_harvest_only_the_prepaid_tile(self):
        generated = render(
            "def agent(obs, configuration=None):\n"
            "    op = 'PASS' if obs['step'] == 48 else 'WATER'\n"
            "    return {'farmer':[op],'hands':[],'market':[]}\n",
            start=0,
            stop=720,
            max_per_turn=1,
            repay_harvest=True,
            label="repay",
        )
        namespace = {}
        exec(compile(generated, "generated.py", "exec"), namespace)
        dry = {
            "step": 48,
            "day": 2,
            "player": 0,
            "farms": [{
                "farmer": [0, 0], "hands": [],
                "tiles": [[{
                    "kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
                    "watered_today": False, "yield_units": 2,
                }]],
            }],
        }
        self.assertEqual(namespace["agent"](dry)["farmer"], ["WATER"])
        wet = {
            **dry,
            "step": 49,
            "farms": [{
                **dry["farms"][0],
                "tiles": [[{**dry["farms"][0]["tiles"][0][0], "watered_today": True}]],
            }],
        }
        self.assertEqual(namespace["agent"](wet)["farmer"], ["HARVEST"])
        self.assertEqual(namespace["agent"].telemetry["harvest_repayments"], 1)


if __name__ == "__main__":
    unittest.main()
