"""Build a data-only two-policy shadow runner with one switch checkpoint.

Both policies see every live observation from step zero and keep independent
Python RNG streams.  Only the source action is returned before ``--switch``;
only the target action is returned from that step onward.  This makes a late
switch test meaningful without pretending that an uninitialised tape can be
grafted into a foreign state.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path


def encoded_source(path: Path) -> str:
    return base64.b85encode(path.read_bytes()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--switch", type=int, required=True)
    args = parser.parse_args()
    if args.switch < 0:
        parser.error("--switch must be non-negative")

    source_b85 = encoded_source(args.source)
    target_b85 = encoded_source(args.target)
    generated = f'''from __future__ import annotations

import base64
import copy as _shadow_copy
import random as _shadow_random


_SOURCE_B85 = {source_b85!r}
_TARGET_B85 = {target_b85!r}
_SOURCE_NS = {{"__name__": "shadow_source"}}
_TARGET_NS = {{"__name__": "shadow_target"}}
exec(compile(base64.b85decode(_SOURCE_B85).decode("utf-8"), "shadow_source.py", "exec"), _SOURCE_NS, _SOURCE_NS)
exec(compile(base64.b85decode(_TARGET_B85).decode("utf-8"), "shadow_target.py", "exec"), _TARGET_NS, _TARGET_NS)

_SWITCH_STEP = {args.switch}
_RNG = {{"source": None, "target": None}}
_TELEMETRY = {{
    "switch_step": _SWITCH_STEP,
    "calls": {{"source": 0, "target": 0}},
    "action_disagreements": 0,
    "selected": None,
}}


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _step(obs):
    value = _get(obs, "step", None)
    if value is not None:
        return int(value or 0)
    return int(_get(obs, "day", 0) or 0) * 24 + int(_get(obs, "hour", 0) or 0)


def _raw_call(namespace, obs, configuration):
    branch = namespace["agent"]
    code = getattr(branch, "__code__", None)
    if code is not None and code.co_argcount >= 2:
        return branch(obs, configuration)
    return branch(obs)


def _isolated_call(name, namespace, obs, configuration):
    process_rng = _shadow_random.getstate()
    if _RNG[name] is None:
        _RNG[name] = process_rng
    try:
        _shadow_random.setstate(_RNG[name])
        action = _raw_call(
            namespace,
            _shadow_copy.deepcopy(obs),
            _shadow_copy.deepcopy(configuration),
        )
        _RNG[name] = _shadow_random.getstate()
        _TELEMETRY["calls"][name] += 1
        return _shadow_copy.deepcopy(action)
    finally:
        _shadow_random.setstate(process_rng)


def agent(obs, configuration=None):
    step = _step(obs)
    if step == 0:
        _RNG["source"] = None
        _RNG["target"] = None
        _TELEMETRY["calls"] = {{"source": 0, "target": 0}}
        _TELEMETRY["action_disagreements"] = 0
    source_action = _isolated_call("source", _SOURCE_NS, obs, configuration)
    target_action = _isolated_call("target", _TARGET_NS, obs, configuration)
    if source_action != target_action:
        _TELEMETRY["action_disagreements"] += 1
    use_target = step >= _SWITCH_STEP
    _TELEMETRY["selected"] = "target" if use_target else "source"
    return target_action if use_target else source_action


agent.telemetry = _TELEMETRY
__version__ = "shadow-switch-{args.switch}"
shadow_switch_kaggle_entrypoint = agent
'''
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(generated, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
