"""Build a single-file early-family selector from two compatible agents."""

from __future__ import annotations

import argparse
import base64
from pathlib import Path


def encoded_source(path: Path) -> str:
    return base64.b85encode(path.read_bytes()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("x544", type=Path)
    parser.add_argument("moon", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    x544_b85 = encoded_source(args.x544)
    moon_b85 = encoded_source(args.moon)
    generated = f'''from __future__ import annotations

import base64
import copy as _selector_copy
import random as _selector_random


# Both sources are public, hash-bound agents.  They share the exact step-0
# opening, then diverge only when the first town shop becomes observable.
_X544_SOURCE_B85 = {x544_b85!r}
_MOON_SOURCE_B85 = {moon_b85!r}
_X544_NS = {{"__name__": "x544_selector_branch"}}
_MOON_NS = {{"__name__": "moon_selector_branch"}}
exec(
    compile(
        base64.b85decode(_X544_SOURCE_B85.encode("ascii")).decode("utf-8"),
        "x544_selector_branch.py",
        "exec",
    ),
    _X544_NS,
    _X544_NS,
)
exec(
    compile(
        base64.b85decode(_MOON_SOURCE_B85.encode("ascii")).decode("utf-8"),
        "moon_selector_branch.py",
        "exec",
    ),
    _MOON_NS,
    _MOON_NS,
)

_SELECTED_ROUTE = None
_SELECTOR_TELEMETRY = {{
    "selected_route": None,
    "opening_disagreement": 0,
    "pasture_opening": False,
}}


def _selector_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _selector_step(obs):
    value = _selector_get(obs, "step", None)
    if value is not None:
        return int(value or 0)
    return int(_selector_get(obs, "day", 0) or 0) * 24 + int(
        _selector_get(obs, "hour", 0) or 0
    )


def _selector_opponent_has_opening_pasture(obs):
    player = int(_selector_get(obs, "player", 0) or 0)
    farms = list(_selector_get(obs, "farms", []) or [])
    opponent = 1 - player
    if opponent < 0 or opponent >= len(farms):
        return False
    tiles = _selector_get(farms[opponent], "tiles", []) or []
    for row in tiles:
        for tile in row or []:
            if isinstance(tile, dict) and tile.get("kind") == "PASTURE":
                return True
    return False


def _selector_call(namespace, obs, configuration):
    branch = namespace["agent"]
    code = getattr(branch, "__code__", None)
    if code is not None and code.co_argcount >= 2:
        return branch(obs, configuration)
    return branch(obs)


def agent(obs, configuration=None):
    global _SELECTED_ROUTE
    step = _selector_step(obs)
    if step == 0:
        _SELECTED_ROUTE = None
        # Moon needs a step-0 call to initialize its compatible route state.
        # Run that discarded branch on copies and restore Python's global RNG:
        # local agents share a process, so shadow initialization must not alter
        # the live observation/configuration or an opponent's random stream.
        moon_obs = _selector_copy.deepcopy(obs)
        moon_configuration = _selector_copy.deepcopy(configuration)
        x544_action = _selector_call(_X544_NS, obs, configuration)
        random_state = _selector_random.getstate()
        try:
            moon_action = _selector_call(_MOON_NS, moon_obs, moon_configuration)
        finally:
            _selector_random.setstate(random_state)
        if x544_action != moon_action:
            _SELECTOR_TELEMETRY["opening_disagreement"] += 1
        return x544_action

    if _SELECTED_ROUTE is None:
        pasture_opening = _selector_opponent_has_opening_pasture(obs)
        _SELECTED_ROUTE = "moon" if pasture_opening else "x544"
        _SELECTOR_TELEMETRY["selected_route"] = _SELECTED_ROUTE
        _SELECTOR_TELEMETRY["pasture_opening"] = pasture_opening

    namespace = _MOON_NS if _SELECTED_ROUTE == "moon" else _X544_NS
    return _selector_call(namespace, obs, configuration)


agent.telemetry = _SELECTOR_TELEMETRY
__version__ = "H22-early-public-family-selector-v1"

# kaggle-environments selects the last callable inserted into module globals.
kaggle_entrypoint = agent
'''
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(generated, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
