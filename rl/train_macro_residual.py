"""Train a small linear residual to rank task or market macro labels.

The model is intentionally weaker than the rules executor: it receives only
features emitted by ``build_macro_imitation_dataset.py`` and ranks high-level
labels.  Evaluation is split by complete episodes/seeds, never random rows, so
the report exposes whether imitation generalizes to a new season rather than
memorizing adjacent turns.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np


def load_rows(path: Path, agent: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in payload["rows"] if row["agent"] == agent]
    if not rows:
        raise ValueError(f"no rows for agent {agent!r} in {path}")
    return rows


def label_value(row: dict, target: str) -> str:
    return str(row["label"][target])


def feature_matrix(rows: list[dict], names: list[str]) -> np.ndarray:
    return np.asarray(
        [[float(row["features"].get(name, 0.0)) for name in names] for row in rows],
        dtype=np.float64,
    )


def softmax(scores: np.ndarray) -> np.ndarray:
    shifted = scores - scores.max(axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def train_softmax(
    x: np.ndarray,
    y: np.ndarray,
    classes: int,
    epochs: int,
    learning_rate: float,
    l2: float,
) -> tuple[np.ndarray, np.ndarray, list[float]]:
    weights = np.zeros((x.shape[1], classes), dtype=np.float64)
    bias = np.zeros(classes, dtype=np.float64)
    counts = np.bincount(y, minlength=classes).astype(np.float64)
    sample_weights = np.sqrt(len(y) / (classes * np.maximum(counts[y], 1.0)))
    sample_weights /= sample_weights.mean()
    target = np.eye(classes, dtype=np.float64)[y]
    history = []
    for epoch in range(epochs):
        probabilities = softmax(x @ weights + bias)
        error = (probabilities - target) * sample_weights[:, None]
        weights -= learning_rate * ((x.T @ error) / len(y) + l2 * weights)
        bias -= learning_rate * error.mean(axis=0)
        if epoch in {0, epochs - 1} or (epoch + 1) % max(1, epochs // 10) == 0:
            chosen = np.maximum(probabilities[np.arange(len(y)), y], 1e-12)
            loss = float(-(sample_weights * np.log(chosen)).mean() + 0.5 * l2 * np.square(weights).sum())
            history.append(loss)
    return weights, bias, history


def contains_macro(label: str, macro: str) -> bool:
    return macro in label.split("+")


def evaluate(scores: np.ndarray, truth: np.ndarray, labels: list[str], target: str) -> dict:
    ranking = np.argsort(-scores, axis=1)
    predicted = ranking[:, 0]
    recalls = []
    per_class = {}
    for index, label in enumerate(labels):
        mask = truth == index
        if not mask.any():
            continue
        recall = float((predicted[mask] == index).mean())
        recalls.append(recall)
        per_class[label] = {"support": int(mask.sum()), "recall": recall}
    top_k = min(3, len(labels))
    top_k_accuracy = float(np.mean([truth[row] in ranking[row, :top_k] for row in range(len(truth))]))
    macros = (
        ("service", "harvest", "logistics", "build", "dig", "plant", "collect")
        if target == "task_macro"
        else ("sell", "hire", "buy_product", "buy_seed", "buy_animal", "buy_land")
    )
    critical = {}
    for macro in macros:
        actual = np.asarray([contains_macro(labels[index], macro) for index in truth])
        guessed = np.asarray([contains_macro(labels[index], macro) for index in predicted])
        positives = int(actual.sum())
        critical[macro] = {
            "support": positives,
            "recall": float((actual & guessed).sum() / positives) if positives else None,
            "precision": float((actual & guessed).sum() / guessed.sum()) if guessed.any() else None,
        }
    return {
        "rows": len(truth),
        "accuracy": float((predicted == truth).mean()),
        "top3_accuracy": top_k_accuracy,
        "balanced_recall": float(sum(recalls) / len(recalls)) if recalls else 0.0,
        "per_class": per_class,
        "critical_macro_detection": critical,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--target", choices=("task_macro", "market_macro"), required=True)
    parser.add_argument("--min-count", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2", type=float, default=0.0001)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    train_rows = load_rows(args.train, args.agent)
    holdout_rows = load_rows(args.holdout, args.agent)
    names = sorted({name for row in train_rows for name in row["features"]})
    raw_train_labels = [label_value(row, args.target) for row in train_rows]
    counts = Counter(raw_train_labels)
    kept = sorted(label for label, count in counts.items() if count >= args.min_count)
    if len(kept) < 2:
        raise ValueError("fewer than two labels survive --min-count")
    other = "__OTHER__"
    labels = kept + ([other] if len(kept) < len(counts) else [])
    label_index = {label: index for index, label in enumerate(labels)}

    def encoded(rows):
        values = []
        for row in rows:
            label = label_value(row, args.target)
            values.append(label_index.get(label, label_index.get(other, 0)))
        return np.asarray(values, dtype=np.int64)

    x_train_raw = feature_matrix(train_rows, names)
    x_holdout_raw = feature_matrix(holdout_rows, names)
    center = x_train_raw.mean(axis=0)
    scale = x_train_raw.std(axis=0)
    scale[scale < 1e-9] = 1.0
    x_train = (x_train_raw - center) / scale
    x_holdout = (x_holdout_raw - center) / scale
    y_train = encoded(train_rows)
    y_holdout = encoded(holdout_rows)
    weights, bias, history = train_softmax(
        x_train,
        y_train,
        len(labels),
        args.epochs,
        args.learning_rate,
        args.l2,
    )
    train_scores = x_train @ weights + bias
    holdout_scores = x_holdout @ weights + bias
    majority = int(np.bincount(y_train, minlength=len(labels)).argmax())
    report = {
        "algorithm": "class-balanced linear softmax macro residual",
        "agent": args.agent,
        "target": args.target,
        "split": "disjoint complete season datasets",
        "feature_count": len(names),
        "labels": labels,
        "label_counts": dict(sorted(counts.items())),
        "optimization": {
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "l2": args.l2,
            "loss_checkpoints": history,
        },
        "majority_holdout_accuracy": float((y_holdout == majority).mean()),
        "train_metrics": evaluate(train_scores, y_train, labels, args.target),
        "holdout_metrics": evaluate(holdout_scores, y_holdout, labels, args.target),
        "model": {
            "feature_names": names,
            "center": center.tolist(),
            "scale": scale.tolist(),
            "weights": weights.tolist(),
            "bias": bias.tolist(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report), encoding="utf-8")
    summary = {
        "agent": args.agent,
        "target": args.target,
        "labels": len(labels),
        "majority_holdout_accuracy": report["majority_holdout_accuracy"],
        "train": report["train_metrics"],
        "holdout": report["holdout_metrics"],
        "report": str(args.output),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
