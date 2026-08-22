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


def parse_animal_counts(values: tuple[str, ...] | list[str]) -> dict[str, int]:
    counts = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("opponent animal count must be ANIMAL=COUNT")
        animal, count = raw.split("=", 1)
        animal = animal.strip().upper()
        if animal not in {"COW", "SHEEP", "GOOSE"}:
            raise ValueError(f"unsupported opponent animal: {animal}")
        try:
            value = int(count)
        except ValueError as exc:
            raise ValueError("opponent animal count must be an integer") from exc
        if value < 0:
            raise ValueError("opponent animal count must be non-negative")
        counts[animal] = value
    return counts


def parse_sell_rules(
    values: tuple[str, ...] | list[str],
) -> tuple[tuple[str, int, int, int], ...]:
    rules = []
    for raw in values:
        parts = raw.split(":")
        if len(parts) != 4:
            raise ValueError("sell rule must be ITEM:START:STOP:CAP")
        item = parts[0].strip().upper()
        try:
            start, stop, cap = (int(value) for value in parts[1:])
        except ValueError as exc:
            raise ValueError("sell rule bounds and cap must be integers") from exc
        rules.append((item, start, stop, cap))
    return tuple(rules)


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
_SPA_SELL_RULES = tuple(__SELL_RULES__)
_SPA_EXECUTE_SELL_ITEMS = {rule[0] for rule in _SPA_SELL_RULES}
_SPA_SELL_CAP = __SELL_CAP__
_SPA_OPPONENT_ANIMALS = __OPPONENT_ANIMALS__
_SPA_OPPONENT_ANIMAL_GATE_STEP = __OPPONENT_ANIMAL_GATE_STEP__
_SPA_DROP_ONLY_ITEMS = set(__DROP_ONLY_ITEMS__)
_SPA_DROP_MAX_TOTAL = __DROP_MAX_TOTAL__
_SPA_MARKET_DEBT = {0: {}, 1: {}}
_SPA_MARKET_FAMILY_OK = {0: None, 1: None}
_SPA_TELEMETRY = {}


