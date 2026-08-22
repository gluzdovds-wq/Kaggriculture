"""Build two-policy agents with a genuinely shared synthesized opening.

Both source policies are shadow-run from step zero with isolated RNG streams.
Before the branch step, the wrapper executes a deterministic common action
derived from both proposals.  Afterward it executes one fixed continuation.
Generating both continuations with identical mode and step therefore guarantees
the same prefix on a given opponent/seed/seat; it does not pretend that either
original policy's opening is a neutral common state.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
import zlib


MODES = (
    "consensus",
    "base_field",
    "donor_field",
    "base_field_donor_market",
    "donor_field_base_market",
    "consensus_base_market",
    "consensus_donor_market",
)
BRANCHES = ("base", "donor")


TEMPLATE = r'''"""Generated shadow-run common-prefix policy."""
import base64 as _cp_base64
import copy as _cp_copy
import inspect as _cp_inspect
import random as _cp_random
import zlib as _cp_zlib


def _cp_load(payload, name):
    namespace = {"__name__": name}
    source = _cp_zlib.decompress(_cp_base64.b85decode(payload)).decode("utf-8")
    exec(compile(source, name, "exec"), namespace)
    return namespace["agent"]


_CP_POLICIES = {
    "base": _cp_load(__BASE_PAYLOAD__, "_common_prefix_base"),
    "donor": _cp_load(__DONOR_PAYLOAD__, "_common_prefix_donor"),
}
_CP_ARITY = {
    name: len([
        parameter
        for parameter in _cp_inspect.signature(policy).parameters.values()
        if parameter.kind in (
            _cp_inspect.Parameter.POSITIONAL_ONLY,
            _cp_inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]) >= 2
    for name, policy in _CP_POLICIES.items()
}
_CP_SWITCH = __SWITCH__
_CP_MODE = __MODE__
_CP_BRANCH = __BRANCH__
_CP_RNG = {0: {}, 1: {}}
_CP_TELEMETRY = {}


def _cp_reset():
    _CP_TELEMETRY.clear()
    _CP_TELEMETRY.update({
        "switch_step": _CP_SWITCH,
        "mode": _CP_MODE,
        "branch": _CP_BRANCH,
        "prefix_turns": 0,
        "field_disagreements": 0,
        "market_disagreements": 0,
        "consensus_actor_passes": 0,
        "selected": None,
    })


_cp_reset()


def _cp_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _cp_step(obs):
    value = _cp_get(obs, "step", None)
    if value is not None:
        return int(value or 0)
    return int(_cp_get(obs, "day", 0) or 0) * 24 + int(
        _cp_get(obs, "hour", 0) or 0
    )


def _cp_call(name, obs, configuration, seat):
    outer = _cp_random.getstate()
    state = _CP_RNG[seat].get(name, outer)
    _cp_random.setstate(state)
    try:
        policy = _CP_POLICIES[name]
        if _CP_ARITY[name]:
            result = policy(_cp_copy.deepcopy(obs), _cp_copy.deepcopy(configuration))
        else:
            result = policy(_cp_copy.deepcopy(obs))
        _CP_RNG[seat][name] = _cp_random.getstate()
        return _cp_copy.deepcopy(result)
    finally:
        _cp_random.setstate(outer)


def _cp_action(value):
    return value if isinstance(value, dict) else {}


def _cp_actor(value):
    return _cp_copy.deepcopy(value) if value else ["PASS"]


def _cp_fields(action):
    action = _cp_action(action)
    return _cp_actor(action.get("farmer")), [
        _cp_actor(value) for value in (action.get("hands") or [])
    ]


def _cp_market(action):
    return [_cp_copy.deepcopy(value) for value in (_cp_action(action).get("market") or [])]


def _cp_intersection(left, right):
    remaining = _cp_copy.deepcopy(right)
    common = []
    for value in left:
        for index, candidate in enumerate(remaining):
            if value == candidate:
                common.append(_cp_copy.deepcopy(value))
                remaining.pop(index)
                break
    return common


def _cp_consensus_actor(left, right):
    if left == right:
        return _cp_copy.deepcopy(left)
    _CP_TELEMETRY["consensus_actor_passes"] += 1
    return ["PASS"]


def _cp_consensus_fields(base_action, donor_action):
    base_farmer, base_hands = _cp_fields(base_action)
    donor_farmer, donor_hands = _cp_fields(donor_action)
    size = max(len(base_hands), len(donor_hands))
    hands = []
    for index in range(size):
        base_value = base_hands[index] if index < len(base_hands) else ["PASS"]
        donor_value = donor_hands[index] if index < len(donor_hands) else ["PASS"]
        hands.append(_cp_consensus_actor(base_value, donor_value))
    return _cp_consensus_actor(base_farmer, donor_farmer), hands


def _cp_prefix_action(base_action, donor_action):
    base_farmer, base_hands = _cp_fields(base_action)
    donor_farmer, donor_hands = _cp_fields(donor_action)
    base_market = _cp_market(base_action)
    donor_market = _cp_market(donor_action)
    if (base_farmer, base_hands) != (donor_farmer, donor_hands):
        _CP_TELEMETRY["field_disagreements"] += 1
    if base_market != donor_market:
        _CP_TELEMETRY["market_disagreements"] += 1
    if _CP_MODE in ("base_field", "base_field_donor_market"):
        farmer, hands = base_farmer, base_hands
        market = (
            donor_market
            if _CP_MODE == "base_field_donor_market"
            else _cp_intersection(base_market, donor_market)
        )
    elif _CP_MODE in ("donor_field", "donor_field_base_market"):
        farmer, hands = donor_farmer, donor_hands
        market = (
            base_market
            if _CP_MODE == "donor_field_base_market"
            else _cp_intersection(base_market, donor_market)
        )
    else:
        farmer, hands = _cp_consensus_fields(base_action, donor_action)
        if _CP_MODE == "consensus_base_market":
            market = base_market
        elif _CP_MODE == "consensus_donor_market":
            market = donor_market
        else:
            market = _cp_intersection(base_market, donor_market)
    return {"farmer": farmer, "hands": hands, "market": market}


def agent(obs, configuration=None):
    step = _cp_step(obs)
    seat = int(_cp_get(obs, "player", 0) or 0)
    if step == 0:
        _CP_RNG[seat] = {}
        _cp_reset()
    base_action = _cp_call("base", obs, configuration, seat)
    donor_action = _cp_call("donor", obs, configuration, seat)
    if step < _CP_SWITCH:
        _CP_TELEMETRY["prefix_turns"] += 1
        _CP_TELEMETRY["selected"] = "common"
        return _cp_prefix_action(base_action, donor_action)
    _CP_TELEMETRY["selected"] = _CP_BRANCH
    return base_action if _CP_BRANCH == "base" else donor_action


agent.telemetry = _CP_TELEMETRY
__version__ = __VERSION__
common_prefix_kaggle_entrypoint = agent
'''


def payload(path: Path) -> str:
    return base64.b85encode(zlib.compress(path.read_bytes(), level=9)).decode("ascii")


def render_common_prefix(
    base: Path, donor: Path, switch: int, mode: str, branch: str
) -> str:
    if switch <= 0:
        raise ValueError("switch must be positive")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    if branch not in BRANCHES:
        raise ValueError(f"unknown branch {branch!r}")
    replacements = {
        "__BASE_PAYLOAD__": repr(payload(base)),
        "__DONOR_PAYLOAD__": repr(payload(donor)),
        "__SWITCH__": str(switch),
        "__MODE__": repr(mode),
        "__BRANCH__": repr(branch),
        "__VERSION__": repr(f"common-prefix-{mode}-s{switch}-{branch}"),
    }
    rendered = TEMPLATE
    for marker, value in replacements.items():
        rendered = rendered.replace(marker, value)
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("donor", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--switch", type=int, required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--branch", choices=BRANCHES, required=True)
    args = parser.parse_args()
    try:
        rendered = render_common_prefix(
            args.base, args.donor, args.switch, args.mode, args.branch
        )
    except ValueError as error:
        parser.error(str(error))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(rendered, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
