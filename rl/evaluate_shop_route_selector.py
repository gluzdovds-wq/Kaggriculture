"""Evaluate the N36 public shop-aware rule from paired fixed-route reports."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


ROUTES = ("x544", "moon")


def checkpoint(match: dict, step: int) -> dict:
    for row in match.get("opponent_public_checkpoints", []):
        if int(row.get("step", -1)) == step:
            return row.get("opponent", {}) or {}
    raise ValueError(f"arena report lacks opponent step-{step} checkpoint")


def opening_pasture(match: dict) -> bool:
    signature = checkpoint(match, 1)
    kinds = signature.get("tile_kinds", {}) or {}
    return int(kinds.get("PASTURE", 0) or 0) > 0


def first_shops(match: dict) -> tuple[str, ...]:
    for row in match.get("shop_unlock_events", []):
        if int(row.get("step", -1)) == 72:
            values = row.get("new_shops", []) or []
            if isinstance(values, str):
                values = [values]
            return tuple(str(value).upper().split(".")[-1] for value in values)
    raise ValueError("arena report lacks step-72 shop event")


def n36_route(has_pasture: bool, shops: tuple[str, ...]) -> str:
    return "x544" if (not has_pasture or "YARN_STORE" in shops) else "moon"


def paired_rows(x_report: dict, moon_report: dict) -> list[dict]:
    if set(x_report.get("opponents", {})) != set(moon_report.get("opponents", {})):
        raise ValueError("route reports have different opponent sets")
    rows = []
    for family in x_report["opponents"]:
        x_matches = x_report["opponents"][family]["matches"]
        moon_matches = moon_report["opponents"][family]["matches"]
        x_by_key = {(row["seed"], row["candidate_seat"]): row for row in x_matches}
        moon_by_key = {
            (row["seed"], row["candidate_seat"]): row for row in moon_matches
        }
        if set(x_by_key) != set(moon_by_key):
            raise ValueError(f"route reports are not paired for {family}")
        for seed, seat in sorted(x_by_key):
            route_matches = {"x544": x_by_key[(seed, seat)], "moon": moon_by_key[(seed, seat)]}
            contexts = {
                route: (opening_pasture(match), first_shops(match))
                for route, match in route_matches.items()
            }
            if contexts["x544"] != contexts["moon"]:
                raise ValueError(f"predecision contexts differ for {family} seed={seed} seat={seat}")
            has_pasture, shops = contexts["x544"]
            predicted = n36_route(has_pasture, shops)
            metrics = {
                route: {
                    "outcome": float(match["outcome"]),
                    "margin": float(match["margin"]),
                }
                for route, match in route_matches.items()
            }
            best_outcome = max(metrics[route]["outcome"] for route in ROUTES)
            best_route = max(
                ROUTES,
                key=lambda route: (metrics[route]["outcome"], metrics[route]["margin"]),
            )
            rows.append(
                {
                    "family": family,
                    "seed": seed,
                    "seat": seat,
                    "opening_pasture": has_pasture,
                    "first_shops": list(shops),
                    "predicted": predicted,
                    "best_route": best_route,
                    "outcome_optimal": metrics[predicted]["outcome"] == best_outcome,
                    "outcome_regret": best_outcome - metrics[predicted]["outcome"],
                    "metrics": metrics,
                }
            )
    return rows


def summary(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("cannot summarize an empty report")
    shop_groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        shop_groups["+".join(row["first_shops"]) or "NONE"].append(row)

    def mean(values):
        values = list(values)
        return sum(values) / len(values)

    return {
        "matches": len(rows),
        "outcome_optimal_rate": mean(float(row["outcome_optimal"]) for row in rows),
        "mean_outcome_regret": mean(row["outcome_regret"] for row in rows),
        "exact_margin_tiebreak_accuracy": mean(
            float(row["predicted"] == row["best_route"]) for row in rows
        ),
        "mean_predicted_outcome": mean(
            row["metrics"][row["predicted"]]["outcome"] for row in rows
        ),
        "mean_fixed_x544_outcome": mean(row["metrics"]["x544"]["outcome"] for row in rows),
        "mean_fixed_moon_outcome": mean(row["metrics"]["moon"]["outcome"] for row in rows),
        "by_first_shop": {
            shop: {
                "matches": len(group),
                "outcome_optimal_rate": mean(float(row["outcome_optimal"]) for row in group),
                "mean_outcome_regret": mean(row["outcome_regret"] for row in group),
            }
            for shop, group in sorted(shop_groups.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x544", type=Path, action="append", required=True)
    parser.add_argument("--moon", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.x544) != len(args.moon):
        parser.error("provide the same number of --x544 and --moon reports")
    rows = []
    pairs = []
    for x_path, moon_path in zip(args.x544, args.moon):
        x_report = json.loads(x_path.read_text(encoding="utf-8"))
        moon_report = json.loads(moon_path.read_text(encoding="utf-8"))
        pair_rows = paired_rows(x_report, moon_report)
        rows.extend(pair_rows)
        pairs.append({"x544": str(x_path), "moon": str(moon_path), "matches": len(pair_rows)})
    report = {
        "algorithm": "full-feedback N36 public shop-aware route evaluation",
        "rule": "x544 if no opening pasture or first shop is YARN_STORE; moon otherwise",
        "pairs": pairs,
        "summary": summary(rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
