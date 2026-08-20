"""Append a terminal EOD overflow-to-sale overlay to an agent file."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    overlay = r'''
# Generated H05 terminal overflow overlay. Unit actions execute before market
# orders, so an otherwise-idle shed-adjacent worker can PLACE wheat and sell it
# on the same final-hour turn instead of letting EOD discard it.
import copy as _to_copy
_TO_BASE_AGENT = agent
_TO_SAFE = {"PASS", "NORTH", "SOUTH", "EAST", "WEST"}
_TO_TELEMETRY = {
    "events": 0,
    "placed_wheat": 0,
    "last_excess": 0,
    "last_positions": [],
}


def _to_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _to_storage_total(private):
    shed = _to_get(private, "shed", {}) or {}
    inventories = _to_get(private, "inventories", []) or []
    return sum(int(value or 0) for value in dict(shed).values()) + sum(
        int(value or 0)
        for inventory in inventories
        for value in dict(inventory or {}).values()
    )


def _to_harvest_additions(farm, action):
    positions = [_to_get(farm, "farmer", None), *list(_to_get(farm, "hands", []) or [])]
    orders = [action.get("farmer") or ["PASS"], *list(action.get("hands") or [])]
    tiles = _to_get(farm, "tiles", []) or []
    additions = 0
    for position, order in zip(positions, orders):
        if not position or not order or order[0] not in {"HARVEST", "COLLECT_FERTILIZER"}:
            continue
        x, y = map(int, position[:2])
        try:
            tile = tiles[y][x]
        except (IndexError, TypeError):
            continue
        if not isinstance(tile, dict):
            continue
        if order[0] == "HARVEST":
            additions += max(0, int(tile.get("yield_units", 0) or 0))
        else:
            additions += max(0, int(tile.get("fertilizer_available", 0) or 0))
    return additions


def _to_existing_sales(private, action):
    available = {
        str(key): max(0, int(value or 0))
        for key, value in dict(_to_get(private, "shed", {}) or {}).items()
    }
    sold = 0
    for order in action.get("market") or []:
        if len(order) < 3 or order[0] != "SELL":
            continue
        item = str(order[1])
        quantity = min(max(0, int(order[2] or 0)), available.get(item, 0))
        available[item] = available.get(item, 0) - quantity
        sold += quantity
    return sold


def _to_add_wheat_sale(action, quantity):
    market = action.setdefault("market", [])
    for order in market:
        if len(order) >= 3 and order[0] == "SELL" and order[1] == "WHEAT":
            order[2] = max(0, int(order[2] or 0)) + quantity
            return
    market.insert(0, ["SELL", "WHEAT", quantity])
    del market[10:]


def agent(obs, configuration=None):
    action = _to_copy.deepcopy(_TO_BASE_AGENT(obs, configuration))
    day = int(_to_get(obs, "day", 0) or 0)
    hour = int(_to_get(obs, "hour", 0) or 0)
    turns = int(_to_get(configuration, "turnsPerDay", 24) or 24)
    episode_steps = int(_to_get(configuration, "episodeSteps", 720) or 720)
    target_day = episode_steps // turns - 2
    if day != target_day or hour != turns - 1:
        return action

    player = int(_to_get(obs, "player", 0) or 0)
    farms = list(_to_get(obs, "farms", []) or [])
    if player >= len(farms):
        return action
    farm = farms[player]
    private = _to_get(obs, "private", {}) or {}
    capacity = int(_to_get(configuration, "shedCapacity", 100) or 100)
    excess = (
        _to_storage_total(private)
        + _to_harvest_additions(farm, action)
        - _to_existing_sales(private, action)
        - capacity
    )
    if excess <= 0:
        return action

    size = len(_to_get(farm, "tiles", []) or []) or 10
    half = size // 2
    access = {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}
    positions = [_to_get(farm, "farmer", None), *list(_to_get(farm, "hands", []) or [])]
    inventories = list(_to_get(private, "inventories", []) or [])
    hands = action.get("hands", []) or []
    orders = [action.get("farmer") or ["PASS"], *hands]
    _TO_TELEMETRY["last_excess"] = excess
    _TO_TELEMETRY["last_positions"] = [
        {
            "position": list(position or []),
            "wheat": max(0, int(dict(inventory or {}).get("WHEAT", 0) or 0)),
            "action": list(order or ["PASS"]),
        }
        for position, inventory, order in zip(positions, inventories, orders)
    ]
    placed = 0
    for index, (position, inventory, order) in enumerate(zip(positions, inventories, orders)):
        if excess <= 0 or not position or tuple(map(int, position[:2])) not in access:
            continue
        if not order or order[0] not in _TO_SAFE:
            continue
        quantity = min(excess, max(0, int(dict(inventory or {}).get("WHEAT", 0) or 0)))
        if quantity <= 0:
            continue
        replacement = ["PLACE", "WHEAT", quantity]
        if index == 0:
            action["farmer"] = replacement
        elif index - 1 < len(hands):
            hands[index - 1] = replacement
        placed += quantity
        excess -= quantity
    if placed:
        _to_add_wheat_sale(action, placed)
        _TO_TELEMETRY["events"] += 1
        _TO_TELEMETRY["placed_wheat"] += placed
    return action


agent.telemetry = _TO_TELEMETRY
__version__ = "H05-terminal-overflow-sale-v1"
kaggle_entrypoint = agent
'''
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
