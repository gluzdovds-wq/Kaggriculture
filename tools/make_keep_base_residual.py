"""Append a bounded residual action to an existing Kaggriculture agent."""

from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = r'''

# Generated KEEP_BASE residual: replace only an already idle actor action with
# a locally legal WATER.  Field routing, inventories and all market orders stay
# under the base policy's control.
import copy as _kbr_copy

_KBR_BASE_AGENT = agent
_KBR_START = __START__
_KBR_STOP = __STOP__
_KBR_MAX_PER_TURN = __MAX_PER_TURN__
_KBR_REPAY_HARVEST = __REPAY_HARVEST__
_KBR_FIRST_YIELD = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
_KBR_PREPAID = {0: set(), 1: set()}
_KBR_DAY = {0: -1, 1: -1}
_KBR_TELEMETRY = {
    "start": _KBR_START,
    "stop": _KBR_STOP,
    "watered": 0,
    "turns_changed": 0,
    "harvest_repayments": 0,
    "first_steps": [],
    "fallbacks": 0,
}


def _kbr_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def agent(obs, configuration=None):
    base = _KBR_BASE_AGENT(obs, configuration)
    action = _kbr_copy.deepcopy(base)
    try:
        step = int(_kbr_get(obs, "step", 0) or 0)
        if not _KBR_START <= step < _KBR_STOP:
            return action
        seat = 1 if int(_kbr_get(obs, "player", 0) or 0) == 1 else 0
        farms = list(_kbr_get(obs, "farms", []) or [])
        if seat >= len(farms):
            return action
        farm = farms[seat]
        day = int(_kbr_get(obs, "day", step // 24) or 0)
        if _KBR_DAY[seat] != day:
            _KBR_PREPAID[seat].clear()
            _KBR_DAY[seat] = day
        positions = [
            _kbr_get(farm, "farmer", [4, 4]),
            *list(_kbr_get(farm, "hands", []) or []),
        ]
        tiles = list(_kbr_get(farm, "tiles", []) or [])
        orders = [
            list(action.get("farmer") or ["PASS"]),
            *[list(value or ["PASS"]) for value in (action.get("hands") or [])],
        ]
        changed = 0
        if _KBR_REPAY_HARVEST:
            for actor, position in enumerate(positions):
                if actor >= len(orders) or not position or not orders[actor]:
                    break
                if orders[actor][0] != "WATER":
                    continue
                x, y = int(position[0]), int(position[1])
                key = (x, y)
                if key not in _KBR_PREPAID[seat]:
                    continue
                if not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
                    continue
                tile = tiles[y][x]
                crop = str(tile.get("crop", "")) if isinstance(tile, dict) else ""
                planted = tile.get("planted_day", day) if isinstance(tile, dict) else day
                age = day - int(day if planted is None else planted)
                if not (
                    isinstance(tile, dict)
                    and tile.get("kind") == "PLANT"
                    and tile.get("watered_today", False)
                    and int(tile.get("yield_units", 0) or 0) > 0
                    and age >= _KBR_FIRST_YIELD.get(crop, 0)
                ):
                    continue
                orders[actor] = ["HARVEST"]
                _KBR_PREPAID[seat].discard(key)
                changed += 1
                _KBR_TELEMETRY["harvest_repayments"] += 1
                if len(_KBR_TELEMETRY["first_steps"]) < 32:
                    _KBR_TELEMETRY["first_steps"].append([step, actor, "HARVEST_REPAY"])
        for actor, position in enumerate(positions):
            if changed >= _KBR_MAX_PER_TURN or actor >= len(orders) or not position:
                break
            if not orders[actor] or orders[actor][0] != "PASS":
                continue
            x, y = int(position[0]), int(position[1])
            if not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
                continue
            tile = tiles[y][x]
            if not (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and not tile.get("watered_today", False)
            ):
                continue
            orders[actor] = ["WATER"]
            _KBR_PREPAID[seat].add((x, y))
            changed += 1
            _KBR_TELEMETRY["watered"] += 1
            if len(_KBR_TELEMETRY["first_steps"]) < 32:
                _KBR_TELEMETRY["first_steps"].append([step, actor])
        if changed:
            action["farmer"] = orders[0]
            action["hands"] = orders[1:]
            _KBR_TELEMETRY["turns_changed"] += 1
        return action
    except Exception:
        _KBR_TELEMETRY["fallbacks"] += 1
        return _kbr_copy.deepcopy(base)


agent.telemetry = _KBR_TELEMETRY
__version__ = "keep-base-idle-water-__LABEL__"
keep_base_residual_kaggle_entrypoint = agent
'''


def render(
    source: str,
    *,
    start: int,
    stop: int,
    max_per_turn: int,
    repay_harvest: bool,
    label: str,
) -> str:
    if not 0 <= start < stop <= 720:
        raise ValueError("window must satisfy 0 <= start < stop <= 720")
    if max_per_turn < 1:
        raise ValueError("max_per_turn must be positive")
    if "def agent(" not in source:
        raise ValueError("base source has no agent")
    overlay = (
        TEMPLATE.replace("__START__", str(start))
        .replace("__STOP__", str(stop))
        .replace("__MAX_PER_TURN__", str(max_per_turn))
        .replace("__REPAY_HARVEST__", repr(bool(repay_harvest)))
        .replace("__LABEL__", label)
    )
    return source.rstrip() + "\n" + overlay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=720)
    parser.add_argument("--max-per-turn", type=int, default=1)
    parser.add_argument("--repay-harvest", action="store_true")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    try:
        generated = render(
            args.source.read_text(encoding="utf-8"),
            start=args.start,
            stop=args.stop,
            max_per_turn=args.max_per_turn,
            repay_harvest=args.repay_harvest,
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
