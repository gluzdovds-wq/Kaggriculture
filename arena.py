"""Paired local arena for Kaggriculture agents.

Every seed is played from both seats.  The report keeps outcome-based metrics
separate from diagnostic coin margins and records exact source hashes plus
per-action latency for reproducibility and Kaggle runtime checks.
"""

from __future__ import annotations

import argparse
import contextlib
import concurrent.futures
import hashlib
import importlib.util
import inspect
import io
import json
import math
import os
import random
import statistics
import time
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


BUILT_INS = {"pass", "random", "starter"}
PUBLIC_CHECKPOINT_STEPS = (1, 12, 24, 48, 72)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def timed_agent(path: Path, tag: str):
    module_name = f"arena_{tag}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load agent: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw_agent = module.agent
    positional = [
        parameter
        for parameter in inspect.signature(raw_agent).parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    accepts_configuration = len(positional) >= 2
    timings = []

    def wrapped(obs, configuration=None):
        started = time.perf_counter()
        try:
            if accepts_configuration:
                return raw_agent(obs, configuration)
            return raw_agent(obs)
        finally:
            timings.append(time.perf_counter() - started)

    wrapped._arena_signature = str(inspect.signature(raw_agent))
    wrapped._arena_accepts_configuration = accepts_configuration
    return wrapped, timings


def resolve_agent(spec: str, tag: str):
    if spec in BUILT_INS:
        return spec, [], {"kind": "built-in", "name": spec}
    path = Path(spec).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    loaded, timings = timed_agent(path, tag)
    return loaded, timings, {
        "kind": "file",
        "path": str(path),
        "sha256": file_hash(path),
        "bytes": path.stat().st_size,
        "callable_signature": loaded._arena_signature,
        "accepts_configuration": loaded._arena_accepts_configuration,
    }


def outcome(ours: float, theirs: float) -> float:
    if ours > theirs:
        return 1.0
    if ours < theirs:
        return 0.0
    return 0.5


def bootstrap_ci(pair_scores: list[float], samples: int = 5000) -> list[float]:
    if not pair_scores:
        return [0.0, 0.0]
    rng = random.Random(20260820)
    means = []
    n = len(pair_scores)
    for _ in range(samples):
        means.append(sum(pair_scores[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return [percentile(means, 0.025), percentile(means, 0.975)]


def latency_summary(values: list[float]) -> dict:
    milliseconds = [value * 1000 for value in values]
    return {
        "calls": len(milliseconds),
        "p50_ms": percentile(milliseconds, 0.50),
        "p95_ms": percentile(milliseconds, 0.95),
        "p99_ms": percentile(milliseconds, 0.99),
        "max_ms": max(milliseconds, default=0.0),
        "mean_ms": statistics.fmean(milliseconds) if milliseconds else 0.0,
    }


def shop_unlock_events(env) -> list[dict]:
    """Return the observable shop history without relying on replay-private data."""
    events = []
    previous: tuple[str, ...] = ()
    for step, states in enumerate(env.steps):
        observation = states[0].observation
        current = tuple((observation.town or {}).get("unlocked_shops", []) or [])
        if current != previous:
            events.append(
                {
                    "step": step,
                    "day": int(observation.day),
                    "shops": list(current),
                    "new_shops": list(current[len(previous) :]),
                }
            )
            previous = current
    return events


def _public_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def public_farm_signature(farm) -> dict:
    """Compress an inference-visible farm into deterministic route features."""
    tile_kinds: dict[str, int] = {}
    crops: dict[str, int] = {}
    animals: dict[str, int] = {}
    occupied = []
    for y, row in enumerate(_public_get(farm, "tiles", []) or []):
        for x, tile in enumerate(row or []):
            if tile is None or tile == "LOCKED":
                continue
            kind = str(_public_get(tile, "kind", type(tile).__name__))
            tile_kinds[kind] = tile_kinds.get(kind, 0) + 1
            crop = _public_get(tile, "crop")
            animal = _public_get(tile, "animal")
            if crop:
                crops[str(crop)] = crops.get(str(crop), 0) + 1
            if animal:
                animals[str(animal)] = animals.get(str(animal), 0) + 1
            occupied.append([x, y, kind, crop, animal])
    return {
        "money": int(_public_get(farm, "money", 0) or 0),
        "farmer": list(_public_get(farm, "farmer", []) or []),
        "hands": [list(position) for position in (_public_get(farm, "hands", []) or [])],
        "hires_today": int(_public_get(farm, "hires_today", 0) or 0),
        "unlocked_quadrants": list(
            _public_get(farm, "unlocked_quadrants", []) or []
        ),
        "tile_kinds": dict(sorted(tile_kinds.items())),
        "crops": dict(sorted(crops.items())),
        "animals": dict(sorted(animals.items())),
        "occupied": occupied,
    }


def opponent_public_checkpoints(env, candidate_seat: int) -> list[dict]:
    """Record only observations that are legal inputs to the candidate policy."""
    opponent_seat = 1 - candidate_seat
    checkpoints = []
    for step in PUBLIC_CHECKPOINT_STEPS:
        if step >= len(env.steps):
            continue
        observation = env.steps[step][candidate_seat].observation
        farms = _public_get(observation, "farms", []) or []
        checkpoints.append(
            {
                "step": step,
                "day": int(_public_get(observation, "day", 0) or 0),
                "hour": int(_public_get(observation, "hour", 0) or 0),
                "opponent": public_farm_signature(farms[opponent_seat]),
            }
        )
    return checkpoints


def play(candidate_spec: str, opponent_spec: str, seed: int, candidate_seat: int) -> dict:
    candidate, candidate_times, candidate_meta = resolve_agent(
        candidate_spec, f"candidate_{seed}_{candidate_seat}"
    )
    opponent, opponent_times, opponent_meta = resolve_agent(
        opponent_spec, f"opponent_{seed}_{candidate_seat}"
    )
    players = [candidate, opponent] if candidate_seat == 0 else [opponent, candidate]
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    started = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)
    wall_seconds = time.perf_counter() - started

    final = env.steps[-1]
    statuses = [str(state.status) for state in final]
    if statuses != ["DONE", "DONE"]:
        raise RuntimeError(f"seed={seed} seat={candidate_seat}: statuses={statuses}")
    opponent_seat = 1 - candidate_seat
    ours = float(final[candidate_seat].reward)
    theirs = float(final[opponent_seat].reward)
    if not all(math.isfinite(value) for value in (ours, theirs)):
        raise RuntimeError(f"non-finite rewards: {(ours, theirs)}")
    return {
        "seed": seed,
        "candidate_seat": candidate_seat,
        "candidate_bank": ours,
        "opponent_bank": theirs,
        "margin": ours - theirs,
        "outcome": outcome(ours, theirs),
        "wall_seconds": wall_seconds,
        "candidate_latency": latency_summary(candidate_times),
        "opponent_latency": latency_summary(opponent_times),
        "candidate_artifact": candidate_meta,
        "opponent_artifact": opponent_meta,
        "shop_unlock_events": shop_unlock_events(env),
        "opponent_public_checkpoints": opponent_public_checkpoints(env, candidate_seat),
    }


def summarize(matches: list[dict]) -> dict:
    grouped: dict[int, list[dict]] = {}
    for match in matches:
        grouped.setdefault(match["seed"], []).append(match)
    incomplete = [seed for seed, rows in grouped.items() if len(rows) != 2]
    if incomplete:
        raise RuntimeError(f"seeds missing a seat: {incomplete}")
    pair_scores = [statistics.fmean(row["outcome"] for row in rows) for rows in grouped.values()]
    candidate_latencies = [
        value
        for match in matches
        for value in [
            match["candidate_latency"]["p50_ms"],
            match["candidate_latency"]["p95_ms"],
            match["candidate_latency"]["p99_ms"],
        ]
    ]
    return {
        "seeds": len(grouped),
        "matches": len(matches),
        "outcome_rate": statistics.fmean(match["outcome"] for match in matches),
        "paired_outcome_rate": statistics.fmean(pair_scores),
        "paired_bootstrap_95ci": bootstrap_ci(pair_scores),
        "average_candidate_bank": statistics.fmean(match["candidate_bank"] for match in matches),
        "average_opponent_bank": statistics.fmean(match["opponent_bank"] for match in matches),
        "average_margin": statistics.fmean(match["margin"] for match in matches),
        "worst_margin": min(match["margin"] for match in matches),
        "average_wall_seconds": statistics.fmean(match["wall_seconds"] for match in matches),
        "latency_check_ms": {
            "median_of_reported_quantiles": statistics.median(candidate_latencies),
            "max_action": max(match["candidate_latency"]["max_ms"] for match in matches),
        },
    }


def parse_opponent(value: str) -> tuple[str, str]:
    if "=" in value:
        name, spec = value.split("=", 1)
        return name, spec
    if value in BUILT_INS:
        return value, value
    path = Path(value)
    return path.parent.name or path.stem, value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default="main.py")
    parser.add_argument(
        "--opponent",
        action="append",
        required=True,
        help="repeat NAME=PATH (or use starter/random/pass)",
    )
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="independent worker processes (use >1 for local multi-core evaluation)",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    # Windows ProcessPool workers start fresh interpreters.  Pin their hash
    # seed before spawning so agents that accidentally depend on set/dict hash
    # order remain reproducible across candidate A/B runs.
    os.environ.setdefault("PYTHONHASHSEED", "0")

    report = {
        "engine": "kaggle-environments==1.32.7",
        "python_hash_seed": os.environ["PYTHONHASHSEED"],
        "candidate": args.candidate,
        "seed_start": args.seed,
        "seed_count": args.seeds,
        "jobs": args.jobs,
        "opponents": {},
    }
    for opponent_name, opponent_spec in map(parse_opponent, args.opponent):
        print(f"opponent={opponent_name}", flush=True)
        tasks = [
            (args.candidate, opponent_spec, seed, seat)
            for seed in range(args.seed, args.seed + args.seeds)
            for seat in (0, 1)
        ]
        if args.jobs == 1:
            matches = [play(*task) for task in tasks]
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as executor:
                matches = list(executor.map(_play_task, tasks))
        matches.sort(key=lambda row: (row["seed"], row["candidate_seat"]))
        for match in matches:
            print(
                f"  seed={match['seed']} seat={match['candidate_seat']} "
                f"outcome={match['outcome']:.1f} "
                f"bank={match['candidate_bank']:.0f}:{match['opponent_bank']:.0f} "
                f"margin={match['margin']:+.0f}",
                flush=True,
            )
        summary = summarize(matches)
        report["opponents"][opponent_name] = {"summary": summary, "matches": matches}
        print(
            f"  summary paired={summary['paired_outcome_rate']:.3f} "
            f"CI={summary['paired_bootstrap_95ci']} margin={summary['average_margin']:+.1f}",
            flush=True,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report={args.output}")


def _play_task(task: tuple[str, str, int, int]) -> dict:
    return play(*task)


if __name__ == "__main__":
    main()
