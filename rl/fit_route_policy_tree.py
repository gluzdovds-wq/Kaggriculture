"""Fit a tiny full-feedback contextual-bandit tree for H22 route choice.

The input reports must evaluate fixed ``x544`` and ``moon`` variants on the
same opponents, seeds and seats.  Their step-1 observations are valid online
features because the routes share step 0.  Each public family therefore gives
complete feedback for both macro actions; the fitted tree never sees private
opponent state or future shop information.

This deliberately fits only a depth-one policy.  With a small public family
pool, a deeper tree would memorize notebook lineages instead of learning a
robust behavioral split.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROUTES = ("x544", "moon")


def checkpoint_one(match: dict) -> dict:
    for row in match.get("opponent_public_checkpoints", []):
        if int(row.get("step", -1)) == 1:
            return row["opponent"]
    raise ValueError("arena report lacks opponent step-1 checkpoint")


def feature_vector(signature: dict) -> dict[str, float]:
    tile_kinds = signature.get("tile_kinds", {}) or {}
    crops = signature.get("crops", {}) or {}
    animals = signature.get("animals", {}) or {}
    farmer = signature.get("farmer", []) or []
    features = {
        "money": float(signature.get("money", 0) or 0),
        "hands": float(len(signature.get("hands", []) or [])),
        "unlocked": float(len(signature.get("unlocked_quadrants", []) or [])),
        "farmer_x": float(farmer[0] if len(farmer) > 0 else -1),
        "farmer_y": float(farmer[1] if len(farmer) > 1 else -1),
        "plants": float(tile_kinds.get("PLANT", 0) or 0),
        "pastures": float(tile_kinds.get("PASTURE", 0) or 0),
        "coops": float(tile_kinds.get("COOP", 0) or 0),
        "weeds": float(tile_kinds.get("WEED", 0) or 0),
    }
    for crop in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"):
        features[f"crop_{crop.lower()}"] = float(crops.get(crop, 0) or 0)
    for animal in ("GOOSE", "SHEEP", "COW"):
        features[f"animal_{animal.lower()}"] = float(animals.get(animal, 0) or 0)
    return features


def mean(values: Iterable[float]) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0.0


def route_metrics(payload: dict, opponent: str) -> dict[str, float]:
    rows = payload["opponents"][opponent]["matches"]
    return {
        "outcome": mean(float(row["outcome"]) for row in rows),
        "margin": mean(float(row["margin"]) for row in rows),
    }


def utility(metrics: dict[str, float]) -> float:
    # Outcome is the competition objective.  A tiny bounded margin term only
    # resolves exact outcome ties and cannot overturn one match outcome.
    return metrics["outcome"] + 0.000001 * max(-20_000.0, min(20_000.0, metrics["margin"]))


@dataclass(frozen=True)
class Family:
    name: str
    features: dict[str, float]
    metrics: dict[str, dict[str, float]]

    def best_route(self) -> str:
        return max(ROUTES, key=lambda route: (self.metrics[route]["outcome"], self.metrics[route]["margin"]))


def load_families(x_path: Path, moon_path: Path) -> list[Family]:
    reports = {
        "x544": json.loads(x_path.read_text(encoding="utf-8")),
        "moon": json.loads(moon_path.read_text(encoding="utf-8")),
    }
    x_names = set(reports["x544"]["opponents"])
    moon_names = set(reports["moon"]["opponents"])
    if x_names != moon_names:
        raise ValueError("route reports have different opponent sets")
    families = []
    for name in sorted(x_names):
        x_rows = reports["x544"]["opponents"][name]["matches"]
        moon_rows = reports["moon"]["opponents"][name]["matches"]
        x_keys = [(row["seed"], row["candidate_seat"]) for row in x_rows]
        moon_keys = [(row["seed"], row["candidate_seat"]) for row in moon_rows]
        if x_keys != moon_keys:
            raise ValueError(f"route reports are not paired for {name}")
        x_features = [feature_vector(checkpoint_one(row)) for row in x_rows]
        moon_features = [feature_vector(checkpoint_one(row)) for row in moon_rows]
        if x_features != moon_features:
            raise ValueError(f"step-1 contexts differ before route choice for {name}")
        first = x_features[0]
        if any(row != first for row in x_features[1:]):
            raise ValueError(f"step-1 feature is seed/seat-dependent for {name}")
        metrics = {route: route_metrics(reports[route], name) for route in ROUTES}
        families.append(Family(name=name, features=first, metrics=metrics))
    return families


def leaf_route(families: list[Family]) -> str:
    return max(
        ROUTES,
        key=lambda route: sum(utility(family.metrics[route]) for family in families),
    )


def split_candidates(families: list[Family]):
    for feature in sorted(families[0].features):
        values = sorted({family.features[feature] for family in families})
        for left, right in zip(values, values[1:]):
            yield feature, (left + right) / 2.0


def fit_stump(families: list[Family]) -> dict:
    if not families:
        raise ValueError("cannot fit an empty family set")
    fallback = leaf_route(families)
    best = {
        "kind": "constant",
        "route": fallback,
        "training_utility": sum(utility(f.metrics[fallback]) for f in families),
    }
    for feature, threshold in split_candidates(families):
        left = [family for family in families if family.features[feature] <= threshold]
        right = [family for family in families if family.features[feature] > threshold]
        if not left or not right:
            continue
        left_route = leaf_route(left)
        right_route = leaf_route(right)
        score = sum(utility(f.metrics[left_route]) for f in left) + sum(
            utility(f.metrics[right_route]) for f in right
        )
        candidate = {
            "kind": "stump",
            "feature": feature,
            "threshold": threshold,
            "left_route": left_route,
            "right_route": right_route,
            "training_utility": score,
        }
        if score > best["training_utility"] + 1e-12:
            best = candidate
    return best


def predict(model: dict, features: dict[str, float]) -> str:
    if model["kind"] == "constant":
        return model["route"]
    return (
        model["left_route"]
        if features[model["feature"]] <= model["threshold"]
        else model["right_route"]
    )


def evaluate(model: dict, families: list[Family]) -> dict:
    rows = []
    for family in families:
        predicted = predict(model, family.features)
        best = family.best_route()
        best_outcome = max(family.metrics[route]["outcome"] for route in ROUTES)
        predicted_outcome = family.metrics[predicted]["outcome"]
        rows.append(
            {
                "family": family.name,
                "predicted": predicted,
                "best": best,
                "correct": predicted == best,
                "outcome_optimal": math.isclose(predicted_outcome, best_outcome),
                "outcome_regret": best_outcome - predicted_outcome,
                "features": family.features,
                "metrics": family.metrics,
            }
        )
    return {
        "exact_route_accuracy": mean(float(row["correct"]) for row in rows),
        "outcome_optimal_rate": mean(float(row["outcome_optimal"]) for row in rows),
        "mean_outcome_regret": mean(float(row["outcome_regret"]) for row in rows),
        "rows": rows,
    }


def leave_one_family_out(families: list[Family]) -> dict:
    rows = []
    for held in families:
        train = [family for family in families if family.name != held.name]
        model = fit_stump(train)
        predicted = predict(model, held.features)
        best_outcome = max(held.metrics[route]["outcome"] for route in ROUTES)
        predicted_outcome = held.metrics[predicted]["outcome"]
        rows.append(
            {
                "held_out": held.name,
                "predicted": predicted,
                "best": held.best_route(),
                "correct": predicted == held.best_route(),
                "outcome_optimal": math.isclose(predicted_outcome, best_outcome),
                "outcome_regret": best_outcome - predicted_outcome,
                "model": model,
            }
        )
    return {
        "exact_route_accuracy": mean(float(row["correct"]) for row in rows),
        "outcome_optimal_rate": mean(float(row["outcome_optimal"]) for row in rows),
        "mean_outcome_regret": mean(float(row["outcome_regret"]) for row in rows),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x544", type=Path, required=True)
    parser.add_argument("--moon", type=Path, required=True)
    parser.add_argument(
        "--model",
        type=Path,
        help="evaluate the model from an earlier report instead of refitting",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    families = load_families(args.x544, args.moon)
    if args.model:
        model = json.loads(args.model.read_text(encoding="utf-8"))["model"]
        mode = "external_holdout"
    else:
        model = fit_stump(families)
        mode = "fit"
    report = {
        "algorithm": "full-feedback contextual-bandit policy stump",
        "mode": mode,
        "observation_step": 1,
        "routes": list(ROUTES),
        "model": model,
        "evaluation": evaluate(model, families),
    }
    if not args.model:
        report["leave_one_family_out"] = leave_one_family_out(families)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
