"""Add inference-visible time, feasibility and cashflow projections to replay rows.

The original N24 corpus retained aggregate observation features but not full
tile coordinates.  This module therefore implements the exact portion of N54
that can be reconstructed without inventing hidden state: clock deadlines,
hire/land costs, end-of-day storage feasibility, known town demand and
sequential liquidation value under the official market price curve.

Future market values assume no player orders and only shops already visible in
the observation.  ``projection_complete_*`` is zero when the horizon crosses a
future random shop unlock.  Geometry ETA and candidate-conditioned simulation
must be evaluated on a newly collected full-observation corpus instead.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SHOPS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
MARKET_PARAMS = {
    "WHEAT":      {"base": 25,  "I0": 10000, "T": 400, "below_func": "sqrt",  "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base": 35,  "I0": 10000, "T": 450, "below_func": "hinge", "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base": 60,  "I0": 10000, "T": 200, "below_func": "hinge", "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": 10000, "T": 100, "below_func": "sqrt",  "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": 10000, "T": 300, "below_func": "log",   "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base": 50,  "I0": 10000, "T": 332, "below_func": "hinge", "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": 10000, "T": 122, "below_func": "sqrt",  "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": 10000, "T": 105, "below_func": "log",   "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": 10000, "T": 200, "below_func": "linear","below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}
HORIZONS = (6, 12, 24)
HINGE_GAIN = 8.0


def _shape(name: str, value: float, scale: float) -> float:
    value = max(0.0, value)
    if name == "linear":
        return value
    if name == "sq":
        return value * value
    if name == "sqrt":
        return math.sqrt(value)
    if name == "log":
        return math.log1p(value)
    if name == "log10":
        return math.log10(1.0 + value)
    if name == "hinge":
        ratio = value / scale
        return ratio + HINGE_GAIN * max(0.0, ratio - 1.0) ** 2
    raise ValueError(f"unknown market shape {name!r}")


def market_price(item: str, inventory: int) -> int:
    """Mirror the default official Kaggriculture market_price function."""
    params = MARKET_PARAMS[item]
    base = params["base"]
    initial = params["I0"]
    scale = params["T"]
    if inventory < initial:
        name = params["below_func"]
        amplitude = params["below_target"] * base / _shape(name, scale, scale)
        price = base + amplitude * _shape(name, initial - inventory, scale)
    else:
        name = params["above_func"]
        amplitude = params["above_target"] * base / _shape(name, scale, scale)
        price = base - amplitude * _shape(name, inventory - initial, scale)
    return max(1, int(round(price)))


def sequential_sale_revenue(item: str, inventory: int, quantity: int) -> int:
    """Revenue of one official SELL order with no simultaneous opponent order."""
    revenue = 0
    for _ in range(max(0, quantity)):
        price = market_price(item, inventory)
        revenue += price
        if price > 1:  # $1 sales do not add supply in the official engine.
            inventory += 1
    return revenue


def fibonacci_hire_cost(hands: int) -> int:
    a, b = 1, 1
    for _ in range(max(0, hands)):
        a, b = b, a + b
    return a


def ticks_in_projection(step: int, horizon: int, interval: int) -> int:
    """Ticks processed from the current action through the future observation."""
    return sum(1 for future_step in range(step, step + horizon) if future_step % interval == 0)


def resolved_step(features: dict[str, float]) -> int:
    """Use the shared clock because replay seat 1 may retain obs.step == 0."""
    if "day" in features and "hour" in features:
        return int(features.get("day", 0.0) or 0) * 24 + int(features.get("hour", 0.0) or 0)
    return int(features.get("step", 0.0) or 0)


def known_shop_demand(features: dict[str, float], item: str) -> int:
    demand = 0
    for shop, products in SHOPS.items():
        instances = int(features.get(f"shop_{shop.lower()}", 0.0) or 0)
        if item in products:
            demand += instances * (2 if len(products) == 1 else 1)
    return demand


def projected_inventory(features: dict[str, float], item: str, horizon: int) -> int:
    step = resolved_step(features)
    inventory = int(features.get(f"market_{item.lower()}", 0.0) or 0)
    shop_ticks = ticks_in_projection(step, horizon, 4)
    center_ticks = ticks_in_projection(step, horizon, 24)
    inventory -= shop_ticks * known_shop_demand(features, item)
    if item != "FERTILIZER":
        inventory -= center_ticks
    return inventory


def liquidation_value(features: dict[str, float], horizon: int = 0) -> int:
    total = 0
    for item in PRODUCTS:
        quantity = int(features.get(f"shed_{item.lower()}", 0.0) or 0)
        inventory = (
            projected_inventory(features, item, horizon)
            if horizon
            else int(features.get(f"market_{item.lower()}", 0.0) or 0)
        )
        total += sequential_sale_revenue(item, inventory, quantity)
    return total


def forward_features(features: dict[str, float]) -> dict[str, float]:
    step = resolved_step(features)
    day = int(features.get("day", step // 24) or 0)
    hour = int(features.get("hour", step % 24) or 0)
    hands = int(features.get("hands", 0.0) or 0)
    money = float(features.get("own_money", 0.0) or 0.0)
    unlocked = int(features.get("unlocked", 1.0) or 0)
    shed_total = max(0.0, float(features.get("shed_total", 0.0) or 0.0))
    carried_total = max(0.0, float(features.get("carried_total", 0.0) or 0.0))
    turns_today = 24 - hour
    next_unlock_step = (day // 3 + 1) * 72
    turns_to_shop_unlock = max(0, next_unlock_step - step)
    service_due = max(0.0, float(features.get("own_plants_unwatered", 0.0) or 0.0)) + max(
        0.0, float(features.get("own_animals_unfed", 0.0) or 0.0)
    )
    opponent_service_due = max(
        0.0, float(features.get("opponent_plants_unwatered", 0.0) or 0.0)
    ) + max(0.0, float(features.get("opponent_animals_unfed", 0.0) or 0.0))
    service_capacity = (hands + 1) * turns_today
    next_hire = fibonacci_hire_cost(hands)
    land_prices = (1000, 2000, 4000)
    extra_unlocked = max(0, unlocked - 1)
    next_land = land_prices[extra_unlocked] if extra_unlocked < len(land_prices) else 0
    current_liquidation = liquidation_value(features)
    current_mark_value = sum(
        int(features.get(f"shed_{item.lower()}", 0.0) or 0)
        * int(features.get(f"price_{item.lower()}", 0.0) or 0)
        for item in PRODUCTS
    )
    output = {
        "forward_turns_remaining": float(max(0, 720 - step)),
        "forward_days_remaining": float(max(0.0, (720 - step) / 24.0)),
        "forward_turns_today": float(turns_today),
        "forward_is_end_of_day_action": float(hour == 23),
        "forward_is_shop_tick_action": float(step % 4 == 0),
        "forward_is_center_tick_action": float(step % 24 == 0),
        "forward_turns_to_shop_unlock": float(turns_to_shop_unlock),
        "forward_terminal_1d": float(step >= 696),
        "forward_terminal_3d": float(step >= 648),
        "forward_terminal_6d": float(step >= 576),
        "forward_service_due": service_due,
        "forward_service_capacity_today": float(service_capacity),
        "forward_service_slack_today": float(service_capacity - service_due),
        "forward_service_load_per_unit_turn": service_due / max(1.0, float(service_capacity)),
        "forward_opponent_service_due": opponent_service_due,
        "forward_shed_room": float(max(0.0, 100.0 - shed_total)),
        "forward_eod_storage_overflow": float(max(0.0, shed_total + carried_total - 100.0)),
        "forward_storage_fill": float(min(1.0, shed_total / 100.0)),
        "forward_next_hire_cost": float(next_hire),
        "forward_next_hire_affordable": float(money >= next_hire),
        "forward_next_land_cost": float(next_land),
        "forward_next_land_affordable": float(bool(next_land) and money >= next_land),
        "forward_liquidation_value_now": float(current_liquidation),
        "forward_liquid_wealth_now": float(money + current_liquidation),
        "forward_liquidation_slippage_now": float(current_mark_value - current_liquidation),
    }
    for horizon in HORIZONS:
        future_value = liquidation_value(features, horizon)
        known_demand = sum(
            int(features.get(f"market_{item.lower()}", 0.0) or 0)
            - projected_inventory(features, item, horizon)
            for item in PRODUCTS
        )
        output[f"forward_liquidation_value_{horizon}"] = float(future_value)
        output[f"forward_liquidation_gain_{horizon}"] = float(future_value - current_liquidation)
        output[f"forward_known_demand_units_{horizon}"] = float(known_demand)
        output[f"forward_projection_complete_{horizon}"] = float(horizon <= turns_to_shop_unlock)
    return output


def augment_payload(payload: dict, require_price_parity: bool = True) -> tuple[dict, dict]:
    mismatches = []
    added_names = set()
    for row_index, row in enumerate(payload.get("rows", [])):
        features = row.get("features") or {}
        for item in PRODUCTS:
            inventory = int(features.get(f"market_{item.lower()}", 0.0) or 0)
            observed = int(features.get(f"price_{item.lower()}", 0.0) or 0)
            expected = market_price(item, inventory)
            if observed != expected:
                mismatches.append(
                    {"row": row_index, "item": item, "observed": observed, "expected": expected}
                )
        additions = forward_features(features)
        features.update(additions)
        added_names.update(additions)
    if require_price_parity and mismatches:
        first = mismatches[0]
        raise ValueError(
            f"official price parity failed in {len(mismatches)} cells; first={first}"
        )
    payload["schema"] = "inference-visible macro imitation + forward features v2"
    payload["forward_feature_contract"] = {
        "feature_count": len(added_names),
        "features": sorted(added_names),
        "price_parity_mismatches": len(mismatches),
        "future_market_assumption": "no player orders; currently visible shops only",
        "random_shop_crossing_flag": "forward_projection_complete_<horizon>",
        "clock_source": "day*24+hour (seat-stable)",
    }
    return payload, payload["forward_feature_contract"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    payload, report = augment_payload(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload), encoding="utf-8")
    print(json.dumps({"rows": len(payload.get("rows", [])), **report}, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
