"""Append a bounded public-fingerprint reactive weed-cleaning task overlay."""

from __future__ import annotations

import argparse
from pathlib import Path


OVERLAY = r'''

# Generated bounded reactive weed-cleaning task.
import copy as _rwc_copy
from collections import deque as _rwc_deque

_RWC_BASE_AGENT = agent
_RWC_START = __START__
_RWC_STOP = __STOP__
_RWC_MIN_WEEDS = __MIN_WEEDS__
_RWC_ALLOW_MOVING = __ALLOW_MOVING__
_RWC_EXTRA_HIRE = __EXTRA_HIRE__
_RWC_ACTIVE = {0: False, 1: False}
_RWC_TELEMETRY = {
    "active": False,
    "routes": 0,
    "digs": 0,
    "hires": 0,
    "first_steps": [],
}


def _rwc_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _rwc_johnson(obs, seat):
    farms = list(_rwc_get(obs, "farms", []) or [])
    opponent = 1 - seat
    if opponent < 0 or opponent >= len(farms):
        return False
    farm = farms[opponent]
    hands = list(_rwc_get(farm, "hands", []) or [])
    kinds, crops, animals = {}, {}, {}
    for row in _rwc_get(farm, "tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", ""))
            kinds[kind] = kinds.get(kind, 0) + 1
            crop = tile.get("crop")
            if crop:
                crops[str(crop)] = crops.get(str(crop), 0) + 1
            animal = tile.get("animal")
            if animal:
                animals[str(animal)] = animals.get(str(animal), 0) + 1
    money = float(_rwc_get(farm, "money", 0) or 0)
    return (
        len(hands) == 6
        and 250 <= money <= 320
        and kinds.get("PASTURE", 0) == 4
        and kinds.get("PLANT", 0) == 8
        and crops.get("WHEAT", 0) == 7
        and crops.get("STRAWBERRY", 0) == 1
        and animals.get("COW", 0) == 1
        and animals.get("SHEEP", 0) == 3
    )


def _rwc_move(position, goals, tiles):
    start = tuple(map(int, position[:2]))
    if start in goals:
        return ["DIG"]
    size = len(tiles)
    queue = _rwc_deque([start])
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


def agent(obs, configuration=None):
    action = _rwc_copy.deepcopy(_RWC_BASE_AGENT(obs, configuration))
    try:
        step = int(_rwc_get(obs, "step", 0) or 0)
        seat = 1 if int(_rwc_get(obs, "player", 0) or 0) == 1 else 0
        if step == 0:
            _RWC_ACTIVE[seat] = False
        if step == 12:
            _RWC_ACTIVE[seat] = _rwc_johnson(obs, seat)
            _RWC_TELEMETRY["active"] = _RWC_ACTIVE[seat]
        if not _RWC_ACTIVE[seat] or not _RWC_START <= step < _RWC_STOP:
            return action
        farms = list(_rwc_get(obs, "farms", []) or [])
        if seat >= len(farms):
            return action
        farm = farms[seat]
        tiles = list(_rwc_get(farm, "tiles", []) or [])
        weeds = {
            (x, y)
            for y, row in enumerate(tiles)
            for x, tile in enumerate(row or [])
            if isinstance(tile, dict) and tile.get("kind") == "WEED"
        }
        if len(weeds) < _RWC_MIN_WEEDS:
            return action
        positions = [_rwc_get(farm, "farmer"), *list(_rwc_get(farm, "hands", []) or [])]
        if _RWC_EXTRA_HIRE and step % 24 == 0 and len(positions) < 7:
            market = [list(order) for order in action.get("market") or []]
            if len(market) < 10:
                market.append(["HIRE"])
                action["market"] = market
                _RWC_TELEMETRY["hires"] += 1
        inventories = list(_rwc_get(_rwc_get(obs, "private", {}) or {}, "inventories", []) or [])
        inventories.extend({} for _ in range(len(positions) - len(inventories)))
        orders = [action.get("farmer") or ["PASS"], *list(action.get("hands") or [])]
        safe = {"PASS"}
        if _RWC_ALLOW_MOVING:
            safe.update({"NORTH", "SOUTH", "WEST", "EAST"})
        choices = []
        for index, (position, inventory, order) in enumerate(zip(positions, inventories, orders)):
            if _RWC_EXTRA_HIRE and (len(positions) < 7 or index != len(positions) - 1):
                continue
            if not position or not order or order[0] not in safe:
                continue
            if any(int(value or 0) > 0 for value in dict(inventory or {}).values()):
                continue
            x, y = map(int, position[:2])
            distance = min(abs(x - gx) + abs(y - gy) for gx, gy in weeds)
            choices.append((0 if order[0] == "PASS" else 1, distance, index))
        if not choices:
            return action
        _, _, index = min(choices)
        replacement = _rwc_move(positions[index], weeds, tiles)
        if replacement == ["PASS"]:
            return action
        orders[index] = replacement
        action["farmer"] = orders[0]
        action["hands"] = orders[1:]
        key = "digs" if replacement == ["DIG"] else "routes"
        _RWC_TELEMETRY[key] += 1
        if len(_RWC_TELEMETRY["first_steps"]) < 32:
            _RWC_TELEMETRY["first_steps"].append([step, index, replacement[0], len(weeds)])
        return action
    except Exception:
        return action


agent.telemetry = _RWC_TELEMETRY
__version__ = "reactive-weed-cleaner-__LABEL__"
reactive_weed_cleaner_kaggle_entrypoint = agent
'''


def render_variant(
    source: str,
    *,
    start: int,
    stop: int,
    min_weeds: int,
    allow_moving: bool,
    extra_hire: bool,
    label: str,
) -> str:
    if not 12 <= start < stop <= 720:
        raise ValueError("window must satisfy 12 <= start < stop <= 720")
    if min_weeds < 1:
        raise ValueError("minimum weeds must be positive")
    overlay = (
        OVERLAY.replace("__START__", str(start))
        .replace("__STOP__", str(stop))
        .replace("__MIN_WEEDS__", str(min_weeds))
        .replace("__ALLOW_MOVING__", repr(bool(allow_moving)))
        .replace("__EXTRA_HIRE__", repr(bool(extra_hire)))
        .replace("__LABEL__", label)
    )
    return source.rstrip() + "\n" + overlay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--start", type=int, default=432)
    parser.add_argument("--stop", type=int, default=696)
    parser.add_argument("--min-weeds", type=int, default=3)
    parser.add_argument("--allow-moving", action="store_true")
    parser.add_argument("--extra-hire", action="store_true")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    try:
        generated = render_variant(
            args.source.read_text(encoding="utf-8"),
            start=args.start,
            stop=args.stop,
            min_weeds=args.min_weeds,
            allow_moving=args.allow_moving,
            extra_hire=args.extra_hire,
            label=args.label,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(generated, encoding="utf-8")
    compile(generated, str(args.destination), "exec")
    print(args.destination)


if __name__ == "__main__":
    main()
