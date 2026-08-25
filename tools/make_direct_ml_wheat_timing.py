"""Append a direct distilled-tree WHEAT timing residual to any base policy.

The generated policy runs only the supplied base policy.  At a public-state
checkpoint it freezes one learned yes/no decision.  If accepted, one bounded
``SELL WHEAT`` order is appended at the configured execution step, provided
the base left a market slot and enough WHEAT remains in the private shed after
its own sells.  The exact advanced quantity becomes per-seat debt and is
removed from the next base WHEAT sell(s), so the wrapper changes timing rather
than season-wide quantity.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from tools.make_ml_wheat_gate import SCHEMA, validate_model as validate_tree_model


FARM_FEATURES = (
    "money",
    "hands",
    "hires_today",
    "unlocked",
    "farmer_x",
    "farmer_y",
    "hands_x_mean",
    "hands_y_mean",
    "animal_cow",
    "animal_goose",
    "animal_sheep",
    "crop_carrot",
    "crop_melon",
    "crop_strawberry",
    "crop_tomato",
    "crop_wheat",
    "kind_coop",
    "kind_pasture",
    "kind_plant",
    "kind_weed",
    "unfed",
    "unwatered",
    "yield_tiles",
)
MARKET_ITEMS = (
    "CARROT",
    "EGG",
    "FERTILIZER",
    "MELON",
    "MILK",
    "STRAWBERRY",
    "TOMATO",
    "WHEAT",
    "WOOL",
)
SHOP_NAMES = (
    "BAKERY",
    "PIZZA_SHOP",
    "BRUNCH_SPOT",
    "YARN_STORE",
    "ICE_CREAM_SHOP",
    "PET_CAFE",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
)
SUPPORTED_FEATURES = {
    "x_step",
    "x_day",
    "x_hour",
    *(f"x_{perspective}_{name}" for perspective in ("focus", "other", "delta") for name in FARM_FEATURES),
    *(f"x_market_inventory_{item.lower()}" for item in MARKET_ITEMS),
    *(f"x_market_price_{item.lower()}" for item in MARKET_ITEMS),
    *(f"x_shop_{shop.lower()}" for shop in SHOP_NAMES),
}


def validate_model(model: dict) -> dict:
    """Validate the shared distilled-tree schema plus direct-wrapper safety."""

    normalized = validate_tree_model(model)
    unsupported = sorted(set(normalized["feature_names"]) - SUPPORTED_FEATURES)
    if unsupported:
        raise ValueError(f"unsupported public feature(s): {', '.join(unsupported)}")
    for value in normalized["thresholds"] + normalized["positive_probabilities"]:
        if not math.isfinite(float(value)):
            raise ValueError("tree thresholds and probabilities must be finite")

    bounds = normalized.get("feature_bounds", {}) or {}
    if not isinstance(bounds, dict):
        raise ValueError("feature_bounds must be an object")
    clean_bounds: dict[str, list[float]] = {}
    for raw_name, raw_pair in bounds.items():
        name = str(raw_name)
        if name not in normalized["feature_names"]:
            raise ValueError("feature_bounds keys must occur in feature_names")
        if not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2:
            raise ValueError("each feature bound must be [minimum, maximum]")
        lower, upper = map(float, raw_pair)
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            raise ValueError("feature bounds must be finite and ordered")
        clean_bounds[name] = [lower, upper]
    normalized["feature_bounds"] = clean_bounds

    # Reject cycles up front.  The generated evaluator also has a traversal
    # bound so a corrupted runtime constant cannot hang an official episode.
    left = normalized["children_left"]
    right = normalized["children_right"]
    visiting: set[int] = set()
    visited: set[int] = set()

    def walk(node: int) -> None:
        if node in visiting:
            raise ValueError("tree must be acyclic")
        if node in visited:
            return
        visiting.add(node)
        if left[node] != -2:
            walk(left[node])
            walk(right[node])
        visiting.remove(node)
        visited.add(node)

    walk(0)
    return normalized


TEMPLATE = r'''

# Direct ML-gated, quantity-conserving WHEAT timing residual.  The base policy
# is the only policy executed; no teacher/candidate policy is embedded.
import copy as _dmwt_copy
import inspect as _dmwt_inspect
import math as _dmwt_math

_DMWT_INNER_AGENT = agent
_DMWT_MODEL = __DMWT_MODEL__
_DMWT_EXECUTE_STEP = __DMWT_EXECUTE_STEP__
_DMWT_CAP = __DMWT_CAP__
_DMWT_LABEL = __DMWT_LABEL__
_DMWT_MAX_MARKET_ORDERS = 10
_DMWT_LAST = {0: -1, 1: -1}
_DMWT_DECISION = {0: None, 1: None}
_DMWT_DEBT = {0: 0, 1: 0}
_DMWT_STATS = {
    0: {"resets": 0, "decisions": 0, "decision_errors": 0, "interventions": 0, "advanced": 0, "repaid": 0},
    1: {"resets": 0, "decisions": 0, "decision_errors": 0, "interventions": 0, "advanced": 0, "repaid": 0},
}
_DMWT_BASE_TELEMETRY = getattr(_DMWT_INNER_AGENT, "telemetry", None)
_DMWT_TELEMETRY = {
    "label": _DMWT_LABEL,
    "checkpoint_step": int(_DMWT_MODEL["checkpoint_step"]),
    "execute_step": _DMWT_EXECUTE_STEP,
    "sell_cap": _DMWT_CAP,
    "model_schema": _DMWT_MODEL["schema"],
    "model_feature_names": list(_DMWT_MODEL["feature_names"]),
    "decision": _DMWT_DECISION,
    "debt": _DMWT_DEBT,
    "stats": _DMWT_STATS,
    "executed": 0,
    "market_advanced": {"WHEAT": 0},
    "market_repaid": {"WHEAT": 0},
}


def _dmwt_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _dmwt_number(value):
    result = float(value)
    if not _dmwt_math.isfinite(result):
        raise ValueError("non-finite public feature")
    return result


def _dmwt_farm(farm):
    if farm is None:
        raise ValueError("missing farm")
    farmer = list(_dmwt_get(farm, "farmer", []) or [])
    if len(farmer) < 2:
        raise ValueError("missing farmer position")
    hands = list(_dmwt_get(farm, "hands", []) or [])
    for position in hands:
        if position is None or len(position) < 2:
            raise ValueError("malformed hand position")
    quadrants = _dmwt_get(farm, "unlocked_quadrants", None)
    tiles = _dmwt_get(farm, "tiles", None)
    if quadrants is None or tiles is None:
        raise ValueError("missing public farm state")
    values = {
        "money": _dmwt_number(_dmwt_get(farm, "money", None)),
        "hands": float(len(hands)),
        "hires_today": _dmwt_number(_dmwt_get(farm, "hires_today", 0) or 0),
        "unlocked": float(len(list(quadrants))),
        "farmer_x": _dmwt_number(farmer[0]),
        "farmer_y": _dmwt_number(farmer[1]),
        "hands_x_mean": (sum(_dmwt_number(row[0]) for row in hands) / len(hands) if hands else -1.0),
        "hands_y_mean": (sum(_dmwt_number(row[1]) for row in hands) / len(hands) if hands else -1.0),
    }
    counts = {
        "animal_cow": 0.0, "animal_goose": 0.0, "animal_sheep": 0.0,
        "crop_carrot": 0.0, "crop_melon": 0.0, "crop_strawberry": 0.0,
        "crop_tomato": 0.0, "crop_wheat": 0.0,
        "kind_coop": 0.0, "kind_pasture": 0.0, "kind_plant": 0.0, "kind_weed": 0.0,
        "unfed": 0.0, "unwatered": 0.0, "yield_tiles": 0.0,
    }
    for row in list(tiles):
        if row is None:
            raise ValueError("malformed tile row")
        for tile in list(row):
            if tile is None or tile == "LOCKED":
                continue
            if not isinstance(tile, dict):
                raise ValueError("malformed tile")
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


def _dmwt_features(obs, seat):
    farms = list(_dmwt_get(obs, "farms", []) or [])
    if len(farms) != 2 or seat not in (0, 1):
        raise ValueError("expected exactly two public farms")
    focus = _dmwt_farm(farms[1 - seat])
    other = _dmwt_farm(farms[seat])
    step = int(_dmwt_get(obs, "step", -1))
    day = int(_dmwt_get(obs, "day", -1))
    hour = int(_dmwt_get(obs, "hour", -1))
    if not 0 <= step < 720 or not 0 <= day < 30 or not 0 <= hour < 24:
        raise ValueError("public clock is outside the season")
    if step != day * 24 + hour:
        raise ValueError("inconsistent public clock")
    result = {"x_step": float(step), "x_day": float(day), "x_hour": float(hour)}
    for name, value in focus.items():
        result["x_focus_" + name] = _dmwt_number(value)
    for name, value in other.items():
        result["x_other_" + name] = _dmwt_number(value)
    for name in set(focus) & set(other):
        result["x_delta_" + name] = _dmwt_number(focus[name] - other[name])

    market = _dmwt_get(obs, "market", None)
    inventory = _dmwt_get(market, "inventory", None)
    prices = _dmwt_get(market, "prices", None)
    if market is None or inventory is None or prices is None:
        raise ValueError("missing public market")
    for item in __DMWT_MARKET_ITEMS__:
        lower = item.lower()
        if _dmwt_get(inventory, item, None) is not None:
            result["x_market_inventory_" + lower] = _dmwt_number(_dmwt_get(inventory, item))
        if _dmwt_get(prices, item, None) is not None:
            result["x_market_price_" + lower] = _dmwt_number(_dmwt_get(prices, item))

    town = _dmwt_get(obs, "town", None)
    shops_raw = _dmwt_get(town, "unlocked_shops", None)
    if town is None or shops_raw is None:
        raise ValueError("missing public town")
    shops = {}
    for raw in list(shops_raw):
        shop = str(raw).upper().split(".")[-1]
        shops[shop] = shops.get(shop, 0) + 1
    for shop in __DMWT_SHOP_NAMES__:
        result["x_shop_" + shop.lower()] = float(shops.get(shop, 0))
    return result


def _dmwt_predict(obs, seat):
    values = _dmwt_features(obs, seat)
    names = _DMWT_MODEL["feature_names"]
    bounds = _DMWT_MODEL.get("feature_bounds", {})
    for name in names:
        if name not in values:
            raise ValueError("required public feature is missing")
        value = _dmwt_number(values[name])
        if name in bounds and not bounds[name][0] <= value <= bounds[name][1]:
            raise ValueError("public feature is out of deployment bounds")
    node = 0
    left = _DMWT_MODEL["children_left"]
    right = _DMWT_MODEL["children_right"]
    features = _DMWT_MODEL["feature_indices"]
    thresholds = _DMWT_MODEL["thresholds"]
    for _ in range(len(left) + 1):
        if left[node] == -2:
            return _dmwt_number(_DMWT_MODEL["positive_probabilities"][node])
        value = _dmwt_number(values[names[features[node]]])
        node = left[node] if value <= thresholds[node] else right[node]
    raise ValueError("invalid tree traversal")


def _dmwt_accepts_configuration(policy):
    try:
        positional = [
            parameter for parameter in _dmwt_inspect.signature(policy).parameters.values()
            if parameter.kind in (
                _dmwt_inspect.Parameter.POSITIONAL_ONLY,
                _dmwt_inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        return len(positional) >= 2
    except Exception:
        return True


_DMWT_INNER_ACCEPTS_CONFIGURATION = _dmwt_accepts_configuration(_DMWT_INNER_AGENT)


def _dmwt_call_inner(obs, configuration):
    if _DMWT_INNER_ACCEPTS_CONFIGURATION:
        return _DMWT_INNER_AGENT(obs, configuration)
    return _DMWT_INNER_AGENT(obs)


def _dmwt_seat_and_step(obs):
    seat = int(_dmwt_get(obs, "player", -1))
    step = int(_dmwt_get(obs, "step", -1))
    if seat not in (0, 1) or not 0 <= step < 720:
        raise ValueError("invalid player or step")
    return seat, step


def _dmwt_reset(seat):
    _DMWT_DECISION[seat] = None
    _DMWT_DEBT[seat] = 0
    resets = _DMWT_STATS[seat].get("resets", 0) + 1
    _DMWT_STATS[seat].clear()
    _DMWT_STATS[seat].update({
        "resets": resets,
        "decisions": 0,
        "decision_errors": 0,
        "interventions": 0,
        "advanced": 0,
        "repaid": 0,
    })
    _dmwt_sync_telemetry()


def _dmwt_sync_telemetry():
    _DMWT_TELEMETRY["executed"] = sum(row["interventions"] for row in _DMWT_STATS.values())
    _DMWT_TELEMETRY["market_advanced"]["WHEAT"] = sum(row["advanced"] for row in _DMWT_STATS.values())
    _DMWT_TELEMETRY["market_repaid"]["WHEAT"] = sum(row["repaid"] for row in _DMWT_STATS.values())


def _dmwt_requested_wheat_pickup(action):
    if not isinstance(action, dict):
        return 0
    fields = [action.get("farmer"), *list(action.get("hands", []) or [])]
    requested = 0
    for raw in fields:
        if (
            isinstance(raw, (list, tuple))
            and len(raw) >= 2
            and str(raw[0]).upper() == "PICKUP"
            and str(raw[1]).upper() == "WHEAT"
        ):
            try:
                quantity = int(raw[2]) if len(raw) >= 3 else 1
            except Exception:
                quantity = 0
            requested += max(0, quantity)
    return requested


def _dmwt_private_shed_wheat(obs):
    private = _dmwt_get(obs, "private", None)
    shed = _dmwt_get(private, "shed", None)
    if private is None or shed is None:
        raise ValueError("missing private shed")
    return max(0, int(_dmwt_get(shed, "WHEAT", 0) or 0))


def _dmwt_repay(action, obs, seat, step):
    result = _dmwt_copy.deepcopy(action)
    if not isinstance(result, dict):
        raise ValueError("base action must be a dictionary")
    raw_market = result.get("market", []) or []
    if not isinstance(raw_market, (list, tuple)):
        raise ValueError("base market must be a sequence")
    debt = max(0, int(_DMWT_DEBT[seat]))
    if debt <= 0:
        result["market"] = list(raw_market)
        return result

    # Field actions execute before market actions.  Requested WHEAT pickups are
    # therefore subtracted even if their context might make them invalid.
    # DROP/PLACE and BUY_PRODUCT additions are deliberately ignored, producing
    # a conservative lower bound.  Repay only when *all* processed base WHEAT
    # sells fit inside that lower bound; otherwise a later sell could consume
    # stock freed by an earlier reduction and the debt would not truly shrink.
    guaranteed_wheat = max(
        0,
        _dmwt_private_shed_wheat(obs) - _dmwt_requested_wheat_pickup(result),
    )
    processed = list(raw_market[:_DMWT_MAX_MARKET_ORDERS])
    requested_total = _dmwt_base_wheat_sells(processed)
    if requested_total > guaranteed_wheat:
        _DMWT_STATS[seat]["repay_blocked_unconfirmed_stock"] = _DMWT_STATS[seat].get("repay_blocked_unconfirmed_stock", 0) + 1
        result["market"] = list(raw_market)
        return result

    market = []
    repaid = 0
    for index, raw in enumerate(raw_market):
        order = list(raw) if isinstance(raw, (list, tuple)) else raw
        if (
            index < _DMWT_MAX_MARKET_ORDERS
            and debt > 0
            and isinstance(order, list)
            and len(order) >= 3
            and str(order[0]).upper() == "SELL"
            and str(order[1]).upper() == "WHEAT"
        ):
            quantity = max(0, int(order[2] or 0))
            reduction = min(quantity, debt)
            quantity -= reduction
            debt -= reduction
            repaid += reduction
            if quantity <= 0:
                continue
            order[2] = quantity
        market.append(order)
    _DMWT_DEBT[seat] = debt
    if repaid:
        _DMWT_STATS[seat]["repaid"] += repaid
        _DMWT_STATS[seat]["last_repay_step"] = step
        _dmwt_sync_telemetry()
    result["market"] = market
    return result


def _dmwt_base_wheat_sells(market):
    quantity = 0
    for raw in market:
        if (
            isinstance(raw, (list, tuple))
            and len(raw) >= 3
            and str(raw[0]).upper() == "SELL"
            and str(raw[1]).upper() == "WHEAT"
        ):
            quantity += max(0, int(raw[2] or 0))
    return quantity


def _dmwt_advance(action, obs, seat, step):
    if step != _DMWT_EXECUTE_STEP:
        return action
    decision = _DMWT_DECISION[seat]
    if not decision or not decision["accepted"]:
        return action
    if _dmwt_requested_wheat_pickup(action) > 0:
        _DMWT_STATS[seat]["blocked_wheat_pickup"] = _DMWT_STATS[seat].get("blocked_wheat_pickup", 0) + 1
        return action
    market = list(action.get("market", []) or [])
    if len(market) >= _DMWT_MAX_MARKET_ORDERS:
        _DMWT_STATS[seat]["blocked_market_full"] = _DMWT_STATS[seat].get("blocked_market_full", 0) + 1
        return action
    shed_wheat = _dmwt_private_shed_wheat(obs)
    available = max(0, shed_wheat - _dmwt_base_wheat_sells(market))
    quantity = min(_DMWT_CAP, available)
    if quantity <= 0:
        _DMWT_STATS[seat]["blocked_no_wheat"] = _DMWT_STATS[seat].get("blocked_no_wheat", 0) + 1
        return action
    market.append(["SELL", "WHEAT", quantity])
    action["market"] = market
    _DMWT_DEBT[seat] += quantity
    _DMWT_STATS[seat]["interventions"] += 1
    _DMWT_STATS[seat]["advanced"] += quantity
    _DMWT_STATS[seat]["last_advance_step"] = step
    _dmwt_sync_telemetry()
    return action


def agent(obs, configuration=None):
    try:
        seat, step = _dmwt_seat_and_step(obs)
    except Exception:
        return _dmwt_call_inner(obs, configuration)
    if step == 0 or step <= _DMWT_LAST[seat]:
        _dmwt_reset(seat)
    _DMWT_LAST[seat] = step
    if step == int(_DMWT_MODEL["checkpoint_step"]):
        try:
            probability = _dmwt_predict(obs, seat)
            _DMWT_DECISION[seat] = {
                "probability": probability,
                "accepted": probability >= float(_DMWT_MODEL["decision_threshold"]),
                "error": False,
            }
            _DMWT_STATS[seat]["decisions"] += 1
        except Exception:
            _DMWT_DECISION[seat] = {"probability": 0.0, "accepted": False, "error": True}
            _DMWT_STATS[seat]["decision_errors"] += 1
    base_action = _dmwt_call_inner(obs, configuration)
    try:
        result = _dmwt_repay(base_action, obs, seat, step)
        return _dmwt_advance(result, obs, seat, step)
    except Exception:
        _DMWT_STATS[seat]["runtime_errors"] = _DMWT_STATS[seat].get("runtime_errors", 0) + 1
        return base_action


agent.telemetry = _DMWT_TELEMETRY
__version__ = "direct-ml-wheat-timing-" + _DMWT_LABEL
direct_ml_wheat_timing_kaggle_entrypoint = agent
'''


def render_variant(
    source: str,
    model: dict,
    *,
    execute_step: int = 119,
    cap: int = 1,
    label: str,
) -> str:
    if "def agent(" not in source:
        raise ValueError("source does not define agent")
    if not label.strip():
        raise ValueError("label must be non-empty")
    normalized = validate_model(model)
    if not int(normalized["checkpoint_step"]) <= execute_step < 720:
        raise ValueError("execute_step must be at or after checkpoint and before 720")
    if not 1 <= cap <= 100:
        raise ValueError("cap must be in [1, 100]")
    appendix = (
        TEMPLATE.replace("__DMWT_MODEL__", repr(normalized))
        .replace("__DMWT_EXECUTE_STEP__", repr(int(execute_step)))
        .replace("__DMWT_CAP__", repr(int(cap)))
        .replace("__DMWT_LABEL__", repr(label.strip()))
        .replace("__DMWT_MARKET_ITEMS__", repr(MARKET_ITEMS))
        .replace("__DMWT_SHOP_NAMES__", repr(SHOP_NAMES))
    )
    generated = source.rstrip() + "\n" + appendix
    compile(generated, f"direct_ml_wheat_timing_{label}.py", "exec")
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--execute-step", type=int, default=119)
    parser.add_argument("--cap", type=int, default=1)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    try:
        generated = render_variant(
            args.source.read_text(encoding="utf-8"),
            json.loads(args.model.read_text(encoding="utf-8")),
            execute_step=args.execute_step,
            cap=args.cap,
            label=args.label,
        )
    except (ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
