"""Freeze and transfer a confidence-gated antisymmetric leaf ranker.

Training pairs are formed from the two *legal controlled-seat* observations at
the same episode/checkpoint.  The feature difference and its negation are fit
together, so the learned linear score is antisymmetric.  At inference the same
scalar score can compare two simulated leaves belonging to one controlled
agent; no opponent private payload is an input to either leaf evaluation.

The learned order may override current-money order only for a close pair with
sufficient model confidence.  Penalty, close-margin threshold and confidence
threshold are selected inside complete-EpisodeId CV.  Registered anchors may
not regress current-money ordering, and a phase needs a non-trivial net gain or
it freezes the current-money fallback.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

try:
    from rl.audit_hidden_state import replay_paths
    from rl.evaluate_leaf_value import (
        feature_names,
        group_folds,
        matrix,
        ridge_fit,
    )
    from rl.phase_leaf_value import (
        ANCHORS,
        CHECKPOINTS,
        PENALTIES,
        PHASES,
        evaluate_frozen,
        load_rows,
        serialize_ridge,
        serialized_ridge_predict,
    )
except ModuleNotFoundError:
    from audit_hidden_state import replay_paths  # type: ignore
    from evaluate_leaf_value import (  # type: ignore
        feature_names,
        group_folds,
        matrix,
        ridge_fit,
    )
    from phase_leaf_value import (  # type: ignore
        ANCHORS,
        CHECKPOINTS,
        PENALTIES,
        PHASES,
        evaluate_frozen,
        load_rows,
        serialize_ridge,
        serialized_ridge_predict,
    )


MARGIN_THRESHOLDS = (250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0)
CONFIDENCE_THRESHOLDS = (0.0, 0.1, 0.2, 0.4, 0.6, 0.8)
MIN_NET_GAIN_FRACTION = 0.02
MIN_NET_GAIN_COUNT = 2


def paired_examples(rows: list[dict], names: tuple[str, ...]) -> list[dict]:
    grouped = {}
    for row in rows:
        key = (int(row["episode_id"]), int(row["checkpoint"]))
        seat = int(row["seat"])
        if seat in grouped.setdefault(key, {}):
            raise ValueError(f"duplicate paired row {key} seat {seat}")
        grouped[key][seat] = row
    output = []
    for (episode_id, checkpoint), seats in sorted(grouped.items()):
        if set(seats) != {0, 1}:
            raise ValueError(f"incomplete paired row {(episode_id, checkpoint)}")
        left, right = seats[0], seats[1]
        left_x = matrix([left], names)[0]
        right_x = matrix([right], names)[0]
        final_margin = float(left["targets"]["final_margin"])
        if abs(final_margin) <= 1e-9:
            continue
        output.append(
            {
                "episode_id": episode_id,
                "checkpoint": checkpoint,
                "x": left_x - right_x,
                "label": float(np.sign(final_margin)),
                "current_margin": float(left["features"]["money_delta"]),
                "legal_margin": float(left["features"]["legal_marked_margin"]),
            }
        )
    return output


def phase_pairs(pairs: list[dict], start: int, stop: int) -> list[dict]:
    return [
        row
        for row in pairs
        if start <= int(row["checkpoint"]) <= stop
    ]


def pair_matrix(pairs: list[dict]) -> np.ndarray:
    return np.asarray([row["x"] for row in pairs], dtype=np.float64)


def pair_labels(pairs: list[dict]) -> np.ndarray:
    return np.asarray([row["label"] for row in pairs], dtype=np.float64)


def antisymmetric_ridge_fit(
    x: np.ndarray, y: np.ndarray, penalty: float
) -> dict:
    augmented_x = np.concatenate((x, -x), axis=0)
    augmented_y = np.concatenate((y, -y), axis=0)
    model = ridge_fit(augmented_x, augmented_y, penalty)
    if abs(float(model["target_center"])) > 1e-12:
        raise AssertionError("antisymmetric target center is nonzero")
    return model


def antisymmetric_oof(
    pairs: list[dict], folds: list[np.ndarray], penalty: float
) -> np.ndarray:
    x = pair_matrix(pairs)
    y = pair_labels(pairs)
    prediction = np.empty(len(pairs), dtype=np.float64)
    for holdout in folds:
        train = ~holdout
        prediction[holdout] = serialized_ridge_predict(
            serialize_ridge(antisymmetric_ridge_fit(x[train], y[train], penalty)),
            x[holdout],
        )
    return prediction


def accuracy(score: np.ndarray, truth: np.ndarray) -> float:
    return float(np.mean(np.sign(score) == truth))


def confidence_decision(
    current_margin: np.ndarray,
    learned_score: np.ndarray,
    margin_threshold: float,
    confidence_threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    current_sign = np.sign(current_margin)
    learned_sign = np.sign(learned_score)
    eligible = (
        (np.abs(current_margin) <= margin_threshold)
        & (np.abs(learned_score) >= confidence_threshold)
        & (learned_sign != 0)
    )
    override = eligible & (learned_sign != current_sign)
    decision = current_margin.copy()
    # Preserve a meaningful nonzero order magnitude while using only the
    # learned sign.  Metrics consume the order, not this arbitrary scale.
    decision[override] = learned_sign[override] * np.maximum(
        1.0, np.abs(current_margin[override])
    )
    return decision, override


def slice_accuracy(
    pairs: list[dict], score: np.ndarray, truth: np.ndarray
) -> dict[str, dict]:
    output = {
        "all": {
            "pairs": len(pairs),
            "accuracy": accuracy(score, truth),
        }
    }
    for checkpoint in CHECKPOINTS:
        mask = np.asarray(
            [int(row["checkpoint"]) == checkpoint for row in pairs], dtype=bool
        )
        output[str(checkpoint)] = {
            "pairs": int(mask.sum()),
            "accuracy": accuracy(score[mask], truth[mask]) if mask.any() else 0.0,
        }
    return output


def anchor_safe(
    pairs: list[dict], decision: np.ndarray, truth: np.ndarray
) -> tuple[bool, dict]:
    current = np.asarray([row["current_margin"] for row in pairs])
    checks = {}
    for checkpoint in ANCHORS:
        mask = np.asarray(
            [int(row["checkpoint"]) == checkpoint for row in pairs], dtype=bool
        )
        if not mask.any():
            continue
        candidate_accuracy = accuracy(decision[mask], truth[mask])
        current_accuracy = accuracy(current[mask], truth[mask])
        checks[str(checkpoint)] = {
            "candidate_accuracy": candidate_accuracy,
            "current_money_accuracy": current_accuracy,
            "pass": candidate_accuracy + 1e-12 >= current_accuracy,
        }
    return all(row["pass"] for row in checks.values()), checks


def select_phase_rank(
    pairs: list[dict], folds: list[np.ndarray]
) -> tuple[dict, np.ndarray, dict]:
    truth = pair_labels(pairs)
    current = np.asarray([row["current_margin"] for row in pairs])
    current_correct = np.sign(current) == truth
    current_accuracy = float(np.mean(current_correct))
    minimum_gain = max(
        MIN_NET_GAIN_COUNT,
        math.ceil(MIN_NET_GAIN_FRACTION * len(pairs)),
    )
    candidates = []
    all_diagnostics = []
    for penalty in PENALTIES:
        learned = antisymmetric_oof(pairs, folds, penalty)
        for margin_threshold in MARGIN_THRESHOLDS:
            for confidence_threshold in CONFIDENCE_THRESHOLDS:
                decision, override = confidence_decision(
                    current,
                    learned,
                    margin_threshold,
                    confidence_threshold,
                )
                safe, anchors = anchor_safe(pairs, decision, truth)
                correct = np.sign(decision) == truth
                repaired = int(np.sum(~current_correct & correct))
                harmed = int(np.sum(current_correct & ~correct))
                net_gain = repaired - harmed
                diagnostics = {
                    "penalty": penalty,
                    "margin_threshold": margin_threshold,
                    "confidence_threshold": confidence_threshold,
                    "accuracy": float(np.mean(correct)),
                    "current_accuracy": current_accuracy,
                    "override_count": int(override.sum()),
                    "repaired": repaired,
                    "harmed": harmed,
                    "net_gain": net_gain,
                    "minimum_net_gain": minimum_gain,
                    "anchor_safety": anchors,
                    "eligible": bool(safe and net_gain >= minimum_gain),
                }
                all_diagnostics.append(diagnostics)
                if not diagnostics["eligible"]:
                    continue
                key = (
                    -diagnostics["accuracy"],
                    diagnostics["override_count"],
                    margin_threshold,
                    confidence_threshold,
                    penalty,
                )
                spec = {
                    "kind": "confidence_ridge",
                    "penalty": penalty,
                    "margin_threshold": margin_threshold,
                    "confidence_threshold": confidence_threshold,
                }
                candidates.append((key, spec, decision, diagnostics))
    if candidates:
        _, selected, decision, diagnostics = min(
            candidates, key=lambda row: row[0]
        )
    else:
        selected = {"kind": "current_money"}
        decision = current.copy()
        diagnostics = {
            "accuracy": current_accuracy,
            "current_accuracy": current_accuracy,
            "override_count": 0,
            "repaired": 0,
            "harmed": 0,
            "net_gain": 0,
            "minimum_net_gain": minimum_gain,
            "anchor_safety": anchor_safe(pairs, current, truth)[1],
            "eligible": True,
        }
    top_diagnostics = sorted(
        all_diagnostics,
        key=lambda row: (
            -row["accuracy"],
            row["override_count"],
            row["margin_threshold"],
            row["confidence_threshold"],
            row["penalty"],
        ),
    )[:20]
    report = {
        "selected": selected,
        "selected_diagnostics": diagnostics,
        "oof": slice_accuracy(pairs, decision, truth),
        "current_money": slice_accuracy(pairs, current, truth),
        "legal_marked": slice_accuracy(
            pairs,
            np.asarray([row["legal_margin"] for row in pairs]),
            truth,
        ),
        "top_candidate_diagnostics": top_diagnostics,
    }
    return selected, decision, report


def fit_selected_rank(selected: dict, pairs: list[dict]) -> dict:
    output = dict(selected)
    if selected["kind"] == "confidence_ridge":
        model = antisymmetric_ridge_fit(
            pair_matrix(pairs), pair_labels(pairs), float(selected["penalty"])
        )
        output["ridge"] = serialize_ridge(model)
    return output


def predict_selected_rank(model: dict, pairs: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    current = np.asarray([row["current_margin"] for row in pairs])
    if model["kind"] == "current_money":
        return current.copy(), np.zeros(len(pairs), dtype=bool)
    learned = serialized_ridge_predict(model["ridge"], pair_matrix(pairs))
    return confidence_decision(
        current,
        learned,
        float(model["margin_threshold"]),
        float(model["confidence_threshold"]),
    )


def episode_ids_from_paths(paths: list[Path]) -> list[int]:
    ids = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        episode_id = int((payload.get("info", {}) or {}).get("EpisodeId", 0) or 0)
        if not episode_id:
            raise ValueError(f"missing EpisodeId: {path}")
        ids.append(episode_id)
    return sorted(set(ids))


def freeze(
    training_paths: list[Path], excluded_paths: list[Path], folds_count: int
) -> tuple[dict, dict]:
    rows, training_ids = load_rows(training_paths)
    names = feature_names(rows)
    pairs = paired_examples(rows, names)
    excluded_ids = sorted(
        set(training_ids) | set(episode_ids_from_paths(excluded_paths))
    )
    models = {}
    reports = {}
    assembled = []
    assembled_truth = []
    assembled_current = []
    for phase_name, start, stop in PHASES:
        selected_pairs = phase_pairs(pairs, start, stop)
        folds = group_folds(selected_pairs, folds_count)
        selected, decision, report = select_phase_rank(selected_pairs, folds)
        models[phase_name] = {
            "start": start,
            "stop": stop,
            "rank": fit_selected_rank(selected, selected_pairs),
        }
        reports[phase_name] = report
        assembled.extend(decision.tolist())
        assembled_truth.extend(pair_labels(selected_pairs).tolist())
        assembled_current.extend(
            [row["current_margin"] for row in selected_pairs]
        )
    assembled_array = np.asarray(assembled)
    truth_array = np.asarray(assembled_truth)
    current_array = np.asarray(assembled_current)
    training_accuracy = accuracy(assembled_array, truth_array)
    current_accuracy = accuracy(current_array, truth_array)
    training_gate = {
        "pass": training_accuracy > current_accuracy + 1e-12,
        "accuracy": training_accuracy,
        "current_money_accuracy": current_accuracy,
        "strict_gain": training_accuracy - current_accuracy,
        "phase_anchor_checks": {
            phase: reports[phase]["selected_diagnostics"]["anchor_safety"]
            for phase in reports
        },
    }
    provenance = ",".join(map(str, excluded_ids))
    model = {
        "schema": "kaggriculture-pairwise-leaf-rank-v1",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "training_episode_count": len(training_ids),
        "training_episode_ids": training_ids,
        "forbidden_evaluation_episode_count": len(excluded_ids),
        "forbidden_evaluation_episode_ids": excluded_ids,
        "forbidden_evaluation_sha256": hashlib.sha256(
            provenance.encode("ascii")
        ).hexdigest(),
        "feature_names": list(names),
        "phases": models,
        "training_cv_gate_pass": training_gate["pass"],
        "selection_contract": {
            "folds": folds_count,
            "minimum_net_gain_fraction": MIN_NET_GAIN_FRACTION,
            "minimum_net_gain_count": MIN_NET_GAIN_COUNT,
            "anchors": list(ANCHORS),
            "fallback": "current money",
        },
        "leakage_contract": {
            "pair": "difference of two independently legal controlled-seat observations",
            "deployment": "scalar legal leaf score; no opponent private input",
            "forbidden": "actions, names, IDs, source seed, opponent private payload",
        },
    }
    report = {
        "schema": "kaggriculture-pairwise-leaf-rank-freeze-v1",
        "model": model,
        "training_pair_count": len(pairs),
        "phase_reports": reports,
        "training_cv_gate": training_gate,
        "warning": "Commit this model before acquiring the second transfer block.",
    }
    return model, report


def evaluate(
    model: dict,
    phase_model: dict,
    transfer_paths: list[Path],
) -> dict:
    rows, episode_ids = load_rows(transfer_paths)
    overlap = sorted(
        set(episode_ids) & set(model["forbidden_evaluation_episode_ids"])
    )
    if overlap:
        raise ValueError(f"transfer EpisodeIds were previously visible: {overlap}")
    names = tuple(model["feature_names"])
    pairs = paired_examples(rows, names)
    phase_reports = {}
    all_decision = []
    all_truth = []
    all_current = []
    all_legal = []
    for phase_name, start, stop in PHASES:
        selected_pairs = phase_pairs(pairs, start, stop)
        decision, override = predict_selected_rank(
            model["phases"][phase_name]["rank"], selected_pairs
        )
        truth = pair_labels(selected_pairs)
        current = np.asarray(
            [row["current_margin"] for row in selected_pairs]
        )
        legal = np.asarray(
            [row["legal_margin"] for row in selected_pairs]
        )
        phase_reports[phase_name] = {
            "model": model["phases"][phase_name]["rank"],
            "override_count": int(override.sum()),
            "candidate": slice_accuracy(selected_pairs, decision, truth),
            "current_money": slice_accuracy(selected_pairs, current, truth),
            "legal_marked": slice_accuracy(selected_pairs, legal, truth),
        }
        all_decision.extend(decision.tolist())
        all_truth.extend(truth.tolist())
        all_current.extend(current.tolist())
        all_legal.extend(legal.tolist())
    decision = np.asarray(all_decision)
    truth = np.asarray(all_truth)
    current = np.asarray(all_current)
    legal = np.asarray(all_legal)
    rank_checks = {
        "all": {
            "candidate_accuracy": accuracy(decision, truth),
            "current_money_accuracy": accuracy(current, truth),
        }
    }
    for checkpoint in ANCHORS:
        phase_name = next(
            name
            for name, start, stop in PHASES
            if start <= checkpoint <= stop
        )
        candidate_row = phase_reports[phase_name]["candidate"][str(checkpoint)]
        current_row = phase_reports[phase_name]["current_money"][str(checkpoint)]
        legal_row = phase_reports[phase_name]["legal_marked"][str(checkpoint)]
        rank_checks[str(checkpoint)] = {
            "candidate_accuracy": candidate_row["accuracy"],
            "current_money_accuracy": current_row["accuracy"],
            "legal_marked_accuracy": legal_row["accuracy"],
        }
    rank_checks["all"]["strict_gain"] = (
        rank_checks["all"]["candidate_accuracy"]
        > rank_checks["all"]["current_money_accuracy"] + 1e-12
    )
    for scope, row in rank_checks.items():
        if scope == "all":
            continue
        row["pass"] = (
            row["candidate_accuracy"] + 1e-12
            >= row["current_money_accuracy"]
        )
    phase_value_report = evaluate_frozen(phase_model, transfer_paths)
    terminal_magnitude = {
        str(checkpoint): {
            "mae_pass": phase_value_report["regression"]["final_margin"]["checks"][str(checkpoint)]["mae_pass"],
            "winner_pass": phase_value_report["regression"]["final_margin"]["checks"][str(checkpoint)]["winner_pass"],
        }
        for checkpoint in (600, 648)
    }
    rank_pass = rank_checks["all"]["strict_gain"] and all(
        rank_checks[str(checkpoint)]["pass"] for checkpoint in ANCHORS
    )
    return {
        "schema": "kaggriculture-pairwise-leaf-rank-transfer-v1",
        "frozen_utc": model["frozen_utc"],
        "forbidden_evaluation_sha256": model["forbidden_evaluation_sha256"],
        "transfer_episode_count": len(episode_ids),
        "transfer_episode_ids": episode_ids,
        "overlap_episode_ids": overlap,
        "pair_count": len(pairs),
        "phase_reports": phase_reports,
        "rank_checks": rank_checks,
        "rank_gate_pass": rank_pass,
        "terminal_magnitude": terminal_magnitude,
        "terminal_magnitude_pass": all(
            row["mae_pass"] and row["winner_pass"]
            for row in terminal_magnitude.values()
        ),
        "fresh_transfer_gate_pass": (
            rank_pass
            and all(
                row["mae_pass"] and row["winner_pass"]
                for row in terminal_magnitude.values()
            )
        ),
        "phase_value_report": phase_value_report,
        "warning": (
            "Replay rank and terminal magnitude are only prerequisite gates; "
            "counterfactual macro-plan regret and official outcomes remain."
        ),
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("replays", nargs="+", type=Path)
    freeze_parser.add_argument(
        "--exclude-replays", nargs="+", type=Path, required=True
    )
    freeze_parser.add_argument("--folds", type=int, default=5)
    freeze_parser.add_argument("--model", type=Path, required=True)
    freeze_parser.add_argument("--report", type=Path, required=True)
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("model", type=Path)
    evaluate_parser.add_argument("phase_model", type=Path)
    evaluate_parser.add_argument("replays", nargs="+", type=Path)
    evaluate_parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "freeze":
        if args.folds < 2:
            parser.error("folds must be at least two")
        model, report = freeze(
            replay_paths(args.replays),
            replay_paths(args.exclude_replays),
            args.folds,
        )
        write_json(args.model, model)
        write_json(args.report, report)
        print(json.dumps({
            "model": str(args.model),
            "report": str(args.report),
            "training_cv_gate_pass": model["training_cv_gate_pass"],
        }))
        return

    model = json.loads(args.model.read_text(encoding="utf-8"))
    phase_model = json.loads(args.phase_model.read_text(encoding="utf-8"))
    report = evaluate(model, phase_model, replay_paths(args.replays))
    write_json(args.report, report)
    print(json.dumps({
        "report": str(args.report),
        "fresh_transfer_gate_pass": report["fresh_transfer_gate_pass"],
    }))


if __name__ == "__main__":
    main()
