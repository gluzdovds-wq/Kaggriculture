"""Evaluate inference-visible leaf values on grouped Kaggriculture replays.

Inputs are the controlled seat's legal observation: public farms/market/town
plus its own private shed, seeds and carried inventory.  EpisodeId, names,
source seed, replay actions and the opponent's private payload are never model
features.  Targets are offline future money margins at +24 turns and at the end
of the game.

The script compares deterministic money/marked-value baselines with ridge,
k-nearest-neighbour and a small deterministic regression tree.  Hyperparameters
and the winning model family are selected only by complete-EpisodeId group CV
inside the training block, then transferred once to a disjoint holdout block.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import fmean

import numpy as np

try:
    from rl.audit_hidden_state import replay_paths
    from rl.build_macro_imitation_dataset import (
        ANIMAL_RULES,
        CROP_RULES,
        CROPS,
        PRODUCTS,
        feature_vector,
    )
except ModuleNotFoundError:
    from audit_hidden_state import replay_paths  # type: ignore
    from build_macro_imitation_dataset import (  # type: ignore
        ANIMAL_RULES,
        CROP_RULES,
        CROPS,
        PRODUCTS,
        feature_vector,
    )


ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
FORBIDDEN_FEATURE_PARTS = (
    "episode_id",
    "replay_id",
    "opponent_name",
    "team_name",
    "source_seed",
    "opponent_private",
    "action",
)
TARGETS = ("margin_24", "final_margin")


def money_margin(observation: dict, seat: int) -> float:
    farms = list(observation.get("farms", []) or [])
    return float(farms[seat].get("money", 0) or 0) - float(
        farms[1 - seat].get("money", 0) or 0
    )


def public_farm_value(farm: dict, prices: dict[str, float]) -> float:
    value = float(farm.get("money", 0) or 0)
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", "")).upper()
            if kind == "PLANT":
                crop = str(tile.get("crop", "")).upper()
                rule = CROP_RULES.get(crop)
                if not rule:
                    continue
                price = float(prices.get(crop, 0) or 0)
                value += float(tile.get("yield_units", 0) or 0) * price * 0.85
                value += float(rule["max_yield"]) * price * (
                    0.80 if rule["ongoing"] else 0.25
                )
                continue
            animal = str(tile.get("animal", "")).upper()
            rule = ANIMAL_RULES.get(animal)
            if rule:
                price = float(prices.get(rule["product"], 0) or 0)
                value += ANIMAL_COST[animal] * 0.65
                value += float(tile.get("yield_units", 0) or 0) * price * 0.85
                value += price * 1.5
            elif kind in {"COOP", "PASTURE"}:
                value += 40.0
    return value


def private_value(private: dict, prices: dict[str, float]) -> float:
    shed = dict(private.get("shed", {}) or {})
    seeds = dict(private.get("seeds", {}) or {})
    inventories = list(private.get("inventories", []) or [])
    quantities: defaultdict[str, float] = defaultdict(float)
    for item, value in shed.items():
        quantities[str(item).upper()] += max(0.0, float(value or 0))
    for inventory in inventories:
        for item, value in dict(inventory or {}).items():
            quantities[str(item).upper()] += max(0.0, float(value or 0))
    value = 0.0
    for item, quantity in quantities.items():
        unit = prices.get(item, 0.0) if item in PRODUCTS else ANIMAL_COST.get(item, 0) * 0.75
        value += quantity * float(unit) * 0.90
    for crop, count in seeds.items():
        value += max(0.0, float(count or 0)) * SEED_COST.get(str(crop).upper(), 0) * 0.45
    return value


def legal_marked_margin(observation: dict) -> tuple[float, float, float]:
    seat = int(observation.get("player", 0) or 0)
    farms = list(observation.get("farms", []) or [])
    prices = {
        str(item).upper(): float(value or 0)
        for item, value in (
            ((observation.get("market", {}) or {}).get("prices", {}) or {}).items()
        )
    }
    own_public = public_farm_value(farms[seat], prices)
    opponent_public = public_farm_value(farms[1 - seat], prices)
    own_private = private_value(dict(observation.get("private", {}) or {}), prices)
    return own_public + own_private - opponent_public, own_private, opponent_public


def legal_value_features(observation: dict) -> dict[str, float]:
    values = feature_vector(observation)
    seat = int(observation.get("player", 0) or 0)
    farms = list(observation.get("farms", []) or [])
    own = farms[seat]
    opponent = farms[1 - seat]
    marked, own_private, opponent_public = legal_marked_margin(observation)
    values.update(
        {
            "own_hires_today": float(own.get("hires_today", 0) or 0),
            "opponent_hands": float(len(opponent.get("hands", []) or [])),
            "opponent_unlocked": float(
                len(opponent.get("unlocked_quadrants", []) or [])
            ),
            "opponent_hires_today": float(opponent.get("hires_today", 0) or 0),
            "legal_marked_margin": marked,
            "own_private_marked_value": own_private,
            "opponent_public_marked_value": opponent_public,
        }
    )
    forbidden = [
        name
        for name in values
        if any(part in name.casefold() for part in FORBIDDEN_FEATURE_PARTS)
    ]
    if forbidden:
        raise ValueError(f"forbidden feature names: {forbidden}")
    return {str(name): float(value) for name, value in sorted(values.items())}


def examples_from_replay(replay: dict, checkpoints: tuple[int, ...]) -> list[dict]:
    steps = list(replay.get("steps", []) or [])
    if not steps:
        raise ValueError("empty replay")
    episode_id = int((replay.get("info", {}) or {}).get("EpisodeId", 0) or 0)
    if not episode_id:
        raise ValueError("missing EpisodeId")
    final_index = len(steps) - 1
    rows = []
    for checkpoint in checkpoints:
        if checkpoint < 0 or checkpoint > final_index:
            raise ValueError(f"checkpoint {checkpoint} outside replay")
        future_index = min(final_index, checkpoint + 24)
        for seat in (0, 1):
            observation = dict(steps[checkpoint][seat].get("observation", {}) or {})
            future = dict(steps[future_index][seat].get("observation", {}) or {})
            final = dict(steps[final_index][seat].get("observation", {}) or {})
            if int(observation.get("player", seat) or 0) != seat:
                raise ValueError(f"episode {episode_id} seat mismatch at {checkpoint}")
            rows.append(
                {
                    "episode_id": episode_id,
                    "checkpoint": checkpoint,
                    "seat": seat,
                    "features": legal_value_features(observation),
                    "targets": {
                        "margin_24": money_margin(future, seat),
                        "final_margin": money_margin(final, seat),
                    },
                }
            )
    return rows


def load_examples(paths: list[Path], checkpoints: tuple[int, ...]) -> list[dict]:
    rows = []
    for path in paths:
        replay = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(examples_from_replay(replay, checkpoints))
    return rows


def feature_names(rows: list[dict]) -> tuple[str, ...]:
    return tuple(sorted({name for row in rows for name in row["features"]}))


def matrix(rows: list[dict], names: tuple[str, ...]) -> np.ndarray:
    return np.asarray(
        [[float(row["features"].get(name, 0.0)) for name in names] for row in rows],
        dtype=np.float64,
    )


def targets(rows: list[dict], name: str) -> np.ndarray:
    return np.asarray([float(row["targets"][name]) for row in rows], dtype=np.float64)


def group_folds(rows: list[dict], count: int = 5) -> list[np.ndarray]:
    episodes = sorted({int(row["episode_id"]) for row in rows})
    assignments = {episode: index % count for index, episode in enumerate(episodes)}
    folds = [
        np.asarray(
            [assignments[int(row["episode_id"])] == fold for row in rows],
            dtype=bool,
        )
        for fold in range(count)
    ]
    if any(not mask.any() or mask.all() for mask in folds):
        raise ValueError("invalid group folds")
    return folds


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    active = scale > 1e-9
    scale = scale.copy()
    scale[~active] = 1.0
    return center, scale, active


def ridge_fit(x: np.ndarray, y: np.ndarray, penalty: float) -> dict:
    center, scale, active = standardize_fit(x)
    z = (x[:, active] - center[active]) / scale[active]
    target_center = float(y.mean())
    centered_y = y - target_center
    gram = z.T @ z
    weights = np.linalg.solve(
        gram + np.eye(gram.shape[0], dtype=np.float64) * penalty,
        z.T @ centered_y,
    )
    return {
        "center": center,
        "scale": scale,
        "active": active,
        "target_center": target_center,
        "weights": weights,
    }


def ridge_predict(model: dict, x: np.ndarray) -> np.ndarray:
    active = model["active"]
    z = (x[:, active] - model["center"][active]) / model["scale"][active]
    return model["target_center"] + z @ model["weights"]


def select_ridge(
    x: np.ndarray,
    y: np.ndarray,
    offset: np.ndarray,
    folds: list[np.ndarray],
    penalties: tuple[float, ...],
) -> tuple[float, dict[str, float]]:
    errors = {penalty: [] for penalty in penalties}
    for holdout in folds:
        train = ~holdout
        for penalty in penalties:
            prediction = offset[holdout] + ridge_predict(
                ridge_fit(x[train], y[train] - offset[train], penalty),
                x[holdout],
            )
            errors[penalty].extend(np.abs(prediction - y[holdout]).tolist())
    scores = {str(penalty): fmean(values) for penalty, values in errors.items()}
    selected = min(penalties, key=lambda value: (scores[str(value)], value))
    return selected, scores


def knn_predict(
    train_x: np.ndarray,
    train_y: np.ndarray,
    query_x: np.ndarray,
    count: int,
    batch_size: int = 128,
) -> np.ndarray:
    count = min(count, len(train_x))
    output = []
    train_norm = np.square(train_x).sum(axis=1)
    for start in range(0, len(query_x), batch_size):
        query = query_x[start : start + batch_size]
        distance = (
            np.square(query).sum(axis=1)[:, None]
            + train_norm[None, :]
            - 2.0 * query @ train_x.T
        )
        indices = np.argpartition(distance, count - 1, axis=1)[:, :count]
        output.append(np.mean(train_y[indices], axis=1))
    return np.concatenate(output)


def standardized_pair(
    train_x: np.ndarray, query_x: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    center, scale, active = standardize_fit(train_x)
    return (
        (train_x[:, active] - center[active]) / scale[active],
        (query_x[:, active] - center[active]) / scale[active],
    )


def select_knn(
    x: np.ndarray,
    y: np.ndarray,
    offset: np.ndarray,
    folds: list[np.ndarray],
    counts: tuple[int, ...],
) -> tuple[int, dict[str, float]]:
    errors = {count: [] for count in counts}
    for holdout in folds:
        train = ~holdout
        train_x, query_x = standardized_pair(x[train], x[holdout])
        for count in counts:
            prediction = offset[holdout] + knn_predict(
                train_x, y[train] - offset[train], query_x, count
            )
            errors[count].extend(np.abs(prediction - y[holdout]).tolist())
    scores = {str(count): fmean(values) for count, values in errors.items()}
    selected = min(counts, key=lambda value: (scores[str(value)], value))
    return selected, scores


def tree_feature_subset(x: np.ndarray, y: np.ndarray, limit: int) -> np.ndarray:
    centered_x = x - x.mean(axis=0)
    centered_y = y - y.mean()
    denominator = np.sqrt(np.square(centered_x).sum(axis=0))
    correlation = np.zeros(x.shape[1], dtype=np.float64)
    active = denominator > 1e-9
    correlation[active] = np.abs(
        centered_x[:, active].T @ centered_y / denominator[active]
    )
    order = np.argsort(-correlation, kind="stable")
    return order[: min(limit, len(order))]


def fit_tree(
    x: np.ndarray,
    y: np.ndarray,
    depth: int,
    min_leaf: int = 32,
    feature_limit: int = 48,
) -> dict:
    candidates = tree_feature_subset(x, y, feature_limit)

    def build(indices: np.ndarray, remaining: int) -> dict:
        values = y[indices]
        prediction = float(values.mean())
        node = {"prediction": prediction}
        if remaining <= 0 or len(indices) < min_leaf * 2:
            return node
        parent_sse = float(np.square(values - prediction).sum())
        best = None
        for feature in candidates:
            column = x[indices, feature]
            thresholds = np.unique(
                np.quantile(column, np.linspace(0.1, 0.9, 9))
            )
            for threshold in thresholds:
                left_mask = column <= threshold
                left_count = int(left_mask.sum())
                right_count = len(indices) - left_count
                if left_count < min_leaf or right_count < min_leaf:
                    continue
                left_values = values[left_mask]
                right_values = values[~left_mask]
                sse = float(
                    np.square(left_values - left_values.mean()).sum()
                    + np.square(right_values - right_values.mean()).sum()
                )
                candidate = (sse, int(feature), float(threshold), left_mask)
                if best is None or candidate[:3] < best[:3]:
                    best = candidate
        if best is None or best[0] >= parent_sse - 1e-9:
            return node
        _, feature, threshold, left_mask = best
        node.update(
            {
                "feature": feature,
                "threshold": threshold,
                "left": build(indices[left_mask], remaining - 1),
                "right": build(indices[~left_mask], remaining - 1),
            }
        )
        return node

    return build(np.arange(len(y), dtype=int), depth)


def tree_predict(tree: dict, x: np.ndarray) -> np.ndarray:
    output = np.empty(len(x), dtype=np.float64)
    for row_index, row in enumerate(x):
        node = tree
        while "feature" in node:
            node = (
                node["left"]
                if row[int(node["feature"])] <= float(node["threshold"])
                else node["right"]
            )
        output[row_index] = float(node["prediction"])
    return output


def select_tree(
    x: np.ndarray,
    y: np.ndarray,
    offset: np.ndarray,
    folds: list[np.ndarray],
    depths: tuple[int, ...],
) -> tuple[int, dict[str, float]]:
    errors = {depth: [] for depth in depths}
    for holdout in folds:
        train = ~holdout
        for depth in depths:
            prediction = offset[holdout] + tree_predict(
                fit_tree(x[train], y[train] - offset[train], depth),
                x[holdout],
            )
            errors[depth].extend(np.abs(prediction - y[holdout]).tolist())
    scores = {str(depth): fmean(values) for depth, values in errors.items()}
    selected = min(depths, key=lambda value: (scores[str(value)], value))
    return selected, scores


def rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and values[order[stop]] == values[order[start]]:
            stop += 1
        rank = 0.5 * (start + stop - 1)
        ranks[order[start:stop]] = rank
        start = stop
    return ranks


def spearman(prediction: np.ndarray, truth: np.ndarray) -> float:
    if len(prediction) < 2:
        return 0.0
    left = rankdata(prediction)
    right = rankdata(truth)
    if left.std() < 1e-12 or right.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def paired_winner_accuracy(
    rows: list[dict], prediction: np.ndarray, truth: np.ndarray
) -> float:
    grouped: defaultdict[tuple[int, int], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[(int(row["episode_id"]), int(row["checkpoint"]))].append(index)
    correct = []
    for indices in grouped.values():
        if len(indices) != 2:
            continue
        left, right = indices
        truth_order = np.sign(truth[left] - truth[right])
        predicted_order = np.sign(prediction[left] - prediction[right])
        correct.append(float(truth_order == predicted_order))
    return fmean(correct) if correct else 0.0


def metrics(rows: list[dict], prediction: np.ndarray, truth: np.ndarray) -> dict:
    error = prediction - truth
    nonzero = np.abs(truth) > 1e-9
    return {
        "rows": len(rows),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "bias": float(np.mean(error)),
        "spearman": spearman(prediction, truth),
        "sign_accuracy": float(
            np.mean(np.sign(prediction[nonzero]) == np.sign(truth[nonzero]))
        )
        if nonzero.any()
        else 1.0,
        "paired_winner_accuracy": paired_winner_accuracy(rows, prediction, truth),
    }


def metric_slices(
    rows: list[dict], prediction: np.ndarray, truth: np.ndarray
) -> dict:
    result = {"all": metrics(rows, prediction, truth)}
    for checkpoint in sorted({int(row["checkpoint"]) for row in rows}):
        mask = np.asarray(
            [int(row["checkpoint"]) == checkpoint for row in rows], dtype=bool
        )
        result[str(checkpoint)] = metrics(
            [row for row, keep in zip(rows, mask) if keep],
            prediction[mask],
            truth[mask],
        )
    return result


def checkpoint_mean_prediction(
    train_rows: list[dict], train_y: np.ndarray, test_rows: list[dict]
) -> np.ndarray:
    values: defaultdict[int, list[float]] = defaultdict(list)
    for row, target in zip(train_rows, train_y):
        values[int(row["checkpoint"])].append(float(target))
    means = {checkpoint: fmean(rows) for checkpoint, rows in values.items()}
    global_mean = float(train_y.mean())
    return np.asarray(
        [means.get(int(row["checkpoint"]), global_mean) for row in test_rows],
        dtype=np.float64,
    )


def group_cv_baseline_mae(
    train_rows: list[dict], train_y: np.ndarray, folds: list[np.ndarray]
) -> dict[str, float]:
    predictions = {
        "current_money": np.asarray(
            [row["features"]["money_delta"] for row in train_rows],
            dtype=np.float64,
        ),
        "legal_marked": np.asarray(
            [row["features"]["legal_marked_margin"] for row in train_rows],
            dtype=np.float64,
        ),
        "checkpoint_mean": np.empty(len(train_rows), dtype=np.float64),
    }
    for holdout in folds:
        train = ~holdout
        predictions["checkpoint_mean"][holdout] = checkpoint_mean_prediction(
            [row for row, keep in zip(train_rows, train) if keep],
            train_y[train],
            [row for row, keep in zip(train_rows, holdout) if keep],
        )
    return {
        name: float(np.mean(np.abs(prediction - train_y)))
        for name, prediction in predictions.items()
    }


def evaluate_target(
    name: str,
    train_rows: list[dict],
    holdout_rows: list[dict],
    train_x: np.ndarray,
    holdout_x: np.ndarray,
    folds: list[np.ndarray],
) -> dict:
    train_y = targets(train_rows, name)
    holdout_y = targets(holdout_rows, name)
    train_offsets = {
        "zero": np.zeros(len(train_rows), dtype=np.float64),
        "current_money": np.asarray(
            [row["features"]["money_delta"] for row in train_rows],
            dtype=np.float64,
        ),
        "legal_marked": np.asarray(
            [row["features"]["legal_marked_margin"] for row in train_rows],
            dtype=np.float64,
        ),
    }
    holdout_offsets = {
        "zero": np.zeros(len(holdout_rows), dtype=np.float64),
        "current_money": np.asarray(
            [row["features"]["money_delta"] for row in holdout_rows],
            dtype=np.float64,
        ),
        "legal_marked": np.asarray(
            [row["features"]["legal_marked_margin"] for row in holdout_rows],
            dtype=np.float64,
        ),
    }
    baselines_train = {
        "current_money": train_offsets["current_money"],
        "legal_marked": train_offsets["legal_marked"],
        "checkpoint_mean": checkpoint_mean_prediction(train_rows, train_y, train_rows),
    }
    baselines_holdout = {
        "current_money": holdout_offsets["current_money"],
        "legal_marked": holdout_offsets["legal_marked"],
        "checkpoint_mean": checkpoint_mean_prediction(
            train_rows, train_y, holdout_rows
        ),
    }
    hyperparameter_cv = {}
    selected_hyperparameters = {}
    family_cv = {}
    model_predictions = {}
    knn_train_x, knn_holdout_x = standardized_pair(train_x, holdout_x)
    for offset_name, train_offset in train_offsets.items():
        holdout_offset = holdout_offsets[offset_name]

        ridge_penalty, ridge_cv = select_ridge(
            train_x,
            train_y,
            train_offset,
            folds,
            (0.1, 1.0, 10.0, 100.0, 1000.0),
        )
        ridge_name = f"ridge_residual_to_{offset_name}"
        hyperparameter_cv[ridge_name] = ridge_cv
        selected_hyperparameters[ridge_name] = ridge_penalty
        family_cv[ridge_name] = ridge_cv[str(ridge_penalty)]
        ridge_model = ridge_fit(
            train_x, train_y - train_offset, ridge_penalty
        )
        model_predictions[ridge_name] = holdout_offset + ridge_predict(
            ridge_model, holdout_x
        )

        knn_count, knn_cv = select_knn(
            train_x, train_y, train_offset, folds, (5, 10, 20, 40)
        )
        knn_name = f"knn_residual_to_{offset_name}"
        hyperparameter_cv[knn_name] = knn_cv
        selected_hyperparameters[knn_name] = knn_count
        family_cv[knn_name] = knn_cv[str(knn_count)]
        model_predictions[knn_name] = holdout_offset + knn_predict(
            knn_train_x,
            train_y - train_offset,
            knn_holdout_x,
            knn_count,
        )

        tree_depth, tree_cv = select_tree(
            train_x, train_y, train_offset, folds, (2, 3, 4)
        )
        tree_name = f"tree_residual_to_{offset_name}"
        hyperparameter_cv[tree_name] = tree_cv
        selected_hyperparameters[tree_name] = tree_depth
        family_cv[tree_name] = tree_cv[str(tree_depth)]
        tree_model = fit_tree(
            train_x, train_y - train_offset, tree_depth
        )
        model_predictions[tree_name] = holdout_offset + tree_predict(
            tree_model, holdout_x
        )

    selected_family = min(family_cv, key=lambda key: (family_cv[key], key))
    baseline_group_cv = group_cv_baseline_mae(train_rows, train_y, folds)
    baseline_train_metrics = {
        method: metric_slices(train_rows, prediction, train_y)
        for method, prediction in baselines_train.items()
    }
    selected_baseline = min(
        baseline_group_cv,
        key=lambda key: (baseline_group_cv[key], key),
    )
    return {
        "target": name,
        "hyperparameter_group_cv_mae": hyperparameter_cv,
        "selected_hyperparameters": selected_hyperparameters,
        "selected_model_family_by_group_cv": selected_family,
        "selected_model_group_cv_mae": family_cv[selected_family],
        "model_family_group_cv_mae": family_cv,
        "baseline_group_cv_mae": baseline_group_cv,
        "selected_baseline_by_group_cv": selected_baseline,
        "train_baselines": baseline_train_metrics,
        "holdout": {
            "baselines": {
                method: metric_slices(holdout_rows, prediction, holdout_y)
                for method, prediction in baselines_holdout.items()
            },
            "models": {
                method: metric_slices(holdout_rows, prediction, holdout_y)
                for method, prediction in model_predictions.items()
            },
        },
    }


def transfer_gate(results: dict[str, dict]) -> dict:
    checks = {}
    for target, report in results.items():
        model_name = report["selected_model_family_by_group_cv"]
        model = report["holdout"]["models"][model_name]
        baselines = report["holdout"]["baselines"]
        best_overall_mae = min(
            baselines, key=lambda name: (baselines[name]["all"]["mae"], name)
        )
        best_overall_spearman = max(
            baselines,
            key=lambda name: (baselines[name]["all"]["spearman"], name),
        )
        target_checks = {
            "overall_mae": (
                model["all"]["mae"]
                < baselines[best_overall_mae]["all"]["mae"]
            ),
            "overall_spearman": (
                model["all"]["spearman"]
                > baselines[best_overall_spearman]["all"]["spearman"]
            ),
        }
        gate_baselines = {
            "overall_mae": best_overall_mae,
            "overall_spearman": best_overall_spearman,
        }
        for checkpoint in (360, 648):
            checkpoint_key = str(checkpoint)
            best_mae = min(
                baselines,
                key=lambda name: (baselines[name][checkpoint_key]["mae"], name),
            )
            best_winner = max(
                baselines,
                key=lambda name: (
                    baselines[name][checkpoint_key]["paired_winner_accuracy"],
                    name,
                ),
            )
            target_checks[f"mae_{checkpoint}"] = (
                model[checkpoint_key]["mae"]
                < baselines[best_mae][checkpoint_key]["mae"]
            )
            target_checks[f"winner_{checkpoint}"] = (
                model[checkpoint_key]["paired_winner_accuracy"]
                >= baselines[best_winner][checkpoint_key]["paired_winner_accuracy"]
            )
            gate_baselines[f"mae_{checkpoint}"] = best_mae
            gate_baselines[f"winner_{checkpoint}"] = best_winner
        checks[target] = {
            "model": model_name,
            "strongest_holdout_baseline_per_metric": gate_baselines,
            "checks": target_checks,
            "pass": all(target_checks.values()),
        }
    return {"pass": all(row["pass"] for row in checks.values()), "targets": checks}


def evaluate(args: argparse.Namespace) -> dict:
    checkpoints = tuple(args.checkpoint or range(24, 649, 24))
    train_paths = replay_paths(args.replays)
    holdout_paths = replay_paths(args.holdout)
    train_rows = load_examples(train_paths, checkpoints)
    holdout_rows = load_examples(holdout_paths, checkpoints)
    train_ids = {int(row["episode_id"]) for row in train_rows}
    overlap_ids = sorted(
        {int(row["episode_id"]) for row in holdout_rows if int(row["episode_id"]) in train_ids}
    )
    holdout_rows = [
        row for row in holdout_rows if int(row["episode_id"]) not in train_ids
    ]
    if not holdout_rows:
        raise ValueError("no disjoint holdout rows")
    names = feature_names(train_rows)
    train_x = matrix(train_rows, names)
    holdout_x = matrix(holdout_rows, names)
    folds = group_folds(train_rows, args.folds)
    results = {
        target: evaluate_target(
            target, train_rows, holdout_rows, train_x, holdout_x, folds
        )
        for target in TARGETS
    }
    report = {
        "schema": "kaggriculture-inference-visible-leaf-value-v1",
        "train_replay_count": len(train_paths),
        "train_episode_count": len(train_ids),
        "holdout_replay_count": len(holdout_paths),
        "disjoint_holdout_episode_count": len(
            {int(row["episode_id"]) for row in holdout_rows}
        ),
        "excluded_overlap_episode_ids": overlap_ids,
        "checkpoints": list(checkpoints),
        "train_rows": len(train_rows),
        "holdout_rows": len(holdout_rows),
        "feature_count": len(names),
        "feature_names": list(names),
        "group_folds": args.folds,
        "results": results,
        "pre_registered_transfer_gate": transfer_gate(results),
        "leakage_contract": {
            "features": "controlled-seat legal observation only",
            "allowed_private": "controlled seat shed, seeds and carried inventories",
            "excluded": list(FORBIDDEN_FEATURE_PARTS),
            "split": "complete EpisodeId; fixed top20-to-live transfer",
            "offline_targets": ["public money margin at +24", "public final money margin"],
        },
        "warning": (
            "Predictive value transfer is only the first N73 gate. A planner "
            "still requires counterfactual macro-plan regret, latency and "
            "official-engine paired outcomes before submission."
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--holdout", nargs="+", required=True, type=Path)
    parser.add_argument("--checkpoint", action="append", type=int)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.folds < 2:
        parser.error("folds must be at least two")
    report = evaluate(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
