"""Fit a tiny public-state route selector from exact replay counterfactuals.

The two route candidates must share the complete prefix through ``--step``.
Each report supplies full feedback for both continuations on the same episode,
seed and seat.  Only the public context recorded by :mod:`arena` is used as a
feature; opponent names, ranks, replay ids and future observations are never
included.

The model is deliberately limited to one split.  Outcome is optimized
lexicographically before clipped coin margin, and ties prefer the Moon default
so that a split cannot be justified only by needless X544 exposure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROUTES = ("x544", "moon")
PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "FERTILIZER",
    "EGG",
    "WOOL",
    "MILK",
)


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("holdout must be NAME=PATH")
    name, raw_path = value.split("=", 1)
    path = Path(raw_path)
    if not name or not path.is_file():
        raise ValueError(f"invalid holdout {value!r}")
    return name, path


def row_key(row: dict) -> tuple[int, int]:
    seat = row.get("candidate_seat", row.get("target_seat"))
    if seat is None:
        raise ValueError("match lacks candidate_seat/target_seat")
    return int(row["episode_id"]), int(seat)


def public_checkpoint(match: dict, step: int) -> dict:
    rows = [
        row
        for row in match.get("public_context_checkpoints", [])
        if int(row.get("step", -1)) == step
    ]
    if len(rows) != 1:
        raise ValueError(f"match {row_key(match)} lacks unique public step-{step} context")
    return rows[0]


def farm_features(prefix: str, signature: dict) -> dict[str, float]:
    farmer = list(signature.get("farmer", []) or [])
    values = {
        f"{prefix}.money": float(signature.get("money", 0) or 0),
        f"{prefix}.hands": float(len(signature.get("hands", []) or [])),
        f"{prefix}.hires_today": float(signature.get("hires_today", 0) or 0),
        f"{prefix}.unlocked": float(
            len(signature.get("unlocked_quadrants", []) or [])
        ),
        f"{prefix}.farmer_x": float(farmer[0] if len(farmer) > 0 else -1),
        f"{prefix}.farmer_y": float(farmer[1] if len(farmer) > 1 else -1),
    }
    for group in ("tile_kinds", "crops", "animals"):
        for name, value in sorted((signature.get(group, {}) or {}).items()):
            values[f"{prefix}.{group}.{str(name).upper()}"] = float(value or 0)
    return values


def feature_vector(context: dict) -> dict[str, float]:
    features = {}
    candidate = farm_features("candidate", context.get("candidate", {}) or {})
    opponent = farm_features("opponent", context.get("opponent", {}) or {})
    features.update(candidate)
    features.update(opponent)
    suffixes = sorted(
        {name.split(".", 1)[1] for name in candidate}
        & {name.split(".", 1)[1] for name in opponent}
    )
    for suffix in suffixes:
        features[f"delta.{suffix}"] = (
            candidate[f"candidate.{suffix}"] - opponent[f"opponent.{suffix}"]
        )
    shops = {
        str(value).upper().split(".")[-1]
        for value in (context.get("shops", []) or [])
    }
    for shop in sorted(shops):
        features[f"shop.{shop}"] = 1.0
    inventory = context.get("market_inventory", {}) or {}
    prices = context.get("market_prices", {}) or {}
    for product in PRODUCTS:
        features[f"market_inventory.{product}"] = float(inventory.get(product, 0) or 0)
        features[f"market_price.{product}"] = float(prices.get(product, 0) or 0)
    return features


def candidate_matches(report: dict, name: str) -> list[dict]:
    try:
        return list(report["candidates"][name]["matches"])
    except KeyError as error:
        raise ValueError(f"report lacks candidate {name!r}") from error


def paired_rows(
    report: dict, x_candidate: str, moon_candidate: str, step: int
) -> list[dict]:
    by_route = {
        "x544": {row_key(row): row for row in candidate_matches(report, x_candidate)},
        "moon": {row_key(row): row for row in candidate_matches(report, moon_candidate)},
    }
    if set(by_route["x544"]) != set(by_route["moon"]):
        raise ValueError("route candidates contain different episode/seat keys")
    rows = []
    for key in sorted(by_route["x544"]):
        matches = {route: by_route[route][key] for route in ROUTES}
        contexts = {route: public_checkpoint(matches[route], step) for route in ROUTES}
        if contexts["x544"] != contexts["moon"]:
            raise ValueError(f"route contexts diverge before decision for {key}")
        metrics = {
            route: {
                "outcome": float(matches[route]["outcome"]),
                "margin": float(matches[route]["margin"]),
            }
            for route in ROUTES
        }
        rows.append(
            {
                "key": list(key),
                "features": feature_vector(contexts["x544"]),
                "metrics": metrics,
            }
        )
    return rows


def clipped_margin(value: float) -> float:
    return max(-20_000.0, min(20_000.0, value))


def route_score(rows: list[dict], route: str) -> tuple[float, float, int]:
    return (
        sum(row["metrics"][route]["outcome"] for row in rows),
        sum(clipped_margin(row["metrics"][route]["margin"]) for row in rows),
        len(rows) if route == "moon" else 0,
    )


def leaf_route(rows: list[dict]) -> str:
    return max(ROUTES, key=lambda route: route_score(rows, route))


def model_score(rows: list[dict], choices: list[str]) -> tuple[float, float, int]:
    return (
        sum(row["metrics"][route]["outcome"] for row, route in zip(rows, choices)),
        sum(
            clipped_margin(row["metrics"][route]["margin"])
            for row, route in zip(rows, choices)
        ),
        sum(route == "moon" for route in choices),
    )


def feature_value(row: dict, feature: str) -> float:
    return float(row["features"].get(feature, 0.0))


def fit_stump(rows: list[dict], min_leaf: int) -> dict:
    if len(rows) < max(2, min_leaf * 2):
        raise ValueError("not enough rows for the requested minimum leaf")
    fallback = leaf_route(rows)
    best = {
        "kind": "constant",
        "route": fallback,
        "training_score": list(route_score(rows, fallback)),
    }
    features = sorted({name for row in rows for name in row["features"]})
    for feature in features:
        values = sorted({feature_value(row, feature) for row in rows})
        for low, high in zip(values, values[1:]):
            threshold = (low + high) / 2.0
            left = [row for row in rows if feature_value(row, feature) <= threshold]
            right = [row for row in rows if feature_value(row, feature) > threshold]
            if len(left) < min_leaf or len(right) < min_leaf:
                continue
            left_route = leaf_route(left)
            right_route = leaf_route(right)
            choices = [
                left_route if feature_value(row, feature) <= threshold else right_route
                for row in rows
            ]
            score = model_score(rows, choices)
            if score > tuple(best["training_score"]):
                best = {
                    "kind": "stump",
                    "feature": feature,
                    "threshold": threshold,
                    "left_route": left_route,
                    "right_route": right_route,
                    "left_rows": len(left),
                    "right_rows": len(right),
                    "training_score": list(score),
                }
    return best


def predict(model: dict, features: dict[str, float]) -> str:
    if model["kind"] == "constant":
        return model["route"]
    return (
        model["left_route"]
        if float(features.get(model["feature"], 0.0)) <= float(model["threshold"])
        else model["right_route"]
    )


def evaluate(model: dict, rows: list[dict]) -> dict:
    evaluated = []
    for row in rows:
        route = predict(model, row["features"])
        metrics = row["metrics"]
        evaluated.append(
            {
                "key": row["key"],
                "predicted": route,
                "feature_value": (
                    feature_value(row, model["feature"])
                    if model["kind"] == "stump"
                    else None
                ),
                "outcome": metrics[route]["outcome"],
                "margin": metrics[route]["margin"],
                "outcome_delta_vs_moon": (
                    metrics[route]["outcome"] - metrics["moon"]["outcome"]
                ),
                "margin_delta_vs_moon": (
                    metrics[route]["margin"] - metrics["moon"]["margin"]
                ),
                "metrics": metrics,
            }
        )
    count = len(evaluated)
    return {
        "games": count,
        "predicted_outcome": sum(row["outcome"] for row in evaluated),
        "predicted_average_margin": sum(row["margin"] for row in evaluated) / count,
        "fixed_x544_outcome": sum(
            row["metrics"]["x544"]["outcome"] for row in evaluated
        ),
        "fixed_moon_outcome": sum(
            row["metrics"]["moon"]["outcome"] for row in evaluated
        ),
        "oracle_outcome": sum(
            max(row["metrics"][route]["outcome"] for route in ROUTES)
            for row in evaluated
        ),
        "route_counts": {
            route: sum(row["predicted"] == route for row in evaluated)
            for route in ROUTES
        },
        "improvements_vs_moon": sum(
            row["outcome_delta_vs_moon"] > 0 for row in evaluated
        ),
        "regressions_vs_moon": sum(
            row["outcome_delta_vs_moon"] < 0 for row in evaluated
        ),
        "rows": evaluated,
    }


def leave_one_out(rows: list[dict], min_leaf: int) -> dict:
    evaluated = []
    for index, held in enumerate(rows):
        train = rows[:index] + rows[index + 1 :]
        model = fit_stump(train, min_leaf)
        route = predict(model, held["features"])
        evaluated.append(
            {
                "key": held["key"],
                "predicted": route,
                "outcome": held["metrics"][route]["outcome"],
                "moon_outcome": held["metrics"]["moon"]["outcome"],
            }
        )
    return {
        "games": len(evaluated),
        "predicted_outcome": sum(row["outcome"] for row in evaluated),
        "fixed_moon_outcome": sum(row["moon_outcome"] for row in evaluated),
        "route_counts": {
            route: sum(row["predicted"] == route for row in evaluated)
            for route in ROUTES
        },
    }


def load_rows(path: Path, x_candidate: str, moon_candidate: str, step: int) -> list[dict]:
    return paired_rows(
        json.loads(path.read_text(encoding="utf-8")),
        x_candidate,
        moon_candidate,
        step,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-report", action="append", type=Path, required=True)
    parser.add_argument("--holdout", action="append", default=[])
    parser.add_argument("--x-candidate", default="FIXED_X544")
    parser.add_argument("--moon-candidate", default="FIXED_MOON")
    parser.add_argument("--step", type=int, default=72)
    parser.add_argument("--min-leaf", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    train_rows = []
    for path in args.train_report:
        train_rows.extend(load_rows(path, args.x_candidate, args.moon_candidate, args.step))
    try:
        holdouts = dict(parse_named_path(value) for value in args.holdout)
    except ValueError as error:
        parser.error(str(error))
    model = fit_stump(train_rows, args.min_leaf)
    report = {
        "algorithm": "depth-one full-feedback public-state route tree",
        "decision_step": args.step,
        "min_leaf": args.min_leaf,
        "train_reports": [str(path) for path in args.train_report],
        "model": model,
        "train": evaluate(model, train_rows),
        "leave_one_out": leave_one_out(train_rows, args.min_leaf),
        "holdouts": {
            name: evaluate(
                model,
                load_rows(path, args.x_candidate, args.moon_candidate, args.step),
            )
            for name, path in holdouts.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "model": model,
                "train": {key: value for key, value in report["train"].items() if key != "rows"},
                "leave_one_out": report["leave_one_out"],
                "holdouts": {
                    name: {key: value for key, value in result.items() if key != "rows"}
                    for name, result in report["holdouts"].items()
                },
            },
            indent=2,
        )
    )
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
