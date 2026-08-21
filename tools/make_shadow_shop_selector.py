"""Build a single-file selector that shadow-runs two compatible policies."""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
import zlib


TEMPLATE = r'''"""Generated compatible whole-policy shop selector."""
import base64 as _ss_base64
import copy as _ss_copy
import inspect as _ss_inspect
import random as _ss_random
import zlib as _ss_zlib


def _ss_load(payload, name):
    namespace = {"__name__": name}
    source = _ss_zlib.decompress(_ss_base64.b85decode(payload)).decode("utf-8")
    exec(compile(source, name, "exec"), namespace)
    return namespace["agent"]


_SS_DEFAULT = _ss_load(__DEFAULT_PAYLOAD__, "_shadow_shop_default")
_SS_OVERRIDE = _ss_load(__OVERRIDE_PAYLOAD__, "_shadow_shop_override")
_SS_DECISION_STEP = __DECISION_STEP__
_SS_SHOPS = __SHOPS__
_SS_SELECTED = {0: None, 1: None}
_SS_COMPATIBLE = {0: True, 1: True}
_SS_RNG = {0: {}, 1: {}}
_SS_TELEMETRY = {
    "selected": None,
    "decision_step": _SS_DECISION_STEP,
    "shops": [],
    "compatible_prefix": True,
    "prefix_mismatches": 0,
}


def _ss_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _ss_accepts_configuration(policy):
    positional = [
        parameter
        for parameter in _ss_inspect.signature(policy).parameters.values()
        if parameter.kind in (
            _ss_inspect.Parameter.POSITIONAL_ONLY,
            _ss_inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    return len(positional) >= 2


_SS_ARITY = {
    "default": _ss_accepts_configuration(_SS_DEFAULT),
    "override": _ss_accepts_configuration(_SS_OVERRIDE),
}


def _ss_call(name, policy, obs, configuration, seat):
    outer = _ss_random.getstate()
    state = _SS_RNG[seat].get(name, outer)
    _ss_random.setstate(state)
    try:
        if _SS_ARITY[name]:
            result = policy(_ss_copy.deepcopy(obs), _ss_copy.deepcopy(configuration))
        else:
            result = policy(_ss_copy.deepcopy(obs))
        _SS_RNG[seat][name] = _ss_random.getstate()
        return result
    finally:
        _ss_random.setstate(outer)


def agent(obs, configuration=None):
    step = int(_ss_get(obs, "step", 0) or 0)
    seat = 1 if int(_ss_get(obs, "player", 0) or 0) == 1 else 0
    if step == 0:
        _SS_SELECTED[seat] = None
        _SS_COMPATIBLE[seat] = True
        _SS_RNG[seat] = {}
        _SS_TELEMETRY["selected"] = None
        _SS_TELEMETRY["shops"] = []
        _SS_TELEMETRY["compatible_prefix"] = True
        _SS_TELEMETRY["prefix_mismatches"] = 0
    default_action = _ss_call("default", _SS_DEFAULT, obs, configuration, seat)
    override_action = _ss_call("override", _SS_OVERRIDE, obs, configuration, seat)
    if step < _SS_DECISION_STEP and default_action != override_action:
        _SS_COMPATIBLE[seat] = False
        _SS_TELEMETRY["prefix_mismatches"] += 1
    if _SS_SELECTED[seat] is None and step >= _SS_DECISION_STEP:
        town = _ss_get(obs, "town", {}) or {}
        shops = [
            str(value).upper()
            for value in (_ss_get(town, "unlocked_shops", []) or [])
        ]
        use_override = _SS_COMPATIBLE[seat] and any(shop in _SS_SHOPS for shop in shops)
        _SS_SELECTED[seat] = "override" if use_override else "default"
        _SS_TELEMETRY["selected"] = _SS_SELECTED[seat]
        _SS_TELEMETRY["shops"] = shops
        _SS_TELEMETRY["compatible_prefix"] = _SS_COMPATIBLE[seat]
    if _SS_SELECTED[seat] == "override":
        return override_action
    return default_action


agent.telemetry = _SS_TELEMETRY
__version__ = "shadow-shop-selector-__LABEL__"
shadow_shop_kaggle_entrypoint = agent
'''


def payload(path: Path) -> str:
    source = path.read_bytes()
    return base64.b85encode(zlib.compress(source, level=9)).decode("ascii")


def render_selector(
    default: Path,
    override: Path,
    *,
    shops: list[str],
    decision_step: int,
    label: str,
) -> str:
    normalized_shops = tuple(
        sorted({shop.strip().upper() for shop in shops if shop.strip()})
    )
    if not normalized_shops:
        raise ValueError("at least one non-empty shop is required")
    if decision_step < 0:
        raise ValueError("decision_step must be non-negative")
    if not label.strip():
        raise ValueError("label must be non-empty")
    return (
        TEMPLATE.replace("__DEFAULT_PAYLOAD__", repr(payload(default)))
        .replace("__OVERRIDE_PAYLOAD__", repr(payload(override)))
        .replace("__DECISION_STEP__", str(decision_step))
        .replace("__SHOPS__", repr(normalized_shops))
        .replace("__LABEL__", label.strip())
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("default", type=Path)
    parser.add_argument("override", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--shop", action="append", required=True)
    parser.add_argument("--decision-step", type=int, default=72)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    try:
        source = render_selector(
            args.default,
            args.override,
            shops=args.shop,
            decision_step=args.decision_step,
            label=args.label,
        )
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
