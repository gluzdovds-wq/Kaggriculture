"""Create a V36 watering-survival ablation without changing unit positions."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--skip-day-parity", type=int, choices=(0, 1), default=1)
    parser.add_argument("--reuse-harvest", action="store_true")
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    overlay = f'''
# Generated H01 probe. It never suppresses same-turn plant-day WATER because
# an empty pre-action tile is left unchanged.
import copy as _v36_sparse_copy
_V36_SPARSE_BASE = _V36_POLICY
_V36_SPARSE_PARITY = {args.skip_day_parity!r}
_V36_SPARSE_REUSE_HARVEST = {args.reuse_harvest!r}
_V36_SPARSE_TELEMETRY = {{"skipped": 0, "harvest_reuse": 0}}

def _v36_sparse_policy(obs, configuration=None):
    _v36_sparse_action = _v36_sparse_copy.deepcopy(_V36_SPARSE_BASE(obs, configuration))
    _v36_sparse_day = int(_v36_get(obs, "day", 0) or 0)
    if _v36_sparse_day % 2 != _V36_SPARSE_PARITY:
        return _v36_sparse_action
    _v36_sparse_player = int(_v36_get(obs, "player", 0) or 0)
    _v36_sparse_farms = list(_v36_get(obs, "farms", []) or [])
    if _v36_sparse_player >= len(_v36_sparse_farms):
        return _v36_sparse_action
    _v36_sparse_farm = _v36_sparse_farms[_v36_sparse_player]
    _v36_sparse_tiles = _v36_get(_v36_sparse_farm, "tiles", []) or []
    _v36_sparse_positions = [_v36_get(_v36_sparse_farm, "farmer", None)]
    _v36_sparse_positions.extend(_v36_get(_v36_sparse_farm, "hands", []) or [])
    _v36_sparse_hands = _v36_sparse_action.get("hands", []) or []
    _v36_sparse_actions = [_v36_sparse_action.get("farmer") or ["PASS"],
                           *_v36_sparse_hands]
    for _v36_sparse_index, (_v36_sparse_position, _v36_sparse_unit_action) in enumerate(
            zip(_v36_sparse_positions, _v36_sparse_actions)):
        if (not _v36_sparse_unit_action or _v36_sparse_unit_action[0] != "WATER" or
                not _v36_sparse_position or len(_v36_sparse_position) < 2):
            continue
        _v36_sparse_x, _v36_sparse_y = map(int, _v36_sparse_position[:2])
        try:
            _v36_sparse_tile = _v36_sparse_tiles[_v36_sparse_y][_v36_sparse_x]
        except (IndexError, TypeError):
            continue
        if (not isinstance(_v36_sparse_tile, dict) or
                _v36_sparse_tile.get("kind") != "PLANT" or
                int(_v36_sparse_tile.get("planted_day", _v36_sparse_day) or 0)
                >= _v36_sparse_day or
                int(_v36_sparse_tile.get("consecutive_unwatered", 0) or 0) != 0):
            continue
        _v36_sparse_replacement = ["PASS"]
        if _V36_SPARSE_REUSE_HARVEST:
            _v36_sparse_crop = _v36_sparse_tile.get("crop")
            _v36_sparse_age = (_v36_sparse_day -
                               int(_v36_sparse_tile.get("planted_day", 0) or 0))
            _v36_sparse_ongoing = _v36_sparse_crop in {{"TOMATO", "STRAWBERRY"}}
            _v36_sparse_peak = {{"WHEAT": 4, "CARROT": 3, "MELON": 12}}.get(
                _v36_sparse_crop, 0)
            if ((_v36_sparse_tile.get("yield_units", 0) or 0) > 0 and
                    (_v36_sparse_ongoing or _v36_sparse_age >= _v36_sparse_peak)):
                _v36_sparse_replacement = ["HARVEST"]
                _V36_SPARSE_TELEMETRY["harvest_reuse"] += 1
        if _v36_sparse_index == 0:
            _v36_sparse_action["farmer"] = _v36_sparse_replacement
        elif _v36_sparse_index - 1 < len(_v36_sparse_hands):
            _v36_sparse_hands[_v36_sparse_index - 1] = _v36_sparse_replacement
        _V36_SPARSE_TELEMETRY["skipped"] += 1
    return _v36_sparse_action

_v36_sparse_policy.telemetry = _V36_SPARSE_TELEMETRY
_V36_POLICY = _v36_sparse_policy
'''
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
