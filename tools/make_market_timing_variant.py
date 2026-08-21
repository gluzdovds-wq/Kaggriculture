"""Append bounded market-timing overlays to the current selector artifact."""

from __future__ import annotations

import argparse
from pathlib import Path


ALLOWED_ITEMS = (
    "WHEAT", "FERTILIZER", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL",
)


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
        step = int(obs.get("step", 0) or 0)
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
        label=args.label,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source + rendered, encoding="utf-8")
    compile(args.output.read_bytes(), str(args.output), "exec")
    print(args.output)


if __name__ == "__main__":
    main()
