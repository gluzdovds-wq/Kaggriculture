"""Delay the compatible X544/Moon route choice to a public checkpoint.

Both branches receive every live observation before the decision and keep an
independent Python RNG stream.  The physical action is X544's common-opening
action until the checkpoint.  At the checkpoint a deliberately tiny public
rule selects Moon when the opponent still has at least ``--moon-min-hands``
active hands, otherwise X544.  This generator is specific to the H22 selector
layout and refuses sources whose selector markers are ambiguous.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


AGENT_START = "def agent(obs, configuration=None):\n    global _SELECTED_ROUTE\n"
AGENT_END = "\n\nagent.telemetry = _SELECTOR_TELEMETRY"


def delayed_selector_source(
    source: str,
    *,
    decision_step: int,
    moon_min_hands: int,
    label: str,
) -> str:
    if decision_step <= 0:
        raise ValueError("decision step must be positive")
    if moon_min_hands < 0:
        raise ValueError("moon minimum hands must be non-negative")

    selector_anchor = source.find("def _selector_call(namespace, obs, configuration):")
    if selector_anchor < 0:
        raise ValueError("source lacks the H22 selector helper")
    start = source.find(AGENT_START, selector_anchor)
    if start < 0:
        raise ValueError("source lacks the H22 selector agent")
    end = source.find(AGENT_END, start)
    if end < 0:
        raise ValueError("source lacks the H22 selector telemetry marker")

    replacement = f'''_DELAYED_DECISION_STEP = {decision_step}
_DELAYED_MOON_MIN_HANDS = {moon_min_hands}
_DELAYED_RNG = {{"x544": None, "moon": None}}


def _delayed_isolated_call(name, namespace, obs, configuration):
    process_rng = _selector_random.getstate()
    if _DELAYED_RNG[name] is None:
        _DELAYED_RNG[name] = process_rng
    try:
        _selector_random.setstate(_DELAYED_RNG[name])
        action = _selector_call(
            namespace,
            _selector_copy.deepcopy(obs),
            _selector_copy.deepcopy(configuration),
        )
        _DELAYED_RNG[name] = _selector_random.getstate()
        return _selector_copy.deepcopy(action)
    finally:
        _selector_random.setstate(process_rng)


def _delayed_opponent_hands(obs):
    player = int(_selector_get(obs, "player", 0) or 0)
    farms = list(_selector_get(obs, "farms", []) or [])
    opponent = 1 - player
    if opponent < 0 or opponent >= len(farms):
        return 0
    return len(_selector_get(farms[opponent], "hands", []) or [])


def agent(obs, configuration=None):
    global _SELECTED_ROUTE
    step = _selector_step(obs)
    if step == 0:
        _SELECTED_ROUTE = None
        _DELAYED_RNG["x544"] = None
        _DELAYED_RNG["moon"] = None
        _SELECTOR_TELEMETRY["selected_route"] = None
        _SELECTOR_TELEMETRY["opening_disagreement"] = 0
        _SELECTOR_TELEMETRY["pasture_opening"] = False
        _SELECTOR_TELEMETRY["decision_step"] = _DELAYED_DECISION_STEP
        _SELECTOR_TELEMETRY["decision_hands"] = None
        _SELECTOR_TELEMETRY["predecision_disagreements"] = 0

    if _SELECTED_ROUTE is None:
        x544_action = _delayed_isolated_call("x544", _X544_NS, obs, configuration)
        moon_action = _delayed_isolated_call("moon", _MOON_NS, obs, configuration)
        if step == 0 and x544_action != moon_action:
            _SELECTOR_TELEMETRY["opening_disagreement"] += 1
        if step < _DELAYED_DECISION_STEP:
            if x544_action != moon_action:
                _SELECTOR_TELEMETRY["predecision_disagreements"] += 1
            if step == 1:
                _SELECTOR_TELEMETRY["pasture_opening"] = (
                    _selector_opponent_has_opening_pasture(obs)
                )
            return x544_action

        hands = _delayed_opponent_hands(obs)
        _SELECTED_ROUTE = (
            "moon" if hands >= _DELAYED_MOON_MIN_HANDS else "x544"
        )
        _SELECTOR_TELEMETRY["selected_route"] = _SELECTED_ROUTE
        _SELECTOR_TELEMETRY["decision_hands"] = hands
        return moon_action if _SELECTED_ROUTE == "moon" else x544_action

    namespace = _MOON_NS if _SELECTED_ROUTE == "moon" else _X544_NS
    return _delayed_isolated_call(_SELECTED_ROUTE, namespace, obs, configuration)
'''
    generated = source[:start] + replacement + source[end:]
    versions = list(re.finditer(
        r'^__version__ = "([^"\r\n]+)"$', generated, flags=re.MULTILINE
    ))
    if not versions:
        raise ValueError("source lacks a version marker")
    final = versions[-1]
    version = f'__version__ = "{final.group(1)}-{label}"'
    return generated[:final.start()] + version + generated[final.end():]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--decision-step", type=int, default=112)
    parser.add_argument("--moon-min-hands", type=int, default=4)
    parser.add_argument("--label", default="delayed112-hands4")
    args = parser.parse_args()
    try:
        generated = delayed_selector_source(
            args.source.read_text(encoding="utf-8"),
            decision_step=args.decision_step,
            moon_min_hands=args.moon_min_hands,
            label=args.label,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(generated, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
