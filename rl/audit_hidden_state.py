"""Audit the private-state gap a legal online search agent must model.

Replay JSON stores one observation per seat, so offline analysis can read the
opponent's private payload from the *other* seat.  This script uses that payload
only as an audit target.  Every reported public field is taken from the target
seat's legal observation, and shared-view equality is checked explicitly.

The gross hidden-value estimate marks products at current public sell prices,
stored animals at purchase cost and seeds at purchase cost.  It is a diagnostic
of missing state magnitude, not a liquidation value or a feature allowed at
live inference.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import fmean


PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
SEED_COST = {
    "WHEAT": 10,
    "CARROT": 20,
    "TOMATO": 50,
    "STRAWBERRY": 100,
    "MELON": 80,
}
# Replay JSON keeps ``step`` only on the leading shared observation even though
# the live framework supplies the resolved step to each agent.  The remaining
# shared fields are duplicated per seat and can be compared directly.
SHARED_KEYS = ("day", "hour", "farms", "market", "town")
SUMMARY_FIELDS = (
    "hidden_shed_units",
    "hidden_seed_units",
    "hidden_carried_units",
    "hidden_total_units",
    "hidden_gross_value",
    "hidden_nonzero_item_types",
)


def positive_counts(values) -> dict[str, int]:
    return {
        str(key).upper(): max(0, int(value or 0))
        for key, value in dict(values or {}).items()
        if int(value or 0) > 0
    }


def private_components(private) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    private = dict(private or {})
    shed = positive_counts(private.get("shed"))
    seeds = positive_counts(private.get("seeds"))
    carried = Counter()
    for inventory in private.get("inventories", []) or []:
        carried.update(positive_counts(inventory))
    return shed, seeds, dict(carried)


def hidden_metrics(private, prices) -> dict:
    shed, seeds, carried = private_components(private)
    prices = {str(key).upper(): int(value or 0) for key, value in dict(prices or {}).items()}
    combined = Counter(shed)
    combined.update(carried)
    product_value = sum(combined[item] * prices.get(item, 0) for item in PRODUCTS)
    animal_value = sum(combined[item] * cost for item, cost in ANIMAL_COST.items())
    seed_value = sum(seeds.get(item, 0) * cost for item, cost in SEED_COST.items())
    all_items = Counter(combined)
    all_items.update(seeds)
    return {
        "hidden_shed_units": sum(shed.values()),
        "hidden_seed_units": sum(seeds.values()),
        "hidden_carried_units": sum(carried.values()),
        "hidden_total_units": sum(shed.values()) + sum(seeds.values()) + sum(carried.values()),
        "hidden_gross_value": product_value + animal_value + seed_value,
        "hidden_nonzero_item_types": sum(value > 0 for value in all_items.values()),
        "hidden_shed": dict(sorted(shed.items())),
        "hidden_seeds": dict(sorted(seeds.items())),
        "hidden_carried": dict(sorted(carried.items())),
    }


def observation_at(replay: dict, checkpoint: int) -> list[dict]:
    steps = replay.get("steps", []) or []
    if checkpoint < len(steps):
        observations = [dict(row.get("observation", {}) or {}) for row in steps[checkpoint]]
        if observations and int(observations[0].get("step", -1)) == checkpoint:
            return observations
    for state in steps:
        observations = [dict(row.get("observation", {}) or {}) for row in state]
        if observations and int(observations[0].get("step", -1)) == checkpoint:
            return observations
    raise ValueError(f"replay lacks observation step {checkpoint}")


def shared_views_equal(left: dict, right: dict) -> bool:
    return all(left.get(key) == right.get(key) for key in SHARED_KEYS)


def extract_checkpoint_rows(replay: dict, checkpoints: tuple[int, ...]) -> list[dict]:
    info = dict(replay.get("info", {}) or {})
    episode_id = int(info.get("EpisodeId", 0) or 0)
    names = list(info.get("TeamNames", []) or [])
    rows = []
    for checkpoint in checkpoints:
        observations = observation_at(replay, checkpoint)
        if len(observations) != 2:
            raise ValueError(f"episode {episode_id} does not have two seats")
        if not shared_views_equal(observations[0], observations[1]):
            raise ValueError(f"episode {episode_id} shared views diverge at {checkpoint}")
        prices = (observations[0].get("market", {}) or {}).get("prices", {}) or {}
        for target_seat in (0, 1):
            opponent_seat = 1 - target_seat
            target = observations[target_seat]
            hidden = hidden_metrics(observations[opponent_seat].get("private"), prices)
            farms = target.get("farms", []) or []
            row = {
                "episode_id": episode_id,
                "checkpoint": checkpoint,
                "target_seat": target_seat,
                "target_name": names[target_seat] if target_seat < len(names) else "",
                "opponent_name": names[opponent_seat] if opponent_seat < len(names) else "",
                "public_target_money": float(farms[target_seat].get("money", 0) or 0),
                "public_opponent_money": float(farms[opponent_seat].get("money", 0) or 0),
                "public_shop_count": len((target.get("town", {}) or {}).get("unlocked_shops", []) or []),
                "replay_seed_present_offline": info.get("seed") is not None,
                "observation_seed_present": "seed" in target,
            }
            row.update(hidden)
            rows.append(row)
    return rows


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return float(ordered[index])


def distribution(values) -> dict:
    values = [float(value) for value in values]
    return {
        "count": len(values),
        "mean": fmean(values) if values else 0.0,
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "max": max(values, default=0.0),
        "fraction_nonzero": (
            sum(value > 0 for value in values) / len(values) if values else 0.0
        ),
    }


def summarize(rows: list[dict], replay_count: int, checkpoints: tuple[int, ...]) -> dict:
    by_checkpoint = defaultdict(list)
    for row in rows:
        by_checkpoint[int(row["checkpoint"])].append(row)
    checkpoint_summary = {}
    for checkpoint in checkpoints:
        selected = by_checkpoint[checkpoint]
        item_presence = Counter()
        for row in selected:
            keys = set(row["hidden_shed"]) | set(row["hidden_seeds"]) | set(row["hidden_carried"])
            item_presence.update(keys)
        checkpoint_summary[str(checkpoint)] = {
            "seat_cases": len(selected),
            "metrics": {
                field: distribution(row[field] for row in selected)
                for field in SUMMARY_FIELDS
            },
            "item_presence_fraction": {
                item: count / len(selected) for item, count in sorted(item_presence.items())
            } if selected else {},
            "largest_hidden_cases": [
                {
                    key: row[key]
                    for key in (
                        "episode_id",
                        "target_seat",
                        "target_name",
                        "opponent_name",
                        "hidden_total_units",
                        "hidden_gross_value",
                    )
                }
                for row in sorted(
                    selected,
                    key=lambda value: (value["hidden_gross_value"], value["hidden_total_units"]),
                    reverse=True,
                )[:5]
            ],
        }
    return {
        "schema": "kaggriculture-hidden-state-audit-v1",
        "replay_count": replay_count,
        "checkpoints": list(checkpoints),
        "seat_case_count": len(rows),
        "shared_view_checks": len(rows) // 2,
        "shared_view_mismatches": 0,
        "source_seed_visibility": {
            "present_in_offline_replay_info_fraction": (
                sum(row["replay_seed_present_offline"] for row in rows) / len(rows)
                if rows else 0.0
            ),
            "present_in_legal_observation_fraction": (
                sum(row["observation_seed_present"] for row in rows) / len(rows)
                if rows else 0.0
            ),
        },
        "by_checkpoint": checkpoint_summary,
        "warning": (
            "Opponent private values are audit labels from the other seat's replay "
            "observation and are forbidden as live policy inputs."
        ),
    }


def replay_paths(values: list[Path]) -> list[Path]:
    paths = []
    for value in values:
        if value.is_dir():
            paths.extend(sorted(value.glob("*.json")))
        elif value.is_file():
            paths.append(value)
        else:
            raise FileNotFoundError(value)
    return sorted(set(path.resolve() for path in paths))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--checkpoint", action="append", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-rows", action="store_true")
    args = parser.parse_args()
    checkpoints = tuple(args.checkpoint or (72, 360, 648))
    if not checkpoints or any(value < 0 for value in checkpoints):
        parser.error("checkpoints must be non-negative")
    paths = replay_paths(args.replays)
    if not paths:
        parser.error("no replay JSON files found")
    rows = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            rows.extend(extract_checkpoint_rows(json.load(handle), checkpoints))
    report = summarize(rows, len(paths), checkpoints)
    if args.include_rows:
        report["rows"] = rows
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
