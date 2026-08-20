"""Measure exact end-of-day shed overflow without changing engine semantics."""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import sys
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena import outcome, resolve_agent

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def projected_drop(private, capacity: int) -> dict:
    """Replay only the documented stable inventory/item insertion order."""
    shed = copy.deepcopy(dict(private["shed"]))
    dropped: dict[str, int] = {}
    for inventory in private["inventories"]:
        for item, raw_count in list(inventory.items()):
            count = max(0, int(raw_count or 0))
            room = max(0, capacity - sum(int(value or 0) for value in shed.values()))
            take = min(count, room)
            if take:
                shed[item] = shed.get(item, 0) + take
            if count > take:
                dropped[item] = dropped.get(item, 0) + count - take
    return {
        "shed_before": dict(private["shed"]),
        "inventories_before": copy.deepcopy(list(private["inventories"])),
        "shed_after_projected": shed,
        "dropped": dropped,
    }


def play(candidate_spec: str, opponent_spec: str, seed: int, candidate_seat: int) -> dict:
    candidate, _, _ = resolve_agent(candidate_spec, f"overflow_candidate_{seed}_{candidate_seat}")
    opponent, _, _ = resolve_agent(opponent_spec, f"overflow_opponent_{seed}_{candidate_seat}")
    players = [candidate, opponent] if candidate_seat == 0 else [opponent, candidate]
    events = []
    original = engine._drop_inventories_to_shed

    def instrumented(private, capacity):
        event = projected_drop(private, capacity)
        event["sequence"] = len(events)
        events.append(event)
        return original(private, capacity)

    engine._drop_inventories_to_shed = instrumented
    try:
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env.run(players)
    finally:
        engine._drop_inventories_to_shed = original

    final = env.steps[-1]
    opponent_seat = 1 - candidate_seat
    ours = float(final[candidate_seat].reward)
    theirs = float(final[opponent_seat].reward)
    candidate_events = []
    for event in events:
        if event["sequence"] % 2 != candidate_seat or not event["dropped"]:
            continue
        sequence = event.pop("sequence")
        event["day"] = sequence // 2
        candidate_events.append(event)
    return {
        "seed": seed,
        "candidate_seat": candidate_seat,
        "candidate_bank": ours,
        "opponent_bank": theirs,
        "outcome": outcome(ours, theirs),
        "overflow_events": candidate_events,
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
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
