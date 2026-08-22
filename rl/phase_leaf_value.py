"""Freeze and transfer a phase-consistent legal Kaggriculture leaf value.

The freeze command sees only the training replay block.  It keeps complete
EpisodeIds in one fold, fits separate early/mid/late/terminal ridge residuals,
and allows shrinkage back to a deterministic legal baseline.  A candidate is
eligible only when its grouped out-of-fold prediction does not regress current
money at registered checkpoints in its phase.  The resulting coefficients are
serialized before a fresh replay block is acquired.

The evaluate command refuses every EpisodeId present in the frozen training
provenance.  It never refits or selects on the transfer block.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

try:
    from rl.audit_hidden_state import replay_paths
    from rl.evaluate_leaf_value import (
        TARGETS,
        examples_from_replay,
        feature_names,
        group_folds,
        matrix,
        metric_slices,
        metrics,
        ridge_fit,
        ridge_predict,
        targets,
    )
except ModuleNotFoundError:
    from audit_hidden_state import replay_paths  # type: ignore
    from evaluate_leaf_value import (  # type: ignore
        TARGETS,
        examples_from_replay,
        feature_names,
        group_folds,
        matrix,
        metric_slices,
        metrics,
        ridge_fit,
        ridge_predict,
        targets,
    )


CHECKPOINTS = tuple(range(24, 649, 24))
PHASES = (
    ("early", 24, 192),
    ("mid", 216, 480),
    ("late", 504, 576),
    ("terminal", 600, 648),
)
ANCHORS = (360, 600, 648)
PENALTIES = (1.0, 10.0, 100.0, 1000.0)
BLENDS = (0.25, 0.5, 0.75, 1.0)
BASELINES = ("current_money", "legal_marked", "zero")
OFFSETS = ("current_money", "legal_marked", "zero")


def load_rows(paths: list[Path]) -> tuple[list[dict], list[int]]:
    rows = []
    episode_ids = []
    for path in paths:
        replay = json.loads(path.read_text(encoding="utf-8"))
        episode_id = int((replay.get("info", {}) or {}).get("EpisodeId", 0) or 0)
        if not episode_id:
            raise ValueError(f"missing EpisodeId: {path}")
        episode_ids.append(episode_id)
        rows.extend(examples_from_replay(replay, CHECKPOINTS))
    if len(set(episode_ids)) != len(episode_ids):
        raise ValueError("duplicate EpisodeId in replay block")
    return rows, sorted(episode_ids)


def phase_rows(rows: list[dict], start: int, stop: int) -> list[dict]:
    return [
        row
        for row in rows
        if start <= int(row["checkpoint"]) <= stop
    ]


def baseline_arrays(rows: list[dict]) -> dict[str, np.ndarray]:
    return {
        "current_money": np.asarray(
            [row["features"]["money_delta"] for row in rows],
            dtype=np.float64,
        ),
        "legal_marked": np.asarray(
            [row["features"]["legal_marked_margin"] for row in rows],
            dtype=np.float64,
        ),
        "zero": np.zeros(len(rows), dtype=np.float64),
    }


def ridge_oof(
    x: np.ndarray,
    y: np.ndarray,
    offset: np.ndarray,
    folds: list[np.ndarray],
    penalty: float,
) -> np.ndarray:
    prediction = np.empty(len(y), dtype=np.float64)
    for holdout in folds:
        train = ~holdout
        model = ridge_fit(x[train], y[train] - offset[train], penalty)
        prediction[holdout] = offset[holdout] + ridge_predict(
            model, x[holdout]
        )
    return prediction


def checkpoint_mask(rows: list[dict], checkpoint: int) -> np.ndarray:
    return np.asarray(
        [int(row["checkpoint"]) == checkpoint for row in rows], dtype=bool
    )


def current_anchor_safe(
    rows: list[dict],
    prediction: np.ndarray,
    truth: np.ndarray,
    current: np.ndarray,
) -> tuple[bool, dict]:
    checks = {}
    for checkpoint in ANCHORS:
        mask = checkpoint_mask(rows, checkpoint)
        if not mask.any():
            continue
        selected_rows = [row for row, keep in zip(rows, mask) if keep]
        candidate = metrics(selected_rows, prediction[mask], truth[mask])
        baseline = metrics(selected_rows, current[mask], truth[mask])
        checks[str(checkpoint)] = {
            "candidate_mae": candidate["mae"],
            "current_money_mae": baseline["mae"],
            "candidate_paired_winner": candidate["paired_winner_accuracy"],
            "current_money_paired_winner": baseline["paired_winner_accuracy"],
            "pass": (
                candidate["mae"] <= baseline["mae"] + 1e-9
                and candidate["paired_winner_accuracy"] + 1e-12
                >= baseline["paired_winner_accuracy"]
            ),
        }
    return all(row["pass"] for row in checks.values()), checks


def serialize_ridge(model: dict) -> dict:
    active = np.asarray(model["active"], dtype=bool)
    return {
        "center": np.asarray(model["center"], dtype=float).tolist(),
        "scale": np.asarray(model["scale"], dtype=float).tolist(),
        "active_indices": np.flatnonzero(active).astype(int).tolist(),
        "target_center": float(model["target_center"]),
        "weights": np.asarray(model["weights"], dtype=float).tolist(),
    }


def serialized_ridge_predict(model: dict, x: np.ndarray) -> np.ndarray:
    active = np.asarray(model["active_indices"], dtype=int)
    center = np.asarray(model["center"], dtype=np.float64)
    scale = np.asarray(model["scale"], dtype=np.float64)
    weights = np.asarray(model["weights"], dtype=np.float64)
    z = (x[:, active] - center[active]) / scale[active]
    return float(model["target_center"]) + z @ weights


def candidate_name(
    fallback: str, offset: str | None = None, penalty: float | None = None,
    blend: float = 0.0,
) -> str:
    if offset is None:
        return f"baseline_{fallback}"
    return f"blend{blend:g}_{fallback}_ridge_{offset}_p{penalty:g}"


def select_phase_regression(
    rows: list[dict],
    x: np.ndarray,
    target_name: str,
    folds: list[np.ndarray],
) -> tuple[dict, np.ndarray, dict]:
    y = targets(rows, target_name)
    baselines = baseline_arrays(rows)
    current = baselines["current_money"]
    candidates: list[tuple[tuple, dict, np.ndarray, dict]] = []

    for fallback_name in BASELINES:
        prediction = baselines[fallback_name]
        safe, anchors = current_anchor_safe(rows, prediction, y, current)
        if safe:
            score = metrics(rows, prediction, y)
            spec = {"kind": "baseline", "fallback": fallback_name}
            key = (score["mae"], -score["spearman"], candidate_name(fallback_name))
            candidates.append((key, spec, prediction, anchors))

    raw_predictions = {}
    for offset_name in OFFSETS:
        for penalty in PENALTIES:
            raw_predictions[(offset_name, penalty)] = ridge_oof(
                x, y, baselines[offset_name], folds, penalty
            )
    for fallback_name in BASELINES:
        fallback = baselines[fallback_name]
        for (offset_name, penalty), raw in raw_predictions.items():
            for blend in BLENDS:
                prediction = fallback + blend * (raw - fallback)
                safe, anchors = current_anchor_safe(
                    rows, prediction, y, current
                )
                if not safe:
                    continue
                score = metrics(rows, prediction, y)
                name = candidate_name(
                    fallback_name, offset_name, penalty, blend
                )
                spec = {
                    "kind": "ridge_blend",
                    "fallback": fallback_name,
                    "offset": offset_name,
                    "penalty": penalty,
                    "blend": blend,
                }
                key = (score["mae"], -score["spearman"], name)
                candidates.append((key, spec, prediction, anchors))
    if not candidates:
        raise ValueError(f"no anchor-safe candidate for {target_name}")
    _, selected, prediction, anchors = min(candidates, key=lambda row: row[0])
    report = {
        "candidate_count": len(candidates),
        "selected": selected,
        "oof": metric_slices(rows, prediction, y),
        "anchor_safety": anchors,
        "baselines": {
            name: metric_slices(rows, values, y)
            for name, values in baselines.items()
        },
    }
    return selected, prediction, report


def fit_selected_regression(
    selected: dict,
    x: np.ndarray,
    y: np.ndarray,
    baselines: dict[str, np.ndarray],
) -> dict:
    output = dict(selected)
    if selected["kind"] == "ridge_blend":
        model = ridge_fit(
            x,
            y - baselines[selected["offset"]],
            float(selected["penalty"]),
        )
        output["ridge"] = serialize_ridge(model)
    return output


def predict_regression(
    model: dict, x: np.ndarray, baselines: dict[str, np.ndarray]
) -> np.ndarray:
    fallback = baselines[model["fallback"]]
    if model["kind"] == "baseline":
        return fallback.copy()
    raw = baselines[model["offset"]] + serialized_ridge_predict(
        model["ridge"], x
    )
    return fallback + float(model["blend"]) * (raw - fallback)


def select_rank_head(
    rows: list[dict],
    x: np.ndarray,
    final_y: np.ndarray,
    regression_prediction: np.ndarray,
    folds: list[np.ndarray],
) -> tuple[dict, np.ndarray, dict]:
    baselines = baseline_arrays(rows)
    signed = np.sign(final_y)
    candidate_predictions = {
        "final_regression": regression_prediction,
        **baselines,
    }
    for penalty in PENALTIES:
        candidate_predictions[f"ridge_sign_p{penalty:g}"] = ridge_oof(
            x, signed, np.zeros(len(rows), dtype=np.float64), folds, penalty
        )
    candidates = []
    for name, prediction in candidate_predictions.items():
        safe, anchors = current_anchor_safe(
            rows, prediction, final_y, baselines["current_money"]
        )
        # Rank selection only constrains the paired outcome at anchors; MAE is
        # a regression-unit quantity and is intentionally ignored here.
        rank_safe = all(
            row["candidate_paired_winner"] + 1e-12
            >= row["current_money_paired_winner"]
            for row in anchors.values()
        )
        if not rank_safe:
            continue
        score = metrics(rows, prediction, final_y)
        key = (
            -score["paired_winner_accuracy"],
            -score["sign_accuracy"],
            name,
        )
        candidates.append((key, name, prediction, anchors, safe))
    if not candidates:
        raise ValueError("no anchor-safe final rank head")
    _, name, prediction, anchors, regression_safe = min(
        candidates, key=lambda row: row[0]
    )
    if name.startswith("ridge_sign_p"):
        penalty = float(name.rsplit("p", 1)[1])
        fitted = serialize_ridge(ridge_fit(x, signed, penalty))
        selected = {"kind": "ridge_sign", "penalty": penalty, "ridge": fitted}
    elif name == "final_regression":
        selected = {"kind": "final_regression"}
    else:
        selected = {"kind": "baseline", "baseline": name}
    report = {
        "candidate_count": len(candidates),
        "selected": selected,
        "oof": metric_slices(rows, prediction, final_y),
        "anchor_rank_safety": anchors,
        "also_regression_unit_safe": regression_safe,
    }
    return selected, prediction, report


def predict_rank(
    model: dict,
    x: np.ndarray,
    baselines: dict[str, np.ndarray],
    final_regression: np.ndarray,
) -> np.ndarray:
    if model["kind"] == "ridge_sign":
        return serialized_ridge_predict(model["ridge"], x)
    if model["kind"] == "final_regression":
        return final_regression.copy()
    return baselines[model["baseline"]].copy()


def strongest_gate(
    rows: list[dict],
    prediction: np.ndarray,
    truth: np.ndarray,
    baselines: dict[str, np.ndarray],
    strict_overall: bool,
) -> dict:
    candidate = metric_slices(rows, prediction, truth)
    baseline_metrics = {
        name: metric_slices(rows, values, truth)
        for name, values in baselines.items()
    }
    checks = {}
    scopes = ("all", "360", "600", "648")
    for scope in scopes:
        best_mae = min(
            baseline_metrics,
            key=lambda name: (baseline_metrics[name][scope]["mae"], name),
        )
        best_winner = max(
            baseline_metrics,
            key=lambda name: (
                baseline_metrics[name][scope]["paired_winner_accuracy"],
                name,
            ),
        )
        mae = candidate[scope]["mae"]
        baseline_mae = baseline_metrics[best_mae][scope]["mae"]
        mae_pass = mae < baseline_mae if strict_overall and scope == "all" else mae <= baseline_mae + 1e-9
        checks[scope] = {
            "mae": mae,
            "best_baseline_mae": baseline_mae,
            "best_mae_baseline": best_mae,
            "paired_winner": candidate[scope]["paired_winner_accuracy"],
            "best_baseline_paired_winner": baseline_metrics[best_winner][scope]["paired_winner_accuracy"],
            "best_winner_baseline": best_winner,
            "mae_pass": bool(mae_pass),
            "winner_pass": (
                candidate[scope]["paired_winner_accuracy"] + 1e-12
                >= baseline_metrics[best_winner][scope]["paired_winner_accuracy"]
            ),
        }
    return {
        "pass": all(
            row["mae_pass"] and row["winner_pass"]
            for row in checks.values()
        ),
        "checks": checks,
        "candidate": candidate,
        "baselines": baseline_metrics,
    }


def freeze(paths: list[Path], folds_count: int) -> tuple[dict, dict]:
    rows, episode_ids = load_rows(paths)
    names = feature_names(rows)
    phase_models = {}
    reports = {}
    assembled_predictions = {
        target: np.empty(len(rows), dtype=np.float64) for target in TARGETS
    }
    assembled_rank = np.empty(len(rows), dtype=np.float64)
    row_index = {id(row): index for index, row in enumerate(rows)}

    for phase_name, start, stop in PHASES:
        selected_rows = phase_rows(rows, start, stop)
        indices = np.asarray([row_index[id(row)] for row in selected_rows])
        x = matrix(selected_rows, names)
        folds = group_folds(selected_rows, folds_count)
        baselines = baseline_arrays(selected_rows)
        target_models = {}
        target_reports = {}
        target_oof = {}
        for target_name in TARGETS:
            selected, prediction, report = select_phase_regression(
                selected_rows, x, target_name, folds
            )
            target_models[target_name] = fit_selected_regression(
                selected,
                x,
                targets(selected_rows, target_name),
                baselines,
            )
            target_reports[target_name] = report
            target_oof[target_name] = prediction
            assembled_predictions[target_name][indices] = prediction
        rank_model, rank_prediction, rank_report = select_rank_head(
            selected_rows,
            x,
            targets(selected_rows, "final_margin"),
            target_oof["final_margin"],
            folds,
        )
        assembled_rank[indices] = rank_prediction
        phase_models[phase_name] = {
            "start": start,
            "stop": stop,
            "targets": target_models,
            "final_rank": rank_model,
        }
        reports[phase_name] = {
            "rows": len(selected_rows),
            "targets": target_reports,
            "final_rank": rank_report,
        }

    baselines = baseline_arrays(rows)
    gates = {
        target: strongest_gate(
            rows,
            assembled_predictions[target],
            targets(rows, target),
            baselines,
            strict_overall=True,
        )
        for target in TARGETS
    }
    rank_truth = targets(rows, "final_margin")
    rank_metrics = metric_slices(rows, assembled_rank, rank_truth)
    rank_baselines = {
        name: metric_slices(rows, values, rank_truth)
        for name, values in baselines.items()
    }
    rank_checks = {}
    for scope in ("all", "360", "600", "648"):
        best_name = max(
            rank_baselines,
            key=lambda name: (
                rank_baselines[name][scope]["paired_winner_accuracy"], name
            ),
        )
        rank_checks[scope] = {
            "paired_winner": rank_metrics[scope]["paired_winner_accuracy"],
            "best_baseline": best_name,
            "best_baseline_paired_winner": rank_baselines[best_name][scope]["paired_winner_accuracy"],
            "pass": (
                rank_metrics[scope]["paired_winner_accuracy"] + 1e-12
                >= rank_baselines[best_name][scope]["paired_winner_accuracy"]
            ),
        }
    training_gate = {
        "pass": all(gate["pass"] for gate in gates.values())
        and all(row["pass"] for row in rank_checks.values()),
        "regression": gates,
        "final_rank": {
            "pass": all(row["pass"] for row in rank_checks.values()),
            "checks": rank_checks,
            "candidate": rank_metrics,
            "baselines": rank_baselines,
        },
    }
    provenance_text = ",".join(map(str, episode_ids))
    model = {
        "schema": "kaggriculture-phase-leaf-value-v1",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "training_episode_count": len(episode_ids),
        "training_episode_ids": episode_ids,
        "training_episode_sha256": hashlib.sha256(
            provenance_text.encode("ascii")
        ).hexdigest(),
        "feature_names": list(names),
        "checkpoints": list(CHECKPOINTS),
        "anchors": list(ANCHORS),
        "phases": phase_models,
        "training_cv_gate_pass": training_gate["pass"],
        "leakage_contract": {
            "features": "controlled-seat legal observation only",
            "split": "complete EpisodeId grouped CV",
            "forbidden": "actions, names, IDs, source seed, opponent private payload",
        },
    }
    report = {
        "schema": "kaggriculture-phase-leaf-value-freeze-report-v1",
        "model": model,
        "training_rows": len(rows),
        "folds": folds_count,
        "phase_reports": reports,
        "training_cv_gate": training_gate,
        "warning": "Freeze this model in Git before acquiring a transfer block.",
    }
    return model, report


def phase_for_checkpoint(model: dict, checkpoint: int) -> tuple[str, dict]:
    for name, phase in model["phases"].items():
        if int(phase["start"]) <= checkpoint <= int(phase["stop"]):
            return name, phase
    raise ValueError(f"checkpoint {checkpoint} outside frozen phases")


def evaluate_frozen(model: dict, paths: list[Path]) -> dict:
    rows, episode_ids = load_rows(paths)
    overlap = sorted(set(episode_ids) & set(model["training_episode_ids"]))
    if overlap:
        raise ValueError(f"transfer EpisodeIds overlap frozen training: {overlap}")
    names = tuple(model["feature_names"])
    predictions = {
        target: np.empty(len(rows), dtype=np.float64) for target in TARGETS
    }
    rank_prediction = np.empty(len(rows), dtype=np.float64)
    grouped_indices: dict[str, list[int]] = {
        name: [] for name in model["phases"]
    }
    for index, row in enumerate(rows):
        phase_name, _ = phase_for_checkpoint(
            model, int(row["checkpoint"])
        )
        grouped_indices[phase_name].append(index)
    for phase_name, indices_list in grouped_indices.items():
        indices = np.asarray(indices_list, dtype=int)
        selected_rows = [rows[index] for index in indices]
        x = matrix(selected_rows, names)
        baselines = baseline_arrays(selected_rows)
        phase = model["phases"][phase_name]
        phase_predictions = {}
        for target_name in TARGETS:
            phase_predictions[target_name] = predict_regression(
                phase["targets"][target_name], x, baselines
            )
            predictions[target_name][indices] = phase_predictions[target_name]
        rank_prediction[indices] = predict_rank(
            phase["final_rank"],
            x,
            baselines,
            phase_predictions["final_margin"],
        )
    baselines = baseline_arrays(rows)
    gates = {
        target: strongest_gate(
            rows,
            predictions[target],
            targets(rows, target),
            baselines,
            strict_overall=True,
        )
        for target in TARGETS
    }
    final_y = targets(rows, "final_margin")
    rank_candidate = metric_slices(rows, rank_prediction, final_y)
    rank_baselines = {
        name: metric_slices(rows, values, final_y)
        for name, values in baselines.items()
    }
    rank_checks = {}
    for scope in ("all", "360", "600", "648"):
        best_name = max(
            rank_baselines,
            key=lambda name: (
                rank_baselines[name][scope]["paired_winner_accuracy"], name
            ),
        )
        rank_checks[scope] = {
            "paired_winner": rank_candidate[scope]["paired_winner_accuracy"],
            "best_baseline": best_name,
            "best_baseline_paired_winner": rank_baselines[best_name][scope]["paired_winner_accuracy"],
            "pass": (
                rank_candidate[scope]["paired_winner_accuracy"] + 1e-12
                >= rank_baselines[best_name][scope]["paired_winner_accuracy"]
            ),
        }
    final_rank = {
        "pass": all(row["pass"] for row in rank_checks.values()),
        "checks": rank_checks,
        "candidate": rank_candidate,
        "baselines": rank_baselines,
    }
    return {
        "schema": "kaggriculture-phase-leaf-value-transfer-v1",
        "frozen_utc": model["frozen_utc"],
        "training_episode_sha256": model["training_episode_sha256"],
        "transfer_episode_count": len(episode_ids),
        "transfer_episode_ids": episode_ids,
        "overlap_episode_ids": overlap,
        "rows": len(rows),
        "regression": gates,
        "final_rank": final_rank,
        "fresh_transfer_gate_pass": (
            all(gate["pass"] for gate in gates.values())
            and final_rank["pass"]
        ),
        "warning": (
            "This gate covers predictive transfer only. Macro-plan regret, "
            "latency and official outcomes remain mandatory."
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
    freeze_parser.add_argument("--folds", type=int, default=5)
    freeze_parser.add_argument("--model", type=Path, required=True)
    freeze_parser.add_argument("--report", type=Path, required=True)
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("model", type=Path)
    evaluate_parser.add_argument("replays", nargs="+", type=Path)
    evaluate_parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "freeze":
        if args.folds < 2:
            parser.error("folds must be at least two")
        paths = replay_paths(args.replays)
        model, report = freeze(paths, args.folds)
        write_json(args.model, model)
        write_json(args.report, report)
        print(json.dumps({
            "model": str(args.model),
            "report": str(args.report),
            "training_cv_gate_pass": model["training_cv_gate_pass"],
        }))
        return

    model = json.loads(args.model.read_text(encoding="utf-8"))
    report = evaluate_frozen(model, replay_paths(args.replays))
    write_json(args.report, report)
    print(json.dumps({
        "report": str(args.report),
        "fresh_transfer_gate_pass": report["fresh_transfer_gate_pass"],
    }))


if __name__ == "__main__":
    main()
