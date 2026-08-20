"""Run reproducible local Kaggriculture matches for main.py."""

import argparse
import contextlib
import io
import json
import math
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

from main import agent


def play(opponent, seed, swapped=False, replay_path=None):
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [opponent, agent] if swapped else [agent, opponent]
    env.run(players)

    final = env.steps[-1]
    our_index = 1 if swapped else 0
    their_index = 1 - our_index
    ours = float(final[our_index]["reward"])
    theirs = float(final[their_index]["reward"])
    statuses = [state["status"] for state in final]
    if statuses != ["DONE", "DONE"] or not all(math.isfinite(x) for x in (ours, theirs)):
        raise RuntimeError(f"invalid final state: statuses={statuses}, rewards={(ours, theirs)}")

    if replay_path is not None:
        replay_path.parent.mkdir(parents=True, exist_ok=True)
        replay_path.write_text(json.dumps(env.toJSON()), encoding="utf-8")

    return {
        "seed": seed,
        "seat": our_index,
        "ours": ours,
        "theirs": theirs,
        "margin": ours - theirs,
        "win": ours > theirs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--opponent",
        default="starter",
        help="built-in agent name or path to a public/local main.py",
    )
    parser.add_argument("--games", type=int, default=4, help="number of seeds; both seats are played")
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--replay-dir", type=Path)
    parser.add_argument("--json", type=Path, help="write machine-readable match results")
    args = parser.parse_args()

    opponent = args.opponent
    if opponent not in {"starter", "random", "pass"}:
        opponent_path = Path(opponent).resolve()
        if not opponent_path.is_file():
            parser.error(f"opponent file does not exist: {opponent_path}")
        opponent = str(opponent_path)

    results = []
    for offset in range(args.games):
        seed = args.seed + offset
        for swapped in (False, True):
            replay = None
            if args.replay_dir:
                seat = 1 if swapped else 0
                replay = args.replay_dir / f"{args.opponent}-seed{seed}-seat{seat}.json"
            result = play(opponent, seed, swapped, replay)
            results.append(result)
            verdict = "WIN" if result["win"] else ("TIE" if result["margin"] == 0 else "LOSS")
            print(
                f"seed={seed} seat={result['seat']} {verdict}: "
                f"{result['ours']:.0f} vs {result['theirs']:.0f} "
                f"(margin {result['margin']:+.0f})"
            )

    wins = sum(r["win"] for r in results)
    average = sum(r["ours"] for r in results) / len(results)
    average_margin = sum(r["margin"] for r in results) / len(results)
    print(
        f"summary: {wins}/{len(results)} wins, "
        f"average score {average:.1f}, average margin {average_margin:+.1f}"
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "opponent": args.opponent,
            "seed_start": args.seed,
            "seed_count": args.games,
            "matches": results,
            "summary": {
                "wins": wins,
                "matches": len(results),
                "win_rate": wins / len(results),
                "average_score": average,
                "average_margin": average_margin,
            },
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
