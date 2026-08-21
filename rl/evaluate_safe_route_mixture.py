"""Evaluate safe stochastic mixtures at the compatible H22 route branch.

The X544 and Moon policies share the opening state at the route decision, so
their paired arena reports provide full feedback for both macro actions.  This
tool compares the deterministic pasture selector with a 95/5 flip and fits a
small robust mixture on training families.  It never randomizes low-level unit
actions and never assumes that shadow state repairs an incompatible farm.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rl.fit_route_policy_tree import Family, load_families, mean


def selector_moon_probability(family: Family) -> float:
    return 1.0 if family.features.get("pastures", 0.0) > 0.0 else 0.0


def evaluate_mixture(
    families: list[Family],
    *,
    no_pasture_moon_probability: float,
    pasture_moon_probability: float,
) -> dict:
    for value in (no_pasture_moon_probability, pasture_moon_probability):
        if not 0.0 <= value <= 1.0:
            raise ValueError("mixture probabilities must be in [0, 1]")
    rows = []
    for family in families:
        has_pasture = family.features.get("pastures", 0.0) > 0.0
        moon_probability = (
            pasture_moon_probability if has_pasture
            else no_pasture_moon_probability
        )
        x_probability = 1.0 - moon_probability
        expected_outcome = (
            x_probability * family.metrics["x544"]["outcome"]
            + moon_probability * family.metrics["moon"]["outcome"]
        )
        expected_margin = (
            x_probability * family.metrics["x544"]["margin"]
            + moon_probability * family.metrics["moon"]["margin"]
        )
        best_outcome = max(
            family.metrics["x544"]["outcome"],
            family.metrics["moon"]["outcome"],
        )
        rows.append({
            "family": family.name,
            "has_opening_pasture": has_pasture,
            "moon_probability": moon_probability,
            "expected_outcome": expected_outcome,
            "expected_margin": expected_margin,
            "outcome_regret": best_outcome - expected_outcome,
            "route_metrics": family.metrics,
        })
    return {
        "no_pasture_moon_probability": no_pasture_moon_probability,
        "pasture_moon_probability": pasture_moon_probability,
        "mean_expected_outcome": mean(row["expected_outcome"] for row in rows),
        "worst_family_expected_outcome": min(
            row["expected_outcome"] for row in rows
        ),
        "mean_expected_margin": mean(row["expected_margin"] for row in rows),
        "mean_outcome_regret": mean(row["outcome_regret"] for row in rows),
        "rows": rows,
    }


def policy_suite(families: list[Family], fitted: dict | None = None) -> dict:
    policies = {
        "deterministic_h22": (0.0, 1.0),
        "flip_05": (0.05, 0.95),
        "uniform": (0.5, 0.5),
    }
    if fitted is not None:
        policies["train_robust"] = (
            fitted["no_pasture_moon_probability"],
            fitted["pasture_moon_probability"],
        )
    return {
        name: evaluate_mixture(
            families,
            no_pasture_moon_probability=no_pasture,
            pasture_moon_probability=pasture,
        )
        for name, (no_pasture, pasture) in policies.items()
    }


def fit_robust_mixture(families: list[Family], step: float = 0.05) -> dict:
    if not families:
        raise ValueError("cannot fit an empty family set")
    if not 0.0 < step <= 1.0:
        raise ValueError("grid step must be in (0, 1]")
    count = round(1.0 / step)
    if abs(count * step - 1.0) > 1e-9:
        raise ValueError("grid step must divide 1 exactly")
    best = None
    best_key = None
    for no_index in range(count + 1):
        for pasture_index in range(count + 1):
            report = evaluate_mixture(
                families,
                no_pasture_moon_probability=no_index * step,
                pasture_moon_probability=pasture_index * step,
            )
            key = (
                report["worst_family_expected_outcome"],
                report["mean_expected_outcome"],
                report["mean_expected_margin"],
            )
            if best_key is None or key > best_key:
                best_key = key
                best = report
    assert best is not None
    return best


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x544", type=Path, required=True)
    parser.add_argument("--moon", type=Path, required=True)
    parser.add_argument("--holdout-x544", type=Path)
    parser.add_argument("--holdout-moon", type=Path)
    parser.add_argument("--grid-step", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    train = load_families(args.x544, args.moon)
    fitted = fit_robust_mixture(train, args.grid_step)
    report = {
        "algorithm": "full-feedback safe macro route mixture",
        "route_branch_step": 1,
        "objective": "lexicographic worst-family outcome, mean outcome, margin",
        "grid_step": args.grid_step,
        "fitted": fitted,
        "train": policy_suite(train, fitted),
    }
    if bool(args.holdout_x544) != bool(args.holdout_moon):
        parser.error("provide both holdout route reports or neither")
    if args.holdout_x544 and args.holdout_moon:
        holdout = load_families(args.holdout_x544, args.holdout_moon)
        report["holdout"] = policy_suite(holdout, fitted)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
