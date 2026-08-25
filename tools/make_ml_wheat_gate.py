"""Append a distilled public-state ML gate to an S11-style market residual.

The wrapped policy remains the source policy.  The learned tree can only decide
whether its already quantity-conserving WHEAT timing residual is enabled; it
cannot emit a new market or field action.  The source must expose the
``_SPA_OPPONENT_ANIMALS`` gate used by ``make_shadow_policy_audit.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCHEMA = "kaggriculture-distilled-wheat-gate-v1"
MODES = ("union", "intersection", "ml_only")
LEAF = -2


def validate_model(model: dict) -> dict:
    if model.get("schema") != SCHEMA:
        raise ValueError(f"model schema must be {SCHEMA!r}")
    checkpoint_step = int(model.get("checkpoint_step", -1))
    if not 0 <= checkpoint_step < 720:
        raise ValueError("checkpoint_step must be in [0, 720)")
    decision_threshold = float(model.get("decision_threshold", -1.0))
    if not 0.0 <= decision_threshold <= 1.0:
        raise ValueError("decision_threshold must be in [0, 1]")
    feature_names = [str(name) for name in model.get("feature_names", [])]
    if not feature_names or len(feature_names) != len(set(feature_names)):
        raise ValueError("feature_names must be non-empty and unique")
    arrays = {
        name: list(model.get(name, []))
        for name in (
            "children_left",
            "children_right",
            "feature_indices",
            "thresholds",
            "positive_probabilities",
        )
    }
    widths = {len(values) for values in arrays.values()}
    if len(widths) != 1 or not widths or next(iter(widths)) < 1:
        raise ValueError("tree arrays must have one shared non-zero width")
    width = next(iter(widths))
    for node in range(width):
        left = int(arrays["children_left"][node])
        right = int(arrays["children_right"][node])
        feature = int(arrays["feature_indices"][node])
        probability = float(arrays["positive_probabilities"][node])
        if not 0.0 <= probability <= 1.0:
            raise ValueError("positive probabilities must be in [0, 1]")
        leaf = left == right == LEAF
        if leaf:
            continue
        if not 0 <= left < width or not 0 <= right < width:
            raise ValueError("child index is outside the tree")
        if not 0 <= feature < len(feature_names):
            raise ValueError("feature index is outside feature_names")
    return {
        **model,
        "checkpoint_step": checkpoint_step,
        "decision_threshold": decision_threshold,
        "feature_names": feature_names,
        "children_left": [int(value) for value in arrays["children_left"]],
        "children_right": [int(value) for value in arrays["children_right"]],
        "feature_indices": [int(value) for value in arrays["feature_indices"]],
        "thresholds": [float(value) for value in arrays["thresholds"]],
        "positive_probabilities": [
            float(value) for value in arrays["positive_probabilities"]
        ],
    }


TEMPLATE = r'''

# Distilled public-state ML gate.  It can only enable/veto the existing
# quantity-conserving WHEAT timing residual; KEEP_BASE remains the fallback.
_MLWG_INNER_AGENT = agent
_MLWG_MODEL = __MODEL__
_MLWG_MODE = __MODE__
_MLWG_LABEL = __LABEL__
_MLWG_OUTSIDE_CAP = __OUTSIDE_CAP__
_MLWG_ORIGINAL_SIGNATURE = dict(_SPA_OPPONENT_ANIMALS)
_MLWG_ORIGINAL_CAP = int(_SPA_SELL_CAP)
_MLWG_BLOCK_SIGNATURE = {"GOOSE": 1000000000}
_MLWG_STATE = {0: None, 1: None}
_MLWG_LAST = {0: -1, 1: -1}


def _mlwg_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _mlwg_farm(farm):
    farmer = list(_mlwg_get(farm, "farmer", []) or [])
    hands = list(_mlwg_get(farm, "hands", []) or [])
    values = {
        "money": float(_mlwg_get(farm, "money", 0) or 0),
        "hands": float(len(hands)),
        "hires_today": float(_mlwg_get(farm, "hires_today", 0) or 0),
        "unlocked": float(len(_mlwg_get(farm, "unlocked_quadrants", []) or [])),
        "farmer_x": float(farmer[0] if len(farmer) > 0 else -1),
        "farmer_y": float(farmer[1] if len(farmer) > 1 else -1),
        "hands_x_mean": (
            sum(float(row[0]) for row in hands) / len(hands) if hands else -1.0
        ),
        "hands_y_mean": (
            sum(float(row[1]) for row in hands) / len(hands) if hands else -1.0
        ),
    }
    counts = {
        "animal_cow": 0.0,
        "animal_goose": 0.0,
        "animal_sheep": 0.0,
        "crop_carrot": 0.0,
        "crop_melon": 0.0,
        "crop_strawberry": 0.0,
        "crop_tomato": 0.0,
        "crop_wheat": 0.0,
        "kind_coop": 0.0,
        "kind_pasture": 0.0,
        "kind_plant": 0.0,
        "kind_weed": 0.0,
        "unfed": 0.0,
        "unwatered": 0.0,
        "yield_tiles": 0.0,
    }
    for row in list(_mlwg_get(farm, "tiles", []) or []):
        for tile in list(row or []):
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", "UNKNOWN")).lower()
            crop = str(tile.get("crop", "")).lower()
            animal = str(tile.get("animal", "")).lower()
            key = "kind_" + kind
            if key in counts:
                counts[key] += 1.0
            key = "crop_" + crop
            if crop and key in counts:
                counts[key] += 1.0
            key = "animal_" + animal
            if animal and key in counts:
                counts[key] += 1.0
            if kind == "plant" and not tile.get("watered_today", False):
                counts["unwatered"] += 1.0
            if animal and not tile.get("fed_today", False):
                counts["unfed"] += 1.0
            if int(tile.get("yield_units", 0) or 0) > 0:
                counts["yield_tiles"] += 1.0
    values.update(counts)
    return values


def _mlwg_features(obs, seat):
    farms = list(_mlwg_get(obs, "farms", []) or [])
    focus = _mlwg_farm(farms[1 - seat])
    other = _mlwg_farm(farms[seat])
    day = int(_mlwg_get(obs, "day", 0) or 0)
    hour = int(_mlwg_get(obs, "hour", 0) or 0)
    result = {"x_step": float(day * 24 + hour), "x_day": float(day), "x_hour": float(hour)}
    for name, value in focus.items():
        result["x_focus_" + name] = float(value)
    for name, value in other.items():
        result["x_other_" + name] = float(value)
    for name in set(focus) & set(other):
        result["x_delta_" + name] = float(focus[name] - other[name])
    market = _mlwg_get(obs, "market", {}) or {}
    inventory = _mlwg_get(market, "inventory", {}) or {}
    prices = _mlwg_get(market, "prices", {}) or {}
    for item in ("CARROT", "EGG", "FERTILIZER", "MELON", "MILK", "STRAWBERRY", "TOMATO", "WHEAT", "WOOL"):
        lower = item.lower()
        # A missing market inventory is an invalid/incomplete observation.  Use
        # the neutral initial inventory so the learned low-inventory branch
        # cannot turn a malformed input into a false positive.
        result["x_market_inventory_" + lower] = float(_mlwg_get(inventory, item, 10000) or 10000)
        result["x_market_price_" + lower] = float(_mlwg_get(prices, item, 0) or 0)
    shops = {}
    town = _mlwg_get(obs, "town", {}) or {}
    for raw in list(_mlwg_get(town, "unlocked_shops", []) or []):
        shop = str(raw).upper().split(".")[-1]
        shops[shop] = shops.get(shop, 0) + 1
    for shop in ("BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "YARN_STORE", "ICE_CREAM_SHOP", "PET_CAFE", "SMOOTHIE_SHOP", "FARMERS_MARKET"):
        result["x_shop_" + shop.lower()] = float(shops.get(shop, 0))
    return result


def _mlwg_predict(obs, seat):
    values = _mlwg_features(obs, seat)
    node = 0
    left = _MLWG_MODEL["children_left"]
    right = _MLWG_MODEL["children_right"]
    features = _MLWG_MODEL["feature_indices"]
    thresholds = _MLWG_MODEL["thresholds"]
    names = _MLWG_MODEL["feature_names"]
    while left[node] != -2:
        value = float(values.get(names[features[node]], 0.0))
        node = left[node] if value <= thresholds[node] else right[node]
    return float(_MLWG_MODEL["positive_probabilities"][node])


def _mlwg_hard_match(obs, seat):
    if not _MLWG_ORIGINAL_SIGNATURE:
        return True
    farms = list(_mlwg_get(obs, "farms", []) or [])
    opponent = farms[1 - seat] if len(farms) == 2 else {}
    observed = {}
    for row in list(_mlwg_get(opponent, "tiles", []) or []):
        for tile in list(row or []):
            animal = str(tile.get("animal", "")).upper() if isinstance(tile, dict) else ""
            if animal:
                observed[animal] = observed.get(animal, 0) + 1
    return all(observed.get(name, 0) == count for name, count in _MLWG_ORIGINAL_SIGNATURE.items())


def _mlwg_active(obs, seat):
    hard = _mlwg_hard_match(obs, seat)
    learned = bool(_MLWG_STATE[seat] and _MLWG_STATE[seat]["accepted"])
    if _MLWG_MODE == "union":
        return hard or learned
    if _MLWG_MODE == "intersection":
        return hard and learned
    return learned


def agent(obs, configuration=None):
    global _SPA_OPPONENT_ANIMALS, _SPA_SELL_CAP
    day = int(_mlwg_get(obs, "day", 0) or 0)
    hour = int(_mlwg_get(obs, "hour", 0) or 0)
    step = day * 24 + hour
    seat = 1 if int(_mlwg_get(obs, "player", 0) or 0) == 1 else 0
    if step == 0 or step <= _MLWG_LAST[seat]:
        _MLWG_STATE[seat] = None
    _MLWG_LAST[seat] = step
    if step == int(_MLWG_MODEL["checkpoint_step"]):
        try:
            probability = _mlwg_predict(obs, seat)
            _MLWG_STATE[seat] = {
                "probability": probability,
                "accepted": probability >= float(_MLWG_MODEL["decision_threshold"]),
                "error": False,
            }
        except Exception:
            # Malformed/OOD observations must never authorize an intervention.
            _MLWG_STATE[seat] = {
                "probability": 0.0,
                "accepted": False,
                "error": True,
            }
    original = _SPA_OPPONENT_ANIMALS
    original_cap = _SPA_SELL_CAP
    hard = _mlwg_hard_match(obs, seat)
    active = _mlwg_active(obs, seat)
    _SPA_OPPONENT_ANIMALS = {} if active else _MLWG_BLOCK_SIGNATURE
    _SPA_SELL_CAP = (
        _MLWG_ORIGINAL_CAP if hard else min(_MLWG_ORIGINAL_CAP, _MLWG_OUTSIDE_CAP)
    )
    try:
        action = _MLWG_INNER_AGENT(obs, configuration)
    finally:
        _SPA_OPPONENT_ANIMALS = original
        _SPA_SELL_CAP = original_cap
    state = _MLWG_STATE[seat]
    _SPA_TELEMETRY["ml_gate_label"] = _MLWG_LABEL
    _SPA_TELEMETRY["ml_gate_mode"] = _MLWG_MODE
    _SPA_TELEMETRY["ml_gate_checkpoint_step"] = _MLWG_MODEL["checkpoint_step"]
    _SPA_TELEMETRY["ml_gate_probability"] = None if state is None else state["probability"]
    _SPA_TELEMETRY["ml_gate_learned_active"] = False if state is None else state["accepted"]
    _SPA_TELEMETRY["ml_gate_error"] = False if state is None else state["error"]
    _SPA_TELEMETRY["ml_gate_effective_active"] = active
    _SPA_TELEMETRY["ml_gate_hard_active"] = hard
    _SPA_TELEMETRY["ml_gate_effective_cap"] = (
        _MLWG_ORIGINAL_CAP if hard else min(_MLWG_ORIGINAL_CAP, _MLWG_OUTSIDE_CAP)
    )
    return action


agent.telemetry = _SPA_TELEMETRY
__version__ = "distilled-wheat-gate-" + _MLWG_LABEL
ml_wheat_gate_kaggle_entrypoint = agent
'''


def render_variant(
    source: str,
    model: dict,
    *,
    mode: str,
    label: str,
    outside_cap: int = 2,
) -> str:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if not label.strip():
        raise ValueError("label must be non-empty")
    if not 1 <= outside_cap <= 8:
        raise ValueError("outside_cap must be in [1, 8]")
    required = (
        "_SPA_OPPONENT_ANIMALS",
        "_SPA_SELL_CAP",
        "_SPA_TELEMETRY",
        "def agent(",
    )
    missing = [name for name in required if name not in source]
    if missing:
        raise ValueError(f"source is not an S11-style residual: missing {missing}")
    normalized = validate_model(model)
    appendix = (
        TEMPLATE.replace("__MODEL__", repr(normalized))
        .replace("__MODE__", repr(mode))
        .replace("__LABEL__", repr(label.strip()))
        .replace("__OUTSIDE_CAP__", repr(int(outside_cap)))
    )
    return source.rstrip() + "\n" + appendix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=MODES, default="union")
    parser.add_argument("--outside-cap", type=int, default=2)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    try:
        generated = render_variant(
            args.source.read_text(encoding="utf-8"),
            json.loads(args.model.read_text(encoding="utf-8")),
            mode=args.mode,
            label=args.label,
            outside_cap=args.outside_cap,
        )
    except (ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    compile(generated, str(args.output), "exec")
    print(args.output)


if __name__ == "__main__":
    main()
