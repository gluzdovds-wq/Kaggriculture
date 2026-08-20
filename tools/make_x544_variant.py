"""Create reproducible X544 variants for local ablation experiments."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--all-crop-seed-trim", action="store_true")
    parser.add_argument("--eod-harvest", action="store_true")
    parser.add_argument("--preempt-ratio", type=float)
    parser.add_argument("--preempt-fraction", type=float)
    parser.add_argument("--preempt-max-batch", type=int)
    args = parser.parse_args()
    if not (
        args.all_crop_seed_trim
        or args.eod_harvest
        or args.preempt_ratio is not None
        or args.preempt_fraction is not None
        or args.preempt_max_batch is not None
    ):
        parser.error("enable at least one variant")

    source = args.source.read_text(encoding="utf-8")
    overlay = f'''
# Generated X544 ablation overlay.  Each switch is deliberately observation-only
# and preserves the embedded route, expert selector, and market controllers.
import copy as _xv_copy
_XV_BASE_AGENT = agent
_XV_ALL_CROP_SEED_TRIM = {args.all_crop_seed_trim!r}
_XV_EOD_HARVEST = {args.eod_harvest!r}
_XV_PREEMPT_RATIO = {args.preempt_ratio!r}
_XV_PREEMPT_FRACTION = {args.preempt_fraction!r}
_XV_PREEMPT_MAX_BATCH = {args.preempt_max_batch!r}
_XV_FIRST_YIELD_DAY = {{"TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}}
_XV_PEAK_DAY = {{"WHEAT": 4, "CARROT": 3, "MELON": 12}}
_XV_ONGOING = {{"TOMATO", "STRAWBERRY"}}
_XV_SAFE_LAST_HOUR = {{"NORTH", "SOUTH", "EAST", "WEST", "PASS"}}
_XV_TELEMETRY = {{"trimmed_orders": 0, "trimmed_units": 0, "eod_harvests": 0}}

# The embedded functions resolve these globals in _X540_NS at call time.
if _XV_PREEMPT_RATIO is not None:
    _X540_NS["_PREEMPT_MIN_PRICE_RATIO"] = float(_XV_PREEMPT_RATIO)
if _XV_PREEMPT_FRACTION is not None:
    _X540_NS["_PREEMPT_FRACTION"] = float(_XV_PREEMPT_FRACTION)
if _XV_PREEMPT_MAX_BATCH is not None:
    _X540_NS["_PREEMPT_MAX_BATCH"] = int(_XV_PREEMPT_MAX_BATCH)


def _xv_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _xv_trim_all_crop_seeds(obs, action, step):
    if not _XV_ALL_CROP_SEED_TRIM:
        return action
    private = _xv_get(obs, "private", {{}}) or {{}}
    seeds = {{
        str(key): max(0, int(value or 0))
        for key, value in dict(_xv_get(private, "seeds", {{}}) or {{}}).items()
    }}
    tape = list(_X540_NS.get("_ACTIONS") or [])
    if not tape:
        return action

    action = _xv_copy.deepcopy(action)
    market = []
    for raw in action.get("market") or []:
        order = list(raw)
        if (len(order) >= 3 and order[0] == "BUY_SEED" and
                order[1] in _XV_FIRST_YIELD_DAY):
            crop = str(order[1])
            last_plant_day = _LAST_SEASON_DAY - _XV_FIRST_YIELD_DAY[crop]
            later = 0
            for ahead in range(step + 1, len(tape)):
                if ahead // 24 > last_plant_day:
                    break
                later += _plant_count(tape[ahead], crop)
            need = _plant_count(action, crop) + later
            have = seeds.get(crop, 0)
            original = max(0, int(order[2] or 0))
            quantity = min(original, max(0, need - have))
            if quantity < original:
                _XV_TELEMETRY["trimmed_orders"] += 1
                _XV_TELEMETRY["trimmed_units"] += original - quantity
            if quantity <= 0:
                continue
            order[2] = quantity
            seeds[crop] = have + quantity
        market.append(order)
    action["market"] = market[:10]
    return action


def _xv_eod_harvest(obs, action, step):
    if not _XV_EOD_HARVEST or int(_xv_get(obs, "hour", step % 24) or 0) != 23:
        return action
    player = int(_xv_get(obs, "player", 0) or 0)
    farms = list(_xv_get(obs, "farms", []) or [])
    if player >= len(farms):
        return action
    farm = farms[player]
    day = int(_xv_get(obs, "day", step // 24) or 0)
    tiles = _xv_get(farm, "tiles", []) or []
    positions = [_xv_get(farm, "farmer", None)]
    positions.extend(_xv_get(farm, "hands", []) or [])
    action = _xv_copy.deepcopy(action)
    hands = action.get("hands", []) or []
    unit_actions = [action.get("farmer") or ["PASS"], *hands]
    claimed = set()
    for index, (position, base_action) in enumerate(zip(positions, unit_actions)):
        if (not base_action or base_action[0] not in _XV_SAFE_LAST_HOUR or
                not position or len(position) < 2):
            continue
        x, y = map(int, position[:2])
        try:
            tile = tiles[y][x]
        except (IndexError, TypeError):
            continue
        if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
            continue
        crop = tile.get("crop")
        age = day - int(tile.get("planted_day", 0) or 0)
        mature = crop in _XV_ONGOING or age >= _XV_PEAK_DAY.get(crop, 10**9)
        if not mature or int(tile.get("yield_units", 0) or 0) <= 0 or (x, y) in claimed:
            continue
        claimed.add((x, y))
        if index == 0:
            action["farmer"] = ["HARVEST"]
        elif index - 1 < len(hands):
            hands[index - 1] = ["HARVEST"]
        _XV_TELEMETRY["eod_harvests"] += 1
    return action


def agent(obs, configuration=None):
    action = _XV_BASE_AGENT(obs, configuration)
    step = _step(obs)
    action = _xv_trim_all_crop_seeds(obs, action, step)
    return _xv_eod_harvest(obs, action, step)


agent.telemetry = _XV_TELEMETRY
__version__ = (
    "X544-local-trim{{int(_XV_ALL_CROP_SEED_TRIM)}}-eod{{int(_XV_EOD_HARVEST)}}"
    "-pr{{_XV_PREEMPT_RATIO}}-pf{{_XV_PREEMPT_FRACTION}}-pb{{_XV_PREEMPT_MAX_BATCH}}"
)
'''
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
