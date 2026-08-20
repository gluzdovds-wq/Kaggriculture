"""Create a V36 probe that delays safe sales across a town-consumption tick."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--start-step", type=int, default=72)
    parser.add_argument("--stop-step", type=int, default=715)
    parser.add_argument("--cash-reserve", type=int, default=500)
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    overlay = f'''
# Generated H14 market-only probe: hold eligible sales over the town tick.
import copy as _v36_delay_copy
_V36_DELAY_BASE = _V36_POLICY
_V36_DELAY_START = {args.start_step!r}
_V36_DELAY_STOP = {args.stop_step!r}
_V36_DELAY_CASH_RESERVE = {args.cash_reserve!r}
_V36_DELAY_PRODUCTS = {{"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
                       "EGG", "MILK", "WOOL"}}
_V36_DELAY_SHOPS = {{
    "BAKERY": {{"EGG", "WHEAT"}},
    "PIZZA_SHOP": {{"MILK", "TOMATO", "WHEAT"}},
    "BRUNCH_SPOT": {{"EGG", "WHEAT", "STRAWBERRY"}},
    "ICE_CREAM_SHOP": {{"STRAWBERRY", "MILK", "WHEAT"}},
    "PET_CAFE": {{"CARROT"}},
    "SMOOTHIE_SHOP": {{"STRAWBERRY", "MILK"}},
    "FARMERS_MARKET": {{"WHEAT", "CARROT", "TOMATO", "STRAWBERRY"}},
    "YARN_STORE": {{"WOOL"}},
}}
_V36_DELAY_STATE = {{"last_step": -1, "deferred": {{}}}}
_V36_DELAY_TELEMETRY = {{"events": 0, "units": 0, "flushes": 0}}

def _v36_delay_policy(obs, configuration=None):
    _v36_delay_action = _v36_delay_copy.deepcopy(_V36_DELAY_BASE(obs, configuration))
    _v36_delay_step = int(_v36_get(obs, "step", 0) or 0)
    if _v36_delay_step <= _V36_DELAY_STATE["last_step"]:
        _V36_DELAY_STATE["deferred"] = {{}}
    _V36_DELAY_STATE["last_step"] = _v36_delay_step
    _v36_delay_market = list(_v36_delay_action.get("market", []) or [])

    # Flush yesterday's/tick's inventory before processing new candidate sales.
    _v36_delay_deferred = _V36_DELAY_STATE["deferred"]
    if _v36_delay_deferred:
        _v36_delay_private = _v36_get(obs, "private", {{}}) or {{}}
        _v36_delay_shed = _v36_get(_v36_delay_private, "shed", {{}}) or {{}}
        for _v36_delay_item, _v36_delay_quantity in sorted(_v36_delay_deferred.items()):
            _v36_delay_available = int(_v36_get(_v36_delay_shed, _v36_delay_item, 0) or 0)
            _v36_delay_sell = min(int(_v36_delay_quantity), _v36_delay_available)
            if _v36_delay_sell > 0:
                _v36_delay_market.insert(0, ["SELL", _v36_delay_item, _v36_delay_sell])
                _V36_DELAY_TELEMETRY["flushes"] += 1
        _V36_DELAY_STATE["deferred"] = {{}}

    _v36_delay_farms = list(_v36_get(obs, "farms", []) or [])
    _v36_delay_player = int(_v36_get(obs, "player", 0) or 0)
    _v36_delay_farm = (_v36_delay_farms[_v36_delay_player]
                       if _v36_delay_player < len(_v36_delay_farms) else {{}})
    _v36_delay_money = float(_v36_get(_v36_delay_farm, "money", 0) or 0)
    _v36_delay_has_spend = any(
        _v36_delay_order and _v36_delay_order[0] in
        {{"BUY_PRODUCT", "BUY_SEED", "BUY_ANIMAL", "HIRE", "BUY_LAND"}}
        for _v36_delay_order in _v36_delay_market
    )
    _v36_delay_is_tick = _v36_delay_step % 4 == 0
    if (_V36_DELAY_START <= _v36_delay_step <= _V36_DELAY_STOP and
            _v36_delay_is_tick and not _v36_delay_has_spend and
            _v36_delay_money >= _V36_DELAY_CASH_RESERVE):
        _v36_delay_town = _v36_get(obs, "town", {{}}) or {{}}
        _v36_delay_consumed = set()
        for _v36_delay_shop in _v36_get(_v36_delay_town, "unlocked_shops", []) or []:
            _v36_delay_consumed.update(_V36_DELAY_SHOPS.get(_v36_delay_shop, set()))
        if _v36_delay_step % 24 == 0:
            _v36_delay_consumed.update(_V36_DELAY_PRODUCTS)
        _v36_delay_kept = []
        _v36_delay_hold = {{}}
        for _v36_delay_order in _v36_delay_market:
            if (len(_v36_delay_order) >= 3 and _v36_delay_order[0] == "SELL" and
                    _v36_delay_order[1] in _v36_delay_consumed):
                _v36_delay_item = str(_v36_delay_order[1])
                _v36_delay_hold[_v36_delay_item] = (
                    _v36_delay_hold.get(_v36_delay_item, 0) +
                    max(0, int(_v36_delay_order[2])))
            else:
                _v36_delay_kept.append(_v36_delay_order)
        if _v36_delay_hold:
            _V36_DELAY_STATE["deferred"] = _v36_delay_hold
            _V36_DELAY_TELEMETRY["events"] += 1
            _V36_DELAY_TELEMETRY["units"] += sum(_v36_delay_hold.values())
            _v36_delay_market = _v36_delay_kept

    _v36_delay_action["market"] = _v36_delay_market
    return _v36_delay_action

_v36_delay_policy.telemetry = _V36_DELAY_TELEMETRY
_V36_POLICY = _v36_delay_policy
'''
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
