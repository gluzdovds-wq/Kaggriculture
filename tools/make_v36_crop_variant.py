"""Create a reproducible crop-substitution experiment from an embedded V36 agent.

This is deliberately a route-level economic probe, not a production policy.  It
replaces matching BUY_SEED and PLANT actions in a bounded step window, rebuilds
the normal V36 hybrid around the changed route, and optionally sells harvested
units of the replacement crop on the next available market phase.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--from-crop", required=True)
    parser.add_argument("--to-crop", required=True)
    parser.add_argument("--start-step", type=int, default=0)
    parser.add_argument("--stop-step", type=int, default=718)
    parser.add_argument("--auto-sell", action="store_true")
    parser.add_argument("--harvest-age", type=int)
    args = parser.parse_args()

    if args.start_step < 0 or args.stop_step < args.start_step:
        raise ValueError("invalid inclusive step window")

    source = args.source.read_text(encoding="utf-8")
    mutation = f'''
# Generated crop-substitution probe.  This intentionally preserves every
# movement/service action and all V36 feedback experts.
import copy as _v36_crop_copy
_V36_CROP_FROM = {args.from_crop.upper()!r}
_V36_CROP_TO = {args.to_crop.upper()!r}
_V36_CROP_START = {args.start_step!r}
_V36_CROP_STOP = {args.stop_step!r}
_V36_CROP_AUTO_SELL = {args.auto_sell!r}
_V36_CROP_HARVEST_AGE = {args.harvest_age!r}
_V36_CROP_ROUTE = _v36_crop_copy.deepcopy(_V36_ROUTE)
_V36_CROP_BUYS_REPLACED = 0
_V36_CROP_PLANTS_REPLACED = 0
for _v36_crop_step, _v36_crop_action in enumerate(_V36_CROP_ROUTE):
    if not (_V36_CROP_START <= _v36_crop_step <= _V36_CROP_STOP):
        continue
    for _v36_crop_order in _v36_crop_action.get("market", []) or []:
        if (_v36_crop_order and _v36_crop_order[0] == "BUY_SEED" and
                len(_v36_crop_order) > 1 and
                _v36_crop_order[1] == _V36_CROP_FROM):
            _v36_crop_order[1] = _V36_CROP_TO
            _V36_CROP_BUYS_REPLACED += int(_v36_crop_order[2])
    _v36_crop_units = [_v36_crop_action.get("farmer") or ["PASS"]]
    _v36_crop_units.extend(_v36_crop_action.get("hands") or [])
    for _v36_crop_unit in _v36_crop_units:
        if (_v36_crop_unit and _v36_crop_unit[0] == "PLANT" and
                len(_v36_crop_unit) > 1 and
                _v36_crop_unit[1] == _V36_CROP_FROM):
            _v36_crop_unit[1] = _V36_CROP_TO
            _V36_CROP_PLANTS_REPLACED += 1

_V36_CROP_BASE_POLICY = _v36_build_policy(_V36_CROP_ROUTE, _V36_CONFIG)

def _v36_crop_policy(obs, configuration=None):
    _v36_crop_action = _V36_CROP_BASE_POLICY(obs, configuration)
    if _V36_CROP_HARVEST_AGE is not None:
        _v36_crop_player = int(_v36_get(obs, "player", 0) or 0)
        _v36_crop_farms = list(_v36_get(obs, "farms", []) or [])
        _v36_crop_farm = (_v36_crop_farms[_v36_crop_player]
                          if _v36_crop_player < len(_v36_crop_farms) else {{}})
        _v36_crop_tiles = _v36_get(_v36_crop_farm, "tiles", []) or []
        _v36_crop_positions = [_v36_get(_v36_crop_farm, "farmer", None)]
        _v36_crop_positions.extend(_v36_get(_v36_crop_farm, "hands", []) or [])
        _v36_crop_keys = [("farmer", 0)]
        _v36_crop_keys.extend(("hands", _v36_crop_i)
                              for _v36_crop_i in range(len(_v36_crop_positions) - 1))
        _v36_crop_day = int(_v36_get(obs, "day", 0) or 0)
        for _v36_crop_position, (_v36_crop_key, _v36_crop_index) in zip(
                _v36_crop_positions, _v36_crop_keys):
            if not _v36_crop_position or len(_v36_crop_position) < 2:
                continue
            _v36_crop_x, _v36_crop_y = map(int, _v36_crop_position[:2])
            try:
                _v36_crop_tile = _v36_crop_tiles[_v36_crop_y][_v36_crop_x]
            except (IndexError, TypeError):
                continue
            if (not isinstance(_v36_crop_tile, dict) or
                    _v36_crop_tile.get("kind") != "PLANT" or
                    _v36_crop_tile.get("crop") != _V36_CROP_TO or
                    int(_v36_crop_tile.get("yield_units", 0) or 0) <= 0 or
                    _v36_crop_day - int(_v36_crop_tile.get("planted_day", 0) or 0)
                    < int(_V36_CROP_HARVEST_AGE)):
                continue
            if _v36_crop_key == "farmer":
                _v36_crop_action["farmer"] = ["HARVEST"]
            else:
                _v36_crop_hands = _v36_crop_action.get("hands", []) or []
                if _v36_crop_index < len(_v36_crop_hands):
                    _v36_crop_hands[_v36_crop_index] = ["HARVEST"]
    if not _V36_CROP_AUTO_SELL:
        return _v36_crop_action
    _v36_crop_private = _v36_get(obs, "private", {{}}) or {{}}
    _v36_crop_shed = _v36_get(_v36_crop_private, "shed", {{}}) or {{}}
    _v36_crop_quantity = int(_v36_get(_v36_crop_shed, _V36_CROP_TO, 0) or 0)
    if _v36_crop_quantity <= 0:
        return _v36_crop_action
    _v36_crop_market = list(_v36_crop_action.get("market", []) or [])
    _v36_crop_market.append(["SELL", _V36_CROP_TO, _v36_crop_quantity])
    _v36_crop_action["market"] = _v36_crop_market
    return _v36_crop_action

_V36_POLICY = _v36_crop_policy
'''
    output = source.rstrip() + "\n\n" + mutation.lstrip()
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(output, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
