"""Trace public weed pressure and executed DIG actions across one exact game."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena import resolve_agent

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def tile_counts(farm) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in get(farm, "tiles", []) or []:
        for tile in row or []:
            if tile is None:
                counts["EMPTY"] += 1
                continue
            if tile == "LOCKED":
                counts["LOCKED"] += 1
                continue
            kind = str(get(tile, "kind", "OTHER"))
            crop = get(tile, "crop")
            animal = get(tile, "animal")
            label = f"{kind}:{crop or animal}" if crop or animal else kind
            counts[label] += 1
    return dict(sorted(counts.items()))


def dig_count(action) -> int:
    action = action or {}
    operations = [action.get("farmer"), *(action.get("hands") or [])]
    return sum(
        int(isinstance(operation, list) and operation and operation[0] == "DIG")
        for operation in operations
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("opponent")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    candidate, _, candidate_meta = resolve_agent(args.candidate, "weed_trace_candidate")
    opponent, _, opponent_meta = resolve_agent(args.opponent, "weed_trace_opponent")
    players = [candidate, opponent] if args.seat == 0 else [opponent, candidate]
    env = make("kaggriculture", configuration={"seed": args.seed}, debug=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)

    other = 1 - args.seat
    cumulative_digs = 0
    rows = []
    for step, states in enumerate(env.steps):
        if step > 0:
            cumulative_digs += dig_count(states[args.seat].action)
        if step % 24 != 0 and step != len(env.steps) - 1:
            continue
        observation = states[args.seat].observation
        farms = list(get(observation, "farms", []) or [])
        rows.append(
            {
                "step": step,
                "day": int(get(observation, "day", 0) or 0),
                "money": float(get(farms[args.seat], "money", 0) or 0),
                "opponent_money": float(get(farms[other], "money", 0) or 0),
                "cumulative_digs": cumulative_digs,
                "tiles": tile_counts(farms[args.seat]),
            }
        )

    report = {
        "candidate": candidate_meta,
        "opponent": opponent_meta,
        "seed": args.seed,
        "seat": args.seat,
        "reward": float(env.steps[-1][args.seat].reward),
        "opponent_reward": float(env.steps[-1][other].reward),
        "rows": rows,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(args.output)
    else:
        print(text)


if __name__ == "__main__":
    main()
