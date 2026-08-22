"""Append bounded market-timing overlays to the current selector artifact."""

from __future__ import annotations

import argparse
from pathlib import Path


ALLOWED_ITEMS = (
    "WHEAT", "FERTILIZER", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL",
)
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
    "WHEAT": {"base": 25, "I0": 10000, "T": 400, "below_func": "sqrt", "below_target": 0.80, "above_func": "log", "above_target": 0.20},
    "CARROT": {"base": 35, "I0": 10000, "T": 450, "below_func": "hinge", "below_target": 1.00, "above_func": "sqrt", "above_target": 0.70},
    "TOMATO": {"base": 60, "I0": 10000, "T": 200, "below_func": "hinge", "below_target": 0.40, "above_func": "sqrt", "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": 10000, "T": 100, "below_func": "sqrt", "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON": {"base": 250, "I0": 10000, "T": 300, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.60},
    "EGG": {"base": 50, "I0": 10000, "T": 332, "below_func": "hinge", "below_target": 0.40, "above_func": "log", "above_target": 0.20},
    "MILK": {"base": 160, "I0": 10000, "T": 122, "below_func": "sqrt", "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL": {"base": 200, "I0": 10000, "T": 105, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": 10000, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}


def parse_item_caps(values: list[str]) -> dict[str, int]:
    caps = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("item cap must be ITEM=QUANTITY")
        item, quantity = raw.split("=", 1)
        item = item.strip().upper()
        if item not in ALLOWED_ITEMS:
            raise ValueError(f"unsupported market item: {item}")
        try:
            value = int(quantity)
        except ValueError as exc:
            raise ValueError("item cap quantity must be an integer") from exc
        if value < 0:
            raise ValueError("item cap quantity must be non-negative")
        caps[item] = value
    return caps


TEMPLATE = r'''

# Generated market-timing experiment: conserve quantities while moving only
# already scheduled sales of selected products a bounded number of turns earlier.
import copy as _mt_copy
import math as _mt_math

_MT_BASE_AGENT = agent
_MT_ITEMS = {items!r}
_MT_CAPS = {caps!r}
_MT_START = {start}
_MT_STOP = {stop}
_MT_LEAD_X544 = {x544_lead}
_MT_LEAD_MOON = {moon_lead}
_MT_MOON_WINDOW_LEAD = {moon_window_lead}
_MT_MOON_WINDOW_START = {moon_window_start}
_MT_MOON_WINDOW_STOP = {moon_window_stop}
_MT_OPENING = {opening!r}
_MT_PRICE_GATE_RATIO = {price_gate_ratio!r}
_MT_MARKET_PARAMS = {market_params!r}
_MT_SHOPS = {shops!r}
_MT_DEBT = {{0: {{}}, 1: {{}}}}
_MT_LAST = {{0: -1, 1: -1}}
_MT_TELEMETRY = {{
    "advanced": {{}},
    "repaid": {{}},
    "opening": _MT_OPENING,
    "lead_x544": _MT_LEAD_X544,
    "lead_moon": _MT_LEAD_MOON,
    "moon_window_lead": _MT_MOON_WINDOW_LEAD,
    "moon_window": [_MT_MOON_WINDOW_START, _MT_MOON_WINDOW_STOP],
    "price_gate_ratio": _MT_PRICE_GATE_RATIO,
    "gate_accepted": {{}},
    "gate_rejected": {{}},
}}


def _mt_trace():
    if globals().get("_SELECTED_ROUTE") == "moon":
        return globals().get("_MOON_NS", {{}}).get("_ACTIONS", [])
    nested = globals().get("_X544_NS", {{}}).get("_X540_NS", {{}})
    return nested.get("_ACTIONS", [])


def _mt_lead(step):
    if globals().get("_SELECTED_ROUTE") != "moon":
        return _MT_LEAD_X544
    if (_MT_MOON_WINDOW_LEAD is not None and
            _MT_MOON_WINDOW_START <= step < _MT_MOON_WINDOW_STOP):
        return _MT_MOON_WINDOW_LEAD
    return _MT_LEAD_MOON


def _mt_shape(name, value, scale):
    value = max(0.0, value)
    if name == "linear": return value
    if name == "sq": return value * value
    if name == "sqrt": return _mt_math.sqrt(value)
    if name == "log": return _mt_math.log1p(value)
    if name == "log10": return _mt_math.log10(1.0 + value)
    if name == "hinge":
        ratio = value / scale
        return ratio + 8.0 * max(0.0, ratio - 1.0) ** 2
    return value


def _mt_price(item, inventory):
    params = _MT_MARKET_PARAMS[item]
    base, initial, scale = params["base"], params["I0"], params["T"]
    if inventory < initial:
        name = params["below_func"]
        amplitude = params["below_target"] * base / _mt_shape(name, scale, scale)
        price = base + amplitude * _mt_shape(name, initial - inventory, scale)
    else:
        name = params["above_func"]
        amplitude = params["above_target"] * base / _mt_shape(name, scale, scale)
        price = base - amplitude * _mt_shape(name, inventory - initial, scale)
    return max(1, int(round(price)))


def _mt_sale(item, inventory, quantity):
    revenue = 0
    for _ in range(max(0, int(quantity))):
        price = _mt_price(item, inventory)
        revenue += price
        if price > 1:
            inventory += 1
    return revenue, inventory


def _mt_ticks(step, horizon, interval):
    return sum(1 for value in range(step, step + horizon) if value % interval == 0)


def _mt_project_inventory(obs, item, step, horizon, starting_inventory):
    shop_demand = 0
    unlocked = list((obs.get("town") or {{}}).get("unlocked_shops") or [])
    for shop in unlocked:
        products = _MT_SHOPS.get(str(shop), ())
        if item in products:
            shop_demand += 2 if len(products) == 1 else 1
    inventory = starting_inventory - _mt_ticks(step, horizon, 4) * shop_demand
    if item != "FERTILIZER":
        inventory -= _mt_ticks(step, horizon, 24)
    return inventory


def _mt_should_advance(obs, item, quantity, prior_quantity, step, horizon):
    if _MT_PRICE_GATE_RATIO is None:
        return True
    # Fall back to the already validated fixed lead when the projection crosses
    # a future random shop reveal whose product demand is not observable yet.
    next_unlock = (step // 72 + 1) * 72
    if step + horizon > next_unlock:
        return True
    market = obs.get("market") or {{}}
    inventory = int((market.get("inventory") or {{}}).get(item, 0) or 0)
    _, inventory_after_prior = _mt_sale(item, inventory, prior_quantity)
    current_revenue, _ = _mt_sale(item, inventory_after_prior, quantity)
    future_inventory = _mt_project_inventory(
        obs, item, step, horizon, inventory_after_prior
    )
    future_revenue, _ = _mt_sale(item, future_inventory, quantity)
    accepted = current_revenue >= _MT_PRICE_GATE_RATIO * future_revenue
    telemetry = _MT_TELEMETRY["gate_accepted" if accepted else "gate_rejected"]
    telemetry[item] = telemetry.get(item, 0) + quantity
    return accepted


def _mt_repay(action, debt):
    if not debt:
        return action
    out = []
    for raw in action.get("market") or []:
        order = list(raw)
        if len(order) >= 3 and order[0] == "SELL" and debt.get(order[1], 0) > 0:
            item = str(order[1])
            quantity = max(0, int(order[2] or 0))
            reduction = min(quantity, int(debt[item]))
            quantity -= reduction
            debt[item] -= reduction
            _MT_TELEMETRY["repaid"][item] = _MT_TELEMETRY["repaid"].get(item, 0) + reduction
            if quantity <= 0:
                continue
            order[2] = quantity
        out.append(order)
    action["market"] = out
    return action


def _mt_advance(action, obs, step, schedule):
    if not _MT_ITEMS or step < _MT_START or step >= _MT_STOP:
        return action
    trace = _mt_trace()
    future_step = step + _mt_lead(step)
    if future_step >= len(trace):
        return action
    future = {{}}
    for raw in trace[future_step].get("market") or []:
        if len(raw) >= 3 and raw[0] == "SELL" and raw[1] in _MT_ITEMS:
            item = str(raw[1])
            future[item] = future.get(item, 0) + max(0, int(raw[2] or 0))
    market = [list(raw) for raw in action.get("market") or []]
    if not future or len(market) >= 10:
        return action
    committed = {{}}
    for raw in market:
        if len(raw) >= 3 and raw[0] == "SELL":
            item = str(raw[1])
            committed[item] = committed.get(item, 0) + max(0, int(raw[2] or 0))
    private = obs.get("private") or {{}}
    shed = private.get("shed") or {{}}
    for item in _MT_ITEMS:
        if len(market) >= 10:
            break
        available = max(0, int(shed.get(item, 0) or 0) - committed.get(item, 0))
        quantity = min(future.get(item, 0), int(_MT_CAPS.get(item, 0)), available)
        if quantity <= 0:
            continue
        if not _mt_should_advance(
            obs, item, quantity, committed.get(item, 0), step, future_step - step
        ):
            continue
        market.append(["SELL", item, quantity])
        due = schedule.setdefault(future_step, {{}})
        due[item] = due.get(item, 0) + quantity
        _MT_TELEMETRY["advanced"][item] = _MT_TELEMETRY["advanced"].get(item, 0) + quantity
    action["market"] = market
    return action


def _mt_opening(action, step):
    if step != 0 or _MT_OPENING == "keep":
        return action
    wanted = 5 if _MT_OPENING == "feed5_first" else 6
    market = [list(raw) for raw in action.get("market") or []]
    rest = [raw for raw in market if not (
        len(raw) >= 3 and raw[0] == "BUY_PRODUCT" and raw[1] == "WHEAT"
    )]
    action["market"] = [["BUY_PRODUCT", "WHEAT", wanted], *rest][:10]
    return action


def agent(obs, configuration=None):
    action = _mt_copy.deepcopy(_MT_BASE_AGENT(obs, configuration))
    try:
        step = int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)
        seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
        if step == 0 or step <= _MT_LAST[seat]:
            _MT_DEBT[seat] = {{}}
        _MT_LAST[seat] = step
        schedule = _MT_DEBT[seat]
        due = schedule.pop(step, {{}})
        action = _mt_repay(action, due)
        if due:
            carry = schedule.setdefault(step + 1, {{}})
            for item, quantity in due.items():
                if quantity > 0:
                    carry[item] = carry.get(item, 0) + quantity
        action = _mt_opening(action, step)
        return _mt_advance(action, obs, step, schedule)
    except Exception:
        return action


agent.telemetry = _MT_TELEMETRY
__version__ = "market-timing-{label}"
market_timing_kaggle_entrypoint = agent
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--items",
        default="",
        help="comma-separated market products to advance",
    )
    parser.add_argument("--wheat-cap", type=int, default=10)
    parser.add_argument("--fertilizer-cap", type=int, default=5)
    parser.add_argument(
        "--item-cap",
        action="append",
        default=[],
        metavar="ITEM=QUANTITY",
        help="override the default cap 10 for any selected product",
    )
    parser.add_argument("--start", type=int, default=120)
    parser.add_argument("--stop", type=int, default=715)
    parser.add_argument("--lead", type=int, default=1)
    parser.add_argument("--x544-lead", type=int)
    parser.add_argument("--moon-lead", type=int)
    parser.add_argument("--moon-window-lead", type=int)
    parser.add_argument("--moon-window-start", type=int, default=0)
    parser.add_argument("--moon-window-stop", type=int, default=0)
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="strip a previously generated market overlay before appending",
    )
    parser.add_argument("--opening", choices=("keep", "feed5_first", "feed6_first"), default="keep")
    parser.add_argument(
        "--price-gate-ratio",
        type=float,
        help=(
            "advance only when exact current revenue is at least this fraction "
            "of the known-demand future revenue"
        ),
    )
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    items = tuple(part.strip().upper() for part in args.items.split(",") if part.strip())
    if any(item not in ALLOWED_ITEMS for item in items):
        parser.error("--items contains an unsupported market product")
    x544_lead = args.x544_lead if args.x544_lead is not None else args.lead
    moon_lead = args.moon_lead if args.moon_lead is not None else args.lead
    if not all(1 <= value <= 24 for value in (x544_lead, moon_lead)):
        parser.error("lead values must be in 1..24")
    if args.moon_window_lead is not None:
        if not 1 <= args.moon_window_lead <= 24:
            parser.error("--moon-window-lead must be in 1..24")
        if args.moon_window_stop <= args.moon_window_start:
            parser.error("moon lead window must have stop > start")
    if args.price_gate_ratio is not None and not 0.0 <= args.price_gate_ratio <= 1.0:
        parser.error("--price-gate-ratio must be in [0, 1]")
    caps = {item: 10 for item in ALLOWED_ITEMS}
    caps.update({"WHEAT": args.wheat_cap, "FERTILIZER": args.fertilizer_cap})
    try:
        caps.update(parse_item_caps(args.item_cap))
    except ValueError as exc:
        parser.error(str(exc))
    source = args.source.read_text(encoding="utf-8")
    marker = "\n# Generated market-timing experiment:"
    if args.replace_existing:
        if source.count(marker) != 1:
            parser.error("--replace-existing requires exactly one generated market overlay")
        source = source.split(marker, 1)[0].rstrip() + "\n"
    rendered = TEMPLATE.format(
        items=items,
        caps=caps,
        start=args.start,
        stop=args.stop,
        x544_lead=x544_lead,
        moon_lead=moon_lead,
        moon_window_lead=args.moon_window_lead,
        moon_window_start=args.moon_window_start,
        moon_window_stop=args.moon_window_stop,
        opening=args.opening,
        price_gate_ratio=args.price_gate_ratio,
        market_params=MARKET_PARAMS,
        shops=SHOPS,
        label=args.label,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source + rendered, encoding="utf-8")
    compile(args.output.read_bytes(), str(args.output), "exec")
    print(args.output)


if __name__ == "__main__":
    main()
