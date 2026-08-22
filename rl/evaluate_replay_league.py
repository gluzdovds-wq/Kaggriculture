"""Evaluate compatible macro candidates on exact public ladder replay losses.

Each replay opponent is converted to an action tape and run on its original
public seed and seat.  A named baseline must reproduce the recorded final banks
exactly before any counterfactual candidate result is accepted.  This gives a
small but high-value best-response league without pretending that an action
tape is the opponent's general source policy.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from arena import play
from tools.extract_replay_agent import render_agent


@dataclass(frozen=True)
class ReplayCase:
    episode_id: int
    replay_path: str
    seed: int
    candidate_seat: int
    opponent_name: str
    opponent_tape: str
    recorded_candidate_bank: float
    recorded_opponent_bank: float


def parse_named_path(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError("candidate must be NAME=PATH")
    name, raw_path = spec.split("=", 1)
    if not name or not raw_path:
        raise ValueError("candidate must be NAME=PATH")
    return name, Path(raw_path)


def load_case(replay_path: Path, own_name: str, generated_dir: Path) -> ReplayCase:
    payload = json.loads(replay_path.read_text(encoding="utf-8"))
    info = payload.get("info", {})
    names = list(info.get("TeamNames", []) or [])
    if names.count(own_name) != 1 or len(names) != 2:
        raise ValueError(f"cannot identify {own_name!r} exactly once in {replay_path}")
    candidate_seat = names.index(own_name)
    opponent_seat = 1 - candidate_seat
    rewards = list(payload.get("rewards", []) or [])
    if len(rewards) != 2:
        raise ValueError(f"replay lacks final rewards: {replay_path}")
    episode_id = int(info.get("EpisodeId"))
    seed = int(info.get("seed"))
    generated_dir.mkdir(parents=True, exist_ok=True)
    tape_path = (generated_dir / f"episode-{episode_id}-seat-{opponent_seat}.py").resolve()
    tape_path.write_text(render_agent(payload, opponent_seat), encoding="utf-8")
    return ReplayCase(
        episode_id=episode_id,
        replay_path=str(replay_path.resolve()),
        seed=seed,
        candidate_seat=candidate_seat,
        opponent_name=names[opponent_seat],
        opponent_tape=str(tape_path),
        recorded_candidate_bank=float(rewards[candidate_seat]),
        recorded_opponent_bank=float(rewards[opponent_seat]),
    )


def run_task(task: tuple[str, str, ReplayCase]) -> dict:
    candidate_name, candidate_path, case = task
    result = play(
        candidate_path,
        case.opponent_tape,
        case.seed,
        case.candidate_seat,
    )
    return {
        "candidate": candidate_name,
        "episode_id": case.episode_id,
        "opponent_name": case.opponent_name,
        "seed": case.seed,
        "candidate_seat": case.candidate_seat,
        "candidate_bank": result["candidate_bank"],
        "opponent_bank": result["opponent_bank"],
        "margin": result["margin"],
        "outcome": result["outcome"],
        "candidate_sha256": result["candidate_artifact"]["sha256"],
        "max_action_ms": result["candidate_latency"]["max_ms"],
        "candidate_telemetry": result.get("candidate_telemetry"),
        "shop_unlock_events": result.get("shop_unlock_events", []),
        "opponent_public_checkpoints": result.get(
            "opponent_public_checkpoints", []
        ),
        "public_context_checkpoints": result.get("public_context_checkpoints", []),
    }


def mean(values) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0.0


def summarize(matches: list[dict], baseline: dict[int, dict]) -> dict:
    flips = 0
    regressions = 0
    for row in matches:
        base = baseline[row["episode_id"]]
        if row["outcome"] > base["outcome"]:
            flips += 1
        elif row["outcome"] < base["outcome"]:
            regressions += 1
        row["margin_delta_vs_baseline"] = row["margin"] - base["margin"]
    return {
        "episodes": len(matches),
        "outcome_rate": mean(row["outcome"] for row in matches),
        "average_margin": mean(row["margin"] for row in matches),
        "average_margin_delta_vs_baseline": mean(
            row["margin_delta_vs_baseline"] for row in matches
        ),
        "outcome_improvements": flips,
        "outcome_regressions": regressions,
        "max_action_ms": max(row["max_action_ms"] for row in matches),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", action="append", type=Path, required=True)
    parser.add_argument("--own-name", required=True)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidates = dict(parse_named_path(spec) for spec in args.candidate)
    if len(candidates) != len(args.candidate):
        parser.error("candidate names must be unique")
    if args.baseline not in candidates:
        parser.error("--baseline must name one --candidate")
    resolved = {name: str(path.resolve()) for name, path in candidates.items()}
    cases = [load_case(path, args.own_name, args.generated_dir) for path in args.replay]
    tasks = [
        (name, path, case)
        for name, path in resolved.items()
        for case in cases
    ]
    if args.jobs <= 1:
        matches = [run_task(task) for task in tasks]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as pool:
            matches = list(pool.map(run_task, tasks))
    matches.sort(key=lambda row: (row["candidate"], row["episode_id"]))

    baseline_rows = [row for row in matches if row["candidate"] == args.baseline]
    baseline = {row["episode_id"]: row for row in baseline_rows}
    for case in cases:
        row = baseline[case.episode_id]
        if (
            row["candidate_bank"] != case.recorded_candidate_bank
            or row["opponent_bank"] != case.recorded_opponent_bank
        ):
            raise RuntimeError(
                f"baseline does not reproduce episode {case.episode_id}: "
                f"{row['candidate_bank']}:{row['opponent_bank']} != "
                f"{case.recorded_candidate_bank}:{case.recorded_opponent_bank}"
            )

    by_candidate = {}
    for name in resolved:
        rows = [row for row in matches if row["candidate"] == name]
        by_candidate[name] = {
            "path": resolved[name],
            "summary": summarize(rows, baseline),
            "matches": rows,
        }
    report = {
        "algorithm": "exact public replay-tape counterfactual league",
        "warning": "valid only on each replay's original public seed and seat",
        "own_name": args.own_name,
        "baseline": args.baseline,
        "baseline_exact_reproduction": True,
        "cases": [asdict(case) for case in cases],
        "candidates": by_candidate,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        name: payload["summary"] for name, payload in by_candidate.items()
    }, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
