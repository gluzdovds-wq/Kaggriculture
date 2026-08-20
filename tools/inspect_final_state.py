"""Inspect the final private/public state of one official Kaggriculture match."""

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


def get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def summarize_observation(observation, player: int) -> dict:
    farms = list(get(observation, "farms", []) or [])
    farm = farms[player]
    private = get(observation, "private", {}) or {}
    tile_counts: Counter[str] = Counter()
    for row in get(farm, "tiles", []) or []:
        for tile in row:
            if isinstance(tile, dict):
                label = str(tile.get("kind", "UNKNOWN"))
                if tile.get("crop"):
                    label += ":" + str(tile["crop"])
                if tile.get("animal"):
                    label += ":" + str(tile["animal"])
                tile_counts[label] += 1
    market = get(observation, "market", {}) or {}
    return {
        "money": get(farm, "money", 0),
        "shed": dict(get(private, "shed", {}) or {}),
        "seeds": dict(get(private, "seeds", {}) or {}),
        "tile_counts": dict(sorted(tile_counts.items())),
        "market_inventory": dict(get(market, "inventory", {}) or {}),
        "market_prices": dict(get(market, "prices", {}) or {}),
        "shops": list(get(get(observation, "town", {}) or {}, "unlocked_shops", []) or []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("opponent")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()

    candidate, _, candidate_meta = resolve_agent(args.candidate, "inspect_candidate")
    opponent, _, opponent_meta = resolve_agent(args.opponent, "inspect_opponent")
    players = [candidate, opponent]
    if args.seat == 1:
        players.reverse()
    env = make("kaggriculture", configuration={"seed": args.seed}, debug=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)
    final = env.steps[-1]
    observations = [final[index].observation for index in range(2)]
    report = {
        "seed": args.seed,
        "candidate_seat": args.seat,
        "candidate": candidate_meta,
        "opponent": opponent_meta,
        "players": [
            {
                "seat": index,
                "reward": final[index].reward,
                **summarize_observation(observations[index], index),
            }
            for index in range(2)
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
