"""Trace candidate positions, inventories and executed actions near an EOD boundary."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena import resolve_agent

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def shed_access(size: int) -> set[tuple[int, int]]:
    half = size // 2
    return {
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    }


def trace_row(env, step: int, seat: int) -> dict:
    state = env.steps[step][seat]
    observation = state.observation
    farm = list(get(observation, "farms", []) or [])[seat]
    private = get(observation, "private", {}) or {}
    positions = [get(farm, "farmer"), *list(get(farm, "hands", []) or [])]
    inventories = list(get(private, "inventories", []) or [])
    inventories.extend({} for _ in range(len(positions) - len(inventories)))
    tiles = list(get(farm, "tiles", []) or [])
    access = shed_access(len(tiles))
    executed = None
    if step + 1 < len(env.steps):
        executed = env.steps[step + 1][seat].action
    units = []
    for index, (position, inventory) in enumerate(zip(positions, inventories)):
        x, y = map(int, position[:2])
        tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles) else None
        units.append(
            {
                "unit": "farmer" if index == 0 else f"hand_{index - 1}",
                "position": [x, y],
                "shed_distance": min(abs(x - sx) + abs(y - sy) for sx, sy in access),
                "inventory": dict(inventory or {}),
                "load": sum(max(0, int(value or 0)) for value in dict(inventory or {}).values()),
                "tile_kind": tile.get("kind") if isinstance(tile, dict) else tile,
            }
        )
    shed = dict(get(private, "shed", {}) or {})
    return {
        "step": step,
        "day": int(get(observation, "day", 0) or 0),
        "hour": int(get(observation, "hour", 0) or 0),
        "shed": shed,
        "shed_total": sum(max(0, int(value or 0)) for value in shed.values()),
        "carried_total": sum(unit["load"] for unit in units),
        "units": units,
        "executed_action": executed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("opponent")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    parser.add_argument("--from-step", type=int, default=684)
    parser.add_argument("--to-step", type=int, default=696)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    candidate, _, _ = resolve_agent(args.candidate, "terminal_trace_candidate")
    opponent, _, _ = resolve_agent(args.opponent, "terminal_trace_opponent")
    players = [candidate, opponent] if args.seat == 0 else [opponent, candidate]
    env = make("kaggriculture", configuration={"seed": args.seed}, debug=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)
    last = min(args.to_step, len(env.steps) - 1)
    report = {
        "candidate": args.candidate,
        "opponent": args.opponent,
        "seed": args.seed,
        "seat": args.seat,
        "rows": [trace_row(env, step, args.seat) for step in range(args.from_step, last + 1)],
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
