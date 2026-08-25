"""Train opponent-archetype and conditional market-gate GBDTs.

This is an offline analysis model, not a direct action executor.  Route labels
are policy-level clusters derived from complete seasons; inputs are restricted
to public state at an earlier checkpoint.  Evaluation holds out complete
submission policies so adjacent turns or games from one bot cannot leak across
the train/test boundary.
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import RobustScaler


SEED = 20260825
warnings.filterwarnings(
    "ignore",
    message="`sklearn.utils.parallel.delayed` should be used.*",
    category=UserWarning,
)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
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
GATES = (
    "y_buy_land",
    "y_buy_animal",
    "y_sell_fertilizer",
    "y_sell_premium",
)


def model_parameters() -> dict:
    return {
        "loss": "log_loss",
        "learning_rate": 0.06,
        "max_iter": 220,
        "max_leaf_nodes": 15,
        "min_samples_leaf": 12,
        "l2_regularization": 5.0,
        "early_stopping": False,
        "random_state": SEED,
    }


def balanced_weights(y: np.ndarray) -> np.ndarray:
    counts = Counter(y.tolist())
    classes = len(counts)
    return np.asarray([len(y) / (classes * counts[value]) for value in y], dtype=float)


def fit_direct(x: np.ndarray, y: np.ndarray) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(**model_parameters())
    model.fit(x, y, sample_weight=balanced_weights(y))
    return model


def aligned_probabilities(model, x: np.ndarray, classes: np.ndarray) -> np.ndarray:
    raw = model.predict_proba(x)
    result = np.full((len(x), len(classes)), 1e-12, dtype=float)
    positions = {value: index for index, value in enumerate(classes.tolist())}
    for source, value in enumerate(model.classes_.tolist()):
        result[:, positions[value]] = raw[:, source]
    result /= result.sum(axis=1, keepdims=True)
    return result


def fit_ovr(x: np.ndarray, y: np.ndarray, classes: np.ndarray) -> dict:
    models = {}
    for value in classes:
        binary = (y == value).astype(int)
        models[str(value)] = fit_direct(x, binary)
    return models


def ovr_probabilities(models: dict, x: np.ndarray, classes: np.ndarray) -> np.ndarray:
    columns = []
    for value in classes:
        model = models[str(value)]
        if len(model.classes_) == 1:
            positive = np.full(len(x), float(model.classes_[0] == 1))
        else:
            positive_index = int(np.flatnonzero(model.classes_ == 1)[0])
            positive = model.predict_proba(x)[:, positive_index]
        columns.append(np.maximum(positive, 1e-12))
    raw = np.column_stack(columns)
    return raw / raw.sum(axis=1, keepdims=True)


def multiclass_metrics(y: np.ndarray, probabilities: np.ndarray, classes: np.ndarray) -> dict:
    predicted = classes[np.argmax(probabilities, axis=1)]
    return {
        "rows": int(len(y)),
        "accuracy": float(accuracy_score(y, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "log_loss": float(log_loss(y, probabilities, labels=classes)),
        "confusion_matrix": confusion_matrix(y, predicted, labels=classes).tolist(),
        "classes": classes.tolist(),
        "predicted_counts": dict(sorted(Counter(predicted.tolist()).items())),
    }


def logo_multiclass(frame: pd.DataFrame, target: str, features: list[str]) -> dict:
    x = frame[features].to_numpy(dtype=float)
    y = frame[target].astype(str).to_numpy()
    groups = frame["submission_id"].to_numpy()
    classes = np.asarray(sorted(set(y)))
    direct_probs = np.zeros((len(frame), len(classes)), dtype=float)
    ovr_probs = np.zeros_like(direct_probs)
    folds = []
    for train, test in LeaveOneGroupOut().split(x, y, groups):
        if len(set(y[train])) != len(classes):
            raise ValueError("a route class has fewer than two policy groups")
        direct = fit_direct(x[train], y[train])
        direct_probs[test] = aligned_probabilities(direct, x[test], classes)
        # With two classes, OVR is the same binary problem twice and provides
        # no additional architecture.  Reserve the comparison for K >= 3.
        if len(classes) == 2:
            ovr_probs[test] = direct_probs[test]
        else:
            ovr = fit_ovr(x[train], y[train], classes)
            ovr_probs[test] = ovr_probabilities(ovr, x[test], classes)
        folds.append(
            {
                "held_submission_id": int(groups[test][0]),
                "rows": int(len(test)),
                "truth": dict(sorted(Counter(y[test].tolist()).items())),
            }
        )
    return {
        "split": "leave-one-submission-policy-out",
        "folds": folds,
        "direct_multiclass": multiclass_metrics(y, direct_probs, classes),
        "one_vs_rest": multiclass_metrics(y, ovr_probs, classes),
        "classes": classes,
        "direct_probabilities": direct_probs,
        "ovr_probabilities": ovr_probs,
    }


def route_clusters(policy_rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    policy = policy_rows.groupby(
        ["submission_id", "policy_name", "rank"], dropna=False
    )[list(ROUTE_METRICS)].mean().reset_index()
    scaler = RobustScaler().fit(policy[list(ROUTE_METRICS)])
    x = scaler.transform(policy[list(ROUTE_METRICS)])
    candidates = []
    for clusters in range(2, min(5, len(policy))):
        model = KMeans(n_clusters=clusters, random_state=SEED, n_init=50).fit(x)
        counts = Counter(model.labels_.tolist())
        if min(counts.values()) < 2:
            continue
        candidates.append(
            {
                "clusters": clusters,
                "silhouette": float(silhouette_score(x, model.labels_)),
                "model": model,
                "counts": counts,
            }
        )
    if not candidates:
        raise ValueError("no route clustering has at least two policies per class")
    selected = max(candidates, key=lambda row: row["silhouette"])
    model = selected["model"]
    raw_centers = scaler.inverse_transform(model.cluster_centers_)
    metric_index = {name: index for index, name in enumerate(ROUTE_METRICS)}
    livestock_balance = {
        cluster: raw_centers[cluster, metric_index["peak_animals_cow"]]
        - raw_centers[cluster, metric_index["peak_animals_sheep"]]
        for cluster in range(selected["clusters"])
    }
    ordered = sorted(livestock_balance, key=livestock_balance.get)
    if len(ordered) == 2:
        # Name a binary clustering by the feature that actually separates its
        # standardized centroids.  This avoids calling a wheat-flood route a
        # sheep route merely because its cow/sheep balance is slightly lower.
        separating_index = int(np.argmax(np.abs(model.cluster_centers_[0] - model.cluster_centers_[1])))
        separating_metric = ROUTE_METRICS[separating_index]
        ordered = sorted(
            range(2), key=lambda cluster: raw_centers[cluster, separating_index]
        )
        names = (f"low_{separating_metric}", f"high_{separating_metric}")
    elif len(ordered) == 3:
        names = ("sheep_heavy", "balanced", "cow_heavy")
    else:
        names = tuple(f"route_{index}" for index in range(len(ordered)))
    label_names = {cluster: names[index] for index, cluster in enumerate(ordered)}
    policy["route_cluster"] = [label_names[int(value)] for value in model.labels_]
    centers = []
    for cluster in range(selected["clusters"]):
        centers.append(
            {
                "raw_cluster": cluster,
                "label": label_names[cluster],
                "policies": int(selected["counts"][cluster]),
                "metrics": {
                    name: float(raw_centers[cluster, index])
                    for index, name in enumerate(ROUTE_METRICS)
                },
            }
        )
    report = {
        "selection": [
            {
                "clusters": row["clusters"],
                "silhouette": row["silhouette"],
                "counts": dict(sorted(row["counts"].items())),
            }
            for row in candidates
        ],
        "selected_clusters": selected["clusters"],
        "centers": centers,
        "policy_assignments": policy[
            ["submission_id", "policy_name", "rank", "route_cluster"]
        ].to_dict("records"),
        "scaler": scaler,
        "kmeans": model,
    }
    return policy, report


def safe_binary_fit(x: np.ndarray, y: np.ndarray):
    values = np.unique(y)
    if len(values) == 1:
        return {"constant": float(values[0])}
    return fit_direct(x, y)


def binary_probabilities(model, x: np.ndarray) -> np.ndarray:
    if isinstance(model, dict):
        return np.full(len(x), model["constant"], dtype=float)
    positive = int(np.flatnonzero(model.classes_ == 1)[0])
    return model.predict_proba(x)[:, positive]


def threshold_for_precision(y: np.ndarray, probabilities: np.ndarray) -> float:
    best = (0.0, 0.5)
    for threshold in np.linspace(0.3, 0.9, 61):
        predicted = probabilities >= threshold
        precision = precision_score(y, predicted, zero_division=0)
        recall = recall_score(y, predicted, zero_division=0)
        f_half = (1.25 * precision * recall / (0.25 * precision + recall)) if precision + recall else 0.0
        candidate = (f_half, float(threshold))
        if candidate > best:
            best = candidate
    return best[1]


def binary_metrics(y: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict:
    predicted = probabilities >= threshold
    result = {
        "rows": int(len(y)),
        "positives": int(y.sum()),
        "prevalence": float(y.mean()),
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "average_precision": float(average_precision_score(y, probabilities)),
    }
    result["roc_auc"] = float(roc_auc_score(y, probabilities)) if len(set(y)) == 2 else None
    return result


def logo_binary(frame: pd.DataFrame, target: str, features: list[str]) -> tuple[dict, np.ndarray]:
    x = frame[features].to_numpy(dtype=float)
    y = frame[target].astype(int).to_numpy()
    groups = frame["submission_id"].to_numpy()
    probabilities = np.zeros(len(frame), dtype=float)
    for train, test in LeaveOneGroupOut().split(x, y, groups):
        model = safe_binary_fit(x[train], y[train])
        probabilities[test] = binary_probabilities(model, x[test])
    threshold = threshold_for_precision(y, probabilities)
    return binary_metrics(y, probabilities, threshold), probabilities


def logo_day_rate_baseline(frame: pd.DataFrame, target: str) -> dict:
    """Policy-held baseline using only the current in-game day."""
    y = frame[target].astype(int).to_numpy()
    groups = frame["submission_id"].to_numpy()
    days = frame["checkpoint_day"].astype(int).to_numpy()
    probabilities = np.zeros(len(frame), dtype=float)
    dummy_x = days.reshape(-1, 1)
    for train, test in LeaveOneGroupOut().split(dummy_x, y, groups):
        global_rate = (float(y[train].sum()) + 1.0) / (len(train) + 2.0)
        rates = {}
        for day in np.unique(days[train]):
            mask = train[days[train] == day]
            rates[int(day)] = (float(y[mask].sum()) + 1.0) / (len(mask) + 2.0)
        probabilities[test] = [rates.get(int(day), global_rate) for day in days[test]]
    threshold = threshold_for_precision(y, probabilities)
    return binary_metrics(y, probabilities, threshold)


def json_clean(value):
    if isinstance(value, dict):
        return {str(key): json_clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    policy_rows = pd.read_csv(args.dataset_dir / "policy_rows.csv.gz")
    checkpoints = pd.read_csv(args.dataset_dir / "checkpoint_rows.csv.gz")
    gates = pd.read_csv(args.dataset_dir / "gate_rows.csv.gz")
    policy, clustering = route_clusters(policy_rows)
    assignments = dict(zip(policy["submission_id"], policy["route_cluster"]))
    checkpoints["route_cluster"] = checkpoints["submission_id"].map(assignments)
    if checkpoints["route_cluster"].isna().any():
        raise ValueError("checkpoint row lacks route assignment")
    feature_names = sorted(column for column in checkpoints if column.startswith("x_"))
    route_reports = {}
    route_cv_payload = {}
    for day in sorted(checkpoints["checkpoint_day"].unique()):
        frame = checkpoints[checkpoints["checkpoint_day"] == day].reset_index(drop=True)
        result = logo_multiclass(frame, "route_cluster", feature_names)
        route_reports[str(int(day))] = {
            key: value
            for key, value in result.items()
            if key not in {"classes", "direct_probabilities", "ovr_probabilities"}
        }
        route_cv_payload[int(day)] = (frame, result)
    def route_choice(day: int) -> tuple:
        metrics = route_reports[str(day)]["direct_multiclass"]
        return (metrics["balanced_accuracy"], -metrics["log_loss"], day)
    best_day = max(route_cv_payload, key=route_choice)
    best_frame, best_result = route_cv_payload[best_day]
    direct = best_result["direct_multiclass"]
    ovr = best_result["one_vs_rest"]
    if len(best_result["classes"]) == 2:
        architecture = "binary_gbdt"
    else:
        architecture = "direct_multiclass" if (
            direct["balanced_accuracy"], -direct["log_loss"]
        ) >= (ovr["balanced_accuracy"], -ovr["log_loss"]) else "one_vs_rest"
    x_best = best_frame[feature_names].to_numpy(dtype=float)
    y_best = best_frame["route_cluster"].astype(str).to_numpy()
    classes = np.asarray(sorted(set(y_best)))
    final_route_model = (
        fit_ovr(x_best, y_best, classes)
        if architecture == "one_vs_rest"
        else fit_direct(x_best, y_best)
    )

    gate_feature_names = sorted(column for column in gates if column.startswith("x_"))
    gate_reports = {}
    gate_models = {}
    for target in GATES:
        metrics, _ = logo_binary(gates, target, gate_feature_names)
        day_only = logo_day_rate_baseline(gates, target)
        gate_reports[target] = {
            "gbdt": metrics,
            "day_only_baseline": day_only,
            "delta_average_precision": metrics["average_precision"]
            - day_only["average_precision"],
            "delta_balanced_accuracy": metrics["balanced_accuracy"]
            - day_only["balanced_accuracy"],
        }
        gate_models[target] = safe_binary_fit(
            gates[gate_feature_names].to_numpy(dtype=float),
            gates[target].astype(int).to_numpy(),
        )

    animal_rows = gates[gates["y_buy_animal"] == 1].copy().reset_index(drop=True)
    animal_report = None
    animal_model = None
    animal_architecture = None
    animal_excluded_classes = []
    animal_class_policy_counts = animal_rows.groupby("y_animal_type")[
        "submission_id"
    ].nunique()
    animal_excluded_classes = sorted(
        str(name) for name, count in animal_class_policy_counts.items() if int(count) < 2
    )
    if animal_excluded_classes:
        animal_rows = animal_rows[
            ~animal_rows["y_animal_type"].isin(animal_excluded_classes)
        ].reset_index(drop=True)
    if animal_rows["y_animal_type"].nunique() >= 2:
        animal_result = logo_multiclass(animal_rows, "y_animal_type", gate_feature_names)
        animal_report = {
            key: value
            for key, value in animal_result.items()
            if key not in {"classes", "direct_probabilities", "ovr_probabilities"}
        }
        animal_direct = animal_result["direct_multiclass"]
        animal_ovr = animal_result["one_vs_rest"]
        animal_architecture = "direct_multiclass" if (
            animal_direct["balanced_accuracy"], -animal_direct["log_loss"]
        ) >= (animal_ovr["balanced_accuracy"], -animal_ovr["log_loss"]) else "one_vs_rest"
        animal_x = animal_rows[gate_feature_names].to_numpy(dtype=float)
        animal_y = animal_rows["y_animal_type"].astype(str).to_numpy()
        animal_classes = np.asarray(sorted(set(animal_y)))
        animal_model = (
            fit_direct(animal_x, animal_y)
            if animal_architecture == "direct_multiclass"
            else fit_ovr(animal_x, animal_y, animal_classes)
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "schema": "kaggriculture-public-replay-gbdt-v1",
        "best_checkpoint_day": int(best_day),
        "route_architecture": architecture,
        "route_features": feature_names,
        "route_classes": classes.tolist(),
        "route_model": final_route_model,
        "route_scaler": clustering["scaler"],
        "route_kmeans": clustering["kmeans"],
        "route_metrics": list(ROUTE_METRICS),
        "gate_features": gate_feature_names,
        "gate_models": gate_models,
        "gate_thresholds": {
            target: gate_reports[target]["gbdt"]["threshold"] for target in GATES
        },
        "animal_type_model": animal_model,
        "animal_type_architecture": animal_architecture,
    }
    model_path = args.output_dir / "public_replay_gbdt.joblib"
    joblib.dump(bundle, model_path, compress=3)
    clustering_report = {key: value for key, value in clustering.items() if key not in {"scaler", "kmeans"}}
    report = {
        "schema": "kaggriculture-public-replay-gbdt-report-v1",
        "dataset_dir": str(args.dataset_dir),
        "model_parameters": model_parameters(),
        "policy_split": "leave-one-complete-submission-policy-out",
        "route_clustering": clustering_report,
        "route_models_by_checkpoint_day": route_reports,
        "selected_route_model": {
            "checkpoint_day": int(best_day),
            "architecture": architecture,
            "direct_multiclass": direct,
            "one_vs_rest": ovr,
        },
        "binary_gate_models": gate_reports,
        "conditional_animal_type": animal_report,
        "conditional_animal_type_selected_architecture": animal_architecture,
        "conditional_animal_type_excluded_classes": animal_excluded_classes,
        "artifacts": {
            "model": str(model_path),
            "model_bytes": model_path.stat().st_size,
        },
        "limitations": [
            "Imitation labels describe top-bot behavior, not counterfactual best response.",
            "Only public state is used, but route clusters are defined from complete-season futures.",
            "No learned action is eligible for deployment before adaptive local league evaluation.",
        ],
    }
    report_path = args.output_dir / "training_report.json"
    report_path.write_text(json.dumps(json_clean(report), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(json_clean(report), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
