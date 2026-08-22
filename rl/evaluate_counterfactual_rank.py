"""Test frozen N75 on counterfactual native macro-plan leaves.

The seven-plan shortlist is already frozen.  For every replay root this script
reruns the native branches, builds an N75 confidence-gated Copeland tournament
inside each shared hidden-particle/RNG/opponent-response scenario, and compares
the selected plan with a forbidden full-state rollout to the official terminal
money objective.  Recorded actions stop at the root.
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


METHODS = ("oracle", "blank", "marginal", "snapshot", "history")
BASELINE_FIELDS = {
    "money_q25": "leaf_money_margin",
    "legal_marked_q25": "leaf_legal_margin",
    "hand_value_delta_q25": "score",
}
FROZEN_VALUE_FIELDS = {
    "n74_final_q25": "leaf_n74_final_value",
}


def parse_engine_output(output: str) -> list[dict]:
    rows = []
    for raw in csv.DictReader(output.splitlines(), delimiter="\t"):
        if not raw:
            continue
        rows.append(
            {
                "scenario": str(raw["scenario"]),
                "future_seed": int(raw["future_seed"]),
                "horizon": int(raw["horizon"]),
                "plan": str(raw["plan"]),
                "response": str(raw["response"]),
                "score": float(raw["score"]),
                "money_delta": float(raw["money_delta"]),
                "branch_step": int(raw["branch_step"]),
                "leaf_money_margin": float(raw["leaf_money_margin"]),
                "leaf_legal_margin": float(raw["leaf_legal_margin"]),
                "leaf_rank_score": float(raw["leaf_rank_score"]),
                "rank_phase": str(raw["rank_phase"]),
                "leaf_n74_final_value": float(raw["leaf_n74_final_value"]),
                "value_phase": str(raw["value_phase"]),
            }
        )
    if not rows:
        raise ValueError("native engine produced no rows")
    return rows


def belongs_to_method(scenario: str, method: str) -> bool:
    return scenario == "oracle" if method == "oracle" else scenario.startswith(
        method + "_"
    )


def robust_field_scores(
    rows: list[dict], method: str, horizon: int, field: str
) -> dict[str, float]:
    values: defaultdict[str, list[float]] = defaultdict(list)
    for row in rows:
        if (
            row["horizon"] == horizon
            and belongs_to_method(row["scenario"], method)
        ):
            values[row["plan"]].append(float(row[field]))
    if not values:
        raise ValueError(f"no rows for {method}/{horizon}/{field}")
    return {
        plan: float(np.quantile(scores, 0.25))
        for plan, scores in values.items()
    }


def rank_scores(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda plan: (-scores[plan], plan))


def router_field(router: dict, checkpoint: int) -> str:
    for route in router["decision_routes"]:
        if int(route["start"]) <= checkpoint <= int(route["stop"]):
            return str(route["score_field"])
    raise ValueError(f"checkpoint {checkpoint} outside frozen search router")


def collapsed_intercept(rank: dict) -> float:
    ridge = rank["ridge"]
    intercept = float(ridge["target_center"])
    for index, weight in zip(ridge["active_indices"], ridge["weights"]):
        intercept -= (
            float(ridge["center"][index])
            / float(ridge["scale"][index])
            * float(weight)
        )
    return intercept


def phase_for_checkpoint(model: dict, checkpoint: int) -> tuple[str, dict]:
    for name, phase in model["phases"].items():
        if int(phase["start"]) <= checkpoint <= int(phase["stop"]):
            return name, phase
    raise ValueError(f"checkpoint {checkpoint} outside frozen N75 phases")


def confidence_winner(
    left: dict, right: dict, phase: dict, intercept: float
) -> tuple[int, bool]:
    rank = phase["rank"]
    current = float(left["leaf_money_margin"]) - float(
        right["leaf_money_margin"]
    )
    learned = (
        intercept
        + float(left["leaf_rank_score"])
        - float(right["leaf_rank_score"])
    )
    current_sign = int(current > 0.0) - int(current < 0.0)
    learned_sign = int(learned > 0.0) - int(learned < 0.0)
    eligible = (
        abs(current) <= float(rank["margin_threshold"])
        and abs(learned) >= float(rank["confidence_threshold"])
        and learned_sign != 0
    )
    override = eligible and learned_sign != current_sign
    return (learned_sign if override else current_sign), override


def pairwise_tournament(
    rows: list[dict],
    method: str,
    horizon: int,
    checkpoint: int,
    model: dict,
) -> dict:
    phase_name, phase = phase_for_checkpoint(model, checkpoint)
    intercept = collapsed_intercept(phase["rank"])
    selected = [
        row
        for row in rows
        if row["horizon"] == horizon
        and belongs_to_method(row["scenario"], method)
    ]
    grouped: defaultdict[tuple, dict[str, dict]] = defaultdict(dict)
    for row in selected:
        if row["rank_phase"] != phase_name:
            raise ValueError(
                f"native phase {row['rank_phase']} != frozen root phase {phase_name}"
            )
        key = (row["scenario"], row["future_seed"], row["response"])
        if row["plan"] in grouped[key]:
            raise ValueError(f"duplicate plan in scenario {key}: {row['plan']}")
        grouped[key][row["plan"]] = row
    if not grouped:
        raise ValueError(f"no tournament rows for {method}/{horizon}")
    plans = sorted(next(iter(grouped.values())))
    if any(sorted(values) != plans for values in grouped.values()):
        raise ValueError("incomplete plan set in a tournament scenario")

    scenario_points: defaultdict[str, list[float]] = defaultdict(list)
    override_count = 0
    comparison_count = 0
    for values in grouped.values():
        points = {plan: 0.0 for plan in plans}
        for left_index, left_plan in enumerate(plans):
            for right_plan in plans[left_index + 1 :]:
                winner, override = confidence_winner(
                    values[left_plan], values[right_plan], phase, intercept
                )
                override_count += int(override)
                comparison_count += 1
                if winner > 0:
                    points[left_plan] += 1.0
                elif winner < 0:
                    points[right_plan] += 1.0
                else:
                    points[left_plan] += 0.5
                    points[right_plan] += 0.5
        for plan, value in points.items():
            scenario_points[plan].append(value)

    q25 = {
        plan: float(np.quantile(values, 0.25))
        for plan, values in scenario_points.items()
    }
    mean = {plan: float(np.mean(values)) for plan, values in scenario_points.items()}
    money = robust_field_scores(rows, method, horizon, "leaf_money_margin")
    ranking = sorted(
        plans,
        key=lambda plan: (-q25[plan], -mean[plan], -money[plan], plan),
    )
    return {
        "phase": phase_name,
        "scenario_count": len(grouped),
        "pair_comparisons": comparison_count,
        "override_count": override_count,
        "override_fraction": override_count / comparison_count,
        "selected": ranking[0],
        "ranking": ranking,
        "q25_copeland": q25,
        "mean_copeland": mean,
    }


def terminal_oracle(rows: list[dict]) -> dict:
    values: defaultdict[str, list[float]] = defaultdict(list)
    horizons = set()
    for row in rows:
        if row["scenario"] != "oracle_terminal":
            continue
        values[row["plan"]].append(float(row["leaf_money_margin"]))
        horizons.add(int(row["horizon"]))
    if not values or len(horizons) != 1:
        raise ValueError("missing or inconsistent terminal oracle rows")
    scores = {
        plan: float(np.quantile(samples, 0.25))
        for plan, samples in values.items()
    }
    ranking = rank_scores(scores)
    return {
        "horizon": next(iter(horizons)),
        "objective": "q25 final official money margin over future RNG and reactive opponent response",
        "scores": scores,
        "ranking": ranking,
        "best": ranking[0],
        "top3": ranking[:3],
    }


def selection_result(plan: str, oracle: dict) -> dict:
    scores = oracle["scores"]
    return {
        "selected": plan,
        "top1": plan == oracle["best"],
        "top3": plan in oracle["top3"],
        "regret": float(scores[oracle["best"]] - scores[plan]),
    }


def score_case(
    rows: list[dict], checkpoint: int, horizon: int, model: dict, router: dict
) -> dict:
    oracle = terminal_oracle(rows)
    methods = {}
    for method in METHODS:
        scorers = {}
        for scorer, field in BASELINE_FIELDS.items():
            ranking = rank_scores(
                robust_field_scores(rows, method, horizon, field)
            )
            scorers[scorer] = selection_result(ranking[0], oracle)
        for scorer, field in FROZEN_VALUE_FIELDS.items():
            ranking = rank_scores(
                robust_field_scores(rows, method, horizon, field)
            )
            scorers[scorer] = selection_result(ranking[0], oracle)
        tournament = pairwise_tournament(
            rows, method, horizon, checkpoint, model
        )
        scorers["n75_tournament"] = {
            **selection_result(tournament["selected"], oracle),
            "diagnostics": tournament,
        }
        component = "n75_tournament" if checkpoint == 360 else "n74_final_q25"
        scorers["n75_mid_n74_terminal"] = {
            **scorers[component],
            "component": component,
        }
        if horizon == int(router["horizon"]):
            field = router_field(router, checkpoint)
            ranking = rank_scores(
                robust_field_scores(rows, method, horizon, field)
            )
            scorers["frozen_search_router"] = {
                **selection_result(ranking[0], oracle),
                "score_field": field,
            }
        methods[method] = scorers
    return {"terminal_oracle": oracle, "methods": methods}


def summarize(cases: list[dict], checkpoints: tuple[int, ...]) -> dict:
    output = {}
    for checkpoint in checkpoints:
        selected_cases = [
            case for case in cases if int(case["checkpoint"]) == checkpoint
        ]
        methods = {}
        for method in METHODS:
            scorers = {}
            for scorer in (
                *BASELINE_FIELDS,
                *FROZEN_VALUE_FIELDS,
                "n75_tournament",
                "n75_mid_n74_terminal",
                *(
                    ("frozen_search_router",)
                    if "frozen_search_router" in selected_cases[0]["evaluation"]["methods"][method]
                    else ()
                ),
            ):
                rows = [case["evaluation"]["methods"][method][scorer] for case in selected_cases]
                scorers[scorer] = {
                    "cases": len(rows),
                    "top1_recall": float(np.mean([row["top1"] for row in rows])),
                    "top3_recall": float(np.mean([row["top3"] for row in rows])),
                    "mean_terminal_money_regret": float(
                        np.mean([row["regret"] for row in rows])
                    ),
                    "p95_terminal_money_regret": float(
                        np.quantile([row["regret"] for row in rows], 0.95)
                    ),
                }
                if scorer == "n75_tournament":
                    scorers[scorer]["mean_override_fraction"] = float(
                        np.mean(
                            [row["diagnostics"]["override_fraction"] for row in rows]
                        )
                    )
                if scorer == "n75_mid_n74_terminal":
                    scorers[scorer]["component"] = rows[0]["component"]
                if scorer == "frozen_search_router":
                    scorers[scorer]["score_field"] = rows[0]["score_field"]
            methods[method] = scorers
        winners = Counter(
            case["evaluation"]["terminal_oracle"]["best"]
            for case in selected_cases
        )
        output[str(checkpoint)] = {
            "cases": len(selected_cases),
            "terminal_oracle_winners": dict(sorted(winners.items())),
            "methods": methods,
        }
    return output


def registered_gate(summary: dict, checkpoints: tuple[int, ...]) -> dict:
    checks = {}
    for checkpoint in checkpoints:
        history = summary[str(checkpoint)]["methods"]["history"]
        candidate = history["n75_tournament"]
        baselines = [history[name] for name in BASELINE_FIELDS]
        best_top3 = max(row["top3_recall"] for row in baselines)
        best_regret = min(row["mean_terminal_money_regret"] for row in baselines)
        noninferior = (
            candidate["top3_recall"] + 1e-12 >= best_top3
            and candidate["mean_terminal_money_regret"] <= best_regret + 1e-9
        )
        strict = (
            candidate["top3_recall"] > best_top3 + 1e-12
            or candidate["mean_terminal_money_regret"] < best_regret - 1e-9
        )
        checks[str(checkpoint)] = {
            "candidate_top3": candidate["top3_recall"],
            "strongest_baseline_top3": best_top3,
            "candidate_mean_regret": candidate["mean_terminal_money_regret"],
            "strongest_baseline_mean_regret": best_regret,
            "noninferior": noninferior,
            "strict_improvement": strict,
            "pass": noninferior and strict,
        }
    return {
        "definition": (
            "history-particle N75 must match or beat the strongest q25 money, "
            "legal-marked and hand-value baseline on top3 and mean terminal-money "
            "regret at every registered checkpoint, with a strict gain at each"
        ),
        "checks": checks,
        "pass": all(row["pass"] for row in checks.values()),
    }


def hybrid_registered_gate(summary: dict, checkpoints: tuple[int, ...]) -> dict:
    checks = {}
    for checkpoint in checkpoints:
        history = summary[str(checkpoint)]["methods"]["history"]
        candidate = history["n75_mid_n74_terminal"]
        baselines = [history[name] for name in BASELINE_FIELDS]
        best_top3 = max(row["top3_recall"] for row in baselines)
        best_regret = min(row["mean_terminal_money_regret"] for row in baselines)
        noninferior = (
            candidate["top3_recall"] + 1e-12 >= best_top3
            and candidate["mean_terminal_money_regret"] <= best_regret + 1e-9
        )
        strict = (
            candidate["top3_recall"] > best_top3 + 1e-12
            or candidate["mean_terminal_money_regret"] < best_regret - 1e-9
        )
        checks[str(checkpoint)] = {
            "component": candidate["component"],
            "candidate_top3": candidate["top3_recall"],
            "strongest_baseline_top3": best_top3,
            "candidate_mean_regret": candidate["mean_terminal_money_regret"],
            "strongest_baseline_mean_regret": best_regret,
            "noninferior": noninferior,
            "strict_improvement": strict,
            "pass": noninferior and strict,
        }
    return {
        "definition": (
            "the frozen evidence-directed hybrid uses N75 only at step 360 and "
            "N74 final magnitude at 600/648; it must match or beat the strongest "
            "q25 money, legal-marked and hand-value baseline on top3 and regret "
            "at every checkpoint, with a strict gain at each"
        ),
        "checks": checks,
        "pass": all(row["pass"] for row in checks.values()),
    }


def evaluate(args: argparse.Namespace) -> dict:
    base = json.loads(args.base_report.read_text(encoding="utf-8"))
    model = json.loads(args.model.read_text(encoding="utf-8"))
    router = json.loads(args.router_config.read_text(encoding="utf-8"))
    checkpoints = tuple(sorted({int(row["checkpoint"]) for row in base["cases"]}))
    cases = []
    timings = []
    for previous in sorted(
        base["cases"],
        key=lambda row: (
            int(row["episode_id"]), int(row["checkpoint"]), int(row["seat"])
        ),
    ):
        episode_id = int(previous["episode_id"])
        checkpoint = int(previous["checkpoint"])
        seat = int(previous["seat"])
        trace = args.work_dir / f"episode-{episode_id}.trace"
        particles = args.work_dir / f"episode-{episode_id}-c{checkpoint}-s{seat}.particles"
        if not trace.is_file() or not particles.is_file():
            raise FileNotFoundError(f"missing cached input: {trace} / {particles}")
        command = [
            str(args.engine.resolve()),
            str(trace.resolve()),
            str(particles.resolve()),
            str(checkpoint),
            str(seat),
            args.future_seeds,
            str(args.horizon),
            args.plan_indices,
            "terminal-oracle",
        ]
        started = time.perf_counter()
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        elapsed = time.perf_counter() - started
        timings.append(elapsed)
        rows = parse_engine_output(completed.stdout)
        cases.append(
            {
                "episode_id": episode_id,
                "checkpoint": checkpoint,
                "seat": seat,
                "engine_seconds": elapsed,
                "evaluation": score_case(
                    rows, checkpoint, args.horizon, model, router
                ),
            }
        )
    summary = summarize(cases, checkpoints)
    return {
        "schema": "kaggriculture-counterfactual-pairwise-rank-v1",
        "base_report": str(args.base_report),
        "model": str(args.model),
        "router_config": str(args.router_config),
        "case_count": len(cases),
        "episode_count": len({case["episode_id"] for case in cases}),
        "checkpoints": list(checkpoints),
        "short_horizon": args.horizon,
        "terminal_horizons": {
            str(checkpoint): int(
                next(
                    case["evaluation"]["terminal_oracle"]["horizon"]
                    for case in cases if case["checkpoint"] == checkpoint
                )
            )
            for checkpoint in checkpoints
        },
        "plan_indices": args.plan_indices,
        "future_seeds": [int(value) for value in args.future_seeds.split(",")],
        "summary": summary,
        "pre_registered_gate": registered_gate(summary, checkpoints),
        "pre_registered_hybrid_gate": hybrid_registered_gate(summary, checkpoints),
        "latency": {
            "case_count": len(timings),
            "mean_engine_process_seconds": float(np.mean(timings)),
            "p95_engine_process_seconds": float(np.quantile(timings, 0.95)),
            "max_engine_process_seconds": float(max(timings)),
            "under_600ms_all_cases": max(timings) < 0.6,
            "includes": "process startup, 119-feature N75 leaves, and terminal full-state oracle label",
            "excludes": "Python particle construction and tournament aggregation",
        },
        "leakage_contract": {
            "candidate_leaf": "controlled private plus public farms/market/town",
            "opponent_private": "history particles only; exact value restricted to oracle label rows",
            "future_actions": "reactive plans only; recorded tape stops at root",
            "future_rng": "shared synthetic seeds, never replay source seed",
            "terminal_oracle": "offline full-state label using official final money objective",
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-report", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument(
        "--model", type=Path, default=Path("rl/frozen_pairwise_rank_e105.json")
    )
    parser.add_argument(
        "--router-config",
        type=Path,
        default=Path("fast_sim/frozen_search_router_e108.json"),
    )
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--future-seeds", default="2026082201,2026082229")
    parser.add_argument("--plan-indices", default="0,1,2,4,8,9,14")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for path in (args.base_report, args.engine, args.model, args.router_config):
        if not path.is_file():
            parser.error(f"file not found: {path}")
    report = evaluate(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
