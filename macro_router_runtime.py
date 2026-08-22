"""Inference-legal reactive executor for the distilled macro search routes.

The base policy may run until a configured compatible checkpoint.  Thereafter
this module selects only among stateless reactive plans, so no hidden action
tape or incompatible donor memory is inherited.  The tiny selector is the
externally audited E109 cost-sensitive tree at 360/600 with the frozen constant
fallback at 648.
"""

from __future__ import annotations

import copy


PRODUCTS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK",
    "WOOL", "FERTILIZER",
)
ANIMALS = ("GOOSE", "COW", "SHEEP")
ANIMAL_PRODUCT = {"GOOSE": "EGG", "COW": "MILK", "SHEEP": "WOOL"}
FIRST_YIELD_DAYS = {
    "WHEAT": 2,
    "CARROT": 2,
    "TOMATO": 8,
    "STRAWBERRY": 10,
    "MELON": 10,
}
MACRO_HORIZON = 48

PLANS = {
    "maintain_workers": {
        "crop": None, "animal": None, "liquidate": False,
        "fertilize": False, "expand": False, "target_hires": 4,
        "target_animals": 0, "seed_stock": 0, "sale_limit": 4,
        "wheat_reserve_days": 0, "care": True,
        "collect_fertilizer": True,
    },
    "strawberry_hold_land": {
        "crop": "STRAWBERRY", "animal": None, "liquidate": False,
        "fertilize": True, "expand": False, "target_hires": 3,
        "target_animals": 0, "seed_stock": 4, "sale_limit": 4,
        "wheat_reserve_days": 0, "care": True,
        "collect_fertilizer": True,
    },
    "cow_lean": {
        "crop": "WHEAT", "animal": "COW", "liquidate": False,
        "fertilize": False, "expand": False, "target_hires": 3,
        "target_animals": 2, "seed_stock": 6, "sale_limit": 4,
        "wheat_reserve_days": 3, "care": True,
        "collect_fertilizer": True,
    },
}


def observation_step(obs):
    return int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)


def select_frozen_plan(obs, checkpoint):
    """Small frozen E109 tree; late external failure uses constant fallback."""

    player = int(obs.get("player", 0) or 0)
    own = (obs.get("farms") or [])[player]
    market = (obs.get("market") or {}).get("inventory") or {}
    if checkpoint == 360:
        if float(own.get("money", 0) or 0) <= 18339.5:
            return (
                "cow_lean"
                if float(market.get("MILK", 0) or 0) <= 9990.5
                else "strawberry_hold_land"
            )
        return (
            "cow_lean"
            if float(market.get("WOOL", 0) or 0) <= 10047.0
            else "strawberry_hold_land"
        )
    if checkpoint == 600:
        return (
            "maintain_workers"
            if float(market.get("WOOL", 0) or 0) <= 10042.0
            else "strawberry_hold_land"
        )
    if checkpoint >= 648:
        return "maintain_workers"
    raise ValueError(f"unsupported macro checkpoint {checkpoint}")


def _inventory_total(inventory):
    return sum(max(0, int(value or 0)) for value in (inventory or {}).values())


def _positions(farm):
    return [tuple(farm.get("farmer") or (4, 4))] + [
        tuple(value) for value in (farm.get("hands") or [])
    ]


def _is_shed_adjacent(x, y):
    return x in (4, 5) and y in (4, 5)


def _nearest_shed(x, y):
    access = ((4, 4), (5, 4), (4, 5), (5, 5))
    return min(access, key=lambda point: (abs(x - point[0]) + abs(y - point[1]), point[1], point[0]))


def _move_toward(x, y, tx, ty):
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _tiles(farm):
    for y, row in enumerate(farm.get("tiles") or []):
        for x, tile in enumerate(row or []):
            yield x, y, tile


def _animal_count(farm, animal=None):
    count = 0
    for _x, _y, tile in _tiles(farm):
        if isinstance(tile, dict) and tile.get("animal"):
            if animal is None or str(tile.get("animal")) == animal:
                count += 1
    return count


def _empty_structure_count(farm, animal):
    wanted = "COOP" if animal == "GOOSE" else "PASTURE"
    return sum(
        isinstance(tile, dict)
        and tile.get("kind") == wanted
        and not tile.get("animal")
        for _x, _y, tile in _tiles(farm)
    )


def _farm_item_total(private, item):
    total = max(0, int((private.get("shed") or {}).get(item, 0) or 0))
    total += sum(
        max(0, int((inventory or {}).get(item, 0) or 0))
        for inventory in (private.get("inventories") or [])
    )
    return total


def _task_better(candidate, best, ux, uy):
    if best is None or candidate[0] != best[0]:
        return best is None or candidate[0] > best[0]
    candidate_distance = abs(ux - candidate[1]) + abs(uy - candidate[2])
    best_distance = abs(ux - best[1]) + abs(uy - best[2])
    if candidate_distance != best_distance:
        return candidate_distance < best_distance
    return (candidate[2], candidate[1]) < (best[2], best[1])


