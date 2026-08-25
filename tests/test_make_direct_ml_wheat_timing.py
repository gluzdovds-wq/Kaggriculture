import copy

import pytest

from tools.make_direct_ml_wheat_timing import render_variant, validate_model
from tools.make_ml_wheat_gate import SCHEMA


BASE_ONE_ARG = r'''
import copy

def agent(obs):
    return copy.deepcopy(obs.get("_base_action", {"farmer": ["PASS"], "hands": [], "market": []}))
'''

BASE_TWO_ARGS = r'''
import copy

def agent(obs, configuration=None):
    result = copy.deepcopy(obs.get("_base_action", {"farmer": ["PASS"], "hands": [], "market": []}))
    result["configuration_seen"] = None if configuration is None else configuration.get("token")
    return result
'''


def leaf_model(probability=1.0, *, checkpoint=2, bounds=None):
    model = {
        "schema": SCHEMA,
        "checkpoint_step": checkpoint,
        "decision_threshold": 0.5,
        "feature_names": ["x_focus_money"],
        "children_left": [-2],
        "children_right": [-2],
        "feature_indices": [-2],
        "thresholds": [-2.0],
        "positive_probabilities": [probability],
    }
    if bounds is not None:
        model["feature_bounds"] = {"x_focus_money": list(bounds)}
    return model


def observation(step, *, seat=0, shed_wheat=5, base_market=None):
    tiles = [[None for _ in range(10)] for _ in range(10)]
    farms = [
        {
            "money": 100,
            "tiles": copy.deepcopy(tiles),
            "farmer": [0, 0],
            "hands": [],
            "hires_today": 0,
            "unlocked_quadrants": ["NW"],
        },
        {
            "money": 200,
            "tiles": copy.deepcopy(tiles),
            "farmer": [1, 1],
            "hands": [],
            "hires_today": 0,
            "unlocked_quadrants": ["NW"],
        },
    ]
    return {
        "step": step,
        "day": step // 24,
        "hour": step % 24,
        "player": seat,
        "farms": farms,
        "private": {"shed": {"WHEAT": shed_wheat}},
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "_base_action": {
            "farmer": ["PASS"],
            "hands": [],
            "market": copy.deepcopy(base_market or []),
        },
    }


def load_generated(model=None, *, source=BASE_ONE_ARG, execute_step=3, cap=1):
    generated = render_variant(
        source,
        leaf_model() if model is None else model,
        execute_step=execute_step,
        cap=cap,
        label="unit",
    )
    namespace = {}
    exec(compile(generated, "generated_direct_ml_timing.py", "exec"), namespace)
    return namespace


def freeze(namespace, *, seat=0, obs=None):
    namespace["agent"](observation(2, seat=seat) if obs is None else obs)


def test_positive_gate_advances_then_repays_exact_quantity():
    namespace = load_generated(cap=1)
    freeze(namespace)

    advanced = namespace["agent"](observation(3, shed_wheat=3))
    assert advanced["market"] == [["SELL", "WHEAT", 1]]
    assert namespace["_DMWT_DEBT"][0] == 1
    assert namespace["_DMWT_TELEMETRY"]["market_advanced"]["WHEAT"] == 1
    assert namespace["_DMWT_TELEMETRY"]["executed"] == 1

    repaid = namespace["agent"](
        observation(4, base_market=[["SELL", "WHEAT", 3], ["SELL", "CARROT", 2]])
    )
    assert repaid["market"] == [["SELL", "WHEAT", 2], ["SELL", "CARROT", 2]]
    assert namespace["_DMWT_DEBT"][0] == 0
    assert namespace["_DMWT_TELEMETRY"]["market_repaid"]["WHEAT"] == 1


def test_debt_uses_nearest_subsequent_sells_across_orders_and_turns():
    namespace = load_generated(cap=3)
    freeze(namespace)
    advanced = namespace["agent"](observation(3, shed_wheat=5))
    assert advanced["market"] == [["SELL", "WHEAT", 3]]

    first = namespace["agent"](
        observation(4, base_market=[["SELL", "WHEAT", 1], ["SELL", "WOOL", 4]])
    )
    assert first["market"] == [["SELL", "WOOL", 4]]
    assert namespace["_DMWT_DEBT"][0] == 2
    second = namespace["agent"](
        observation(5, base_market=[["SELL", "WHEAT", 1], ["SELL", "WHEAT", 3]])
    )
    assert second["market"] == [["SELL", "WHEAT", 2]]
    assert namespace["_DMWT_DEBT"][0] == 0


def test_gate_never_oversells_private_shed_after_base_sells():
    namespace = load_generated(cap=3)
    freeze(namespace)
    no_room = namespace["agent"](
        observation(3, shed_wheat=2, base_market=[["SELL", "WHEAT", 2]])
    )
    assert no_room["market"] == [["SELL", "WHEAT", 2]]
    assert namespace["_DMWT_DEBT"][0] == 0


