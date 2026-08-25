"""Fit a leakage-aware value gate for one bounded WHEAT sale advance.

The input reports must evaluate KEEP_BASE and ADVANCE1 on exactly the same
public seed, seat, and opponent action tape.  The target is the paired final
margin difference, not an imitation label.  All features are public at step
112, before the step-119 intervention.

Validation leaves one complete opponent identity out and removes every
training row sharing an episode with that fold.  Model-complexity selection is
nested inside the outer split.  Kaggle replay metadata exposes opponent names,
not opponent submission ids; the report calls out that unavoidable limitation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.tree import DecisionTreeRegressor


SEED = 20260825
CHECKPOINT_STEP = 112
RUNTIME_SCHEMA = "kaggriculture-distilled-wheat-gate-v1"
TREATMENT_LABEL = "e151-direct-always-step112-step119-cap1"
EXECUTE_STEP = 119
SELL_CAP = 1
CASE_IDENTITY_FIELDS = (
    "episode_id",
    "seed",
    "target_seat",
    "target_name",
    "target_submission_id",
    "opponent_name",
    "recorded_target_bank",
    "recorded_opponent_bank",
)
WHEAT_SHOPS = (
    "bakery",
    "pizza_shop",
    "brunch_spot",
    "ice_cream_shop",
    "farmers_market",
)

# Deliberately narrow, coordinate-free, runtime-supported feature contract.
# ``focus`` is the opponent and ``other`` is our fixed S09 backbone, matching
# tools.make_ml_wheat_gate's naming convention.
FEATURES = (
    "x_market_price_wheat",
    "x_market_inventory_wheat",
    *(f"x_shop_{shop}" for shop in WHEAT_SHOPS),
    "x_focus_money",
    "x_focus_hands",
    "x_focus_crop_wheat",
)
RULE_FEATURES = (
    "target_seat",
    "x_market_price_wheat",
    "x_market_inventory_wheat",
    "x_wheat_shop_instances",
    "x_focus_money",
    "x_focus_hands",
    "x_focus_crop_wheat",
)
RULE_DIRECTIONS = ("le", "gt")
RULE_MIN_SELECTED = 8
RULE_MIN_BENEFITED = 3


@dataclass(frozen=True)
class ModelSpec:
    name: str
    max_depth: int | None
    min_samples_leaf: int


SPECS = (
    ModelSpec("KEEP_BASE", None, 0),
    ModelSpec("stump-leaf8", 1, 8),
    ModelSpec("depth2-leaf10", 2, 10),
)
SPEC_BY_NAME = {spec.name: spec for spec in SPECS}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_name(value: object) -> str:
    return " ".join(str(value).casefold().split())


def keyed_matches(report: dict, candidate: str) -> dict[tuple[int, int, str], dict]:
    payload = (report.get("candidates") or {}).get(candidate)
    if not payload:
        raise ValueError(f"candidate {candidate!r} is absent from report")
    result = {}
    for row in payload.get("matches", []):
        key = (
            int(row["episode_id"]),
            int(row["target_seat"]),
            str(row["target_name"]),
        )
        if key in result:
            raise ValueError(f"duplicate match key {key!r}")
        result[key] = row
    return result


def checkpoint(row: dict, step: int = CHECKPOINT_STEP) -> dict:
    checkpoints = row.get("public_context_checkpoints")
    if not isinstance(checkpoints, list):
        raise ValueError("public_context_checkpoints must be a list")
    matches = [
        value
        for value in checkpoints
        if isinstance(value, dict) and value.get("step") == step
    ]
    if len(matches) != 1:
        raise ValueError(
            f"row {row.get('episode_id')} seat {row.get('target_seat')} has "
            f"{len(matches)} public checkpoints at step {step}"
        )
    result = matches[0]
    if result.get("day") != step // 24 or result.get("hour") != step % 24:
        raise ValueError(f"checkpoint {step} has an inconsistent public clock")
    return result


def required_mapping(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def required_list(value: object, path: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list")
    return value


def finite_number(value: object, path: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{path} must be numeric, not boolean")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path} must be numeric") from error
    if not math.isfinite(result):
        raise ValueError(f"{path} must be finite")
    return result


def required_number(mapping: dict, key: object, path: str) -> float:
    if key not in mapping:
        raise ValueError(f"missing {path}")
    return finite_number(mapping[key], path)


def required_int(mapping: dict, key: object, path: str) -> int:
    value = required_number(mapping, key, path)
    result = int(value)
    if value != result:
        raise ValueError(f"{path} must be an integer")
    return result


def seat_value(mapping: dict, seat: int, path: str) -> object:
    if seat in mapping:
        return mapping[seat]
    if str(seat) in mapping:
        return mapping[str(seat)]
    raise ValueError(f"missing {path}[{seat}]")


def public_features(context: dict) -> dict[str, float]:
    context = required_mapping(context, "checkpoint")
    market_prices = required_mapping(context.get("market_prices"), "market_prices")
    market_inventory = required_mapping(
        context.get("market_inventory"), "market_inventory"
    )
    raw_shops = required_list(context.get("shops"), "shops")
    if any(not isinstance(value, str) or not value.strip() for value in raw_shops):
        raise ValueError("every shop must be a non-empty string")
    shops = Counter(value.casefold() for value in raw_shops)
    focus = required_mapping(context.get("opponent"), "opponent")
    hands = required_list(focus.get("hands"), "opponent.hands")
    occupied = required_list(focus.get("occupied"), "opponent.occupied")
    wheat_tiles = 0
    for index, tile in enumerate(occupied):
        if not isinstance(tile, list) or len(tile) != 5:
            raise ValueError(f"opponent.occupied[{index}] must have five fields")
        if tile[3] is not None and not isinstance(tile[3], str):
            raise ValueError(f"opponent.occupied[{index}].crop must be a string or null")
        wheat_tiles += int(str(tile[3]).upper() == "WHEAT")
    result = {
        "x_market_price_wheat": required_number(
            market_prices, "WHEAT", "market_prices.WHEAT"
        ),
        "x_market_inventory_wheat": required_number(
            market_inventory, "WHEAT", "market_inventory.WHEAT"
        ),
    }
    for shop in WHEAT_SHOPS:
        result[f"x_shop_{shop}"] = float(shops.get(shop, 0))
    result.update(
        {
            "x_focus_money": required_number(focus, "money", "opponent.money"),
            "x_focus_hands": float(len(hands)),
            "x_focus_crop_wheat": float(wheat_tiles),
        }
    )
    if tuple(result) != FEATURES:
        raise RuntimeError("public feature builder violated its exact schema")
    for name, value in result.items():
        finite_number(value, name)
    return result


def q3_imitation_accept(context: dict) -> bool:
    """Replay-corpus q3 rule, reported only as a non-holdout comparison."""
    context = required_mapping(context, "checkpoint")
    inventory = required_mapping(context.get("market_inventory"), "market_inventory")
    opponent = required_mapping(context.get("opponent"), "opponent")
    money = required_number(opponent, "money", "opponent.money")
    wool_inventory = required_number(
        inventory, "WOOL", "market_inventory.WOOL"
    )
    return bool(money > 20.5 or (money <= 20.5 and wool_inventory <= 9985.0))


def treatment_units(row: dict) -> int:
    """Validate the exact direct-wrapper contract and return 0/1 units."""
    telemetry = required_mapping(row.get("candidate_telemetry"), "candidate_telemetry")
    exact = {
        "label": TREATMENT_LABEL,
        "checkpoint_step": CHECKPOINT_STEP,
        "execute_step": EXECUTE_STEP,
        "sell_cap": SELL_CAP,
        "model_schema": RUNTIME_SCHEMA,
    }
    for key, expected in exact.items():
        if telemetry.get(key) != expected:
            raise ValueError(
                f"treatment telemetry {key}={telemetry.get(key)!r}, expected {expected!r}"
            )
    advanced = required_mapping(telemetry.get("market_advanced"), "market_advanced")
    repaid = required_mapping(telemetry.get("market_repaid"), "market_repaid")
    units = required_int(advanced, "WHEAT", "market_advanced.WHEAT")
    repaid_units = required_int(repaid, "WHEAT", "market_repaid.WHEAT")
    if units not in (0, 1):
        raise ValueError(f"market_advanced.WHEAT must be 0 or 1, got {units}")
    if repaid_units != units:
        raise ValueError(
            f"market repayment mismatch: advanced={units}, repaid={repaid_units}"
        )
    executed = required_int(telemetry, "executed", "executed")
    if executed != units:
        raise ValueError(f"executed={executed} does not match advanced={units}")
    seat = int(row["target_seat"])
    debt = required_mapping(telemetry.get("debt"), "debt")
    terminal_debt = finite_number(seat_value(debt, seat, "debt"), f"debt[{seat}]")
    if terminal_debt != 0.0:
        raise ValueError(f"terminal debt[{seat}] must be zero, got {terminal_debt}")
    return units


def case_key(case: dict) -> tuple[int, int, str]:
    return (
        int(case["episode_id"]),
        int(case["target_seat"]),
        str(case["target_name"]),
    )


def keyed_cases(report: dict) -> dict[tuple[int, int, str], dict]:
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("report cases must be a list")
    result = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("every report case must be an object")
        key = case_key(case)
        if key in result:
            raise ValueError(f"duplicate case key {key!r}")
        result[key] = case
    return result


def tape_sha_if_present(case: dict, field: str) -> str | None:
    raw = case.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field} must be a non-empty path string")
    path = Path(raw)
    return sha256(path) if path.is_file() else None


def validate_paired_cases(
    reference_report: dict, treatment_report: dict
) -> dict[tuple[int, int, str], dict]:
    reference = keyed_cases(reference_report)
    treatment = keyed_cases(treatment_report)
    if set(reference) != set(treatment):
        raise ValueError("reference and treatment reports have different case keys")
    for key in sorted(reference):
        left = reference[key]
        right = treatment[key]
        for field in CASE_IDENTITY_FIELDS:
            if field not in left or field not in right or left[field] != right[field]:
                raise ValueError(f"paired case {key!r} differs at {field}")
        for field in ("target_tape", "opponent_tape"):
            left_sha = tape_sha_if_present(left, field)
            right_sha = tape_sha_if_present(right, field)
            if left_sha is not None and right_sha is not None and left_sha != right_sha:
                raise ValueError(f"paired case {key!r} has different {field} bytes")
            if (left_sha is None) != (right_sha is None):
                raise ValueError(
                    f"paired case {key!r} has only one readable {field} path"
                )
    return reference


def build_rows(
    reference_report: dict,
    treatment_report: dict,
    reference_candidate: str,
    treatment_candidate: str,
) -> tuple[list[dict], dict]:
    reference = keyed_matches(reference_report, reference_candidate)
    treatment = keyed_matches(treatment_report, treatment_candidate)
    paired_cases = validate_paired_cases(reference_report, treatment_report)
    if set(reference) != set(treatment):
        missing_treatment = sorted(set(reference) - set(treatment))
        missing_reference = sorted(set(treatment) - set(reference))
        raise ValueError(
            "paired reports have different match keys: "
            f"missing treatment={len(missing_treatment)}, "
            f"missing reference={len(missing_reference)}"
        )
    if set(reference) != set(paired_cases):
        raise ValueError("match rows and top-level cases have different identities")
    rows = []
    untreated = 0
    policy_ids_by_name: dict[str, set[int]] = defaultdict(set)
    for case in reference_report.get("cases", []):
        submission_id = int(case.get("target_submission_id", 0) or 0)
        if submission_id:
            policy_ids_by_name[normalize_name(case.get("target_name", ""))].add(
                submission_id
            )
    ambiguous_names = {
        name: sorted(values)
        for name, values in policy_ids_by_name.items()
        if len(values) > 1
    }
    if ambiguous_names:
        raise ValueError(f"target names map to multiple submission ids: {ambiguous_names}")
    known_opponent_policy_rows = 0
    for key in sorted(reference):
        base = reference[key]
        advanced = treatment[key]
        case = paired_cases[key]
        for field in ("episode_id", "target_seat", "target_name", "opponent_name"):
            if base.get(field) != advanced.get(field):
                raise ValueError(f"paired match {key!r} differs at {field}")
            if field in case and base.get(field) != case.get(field):
                raise ValueError(f"match {key!r} disagrees with its case at {field}")
        base_checkpoint = checkpoint(base)
        treatment_checkpoint = checkpoint(advanced)
        if base_checkpoint != treatment_checkpoint:
            raise ValueError(f"paired match {key!r} differs at public checkpoint 112")
        units = treatment_units(advanced)
        if units < 1:
            untreated += 1
            for field in ("candidate_bank", "opponent_bank", "margin", "outcome"):
                left = finite_number(base.get(field), f"reference.{field}")
                right = finite_number(advanced.get(field), f"treatment.{field}")
                if left != right:
                    raise ValueError(
                        f"untreated match {key!r} changed {field}: {left} != {right}"
                    )
        features = public_features(base_checkpoint)
        opponent_name = str(base["opponent_name"])
        normalized_opponent = normalize_name(opponent_name)
        known_ids = policy_ids_by_name.get(normalized_opponent, set())
        opponent_policy_id = next(iter(known_ids)) if known_ids else None
        if opponent_policy_id is not None:
            known_opponent_policy_rows += 1
        opponent_group = (
            f"submission:{opponent_policy_id}"
            if opponent_policy_id is not None
            else f"name:{normalized_opponent}"
        )
        row = {
            "episode_id": int(base["episode_id"]),
            "seed": int(case["seed"]),
            "target_seat": int(base["target_seat"]),
            "target_name": str(base["target_name"]),
            "opponent_name": opponent_name,
            "opponent_policy_id": opponent_policy_id,
            "opponent_group": opponent_group,
            "reference_margin": finite_number(base.get("margin"), "reference.margin"),
            "treatment_margin": finite_number(
                advanced.get("margin"), "treatment.margin"
            ),
            "margin_delta": finite_number(
                finite_number(advanced.get("margin"), "treatment.margin")
                - finite_number(base.get("margin"), "reference.margin"),
                "margin_delta",
            ),
            "outcome_delta": finite_number(
                finite_number(advanced.get("outcome"), "treatment.outcome")
                - finite_number(base.get("outcome"), "reference.outcome"),
                "outcome_delta",
            ),
            "advanced_units": units,
            "eligible": units == 1,
            "q3_imitation_accept": q3_imitation_accept(base_checkpoint),
            "features": features,
        }
        row["rule_features"] = {
            "target_seat": float(row["target_seat"]),
            "x_market_price_wheat": features["x_market_price_wheat"],
            "x_market_inventory_wheat": features["x_market_inventory_wheat"],
            "x_wheat_shop_instances": float(
                sum(features[f"x_shop_{shop}"] for shop in WHEAT_SHOPS)
            ),
            "x_focus_money": features["x_focus_money"],
            "x_focus_hands": features["x_focus_hands"],
            "x_focus_crop_wheat": features["x_focus_crop_wheat"],
        }
        if tuple(row["rule_features"]) != RULE_FEATURES:
            raise RuntimeError("rule feature builder violated its exact schema")
        rows.append(row)
    telemetry = {
        "paired_rows": len(reference),
        "eligible_advanced_rows": len(rows) - untreated,
        "untreated_noop_rows": untreated,
        "rows_with_known_opponent_submission_id": known_opponent_policy_rows,
        "rows_grouped_by_opponent_name_fallback": len(rows)
        - known_opponent_policy_rows,
    }
    if len(rows) != len(reference):
        raise RuntimeError("paired row accounting failed")
    return rows, telemetry


def arrays(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(
        [[row["features"][name] for name in FEATURES] for row in rows], dtype=float
    )
    y = np.asarray([row["margin_delta"] for row in rows], dtype=float)
    groups = np.asarray([row["opponent_group"] for row in rows], dtype=object)
    episodes = np.asarray([row["episode_id"] for row in rows], dtype=np.int64)
    return x, y, groups, episodes


def fit_model(spec: ModelSpec, x: np.ndarray, y: np.ndarray):
    if spec.name == "KEEP_BASE":
        return None
    model = DecisionTreeRegressor(
        criterion="squared_error",
        max_depth=spec.max_depth,
        min_samples_leaf=spec.min_samples_leaf,
        random_state=SEED,
    )
    model.fit(x, y)
    return model


def predict_model(model, x: np.ndarray) -> np.ndarray:
    return np.zeros(len(x), dtype=float) if model is None else model.predict(x)


def purged_logo_predictions(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    episodes: np.ndarray,
    spec: ModelSpec,
) -> tuple[np.ndarray, list[dict]]:
    predictions = np.full(len(y), np.nan, dtype=float)
    folds = []
    for held_group in sorted(set(groups.tolist())):
        test = np.flatnonzero(groups == held_group)
        test_episodes = set(episodes[test].tolist())
        nominal_train = np.flatnonzero(groups != held_group)
        train = np.asarray(
            [index for index in nominal_train if int(episodes[index]) not in test_episodes],
            dtype=int,
        )
        if len(train) == 0:
            raise ValueError(f"held group {held_group!r} leaves no purged training rows")
        model = fit_model(spec, x[train], y[train])
        predictions[test] = predict_model(model, x[test])
        folds.append(
            {
                "held_opponent_group": held_group,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "episode_purged_rows": int(len(nominal_train) - len(train)),
            }
        )
    if np.isnan(predictions).any():
        raise RuntimeError("some rows lack out-of-fold predictions")
    return predictions, folds


def choose_spec_inner(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    episodes: np.ndarray,
) -> tuple[ModelSpec, list[dict]]:
    if len(set(groups.tolist())) < 2:
        return SPEC_BY_NAME["KEEP_BASE"], [
            {"spec": "KEEP_BASE", "mean_policy_uplift": 0.0}
        ]
    scores = []
    for complexity, spec in enumerate(SPECS):
        predicted, _ = purged_logo_predictions(x, y, groups, episodes, spec)
        selected = predicted > 0.0
        uplift = np.where(selected, y, 0.0)
        scores.append(
            {
                "spec": spec.name,
                "mean_policy_uplift": float(uplift.mean()),
                "selected_rows": int(selected.sum()),
                "complexity": complexity,
            }
        )
    # Prefer the simpler model for an exact uplift tie.
    winner = max(scores, key=lambda row: (row["mean_policy_uplift"], -row["complexity"]))
    return SPEC_BY_NAME[winner["spec"]], scores


def nested_predictions(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    episodes: np.ndarray,
) -> tuple[np.ndarray, list[dict]]:
    predictions = np.full(len(y), np.nan, dtype=float)
    folds = []
    for held_group in sorted(set(groups.tolist())):
        test = np.flatnonzero(groups == held_group)
        test_episodes = set(episodes[test].tolist())
        nominal_train = np.flatnonzero(groups != held_group)
        train = np.asarray(
            [index for index in nominal_train if int(episodes[index]) not in test_episodes],
            dtype=int,
        )
        if len(train) == 0:
            raise ValueError(f"held group {held_group!r} leaves no purged training rows")
        selected_spec, inner_scores = choose_spec_inner(
            x[train], y[train], groups[train], episodes[train]
        )
        model = fit_model(selected_spec, x[train], y[train])
        predictions[test] = predict_model(model, x[test])
        folds.append(
            {
                "held_opponent_group": held_group,
                "selected_spec": selected_spec.name,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "episode_purged_rows": int(len(nominal_train) - len(train)),
                "inner_scores": inner_scores,
            }
        )
    if np.isnan(predictions).any():
        raise RuntimeError("some rows lack nested out-of-fold predictions")
    return predictions, folds


def cluster_bootstrap(
    uplift: np.ndarray,
    groups: np.ndarray,
    repetitions: int = 20_000,
) -> dict:
    unique = sorted(set(groups.tolist()))
    indices = {group: np.flatnonzero(groups == group) for group in unique}
    rng = np.random.default_rng(SEED)
    samples = np.empty(repetitions, dtype=float)
    for repetition in range(repetitions):
        draw = rng.choice(unique, size=len(unique), replace=True)
        selected = np.concatenate([indices[group] for group in draw])
        samples[repetition] = float(uplift[selected].mean())
    low, high = np.quantile(samples, [0.025, 0.975])
    return {
        "unit": "opponent_group",
        "groups": len(unique),
        "repetitions": repetitions,
        "mean": float(uplift.mean()),
        "ci95": [float(low), float(high)],
        "probability_mean_positive": float((samples > 0.0).mean()),
    }


def policy_metrics(
    y: np.ndarray,
    outcome_delta: np.ndarray,
    groups: np.ndarray,
    predictions: np.ndarray,
) -> dict:
    selected = predictions > 0.0
    uplift = np.where(selected, y, 0.0)
    selected_delta = y[selected]
    return {
        "rows": int(len(y)),
        "selected_rows": int(selected.sum()),
        "selection_rate": float(selected.mean()),
        "total_margin_uplift": float(uplift.sum()),
        "mean_margin_uplift_per_game": float(uplift.mean()),
        "mean_delta_when_selected": (
            float(selected_delta.mean()) if len(selected_delta) else None
        ),
        "benefited_selected": int((selected_delta > 0).sum()),
        "neutral_selected": int((selected_delta == 0).sum()),
        "harmed_selected": int((selected_delta < 0).sum()),
        "outcome_improvements": int(((outcome_delta > 0) & selected).sum()),
        "outcome_regressions": int(((outcome_delta < 0) & selected).sum()),
        "cluster_bootstrap": cluster_bootstrap(uplift, groups),
    }


def rule_mask(values: np.ndarray, direction: str, threshold: float) -> np.ndarray:
    if direction == "le":
        return values <= threshold
    if direction == "gt":
        return values > threshold
    raise ValueError(f"unknown rule direction {direction!r}")


def best_high_precision_rule(
    values: np.ndarray,
    y: np.ndarray,
    feature: str,
    direction: str,
) -> dict | None:
    unique = np.unique(values)
    if not len(unique):
        return None
    thresholds = unique.tolist()
    thresholds.append(float(np.nextafter(unique[0], -np.inf)))
    candidates = []
    seen_masks = set()
    for threshold in thresholds:
        selected = rule_mask(values, direction, float(threshold))
        signature = selected.tobytes()
        if signature in seen_masks:
            continue
        seen_masks.add(signature)
        selected_y = y[selected]
        if len(selected_y) < RULE_MIN_SELECTED:
            continue
        harmed = int((selected_y < 0.0).sum())
        benefited = int((selected_y > 0.0).sum())
        total = float(selected_y.sum())
        if harmed or benefited < RULE_MIN_BENEFITED or total <= 0.0:
            continue
        candidates.append(
            {
                "feature": feature,
                "direction": direction,
                "threshold": float(threshold),
                "train_selected": int(len(selected_y)),
                "train_benefited": benefited,
                "train_harmed": harmed,
                "train_total_uplift": total,
                "train_mean_uplift": float(selected_y.mean()),
            }
        )
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            row["train_mean_uplift"],
            row["train_total_uplift"],
            row["train_benefited"],
            -row["train_selected"],
            -row["threshold"],
        ),
    )


def rule_predictions(
    rows: list[dict], feature: str | None = None, direction: str | None = None
) -> tuple[np.ndarray, list[dict]]:
    y = np.asarray([row["margin_delta"] for row in rows], dtype=float)
    groups = np.asarray([row["opponent_group"] for row in rows], dtype=object)
    episodes = np.asarray([row["episode_id"] for row in rows], dtype=np.int64)
    matrix = {
        name: np.asarray([row["rule_features"][name] for row in rows], dtype=float)
        for name in RULE_FEATURES
    }
    predictions = np.zeros(len(rows), dtype=float)
    folds = []
    for held_group in sorted(set(groups.tolist())):
        test = np.flatnonzero(groups == held_group)
        test_episodes = set(episodes[test].tolist())
        nominal_train = np.flatnonzero(groups != held_group)
        train = np.asarray(
            [index for index in nominal_train if int(episodes[index]) not in test_episodes],
            dtype=int,
        )
        axes = (
            [(feature, direction)]
            if feature is not None and direction is not None
            else [
                (candidate_feature, candidate_direction)
                for candidate_feature in RULE_FEATURES
                for candidate_direction in RULE_DIRECTIONS
            ]
        )
        candidates = []
        for candidate_feature, candidate_direction in axes:
            rule = best_high_precision_rule(
                matrix[candidate_feature][train],
                y[train],
                candidate_feature,
                candidate_direction,
            )
            if rule is not None:
                candidates.append(rule)
        selected_rule = (
            max(
                candidates,
                key=lambda row: (
                    row["train_mean_uplift"],
                    row["train_total_uplift"],
                    row["train_benefited"],
                    -row["train_selected"],
                    row["feature"],
                    row["direction"],
                ),
            )
            if candidates
            else None
        )
        if selected_rule is not None:
            predictions[test] = rule_mask(
                matrix[selected_rule["feature"]][test],
                selected_rule["direction"],
                selected_rule["threshold"],
            ).astype(float)
        folds.append(
            {
                "held_opponent_group": held_group,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "episode_purged_rows": int(len(nominal_train) - len(train)),
                "selected_rule": selected_rule,
            }
        )
    return predictions, folds


def high_precision_rule_report(
    rows: list[dict], outcome_delta: np.ndarray, groups: np.ndarray
) -> dict:
    per_axis = {}
    qualified = []
    for feature in RULE_FEATURES:
        for direction in RULE_DIRECTIONS:
            predictions, folds = rule_predictions(rows, feature, direction)
            metrics = policy_metrics(
                np.asarray([row["margin_delta"] for row in rows], dtype=float),
                outcome_delta,
                groups,
                predictions,
            )
            key = f"{feature}:{direction}"
            full_rule = best_high_precision_rule(
                np.asarray(
                    [row["rule_features"][feature] for row in rows], dtype=float
                ),
                np.asarray([row["margin_delta"] for row in rows], dtype=float),
                feature,
                direction,
            )
            per_axis[key] = {
                "metrics": metrics,
                "folds": folds,
                "full_fit_rule": full_rule,
            }
            if (
                metrics["selected_rows"] >= RULE_MIN_SELECTED
                and metrics["harmed_selected"] == 0
                and metrics["total_margin_uplift"] > 0.0
            ):
                qualified.append(key)
    selector_predictions, selector_folds = rule_predictions(rows)
    selector_metrics = policy_metrics(
        np.asarray([row["margin_delta"] for row in rows], dtype=float),
        outcome_delta,
        groups,
        selector_predictions,
    )
    return {
        "family": "one public feature, one train-fitted threshold, <= or >",
        "train_gate": {
            "minimum_selected": RULE_MIN_SELECTED,
            "minimum_benefited": RULE_MIN_BENEFITED,
            "maximum_harmed": 0,
            "minimum_total_uplift": "strictly positive",
        },
        "split": (
            "leave one opponent policy/name out; purge every overlapping episode; "
            "fit threshold only on remaining train rows"
        ),
        "opponent_identity_usage": (
            "grouping only; opponent identity is not a runtime feature"
        ),
        "per_axis": per_axis,
        "qualified_axis_algorithms": qualified,
        "nested_axis_selector": {
            "metrics": selector_metrics,
            "folds": selector_folds,
        },
        "verdict": (
            "candidate_exists" if qualified else "reject_no_qualified_public_rule"
        ),
    }


def export_tree(model: DecisionTreeRegressor, spec: ModelSpec) -> dict:
    tree = model.tree_
    leaf_values = [float(value[0][0]) for value in tree.value]
    rules = []

    def visit(node: int, conditions: list[str]) -> None:
        left = int(tree.children_left[node])
        right = int(tree.children_right[node])
        if left == right == -1:
            value = leaf_values[node]
            rules.append(
                {
                    "when": " and ".join(conditions) if conditions else "always",
                    "predicted_margin_delta": value,
                    "decision": "ADVANCE1" if value > 0.0 else "KEEP_BASE",
                    "samples": int(tree.n_node_samples[node]),
                }
            )
            return
        feature = FEATURES[int(tree.feature[node])]
        threshold = float(tree.threshold[node])
        visit(left, [*conditions, f"{feature} <= {threshold:.12g}"])
        visit(right, [*conditions, f"{feature} > {threshold:.12g}"])

    visit(0, [])
    children_left = [
        -2 if int(value) == -1 else int(value) for value in tree.children_left
    ]
    children_right = [
        -2 if int(value) == -1 else int(value) for value in tree.children_right
    ]
    used_original_indices = sorted(
        {int(value) for value in tree.feature if int(value) >= 0}
    )
    # The shared wire format requires at least one feature name even for a
    # constant tree.  A non-constant tree exports only features it actually
    # uses, avoiding needless runtime dependencies.
    if not used_original_indices:
        used_original_indices = [0]
    remap = {
        original: compact for compact, original in enumerate(used_original_indices)
    }
    feature_indices = [
        -2 if int(value) < 0 else remap[int(value)] for value in tree.feature
    ]
    # The direct runtime consumes the shared classifier-tree wire format.  A
    # leaf's 0/1 score is only a transport for the sign of its estimated value;
    # it is explicitly not claimed to be a calibrated probability.
    decision_scores = [1.0 if value > 0.0 else 0.0 for value in leaf_values]
    return {
        "schema": RUNTIME_SCHEMA,
        "checkpoint_step": CHECKPOINT_STEP,
        "action": "enable quantity-conserving step119 WHEAT advance capped at 1",
        "fallback": "KEEP_BASE",
        "decision_threshold": 0.5,
        "feature_names": [FEATURES[index] for index in used_original_indices],
        # No empirical min/max bounds: they would reject legitimate fresh-seed
        # states and silently collapse the policy to KEEP_BASE out of sample.
        "feature_bounds": {},
        "estimator": {
            "type": "DecisionTreeRegressor",
            "criterion": "squared_error",
            "max_depth": spec.max_depth,
            "min_samples_leaf": spec.min_samples_leaf,
            "random_state": SEED,
        },
        "children_left": children_left,
        "children_right": children_right,
        "feature_indices": feature_indices,
        "thresholds": [float(value) for value in tree.threshold],
        "positive_probabilities": decision_scores,
        "leaf_values": leaf_values,
        "node_samples": [int(value) for value in tree.n_node_samples],
        "leaf_rules": rules,
        "provenance": {
            "training_objective": "paired final-margin delta ADVANCE1 minus KEEP_BASE",
            "score_contract": (
                "positive_probabilities is a binary sign score for direct-wrapper "
                "compatibility, not a calibrated probability; leaf_values preserves "
                "the fitted expected margin delta"
            ),
        },
    }


def finite(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--reference-candidate", default="S09")
    parser.add_argument("--treatment-report", type=Path, required=True)
    parser.add_argument("--treatment-candidate", default="ADVANCE1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-output", type=Path)
    args = parser.parse_args()

    reference_report = json.loads(args.reference_report.read_text(encoding="utf-8"))
    treatment_report = json.loads(args.treatment_report.read_text(encoding="utf-8"))
    rows, treatment_telemetry = build_rows(
        reference_report,
        treatment_report,
        args.reference_candidate,
        args.treatment_candidate,
    )
    x_all, y, groups, episodes = arrays(rows)
    outcome_delta = np.asarray([row["outcome_delta"] for row in rows], dtype=float)
    eligible = np.asarray([bool(row["eligible"]) for row in rows], dtype=bool)
    eligible_indices = np.flatnonzero(eligible)
    x_fit = x_all[eligible]
    y_fit = y[eligible]
    groups_fit = groups[eligible]
    episodes_fit = episodes[eligible]

    def all_row_predictions(fit_predictions: np.ndarray) -> np.ndarray:
        result = np.zeros(len(rows), dtype=float)
        result[eligible_indices] = fit_predictions
        return result

    fixed = {}
    fixed_folds = {}
    if len(eligible_indices):
        for spec in SPECS:
            predicted_fit, folds = purged_logo_predictions(
                x_fit, y_fit, groups_fit, episodes_fit, spec
            )
            fixed_folds[spec.name] = folds
            fixed[spec.name] = policy_metrics(
                y, outcome_delta, groups, all_row_predictions(predicted_fit)
            )
        nested_fit, nested_folds = nested_predictions(
            x_fit, y_fit, groups_fit, episodes_fit
        )
        nested = all_row_predictions(nested_fit)
        full_selected_spec, full_selection_scores = choose_spec_inner(
            x_fit, y_fit, groups_fit, episodes_fit
        )
    else:
        for spec in SPECS:
            fixed_folds[spec.name] = []
            fixed[spec.name] = policy_metrics(
                y, outcome_delta, groups, np.zeros(len(rows), dtype=float)
            )
        nested = np.zeros(len(rows), dtype=float)
        nested_folds = []
        full_selected_spec = SPEC_BY_NAME["KEEP_BASE"]
        full_selection_scores = [
            {"spec": "KEEP_BASE", "mean_policy_uplift": 0.0, "selected_rows": 0}
        ]
    nested_metrics = policy_metrics(y, outcome_delta, groups, nested)

    runtime_tree = None
    if full_selected_spec.name != "KEEP_BASE":
        runtime_tree = export_tree(
            fit_model(full_selected_spec, x_fit, y_fit), full_selected_spec
        )

    distribution = Counter(str(int(value) if value.is_integer() else value) for value in y)
    eligible_distribution = Counter(
        str(int(value) if value.is_integer() else value) for value in y_fit
    )
    group_sizes = Counter(groups.tolist())
    always_uplift = policy_metrics(
        y, outcome_delta, groups, np.ones(len(y), dtype=float)
    )
    q3_predictions = np.asarray(
        [
            1.0 if row["eligible"] and row["q3_imitation_accept"] else 0.0
            for row in rows
        ],
        dtype=float,
    )
    q3_benchmark = policy_metrics(
        y, outcome_delta, groups, q3_predictions
    )
    public_rule_report = high_precision_rule_report(rows, outcome_delta, groups)
    nested_ci = nested_metrics["cluster_bootstrap"]["ci95"]
    enough_selected = nested_metrics["selected_rows"] >= max(8, len(group_sizes))
    if nested_metrics["mean_margin_uplift_per_game"] <= 0.0:
        verdict = "reject_no_positive_nested_uplift"
    elif not enough_selected or nested_ci[0] <= 0.0:
        verdict = "insufficient_evidence_experimental_only"
    else:
        verdict = "promote_value_gate"

    report = {
        "schema": "kaggriculture-wheat-timing-value-study-v1",
        "objective": "ADVANCE1 vs KEEP_BASE paired final-margin delta",
        "causal_scope": (
            "same seed/seat and exact opponent action tape; estimates the bounded "
            "timing residual on this replay cohort, not arbitrary policy changes"
        ),
        "inputs": {
            "reference_report": str(args.reference_report),
            "reference_sha256": sha256(args.reference_report),
            "reference_candidate": args.reference_candidate,
            "treatment_report": str(args.treatment_report),
            "treatment_sha256": sha256(args.treatment_report),
            "treatment_candidate": args.treatment_candidate,
        },
        "dataset": {
            **treatment_telemetry,
            "unique_episodes": int(len(set(episodes.tolist()))),
            "opponent_groups": int(len(group_sizes)),
            "opponent_group_sizes": dict(sorted(group_sizes.items())),
            "delta_distribution": dict(sorted(distribution.items())),
            "eligible_delta_distribution": dict(sorted(eligible_distribution.items())),
            "positive_rows": int((y > 0).sum()),
            "neutral_rows": int((y == 0).sum()),
            "negative_rows": int((y < 0).sum()),
            "mean_treatment_delta": finite(float(y.mean())),
            "minimum_delta": finite(float(y.min())),
            "maximum_delta": finite(float(y.max())),
            "training_rows": int(eligible.sum()),
            "training_opponent_groups": int(len(set(groups_fit.tolist()))),
        },
        "feature_contract": {
            "checkpoint_step": CHECKPOINT_STEP,
            "features": list(FEATURES),
            "public_only": True,
            "coordinate_free": True,
            "private_storage_excluded": True,
        },
        "validation": {
            "outer_split": (
                "leave-one-opponent-submission-out where inferable from top10 cases; "
                "otherwise leave-one-opponent-name-out"
            ),
            "purge": "remove all training rows sharing an episode with the test fold",
            "model_selection": "nested purged leave-one-opponent-name-out",
            "identity_limitation": (
                "public replay metadata has opponent names but no direct opponent "
                "submission ids; ids are recovered only when that name is also a "
                "top10 target, otherwise a name is treated as one complete policy"
            ),
            "fixed_models": fixed,
            "fixed_folds": fixed_folds,
            "nested_model_selection": {
                "metrics": nested_metrics,
                "folds": nested_folds,
            },
            "always_advance_control": always_uplift,
            "q3_direct_benchmark": {
                "metrics": q3_benchmark,
                "rule": (
                    "opponent_money > 20.5 OR (opponent_money <= 20.5 AND "
                    "market_inventory_WOOL <= 9985)"
                ),
                "warning": (
                    "comparison only: this imitation rule was selected on the same "
                    "replay corpus and is not an honest holdout estimate"
                ),
            },
            "preregistered_high_precision_rules": public_rule_report,
        },
        "full_data_model_selection": {
            "selected_spec": full_selected_spec.name,
            "scores": full_selection_scores,
            "note": (
                "used only to construct a deployable full-fit tree; rely on nested outer "
                "metrics for an honest performance estimate"
            ),
        },
        "runtime_tree": runtime_tree,
        "verdict": verdict,
        "transfer_protocol": (
            "S22/S23 hard-negative episodes were not read by this trainer and remain "
            "untouched for a one-time transfer gate"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if args.runtime_output and runtime_tree is not None:
        args.runtime_output.parent.mkdir(parents=True, exist_ok=True)
        args.runtime_output.write_text(
            json.dumps(runtime_tree, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "rows": len(rows),
                "groups": len(group_sizes),
                "delta_distribution": dict(sorted(distribution.items())),
                "always_advance": always_uplift,
                "q3_direct_benchmark": q3_benchmark,
                "public_rule_verdict": public_rule_report["verdict"],
                "qualified_public_rules": public_rule_report[
                    "qualified_axis_algorithms"
                ],
                "public_rule_selector": public_rule_report[
                    "nested_axis_selector"
                ]["metrics"],
                "nested": nested_metrics,
                "full_selected_spec": full_selected_spec.name,
                "verdict": verdict,
                "report": str(args.output),
                "runtime": str(args.runtime_output) if runtime_tree else None,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
