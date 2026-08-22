"""Compare legal day-boundary priors for hidden opponent shed and seeds.

The offline target comes from the other seat's replay-private observation.  All
distance features come from the target seat's legal observation.  Evaluation
holds out complete episodes, so the opposite viewpoint of the same game can
never become a nearest neighbour.

This is a state-reconstruction gate, not a claim that lower inventory error
necessarily improves match outcome.  Its purpose is to decide whether a static
public snapshot already improves a checkpoint-marginal particle prior, or
whether a future model must consume persistent legal observation history.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import fmean

import numpy as np

try:
    from rl.audit_hidden_state import (
        ANIMAL_COST,
        PRODUCTS,
        SEED_COST,
        observation_at,
        private_components,
        replay_paths,
        shared_views_equal,
    )
    from rl.build_macro_imitation_dataset import feature_vector
except ModuleNotFoundError:
    # Support ``python rl/evaluate_hidden_state_prior.py`` as well as ``-m``.
    from audit_hidden_state import (  # type: ignore
        ANIMAL_COST,
        PRODUCTS,
        SEED_COST,
        observation_at,
        private_components,
        replay_paths,
        shared_views_equal,
    )
    from build_macro_imitation_dataset import feature_vector  # type: ignore


SHED_ITEMS = PRODUCTS + tuple(ANIMAL_COST)
SEED_ITEMS = tuple(SEED_COST)
TARGET_NAMES = tuple(f"shed_{item.lower()}" for item in SHED_ITEMS) + tuple(
    f"seed_{item.lower()}" for item in SEED_ITEMS
)
FORBIDDEN_FEATURE_PARTS = (
    "episode_id",
    "replay_id",
    "opponent_name",
    "target_name",
    "source_seed",
    "opponent_private",
)


def hidden_target(private) -> tuple[np.ndarray, int]:
    shed, seeds, carried = private_components(private)
    values = [shed.get(item, 0) for item in SHED_ITEMS]
    values.extend(seeds.get(item, 0) for item in SEED_ITEMS)
    return np.asarray(values, dtype=float), sum(carried.values())


def legal_features(observation: dict) -> dict[str, float]:
    values = feature_vector(observation)
    player = int(observation.get("player", 0) or 0)
    farms = list(observation.get("farms", []) or [])
    own = farms[player]
    opponent = farms[1 - player]
    values.update(
        {
            "own_hires_today": float(own.get("hires_today", 0) or 0),
            "opponent_hands": float(len(opponent.get("hands", []) or [])),
            "opponent_unlocked": float(
                len(opponent.get("unlocked_quadrants", []) or [])
            ),
            "opponent_hires_today": float(opponent.get("hires_today", 0) or 0),
        }
    )
    forbidden = [
        name
        for name in values
        if any(part in name.casefold() for part in FORBIDDEN_FEATURE_PARTS)
    ]
    if forbidden:
        raise ValueError(f"forbidden legal feature names: {forbidden}")
    return {str(name): float(value) for name, value in sorted(values.items())}


def examples_from_replay(replay: dict, checkpoints: tuple[int, ...]) -> list[dict]:
    info = dict(replay.get("info", {}) or {})
    episode_id = int(info.get("EpisodeId", 0) or 0)
    examples = []
    for checkpoint in checkpoints:
        observations = observation_at(replay, checkpoint)
        if len(observations) != 2 or not shared_views_equal(*observations):
            raise ValueError(f"episode {episode_id} invalid shared state at {checkpoint}")
        for target_seat in (0, 1):
            target_observation = observations[target_seat]
            target, carried = hidden_target(
                observations[1 - target_seat].get("private")
            )
            examples.append(
                {
                    "episode_id": episode_id,
                    "checkpoint": checkpoint,
                    "target_seat": target_seat,
                    "features": legal_features(target_observation),
                    "target": target,
                    "hidden_carried_units": carried,
                    "prices": {
                        str(key).upper(): int(value or 0)
                        for key, value in (
                            (target_observation.get("market", {}) or {}).get(
                                "prices", {}
                            )
                            or {}
                        ).items()
                    },
                }
            )
    return examples


def gross_value(vector: np.ndarray, prices: dict[str, int]) -> float:
    value = 0.0
    for index, item in enumerate(SHED_ITEMS):
        unit = prices.get(item, 0) if item in PRODUCTS else ANIMAL_COST[item]
        value += float(vector[index]) * unit
    offset = len(SHED_ITEMS)
    for index, item in enumerate(SEED_ITEMS):
        value += float(vector[offset + index]) * SEED_COST[item]
    return value


def prediction_metrics(
    prediction: np.ndarray, target: np.ndarray, prices: dict[str, int]
) -> dict[str, float]:
    difference = np.abs(prediction - target)
    predicted_support = prediction > 0.5
    target_support = target > 0
    union = np.logical_or(predicted_support, target_support).sum()
    intersection = np.logical_and(predicted_support, target_support).sum()
    return {
        "item_l1": float(difference.sum()),
        "item_mae": float(difference.mean()),
        "total_units_abs_error": float(abs(prediction.sum() - target.sum())),
        "gross_value_abs_error": float(
            abs(gross_value(prediction, prices) - gross_value(target, prices))
        ),
        "support_jaccard": float(intersection / union if union else 1.0),
    }


def feature_matrix(
    examples: list[dict], names: tuple[str, ...], feature_key: str = "features"
) -> np.ndarray:
    return np.asarray(
        [
            [example[feature_key].get(name, 0.0) for name in names]
            for example in examples
        ],
        dtype=float,
    )


def standardized_distances(train: np.ndarray, test: np.ndarray) -> np.ndarray:
    mean = train.mean(axis=0)
    scale = train.std(axis=0)
    active = scale > 1e-9
    if not np.any(active):
        return np.zeros(train.shape[0], dtype=float)
    normalized_train = (train[:, active] - mean[active]) / scale[active]
    normalized_test = (test[active] - mean[active]) / scale[active]
    return np.mean((normalized_train - normalized_test) ** 2, axis=1)


def aggregate(rows: list[dict]) -> dict:
    fields = (
        "item_l1",
        "item_mae",
        "total_units_abs_error",
        "gross_value_abs_error",
        "support_jaccard",
    )
    return {
        field: fmean(row[field] for row in rows) if rows else 0.0
        for field in fields
    }


def random_particle_coverage(
    train_targets: np.ndarray,
    target: np.ndarray,
    prices: dict[str, int],
    count: int,
    draws: int,
    rng: np.random.Generator,
) -> dict[str, float]:
    count = min(count, len(train_targets))
    item_best = []
    gross_best = []
    for _ in range(draws):
        indices = rng.choice(len(train_targets), size=count, replace=False)
        particles = train_targets[indices]
        metrics = [prediction_metrics(particle, target, prices) for particle in particles]
        item_best.append(min(row["item_l1"] for row in metrics))
        gross_best.append(min(row["gross_value_abs_error"] for row in metrics))
    return {
        "best_particle_item_l1": fmean(item_best),
        "best_particle_gross_value_abs_error": fmean(gross_best),
    }


def evaluate_checkpoint(
    examples: list[dict],
    neighbors: tuple[int, ...],
    particle_draws: int = 128,
    feature_key: str = "features",
    method_prefix: str = "public",
) -> dict:
    feature_names = tuple(
        sorted({name for example in examples for name in example[feature_key]})
    )
    method_rows = defaultdict(list)
    particle_rows = defaultdict(list)
    same_episode_neighbors = 0
    episodes = sorted({int(example["episode_id"]) for example in examples})
    for fold_index, episode_id in enumerate(episodes):
        train = [example for example in examples if example["episode_id"] != episode_id]
        test = [example for example in examples if example["episode_id"] == episode_id]
        train_features = feature_matrix(train, feature_names, feature_key)
        train_targets = np.stack([example["target"] for example in train])
        marginal = np.median(train_targets, axis=0)
        for test_index, example in enumerate(test):
            target = example["target"]
            prices = example["prices"]
            method_rows["blank"].append(
                prediction_metrics(np.zeros_like(target), target, prices)
            )
            method_rows["checkpoint_median"].append(
                prediction_metrics(marginal, target, prices)
            )
            test_features = feature_matrix([example], feature_names, feature_key)[0]
            order = np.argsort(
                standardized_distances(train_features, test_features),
                kind="stable",
            )
            for count in neighbors:
                random_name = f"checkpoint_random_{count}"
                particle_rows[random_name].append(
                    random_particle_coverage(
                        train_targets,
                        target,
                        prices,
                        count,
                        particle_draws,
                        np.random.default_rng(
                            20260822 + fold_index * 1009 + test_index * 37 + count
                        ),
                    )
                )
                selected_indices = order[: min(count, len(order))]
                selected = [train[index] for index in selected_indices]
                same_episode_neighbors += sum(
                    row["episode_id"] == episode_id for row in selected
                )
                particles = train_targets[selected_indices]
                prediction = np.median(particles, axis=0)
                name = f"{method_prefix}_knn_{count}"
                method_rows[name].append(
                    prediction_metrics(prediction, target, prices)
                )
                particle_metrics = [
                    prediction_metrics(particle, target, prices)
                    for particle in particles
                ]
                particle_rows[name].append(
                    {
                        "best_particle_item_l1": min(
                            row["item_l1"] for row in particle_metrics
                        ),
                        "best_particle_gross_value_abs_error": min(
                            row["gross_value_abs_error"] for row in particle_metrics
                        ),
                    }
                )
    methods = {name: aggregate(rows) for name, rows in sorted(method_rows.items())}
    marginal_error = methods["checkpoint_median"]["item_l1"]
    for name, metrics in methods.items():
        metrics["item_l1_improvement_vs_median"] = (
            (marginal_error - metrics["item_l1"]) / marginal_error
            if marginal_error else 0.0
        )
    particle_coverage = {
        name: {
            field: fmean(row[field] for row in rows)
            for field in (
                "best_particle_item_l1",
                "best_particle_gross_value_abs_error",
            )
        }
        for name, rows in sorted(particle_rows.items())
    }
    return {
        "episode_count": len(episodes),
        "seat_cases": len(examples),
        "legal_feature_count": len(feature_names),
        "marginal_particle_draws": particle_draws,
        "same_episode_neighbor_violations": same_episode_neighbors,
        "hidden_carried_nonzero_cases": sum(
            example["hidden_carried_units"] > 0 for example in examples
        ),
        "methods": methods,
        "particle_coverage": particle_coverage,
    }


def evaluate_fixed_split(
    train: list[dict],
    test: list[dict],
    neighbors: tuple[int, ...],
    particle_draws: int = 128,
    feature_key: str = "features",
    method_prefix: str = "public",
) -> dict:
    if not train or not test:
        raise ValueError("fixed split requires non-empty train and test sets")
    feature_names = tuple(
        sorted(
            {
                name
                for example in [*train, *test]
                for name in example[feature_key]
            }
        )
    )
    train_features = feature_matrix(train, feature_names, feature_key)
    train_targets = np.stack([example["target"] for example in train])
    marginal = np.median(train_targets, axis=0)
    method_rows = defaultdict(list)
    particle_rows = defaultdict(list)
    same_episode_neighbors = 0
    for test_index, example in enumerate(test):
        target = example["target"]
        prices = example["prices"]
        method_rows["blank"].append(
            prediction_metrics(np.zeros_like(target), target, prices)
        )
        method_rows["checkpoint_median"].append(
            prediction_metrics(marginal, target, prices)
        )
        test_features = feature_matrix([example], feature_names, feature_key)[0]
        order = np.argsort(
            standardized_distances(train_features, test_features), kind="stable"
        )
        for count in neighbors:
            particle_rows[f"checkpoint_random_{count}"].append(
                random_particle_coverage(
                    train_targets,
                    target,
                    prices,
                    count,
                    particle_draws,
                    np.random.default_rng(20260822 + test_index * 1009 + count),
                )
            )
            selected_indices = order[: min(count, len(order))]
            selected = [train[index] for index in selected_indices]
            same_episode_neighbors += sum(
                row["episode_id"] == example["episode_id"] for row in selected
            )
            particles = train_targets[selected_indices]
            prediction = np.median(particles, axis=0)
            name = f"{method_prefix}_knn_{count}"
            method_rows[name].append(prediction_metrics(prediction, target, prices))
            candidate_metrics = [
                prediction_metrics(particle, target, prices) for particle in particles
            ]
            particle_rows[name].append(
                {
                    "best_particle_item_l1": min(
                        row["item_l1"] for row in candidate_metrics
                    ),
                    "best_particle_gross_value_abs_error": min(
                        row["gross_value_abs_error"] for row in candidate_metrics
                    ),
                }
            )
    methods = {name: aggregate(rows) for name, rows in sorted(method_rows.items())}
    marginal_error = methods["checkpoint_median"]["item_l1"]
    for metrics in methods.values():
        metrics["item_l1_improvement_vs_median"] = (
            (marginal_error - metrics["item_l1"]) / marginal_error
            if marginal_error
            else 0.0
        )
    return {
        "train_episode_count": len({row["episode_id"] for row in train}),
        "test_episode_count": len({row["episode_id"] for row in test}),
        "train_seat_cases": len(train),
        "test_seat_cases": len(test),
        "legal_feature_count": len(feature_names),
        "marginal_particle_draws": particle_draws,
        "same_episode_neighbor_violations": same_episode_neighbors,
        "hidden_carried_nonzero_cases": sum(
            example["hidden_carried_units"] > 0 for example in test
        ),
        "methods": methods,
        "particle_coverage": {
            name: {
                field: fmean(row[field] for row in rows)
                for field in (
                    "best_particle_item_l1",
                    "best_particle_gross_value_abs_error",
                )
            }
            for name, rows in sorted(particle_rows.items())
        },
    }


def evaluate(
    examples: list[dict],
    checkpoints: tuple[int, ...],
    neighbors: tuple[int, ...],
    particle_draws: int = 128,
) -> dict:
    by_checkpoint = defaultdict(list)
    for example in examples:
        by_checkpoint[int(example["checkpoint"])].append(example)
    results = {
        str(checkpoint): evaluate_checkpoint(
            by_checkpoint[checkpoint], neighbors, particle_draws
        )
        for checkpoint in checkpoints
    }
    return {
        "schema": "kaggriculture-hidden-prior-evaluation-v1",
        "checkpoints": list(checkpoints),
        "target_names": list(TARGET_NAMES),
        "neighbor_counts": list(neighbors),
        "marginal_particle_draws": particle_draws,
        "by_checkpoint": results,
        "leakage_contract": {
            "features": "target-seat legal observation only",
            "group_holdout": "complete EpisodeId",
            "forbidden": list(FORBIDDEN_FEATURE_PARTS),
            "offline_label": "other-seat private replay observation",
        },
        "warning": (
            "Lower hidden-state reconstruction error is only a particle-prior "
            "gate; promotion still requires macro-plan recall and match outcome."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--checkpoint", action="append", type=int)
    parser.add_argument("--neighbors", default="1,3,5,10")
    parser.add_argument("--particle-draws", type=int, default=128)
    parser.add_argument("--output", type=Path)
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
    if not paths:
        parser.error("no replay JSON files found")
    examples = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            examples.extend(examples_from_replay(json.load(handle), checkpoints))
    report = evaluate(examples, checkpoints, neighbors, args.particle_draws)
    report["replay_count"] = len(paths)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
