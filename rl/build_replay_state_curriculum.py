"""Build inference-visible rare-state strata from public ladder replays.

The curriculum keeps only observations available to our agent before its
recorded action.  It tags the largest relative-bank swings, simultaneous market
collisions, terminal market decisions and high-storage states.  These strata
are intended for masked macro best-response rollouts, not for reconstructing
opponent-private memory or training an unrestricted low-level policy.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rl.build_macro_imitation_dataset import feature_vector, macro_label, operation


def farm_money(observation: dict, seat: int) -> float:
    farms = list(observation.get("farms", []) or [])
    return float(farms[seat].get("money", 0) or 0)


def market_summary(action: dict | None) -> dict:
    counts = Counter()
    quantities = Counter()
    for order in (action or {}).get("market", []) or []:
        op = operation(order)
        counts[op] += 1
        item = str(order[1]).upper() if len(order) > 1 else ""
        quantity = int(order[2]) if len(order) > 2 and isinstance(order[2], (int, float)) else 1
        if item:
            quantities[f"{op}:{item}"] += quantity
    return {
        "operations": dict(sorted(counts.items())),
        "quantities": dict(sorted(quantities.items())),
    }


def collect_episode(payload: dict, own_name: str, top_k: int) -> dict:
    info = payload.get("info", {})
    names = list(info.get("TeamNames", []) or [])
    if names.count(own_name) != 1 or len(names) != 2:
        raise ValueError(f"cannot identify {own_name!r} exactly once")
    seat = names.index(own_name)
    opponent_seat = 1 - seat
    episode_id = int(info.get("EpisodeId"))
    rewards = list(payload.get("rewards", []) or [])
    steps = payload.get("steps", [])
    rows = []
    totals = {"candidate": Counter(), "opponent": Counter()}
    for index in range(1, len(steps)):
        previous = steps[index - 1][seat]["observation"]
        current = steps[index][seat]["observation"]
        candidate_action = steps[index][seat].get("action") or {}
        opponent_action = steps[index][opponent_seat].get("action") or {}
        gap_before = farm_money(previous, seat) - farm_money(previous, opponent_seat)
        gap_after = farm_money(current, seat) - farm_money(current, opponent_seat)
        candidate_market = market_summary(candidate_action)
        opponent_market = market_summary(opponent_action)
        totals["candidate"].update(candidate_market["quantities"])
        totals["opponent"].update(opponent_market["quantities"])
        features = feature_vector(previous)
        rows.append({
            "episode_id": episode_id,
            "opponent_name": names[opponent_seat],
            "seed": int(info.get("seed")),
            "seat": seat,
            "step": index - 1,
            "gap_before": gap_before,
            "gap_after": gap_after,
            "gap_delta": gap_after - gap_before,
            "storage_pressure": features["shed_total"] + features["carried_total"],
            "features": features,
            "candidate_macro": macro_label(candidate_action),
            "opponent_macro": macro_label(opponent_action),
            "candidate_market": candidate_market,
            "opponent_market": opponent_market,
            "tags": [],
        })

    selected: dict[int, dict] = {}

    def add(tag: str, candidates: list[dict]) -> None:
        for row in candidates[:top_k]:
            target = selected.setdefault(row["step"], row)
            if tag not in target["tags"]:
                target["tags"].append(tag)

    add("negative_gap_swing", sorted(rows, key=lambda row: row["gap_delta"]))
    market_collisions = [
        row for row in rows
        if row["candidate_market"]["operations"] and row["opponent_market"]["operations"]
    ]
    add("market_collision", sorted(market_collisions, key=lambda row: row["gap_delta"]))
    terminal = [
        row for row in rows
        if row["step"] >= 672 and (
            row["candidate_market"]["operations"] or row["opponent_market"]["operations"]
        )
    ]
    add("terminal_market", sorted(terminal, key=lambda row: row["gap_delta"]))
    pressure = [row for row in rows if row["storage_pressure"] >= 90]
    add("storage_pressure", sorted(
        pressure, key=lambda row: (row["storage_pressure"], -row["gap_delta"]), reverse=True
    ))

    return {
        "episode_id": episode_id,
        "opponent_name": names[opponent_seat],
        "seed": int(info.get("seed")),
        "seat": seat,
        "recorded_candidate_bank": float(rewards[seat]),
        "recorded_opponent_bank": float(rewards[opponent_seat]),
        "recorded_margin": float(rewards[seat]) - float(rewards[opponent_seat]),
        "market_quantity_totals": {
            side: dict(sorted(counter.items())) for side, counter in totals.items()
        },
        "strata": [selected[step] for step in sorted(selected)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", action="append", type=Path, required=True)
    parser.add_argument("--own-name", required=True)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.top_k <= 0:
        parser.error("--top-k must be positive")

    episodes = [
        collect_episode(
            json.loads(path.read_text(encoding="utf-8")),
            args.own_name,
            args.top_k,
        )
        for path in args.replay
    ]
    tag_counts = Counter(
        tag for episode in episodes for row in episode["strata"] for tag in row["tags"]
    )
    report = {
        "schema": "inference-visible replay-state curriculum v1",
        "own_name": args.own_name,
        "episode_count": len(episodes),
        "row_count": sum(len(episode["strata"]) for episode in episodes),
        "tag_counts": dict(sorted(tag_counts.items())),
        "episodes": episodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "episode_count": report["episode_count"],
        "row_count": report["row_count"],
        "tag_counts": report["tag_counts"],
    }, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
