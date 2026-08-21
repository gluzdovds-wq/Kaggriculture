"""Append a conservative value-aware terminal route overlay to an agent."""

from __future__ import annotations

import argparse
from pathlib import Path


OVERLAY = r'''
# Generated conservative terminal routing overlay.  At the start of the final
# routing window it selects at most one loaded hand that can reach shed access
# in the configured number of moves.  This avoids H21's long fixed routes.
import copy as _tn_copy
from collections import deque as _tn_deque

_TN_BASE_AGENT = agent
_TN_START_STEP = __START_STEP__
_TN_MIN_TOTAL = __MIN_TOTAL__
_TN_MAX_DISTANCE = __MAX_DISTANCE__
_TN_SELECTED = {0: None, 1: None}
_TN_ACTIVE = {0: False, 1: False}
_TN_TELEMETRY = {
    "triggered": False,
    "trigger_total": None,
    "selected_actor": None,
    "selected_distance": None,
    "selected_units": 0,
    "route_moves": 0,
    "drops": 0,
    "sold": {},
}


def _tn_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _tn_access(size):
    half = size // 2
    return {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def _tn_route(position, goals, tiles):
    start = tuple(map(int, position[:2]))
    if start in goals:
        return 0, ["PASS"]
    size = len(tiles)
    queue = _tn_deque([(start, 0)])
    first = {start: None}
    directions = (("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0))
    while queue:
        (x, y), distance = queue.popleft()
        for operation, dx, dy in directions:
            cell = (x + dx, y + dy)
            if cell in first or not (0 <= cell[0] < size and 0 <= cell[1] < size):
                continue
            if tiles[cell[1]][cell[0]] == "LOCKED":
                continue
            first[cell] = operation if (x, y) == start else first[(x, y)]
            if cell in goals:
                return distance + 1, [first[cell]]
            queue.append((cell, distance + 1))
    return None, ["PASS"]


def _tn_add_sales(action, inventory):
    totals = {}
    for raw in action.get("market") or []:
        if len(raw) >= 3 and raw[0] == "SELL":
            totals[str(raw[1])] = totals.get(str(raw[1]), 0) + max(0, int(raw[2] or 0))
    for item, raw_count in dict(inventory or {}).items():
        count = max(0, int(raw_count or 0))
        if count:
            totals[str(item)] = totals.get(str(item), 0) + count
            sold = _TN_TELEMETRY["sold"]
            sold[str(item)] = sold.get(str(item), 0) + count
    retained = [list(raw) for raw in action.get("market") or [] if not (len(raw) >= 3 and raw[0] == "SELL")]
    retained.extend(["SELL", item, count] for item, count in totals.items() if count > 0)
    action["market"] = retained[:10]


def agent(obs, configuration=None):
    action = _tn_copy.deepcopy(_TN_BASE_AGENT(obs, configuration))
    step = int(_tn_get(obs, "step", 0) or 0)
    seat = int(_tn_get(obs, "player", 0) or 0)
    if step == 0:
        _TN_SELECTED[seat] = None
        _TN_ACTIVE[seat] = False
    if step < _TN_START_STEP or step > 695:
        return action
    farms = list(_tn_get(obs, "farms", []) or [])
    if seat >= len(farms):
        return action
    farm = farms[seat]
    private = _tn_get(obs, "private", {}) or {}
    positions = [_tn_get(farm, "farmer"), *list(_tn_get(farm, "hands", []) or [])]
    inventories = list(_tn_get(private, "inventories", []) or [])
    inventories.extend({} for _ in range(len(positions) - len(inventories)))
    tiles = list(_tn_get(farm, "tiles", []) or [])
    goals = _tn_access(len(tiles))
    if step == _TN_START_STEP:
        shed = dict(_tn_get(private, "shed", {}) or {})
        total = sum(max(0, int(value or 0)) for value in shed.values())
        total += sum(
            max(0, int(value or 0))
            for inventory in inventories
            for value in dict(inventory or {}).values()
        )
        options = []
        if total >= _TN_MIN_TOTAL:
            for index in range(1, min(len(positions), len(inventories))):
                inventory = dict(inventories[index] or {})
                units = sum(max(0, int(value or 0)) for value in inventory.values())
                if units <= 0:
                    continue
                distance, _ = _tn_route(positions[index], goals, tiles)
                if distance is not None and distance <= _TN_MAX_DISTANCE:
                    options.append((units, -distance, -index, index, distance))
        selected = max(options)[3:] if options else None
        _TN_SELECTED[seat] = selected[0] if selected else None
        _TN_ACTIVE[seat] = selected is not None
        _TN_TELEMETRY["triggered"] = _TN_ACTIVE[seat]
        _TN_TELEMETRY["trigger_total"] = total
        _TN_TELEMETRY["selected_actor"] = selected[0] if selected else None
        _TN_TELEMETRY["selected_distance"] = selected[1] if selected else None
        _TN_TELEMETRY["selected_units"] = max(options)[0] if options else 0
    if not _TN_ACTIVE[seat]:
        return action
    index = _TN_SELECTED[seat]
    hands = action.get("hands", []) or []
    orders = [action.get("farmer") or ["PASS"], *hands]
    if index is None or index >= len(positions) or index >= len(inventories) or index >= len(orders):
        return action
    inventory = dict(inventories[index] or {})
    if not any(int(value or 0) > 0 for value in inventory.values()):
        _TN_ACTIVE[seat] = False
        return action
    distance, move = _tn_route(positions[index], goals, tiles)
    if distance == 0:
        orders[index] = ["DROP"]
        _tn_add_sales(action, inventory)
        _TN_TELEMETRY["drops"] += 1
        _TN_ACTIVE[seat] = False
    elif distance is not None:
        orders[index] = move
        _TN_TELEMETRY["route_moves"] += 1
    action["farmer"] = orders[0]
    action["hands"] = orders[1:]
    return action


agent.telemetry = _TN_TELEMETRY
__version__ = "terminal-nearby-p__MIN_TOTAL__-d__MAX_DISTANCE__"
terminal_nearby_kaggle_entrypoint = agent
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--start-step", type=int, default=689)
    parser.add_argument("--min-total", type=int, default=90)
    parser.add_argument("--max-distance", type=int, default=1)
    args = parser.parse_args()
    if args.max_distance < 0:
        raise ValueError("max distance must be non-negative")
    overlay = (
        OVERLAY.replace("__START_STEP__", str(args.start_step))
        .replace("__MIN_TOTAL__", str(args.min_total))
        .replace("__MAX_DISTANCE__", str(args.max_distance))
    )
    source = args.source.read_text(encoding="utf-8")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
