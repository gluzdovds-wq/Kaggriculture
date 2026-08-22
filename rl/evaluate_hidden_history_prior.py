"""Evaluate legal observation-history features for hidden shed/seed particles.

History is reconstructed exclusively from the target seat's observation stream.
The code never reads replay actions, replay metadata, or the other seat's private
payload while building features.  Other-seat private state remains an offline
label inside ``examples_from_replay`` inherited from the E100 evaluator.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Iterable

try:
    from rl.audit_hidden_state import PRODUCTS, replay_paths
    from rl.evaluate_hidden_state_prior import (
        evaluate_checkpoint,
        evaluate_fixed_split,
        examples_from_replay,
    )
except ModuleNotFoundError:
    from audit_hidden_state import PRODUCTS, replay_paths  # type: ignore
    from evaluate_hidden_state_prior import (  # type: ignore
        evaluate_checkpoint,
        evaluate_fixed_split,
        examples_from_replay,
    )


CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMAL_PRODUCTS = {"GOOSE": "EGG", "COW": "MILK", "SHEEP": "WOOL"}


def clock(observation: dict) -> int:
    return int(observation.get("day", 0) or 0) * 24 + int(
        observation.get("hour", 0) or 0
    )


def target_observation_stream(
    replay: dict, target_seat: int, checkpoint: int
) -> list[dict]:
    observations = []
    for state in replay.get("steps", []) or []:
        if target_seat >= len(state):
            raise ValueError(f"state lacks target seat {target_seat}")
        observation = dict(state[target_seat].get("observation", {}) or {})
        if not observation:
            continue
        step = clock(observation)
        if step > checkpoint:
            break
        observations.append(observation)
    if not observations or clock(observations[-1]) != checkpoint:
        raise ValueError(f"target stream lacks checkpoint {checkpoint}")
    return observations


def tile_kind(tile) -> str:
    if not isinstance(tile, dict):
        return "LOCKED" if tile == "LOCKED" else "EMPTY"
    return str(tile.get("kind", "UNKNOWN")).upper()


def same_plant(left, right) -> bool:
    return (
        tile_kind(left) == "PLANT"
        and tile_kind(right) == "PLANT"
        and str(left.get("crop", "")).upper() == str(right.get("crop", "")).upper()
    )


def animal(tile) -> str:
    if not isinstance(tile, dict):
        return ""
    return str(tile.get("animal", "")).upper()


def add_tile_deltas(features: defaultdict[str, float], previous, current) -> None:
    previous_kind = tile_kind(previous)
    current_kind = tile_kind(current)
    previous_crop = (
        str(previous.get("crop", "")).upper()
        if isinstance(previous, dict)
        else ""
    )
    current_crop = (
        str(current.get("crop", "")).upper() if isinstance(current, dict) else ""
    )
    if current_kind == "PLANT" and not same_plant(previous, current):
        features[f"opponent_plant_started_{current_crop.lower()}"] += 1
    if previous_kind == "PLANT" and not same_plant(previous, current):
        features[f"opponent_plant_removed_{previous_crop.lower()}"] += 1
        features[f"opponent_visible_yield_removed_{previous_crop.lower()}"] += float(
            previous.get("yield_units", 0) or 0
        )
    if same_plant(previous, current):
        removed = max(
            0,
            int(previous.get("yield_units", 0) or 0)
            - int(current.get("yield_units", 0) or 0),
        )
        features[f"opponent_visible_yield_removed_{current_crop.lower()}"] += removed

    previous_animal = animal(previous)
    current_animal = animal(current)
    if current_animal and current_animal != previous_animal:
        features[f"opponent_animal_placed_{current_animal.lower()}"] += 1
    if previous_animal and previous_animal != current_animal:
        features[f"opponent_animal_removed_{previous_animal.lower()}"] += 1
    if previous_animal and previous_animal == current_animal:
        removed = max(
            0,
            int(previous.get("yield_units", 0) or 0)
            - int(current.get("yield_units", 0) or 0),
        )
        product = ANIMAL_PRODUCTS.get(current_animal, current_animal)
        features[f"opponent_visible_yield_removed_{product.lower()}"] += removed
        if previous.get("fertilizer_available", False) and not current.get(
            "fertilizer_available", False
        ):
            features["opponent_fertilizer_collected_events"] += 1

    if current_kind in {"COOP", "PASTURE"} and previous_kind != current_kind:
        features[f"opponent_structure_built_{current_kind.lower()}"] += 1
    if current_kind == "WEED" and previous_kind != "WEED":
        features["opponent_weed_appeared"] += 1
    if previous_kind == "WEED" and current_kind != "WEED":
        features["opponent_weed_removed"] += 1


def paired_tiles(previous_farm: dict, current_farm: dict) -> Iterable[tuple[object, object]]:
    previous_rows = list(previous_farm.get("tiles", []) or [])
    current_rows = list(current_farm.get("tiles", []) or [])
    height = max(len(previous_rows), len(current_rows))
    for y in range(height):
        previous_row = previous_rows[y] if y < len(previous_rows) else []
        current_row = current_rows[y] if y < len(current_rows) else []
        width = max(len(previous_row), len(current_row))
        for x in range(width):
            yield (
                previous_row[x] if x < len(previous_row) else None,
                current_row[x] if x < len(current_row) else None,
            )


def public_history_features(observations: list[dict], target_seat: int) -> dict[str, float]:
    if not observations:
        return {}
    opponent_seat = 1 - target_seat
    features: defaultdict[str, float] = defaultdict(float)
    first_farms = observations[0].get("farms", []) or []
    first_target_money = float(first_farms[target_seat].get("money", 0) or 0)
    first_opponent_money = float(first_farms[opponent_seat].get("money", 0) or 0)
    opponent_money_values = [first_opponent_money]
    target_money_values = [first_target_money]
    features["visible_steps"] = float(max(0, len(observations) - 1))

    for previous, current in zip(observations, observations[1:]):
        previous_farms = previous.get("farms", []) or []
        current_farms = current.get("farms", []) or []
        previous_target = previous_farms[target_seat]
        current_target = current_farms[target_seat]
        previous_opponent = previous_farms[opponent_seat]
        current_opponent = current_farms[opponent_seat]

        for label, old_farm, new_farm, values in (
            ("target", previous_target, current_target, target_money_values),
            ("opponent", previous_opponent, current_opponent, opponent_money_values),
        ):
            old_money = float(old_farm.get("money", 0) or 0)
            new_money = float(new_farm.get("money", 0) or 0)
            delta = new_money - old_money
            values.append(new_money)
            if delta > 0:
                features[f"{label}_money_positive_total"] += delta
                features[f"{label}_money_positive_events"] += 1
                features[f"{label}_money_positive_max"] = max(
                    features[f"{label}_money_positive_max"], delta
                )
            elif delta < 0:
                spend = -delta
                features[f"{label}_money_negative_total"] += spend
                features[f"{label}_money_negative_events"] += 1
                features[f"{label}_money_negative_max"] = max(
                    features[f"{label}_money_negative_max"], spend
                )

        old_quadrants = len(previous_opponent.get("unlocked_quadrants", []) or [])
        new_quadrants = len(current_opponent.get("unlocked_quadrants", []) or [])
        features["opponent_land_unlock_events"] += max(0, new_quadrants - old_quadrants)
        old_hands = len(previous_opponent.get("hands", []) or [])
        new_hands = len(current_opponent.get("hands", []) or [])
        features["opponent_hand_add_events"] += max(0, new_hands - old_hands)
        features["opponent_max_hands"] = max(features["opponent_max_hands"], new_hands)
        features["opponent_max_hires_today"] = max(
            features["opponent_max_hires_today"],
            float(current_opponent.get("hires_today", 0) or 0),
        )
        features["opponent_max_quadrants"] = max(
            features["opponent_max_quadrants"], new_quadrants
        )
        for old_tile, new_tile in paired_tiles(previous_opponent, current_opponent):
            add_tile_deltas(features, old_tile, new_tile)

        previous_market = previous.get("market", {}) or {}
        current_market = current.get("market", {}) or {}
        previous_inventory = previous_market.get("inventory", {}) or {}
        current_inventory = current_market.get("inventory", {}) or {}
        previous_prices = previous_market.get("prices", {}) or {}
        current_prices = current_market.get("prices", {}) or {}
        for product in PRODUCTS:
            lower = product.lower()
            inventory_delta = int(current_inventory.get(product, 0) or 0) - int(
                previous_inventory.get(product, 0) or 0
            )
            features[f"market_inventory_net_{lower}"] += inventory_delta
            features[f"market_inventory_abs_{lower}"] += abs(inventory_delta)
            features[f"market_inventory_up_{lower}"] += max(0, inventory_delta)
            features[f"market_inventory_down_{lower}"] += max(0, -inventory_delta)
            price_delta = int(current_prices.get(product, 0) or 0) - int(
                previous_prices.get(product, 0) or 0
            )
            features[f"market_price_net_{lower}"] += price_delta
            features[f"market_price_abs_{lower}"] += abs(price_delta)

    features["opponent_money_net"] = opponent_money_values[-1] - first_opponent_money
    features["opponent_money_range"] = max(opponent_money_values) - min(
        opponent_money_values
    )
    features["target_money_net"] = target_money_values[-1] - first_target_money
    features["target_money_range"] = max(target_money_values) - min(target_money_values)

    for crop in CROPS:
        lower = crop.lower()
        features[f"opponent_plant_started_{lower}"] += 0
        features[f"opponent_plant_removed_{lower}"] += 0
        features[f"opponent_visible_yield_removed_{lower}"] += 0
    for animal_name, product in ANIMAL_PRODUCTS.items():
        lower = animal_name.lower()
        features[f"opponent_animal_placed_{lower}"] += 0
        features[f"opponent_animal_removed_{lower}"] += 0
        features[f"opponent_visible_yield_removed_{product.lower()}"] += 0
    for product in PRODUCTS:
        lower = product.lower()
        for stem in (
            "market_inventory_net",
            "market_inventory_abs",
            "market_inventory_up",
            "market_inventory_down",
            "market_price_net",
            "market_price_abs",
        ):
            features[f"{stem}_{lower}"] += 0
    return dict(sorted(features.items()))


def combined_history_features(
    replay: dict,
    target_seat: int,
    checkpoint: int,
    snapshot_features: dict[str, float],
) -> dict[str, float]:
    stream = target_observation_stream(replay, target_seat, checkpoint)
    recent_start = max(0, checkpoint - 72)
    recent = [observation for observation in stream if clock(observation) >= recent_start]
    combined = dict(snapshot_features)
    combined.update(
        {
            f"history_{name}": value
            for name, value in public_history_features(stream, target_seat).items()
        }
    )
    combined.update(
        {
            f"history_recent72_{name}": value
            for name, value in public_history_features(recent, target_seat).items()
        }
    )
    return dict(sorted(combined.items()))


def history_examples_from_replay(
    replay: dict, checkpoints: tuple[int, ...]
) -> list[dict]:
    examples = examples_from_replay(replay, checkpoints)
    for example in examples:
        example["history_features"] = combined_history_features(
            replay,
            int(example["target_seat"]),
            int(example["checkpoint"]),
            example["features"],
        )
    return examples


def comparison(snapshot: dict, history: dict, count: int) -> dict:
    snapshot_name = f"public_knn_{count}"
    history_name = f"history_knn_{count}"
    output = {}
    for field in ("item_l1", "gross_value_abs_error"):
        old = snapshot["methods"][snapshot_name][field]
        new = history["methods"][history_name][field]
        output[f"{field}_snapshot"] = old
        output[f"{field}_history"] = new
        output[f"{field}_improvement"] = (old - new) / old if old else 0.0
    for field in (
        "best_particle_item_l1",
        "best_particle_gross_value_abs_error",
    ):
        old = snapshot["particle_coverage"][snapshot_name][field]
        new = history["particle_coverage"][history_name][field]
        output[f"{field}_snapshot"] = old
        output[f"{field}_history"] = new
        output[f"{field}_improvement"] = (old - new) / old if old else 0.0
    return output


def evaluate_history(
    examples: list[dict],
    checkpoints: tuple[int, ...],
    neighbors: tuple[int, ...],
    particle_draws: int,
) -> dict:
    by_checkpoint: defaultdict[int, list[dict]] = defaultdict(list)
    for example in examples:
        by_checkpoint[int(example["checkpoint"])].append(example)
    selected_count = max(neighbors)
    results = {}
    for checkpoint in checkpoints:
        rows = by_checkpoint[checkpoint]
        snapshot = evaluate_checkpoint(
            rows,
            neighbors,
            particle_draws,
            feature_key="features",
            method_prefix="public",
        )
        history = evaluate_checkpoint(
            rows,
            neighbors,
            particle_draws,
            feature_key="history_features",
            method_prefix="history",
        )
        results[str(checkpoint)] = {
            "snapshot": snapshot,
            "history": history,
            f"knn_{selected_count}_comparison": comparison(
                snapshot, history, selected_count
            ),
        }
    late_checks = []
    for checkpoint in (360, 648):
        if str(checkpoint) not in results:
            continue
        values = results[str(checkpoint)][f"knn_{selected_count}_comparison"]
        late_checks.append(
            all(
                values[f"{field}_improvement"] > 0
                for field in (
                    "item_l1",
                    "gross_value_abs_error",
                    "best_particle_item_l1",
                    "best_particle_gross_value_abs_error",
                )
            )
        )
    return {
        "schema": "kaggriculture-hidden-history-prior-v1",
        "checkpoints": list(checkpoints),
        "neighbor_counts": list(neighbors),
        "particle_draws": particle_draws,
        "by_checkpoint": results,
        "pre_registered_late_gate_pass": bool(late_checks) and all(late_checks),
        "leakage_contract": {
            "history_source": "target-seat observation stream only",
            "excluded_from_features": [
                "replay actions",
                "other-seat private observation",
                "EpisodeId",
                "team/opponent name",
                "source seed",
            ],
            "offline_label": "other-seat private observation at checkpoint",
        },
    }


def evaluate_history_transfer(
    train_examples: list[dict],
    test_examples: list[dict],
    checkpoints: tuple[int, ...],
    neighbors: tuple[int, ...],
    particle_draws: int,
) -> dict:
    train_by_checkpoint: defaultdict[int, list[dict]] = defaultdict(list)
    test_by_checkpoint: defaultdict[int, list[dict]] = defaultdict(list)
    for example in train_examples:
        train_by_checkpoint[int(example["checkpoint"])].append(example)
    for example in test_examples:
        test_by_checkpoint[int(example["checkpoint"])].append(example)
    selected_count = max(neighbors)
    results = {}
    for checkpoint in checkpoints:
        snapshot = evaluate_fixed_split(
            train_by_checkpoint[checkpoint],
            test_by_checkpoint[checkpoint],
            neighbors,
            particle_draws,
            feature_key="features",
            method_prefix="public",
        )
        history = evaluate_fixed_split(
            train_by_checkpoint[checkpoint],
            test_by_checkpoint[checkpoint],
            neighbors,
            particle_draws,
            feature_key="history_features",
            method_prefix="history",
        )
        results[str(checkpoint)] = {
            "snapshot": snapshot,
            "history": history,
            f"knn_{selected_count}_comparison": comparison(
                snapshot, history, selected_count
            ),
        }
    late_checks = []
    for checkpoint in (360, 648):
        if str(checkpoint) not in results:
            continue
        values = results[str(checkpoint)][f"knn_{selected_count}_comparison"]
        late_checks.append(
            all(
                values[f"{field}_improvement"] > 0
                for field in (
                    "item_l1",
                    "gross_value_abs_error",
                    "best_particle_item_l1",
                    "best_particle_gross_value_abs_error",
                )
            )
        )
    return {
        "by_checkpoint": results,
        "pre_registered_late_gate_pass": bool(late_checks) and all(late_checks),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--checkpoint", action="append", type=int)
    parser.add_argument("--neighbors", default="10")
    parser.add_argument("--particle-draws", type=int, default=128)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--holdout", nargs="+", type=Path)
    args = parser.parse_args()
    checkpoints = tuple(args.checkpoint or (72, 360, 648))
    neighbors = tuple(sorted({int(value) for value in args.neighbors.split(",")}))
    if not checkpoints or any(value < 0 for value in checkpoints):
        parser.error("checkpoints must be non-negative")
    if not neighbors or any(value <= 0 for value in neighbors):
        parser.error("neighbor counts must be positive")
    if args.particle_draws <= 0:
        parser.error("particle draws must be positive")
    paths = replay_paths(args.replays)
    examples = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            examples.extend(history_examples_from_replay(json.load(handle), checkpoints))
    report = evaluate_history(examples, checkpoints, neighbors, args.particle_draws)
    report["replay_count"] = len(paths)
    if args.holdout:
        holdout_paths = replay_paths(args.holdout)
        holdout_examples = []
        for path in holdout_paths:
            with path.open("r", encoding="utf-8") as handle:
                holdout_examples.extend(
                    history_examples_from_replay(json.load(handle), checkpoints)
                )
        train_episode_ids = {example["episode_id"] for example in examples}
        overlap_ids = {
            example["episode_id"]
            for example in holdout_examples
            if example["episode_id"] in train_episode_ids
        }
        disjoint_holdout = [
            example
            for example in holdout_examples
            if example["episode_id"] not in train_episode_ids
        ]
        report["transfer"] = evaluate_history_transfer(
            examples,
            disjoint_holdout,
            checkpoints,
            neighbors,
            args.particle_draws,
        )
        report["transfer"]["holdout_files"] = len(holdout_paths)
        report["transfer"]["excluded_overlap_episode_ids"] = sorted(overlap_ids)
        report["transfer"]["disjoint_holdout_episode_count"] = len(
            {example["episode_id"] for example in disjoint_holdout}
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
