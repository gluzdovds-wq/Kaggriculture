from rl.build_public_replay_ml_dataset import future_gate_labels, public_features


def test_public_features_exclude_private_state():
    observation = {
        "day": 3,
        "hour": 0,
        "farms": [
            {"money": 100, "farmer": [0, 0], "hands": [], "tiles": [], "unlocked_quadrants": ["NW"]},
            {"money": 90, "farmer": [1, 1], "hands": [], "tiles": [], "unlocked_quadrants": ["NW"]},
        ],
        "private": {"shed": {"MILK": 999}, "seeds": {"WHEAT": 999}},
        "market": {"inventory": {"MILK": 10}, "prices": {"MILK": 50}},
        "town": {"unlocked_shops": ["ICE_CREAM_SHOP"]},
    }
    features = public_features(observation, 1)
    assert features["x_focus_money"] == 90
    assert features["x_other_money"] == 100
    assert features["x_shop_ice_cream_shop"] == 1
    assert all("shed" not in name and "seed" not in name for name in features)


def test_future_gate_labels_are_factorized():
    steps = [
        [{}, {}],
        [
            {"action": {"market": [["BUY_LAND"], ["BUY_ANIMAL", "COW", 2]]}},
            {},
        ],
        [
            {"action": {"market": [["SELL", "FERTILIZER", 3], ["SELL", "MILK", 4]]}},
            {},
        ],
    ]
    labels = future_gate_labels(steps, 0, 0, 24)
    assert labels["y_buy_land"] == 1
    assert labels["y_buy_animal"] == 1
    assert labels["y_animal_type"] == "COW"
    assert labels["y_sell_fertilizer"] == 1
    assert labels["y_sell_premium"] == 1
