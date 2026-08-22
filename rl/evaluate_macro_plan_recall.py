"""Evaluate whether legal hidden-state particles preserve oracle macro plans.

Both seats execute fixed reactive C++ task graphs after the checkpoint.  The
controlled planner never reads the opponent's private state; the opponent reads
only its own particle-private state.  Downloaded actions reconstruct the root
but are never replayed inside a future branch.

The forbidden full state supplies the oracle ranking.  Checkpoint-marginal,
snapshot-kNN10 and observation-history-kNN10 particles are selected from a
disjoint training block.  Every method is evaluated under the same synthetic
future RNG seeds, so the source replay seed is not an inference feature or a
future-randomness oracle.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import subprocess
import time

import numpy as np

try:
    from rl.audit_hidden_state import replay_paths
    from rl.evaluate_hidden_history_prior import history_examples_from_replay
    from rl.evaluate_hidden_state_prior import (
        feature_matrix,
        standardized_distances,
    )
except ModuleNotFoundError:
    from audit_hidden_state import replay_paths  # type: ignore
    from evaluate_hidden_history_prior import history_examples_from_replay  # type: ignore
    from evaluate_hidden_state_prior import (  # type: ignore
        feature_matrix,
        standardized_distances,
    )


OPS = (
    "PASS", "NORTH", "SOUTH", "EAST", "WEST", "PICKUP", "DROP", "PLACE",
    "PLANT", "WATER", "HARVEST", "FERTILIZE", "DIG", "BUILD_COOP",
    "BUILD_PASTURE", "FEED", "COLLECT_FERTILIZER", "CARE",
)
ITEMS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK",
    "WOOL", "FERTILIZER", "GOOSE", "COW", "SHEEP",
)
MOPS = ("NONE", "HIRE", "BUY_LAND", "BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL")
OP_INDEX = {name: index for index, name in enumerate(OPS)}
ITEM_INDEX = {name: index for index, name in enumerate(ITEMS)}
MOP_INDEX = {name: index for index, name in enumerate(MOPS)}


def encode_unit(action) -> tuple[int, int, int]:
    if not isinstance(action, list) or not action:
        return 0, 0, 1
    operation = OP_INDEX.get(str(action[0]).upper(), len(OPS))
    argument = (
        ITEM_INDEX.get(str(action[1]).upper(), 255)
        if len(action) >= 2 and isinstance(action[1], str)
        else 0
    )
    try:
        amount = int(action[2]) if len(action) >= 3 else 1
    except (TypeError, ValueError):
        amount = 1
    return operation, argument, amount


def encode_order(order) -> tuple[int, int, int]:
    if not isinstance(order, list) or not order:
        return 0, 0, 0
    operation = MOP_INDEX.get(str(order[0]).upper(), 0)
    if operation in (MOP_INDEX["HIRE"], MOP_INDEX["BUY_LAND"]):
        return operation, 0, 1
    if len(order) < 3:
        return 0, 0, 0
    try:
        return operation, ITEM_INDEX.get(str(order[1]).upper(), 255), int(order[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def export_replay_trace(replay: dict, destination: Path) -> None:
    """Export downloaded replay actions in the validated fast-sim format."""

    steps = list(replay.get("steps", []) or [])
    if len(steps) < 2:
        raise ValueError("replay has no transitions")
    configuration = dict(replay.get("configuration", {}) or {})
    seed = int((replay.get("info", {}) or {}).get("seed", 0) or 0)
    values = (
        int(configuration.get("episodeSteps", 720)),
        int(configuration.get("boardSize", 10)),
        int(configuration.get("startingMoney", 3000)),
        int(configuration.get("maxMarketOrdersPerTurn", 10)),
        int(configuration.get("turnsPerDay", 24)),
        int(configuration.get("shedCapacity", 100)),
        float(configuration.get("weedSpawnChance", 0.005)),
        int(configuration.get("townShopUnlockInterval", 3)),
        int(configuration.get("townShopSellInterval", 4)),
        int(configuration.get("townCenterSellInterval", 24)),
        int(configuration.get("farmHandCostMult", 1)),
    )
    lines = [f"{seed} {len(steps) - 1}", "CONFIG " + " ".join(map(str, values))]
    for transition in range(len(steps) - 1):
        # Kaggle records the action driving t -> t+1 on the resulting state.
        for seat in (0, 1):
            action = steps[transition + 1][seat].get("action") or {}
            units = [action.get("farmer") or ["PASS"]]
            units.extend(action.get("hands") or [])
            orders = list(action.get("market") or [])
            fields = [str(len(units)), str(len(orders))]
            for unit in units:
                fields.extend(str(value) for value in encode_unit(unit))
            for order in orders:
                fields.extend(str(value) for value in encode_order(order))
            lines.append(" ".join(fields))
    lines.append("TRUTH")
    for state in steps:
        observation = state[0].get("observation", {}) or {}
        farms = observation.get("farms", []) or []
        inventory = (observation.get("market", {}) or {}).get("inventory", {}) or {}
        truth = [
            str(float(farms[0].get("money", 0) or 0)),
            str(float(farms[1].get("money", 0) or 0)),
        ]
        truth.extend(str(int(inventory.get(item, 0) or 0)) for item in ITEMS[:9])
        lines.append(" ".join(truth))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def example_particles(
    train: list[dict],
    test: dict,
    count: int,
    feature_key: str,
) -> list[np.ndarray]:
    if any(row["episode_id"] == test["episode_id"] for row in train):
        raise ValueError("same EpisodeId entered particle training pool")
    names = tuple(
        sorted(
            {
                name
                for example in [*train, test]
                for name in example[feature_key]
            }
        )
    )
    training = feature_matrix(train, names, feature_key)
    query = feature_matrix([test], names, feature_key)[0]
    order = np.argsort(standardized_distances(training, query), kind="stable")
    return [np.asarray(train[index]["target"], dtype=int) for index in order[:count]]


def marginal_particles(
    train: list[dict],
    count: int,
    checkpoint: int,
    seat: int,
    case_index: int,
) -> list[np.ndarray]:
    rng = np.random.default_rng(
        20260822 + checkpoint * 1009 + seat * 37 + case_index * 7919
    )
    indices = rng.choice(len(train), size=min(count, len(train)), replace=False)
    return [np.asarray(train[index]["target"], dtype=int) for index in indices]


def write_particle_file(destination: Path, methods: dict[str, list[np.ndarray]]) -> None:
    width = len(ITEMS) + 5
    zero = " ".join("0" for _ in range(width))
    lines = [f"oracle {zero}", f"blank_0 {zero}"]
    for method in ("marginal", "snapshot", "history"):
        for index, vector in enumerate(methods[method]):
            if len(vector) != width:
                raise ValueError(f"particle width {len(vector)} != {width}")
            values = " ".join(str(max(0, int(round(value)))) for value in vector)
            lines.append(f"{method}_{index} {values}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_engine_output(output: str) -> list[dict]:
    rows = []
    for row in csv.DictReader(output.splitlines(), delimiter="\t"):
        if not row:
            continue
        rows.append(
            {
                "scenario": row["scenario"],
                "future_seed": int(row["future_seed"]),
                "horizon": int(row["horizon"]),
                "plan": row["plan"],
                "score": float(row["score"]),
                "money_delta": float(row["money_delta"]),
            }
        )
    if not rows:
        raise ValueError("macro-plan engine produced no rows")
    return rows


def robust_plan_scores(rows: list[dict], method: str, horizon: int) -> dict[str, float]:
    values: defaultdict[str, list[float]] = defaultdict(list)
    for row in rows:
        scenario = str(row["scenario"])
        belongs = scenario == "oracle" if method == "oracle" else scenario.startswith(method + "_")
        if belongs and int(row["horizon"]) == horizon:
            values[str(row["plan"])].append(float(row["score"]))
    if not values:
        raise ValueError(f"no {method} rows for horizon {horizon}")
    return {name: float(np.quantile(scores, 0.25)) for name, scores in values.items()}


def rank_scores(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda name: (-scores[name], name))


def score_case(rows: list[dict], horizon: int) -> dict:
    oracle_scores = robust_plan_scores(rows, "oracle", horizon)
    oracle_ranking = rank_scores(oracle_scores)
    oracle_best = oracle_ranking[0]
    methods = {}
    for method in ("blank", "marginal", "snapshot", "history"):
        scores = robust_plan_scores(rows, method, horizon)
        ranking = rank_scores(scores)
        predicted = ranking[0]
        methods[method] = {
            "top1": predicted,
            "top3": ranking[:3],
            "oracle_best_in_top3": oracle_best in ranking[:3],
            "top1_agreement": predicted == oracle_best,
            "oracle_regret": oracle_scores[oracle_best] - oracle_scores[predicted],
            "robust_top1_score": scores[predicted],
        }
    return {
        "horizon": horizon,
        "oracle_best": oracle_best,
        "oracle_top3": oracle_ranking[:3],
        "oracle_margin_top1_top2": (
            oracle_scores[oracle_ranking[0]] - oracle_scores[oracle_ranking[1]]
        ),
        "methods": methods,
    }


def summarize(cases: list[dict], checkpoints: tuple[int, ...], horizons: tuple[int, ...]) -> dict:
    output = {}
    for checkpoint in checkpoints:
        checkpoint_result = {}
        for horizon in horizons:
            selected = [
                row
                for case in cases
                if case["checkpoint"] == checkpoint
                for row in case["horizons"]
                if row["horizon"] == horizon
            ]
            if not selected:
                continue
            methods = {}
            for method in ("blank", "marginal", "snapshot", "history"):
                rows = [case["methods"][method] for case in selected]
                recalls = [float(row["oracle_best_in_top3"]) for row in rows]
                agreements = [float(row["top1_agreement"]) for row in rows]
                regrets = [float(row["oracle_regret"]) for row in rows]
                methods[method] = {
                    "top3_recall": float(np.mean(recalls)),
                    "top1_agreement": float(np.mean(agreements)),
                    "mean_oracle_regret": float(np.mean(regrets)),
                    "median_oracle_regret": float(np.median(regrets)),
                    "zero_regret_rate": float(np.mean(np.asarray(regrets) <= 1e-9)),
                    "selected_plan_counts": dict(sorted(Counter(row["top1"] for row in rows).items())),
                }
            checkpoint_result[str(horizon)] = {
                "case_count": len(selected),
                "oracle_best_counts": dict(sorted(Counter(row["oracle_best"] for row in selected).items())),
                "mean_oracle_margin_top1_top2": float(
                    np.mean([row["oracle_margin_top1_top2"] for row in selected])
                ),
                "methods": methods,
            }
        output[str(checkpoint)] = checkpoint_result
    return output


def history_gate(summary: dict, checkpoints: tuple[int, ...]) -> dict:
    checks = []
    details = {}
    for checkpoint in checkpoints:
        if "24" not in summary.get(str(checkpoint), {}):
            details[str(checkpoint)] = {"missing_horizon_24": True}
            checks.append(False)
            continue
        metrics = summary[str(checkpoint)]["24"]["methods"]
        history = metrics["history"]
        competitors = [metrics["blank"], metrics["marginal"], metrics["snapshot"]]
        recall_pass = history["top3_recall"] > max(row["top3_recall"] for row in competitors)
        regret_pass = history["mean_oracle_regret"] < min(
            row["mean_oracle_regret"] for row in competitors
        )
        details[str(checkpoint)] = {
            "history_top3_strictly_best": recall_pass,
            "history_regret_strictly_best": regret_pass,
        }
        checks.extend((recall_pass, regret_pass))
    return {"pass": bool(checks) and all(checks), "checks": details}


def load_examples(
    paths: list[Path], checkpoints: tuple[int, ...]
) -> tuple[list[dict], dict[int, Path]]:
    examples = []
    sources = {}
    for path in paths:
        replay = json.loads(path.read_text(encoding="utf-8"))
        episode_id = int((replay.get("info", {}) or {}).get("EpisodeId", 0) or 0)
        if not episode_id:
            raise ValueError(f"missing EpisodeId: {path}")
        examples.extend(history_examples_from_replay(replay, checkpoints))
        sources[episode_id] = path
    return examples, sources


def evaluate(args: argparse.Namespace) -> dict:
    checkpoints = tuple(args.checkpoint or (360, 648))
    horizons = tuple(sorted({int(value) for value in args.horizons.split(",")}))
    train_paths = replay_paths(args.replays)
    holdout_paths = replay_paths(args.holdout)
    train_examples, _train_sources = load_examples(train_paths, checkpoints)
    holdout_examples, holdout_sources = load_examples(holdout_paths, checkpoints)
    train_ids = {int(row["episode_id"]) for row in train_examples}
    overlap_ids = sorted(
        {int(row["episode_id"]) for row in holdout_examples if int(row["episode_id"]) in train_ids}
    )
    holdout_examples = [row for row in holdout_examples if int(row["episode_id"]) not in train_ids]
    if not holdout_examples:
        raise ValueError("no disjoint holdout examples")

    train_by_checkpoint: defaultdict[int, list[dict]] = defaultdict(list)
    for example in train_examples:
        train_by_checkpoint[int(example["checkpoint"])].append(example)

    args.work_dir.mkdir(parents=True, exist_ok=True)
    trace_paths = {}
    for episode_id in sorted({int(row["episode_id"]) for row in holdout_examples}):
        replay = json.loads(holdout_sources[episode_id].read_text(encoding="utf-8"))
        trace = args.work_dir / f"episode-{episode_id}.trace"
        export_replay_trace(replay, trace)
        trace_paths[episode_id] = trace

    cases = []
    timings = []
    macro_plans = set()
    ordered_examples = sorted(
        holdout_examples,
        key=lambda row: (int(row["episode_id"]), int(row["checkpoint"]), int(row["target_seat"])),
    )
    for case_index, example in enumerate(ordered_examples):
        checkpoint = int(example["checkpoint"])
        seat = int(example["target_seat"])
        episode_id = int(example["episode_id"])
        train = train_by_checkpoint[checkpoint]
        methods = {
            "marginal": marginal_particles(train, args.neighbors, checkpoint, seat, case_index),
            "snapshot": example_particles(train, example, args.neighbors, "features"),
            "history": example_particles(train, example, args.neighbors, "history_features"),
        }
        particle_path = args.work_dir / f"episode-{episode_id}-c{checkpoint}-s{seat}.particles"
        write_particle_file(particle_path, methods)
        command = [
            str(args.engine.resolve()),
            str(trace_paths[episode_id].resolve()),
            str(particle_path.resolve()),
            str(checkpoint),
            str(seat),
            args.future_seeds,
            ",".join(map(str, horizons)),
        ]
        if args.plan_indices:
            command.append(args.plan_indices)
        started = time.perf_counter()
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        elapsed = time.perf_counter() - started
        timings.append(elapsed)
        engine_rows = parse_engine_output(completed.stdout)
        macro_plans.update(row["plan"] for row in engine_rows)
        cases.append(
            {
                "episode_id": episode_id,
                "checkpoint": checkpoint,
                "seat": seat,
                "engine_seconds": elapsed,
                "horizons": [score_case(engine_rows, horizon) for horizon in horizons],
            }
        )

    summary = summarize(cases, checkpoints, horizons)
    gate = history_gate(summary, checkpoints)
    return {
        "schema": "kaggriculture-particle-macro-plan-recall-v3",
        "train_replay_count": len(train_paths),
        "train_episode_count": len(train_ids),
        "holdout_replay_count": len(holdout_paths),
        "disjoint_holdout_episode_count": len({row["episode_id"] for row in holdout_examples}),
        "excluded_overlap_episode_ids": overlap_ids,
        "checkpoints": list(checkpoints),
        "horizons": list(horizons),
        "particle_count_per_method": args.neighbors,
        "blank_private_particle_count": 1,
        "synthetic_future_seeds": [int(value) for value in args.future_seeds.split(",")],
        "ranking_objective": "lower quartile across future RNG, opponent response and (for priors) hidden particles",
        "macro_plan_count": len(macro_plans),
        "macro_plans": sorted(macro_plans),
        "candidate_plan_indices": args.plan_indices or "all",
        "opponent_response_plans": ["maintain", "liquidate"],
        "summary": summary,
        "pre_registered_history_gate": gate,
        "latency": {
            "case_count": len(timings),
            "mean_engine_process_seconds": float(np.mean(timings)),
            "p95_engine_process_seconds": float(np.quantile(timings, 0.95)),
            "max_engine_process_seconds": float(max(timings)),
            "under_600ms_all_cases": max(timings) < 0.6,
            "warning": "includes process startup; excludes Python particle feature construction",
        },
        "leakage_contract": {
            "candidate": "reactive task graph; controlled farm and shared state only",
            "opponent": "reactive maintain/liquidate task graphs; own particle-private and shared state only",
            "future_action_tape": "none; replay actions stop at the checkpoint root",
            "particle_features": "target-seat current observation or legal observation history",
            "grouping": "fixed disjoint top20-to-live EpisodeId transfer",
            "future_rng": "shared synthetic seeds, never the source replay seed",
            "forbidden_full_state": "oracle label only",
        },
        "warning": (
            "This is a plan-recall gate, not a strength claim. Promotion still "
            "requires official-engine paired outcomes against N39 and the broad pool."
        ),
        "cases": cases,
    }


def reevaluate_cached_report(args: argparse.Namespace) -> dict:
    """Rerun only C++ branches using already materialized legal particles."""

    report = json.loads(args.reuse_report.read_text(encoding="utf-8"))
    checkpoints = tuple(int(value) for value in report["checkpoints"])
    horizons = tuple(sorted({int(value) for value in args.horizons.split(",")}))
    cases = []
    timings = []
    macro_plans = set()
    for previous in sorted(
        report["cases"],
        key=lambda row: (int(row["episode_id"]), int(row["checkpoint"]), int(row["seat"])),
    ):
        episode_id = int(previous["episode_id"])
        checkpoint = int(previous["checkpoint"])
        seat = int(previous["seat"])
        trace = args.work_dir / f"episode-{episode_id}.trace"
        particles = args.work_dir / f"episode-{episode_id}-c{checkpoint}-s{seat}.particles"
        if not trace.is_file() or not particles.is_file():
            raise FileNotFoundError(f"missing cached branch input: {trace} / {particles}")
        command = [
            str(args.engine.resolve()),
            str(trace.resolve()),
            str(particles.resolve()),
            str(checkpoint),
            str(seat),
            args.future_seeds,
            ",".join(map(str, horizons)),
        ]
        if args.plan_indices:
            command.append(args.plan_indices)
        started = time.perf_counter()
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        elapsed = time.perf_counter() - started
        timings.append(elapsed)
        rows = parse_engine_output(completed.stdout)
        macro_plans.update(row["plan"] for row in rows)
        cases.append(
            {
                "episode_id": episode_id,
                "checkpoint": checkpoint,
                "seat": seat,
                "engine_seconds": elapsed,
                "horizons": [score_case(rows, horizon) for horizon in horizons],
            }
        )
    report.update(
        {
            "schema": "kaggriculture-particle-macro-plan-recall-v3",
            "horizons": list(horizons),
            "synthetic_future_seeds": [
                int(value) for value in args.future_seeds.split(",")
            ],
            "ranking_objective": (
                "lower quartile across future RNG, opponent response and "
                "(for priors) hidden particles"
            ),
            "opponent_response_plans": ["maintain", "liquidate"],
            "macro_plan_count": len(macro_plans),
            "macro_plans": sorted(macro_plans),
            "candidate_plan_indices": args.plan_indices or "all",
            "summary": summarize(cases, checkpoints, horizons),
            "cases": cases,
            "latency": {
                "case_count": len(timings),
                "mean_engine_process_seconds": float(np.mean(timings)),
                "p95_engine_process_seconds": float(np.quantile(timings, 0.95)),
                "max_engine_process_seconds": float(max(timings)),
                "under_600ms_all_cases": max(timings) < 0.6,
                "warning": (
                    "includes process startup; excludes Python particle "
                    "feature construction"
                ),
            },
            "leakage_contract": {
                "candidate": (
                    "reactive task graph; controlled farm and shared state only"
                ),
                "opponent": (
                    "reactive maintain/liquidate task graphs; own particle-private "
                    "and shared state only"
                ),
                "future_action_tape": (
                    "none; replay actions stop at the checkpoint root"
                ),
                "particle_features": (
                    "target-seat current observation or legal observation history"
                ),
                "grouping": "fixed disjoint top20-to-live EpisodeId transfer",
                "future_rng": (
                    "shared synthetic seeds, never the source replay seed"
                ),
                "forbidden_full_state": "oracle label only",
            },
        }
    )
    report["pre_registered_history_gate"] = history_gate(
        report["summary"], checkpoints
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="*", type=Path)
    parser.add_argument("--holdout", nargs="+", type=Path)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, default=Path("artifacts/e102-macro-plan"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint", action="append", type=int)
    parser.add_argument("--horizons", default="6,12,24")
    parser.add_argument("--neighbors", type=int, default=10)
    parser.add_argument("--future-seeds", default="2026082201,2026082229")
    parser.add_argument(
        "--plan-indices",
        help="comma-separated frozen C++ plan indices; default evaluates all",
    )
    parser.add_argument("--reuse-report", type=Path)
    args = parser.parse_args()
    if not args.engine.is_file():
        parser.error(f"engine not found: {args.engine}")
    if args.neighbors <= 0:
        parser.error("neighbors must be positive")
    if args.reuse_report:
        if not args.reuse_report.is_file():
            parser.error(f"reuse report not found: {args.reuse_report}")
        report = reevaluate_cached_report(args)
    else:
        if not args.replays or not args.holdout:
            parser.error("training replays and --holdout are required")
        report = evaluate(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
