"""Build the hash-bound V48/V43 first-shop router as one Kaggle file."""

from __future__ import annotations

import argparse
import base64
import hashlib
from pathlib import Path
import zlib


V48_SHA256 = "dadee25a9840313218384208c53b2c4752f82c3209cc654632e0b96c65e2664a"
V43_SHA256 = "69f06a802b62aa08f28705dab5728eb924bb6a7c23ffe0164f65b104cc3dadf3"


TEMPLATE = r'''"""V48 floor with a first-shop V43 route for Farmers Market / Ice Cream."""
import base64 as _sr_base64
import copy as _sr_copy
import random as _sr_random
import sys as _sr_sys
import zlib as _sr_zlib


def _sr_load(payload, name):
    # The bundled agents create packages such as ``v23`` in sys.modules while
    # they initialise.  Restore the module table after each load so V48 and
    # V43 cannot overwrite one another's package namespace.  Their policy
    # objects retain direct references to the modules they were built from.
    before = dict(_sr_sys.modules)
    namespace = {"__name__": name}
    source = _sr_zlib.decompress(_sr_base64.b85decode(payload)).decode("utf-8")
    try:
        exec(compile(source, name, "exec"), namespace, namespace)
    finally:
        for module_name in tuple(_sr_sys.modules):
            if module_name not in before:
                del _sr_sys.modules[module_name]
        _sr_sys.modules.update(before)
    return namespace


_SR_V48_SOURCE_SHA256 = __V48_SHA256__
_SR_V43_SOURCE_SHA256 = __V43_SHA256__
_SR_V48_NS = _sr_load(__V48_PAYLOAD__, "_e152_v48_branch")
_SR_V43_NS = _sr_load(__V43_PAYLOAD__, "_e152_v43_branch")
_SR_V43_FIRST_SHOPS = frozenset(("FARMERS_MARKET", "ICE_CREAM_SHOP"))
_SR_SELECTED = {0: None, 1: None}
_SR_FIRST_SHOP = {0: None, 1: None}
_SR_COMPATIBLE = {0: True, 1: True}
_SR_RNG = {0: {}, 1: {}}
_SR_TELEMETRY = {
    "selected": None,
    "first_shop": None,
    "compatible_prefix": True,
    "prefix_mismatches": 0,
    "calls": {"v48": 0, "v43": 0},
    "v43_errors": 0,
    "v43_invalid_actions": 0,
}


def _sr_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _sr_step(obs):
    explicit = _sr_get(obs, "step", None)
    if explicit is not None:
        return int(explicit or 0)
    return int(_sr_get(obs, "day", 0) or 0) * 24 + int(
        _sr_get(obs, "hour", 0) or 0
    )


def _sr_seat(obs):
    return 1 if int(_sr_get(obs, "player", 0) or 0) == 1 else 0


def _sr_raw_call(namespace, obs, configuration):
    branch = namespace["agent"]
    code = getattr(branch, "__code__", None)
    if code is not None and code.co_argcount >= 2:
        return branch(obs, configuration)
    return branch(obs)


def _sr_isolated_call(name, namespace, obs, configuration, seat):
    process_rng = _sr_random.getstate()
    branch_rng = _SR_RNG[seat].get(name, process_rng)
    try:
        _sr_random.setstate(branch_rng)
        action = _sr_raw_call(
            namespace,
            _sr_copy.deepcopy(obs),
            _sr_copy.deepcopy(configuration),
        )
        _SR_RNG[seat][name] = _sr_random.getstate()
        _SR_TELEMETRY["calls"][name] += 1
        return _sr_copy.deepcopy(action)
    finally:
        _sr_random.setstate(process_rng)


def _sr_pass_action(obs, seat):
    farms = list(_sr_get(obs, "farms", []) or [])
    farm = farms[seat] if seat < len(farms) else {}
    return {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in (_sr_get(farm, "hands", []) or [])],
        "market": [],
    }


def _sr_valid_action(action):
    return (
        isinstance(action, dict)
        and isinstance(action.get("farmer"), list)
        and isinstance(action.get("hands"), list)
        and isinstance(action.get("market"), list)
    )


def _sr_normalize_action(value):
    """Return a detached, recursively comparable action representation."""
    if isinstance(value, dict):
        return tuple(
            sorted(
                (str(key), _sr_normalize_action(item))
                for key, item in value.items()
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_sr_normalize_action(item) for item in value)
    return _sr_copy.deepcopy(value)


def _sr_actions_equal(left, right):
    return _sr_normalize_action(left) == _sr_normalize_action(right)


def _sr_shop_name(value):
    if isinstance(value, dict):
        value = value.get("name", value.get("shop", ""))
    else:
        value = getattr(value, "name", value)
    return str(value or "").strip().upper()


def agent(obs, configuration=None):
    seat = _sr_seat(obs)
    step = _sr_step(obs)
    if step == 0:
        _SR_SELECTED[seat] = None
        _SR_FIRST_SHOP[seat] = None
        _SR_COMPATIBLE[seat] = True
        _SR_RNG[seat] = {}
        _SR_TELEMETRY["selected"] = None
        _SR_TELEMETRY["first_shop"] = None
        _SR_TELEMETRY["compatible_prefix"] = True
        _SR_TELEMETRY["prefix_mismatches"] = 0

    # V48 is evaluated first and retained as the fail-closed action.  V43 is
    # nevertheless evaluated on every step, including the common opening, so
    # its route state is ready when the first town shop appears.
    v48_ok = True
    try:
        v48_action = _sr_isolated_call(
            "v48", _SR_V48_NS, obs, configuration, seat
        )
    except Exception:
        v48_ok = False
        v48_action = _sr_pass_action(obs, seat)

    v43_ok = True
    try:
        v43_action = _sr_isolated_call(
            "v43", _SR_V43_NS, obs, configuration, seat
        )
    except Exception:
        v43_ok = False
        _SR_TELEMETRY["v43_errors"] += 1
        v43_action = None
    v43_action_valid = v43_ok and _sr_valid_action(v43_action)
    if v43_ok and not v43_action_valid:
        _SR_TELEMETRY["v43_invalid_actions"] += 1

    try:
        town = _sr_get(obs, "town", {}) or {}
        shops = list(_sr_get(town, "unlocked_shops", []) or [])
        if _SR_FIRST_SHOP[seat] is None and shops:
            first_shop = _sr_shop_name(shops[0])
            _SR_FIRST_SHOP[seat] = first_shop
            _SR_TELEMETRY["first_shop"] = first_shop
            if _SR_SELECTED[seat] is None:
                _SR_SELECTED[seat] = (
                    "v43"
                    if (
                        _SR_COMPATIBLE[seat]
                        and v43_action_valid
                        and first_shop in _SR_V43_FIRST_SHOPS
                    )
                    else "v48"
                )
                _SR_TELEMETRY["selected"] = _SR_SELECTED[seat]

        # Compare the entire detached action while the public shop signal is
        # still absent.  A single disagreement/error permanently latches V48:
        # switching later would splice V43 state onto a different trajectory.
        if _SR_SELECTED[seat] is None and not shops:
            compatible_now = (
                v48_ok
                and _sr_valid_action(v48_action)
                and v43_action_valid
                and _sr_actions_equal(v48_action, v43_action)
            )
            if not compatible_now:
                _SR_COMPATIBLE[seat] = False
                _SR_SELECTED[seat] = "v48"
                _SR_TELEMETRY["compatible_prefix"] = False
                _SR_TELEMETRY["prefix_mismatches"] += 1
                _SR_TELEMETRY["selected"] = "v48"
    except Exception:
        _SR_COMPATIBLE[seat] = False
        _SR_SELECTED[seat] = "v48"
        _SR_TELEMETRY["compatible_prefix"] = False
        _SR_TELEMETRY["selected"] = "v48"

    if _SR_SELECTED[seat] == "v43":
        if v43_action_valid:
            return v43_action
    return v48_action


agent.telemetry = _SR_TELEMETRY
__version__ = "e152-v48-v43-first-shop-router-v1"

# kaggle-environments selects the last callable inserted into module globals.
kaggle_submission_entrypoint = agent
'''