def _choose_task(farm, private, plan, unit, day, claimed, remaining_seed):
    positions = _positions(farm)
    inventories = private.get("inventories") or []
    inventory = inventories[unit] if unit < len(inventories) else {}
    ux, uy = positions[unit]
    has_wheat = int((inventory or {}).get("WHEAT", 0) or 0) > 0
    has_fertilizer = int((inventory or {}).get("FERTILIZER", 0) or 0) > 0
    best = None
    for x, y, tile in _tiles(farm):
        if (x, y) in claimed:
            continue
        task = None
        if isinstance(tile, dict) and tile.get("animal"):
            bonus = 12 if tile.get("animal") == plan["animal"] else 0
            if not tile.get("fed_today", False) and has_wheat:
                task = (100 + bonus, x, y, ["FEED"])
            elif int(tile.get("yield_units", 0) or 0) > 0:
                task = (94 + bonus, x, y, ["HARVEST"])
            elif plan["collect_fertilizer"] and tile.get("fertilizer_available", False):
                task = (82 + bonus, x, y, ["COLLECT_FERTILIZER"])
            elif plan["care"] and not tile.get("cared_today", False):
                task = (74 + bonus, x, y, ["CARE"])
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            bonus = 10 if tile.get("crop") == plan["crop"] else 0
            first = 105 if plan["liquidate"] else 92
            crop = str(tile.get("crop"))
            age = day - int(tile.get("planted_day", day) or day)
            if (
                int(tile.get("yield_units", 0) or 0) > 0
                and age >= FIRST_YIELD_DAYS.get(crop, 0)
            ):
                task = (first + bonus, x, y, ["HARVEST"])
            if not tile.get("watered_today", False) and (
                task is None or 88 + bonus > task[0]
            ):
                task = (88 + bonus, x, y, ["WATER"])
            if (
                plan["fertilize"]
                and has_fertilizer
                and tile.get("crop") == plan["crop"]
                and int(tile.get("fertilized_until_day", -1) or -1) < day
                and (task is None or 84 + bonus > task[0])
            ):
                task = (84 + bonus, x, y, ["FERTILIZE"])
        elif isinstance(tile, dict) and tile.get("kind") == "WEED":
            task = (86, x, y, ["DIG"])
        elif (
            isinstance(tile, dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and not tile.get("animal")
            and plan["animal"]
            and int((inventory or {}).get(plan["animal"], 0) or 0) > 0
            and tile.get("kind") == ("COOP" if plan["animal"] == "GOOSE" else "PASTURE")
        ):
            task = (98, x, y, ["PLACE", plan["animal"], 1])
        elif tile is None and plan["crop"] and remaining_seed.get(plan["crop"], 0) > 0:
            task = (52, x, y, ["PLANT", plan["crop"]])
        elif (
            tile is None
            and plan["animal"]
            and _empty_structure_count(farm, plan["animal"]) == 0
            and _farm_item_total(private, plan["animal"]) > 0
        ):
            task = (
                48, x, y,
                ["BUILD_COOP" if plan["animal"] == "GOOSE" else "BUILD_PASTURE"],
            )
        if task is not None and _task_better(task, best, ux, uy):
            best = task
    return best


def reactive_macro_action(obs, plan_name):
    plan = PLANS[plan_name]
    player = int(obs.get("player", 0) or 0)
    farm = (obs.get("farms") or [])[player]
    private = obs.get("private") or {}
    positions = _positions(farm)
    inventories = private.get("inventories") or []
    shed = private.get("shed") or {}
    hands = [["PASS"] for _ in (farm.get("hands") or [])]
    units = [["PASS"], *hands]
    claimed = set()
    seeds = private.get("seeds") or {}
    remaining_seed = {
        crop: max(0, int(seeds.get(crop, 0) or 0))
        for crop in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
    }
    unfed = sum(
        isinstance(tile, dict)
        and bool(tile.get("animal"))
        and not tile.get("fed_today", False)
        for _x, _y, tile in _tiles(farm)
    )
    for unit, (x, y) in enumerate(positions):
        inventory = inventories[unit] if unit < len(inventories) else {}
        carried = _inventory_total(inventory)
        useful_wheat = int((inventory or {}).get("WHEAT", 0) or 0) > 0 and unfed > 0
        useful_animal = (
            plan["animal"]
            and int((inventory or {}).get(plan["animal"], 0) or 0) > 0
        )
        useful_fertilizer = (
            plan["fertilize"]
            and int((inventory or {}).get("FERTILIZER", 0) or 0) > 0
        )
        if carried > 0 and not useful_wheat and not useful_animal and not useful_fertilizer:
            if _is_shed_adjacent(x, y):
                units[unit] = ["DROP"]
            else:
                tx, ty = _nearest_shed(x, y)
                units[unit] = _move_toward(x, y, tx, ty)
            continue
        if carried == 0 and _is_shed_adjacent(x, y):
            if unfed > 0 and int(shed.get("WHEAT", 0) or 0) > 0:
                units[unit] = ["PICKUP", "WHEAT", min(8, int(shed["WHEAT"]))]
                continue
            if (
                plan["animal"]
                and int(shed.get(plan["animal"], 0) or 0) > 0
                and _empty_structure_count(farm, plan["animal"]) > 0
            ):
                units[unit] = ["PICKUP", plan["animal"], 1]
                continue
            if plan["fertilize"] and int(shed.get("FERTILIZER", 0) or 0) > 0:
                units[unit] = ["PICKUP", "FERTILIZER", 1]
                continue
        if carried == 0 and unfed > 0 and int(shed.get("WHEAT", 0) or 0) > 0:
            tx, ty = _nearest_shed(x, y)
            units[unit] = _move_toward(x, y, tx, ty)
            continue
        task = _choose_task(
            farm, private, plan, unit,
            int(obs.get("day", 0) or 0), claimed, remaining_seed,
        )
        if task is not None:
            _priority, tx, ty, operation = task
            claimed.add((tx, ty))
            if (x, y) == (tx, ty):
                units[unit] = operation
                if operation[0] == "PLANT":
                    remaining_seed[operation[1]] -= 1
            else:
                units[unit] = _move_toward(x, y, tx, ty)

    prices = (obs.get("market") or {}).get("prices") or {}
    wheat_reserve = (
        max(4, _animal_count(farm) * plan["wheat_reserve_days"])
        if plan["animal"] else 0
    )
    sales = []
    for index, item in enumerate(PRODUCTS):
        quantity = max(0, int(shed.get(item, 0) or 0))
        if item == "WHEAT":
            quantity = max(0, quantity - wheat_reserve)
        if quantity > 0:
            sales.append((-(quantity * int(prices.get(item, 0) or 0)), index, item))
    sales.sort()
    market = []
    for _value, _index, item in sales[: plan["sale_limit"]]:
        quantity = max(0, int(shed.get(item, 0) or 0))
        if item == "WHEAT":
            quantity = max(0, quantity - wheat_reserve)
        market.append(["SELL", item, quantity])
    if not plan["liquidate"]:
        hires = int(farm.get("hires_today", 0) or 0)
        while hires < plan["target_hires"] and len(market) < 10:
            market.append(["HIRE"])
            hires += 1
        if (
            plan["expand"]
            and len(farm.get("unlocked_quadrants") or []) < 4
            and float(farm.get("money", 0) or 0) > 5000
            and len(market) < 10
        ):
            market.append(["BUY_LAND"])
        crop = plan["crop"]
        if crop and int(seeds.get(crop, 0) or 0) < plan["seed_stock"] and len(market) < 10:
            market.append(["BUY_SEED", crop, plan["seed_stock"] - int(seeds.get(crop, 0) or 0)])
        animal = plan["animal"]
        if (
            animal
            and _animal_count(farm, animal) + _farm_item_total(private, animal)
            < plan["target_animals"]
            and len(market) < 10
        ):
            market.append(["BUY_ANIMAL", animal, 1])
        wheat_need = max(
            0,
            _animal_count(farm) * plan["wheat_reserve_days"]
            - _farm_item_total(private, "WHEAT"),
        )
        if wheat_need > 0 and len(market) < 10:
            market.append(["BUY_PRODUCT", "WHEAT", wheat_need])
        if plan["fertilize"] and _farm_item_total(private, "FERTILIZER") < 2 and len(market) < 10:
            market.append(["BUY_PRODUCT", "FERTILIZER", 2])
    return {"farmer": units[0], "hands": units[1:], "market": market}


def wrap_agent(base_agent, checkpoints=(360, 600, 648)):
    checkpoints = tuple(int(value) for value in checkpoints)
    if not checkpoints or any(value not in (360, 600, 648) for value in checkpoints):
        raise ValueError("checkpoints must be a non-empty subset of 360, 600, 648")
    if tuple(sorted(set(checkpoints))) != checkpoints:
        raise ValueError("checkpoints must be unique and increasing")
    plans = {0: None, 1: None}
    active_until = {0: -1, 1: -1}
    last_steps = {0: -1, 1: -1}
    telemetry = {
        "checkpoints": list(checkpoints),
        "selected": {},
        "macro_turns": 0,
        "fallbacks": 0,
    }

    def routed_agent(obs, configuration=None):
        base = base_agent(obs, configuration)
        step = observation_step(obs)
        seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
        if step == 0 or step <= last_steps[seat]:
            plans[seat] = None
            active_until[seat] = -1
        last_steps[seat] = step
        try:
            if step in checkpoints:
                plans[seat] = select_frozen_plan(obs, step)
                active_until[seat] = step + MACRO_HORIZON
                telemetry["selected"][f"{seat}:{step}"] = plans[seat]
            if plans[seat] is None or step >= active_until[seat]:
                return base
            action = reactive_macro_action(obs, plans[seat])
            telemetry["macro_turns"] += 1
            return action
        except Exception:
            telemetry["fallbacks"] += 1
            return copy.deepcopy(base)

    routed_agent.telemetry = telemetry
    return routed_agent
