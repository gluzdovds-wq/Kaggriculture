"""Probe YARN_STORE with one Moon action, then classify the public response.

X544 and Moon are compatible through step 71.  For pasture openings with a
first YARN_STORE, this selector executes Moon's step-72 action, observes the
opponent's public step-73 hire count, and selects X544 only for an aggressive
response.  Other contexts retain the N36 rule and freeze at step 72.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


AGENT_START = "def agent(obs, configuration=None):\n"
AGENT_END = "\n\nagent.telemetry = _SELECTOR_TELEMETRY"


def shop_probe_selector_source(
    source: str,
    *,
    aggressive_min_hands: int,
    label: str,
) -> str:
    if aggressive_min_hands < 1:
        raise ValueError("aggressive hand threshold must be positive")
    selector_anchor = source.find("def _selector_call(namespace, obs, configuration):")
    if selector_anchor < 0:
        raise ValueError("source lacks the H22 selector helper")
    start = source.find(AGENT_START, selector_anchor)
    if start < 0:
        raise ValueError("source lacks the H22 selector agent")
    end = source.find(AGENT_END, start)
    if end < 0:
        raise ValueError("source lacks the H22 selector telemetry marker")

    replacement = f'''_PROBE_SHOP_STEP = 72
_PROBE_RESPONSE_STEP = 73
_PROBE_SHOP_COUNTER = "YARN_STORE"
_PROBE_AGGRESSIVE_MIN_HANDS = {aggressive_min_hands}
_PROBE_RNG = {{"x544": None, "moon": None}}
_PROBE_OPENING_PASTURE = False
_PROBE_YARN = False


def _probe_isolated_call(name, namespace, obs, configuration):
    process_rng = _selector_random.getstate()
    if _PROBE_RNG[name] is None:
        _PROBE_RNG[name] = process_rng
    try:
        _selector_random.setstate(_PROBE_RNG[name])
        action = _selector_call(
            namespace,
            _selector_copy.deepcopy(obs),
            _selector_copy.deepcopy(configuration),
        )
        _PROBE_RNG[name] = _selector_random.getstate()
        return _selector_copy.deepcopy(action)
    finally:
        _selector_random.setstate(process_rng)


def _probe_shop_names(obs):
    town = _selector_get(obs, "town", {{}}) or {{}}
    values = _selector_get(town, "unlocked_shops", []) or []
    return [getattr(value, "name", str(value)).upper().split(".")[-1]
            for value in values]


def _probe_opponent_hands(obs):
    player = int(_selector_get(obs, "player", 0) or 0)
    farms = list(_selector_get(obs, "farms", []) or [])
    opponent = 1 - player
    if opponent < 0 or opponent >= len(farms):
        return 0
    return len(_selector_get(farms[opponent], "hands", []) or [])


def agent(obs, configuration=None):
    global _SELECTED_ROUTE, _PROBE_OPENING_PASTURE, _PROBE_YARN
    step = _selector_step(obs)
    if step == 0:
        _SELECTED_ROUTE = None
        _PROBE_RNG["x544"] = None
        _PROBE_RNG["moon"] = None
        _PROBE_OPENING_PASTURE = False
        _PROBE_YARN = False
        _SELECTOR_TELEMETRY["selected_route"] = None
        _SELECTOR_TELEMETRY["opening_disagreement"] = 0
        _SELECTOR_TELEMETRY["pasture_opening"] = False
        _SELECTOR_TELEMETRY["decision_step"] = _PROBE_SHOP_STEP
        _SELECTOR_TELEMETRY["first_shops"] = []
        _SELECTOR_TELEMETRY["yarn_probe"] = False
        _SELECTOR_TELEMETRY["response_hands"] = None
        _SELECTOR_TELEMETRY["predecision_disagreements"] = 0

    if _SELECTED_ROUTE is None:
        x544_action = _probe_isolated_call("x544", _X544_NS, obs, configuration)
        moon_action = _probe_isolated_call("moon", _MOON_NS, obs, configuration)
        if step == 0 and x544_action != moon_action:
            _SELECTOR_TELEMETRY["opening_disagreement"] += 1
        if step < _PROBE_SHOP_STEP:
            if step == 1:
                _PROBE_OPENING_PASTURE = (
                    _selector_opponent_has_opening_pasture(obs)
                )
                _SELECTOR_TELEMETRY["pasture_opening"] = _PROBE_OPENING_PASTURE
            if x544_action != moon_action:
                _SELECTOR_TELEMETRY["predecision_disagreements"] += 1
            return x544_action

        if step == _PROBE_SHOP_STEP:
            shops = _probe_shop_names(obs)
            _SELECTOR_TELEMETRY["first_shops"] = shops
            if not _PROBE_OPENING_PASTURE:
                _SELECTED_ROUTE = "x544"
                _SELECTOR_TELEMETRY["selected_route"] = _SELECTED_ROUTE
                return x544_action
            _PROBE_YARN = _PROBE_SHOP_COUNTER in shops
            if not _PROBE_YARN:
                _SELECTED_ROUTE = "moon"
                _SELECTOR_TELEMETRY["selected_route"] = _SELECTED_ROUTE
                return moon_action
            _SELECTOR_TELEMETRY["yarn_probe"] = True
            _SELECTOR_TELEMETRY["decision_step"] = _PROBE_RESPONSE_STEP
            return moon_action

        hands = _probe_opponent_hands(obs)
        _SELECTED_ROUTE = (
            "x544" if hands >= _PROBE_AGGRESSIVE_MIN_HANDS else "moon"
        )
        _SELECTOR_TELEMETRY["selected_route"] = _SELECTED_ROUTE
        _SELECTOR_TELEMETRY["response_hands"] = hands
        return moon_action if _SELECTED_ROUTE == "moon" else x544_action

    namespace = _MOON_NS if _SELECTED_ROUTE == "moon" else _X544_NS
    return _probe_isolated_call(_SELECTED_ROUTE, namespace, obs, configuration)
'''
    generated = source[:start] + replacement + source[end:]
    versions = list(
        re.finditer(r'^__version__ = "([^"\r\n]+)"$', generated, flags=re.MULTILINE)
    )
    if not versions:
        raise ValueError("source lacks a version marker")
    final = versions[-1]
    version = f'__version__ = "{final.group(1)}-{label}"'
    return generated[: final.start()] + version + generated[final.end() :]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--aggressive-min-hands", type=int, default=4)
    parser.add_argument("--label", default="shop73-yarn-probe")
    args = parser.parse_args()
    try:
        generated = shop_probe_selector_source(
            args.source.read_text(encoding="utf-8"),
            aggressive_min_hands=args.aggressive_min_hands,
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
