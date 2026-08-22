"""Build inference-visible macro imitation data from Kaggriculture agents.

Every row pairs an agent's own pre-action observation with the action executed
on the next environment state.  Raw opponent-private state and engine-only
internals are never read.  Actions are summarized into task and market macro
counts so a learned residual can rank planner candidates without replacing the
legal low-level executor.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import contextlib
import hashlib
import importlib.util
import io
import json
from collections import Counter
from pathlib import Path


BUILT_INS = {"pass", "random", "starter"}
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "SHEEP", "COW")
SHOPS = ("BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "YARN_STORE", "ICE_CREAM_SHOP", "PET_CAFE", "SMOOTHIE_SHOP", "FARMERS_MARKET")
CROP_RULES = {
    "WHEAT": {"first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT": {"first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO": {"first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON": {"first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
ANIMAL_RULES = {
    "GOOSE": {"first_yield_day": 4, "interval": 1, "product": "EGG"},
    "COW": {"first_yield_day": 8, "interval": 2, "product": "MILK"},
    "SHEEP": {"first_yield_day": 6, "interval": 3, "product": "WOOL"},
}
FIELD_GROUPS = {
    "NORTH": "move",
    "SOUTH": "move",
    "EAST": "move",
    "WEST": "move",
    "PASS": "pass",
    "PLANT": "plant",
    "WATER": "service",
    "FEED": "service",
    "CARE": "service",
    "FERTILIZE": "service",
    "COLLECT_FERTILIZER": "collect",
    "HARVEST": "harvest",
    "BUILD_COOP": "build",
    "BUILD_PASTURE": "build",
    "DIG": "dig",
    "PICKUP": "logistics",
    "DROP": "logistics",
    "PLACE": "logistics",
}


def make_environment(seed: int):
    # Keep importing the large optional engine out of feature/label unit tests.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from kaggle_environments import make

    return make("kaggriculture", configuration={"seed": seed}, debug=False)


def get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def load_agent(spec: str, tag: str):
    if spec in BUILT_INS:
        return spec
    path = Path(spec).resolve()
    module_spec = importlib.util.spec_from_file_location(tag, path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.agent


def parse_named(value: str) -> tuple[str, str]:
    if "=" in value:
        return tuple(value.split("=", 1))
    path = Path(value)
    return (path.parent.name or path.stem, value)


def file_meta(spec: str) -> dict:
    if spec in BUILT_INS:
        return {"kind": "built-in", "name": spec}
    path = Path(spec).resolve()
    data = path.read_bytes()
    return {
        "kind": "file",
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def tile_features(farm) -> dict[str, float]:
    counts = Counter()
    for row in get(farm, "tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", "UNKNOWN"))
            counts[f"tile_{kind.lower()}"] += 1
            if tile.get("crop"):
                counts[f"crop_{str(tile['crop']).lower()}"] += 1
            if tile.get("animal"):
                counts[f"animal_{str(tile['animal']).lower()}"] += 1
            if kind == "PLANT" and not tile.get("watered_today", False):
                counts["plants_unwatered"] += 1
            if kind in {"COOP", "PASTURE"} and tile.get("animal") and not tile.get("fed_today", False):
                counts["animals_unfed"] += 1
            if tile.get("yield_units", 0):
                counts["tiles_with_yield"] += 1
    features = dict(counts)
    for key in ("tile_plant", "tile_pasture", "tile_coop", "tile_weed", "plants_unwatered", "animals_unfed", "tiles_with_yield"):
        features.setdefault(key, 0)
    for crop in CROPS:
        features.setdefault(f"crop_{crop.lower()}", 0)
    for animal in ANIMALS:
        features.setdefault(f"animal_{animal.lower()}", 0)
    return {key: float(value) for key, value in sorted(features.items())}


def _positions(farm) -> list[tuple[int, int]]:
    values = [get(farm, "farmer", None), *(get(farm, "hands", []) or [])]
    return [tuple(map(int, value)) for value in values if isinstance(value, (list, tuple)) and len(value) >= 2]


def _eta(position: tuple[int, int], target: tuple[int, int]) -> int:
    """Static-board lower bound: movement turns plus one interaction action."""
    return abs(position[0] - target[0]) + abs(position[1] - target[1]) + 1


def _target_summary(
    features: dict[str, float],
    name: str,
    units: list[tuple[int, int]],
    targets: list[tuple[int, int]],
    turns_today: int,
) -> None:
    etas = [min(_eta(unit, target) for unit in units) for target in targets] if units else []
    features[f"forward_{name}_targets"] = float(len(targets))
    features[f"forward_{name}_eta_min"] = float(min(etas) if etas else 0)
    features[f"forward_{name}_eta_mean"] = float(sum(etas) / len(etas) if etas else 0)
    features[f"forward_{name}_reachable_today"] = float(sum(eta <= turns_today for eta in etas))


def observation_forward_features(obs) -> dict[str, float]:
    """Position/age features available only while the full observation exists.

    These are lower-bound ETA and exact object-clock summaries, not a claim that
    multiple tasks can all be served independently by the same nearest worker.
    """
    player = int(get(obs, "player", 0) or 0)
    farm = list(get(obs, "farms", []) or [])[player]
    private = get(obs, "private", {}) or {}
    inventories = list(get(private, "inventories", []) or [])
    prices = dict(get(get(obs, "market", {}) or {}, "prices", {}) or {})
    day = int(get(obs, "day", 0) or 0)
    hour = int(get(obs, "hour", 0) or 0)
    step = int(get(obs, "step", 0) or 0)
    turns_today = 24 - hour
    units = _positions(farm)
    service_targets = []
    harvest_targets = []
    weed_targets = []
    fertilizer_targets = []
    ready_units = 0
    ready_value = 0
    critical_plants = 0
    critical_animals = 0
    pending_care = 0
    fertilized_tiles = 0
    crop_first_etas = []
    animal_next_etas = []
    terminal_stranded = 0
    decay_turns = []
    tiles = get(farm, "tiles", []) or []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row or []):
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", ""))
            position = (x, y)
            if kind == "WEED":
                weed_targets.append(position)
                continue
            if kind == "PLANT":
                crop = str(tile.get("crop", ""))
                rule = CROP_RULES.get(crop)
                if not tile.get("watered_today", False):
                    service_targets.append(position)
                    critical_plants += int(tile.get("consecutive_unwatered", 0) >= 1)
                if tile.get("fertilized_until_day", -1) >= day:
                    fertilized_tiles += 1
                if rule:
                    first_day = int(tile.get("planted_day", day)) + rule["first_yield_day"]
                    crop_first_etas.append(max(0, first_day - day))
                    terminal_stranded += int(first_day >= 30)
                    available = int(tile.get("yield_units", 0) or 0)
                    mature = rule["ongoing"] or day >= first_day
                    if available > 0 and mature:
                        harvest_targets.append(position)
                        ready_units += available
                        ready_value += available * int(prices.get(crop, 0) or 0)
                lifespan = int(tile.get("max_lifespan_step", -1) or -1)
                if lifespan >= 0:
                    decay_turns.append(max(0, lifespan - step))
                continue
            animal = str(tile.get("animal", ""))
            if animal:
                rule = ANIMAL_RULES.get(animal)
                if not tile.get("fed_today", False):
                    service_targets.append(position)
                    critical_animals += int(tile.get("consecutive_unfed", 0) >= 1)
                if tile.get("fertilizer_available", False):
                    fertilizer_targets.append(position)
                pending_care += int(tile.get("pending_care_bonus", 0) or 0)
                available = int(tile.get("yield_units", 0) or 0)
                if available > 0:
                    harvest_targets.append(position)
                    ready_units += available
                    if rule:
                        ready_value += available * int(prices.get(rule["product"], 0) or 0)
                if rule:
                    first_day = int(tile.get("placed_day", day)) + rule["first_yield_day"]
                    next_day = max(first_day, day + 1)
                    remainder = (next_day - first_day) % rule["interval"]
                    if remainder:
                        next_day += rule["interval"] - remainder
                    animal_next_etas.append(next_day - day)
                    terminal_stranded += int(next_day >= 30)

    features = {
        "forward_ready_yield_units": float(ready_units),
        "forward_ready_yield_value": float(ready_value),
        "forward_critical_plants": float(critical_plants),
        "forward_critical_animals": float(critical_animals),
        "forward_pending_care_bonus": float(pending_care),
        "forward_fertilizer_available_tiles": float(len(fertilizer_targets)),
        "forward_fertilized_tiles": float(fertilized_tiles),
        "forward_crop_first_yield_days_min": float(min(crop_first_etas) if crop_first_etas else 0),
        "forward_crop_first_yield_days_mean": float(sum(crop_first_etas) / len(crop_first_etas) if crop_first_etas else 0),
        "forward_animal_next_yield_days_min": float(min(animal_next_etas) if animal_next_etas else 0),
        "forward_animal_next_yield_days_mean": float(sum(animal_next_etas) / len(animal_next_etas) if animal_next_etas else 0),
        "forward_terminal_stranded_objects": float(terminal_stranded),
        "forward_decay_turns_min": float(min(decay_turns) if decay_turns else 0),
    }
    _target_summary(features, "service", units, service_targets, turns_today)
    _target_summary(features, "harvest", units, harvest_targets, turns_today)
    _target_summary(features, "weed", units, weed_targets, turns_today)
    _target_summary(features, "fertilizer", units, fertilizer_targets, turns_today)
    shed_access = [(4, 4), (5, 4), (4, 5), (5, 5)]
    carried_units = [
        units[index]
        for index, inventory in enumerate(inventories)
        if index < len(units) and sum(max(0, int(value or 0)) for value in dict(inventory or {}).values()) > 0
    ]
    carried_etas = [min(_eta(unit, target) for target in shed_access) for unit in carried_units]
    features["forward_carried_units"] = float(len(carried_units))
    features["forward_carried_to_shed_eta_min"] = float(min(carried_etas) if carried_etas else 0)
    features["forward_carried_to_shed_reachable_today"] = float(sum(eta <= turns_today for eta in carried_etas))
    return features


def feature_vector(obs) -> dict[str, float]:
    player = int(get(obs, "player", 0) or 0)
    farms = list(get(obs, "farms", []) or [])
    own = farms[player]
    opponent = farms[1 - player]
    private = get(obs, "private", {}) or {}
    shed = dict(get(private, "shed", {}) or {})
    seeds = dict(get(private, "seeds", {}) or {})
    inventories = list(get(private, "inventories", []) or [])
    market = get(obs, "market", {}) or {}
    prices = dict(get(market, "prices", {}) or {})
    inventory = dict(get(market, "inventory", {}) or {})
    shops = Counter(
        str(value).upper()
        for value in (get(get(obs, "town", {}) or {}, "unlocked_shops", []) or [])
    )
    features = {
        "step": float(get(obs, "step", 0) or 0),
        "day": float(get(obs, "day", 0) or 0),
        "hour": float(get(obs, "hour", 0) or 0),
        "own_money": float(get(own, "money", 0) or 0),
        "opponent_money": float(get(opponent, "money", 0) or 0),
        "money_delta": float((get(own, "money", 0) or 0) - (get(opponent, "money", 0) or 0)),
        "hands": float(len(get(own, "hands", []) or [])),
        "unlocked": float(len(get(own, "unlocked_quadrants", []) or [])),
        "shed_total": float(sum(max(0, int(value or 0)) for value in shed.values())),
        "carried_total": float(sum(max(0, int(value or 0)) for row in inventories for value in dict(row or {}).values())),
    }
    features.update({f"own_{key}": value for key, value in tile_features(own).items()})
    features.update({f"opponent_{key}": value for key, value in tile_features(opponent).items()})
    for product in PRODUCTS:
        lower = product.lower()
        features[f"shed_{lower}"] = float(shed.get(product, 0) or 0)
        features[f"price_{lower}"] = float(prices.get(product, 0) or 0)
        features[f"market_{lower}"] = float(inventory.get(product, 0) or 0)
    for crop in CROPS:
        features[f"seed_{crop.lower()}"] = float(seeds.get(crop, 0) or 0)
    for shop in SHOPS:
        features[f"shop_{shop.lower()}"] = float(shops.get(shop, 0) or 0)
    features.update(observation_forward_features(obs))
    return features


def operation(action) -> str:
    if not action:
        return "PASS"
    if isinstance(action, (list, tuple)) and action:
        return str(action[0]).upper()
    return "PASS"


def macro_label(action) -> dict:
    action = action or {}
    units = [action.get("farmer"), *(action.get("hands") or [])]
    field_ops = Counter(operation(raw) for raw in units)
    field_groups = Counter(FIELD_GROUPS.get(op, "other") for op in field_ops.elements())
    market_ops = Counter(operation(raw) for raw in (action.get("market") or []))
    active_groups = sorted(group for group, count in field_groups.items() if group != "pass" and count)
    active_market = sorted(op.lower() for op, count in market_ops.items() if count)
    return {
        "task_macro": "+".join(active_groups) if active_groups else "pass",
        "market_macro": "+".join(active_market) if active_market else "none",
        "field_operations": dict(sorted(field_ops.items())),
        "field_groups": dict(sorted(field_groups.items())),
        "market_operations": dict(sorted(market_ops.items())),
    }


def collect(agent_name: str, agent_spec: str, opponent_spec: str, seed: int, seat: int) -> tuple[list[dict], dict]:
    agent = load_agent(agent_spec, f"imitation_{agent_name}_{seed}_{seat}")
    opponent = load_agent(opponent_spec, f"imitation_opponent_{agent_name}_{seed}_{seat}")
    players = [agent, opponent] if seat == 0 else [opponent, agent]
    env = make_environment(seed)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)
    final = env.steps[-1]
    rows = []
    for step in range(len(env.steps) - 1):
        pre = env.steps[step][seat].observation
        executed = env.steps[step + 1][seat].action
        rows.append(
            {
                "agent": agent_name,
                "seed": seed,
                "seat": seat,
                "features": feature_vector(pre),
                "label": macro_label(executed),
            }
        )
    episode = {
        "agent": agent_name,
        "seed": seed,
        "seat": seat,
        "bank": float(final[seat].reward),
        "opponent_bank": float(final[1 - seat].reward),
        "outcome": 1.0 if final[seat].reward > final[1 - seat].reward else (0.5 if final[seat].reward == final[1 - seat].reward else 0.0),
    }
    return rows, episode


def collect_task(task: tuple[str, str, str, int, int]) -> tuple[list[dict], dict]:
    """Pickle-friendly adapter used by the optional process pool."""
    return collect(*task)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", action="append", required=True, help="repeat NAME=PATH")
    parser.add_argument("--opponent", default="main.py")
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    episodes = []
    agents = {}
    tasks = []
    for name, spec in map(parse_named, args.agent):
        agents[name] = file_meta(spec)
        for seed in range(args.seed, args.seed + args.seeds):
            for seat in (0, 1):
                tasks.append((name, spec, args.opponent, seed, seat))
    if args.jobs < 1:
        raise ValueError("--jobs must be positive")
    if args.jobs == 1:
        results = map(collect_task, tasks)
        pool = None
    else:
        pool = ProcessPoolExecutor(max_workers=args.jobs)
        results = pool.map(collect_task, tasks)
    try:
        for task, (episode_rows, episode) in zip(tasks, results):
            rows.extend(episode_rows)
            episodes.append(episode)
            print(
                f"agent={task[0]} seed={task[3]} seat={task[4]} "
                f"outcome={episode['outcome']:.1f}",
                flush=True,
            )
    finally:
        if pool is not None:
            pool.shutdown()
    payload = {
        "schema": "inference-visible macro imitation v1",
        "engine": "kaggle-environments==1.32.7",
        "agents": agents,
        "opponent": file_meta(args.opponent),
        "seed_start": args.seed,
        "seed_count": args.seeds,
        "episodes": episodes,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload), encoding="utf-8")
    print(f"rows={len(rows)} report={args.output}")


if __name__ == "__main__":
    main()
