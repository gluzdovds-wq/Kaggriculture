import json
from pathlib import Path
import random
import unittest

from tools.generate_pairwise_rank_header import collapsed_ridge, render
from tools.generate_phase_value_header import render as render_phase_value


ROOT = Path(__file__).parents[1]
MODEL_PATH = ROOT / "rl" / "frozen_pairwise_rank_e105.json"
HEADER_PATH = ROOT / "fast_sim" / "frozen_pairwise_rank_e105.hpp"
PHASE_MODEL_PATH = ROOT / "rl" / "frozen_phase_value_e104.json"
PHASE_HEADER_PATH = ROOT / "fast_sim" / "frozen_phase_value_e104.hpp"


class NativeLeafFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def test_generated_header_is_current_and_feature_complete(self):
        expected = render(self.model, Path("rl/frozen_pairwise_rank_e105.json"))
        self.assertEqual(HEADER_PATH.read_text(encoding="utf-8"), expected)
        self.assertEqual(len(self.model["feature_names"]), 119)
        for index, name in enumerate(self.model["feature_names"]):
            self.assertIn(f'    "{name}"', expected)
            self.assertIn(f" = {index}", expected)

    def test_collapsed_native_ridge_matches_serialized_prediction(self):
        rng = random.Random(20260822)
        width = len(self.model["feature_names"])
        for phase in self.model["phases"].values():
            rank = phase["rank"]
            ridge = rank["ridge"]
            intercept, raw = collapsed_ridge(rank, width)
            for _ in range(8):
                values = [rng.uniform(-20000.0, 20000.0) for _ in range(width)]
                expected = float(ridge["target_center"])
                for index, weight in zip(
                    ridge["active_indices"], ridge["weights"]
                ):
                    expected += (
                        (values[index] - ridge["center"][index])
                        / ridge["scale"][index]
                        * weight
                    )
                actual = intercept + sum(
                    value * weight for value, weight in zip(values, raw)
                )
                self.assertAlmostEqual(actual, expected, places=10)

    def test_generated_n74_value_header_is_current(self):
        model = json.loads(PHASE_MODEL_PATH.read_text(encoding="utf-8"))
        expected = render_phase_value(
            model, Path("rl/frozen_phase_value_e104.json")
        )
        self.assertEqual(PHASE_HEADER_PATH.read_text(encoding="utf-8"), expected)
        self.assertEqual(model["feature_names"], self.model["feature_names"])

    def test_collapsed_n74_prediction_matches_python_formula(self):
        model = json.loads(PHASE_MODEL_PATH.read_text(encoding="utf-8"))
        rng = random.Random(20260823)
        width = len(model["feature_names"])
        money_index = model["feature_names"].index("money_delta")
        legal_index = model["feature_names"].index("legal_marked_margin")
        for phase in model["phases"].values():
            regression = phase["targets"]["final_margin"]
            ridge = regression["ridge"]
            intercept, raw = collapsed_ridge(regression, width)
            for _ in range(8):
                values = [rng.uniform(-20000.0, 20000.0) for _ in range(width)]
                residual = float(ridge["target_center"])
                for index, weight in zip(
                    ridge["active_indices"], ridge["weights"]
                ):
                    residual += (
                        (values[index] - ridge["center"][index])
                        / ridge["scale"][index]
                        * weight
                    )
                raw_prediction = values[legal_index] + residual
                fallback = (
                    values[money_index]
                    if regression["fallback"] == "current_money"
                    else 0.0
                )
                expected = fallback + float(regression["blend"]) * (
                    raw_prediction - fallback
                )
                native_residual = intercept + sum(
                    value * weight for value, weight in zip(values, raw)
                )
                native_raw = values[legal_index] + native_residual
                actual = fallback + float(regression["blend"]) * (
                    native_raw - fallback
                )
                self.assertAlmostEqual(actual, expected, delta=1e-7)

    def test_native_extractor_declares_inference_contract(self):
        source = (ROOT / "fast_sim" / "legal_leaf_features.hpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("Only the controlled farm's private", source)
        self.assertIn("const Farm& own = sim.st.farms[seat]", source)
        self.assertIn("const Farm& opponent = sim.st.farms[1 - seat]", source)
        self.assertNotIn("opponent.shed", source)
        self.assertNotIn("opponent.seeds", source)
        self.assertNotIn("opponent.inv", source)


if __name__ == "__main__":
    unittest.main()
