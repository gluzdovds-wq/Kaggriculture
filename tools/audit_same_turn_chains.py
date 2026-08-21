"""Audit co-located same-turn dependency chains in official Kaggriculture games."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena import resolve_agent

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


BUILD_FOR_ANIMAL = {
    "GOOSE": "BUILD_COOP",
    "COW": "BUILD_BARN",
    "SHEEP": "BUILD_BARN",
}


def get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def classify(first: list, second: list, tile) -> str | None:
    if not first or not second:
        return None
    op1, op2 = first[0], second[0]
    if op1 == "PLANT" and op2 == "WATER" and tile is None:
        return "PLANT→WATER"
    if (
        op1 == "HARVEST"
        and op2 == "PLANT"
        and isinstance(tile, dict)
        and int(tile.get("yield_units", 0) or 0) > 0
    ):
        return "HARVEST→PLANT"
    if op2 == "PLACE" and len(second) >= 2 and BUILD_FOR_ANIMAL.get(second[1]) == op1:
        return f"{op1}→PLACE_{second[1]}"
    return None


def audit(env, seat: int) -> list[dict]:
    events = []
    for step in range(len(env.steps) - 1):
        observation = env.steps[step][seat].observation
        farm = list(get(observation, "farms", []) or [])[seat]
        tiles = list(get(farm, "tiles", []) or [])
        positions = [get(farm, "farmer"), *list(get(farm, "hands", []) or [])]
        action = env.steps[step + 1][seat].action or {}
        actions = [action.get("farmer") or ["PASS"], *list(action.get("hands") or [])]
        for first_index in range(min(len(positions), len(actions))):
            position = positions[first_index]
            if not position:
                continue
            x, y = map(int, position[:2])
            tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles) else None
            for second_index in range(first_index + 1, min(len(positions), len(actions))):
                if list(positions[second_index] or [])[:2] != list(position)[:2]:
                    continue
                label = classify(list(actions[first_index]), list(actions[second_index]), tile)
                if label:
                    events.append(
                        {
                            "step": step,
                            "day": int(get(observation, "day", 0) or 0),
                            "hour": int(get(observation, "hour", 0) or 0),
                            "position": [x, y],
                            "first_actor": first_index,
                            "second_actor": second_index,
                            "first_action": list(actions[first_index]),
                            "second_action": list(actions[second_index]),
                            "chain": label,
                        }
                    )
    return events


def play(candidate_spec: str, opponent_spec: str, seed: int, seat: int) -> dict:
    candidate, _, _ = resolve_agent(candidate_spec, f"chain_candidate_{seed}_{seat}")
    opponent, _, _ = resolve_agent(opponent_spec, f"chain_opponent_{seed}_{seat}")
    players = [candidate, opponent] if seat == 0 else [opponent, candidate]
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)
    events = audit(env, seat)
    final = env.steps[-1]
    return {
        "seed": seed,
        "seat": seat,
        "candidate_bank": final[seat].reward,
        "counts": dict(Counter(event["chain"] for event in events)),
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("opponent")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    matches = [
        play(args.candidate, args.opponent, seed, seat)
        for seed in range(args.seed, args.seed + args.seeds)
        for seat in (0, 1)
    ]
    report = {
        "candidate": args.candidate,
        "opponent": args.opponent,
        "seed_start": args.seed,
        "seed_count": args.seeds,
        "matches": matches,
        "total_counts": dict(
            Counter(
                event["chain"]
                for match in matches
                for event in match["events"]
            )
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
