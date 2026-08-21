"""Append a fixed-actor pre-EOD shed route overlay for H21 experiments."""

from __future__ import annotations

import argparse
from pathlib import Path


OVERLAY = r'''
# Generated H21 pre-EOD routing overlay. Selected unit indexes use farmer=0,
# hand_0=1, ... and are intentionally fixed for a causal route-cost screen.
import copy as _h21_copy
from collections import deque as _h21_deque

_H21_BASE_AGENT = agent
_H21_ACTORS = __ACTORS__
_H21_START_STEP = __START_STEP__
_H21_MIN_TOTAL = __MIN_TOTAL__
_H21_ROUTE = __ROUTE__
_H21_ACTIVE = {0: False, 1: False}
_H21_TELEMETRY = {
    "triggered": False,
    "trigger_total": None,
    "required_route": _H21_ROUTE,
    "route_moves": 0,
    "drops": 0,
    "sold": {},
}


def _h21_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _h21_access(size):
    half = size // 2
    return {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def _h21_move(position, goals, tiles):
    start = tuple(map(int, position[:2]))
    if start in goals:
        return ["PASS"]
    size = len(tiles)
    queue = _h21_deque([start])
    first = {start: None}
    directions = (("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0))
    while queue:
        x, y = queue.popleft()
        for operation, dx, dy in directions:
            cell = (x + dx, y + dy)
            if cell in first or not (0 <= cell[0] < size and 0 <= cell[1] < size):
                continue
            if tiles[cell[1]][cell[0]] == "LOCKED":
                continue
            first[cell] = operation if (x, y) == start else first[(x, y)]
            if cell in goals:
                return [first[cell]]
            queue.append(cell)
    return ["PASS"]


def _h21_add_sales(action, inventory):
    totals = {}
    for raw in action.get("market") or []:
        if len(raw) >= 3 and raw[0] == "SELL":
            totals[str(raw[1])] = totals.get(str(raw[1]), 0) + max(0, int(raw[2] or 0))
    for item, raw_count in dict(inventory or {}).items():
        count = max(0, int(raw_count or 0))
        if count:
            totals[str(item)] = totals.get(str(item), 0) + count
            sold = _H21_TELEMETRY["sold"]
            sold[str(item)] = sold.get(str(item), 0) + count
    retained = [list(raw) for raw in action.get("market") or [] if not (len(raw) >= 3 and raw[0] == "SELL")]
    retained.extend(["SELL", item, count] for item, count in totals.items() if count > 0)
    action["market"] = retained[:10]


def agent(obs, configuration=None):
    action = _h21_copy.deepcopy(_H21_BASE_AGENT(obs, configuration))
    step = int(_h21_get(obs, "step", 0) or 0)
    seat = int(_h21_get(obs, "player", 0) or 0)
    if step == 0:
        _H21_ACTIVE[seat] = False
    if step < _H21_START_STEP or step > 695:
        return action
    farms = list(_h21_get(obs, "farms", []) or [])
    if seat >= len(farms):
        return action
    farm = farms[seat]
    private = _h21_get(obs, "private", {}) or {}
    positions = [_h21_get(farm, "farmer"), *list(_h21_get(farm, "hands", []) or [])]
    inventories = list(_h21_get(private, "inventories", []) or [])
    inventories.extend({} for _ in range(len(positions) - len(inventories)))
    if step == _H21_START_STEP:
        shed = dict(_h21_get(private, "shed", {}) or {})
        total = sum(max(0, int(value or 0)) for value in shed.values())
        total += sum(
            max(0, int(value or 0))
            for inventory in inventories
            for value in dict(inventory or {}).values()
        )
        route_matches = _H21_ROUTE is None or globals().get("_SELECTED_ROUTE") == _H21_ROUTE
        _H21_ACTIVE[seat] = route_matches and total >= _H21_MIN_TOTAL
        _H21_TELEMETRY["triggered"] = _H21_ACTIVE[seat]
        _H21_TELEMETRY["trigger_total"] = total
    if not _H21_ACTIVE[seat]:
        return action
    tiles = list(_h21_get(farm, "tiles", []) or [])
    goals = _h21_access(len(tiles))
    hands = action.get("hands", []) or []
    orders = [action.get("farmer") or ["PASS"], *hands]
    for index in _H21_ACTORS:
        if index >= len(positions) or index >= len(inventories) or index >= len(orders):
            continue
        inventory = dict(inventories[index] or {})
        if not any(int(value or 0) > 0 for value in inventory.values()):
            continue
        if tuple(map(int, positions[index][:2])) in goals:
            orders[index] = ["DROP"]
            _h21_add_sales(action, inventory)
            _H21_TELEMETRY["drops"] += 1
        else:
            orders[index] = _h21_move(positions[index], goals, tiles)
            _H21_TELEMETRY["route_moves"] += 1
    action["farmer"] = orders[0]
    action["hands"] = orders[1:]
    return action


agent.telemetry = _H21_TELEMETRY
__version__ = "H21-terminal-route-__LABEL__"
# The selector source already contains ``kaggle_entrypoint``. Reassigning that
# existing dict key does not move it after helpers for Kaggle's insertion-order
# loader, so H21 needs a fresh final alias name.
h21_kaggle_entrypoint = agent
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--actor", type=int, action="append", required=True)
    parser.add_argument("--start-step", type=int, default=689)
    parser.add_argument("--min-total", type=int, default=0)
    parser.add_argument("--route", choices=("moon", "x544", "any"), default="any")
    args = parser.parse_args()
    actors = tuple(sorted(set(args.actor)))
    if not actors or min(actors) < 0:
        raise ValueError("actors must be non-negative unit indexes")
    label = f"{args.route}-p{args.min_total}-" + "-".join(map(str, actors))
    overlay = (
        OVERLAY.replace("__ACTORS__", repr(actors))
        .replace("__START_STEP__", str(args.start_step))
        .replace("__MIN_TOTAL__", str(args.min_total))
        .replace("__ROUTE__", repr(None if args.route == "any" else args.route))
        .replace("__LABEL__", label)
    )
    source = args.source.read_text(encoding="utf-8")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
