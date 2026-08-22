"""Replace leaderboard agents on their exact public seeds against opponent tapes."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from arena import play
from tools.analyze_replay_meta import normalize_name, player_names
from tools.extract_replay_agent import render_agent


@dataclass(frozen=True)
class DonorCase:
    episode_id: int
    seed: int
    target_seat: int
    target_name: str
    target_rank: int
    target_submission_id: int
    target_tape: str
    opponent_name: str
    opponent_tape: str
    recorded_target_bank: float
    recorded_opponent_bank: float


def parse_named_path(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError("candidate must be NAME=PATH")
    name, raw_path = value.split("=", 1)
    path = Path(raw_path).resolve()
    if not name or not path.is_file():
        raise ValueError(f"invalid candidate {value!r}")
    return name, str(path)


def requested_target_matches(request: dict, target_names: tuple[str, ...]) -> bool:
    if not target_names:
        return True
    targets = {normalize_name(name) for name in target_names}
    request_names = {
        normalize_name(request.get("name", "")),
        normalize_name(request.get("replay_name", "")),
    }
    return bool(targets & request_names)


def find_named_seat(names: list[str], target_names: tuple[str, ...]) -> int | None:
    targets = {normalize_name(name) for name in target_names}
    return next(
        (seat for seat, name in enumerate(names) if normalize_name(name) in targets),
        None,
    )


def build_cases(
    manifest: dict,
    generated_dir: Path,
    max_rank: int,
    target_names: tuple[str, ...] = (),
    episode_ids: tuple[int, ...] = (),
) -> list[DonorCase]:
    generated_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    seen = set()
    for episode in manifest.get("episodes", []):
        if episode_ids and int(episode["episode_id"]) not in episode_ids:
            continue
        replay = json.loads(Path(episode["path"]).read_text(encoding="utf-8"))
        names = player_names(replay)
        normalized = [normalize_name(name) for name in names]
        rewards = [float(value or 0) for value in replay.get("rewards", [])]
        info = replay.get("info", {}) or {}
        for request in episode.get("requested_for", []):
            rank = request.get("rank")
            if request.get("cohort") != "top20" or rank is None or int(rank) > max_rank:
                continue
            if not requested_target_matches(request, target_names):
                continue
            key = (int(request["submission_id"]), int(episode["episode_id"]))
            if key in seen:
                continue
            seen.add(key)
            target = normalize_name(request.get("replay_name", request["name"]))
            if target not in normalized:
                raise ValueError(
                    f"cannot find {request['name']!r} in episode {episode['episode_id']}: {names}"
                )
            target_seat = normalized.index(target)
            opponent_seat = 1 - target_seat
            target_tape = generated_dir / f"episode-{episode['episode_id']}-seat-{target_seat}.py"
            opponent_tape = generated_dir / f"episode-{episode['episode_id']}-seat-{opponent_seat}.py"
            if not target_tape.is_file():
                target_tape.write_text(render_agent(replay, target_seat), encoding="utf-8")
            if not opponent_tape.is_file():
                opponent_tape.write_text(render_agent(replay, opponent_seat), encoding="utf-8")
            cases.append(
                DonorCase(
                    episode_id=int(episode["episode_id"]),
                    seed=int(info.get("seed", 0) or 0),
                    target_seat=target_seat,
                    target_name=request["name"],
                    target_rank=int(rank),
                    target_submission_id=int(request["submission_id"]),
                    target_tape=str(target_tape.resolve()),
                    opponent_name=names[opponent_seat],
                    opponent_tape=str(opponent_tape.resolve()),
                    recorded_target_bank=rewards[target_seat],
                    recorded_opponent_bank=rewards[opponent_seat],
                )
            )
    cases.sort(key=lambda case: (case.target_rank, case.episode_id))
    return cases


def build_opponent_cases(
    manifest: dict,
    generated_dir: Path,
    opponent_names: tuple[str, ...],
    episode_ids: tuple[int, ...] = (),
) -> list[DonorCase]:
    generated_dir.mkdir(parents=True, exist_ok=True)
    leaderboard_by_name = {
        normalize_name(entry["name"]): entry
        for entry in manifest.get("leaderboard_entries", [])
    }
    cases = []
    for episode in manifest.get("episodes", []):
        if episode_ids and int(episode["episode_id"]) not in episode_ids:
            continue
        replay = json.loads(Path(episode["path"]).read_text(encoding="utf-8"))
        names = player_names(replay)
        opponent_seat = find_named_seat(names, opponent_names)
        if opponent_seat is None or len(names) != 2:
            continue
        target_seat = 1 - opponent_seat
        target_meta = leaderboard_by_name.get(normalize_name(names[target_seat]), {})
        target_tape = generated_dir / f"episode-{episode['episode_id']}-seat-{target_seat}.py"
        opponent_tape = generated_dir / f"episode-{episode['episode_id']}-seat-{opponent_seat}.py"
        if not target_tape.is_file():
            target_tape.write_text(render_agent(replay, target_seat), encoding="utf-8")
        if not opponent_tape.is_file():
            opponent_tape.write_text(render_agent(replay, opponent_seat), encoding="utf-8")
        rewards = [float(value or 0) for value in replay.get("rewards", [])]
        cases.append(
            DonorCase(
                episode_id=int(episode["episode_id"]),
                seed=int((replay.get("info", {}) or {}).get("seed", 0) or 0),
                target_seat=target_seat,
                target_name=names[target_seat],
                target_rank=int(target_meta.get("rank", 10_000)),
                target_submission_id=int(target_meta.get("submission_id", 0)),
                target_tape=str(target_tape.resolve()),
                opponent_name=names[opponent_seat],
                opponent_tape=str(opponent_tape.resolve()),
                recorded_target_bank=rewards[target_seat],
                recorded_opponent_bank=rewards[opponent_seat],
            )
        )
    cases.sort(key=lambda case: case.episode_id)
    return cases


def run_one(task: tuple[str, str, DonorCase]) -> dict:
    candidate_name, candidate_path, case = task
    result = play(candidate_path, case.opponent_tape, case.seed, case.target_seat)
    return {
        "candidate": candidate_name,
        "episode_id": case.episode_id,
        "target_rank": case.target_rank,
        "target_name": case.target_name,
        "target_seat": case.target_seat,
        "opponent_name": case.opponent_name,
        "candidate_bank": result["candidate_bank"],
        "opponent_bank": result["opponent_bank"],
        "margin": result["margin"],
        "outcome": result["outcome"],
        "max_action_ms": result["candidate_latency"]["max_ms"],
        "candidate_telemetry": result.get("candidate_telemetry", {}),
    }


def average(rows) -> float:
    values = list(rows)
    return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict], donor: dict[tuple[int, int], dict]) -> dict:
    for row in rows:
        original = donor[(row["episode_id"], row["target_seat"])]
        row["bank_delta_vs_donor"] = row["candidate_bank"] - original["candidate_bank"]
        row["margin_delta_vs_donor"] = row["margin"] - original["margin"]
        row["outcome_delta_vs_donor"] = row["outcome"] - original["outcome"]
    return {
        "games": len(rows),
        "outcome_rate": average(row["outcome"] for row in rows),
        "average_bank": average(row["candidate_bank"] for row in rows),
        "average_margin": average(row["margin"] for row in rows),
        "average_bank_delta_vs_donor": average(row["bank_delta_vs_donor"] for row in rows),
        "average_margin_delta_vs_donor": average(row["margin_delta_vs_donor"] for row in rows),
        "outcome_improvements": sum(row["outcome_delta_vs_donor"] > 0 for row in rows),
        "outcome_regressions": sum(row["outcome_delta_vs_donor"] < 0 for row in rows),
        "worst_margin_delta_vs_donor": min(row["margin_delta_vs_donor"] for row in rows),
        "max_action_ms": max(row["max_action_ms"] for row in rows),
    }


def evaluate(
    cases: list[DonorCase], candidates: dict[str, str], jobs: int
) -> dict:
    tasks = [("DONOR_TAPE", case.target_tape, case) for case in cases]
    tasks.extend(
        (name, path, case)
        for name, path in candidates.items()
        for case in cases
    )
    if jobs <= 1:
        matches = [run_one(task) for task in tasks]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
            matches = list(pool.map(run_one, tasks))
    matches.sort(key=lambda row: (row["candidate"], row["target_rank"], row["episode_id"]))

    donor_rows = [row for row in matches if row["candidate"] == "DONOR_TAPE"]
    donor = {(row["episode_id"], row["target_seat"]): row for row in donor_rows}
    for case in cases:
        row = donor[(case.episode_id, case.target_seat)]
        if (
            row["candidate_bank"] != case.recorded_target_bank
            or row["opponent_bank"] != case.recorded_opponent_bank
        ):
            raise RuntimeError(
                f"tapes do not reproduce episode {case.episode_id}: "
                f"{row['candidate_bank']}:{row['opponent_bank']} != "
                f"{case.recorded_target_bank}:{case.recorded_opponent_bank}"
            )
    groups = {}
    for name in ["DONOR_TAPE", *candidates]:
        rows = [row for row in matches if row["candidate"] == name]
        groups[name] = {"summary": summarize(rows, donor), "matches": rows}
    return {
        "schema": "top-replay-counterfactual-v1",
        "warning": "opponent is an exact action tape on the original public seed, not its source policy",
        "baseline_exact_reproduction": True,
        "cases": [asdict(case) for case in cases],
        "candidates": groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--max-rank", type=int, default=5)
    parser.add_argument("--target-name", action="append", default=[])
    parser.add_argument("--opponent-name", action="append", default=[])
    parser.add_argument("--episode-id", action="append", type=int, default=[])
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.target_name and args.opponent_name:
        parser.error("--target-name and --opponent-name are mutually exclusive")
    try:
        candidates = dict(parse_named_path(value) for value in args.candidate)
    except ValueError as error:
        parser.error(str(error))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.opponent_name:
        cases = build_opponent_cases(
            manifest,
            args.generated_dir,
            tuple(args.opponent_name),
            tuple(args.episode_id),
        )
    else:
        cases = build_cases(
            manifest,
            args.generated_dir,
            args.max_rank,
            tuple(args.target_name),
            tuple(args.episode_id),
        )
    report = evaluate(cases, candidates, max(1, args.jobs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {name: payload["summary"] for name, payload in report["candidates"].items()},
            indent=2,
        )
    )
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