def test_same_turn_wheat_pickup_blocks_intervention():
    namespace = load_generated(cap=3)
    freeze(namespace)
    obs = observation(3, shed_wheat=5)
    obs["_base_action"]["farmer"] = ["PICKUP", "WHEAT"]
    result = namespace["agent"](obs)
    assert result["market"] == []
    assert namespace["_DMWT_DEBT"][0] == 0
    assert namespace["_DMWT_STATS"][0]["blocked_wheat_pickup"] == 1


def test_debt_carries_when_base_sell_is_not_guaranteed_to_execute():
    namespace = load_generated(cap=1)
    freeze(namespace)
    namespace["agent"](observation(3, shed_wheat=2))
    assert namespace["_DMWT_DEBT"][0] == 1

    # With only one unit in the shed, requesting two does not guarantee that
    # lowering the request by one lowers the actually executed quantity.
    uncertain = namespace["agent"](
        observation(4, shed_wheat=1, base_market=[["SELL", "WHEAT", 2]])
    )
    assert uncertain["market"] == [["SELL", "WHEAT", 2]]
    assert namespace["_DMWT_DEBT"][0] == 1
    assert namespace["_DMWT_STATS"][0]["repay_blocked_unconfirmed_stock"] == 1

    # The next fully-backed request is safe and is the nearest confirmed sale.
    confirmed = namespace["agent"](
        observation(5, shed_wheat=2, base_market=[["SELL", "WHEAT", 2]])
    )
    assert confirmed["market"] == [["SELL", "WHEAT", 1]]
    assert namespace["_DMWT_DEBT"][0] == 0


def test_full_market_and_negative_gate_keep_base_action():
    full = [["HIRE"] for _ in range(10)]
    positive = load_generated()
    freeze(positive)
    assert positive["agent"](observation(3, base_market=full))["market"] == full
    assert positive["_DMWT_DEBT"][0] == 0

    negative = load_generated(leaf_model(0.0))
    freeze(negative)
    assert negative["agent"](observation(3))["market"] == []
    assert negative["_DMWT_DECISION"][0]["accepted"] is False


def test_malformed_and_out_of_bounds_checkpoint_fail_closed():
    malformed = load_generated()
    bad = observation(2)
    bad["farms"] = []
    freeze(malformed, obs=bad)
    assert malformed["_DMWT_DECISION"][0]["error"] is True
    assert malformed["agent"](observation(3))["market"] == []

    bounded = load_generated(leaf_model(1.0, bounds=(0, 150)))
    out_of_bounds = observation(2)
    out_of_bounds["farms"][1]["money"] = 200
    freeze(bounded, obs=out_of_bounds)
    assert bounded["_DMWT_DECISION"][0]["error"] is True
    assert bounded["agent"](observation(3))["market"] == []


def test_reset_and_debt_are_isolated_per_seat():
    namespace = load_generated()
    freeze(namespace, seat=0)
    namespace["agent"](observation(3, seat=0))
    freeze(namespace, seat=1)
    namespace["agent"](observation(3, seat=1))
    assert namespace["_DMWT_DEBT"] == {0: 1, 1: 1}

    namespace["agent"](observation(0, seat=0))
    assert namespace["_DMWT_DEBT"] == {0: 0, 1: 1}
    assert namespace["_DMWT_DECISION"][0] is None
    assert namespace["_DMWT_DECISION"][1]["accepted"] is True


def test_generated_agent_supports_one_and_two_argument_bases():
    one_arg = load_generated(source=BASE_ONE_ARG)
    assert one_arg["agent"](observation(0), {"token": 7})["market"] == []

    two_args = load_generated(source=BASE_TWO_ARGS)
    assert two_args["agent"](observation(0), {"token": 7})["configuration_seen"] == 7


def test_invalid_tree_feature_cycle_and_execution_options_are_rejected():
    unsupported = leaf_model()
    unsupported["feature_names"] = ["private_opponent_secret"]
    with pytest.raises(ValueError, match="unsupported public"):
        validate_model(unsupported)

    cycle = leaf_model()
    cycle.update(
        children_left=[0],
        children_right=[0],
        feature_indices=[0],
        thresholds=[1.0],
    )
    with pytest.raises(ValueError, match="acyclic"):
        validate_model(cycle)

    with pytest.raises(ValueError, match="at or after checkpoint"):
        render_variant(BASE_ONE_ARG, leaf_model(), execute_step=1, cap=1, label="bad")
    with pytest.raises(ValueError, match="cap"):
        render_variant(BASE_ONE_ARG, leaf_model(), execute_step=3, cap=0, label="bad")
