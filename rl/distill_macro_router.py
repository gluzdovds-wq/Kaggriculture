"""Distill the frozen native macro search into a tiny legal policy tree.

Training uses full counterfactual terminal-money scores from an already
completed search report.  A leaf chooses the plan with minimum summed oracle
regret, so the tree optimizes the decision objective rather than imitation
accuracy.  Inputs are exactly the 119 controlled-observation features.  Model
selection uses complete-EpisodeId CV; external evaluation forbids training-ID
overlap and never refits.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

try:
    from rl.audit_hidden_state import replay_paths
    from rl.evaluate_leaf_value import legal_value_features
except ModuleNotFoundError:
    from audit_hidden_state import replay_paths  # type: ignore
    from evaluate_leaf_value import legal_value_features  # type: ignore


DEPTHS = (0, 1, 2, 3)
MIN_LEAVES = (4, 8)
FOLDS = 5


def replay_index(specs: list[Path]) -> dict[int, Path]:
    output = {}
    for path in replay_paths(specs):
        # EpisodeId is stable in the downloaded filename and avoids loading
        # every ~30 MB replay merely to build the index.
        pieces = path.stem.split("-")
        episode_id = next(
            (int(value) for value in pieces if value.isdigit()), 0
        )
        if not episode_id:
            payload = json.loads(path.read_text(encoding="utf-8"))
            episode_id = int(
                (payload.get("info", {}) or {}).get("EpisodeId", 0) or 0
            )
        if not episode_id or episode_id in output:
            raise ValueError(f"missing/duplicate EpisodeId: {path}")
        output[episode_id] = path
    return output


def search_router_plan(case: dict) -> str:
    checkpoint = int(case["checkpoint"])
    methods = case["evaluation"]["methods"]["history"]
    if "frozen_search_router" in methods:
        return str(methods["frozen_search_router"]["selected"])
    scorer = "money_q25" if checkpoint >= 648 else "legal_marked_q25"
    return str(methods[scorer]["selected"])


def load_rows(report_path: Path, replay_specs: list[Path]) -> tuple[list[dict], tuple[str, ...]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    paths = replay_index(replay_specs)
    payload_cache = {}
    rows = []
    names = None
    for case in report["cases"]:
        episode_id = int(case["episode_id"])
        checkpoint = int(case["checkpoint"])
        seat = int(case["seat"])
        if episode_id not in paths:
            raise ValueError(f"missing replay {episode_id}")
        replay = payload_cache.get(episode_id)
        if replay is None:
            replay = json.loads(paths[episode_id].read_text(encoding="utf-8"))
            payload_cache[episode_id] = replay
        observation = dict(
            replay["steps"][checkpoint][seat].get("observation", {}) or {}
        )
        features = legal_value_features(observation)
        row_names = tuple(features)
        if names is None:
            names = row_names
        elif names != row_names:
            raise ValueError("feature order changed across observations")
        oracle = case["evaluation"]["terminal_oracle"]
        scores = {
            str(plan): float(value) for plan, value in oracle["scores"].items()
        }
        ranking = list(map(str, oracle["ranking"]))
        rows.append(
            {
                "episode_id": episode_id,
                "checkpoint": checkpoint,
                "seat": seat,
                "features": features,
                "scores": scores,
                "oracle_ranking": ranking,
                "search_router_plan": search_router_plan(case),
            }
        )
    if not rows or names is None:
        raise ValueError("empty distillation dataset")
    return rows, names


def best_plan(rows: list[dict]) -> tuple[str, float]:
    plans = sorted(rows[0]["scores"])
    if any(sorted(row["scores"]) != plans for row in rows):
        raise ValueError("counterfactual plan sets differ")
    regrets = {}
    for plan in plans:
        regrets[plan] = sum(
            max(row["scores"].values()) - row["scores"][plan] for row in rows
        )
    selected = min(plans, key=lambda plan: (regrets[plan], plan))
    return selected, float(regrets[selected])


def split_candidates(rows: list[dict], names: tuple[str, ...]):
    for name in names:
        values = sorted({float(row["features"][name]) for row in rows})
        for left, right in zip(values, values[1:]):
            yield name, (left + right) / 2.0


def fit_tree(
    rows: list[dict], names: tuple[str, ...], depth: int, min_leaf: int
) -> dict:
    plan, regret = best_plan(rows)
    node = {
        "plan": plan,
        "training_rows": len(rows),
        "training_regret": regret,
    }
    if depth <= 0 or len(rows) < 2 * min_leaf:
        return node
    best = None
    for feature, threshold in split_candidates(rows, names):
        left = [
            row for row in rows if float(row["features"][feature]) <= threshold
        ]
        if len(left) < min_leaf or len(rows) - len(left) < min_leaf:
            continue
        right = [
            row for row in rows if float(row["features"][feature]) > threshold
        ]
        _, left_regret = best_plan(left)
        _, right_regret = best_plan(right)
        candidate = (left_regret + right_regret, feature, threshold, left, right)
        if best is None or candidate[:3] < best[:3]:
            best = candidate
    if best is None or best[0] >= regret - 1e-9:
        return node
    split_regret, feature, threshold, left, right = best
    node.update(
        {
            "feature": feature,
            "threshold": threshold,
            "split_training_regret": split_regret,
            "left": fit_tree(left, names, depth - 1, min_leaf),
            "right": fit_tree(right, names, depth - 1, min_leaf),
        }
    )
    return node


def predict(tree: dict, features: dict[str, float]) -> str:
    node = tree
    while "feature" in node:
        node = (
            node["left"]
            if float(features[node["feature"]]) <= float(node["threshold"])
            else node["right"]
        )
    return str(node["plan"])


def metrics(rows: list[dict], plans: list[str]) -> dict:
    if len(rows) != len(plans):
        raise ValueError("prediction width mismatch")
    regrets = []
    top1 = []
    top3 = []
    agreement = []
    selected_counts: defaultdict[str, int] = defaultdict(int)
    for row, plan in zip(rows, plans):
        ranking = row["oracle_ranking"]
        regret = row["scores"][ranking[0]] - row["scores"][plan]
        regrets.append(regret)
        top1.append(plan == ranking[0])
        top3.append(plan in ranking[:3])
        agreement.append(plan == row["search_router_plan"])
        selected_counts[plan] += 1
    return {
        "rows": len(rows),
        "top1_recall": float(np.mean(top1)),
        "top3_recall": float(np.mean(top3)),
        "mean_terminal_money_regret": float(np.mean(regrets)),
        "p95_terminal_money_regret": float(np.quantile(regrets, 0.95)),
        "exact_search_router_agreement": float(np.mean(agreement)),
        "selected_plan_counts": dict(sorted(selected_counts.items())),
    }


def folds(rows: list[dict], count: int = FOLDS) -> list[list[int]]:
    episode_ids = sorted({int(row["episode_id"]) for row in rows})
    assignment = {
        episode_id: index % count for index, episode_id in enumerate(episode_ids)
    }
    return [
        [index for index, row in enumerate(rows) if assignment[int(row["episode_id"])] == fold]
        for fold in range(count)
    ]


def select_tree(rows: list[dict], names: tuple[str, ...]) -> tuple[dict, dict]:
    candidates = []
    for depth in DEPTHS:
        leaves = (MIN_LEAVES[0],) if depth == 0 else MIN_LEAVES
        for min_leaf in leaves:
            predictions = [None] * len(rows)
            for holdout_indices in folds(rows):
                holdout = set(holdout_indices)
                training = [row for index, row in enumerate(rows) if index not in holdout]
                tree = fit_tree(training, names, depth, min_leaf)
                for index in holdout_indices:
                    predictions[index] = predict(tree, rows[index]["features"])
            report = metrics(rows, list(predictions))
            spec = {"depth": depth, "min_leaf": min_leaf}
            candidates.append((spec, report))
    selected, report = min(
        candidates,
        key=lambda row: (
            row[1]["mean_terminal_money_regret"],
            -row[1]["top3_recall"],
            -row[1]["top1_recall"],
            row[0]["depth"],
            row[0]["min_leaf"],
        ),
    )
    return selected, {
        "selected": selected,
        "selected_oof": report,
        "candidates": [
            {"spec": spec, "oof": result} for spec, result in candidates
        ],
    }


def freeze(report_path: Path, replay_specs: list[Path]) -> tuple[dict, dict]:
    rows, names = load_rows(report_path, replay_specs)
    by_checkpoint: defaultdict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_checkpoint[int(row["checkpoint"])].append(row)
    models = {}
    selection = {}
    for checkpoint, selected_rows in sorted(by_checkpoint.items()):
        spec, cv = select_tree(selected_rows, names)
        tree = fit_tree(
            selected_rows, names, int(spec["depth"]), int(spec["min_leaf"])
        )
        models[str(checkpoint)] = {
            "checkpoint": checkpoint,
            "spec": spec,
            "constant_plan": best_plan(selected_rows)[0],
            "tree": tree,
        }
        selection[str(checkpoint)] = cv
    episode_ids = sorted({int(row["episode_id"]) for row in rows})
    model = {
        "schema": "kaggriculture-cost-sensitive-macro-router-v1",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "training_report": str(report_path),
        "training_episode_ids": episode_ids,
        "feature_names": list(names),
        "checkpoint_models": models,
        "selection_contract": {
            "folds": FOLDS,
            "group": "complete EpisodeId",
            "depths": list(DEPTHS),
            "min_leaves": list(MIN_LEAVES),
            "objective": "mean full-feedback terminal-money regret",
        },
        "leakage_contract": {
            "features": "119 controlled-observation legal features",
            "labels": "offline full-state terminal oracle only",
            "forbidden_at_inference": "identity, EpisodeId, source seed, replay actions, opponent private",
        },
    }
    diagnostics = {
        "schema": "kaggriculture-cost-sensitive-macro-router-freeze-v1",
        "model": model,
        "training_rows": len(rows),
        "selection": selection,
        "warning": "Commit this model before external evaluation.",
    }
    return model, diagnostics


def evaluate(model: dict, report_path: Path, replay_specs: list[Path]) -> dict:
    rows, names = load_rows(report_path, replay_specs)
    if tuple(model["feature_names"]) != names:
        raise ValueError("external feature order differs from frozen model")
    overlap = sorted(
        set(model["training_episode_ids"])
        & {int(row["episode_id"]) for row in rows}
    )
    if overlap:
        raise ValueError(f"external EpisodeIds overlap training: {overlap}")
    by_checkpoint: defaultdict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_checkpoint[int(row["checkpoint"])].append(row)
    reports = {}
    for checkpoint, selected_rows in sorted(by_checkpoint.items()):
        phase = model["checkpoint_models"][str(checkpoint)]
        tree_plans = [predict(phase["tree"], row["features"]) for row in selected_rows]
        constant_plans = [phase["constant_plan"]] * len(selected_rows)
        search_plans = [row["search_router_plan"] for row in selected_rows]
        reports[str(checkpoint)] = {
            "tree": metrics(selected_rows, tree_plans),
            "constant": metrics(selected_rows, constant_plans),
            "native_search_router": metrics(selected_rows, search_plans),
        }
    tree_regret = float(
        np.mean([row["tree"]["mean_terminal_money_regret"] for row in reports.values()])
    )
    constant_regret = float(
        np.mean([row["constant"]["mean_terminal_money_regret"] for row in reports.values()])
    )
    return {
        "schema": "kaggriculture-cost-sensitive-macro-router-transfer-v1",
        "model_frozen_utc": model["frozen_utc"],
        "evaluation_report": str(report_path),
        "episode_count": len({int(row["episode_id"]) for row in rows}),
        "row_count": len(rows),
        "overlap_episode_ids": overlap,
        "checkpoints": reports,
        "aggregate": {
            "tree_mean_regret": tree_regret,
            "constant_mean_regret": constant_regret,
            "tree_vs_constant_improvement_fraction": (
                1.0 - tree_regret / constant_regret if constant_regret else 0.0
            ),
        },
        "pre_registered_gate": {
            "definition": "tree mean regret below constant at every checkpoint and in aggregate",
            "checkpoint_pass": {
                checkpoint: row["tree"]["mean_terminal_money_regret"]
                < row["constant"]["mean_terminal_money_regret"]
                for checkpoint, row in reports.items()
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "evaluate"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--replays", nargs="+", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "freeze":
        model, diagnostics = freeze(args.report, args.replays)
        args.output.write_text(
            json.dumps(model, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        diagnostic_path = args.output.with_suffix(".freeze-report.json")
        diagnostic_path.write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
        return
    if not args.model or not args.model.is_file():
        parser.error("evaluate mode requires --model")
    model = json.loads(args.model.read_text(encoding="utf-8"))
    result = evaluate(model, args.report, args.replays)
    result["pre_registered_gate"]["pass"] = all(
        result["pre_registered_gate"]["checkpoint_pass"].values()
    ) and result["aggregate"]["tree_mean_regret"] < result["aggregate"]["constant_mean_regret"]
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