def _spa_reset():
    _SPA_TELEMETRY.clear()
    _SPA_TELEMETRY.update({
        "label": __LABEL__,
        "execute_operations": sorted(_SPA_EXECUTE),
        "execute_start": _SPA_EXECUTE_START,
        "execute_stop": _SPA_EXECUTE_STOP,
        "execute_sell_items": sorted(_SPA_EXECUTE_SELL_ITEMS),
        "sell_rules": [list(rule) for rule in _SPA_SELL_RULES],
        "sell_cap": _SPA_SELL_CAP,
        "opponent_animals": _SPA_OPPONENT_ANIMALS,
        "opponent_animal_gate_step": _SPA_OPPONENT_ANIMAL_GATE_STEP,
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
        "candidate_sell_excess": {},
        "candidate_sell_executable": {},
        "candidate_sell_executable_by_step": {},
        "candidate_sell_deficit": {},
        "market_divergence_samples": [],
        "market_advanced": {},
        "market_repaid": {},
        "market_advance_steps": [],
        "market_family_accepted": 0,
        "market_family_rejected": 0,
        "market_family_observations": [],
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
    if not market_equal:
        def sell_quantities(orders):
            quantities = {}
            for raw in orders:
                if (
                    isinstance(raw, (list, tuple))
                    and len(raw) >= 3
                    and str(raw[0]).upper() == "SELL"
                ):
                    item = str(raw[1]).upper()
                    quantities[item] = quantities.get(item, 0) + max(
                        0, int(raw[2] or 0)
                    )
            return quantities

        base_sells = sell_quantities(base_market)
        candidate_sells = sell_quantities(candidate_market)
        shed = dict((_spa_get(obs, "private", {}) or {}).get("shed", {}) or {})
        executable_sells = {}
        for item in sorted(set(base_sells) | set(candidate_sells)):
            delta = candidate_sells.get(item, 0) - base_sells.get(item, 0)
            if delta > 0:
                _spa_increment("candidate_sell_excess", item, delta)
                available = max(
                    0, int(shed.get(item, 0) or 0) - base_sells.get(item, 0)
                )
                executable = min(delta, available)
                if executable > 0:
                    executable_sells[item] = executable
                    _spa_increment("candidate_sell_executable", item, executable)
                    by_step = _SPA_TELEMETRY["candidate_sell_executable_by_step"]
                    step_key = str(step)
                    step_items = by_step.setdefault(step_key, {})
                    step_items[item] = step_items.get(item, 0) + executable
            elif delta < 0:
                _spa_increment("candidate_sell_deficit", item, -delta)
        if len(_SPA_TELEMETRY["market_divergence_samples"]) < 64:
            _SPA_TELEMETRY["market_divergence_samples"].append({
                "step": step,
                "base": _spa_copy.deepcopy(base_market),
                "candidate": _spa_copy.deepcopy(candidate_market),
                "sell_delta": {
                    item: candidate_sells.get(item, 0) - base_sells.get(item, 0)
                    for item in sorted(set(base_sells) | set(candidate_sells))
                    if candidate_sells.get(item, 0) != base_sells.get(item, 0)
                },
                "executable_sell_delta": executable_sells,
            })
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


def _spa_sell_quantities(orders):
    quantities = {}
    for raw in orders:
        if (
            isinstance(raw, (list, tuple))
            and len(raw) >= 3
            and str(raw[0]).upper() == "SELL"
        ):
            item = str(raw[1]).upper()
            quantities[item] = quantities.get(item, 0) + max(0, int(raw[2] or 0))
    return quantities


def _spa_observed_opponent_animals(obs, seat):
    farms = list(_spa_get(obs, "farms", []) or [])
    opponent_index = 1 - seat
    opponent = farms[opponent_index] if opponent_index < len(farms) else {}
    observed = {}
    for row in list(_spa_get(opponent, "tiles", []) or []):
        for tile in list(row or []):
            animal = (
                str(tile.get("animal", "")).upper()
                if isinstance(tile, dict)
                else ""
            )
            if animal:
                observed[animal] = observed.get(animal, 0) + 1
    return observed


def _spa_matches_opponent_family(observed):
    return all(
        observed.get(animal, 0) == count
        for animal, count in _SPA_OPPONENT_ANIMALS.items()
    )


def _spa_apply_market(base_action, candidate_action, obs, step, seat):
    if not _SPA_SELL_RULES:
        return base_action
    result = _spa_copy.deepcopy(base_action)
    market = [list(raw) for raw in _spa_market(result)]
    debt = _SPA_MARKET_DEBT[seat]
    repaid_market = []
    for raw in market:
        order = list(raw)
        if len(order) >= 3 and str(order[0]).upper() == "SELL":
            item = str(order[1]).upper()
            quantity = max(0, int(order[2] or 0))
            reduction = min(quantity, max(0, int(debt.get(item, 0))))
            if reduction:
                quantity -= reduction
                debt[item] -= reduction
                _spa_increment("market_repaid", item, reduction)
            if quantity <= 0:
                continue
            order[2] = quantity
        repaid_market.append(order)
    market = repaid_market
    if (
        _SPA_OPPONENT_ANIMALS
        and _SPA_OPPONENT_ANIMAL_GATE_STEP is not None
        and step == _SPA_OPPONENT_ANIMAL_GATE_STEP
    ):
        observed = _spa_observed_opponent_animals(obs, seat)
        accepted = _spa_matches_opponent_family(observed)
        _SPA_MARKET_FAMILY_OK[seat] = accepted
        if len(_SPA_TELEMETRY["market_family_observations"]) < 8:
            _SPA_TELEMETRY["market_family_observations"].append({
                "step": step,
                "observed": observed,
                "accepted": accepted,
            })
    active_rules = [
        rule for rule in _SPA_SELL_RULES if rule[1] <= step < rule[2]
    ]
    if not active_rules:
        result["market"] = market
        return result
    if _SPA_OPPONENT_ANIMALS:
        if _SPA_OPPONENT_ANIMAL_GATE_STEP is None:
            family_ok = _spa_matches_opponent_family(
                _spa_observed_opponent_animals(obs, seat)
            )
        else:
            family_ok = _SPA_MARKET_FAMILY_OK[seat] is True
        if not family_ok:
            _SPA_TELEMETRY["market_family_rejected"] += 1
            result["market"] = market
            return result
        _SPA_TELEMETRY["market_family_accepted"] += 1
    base_sells = _spa_sell_quantities(market)
    candidate_sells = _spa_sell_quantities(_spa_market(candidate_action))
    shed = dict((_spa_get(obs, "private", {}) or {}).get("shed", {}) or {})
    for item, _start, _stop, rule_cap in active_rules:
        if len(market) >= 10:
            break
        excess = max(0, candidate_sells.get(item, 0) - base_sells.get(item, 0))
        available = max(0, int(shed.get(item, 0) or 0) - base_sells.get(item, 0))
        quantity = min(excess, rule_cap, available)
        if quantity <= 0:
            continue
        market.append(["SELL", item, quantity])
        debt[item] = debt.get(item, 0) + quantity
        _spa_increment("market_advanced", item, quantity)
        if len(_SPA_TELEMETRY["market_advance_steps"]) < 32:
            _SPA_TELEMETRY["market_advance_steps"].append([step, item, quantity])
    result["market"] = market
    return result


def agent(obs, configuration=None):
    day = int(_spa_get(obs, "day", 0) or 0)
    hour = int(_spa_get(obs, "hour", 0) or 0)
    step = day * 24 + hour
    seat = 1 if int(_spa_get(obs, "player", 0) or 0) == 1 else 0
    if step == 0 or step <= _SPA_LAST[seat]:
        _SPA_RNG[seat] = {}
        _SPA_MARKET_DEBT[seat] = {}
        _SPA_MARKET_FAMILY_OK[seat] = None
        _spa_reset()
    _SPA_LAST[seat] = step
    base_action = _spa_call("base", _SPA_BASE, obs, configuration, seat)
    try:
        candidate_action = _spa_call(
            "candidate", _SPA_CANDIDATE, obs, configuration, seat
        )
        _spa_record(base_action, candidate_action, step, obs)
        result = _spa_apply_immediate(base_action, candidate_action, obs, step)
        return _spa_apply_market(result, candidate_action, obs, step, seat)
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
    execute_sell_items: tuple[str, ...] = (),
    sell_cap: int = 0,
    execute_sell_rules: tuple[tuple[str, int, int, int], ...] = (),
    opponent_animal_counts: dict[str, int] | None = None,
    opponent_animal_gate_step: int | None = None,
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
    allowed_sell_items = {
        "WHEAT", "FERTILIZER", "CARROT", "TOMATO", "STRAWBERRY",
        "MELON", "EGG", "MILK", "WOOL",
    }
    normalized_sell_items = tuple(
        sorted({str(item).strip().upper() for item in execute_sell_items})
    )
    if execute_sell_rules and normalized_sell_items:
        raise ValueError("use either execute_sell_rules or execute_sell_items")
    normalized_sell_rules = tuple(
        (
            str(item).strip().upper(),
            int(start),
            int(stop),
            int(cap),
        )
        for item, start, stop, cap in execute_sell_rules
    )
    if not normalized_sell_rules:
        normalized_sell_rules = tuple(
            (item, int(execute_start), int(execute_stop), int(sell_cap))
            for item in normalized_sell_items
        )
    normalized_rule_items = tuple(rule[0] for rule in normalized_sell_rules)
    unknown_sell_items = sorted(set(normalized_sell_items) - allowed_sell_items)
    unknown_sell_items.extend(
        sorted(set(normalized_rule_items) - allowed_sell_items)
    )
    unknown_sell_items = sorted(set(unknown_sell_items))
    if unknown_sell_items:
        raise ValueError(
            f"unsupported sell item(s): {', '.join(unknown_sell_items)}"
        )
    if sell_cap < 0 or (normalized_sell_items and sell_cap < 1):
        raise ValueError("sell_cap must be positive when sell items are enabled")
    for _item, start, stop, cap in normalized_sell_rules:
        if not 0 <= start < stop <= 720:
            raise ValueError("sell rule must satisfy 0 <= start < stop <= 720")
        if cap < 1:
            raise ValueError("sell rule cap must be positive")
    for index, (item, start, stop, _cap) in enumerate(normalized_sell_rules):
        for other_item, other_start, other_stop, _other_cap in normalized_sell_rules[index + 1:]:
            if item == other_item and max(start, other_start) < min(stop, other_stop):
                raise ValueError("sell rules for the same item must not overlap")
    normalized_opponent_animals = {
        str(animal).strip().upper(): int(count)
        for animal, count in (opponent_animal_counts or {}).items()
    }
    if any(animal not in {"COW", "SHEEP", "GOOSE"} for animal in normalized_opponent_animals):
        raise ValueError("opponent animal signature contains an unsupported animal")
    if any(count < 0 for count in normalized_opponent_animals.values()):
        raise ValueError("opponent animal signature counts must be non-negative")
    if opponent_animal_gate_step is not None and not 0 <= opponent_animal_gate_step < 720:
        raise ValueError("opponent animal gate step must be in [0, 720)")
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
        .replace("__SELL_RULES__", repr(normalized_sell_rules))
        .replace("__SELL_CAP__", repr(int(sell_cap)))
        .replace("__OPPONENT_ANIMALS__", repr(normalized_opponent_animals))
        .replace("__OPPONENT_ANIMAL_GATE_STEP__", repr(opponent_animal_gate_step))
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
    parser.add_argument("--execute-sell-item", action="append", default=[])
    parser.add_argument(
        "--execute-sell-rule",
        action="append",
        default=[],
        metavar="ITEM:START:STOP:CAP",
    )
    parser.add_argument("--sell-cap", type=int, default=0)
    parser.add_argument("--opponent-animal-count", action="append", default=[])
    parser.add_argument("--opponent-animal-gate-step", type=int)
    parser.add_argument("--drop-only-item", action="append", default=[])
    parser.add_argument("--drop-max-total", type=int)
    args = parser.parse_args()
    try:
        opponent_animal_counts = parse_animal_counts(args.opponent_animal_count)
        execute_sell_rules = parse_sell_rules(args.execute_sell_rule)
        source = render_audit(
            args.base,
            args.candidate,
            label=args.label,
            execute_operations=tuple(args.execute_operation),
            execute_start=args.execute_start,
            execute_stop=args.execute_stop,
            execute_sell_items=tuple(args.execute_sell_item),
            sell_cap=args.sell_cap,
            execute_sell_rules=execute_sell_rules,
            opponent_animal_counts=opponent_animal_counts,
            opponent_animal_gate_step=args.opponent_animal_gate_step,
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
