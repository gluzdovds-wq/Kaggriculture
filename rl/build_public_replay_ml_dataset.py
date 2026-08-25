"""Build leakage-audited ML datasets from public Kaggriculture replays.

The builder deliberately separates three kinds of information:

* ``policy_rows`` contains full-season summaries and is used only to define
  strategy archetypes.
* ``checkpoint_rows`` contains public state available at days 3/6/9 and is the
  input for opponent-archetype classification.
* ``gate_rows`` contains public day-start state and labels describing whether
  selected high-impact market events occur during the following 24 turns.

Opponent-private shed, seeds and unit inventories are never read into model
features.  Future actions and final rewards appear only in labels/metadata.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from tools.analyze_replay_meta import (
    ANIMALS,
    CROPS,
    PRODUCTS,
    analyze_player,
    normalize_name,
    operation,
    player_names,
    quantity,
    scalar_metrics,
    tile_counts,
)


CHECKPOINT_DAYS = (3, 6, 9)
GATE_DAYS = tuple(range(0, 29))
GATE_HORIZON = 24
SHOPS = (
    "BAKERY",
    "PIZZA_SHOP",
    "BRUNCH_SPOT",
    "YARN_STORE",
    "ICE_CREAM_SHOP",
    "PET_CAFE",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
)
ROUTE_METRICS = (
    "land_purchase_1_step",
    "land_purchase_2_step",
    "total_hires",
    "peak_hands",
    "peak_animals_cow",
    "peak_animals_sheep",
    "peak_animals_goose",
    "seed_buys_wheat",
    "seed_buys_strawberry",
    "actions_water",
    "actions_harvest",
    "actions_fertilize",
    "actions_feed",
    "actions_care",
    "actions_collect_fertilizer",
    "sales_wheat",
    "sales_strawberry",
    "sales_milk",
    "sales_wool",
    "sales_fertilizer",
)


def _prefix(prefix: str, values: dict[str, int | float]) -> dict[str, float]:
    return {f"x_{prefix}_{key.lower()}": float(value or 0) for key, value in values.items()}


def farm_features(prefix: str, farm: dict) -> dict[str, float]:
    farmer = list(farm.get("farmer", []) or [])
    hands = list(farm.get("hands", []) or [])
    values = {
        "money": float(farm.get("money", 0) or 0),
        "hands": float(len(hands)),
        "hires_today": float(farm.get("hires_today", 0) or 0),
        "unlocked": float(len(farm.get("unlocked_quadrants", []) or [])),
        "farmer_x": float(farmer[0] if len(farmer) > 0 else -1),
        "farmer_y": float(farmer[1] if len(farmer) > 1 else -1),
    }
    if hands:
        values["hands_x_mean"] = sum(float(row[0]) for row in hands) / len(hands)
        values["hands_y_mean"] = sum(float(row[1]) for row in hands) / len(hands)
    else:
        values["hands_x_mean"] = -1.0
        values["hands_y_mean"] = -1.0
    values.update({key.lower(): float(value) for key, value in tile_counts(farm).items()})
    return _prefix(prefix, values)


def public_features(observation: dict, focus_seat: int) -> dict[str, float]:
    farms = list(observation.get("farms", []) or [])
    if len(farms) != 2:
        raise ValueError("expected exactly two public farms")
    focus = farm_features("focus", farms[focus_seat])
    other = farm_features("other", farms[1 - focus_seat])
    day = int(observation.get("day", 0) or 0)
    hour = int(observation.get("hour", 0) or 0)
    features = {
        "x_step": float(day * 24 + hour),
        "x_day": float(day),
        "x_hour": float(hour),
        **focus,
        **other,
    }
    for suffix in sorted(
        {key.removeprefix("x_focus_") for key in focus}
        & {key.removeprefix("x_other_") for key in other}
    ):
        features[f"x_delta_{suffix}"] = focus[f"x_focus_{suffix}"] - other[f"x_other_{suffix}"]
    market = observation.get("market", {}) or {}
    inventory = market.get("inventory", {}) or {}
    prices = market.get("prices", {}) or {}
    for product in PRODUCTS:
        lower = product.lower()
        features[f"x_market_inventory_{lower}"] = float(inventory.get(product, 0) or 0)
        features[f"x_market_price_{lower}"] = float(prices.get(product, 0) or 0)
    shops = Counter(
        str(value).upper().split(".")[-1]
        for value in (observation.get("town", {}) or {}).get("unlocked_shops", []) or []
    )
    for shop in SHOPS:
        features[f"x_shop_{shop.lower()}"] = float(shops.get(shop, 0))
    return features


def state_index_by_day(steps: list, seat: int) -> dict[int, int]:
    result = {}
    for index, state in enumerate(steps[:-1]):
        observation = state[seat].get("observation", {}) or {}
        day = int(observation.get("day", index // 24) or 0)
        hour = int(observation.get("hour", index % 24) or 0)
        if hour == 0:
            result.setdefault(day, index)
    return result


def future_gate_labels(steps: list, seat: int, index: int, horizon: int) -> dict:
    counts = Counter()
    animal_quantities = Counter()
    sales = Counter()
    stop = min(len(steps) - 1, index + horizon)
    for action_index in range(index, stop):
        action = steps[action_index + 1][seat].get("action", {}) or {}
        for raw in action.get("market", []) or []:
            op = operation(raw)
            counts[op] += 1
            if op == "BUY_ANIMAL" and isinstance(raw, (list, tuple)) and len(raw) >= 2:
                animal_quantities[str(raw[1]).upper()] += quantity(raw)
            elif op == "SELL" and isinstance(raw, (list, tuple)) and len(raw) >= 2:
                sales[str(raw[1]).upper()] += quantity(raw)
    positive_animals = [animal for animal in ANIMALS if animal_quantities[animal] > 0]
    if not positive_animals:
        animal_type = "NONE"
    elif len(positive_animals) == 1:
        animal_type = positive_animals[0]
    else:
        animal_type = "MIX"
    return {
        "y_buy_land": int(counts["BUY_LAND"] > 0),
        "y_buy_animal": int(sum(animal_quantities.values()) > 0),
        "y_animal_type": animal_type,
        "y_sell_fertilizer": int(sales["FERTILIZER"] > 0),
        "y_sell_premium": int(sum(sales[item] for item in ("MILK", "WOOL", "STRAWBERRY")) > 0),
        "label_land_orders": int(counts["BUY_LAND"]),
        "label_animal_quantity": int(sum(animal_quantities.values())),
        "label_fertilizer_quantity": int(sales["FERTILIZER"]),
        "label_premium_quantity": int(sum(sales[item] for item in ("MILK", "WOOL", "STRAWBERRY"))),
    }


def resolve_targets(replay: dict, requests: list[dict]) -> list[tuple[int, dict]]:
    names = player_names(replay)
    normalized = [normalize_name(name) for name in names]
    resolved = []
    for request in requests:
        target = normalize_name(request.get("replay_name", request["name"]))
        if target not in normalized:
            continue
        resolved.append((normalized.index(target), request))
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_frame(rows: list[dict], path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    order = [column for column in frame if not column.startswith("x_")] + sorted(
        column for column in frame if column.startswith("x_")
    )
    frame = frame[order]
    frame.to_csv(path, index=False, compression="gzip")
    return {
        "path": str(path),
        "rows": len(frame),
        "columns": len(frame.columns),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build(manifest: dict) -> tuple[list[dict], list[dict], list[dict], dict]:
    policy_rows = []
    checkpoint_rows = []
    gate_rows = []
    seen = set()
    missing = []
    replay_bytes = 0
    for replay_number, episode in enumerate(manifest.get("episodes", []), start=1):
        path = Path(episode["path"])
        replay_bytes += path.stat().st_size
        with path.open("r", encoding="utf-8") as handle:
            replay = json.load(handle)
        targets = resolve_targets(replay, episode.get("requested_for", []))
        if not targets:
            missing.append({"episode_id": episode["episode_id"], "names": player_names(replay)})
            continue
        steps = replay.get("steps", []) or []
        for seat, request in targets:
            key = (int(episode["episode_id"]), int(request["submission_id"]))
            if key in seen:
                continue
            seen.add(key)
            game = analyze_player(replay, seat)
            metrics = scalar_metrics(game)
            metadata = {
                "episode_id": int(episode["episode_id"]),
                "submission_id": int(request["submission_id"]),
                "policy_name": str(request.get("policy", request["name"])),
                "team_name": str(request["name"]),
                "rank": request.get("rank"),
                "leaderboard_score": float(request.get("score", 0) or 0),
                "seat": int(seat),
                "seed": int(game["seed"]),
                "final_bank": float(game["final_bank"]),
                "margin": float(game["margin"]),
                "outcome": float(game["outcome"]),
            }
            policy_rows.append({**metadata, **{name: float(metrics[name]) for name in ROUTE_METRICS}})
            by_day = state_index_by_day(steps, seat)
            for day in CHECKPOINT_DAYS:
                if day not in by_day:
                    continue
                index = by_day[day]
                observation = steps[index][seat].get("observation", {}) or {}
                checkpoint_rows.append(
                    {**metadata, "checkpoint_day": day, **public_features(observation, seat)}
                )
            for day in GATE_DAYS:
                if day not in by_day:
                    continue
                index = by_day[day]
                observation = steps[index][seat].get("observation", {}) or {}
                gate_rows.append(
                    {
                        **metadata,
                        "checkpoint_day": day,
                        **future_gate_labels(steps, seat, index, GATE_HORIZON),
                        **public_features(observation, seat),
                    }
                )
        print(
            f"parsed {replay_number}/{len(manifest.get('episodes', []))} "
            f"episode={episode['episode_id']} targets={len(targets)}",
            flush=True,
        )
    audit = {
        "source_schema": manifest.get("schema"),
        "source_unique_episodes": len(manifest.get("episodes", [])),
        "parsed_target_seasons": len(policy_rows),
        "unique_policies": len({row["submission_id"] for row in policy_rows}),
        "checkpoint_days": list(CHECKPOINT_DAYS),
        "gate_days": list(GATE_DAYS),
        "gate_horizon": GATE_HORIZON,
        "replay_bytes": replay_bytes,
        "missing": missing,
        "feature_contract": "public farms + shared market + visible shops only",
        "forbidden_private_fields": ["private.shed", "private.seeds", "private.inventories"],
    }
    return policy_rows, checkpoint_rows, gate_rows, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    policy_rows, checkpoint_rows, gate_rows, audit = build(manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "policy_rows": write_frame(policy_rows, args.output_dir / "policy_rows.csv.gz"),
        "checkpoint_rows": write_frame(checkpoint_rows, args.output_dir / "checkpoint_rows.csv.gz"),
        "gate_rows": write_frame(gate_rows, args.output_dir / "gate_rows.csv.gz"),
    }
    report = {
        "schema": "kaggriculture-public-replay-ml-v1",
        "source_manifest": str(args.manifest),
        "source_manifest_sha256": sha256_file(args.manifest),
        "route_metrics": list(ROUTE_METRICS),
        "audit": audit,
        "outputs": outputs,
    }
    report_path = args.output_dir / "dataset_manifest.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

