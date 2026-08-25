import json

import pytest

from tools.make_ml_wheat_gate import SCHEMA, render_variant, validate_model


def leaf_model(probability: float) -> dict:
    return {
        "schema": SCHEMA,
        "checkpoint_step": 0,
        "decision_threshold": 0.7,
        "feature_names": ["x_focus_money"],
        "children_left": [-2],
        "children_right": [-2],
        "feature_indices": [-2],
        "thresholds": [-2.0],
        "positive_probabilities": [probability],
    }


DUMMY_SOURCE = r'''
_SPA_OPPONENT_ANIMALS = {"COW": 3, "SHEEP": 2}
_SPA_SELL_CAP = 8
_SPA_TELEMETRY = {}

def agent(obs, configuration=None):
    return {"market": [["SELL", "WHEAT", 1]] if not _SPA_OPPONENT_ANIMALS else []}
'''


def observation():
    empty = [[None for _ in range(10)] for _ in range(10)]
    return {
        "day": 0,
        "hour": 0,
        "player": 0,
        "farms": [
            {"money": 1, "tiles": empty, "farmer": [0, 0]},
            {"money": 2, "tiles": empty, "farmer": [0, 0]},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
    }


def load_generated(model: dict, mode: str = "ml_only") -> dict:
    source = render_variant(DUMMY_SOURCE, model, mode=mode, label="test")
    namespace: dict = {}
    exec(compile(source, "generated_ml_gate.py", "exec"), namespace)
    return namespace


def test_positive_leaf_enables_existing_residual():
    namespace = load_generated(leaf_model(0.9))
    assert namespace["agent"](observation())["market"] == [["SELL", "WHEAT", 1]]
    assert namespace["_SPA_TELEMETRY"]["ml_gate_learned_active"] is True


def test_negative_leaf_keeps_base():
    namespace = load_generated(leaf_model(0.1))
    assert namespace["agent"](observation())["market"] == []
    assert namespace["_SPA_TELEMETRY"]["ml_gate_learned_active"] is False


def test_malformed_observation_falls_back_without_raising():
    namespace = load_generated(leaf_model(0.9))
    result = namespace["agent"](
        {"day": 0, "hour": 0, "player": 0, "farms": []}
    )
    assert result["market"] == []
    assert namespace["_SPA_TELEMETRY"]["ml_gate_error"] is True


def test_invalid_probability_is_rejected():
    model = leaf_model(1.5)
    with pytest.raises(ValueError, match="probabilities"):
        validate_model(model)


def test_outside_cap_is_bounded():
    with pytest.raises(ValueError, match="outside_cap"):
        render_variant(DUMMY_SOURCE, leaf_model(1.0), mode="union", label="x", outside_cap=9)


def test_model_is_json_round_trip_safe():
    assert validate_model(json.loads(json.dumps(leaf_model(0.75))))[
        "positive_probabilities"
    ] == [0.75]
