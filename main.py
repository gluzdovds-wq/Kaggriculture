"""Deterministic crop baseline for the Kaggriculture competition.

The submission API requires an ``agent(obs)`` function in this file.  The
strategy deliberately keeps no module-level game state: every decision is
reconstructed from the observation, which makes local evaluation and Kaggle
execution reproducible and safe when several games share a Python process.
"""

CROP = "CARROT"
MAX_YIELD_DAY = 3
SEED_PRICE = 20
HANDS_PER_DAY = 5
LAST_PLANTING_DAY = 26
LAST_PLANTING_HOUR = 20
SELL_LIMIT = 100


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _shed_tiles(board_size):
    half = board_size // 2
    return [(half - 1, half - 1), (half, half - 1),
            (half - 1, half), (half, half)]


def _move_towards(position, target):
    """Return a deterministic shortest-path move on the obstacle-free board."""
    x, y = position
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _tile_tasks(farm, private, day, hour):
    """Build prioritized, unique jobs for the currently unlocked field."""
    tasks = []
    empty = []
    tiles = farm["tiles"]

    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if tile is None:
                empty.append((x, y))
                continue
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "WEED":
                tasks.append((2, x, y, "DIG"))
                continue
            if tile.get("kind") != "PLANT" or tile.get("crop") != CROP:
                continue

            # Water before harvesting so the last eligible watering bonus is
            # included in the crop's yield.
            if not tile.get("watered_today", False):
                tasks.append((0, x, y, "WATER"))
            elif day - tile.get("planted_day", day) >= MAX_YIELD_DAY:
                tasks.append((1, x, y, "HARVEST"))

    seeds = max(0, int(private.get("seeds", {}).get(CROP, 0)))
    can_plant = day <= LAST_PLANTING_DAY and hour <= LAST_PLANTING_HOUR
    if can_plant and seeds:
        positions = [tuple(farm["farmer"])] + [tuple(p) for p in farm.get("hands", [])]
        # When seed stock is low, reserve it for the empty tiles closest to any
        # worker. This also guarantees that simultaneous PLANT requests never
        # exceed the available stock (the environment would reject all of them).
        empty.sort(key=lambda p: (min(_distance(p, u) for u in positions), p[1], p[0]))
        for x, y in empty[:seeds]:
            tasks.append((3, x, y, "PLANT"))

    return tasks, len(empty)


def _assign_jobs(positions, tasks):
    """Greedily match each unit to one distinct highest-priority nearby job."""
    remaining_units = set(range(len(positions)))
    remaining_tasks = set(range(len(tasks)))
    assignments = {}

    while remaining_units and remaining_tasks:
        best = None
        for unit_idx in remaining_units:
            for task_idx in remaining_tasks:
                priority, x, y, _ = tasks[task_idx]
                candidate = (
                    priority,
                    _distance(positions[unit_idx], (x, y)),
                    unit_idx,
                    y,
                    x,
                    task_idx,
                )
                if best is None or candidate < best:
                    best = candidate
        unit_idx = best[2]
        task_idx = best[5]
        assignments[unit_idx] = tasks[task_idx]
        remaining_units.remove(unit_idx)
        remaining_tasks.remove(task_idx)

    return assignments


def _return_action(position, inventory, board_size):
    """Move carried goods to the nearest shed access tile, or drop them."""
    if not any(amount > 0 for amount in inventory.values()):
        return None
    access = min(_shed_tiles(board_size), key=lambda p: (_distance(position, p), p[1], p[0]))
    if tuple(position) == access:
        return ["DROP"]
    return _move_towards(position, access)


def _market_actions(farm, private, day, hour, empty_count):
    orders = [["SELL", CROP, SELL_LIMIT]]

    if day <= LAST_PLANTING_DAY:
        seeds = int(private.get("seeds", {}).get(CROP, 0))
        needed = max(0, empty_count - seeds)
        affordable = max(0, int(farm.get("money", 0)) // SEED_PRICE)
        if needed and affordable:
            orders.append(["BUY_SEED", CROP, min(needed, affordable)])

    # Hiring is cheapest at the beginning of each day and hands are available
    # from the following turn. Five hands give enough capacity to service a 5x5
    # field while keeping seven of ten market-order slots in use at most.
    if hour == 0:
        orders.extend([["HIRE"] for _ in range(HANDS_PER_DAY)])

    return orders[:10]


def agent(obs):
    farms = obs.get("farms", [])
    player = int(obs.get("player", 0))
    private = obs.get("private", {}) or {}
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    board_size = len(farm.get("tiles", [])) or 10
    positions = [tuple(farm["farmer"])] + [tuple(p) for p in farm.get("hands", [])]
    inventories = list(private.get("inventories", []))
    inventories.extend({} for _ in range(len(positions) - len(inventories)))

    tasks, empty_count = _tile_tasks(farm, private, day, hour)
    assignments = _assign_jobs(positions, tasks)
    actions = []

    for unit_idx, position in enumerate(positions):
        inventory = inventories[unit_idx] or {}

        # During the final day, bank harvested goods instead of relying on the
        # automatic end-of-day drop, which occurs after the last market phase.
        if day >= 29:
            returning = _return_action(position, inventory, board_size)
            if returning is not None:
                actions.append(returning)
                continue

        task = assignments.get(unit_idx)
        if task is None:
            # Opportunistically bank inventory when already standing at the shed.
            returning = _return_action(position, inventory, board_size)
            if returning == ["DROP"]:
                actions.append(returning)
            else:
                actions.append(["PASS"])
            continue

        _, x, y, operation = task
        target = (x, y)
        if position == target:
            actions.append([operation, CROP] if operation == "PLANT" else [operation])
        else:
            actions.append(_move_towards(position, target))

    return {
        "farmer": actions[0] if actions else ["PASS"],
        "hands": actions[1:],
        "market": _market_actions(farm, private, day, hour, empty_count),
    }

