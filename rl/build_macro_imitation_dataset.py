"""Build inference-visible macro imitation data from Kaggriculture agents.

Every row pairs an agent's own pre-action observation with the action executed
on the next environment state.  Raw opponent-private state and engine-only
internals are never read.  Actions are summarized into task and market macro
counts so a learned residual can rank planner candidates without replacing the
legal low-level executor.
"""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", action="append", required=True, help="repeat NAME=PATH")
    parser.add_argument("--opponent", default="main.py")
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    episodes = []
    agents = {}
    for name, spec in map(parse_named, args.agent):
        agents[name] = file_meta(spec)
        for seed in range(args.seed, args.seed + args.seeds):
            for seat in (0, 1):
                episode_rows, episode = collect(name, spec, args.opponent, seed, seat)
                rows.extend(episode_rows)
                episodes.append(episode)
                print(f"agent={name} seed={seed} seat={seat} outcome={episode['outcome']:.1f}")
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
