"""Select a compatible route from the opponent opening and first public shop.

The X544 and Moon branches are shadow-run with isolated RNG streams through
step 72, where the first town shop is public.  The conservative learned rule
keeps X544 for non-pasture openings and for YARN_STORE pasture openings;
other pasture openings use Moon.  The generator is specific to the H22
selector layout and refuses ambiguous sources.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


AGENT_START = "def agent(obs, configuration=None):\n    global _SELECTED_ROUTE\n"
AGENT_END = "\n\nagent.telemetry = _SELECTOR_TELEMETRY"


def shop_aware_selector_source(source: str, *, label: str) -> str:
    selector_anchor = source.find("def _selector_call(namespace, obs, configuration):")
    if selector_anchor < 0:
        raise ValueError("source lacks the H22 selector helper")
    start = source.find(AGENT_START, selector_anchor)
    if start < 0:
        raise ValueError("source lacks the H22 selector agent")
    end = source.find(AGENT_END, start)
    if end < 0:
        raise ValueError("source lacks the H22 selector telemetry marker")

    replacement = '''_SHOP_DECISION_STEP = 72
_SHOP_COUNTER = "YARN_STORE"
_SHOP_RNG = {"x544": None, "moon": None}
_SHOP_OPENING_PASTURE = False


def _shop_isolated_call(name, namespace, obs, configuration):
    process_rng = _selector_random.getstate()
    if _SHOP_RNG[name] is None:
        _SHOP_RNG[name] = process_rng
    try:
        _selector_random.setstate(_SHOP_RNG[name])
        action = _selector_call(
            namespace,
            _selector_copy.deepcopy(obs),
            _selector_copy.deepcopy(configuration),
        )
        _SHOP_RNG[name] = _selector_random.getstate()
        return _selector_copy.deepcopy(action)
    finally:
        _selector_random.setstate(process_rng)


def _shop_names(obs):
    town = _selector_get(obs, "town", {}) or {}
    values = _selector_get(town, "unlocked_shops", []) or []
    names = []
    for value in values:
        name = getattr(value, "name", str(value)).upper().split(".")[-1]
        names.append(name)
    return names


def agent(obs, configuration=None):
    global _SELECTED_ROUTE, _SHOP_OPENING_PASTURE
    step = _selector_step(obs)
    if step == 0:
        _SELECTED_ROUTE = None
        _SHOP_RNG["x544"] = None
        _SHOP_RNG["moon"] = None
        _SHOP_OPENING_PASTURE = False
        _SELECTOR_TELEMETRY["selected_route"] = None
        _SELECTOR_TELEMETRY["opening_disagreement"] = 0
        _SELECTOR_TELEMETRY["pasture_opening"] = False
        _SELECTOR_TELEMETRY["decision_step"] = _SHOP_DECISION_STEP
        _SELECTOR_TELEMETRY["first_shops"] = []
        _SELECTOR_TELEMETRY["yarn_counter"] = False
        _SELECTOR_TELEMETRY["predecision_disagreements"] = 0

    if _SELECTED_ROUTE is None:
        x544_action = _shop_isolated_call("x544", _X544_NS, obs, configuration)
        moon_action = _shop_isolated_call("moon", _MOON_NS, obs, configuration)
        if step == 0 and x544_action != moon_action:
            _SELECTOR_TELEMETRY["opening_disagreement"] += 1
        if step < _SHOP_DECISION_STEP:
            if step == 1:
                _SHOP_OPENING_PASTURE = (
                    _selector_opponent_has_opening_pasture(obs)
                )
                _SELECTOR_TELEMETRY["pasture_opening"] = _SHOP_OPENING_PASTURE
            if x544_action != moon_action:
                _SELECTOR_TELEMETRY["predecision_disagreements"] += 1
            return x544_action

        shops = _shop_names(obs)
        yarn_counter = _SHOP_COUNTER in shops
        _SELECTED_ROUTE = (
            "x544" if (not _SHOP_OPENING_PASTURE or yarn_counter) else "moon"
        )
        _SELECTOR_TELEMETRY["selected_route"] = _SELECTED_ROUTE
        _SELECTOR_TELEMETRY["first_shops"] = shops
        _SELECTOR_TELEMETRY["yarn_counter"] = yarn_counter
        return moon_action if _SELECTED_ROUTE == "moon" else x544_action

    namespace = _MOON_NS if _SELECTED_ROUTE == "moon" else _X544_NS
    return _shop_isolated_call(_SELECTED_ROUTE, namespace, obs, configuration)
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
    parser.add_argument("--label", default="shop72-yarn-counter")
    args = parser.parse_args()
    try:
        generated = shop_aware_selector_source(
            args.source.read_text(encoding="utf-8"),
            label=args.label,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(generated, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
