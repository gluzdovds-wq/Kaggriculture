"""Build a single-file base agent with a continuously shadow-run candidate.

The default audit mode is deliberately outcome-neutral.  It isolates Python RNG
state for both policies, feeds each the same observation available to the
controlled seat, records action/macro compatibility, and executes the base.
An explicit ``--execute-operation`` allowlist can promote only locally valid,
non-redundant immediate actions when the corresponding base actor is passing.
This supplies a narrow official-engine gate between pure shadow analysis and a
whole-policy switch.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
import zlib


TEMPLATE = r'''"""Generated outcome-neutral shadow-policy audit."""
import base64 as _spa_base64
import copy as _spa_copy
import inspect as _spa_inspect
import random as _spa_random
import zlib as _spa_zlib


def _spa_load(payload, name):
    namespace = {"__name__": name}
    source = _spa_zlib.decompress(_spa_base64.b85decode(payload)).decode("utf-8")
    exec(compile(source, name, "exec"), namespace)
    return namespace["agent"]


_SPA_BASE = _spa_load(__BASE_PAYLOAD__, "_shadow_audit_base")
_SPA_CANDIDATE = _spa_load(__CANDIDATE_PAYLOAD__, "_shadow_audit_candidate")
_SPA_RNG = {0: {}, 1: {}}
_SPA_LAST = {0: -1, 1: -1}
_SPA_SERVICE = {"WATER", "FEED", "CARE", "FERTILIZE"}
_SPA_VALUE = {"HARVEST", "COLLECT_FERTILIZER", "DROP", "PLACE"}
_SPA_EXECUTE = set(__EXECUTE_OPERATIONS__)
_SPA_EXECUTE_START = __EXECUTE_START__
_SPA_EXECUTE_STOP = __EXECUTE_STOP__
_SPA_DROP_ONLY_ITEMS = set(__DROP_ONLY_ITEMS__)
_SPA_DROP_MAX_TOTAL = __DROP_MAX_TOTAL__
_SPA_TELEMETRY = {}


def _spa_reset():
    _SPA_TELEMETRY.clear()
    _SPA_TELEMETRY.update({
        "label": __LABEL__,
        "execute_operations": sorted(_SPA_EXECUTE),
        "execute_start": _SPA_EXECUTE_START,
        "execute_stop": _SPA_EXECUTE_STOP,
        "turns": 0,
        "joint_equal": 0,
        "field_equal": 0,
        "market_equal": 0,
        "first_joint_divergence": None,
        "last_joint_divergence": None,
        "longest_joint_equal_streak": 0,
        "current_joint_equal_streak": 0,
        "candidate_errors": 0,
        "divergence_by_day_band": {},
        "base_task_macros": {},
        "candidate_task_macros": {},
        "candidate_nonpass_for_base_pass": 0,
        "candidate_service_for_base_pass": 0,
        "candidate_value_for_base_pass": 0,
        "candidate_immediate_valid_for_base_pass": 0,
        "candidate_immediate_nonredundant_for_base_pass": 0,
        "immediate_samples": [],
        "valid_immediate_samples": [],
        "executed": 0,
        "executed_by_operation": {},
        "filtered_by_context": 0,
    })


_spa_reset()


def _spa_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _spa_accepts_configuration(policy):
    positional = [
        parameter
        for parameter in _spa_inspect.signature(policy).parameters.values()
        if parameter.kind in (
            _spa_inspect.Parameter.POSITIONAL_ONLY,
            _spa_inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    return len(positional) >= 2


_SPA_ARITY = {
    "base": _spa_accepts_configuration(_SPA_BASE),
    "candidate": _spa_accepts_configuration(_SPA_CANDIDATE),
}


def _spa_call(name, policy, obs, configuration, seat):
    outer = _spa_random.getstate()
    state = _SPA_RNG[seat].get(name, outer)
    _spa_random.setstate(state)
    try:
        if _SPA_ARITY[name]:
            result = policy(_spa_copy.deepcopy(obs), _spa_copy.deepcopy(configuration))
        else:
            result = policy(_spa_copy.deepcopy(obs))
        _SPA_RNG[seat][name] = _spa_random.getstate()
        return result
    finally:
        _spa_random.setstate(outer)


def _spa_operation(action):
    if isinstance(action, (list, tuple)) and action:
        return str(action[0]).upper()
    return "PASS"


def _spa_field(action):
    action = action if isinstance(action, dict) else {}
    return [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]


def _spa_market(action):
    action = action if isinstance(action, dict) else {}
    return list(action.get("market") or [])


def _spa_task_macro(action):
    groups = {
        "NORTH": "move", "SOUTH": "move", "EAST": "move", "WEST": "move",
        "PLANT": "plant", "WATER": "service", "FEED": "service",
        "CARE": "service", "FERTILIZE": "service",
        "COLLECT_FERTILIZER": "collect", "HARVEST": "harvest",
        "BUILD_COOP": "build", "BUILD_PASTURE": "build", "DIG": "dig",
        "PICKUP": "logistics", "DROP": "logistics", "PLACE": "logistics",
    }
    active = sorted({groups[operation] for operation in map(_spa_operation, _spa_field(action)) if operation in groups})
    return "+".join(active) if active else "pass"


def _spa_increment(name, key, amount=1):
    table = _SPA_TELEMETRY[name]
    table[key] = table.get(key, 0) + amount


def _spa_immediate_context(obs, actor_index, candidate_raw):
    operation = _spa_operation(candidate_raw)
    player = int(_spa_get(obs, "player", 0) or 0)
    farms = list(_spa_get(obs, "farms", []) or [])
    if player >= len(farms):
        return False, {}
    farm = farms[player]
    positions = [_spa_get(farm, "farmer"), *list(_spa_get(farm, "hands", []) or [])]
    private = _spa_get(obs, "private", {}) or {}
    inventories = list(_spa_get(private, "inventories", []) or [])
    if actor_index >= len(positions) or not positions[actor_index]:
        return False, {}
    position = positions[actor_index]
    x, y = int(position[0]), int(position[1])
    tiles = list(_spa_get(farm, "tiles", []) or [])
    tile = None
    if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]):
        tile = tiles[y][x]
    inventory = (
        dict(inventories[actor_index] or {})
        if actor_index < len(inventories)
        else {}
    )
    valid = False
    if isinstance(tile, dict):
        if operation == "WATER":
            valid = tile.get("kind") == "PLANT" and not tile.get("watered_today", False)
        elif operation == "FEED":
            valid = bool(tile.get("animal")) and not tile.get("fed_today", False) and int(inventory.get("WHEAT", 0) or 0) > 0
        elif operation == "CARE":
            valid = bool(tile.get("animal")) and not tile.get("cared_today", False)
        elif operation == "FERTILIZE":
            valid = tile.get("kind") == "PLANT" and int(inventory.get("FERTILIZER", 0) or 0) > 0
        elif operation == "HARVEST":
            valid = int(tile.get("yield_units", 0) or 0) > 0
        elif operation == "COLLECT_FERTILIZER":
            valid = bool(tile.get("fertilizer_available", False))
    if operation == "DROP":
        center = {len(tiles) // 2 - 1, len(tiles) // 2}
        valid = bool(tiles) and x in center and y in center and any(int(value or 0) > 0 for value in inventory.values())
    elif operation == "PLACE" and len(candidate_raw) >= 2:
        item = str(candidate_raw[1])
        quantity = int(candidate_raw[2]) if len(candidate_raw) >= 3 else 1
        center = {len(tiles) // 2 - 1, len(tiles) // 2}
        valid = bool(tiles) and x in center and y in center and int(inventory.get(item, 0) or 0) >= quantity > 0
    tile_summary = {}
    if isinstance(tile, dict):
        for key in (
            "kind", "crop", "animal", "yield_units", "watered_today",
            "fed_today", "cared_today", "consecutive_unwatered",
            "consecutive_unfed", "fertilizer_available",
        ):
            if key in tile:
                tile_summary[key] = tile[key]
    return valid, {
        "actor": actor_index,
        "operation": operation,
        "position": [x, y],
        "tile": tile_summary,
        "inventory": {key: value for key, value in inventory.items() if int(value or 0) > 0},
    }


def _spa_record(base_action, candidate_action, step, obs):
    base_field = _spa_field(base_action)
    candidate_field = _spa_field(candidate_action)
    base_market = _spa_market(base_action)
    candidate_market = _spa_market(candidate_action)
    field_equal = base_field == candidate_field
    market_equal = base_market == candidate_market
    joint_equal = field_equal and market_equal
    _SPA_TELEMETRY["turns"] += 1
    _SPA_TELEMETRY["field_equal"] += int(field_equal)
    _SPA_TELEMETRY["market_equal"] += int(market_equal)
    _SPA_TELEMETRY["joint_equal"] += int(joint_equal)
    _spa_increment("base_task_macros", _spa_task_macro(base_action))
    _spa_increment("candidate_task_macros", _spa_task_macro(candidate_action))
    if joint_equal:
        streak = _SPA_TELEMETRY["current_joint_equal_streak"] + 1
        _SPA_TELEMETRY["current_joint_equal_streak"] = streak
        _SPA_TELEMETRY["longest_joint_equal_streak"] = max(
            _SPA_TELEMETRY["longest_joint_equal_streak"], streak
        )
    else:
        _SPA_TELEMETRY["current_joint_equal_streak"] = 0
        if _SPA_TELEMETRY["first_joint_divergence"] is None:
            _SPA_TELEMETRY["first_joint_divergence"] = step
        _SPA_TELEMETRY["last_joint_divergence"] = step
        band = "%02d-%02d" % ((step // 144) * 6, min(29, (step // 144) * 6 + 5))
        _spa_increment("divergence_by_day_band", band)
    for actor_index, (base_raw, candidate_raw) in enumerate(zip(base_field, candidate_field)):
        base_op = _spa_operation(base_raw)
        candidate_op = _spa_operation(candidate_raw)
        if base_op != "PASS" or candidate_op == "PASS":
            continue
        _SPA_TELEMETRY["candidate_nonpass_for_base_pass"] += 1
        _SPA_TELEMETRY["candidate_service_for_base_pass"] += int(candidate_op in _SPA_SERVICE)
        _SPA_TELEMETRY["candidate_value_for_base_pass"] += int(candidate_op in _SPA_VALUE)
        if candidate_op in _SPA_SERVICE or candidate_op in _SPA_VALUE:
            valid, context = _spa_immediate_context(obs, actor_index, candidate_raw)
            _SPA_TELEMETRY["candidate_immediate_valid_for_base_pass"] += int(valid)
            player = int(_spa_get(obs, "player", 0) or 0)
            farms = list(_spa_get(obs, "farms", []) or [])
            farm = farms[player] if player < len(farms) else {}
            positions = [_spa_get(farm, "farmer"), *list(_spa_get(farm, "hands", []) or [])]
            target_position = context.get("position")
            same_tile_operations = [
                _spa_operation(base_field[index])
                for index, position in enumerate(positions)
                if index < len(base_field)
                and position is not None
                and list(position[:2]) == target_position
            ]
            redundant = candidate_op in same_tile_operations
            nonredundant = valid and not redundant
            _SPA_TELEMETRY["candidate_immediate_nonredundant_for_base_pass"] += int(nonredundant)
            context["base_same_tile_operations"] = same_tile_operations
            context["redundant"] = redundant
            context.update({"step": step, "valid": valid})
            if valid and len(_SPA_TELEMETRY["valid_immediate_samples"]) < 32:
                _SPA_TELEMETRY["valid_immediate_samples"].append(
                    _spa_copy.deepcopy(context)
                )
            if len(_SPA_TELEMETRY["immediate_samples"]) < 32:
                _SPA_TELEMETRY["immediate_samples"].append(context)


def _spa_apply_immediate(base_action, candidate_action, obs, step):
    if not _SPA_EXECUTE:
        return base_action
    if not _SPA_EXECUTE_START <= step < _SPA_EXECUTE_STOP:
        return base_action
    result = _spa_copy.deepcopy(base_action)
    result_field = _spa_field(result)
    candidate_field = _spa_field(candidate_action)
    player = int(_spa_get(obs, "player", 0) or 0)
    farms = list(_spa_get(obs, "farms", []) or [])
    farm = farms[player] if player < len(farms) else {}
    positions = [_spa_get(farm, "farmer"), *list(_spa_get(farm, "hands", []) or [])]
    for actor_index, (base_raw, candidate_raw) in enumerate(
        zip(result_field, candidate_field)
    ):
        candidate_op = _spa_operation(candidate_raw)
        if _spa_operation(base_raw) != "PASS" or candidate_op not in _SPA_EXECUTE:
            continue
        valid, context = _spa_immediate_context(obs, actor_index, candidate_raw)
        if not valid:
            continue
        if candidate_op == "DROP":
            inventory = context.get("inventory") or {}
            positive_items = {
                str(item)
                for item, quantity in inventory.items()
                if int(quantity or 0) > 0
            }
            total = sum(max(0, int(quantity or 0)) for quantity in inventory.values())
            allowed_items = not _SPA_DROP_ONLY_ITEMS or positive_items <= _SPA_DROP_ONLY_ITEMS
            allowed_total = _SPA_DROP_MAX_TOTAL is None or total <= _SPA_DROP_MAX_TOTAL
            if not (allowed_items and allowed_total):
                _SPA_TELEMETRY["filtered_by_context"] += 1
                continue
        target_position = context.get("position")
        same_tile_operations = [
            _spa_operation(result_field[index])
            for index, position in enumerate(positions)
            if index < len(result_field)
            and position is not None
            and list(position[:2]) == target_position
        ]
        if candidate_op in same_tile_operations:
            continue
        result_field[actor_index] = _spa_copy.deepcopy(candidate_raw)
        _SPA_TELEMETRY["executed"] += 1
        _spa_increment("executed_by_operation", candidate_op)
    if result_field:
        result["farmer"] = result_field[0]
        result["hands"] = result_field[1:]
    return result


def agent(obs, configuration=None):
    day = int(_spa_get(obs, "day", 0) or 0)
    hour = int(_spa_get(obs, "hour", 0) or 0)
    step = day * 24 + hour
    seat = 1 if int(_spa_get(obs, "player", 0) or 0) == 1 else 0
    if step == 0 or step <= _SPA_LAST[seat]:
        _SPA_RNG[seat] = {}
        _spa_reset()
    _SPA_LAST[seat] = step
    base_action = _spa_call("base", _SPA_BASE, obs, configuration, seat)
    try:
        candidate_action = _spa_call(
            "candidate", _SPA_CANDIDATE, obs, configuration, seat
        )
        _spa_record(base_action, candidate_action, step, obs)
        return _spa_apply_immediate(base_action, candidate_action, obs, step)
    except Exception:
        _SPA_TELEMETRY["candidate_errors"] += 1
    return base_action


agent.telemetry = _SPA_TELEMETRY
__version__ = "shadow-policy-audit-__LABEL_TEXT__"
shadow_policy_audit_kaggle_entrypoint = agent
'''


def payload(path: Path) -> str:
    source = path.read_bytes()
    return base64.b85encode(zlib.compress(source, level=9)).decode("ascii")


def render_audit(
    base: Path,
    candidate: Path,
    *,
    label: str,
    execute_operations: tuple[str, ...] = (),
    execute_start: int = 0,
    execute_stop: int = 720,
    drop_only_items: tuple[str, ...] = (),
    drop_max_total: int | None = None,
) -> str:
    if not label.strip():
        raise ValueError("label must be non-empty")
    if not base.is_file():
        raise ValueError(f"base policy does not exist: {base}")
    if not candidate.is_file():
        raise ValueError(f"candidate policy does not exist: {candidate}")
    allowed = {"WATER", "FEED", "CARE", "FERTILIZE", "HARVEST", "COLLECT_FERTILIZER", "DROP", "PLACE"}
    normalized_operations = tuple(
        sorted({str(operation).strip().upper() for operation in execute_operations})
    )
    unknown = sorted(set(normalized_operations) - allowed)
    if unknown:
        raise ValueError(f"unsupported immediate operation(s): {', '.join(unknown)}")
    if not 0 <= execute_start < execute_stop <= 720:
        raise ValueError("execute window must satisfy 0 <= start < stop <= 720")
    normalized_drop_items = tuple(
        sorted({str(item).strip().upper() for item in drop_only_items if str(item).strip()})
    )
    if drop_max_total is not None and drop_max_total < 0:
        raise ValueError("drop_max_total must be non-negative")
    return (
        TEMPLATE.replace("__BASE_PAYLOAD__", repr(payload(base)))
        .replace("__CANDIDATE_PAYLOAD__", repr(payload(candidate)))
        .replace("__EXECUTE_OPERATIONS__", repr(normalized_operations))
        .replace("__EXECUTE_START__", repr(int(execute_start)))
        .replace("__EXECUTE_STOP__", repr(int(execute_stop)))
        .replace("__DROP_ONLY_ITEMS__", repr(normalized_drop_items))
        .replace("__DROP_MAX_TOTAL__", repr(drop_max_total))
        .replace("__LABEL__", repr(label.strip()))
        .replace("__LABEL_TEXT__", label.strip())
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--execute-operation", action="append", default=[])
    parser.add_argument("--execute-start", type=int, default=0)
    parser.add_argument("--execute-stop", type=int, default=720)
    parser.add_argument("--drop-only-item", action="append", default=[])
    parser.add_argument("--drop-max-total", type=int)
    args = parser.parse_args()
    try:
        source = render_audit(
            args.base,
            args.candidate,
            label=args.label,
            execute_operations=tuple(args.execute_operation),
            execute_start=args.execute_start,
            execute_stop=args.execute_stop,
            drop_only_items=tuple(args.drop_only_item),
            drop_max_total=args.drop_max_total,
        )
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
