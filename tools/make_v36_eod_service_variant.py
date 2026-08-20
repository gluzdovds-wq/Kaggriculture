"""Create a V36 probe that reuses otherwise-dead final-hour movement actions."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--start-day", type=int, default=0)
    parser.add_argument("--stop-day", type=int, default=29)
    parser.add_argument("--disable-harvest", action="store_true")
    parser.add_argument("--disable-water", action="store_true")
    parser.add_argument("--disable-animal", action="store_true")
    parser.add_argument("--disable-dig", action="store_true")
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    overlay = f'''
# Generated H04 probe: final-hour movement has no positional value because all
# units reset after this action and every carried item auto-drops to the shed.
import copy as _v36_eod_copy
_V36_EOD_BASE = _V36_POLICY
_V36_EOD_START_DAY = {args.start_day!r}
_V36_EOD_STOP_DAY = {args.stop_day!r}
_V36_EOD_HARVEST = {not args.disable_harvest!r}
_V36_EOD_WATER = {not args.disable_water!r}
_V36_EOD_ANIMAL = {not args.disable_animal!r}
_V36_EOD_DIG = {not args.disable_dig!r}
_V36_EOD_SAFE = {{"NORTH", "SOUTH", "EAST", "WEST", "PASS"}}
_V36_EOD_TELEMETRY = {{"eligible": 0, "replaced": 0, "operations": {{}}}}

def _v36_eod_policy(obs, configuration=None):
    _v36_eod_action = _v36_eod_copy.deepcopy(_V36_EOD_BASE(obs, configuration))
    _v36_eod_step = int(_v36_get(obs, "step", 0) or 0)
    _v36_eod_day = int(_v36_get(obs, "day", _v36_eod_step // 24) or 0)
    _v36_eod_hour = int(_v36_get(obs, "hour", _v36_eod_step % 24) or 0)
    if (_v36_eod_hour != 23 or not
            (_V36_EOD_START_DAY <= _v36_eod_day <= _V36_EOD_STOP_DAY)):
        return _v36_eod_action

    _v36_eod_player = int(_v36_get(obs, "player", 0) or 0)
    _v36_eod_farms = list(_v36_get(obs, "farms", []) or [])
    if _v36_eod_player >= len(_v36_eod_farms):
        return _v36_eod_action
    _v36_eod_farm = _v36_eod_farms[_v36_eod_player]
    _v36_eod_private = _v36_get(obs, "private", {{}}) or {{}}
    _v36_eod_inventories = list(_v36_get(_v36_eod_private, "inventories", []) or [])
    _v36_eod_tiles = _v36_get(_v36_eod_farm, "tiles", []) or []
    _v36_eod_positions = [_v36_get(_v36_eod_farm, "farmer", None)]
    _v36_eod_positions.extend(_v36_get(_v36_eod_farm, "hands", []) or [])
    _v36_eod_hands = _v36_eod_action.get("hands", []) or []
    _v36_eod_actions = [_v36_eod_action.get("farmer") or ["PASS"], *_v36_eod_hands]
    _v36_eod_claimed = set()

    for _v36_eod_index, (_v36_eod_position, _v36_eod_base_action) in enumerate(
            zip(_v36_eod_positions, _v36_eod_actions)):
        if (not _v36_eod_base_action or
                _v36_eod_base_action[0] not in _V36_EOD_SAFE or
                not _v36_eod_position or len(_v36_eod_position) < 2):
            continue
        _V36_EOD_TELEMETRY["eligible"] += 1
        _v36_eod_x, _v36_eod_y = map(int, _v36_eod_position[:2])
        try:
            _v36_eod_tile = _v36_eod_tiles[_v36_eod_y][_v36_eod_x]
        except (IndexError, TypeError):
            continue
        _v36_eod_choice = None
        if isinstance(_v36_eod_tile, dict) and _v36_eod_tile.get("kind") == "PLANT":
            _v36_eod_age = _v36_eod_day - int(_v36_eod_tile.get("planted_day", 0) or 0)
            _v36_eod_crop = _v36_eod_tile.get("crop")
            _v36_eod_ongoing = _v36_eod_crop in {{"TOMATO", "STRAWBERRY"}}
            _v36_eod_peak = {{"WHEAT": 4, "CARROT": 3, "MELON": 12}}.get(
                _v36_eod_crop, 0)
            if (_V36_EOD_HARVEST and
                    (_v36_eod_tile.get("yield_units", 0) or 0) > 0 and
                    (_v36_eod_ongoing or _v36_eod_age >= _v36_eod_peak)):
                _v36_eod_choice = "HARVEST"
            elif (_V36_EOD_WATER and
                  not _v36_eod_tile.get("watered_today", False)):
                _v36_eod_choice = "WATER"
        elif (_V36_EOD_DIG and isinstance(_v36_eod_tile, dict) and
              _v36_eod_tile.get("kind") == "WEED"):
            _v36_eod_choice = "DIG"
        elif (_V36_EOD_ANIMAL and isinstance(_v36_eod_tile, dict) and
              "animal" in _v36_eod_tile):
            _v36_eod_inventory = (_v36_eod_inventories[_v36_eod_index]
                                  if _v36_eod_index < len(_v36_eod_inventories) else {{}})
            _v36_eod_options = []
            if (_v36_eod_tile.get("yield_units", 0) or 0) > 0:
                _v36_eod_options.append("HARVEST")
            if (not _v36_eod_tile.get("fed_today", False) and
                    int(_v36_get(_v36_eod_inventory, "WHEAT", 0) or 0) > 0):
                _v36_eod_options.append("FEED")
            if _v36_eod_tile.get("fertilizer_available", False):
                _v36_eod_options.append("COLLECT_FERTILIZER")
            if not _v36_eod_tile.get("cared_today", False):
                _v36_eod_options.append("CARE")
            for _v36_eod_option in _v36_eod_options:
                if (_v36_eod_x, _v36_eod_y, _v36_eod_option) not in _v36_eod_claimed:
                    _v36_eod_choice = _v36_eod_option
                    break
        if _v36_eod_choice is None:
            continue
        _v36_eod_claimed.add((_v36_eod_x, _v36_eod_y, _v36_eod_choice))
        if _v36_eod_index == 0:
            _v36_eod_action["farmer"] = [_v36_eod_choice]
        elif _v36_eod_index - 1 < len(_v36_eod_hands):
            _v36_eod_hands[_v36_eod_index - 1] = [_v36_eod_choice]
        _V36_EOD_TELEMETRY["replaced"] += 1
        _v36_eod_ops = _V36_EOD_TELEMETRY["operations"]
        _v36_eod_ops[_v36_eod_choice] = _v36_eod_ops.get(_v36_eod_choice, 0) + 1
    return _v36_eod_action

_v36_eod_policy.telemetry = _V36_EOD_TELEMETRY
_V36_POLICY = _v36_eod_policy
'''
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
