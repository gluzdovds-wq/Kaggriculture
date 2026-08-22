"""Evaluate a factorized task/market macro shortlist on disjoint episodes.

The residual models rank task and market labels independently.  This evaluator
measures whether the exact pair produced by the donor policy appears in a small
Cartesian top-k shortlist.  It also reports the smaller shortlist obtained by
discarding pairs never observed in the training season.  ``__OTHER__`` is not
treated as an executable macro, so rare labels count as misses rather than as
accidental successes through the catch-all class.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Iterable

import numpy as np


DEFAULT_CONFIGURATIONS = ((1, 1), (3, 1), (3, 3), (5, 3), (8, 3), (8, 5))
NOOP_PAIR = ("pass", "none")
OTHER = "__OTHER__"


def load_rows(path: Path, agent: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in payload.get("rows", []) if row.get("agent") == agent]
    if not rows:
        raise ValueError(f"no rows for agent {agent!r} in {path}")
    return rows


def load_model(path: Path, agent: str, target: str) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("agent") != agent:
        raise ValueError(f"{path} is for agent {report.get('agent')!r}, not {agent!r}")
    if report.get("target") != target:
        raise ValueError(f"{path} targets {report.get('target')!r}, not {target!r}")
    return report


def raw_pair(row: dict) -> tuple[str, str]:
    label = row.get("label") or {}
    return str(label.get("task_macro", "pass")), str(label.get("market_macro", "none"))


def rank_macro_labels(rows: list[dict], report: dict) -> list[list[str]]:
    model = report["model"]
    names = list(model["feature_names"])
    center = np.asarray(model["center"], dtype=np.float64)
    scale = np.asarray(model["scale"], dtype=np.float64)
    weights = np.asarray(model["weights"], dtype=np.float64)
    bias = np.asarray(model["bias"], dtype=np.float64)
    labels = list(report["labels"])
    if weights.shape != (len(names), len(labels)):
        raise ValueError(
            f"weight shape {weights.shape} does not match "
            f"{len(names)} features x {len(labels)} labels"
        )
    if center.shape != scale.shape or center.shape != (len(names),):
        raise ValueError("feature normalization shape does not match feature names")
    if bias.shape != (len(labels),):
        raise ValueError("bias shape does not match labels")

    raw = np.asarray(
        [[float(row.get("features", {}).get(name, 0.0)) for name in names] for row in rows],
        dtype=np.float64,
    )
    normalized = (raw - center) / np.where(np.abs(scale) < 1e-12, 1.0, scale)
    ranking = np.argsort(-(normalized @ weights + bias), axis=1, kind="stable")
    return [[labels[index] for index in indices if labels[index] != OTHER] for indices in ranking]


def _distribution(values: list[int]) -> dict:
    if not values:
        return {"mean": 0.0, "p95": 0, "max": 0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(np.ceil(0.95 * len(ordered))) - 1)
    return {"mean": mean(values), "p95": ordered[p95_index], "max": ordered[-1]}


def evaluate_scope(
    rows: list[dict],
    task_rankings: list[list[str]],
    market_rankings: list[list[str]],
    seen_pairs: set[tuple[str, str]],
    configurations: Iterable[tuple[int, int]] = DEFAULT_CONFIGURATIONS,
) -> dict:
    if not (len(rows) == len(task_rankings) == len(market_rankings)):
        raise ValueError("rows and rankings must have identical lengths")
    truths = [raw_pair(row) for row in rows]
    task_vocabulary = {label for ranking in task_rankings for label in ranking}
    market_vocabulary = {label for ranking in market_rankings for label in ranking}
    representable = [task in task_vocabulary and market in market_vocabulary for task, market in truths]

    results = {}
    for task_k, market_k in configurations:
        task_hits = 0
        market_hits = 0
        joint_hits = 0
        seen_joint_hits = 0
        cartesian_sizes = []
        seen_sizes = []
        for truth, task_ranking, market_ranking in zip(truths, task_rankings, market_rankings):
            task_choices = task_ranking[:task_k]
            market_choices = market_ranking[:market_k]
            task_hits += truth[0] in task_choices
            market_hits += truth[1] in market_choices
            candidates = {(task, market) for task in task_choices for market in market_choices}
            filtered = candidates & seen_pairs
            joint_hits += truth in candidates
            seen_joint_hits += truth in filtered
            cartesian_sizes.append(len(candidates))
            seen_sizes.append(len(filtered))
        denominator = len(rows) or 1
        results[f"task{task_k}_market{market_k}"] = {
            "task_recall": task_hits / denominator,
            "market_recall": market_hits / denominator,
            "joint_recall": joint_hits / denominator,
            "seen_pair_filtered_recall": seen_joint_hits / denominator,
            "cartesian_candidate_count": _distribution(cartesian_sizes),
            "seen_pair_candidate_count": _distribution(seen_sizes),
        }

    return {
        "rows": len(rows),
        "representable_task_rate": (
            sum(task in task_vocabulary for task, _ in truths) / len(rows) if rows else 0.0
        ),
        "representable_market_rate": (
            sum(market in market_vocabulary for _, market in truths) / len(rows) if rows else 0.0
        ),
        "representable_joint_rate": sum(representable) / len(rows) if rows else 0.0,
        "pair_seen_in_train_rate": sum(pair in seen_pairs for pair in truths) / len(rows) if rows else 0.0,
        "configurations": results,
    }


def evaluate(
    train_rows: list[dict],
    holdout_rows: list[dict],
    task_report: dict,
    market_report: dict,
) -> dict:
    task_rankings = rank_macro_labels(holdout_rows, task_report)
    market_rankings = rank_macro_labels(holdout_rows, market_report)
    seen_pairs = {raw_pair(row) for row in train_rows}
    decision_indices = [index for index, row in enumerate(holdout_rows) if raw_pair(row) != NOOP_PAIR]

    def select(values: list) -> list:
        return [values[index] for index in decision_indices]

    return {
        "all_turns": evaluate_scope(
            holdout_rows, task_rankings, market_rankings, seen_pairs
        ),
        "decision_turns": evaluate_scope(
            select(holdout_rows),
            select(task_rankings),
            select(market_rankings),
            seen_pairs,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--task-model", type=Path, required=True)
    parser.add_argument("--market-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    train_rows = load_rows(args.train, args.agent)
    holdout_rows = load_rows(args.holdout, args.agent)
    task_report = load_model(args.task_model, args.agent, "task_macro")
    market_report = load_model(args.market_model, args.agent, "market_macro")
    report = {
        "schema": "factorized-macro-shortlist-v1",
        "agent": args.agent,
        "split": "disjoint complete season datasets",
        "train_dataset": str(args.train),
        "holdout_dataset": str(args.holdout),
        "task_model": str(args.task_model),
        "market_model": str(args.market_model),
        **evaluate(train_rows, holdout_rows, task_report, market_report),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
