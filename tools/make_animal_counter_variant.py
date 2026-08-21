"""Append a bounded opponent-conditioned animal substitution overlay.

The overlay recognizes a named public farm fingerprint, then replaces an
already scheduled animal purchase and translates only the matching subsequent
pickups/placements.  It does not invent a purchase or alter unrelated actions.
"""

from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = r'''

# Generated bounded animal-counter experiment.
import copy as _ac_copy

_AC_BASE_AGENT = agent
_AC_PROFILE = {fingerprint_profile!r}
_AC_FINGERPRINT_STEP = {fingerprint_step}
_AC_START = {start}
_AC_STOP = {stop}
_AC_FROM = {from_animal!r}
_AC_TO = {to_animal!r}
_AC_ACTIVE = {{0: False, 1: False}}
_AC_PENDING_PICKUP = {{0: 0, 1: 0}}
_AC_PENDING_PLACE = {{0: 0, 1: 0}}
_AC_TELEMETRY = {{
    "profile": _AC_PROFILE,
    "fingerprint_step": _AC_FINGERPRINT_STEP,
    "active": False,
    "purchased": 0,
    "picked_up": 0,
    "placed": 0,
}}


def _ac_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _ac_matches(obs, seat):
    farms = list(_ac_get(obs, "farms", []) or [])
    opponent = 1 - seat
    if opponent < 0 or opponent >= len(farms):
        return False
    farm = farms[opponent]
    hands = list(_ac_get(farm, "hands", []) or [])
    kinds = {{}}
    crops = {{}}
    animals = {{}}
    for row in _ac_get(farm, "tiles", []) or []:
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
    if _AC_PROFILE == "uri":
        return (
            len(hands) == 4
            and kinds.get("PASTURE", 0) == 5
            and kinds.get("PLANT", 0) == 13
            and crops.get("WHEAT", 0) == 5
            and crops.get("MELON", 0) == 5
            and crops.get("STRAWBERRY", 0) == 3
        )
    if _AC_PROFILE == "johnson":
        money = float(_ac_get(farm, "money", 0) or 0)
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
    return False


def _ac_translate_unit(order, seat):
    raw = list(order or ["PASS"])
    if len(raw) < 2 or raw[1] != _AC_FROM:
        return raw
    quantity = max(1, int(raw[2] if len(raw) > 2 else 1))
    if raw[0] == "PICKUP" and _AC_PENDING_PICKUP[seat] >= quantity:
        raw[1] = _AC_TO
        _AC_PENDING_PICKUP[seat] -= quantity
        _AC_PENDING_PLACE[seat] += quantity
        _AC_TELEMETRY["picked_up"] += quantity
    elif raw[0] == "PLACE" and _AC_PENDING_PLACE[seat] >= quantity:
        raw[1] = _AC_TO
        _AC_PENDING_PLACE[seat] -= quantity
        _AC_TELEMETRY["placed"] += quantity
    return raw


def agent(obs, configuration=None):
    action = _ac_copy.deepcopy(_AC_BASE_AGENT(obs, configuration))
    try:
        step = int(_ac_get(obs, "step", 0) or 0)
        seat = 1 if int(_ac_get(obs, "player", 0) or 0) == 1 else 0
        if step == 0:
            _AC_ACTIVE[seat] = False
            _AC_PENDING_PICKUP[seat] = 0
            _AC_PENDING_PLACE[seat] = 0
        if step == _AC_FINGERPRINT_STEP:
            _AC_ACTIVE[seat] = _ac_matches(obs, seat)
            _AC_TELEMETRY["active"] = _AC_ACTIVE[seat]
        if not _AC_ACTIVE[seat] or globals().get("_SELECTED_ROUTE") != "x544":
            return action
        if not _AC_START <= step < _AC_STOP:
            return action

        market = []
        for order in action.get("market") or []:
            raw = list(order)
            if len(raw) >= 3 and raw[0] == "BUY_ANIMAL" and raw[1] == _AC_FROM:
                quantity = max(0, int(raw[2] or 0))
                if quantity > 0:
                    raw[1] = _AC_TO
                    _AC_PENDING_PICKUP[seat] += quantity
                    _AC_TELEMETRY["purchased"] += quantity
            market.append(raw)
        action["market"] = market
        action["farmer"] = _ac_translate_unit(action.get("farmer"), seat)
        action["hands"] = [
            _ac_translate_unit(order, seat) for order in action.get("hands") or []
        ]
        return action
    except Exception:
        return action


agent.telemetry = _AC_TELEMETRY
__version__ = "animal-counter-{label}"
animal_counter_kaggle_entrypoint = agent
'''


def render_variant(
    source: str,
    *,
    fingerprint_profile: str = "uri",
    fingerprint_step: int,
    start: int,
    stop: int,
    from_animal: str,
    to_animal: str,
    label: str,
) -> str:
    if fingerprint_profile not in {"uri", "johnson"}:
        raise ValueError("fingerprint profile must be uri or johnson")
    if fingerprint_step < 0:
        raise ValueError("fingerprint step must be non-negative")
    if not 0 <= start < stop:
        raise ValueError("window must satisfy 0 <= start < stop")
    allowed = {"GOOSE", "COW", "SHEEP"}
    if from_animal not in allowed or to_animal not in allowed:
        raise ValueError("animals must be GOOSE, COW, or SHEEP")
    if from_animal == to_animal:
        raise ValueError("source and target animal must differ")
    return source.rstrip() + "\n" + TEMPLATE.format(
        fingerprint_profile=fingerprint_profile,
        fingerprint_step=fingerprint_step,
        start=start,
        stop=stop,
        from_animal=from_animal,
        to_animal=to_animal,
        label=label,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--fingerprint-profile", choices=("uri", "johnson"), default="uri")
    parser.add_argument("--fingerprint-step", type=int, default=112)
    parser.add_argument("--start", type=int, default=264)
    parser.add_argument("--stop", type=int, default=276)
    parser.add_argument("--from-animal", choices=("GOOSE", "COW", "SHEEP"), default="COW")
    parser.add_argument("--to-animal", choices=("GOOSE", "COW", "SHEEP"), default="SHEEP")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    try:
        generated = render_variant(
            args.source.read_text(encoding="utf-8"),
            fingerprint_profile=args.fingerprint_profile,
            fingerprint_step=args.fingerprint_step,
            start=args.start,
            stop=args.stop,
            from_animal=args.from_animal,
            to_animal=args.to_animal,
            label=args.label,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(generated, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