def _payload(source: bytes) -> str:
    return base64.b85encode(zlib.compress(source, level=9)).decode("ascii")


def render_router(
    v48: Path,
    v43: Path,
    *,
    expected_v48_sha256: str | None = V48_SHA256,
    expected_v43_sha256: str | None = V43_SHA256,
) -> str:
    v48_source = v48.read_bytes()
    v43_source = v43.read_bytes()
    v48_sha256 = hashlib.sha256(v48_source).hexdigest()
    v43_sha256 = hashlib.sha256(v43_source).hexdigest()
    if expected_v48_sha256 and v48_sha256 != expected_v48_sha256.lower():
        raise ValueError(
            f"V48 SHA256 mismatch: expected {expected_v48_sha256}, got {v48_sha256}"
        )
    if expected_v43_sha256 and v43_sha256 != expected_v43_sha256.lower():
        raise ValueError(
            f"V43 SHA256 mismatch: expected {expected_v43_sha256}, got {v43_sha256}"
        )
    return (
        TEMPLATE.replace("__V48_PAYLOAD__", repr(_payload(v48_source)))
        .replace("__V43_PAYLOAD__", repr(_payload(v43_source)))
        .replace("__V48_SHA256__", repr(v48_sha256))
        .replace("__V43_SHA256__", repr(v43_sha256))
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("v48", type=Path)
    parser.add_argument("v43", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--v48-sha256", default=V48_SHA256)
    parser.add_argument("--v43-sha256", default=V43_SHA256)
    args = parser.parse_args()
    try:
        generated = render_router(
            args.v48,
            args.v43,
            expected_v48_sha256=args.v48_sha256,
            expected_v43_sha256=args.v43_sha256,
        )
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
