"""Classify and counterfactually evaluate live submission replays.

The evaluator uses only the target player's public observation to classify an
opponent-family gate.  For counterfactuals it extracts the other seat's public
action tape and first requires exact reproduction of the recorded banks on the
original seed.  The tape is an offline control, not an inference-time feature.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.analyze_replay_meta import normalize_name, player_names
from tools.extract_replay_agent import render_agent


@dataclass(frozen=True)
class LiveReplayMeta:
    episode_id: int
    path: str
    seed: int
    target_name: str
    target_seat: int
    opponent_name: str
    opponent_animals: dict[str, int]
    gate_active: bool
    recorded_target_bank: float
    recorded_opponent_bank: float
    recorded_outcome: float


def console_cohort_summary(live_cohort: dict) -> dict:
    replays = live_cohort.get("replays", [])
    return {
        key: value
        for key, value in live_cohort.items()
        if key != "replays"
    } | {
        "active_episode_ids": [
            replay["episode_id"] for replay in replays if replay["gate_active"]
        ],
        "loss_episode_ids": [
            replay["episode_id"]
            for replay in replays
            if replay["recorded_outcome"] == 0
        ],
    }


def parse_gate_animals(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"gate animal must be ANIMAL=COUNT, got {value!r}")
        animal, raw_count = value.split("=", 1)
        animal = animal.strip().upper()
        count = int(raw_count)
        if not animal or count < 0:
            raise ValueError(f"invalid gate animal {value!r}")
        result[animal] = count
    return result


def observation_at(replay: dict, step: int, seat: int) -> dict:
    state = replay["steps"][step][seat]
    observation = state.get("observation") or {}
    if isinstance(observation, str):
        observation = json.loads(observation)
    return observation


def observed_opponent_animals(observation: dict, target_seat: int) -> dict[str, int]:
    farms = observation.get("farms", []) or []
    opponent = farms[1 - target_seat]
    counts: dict[str, int] = {}
    for row in opponent.get("tiles", []) or []:
        for tile in row or []:
            animal = (
                str(tile.get("animal", "")).upper()
                if isinstance(tile, dict)
                else ""
            )
            if animal:
                counts[animal] = counts.get(animal, 0) + 1
    return counts


def outcome(target_bank: float, opponent_bank: float) -> float:
    if target_bank > opponent_bank:
        return 1.0
    if target_bank < opponent_bank:
        return 0.0
    return 0.5


def classify_replay(
    path: Path,
    target_names: tuple[str, ...],
    gate_step: int,
    gate_animals: dict[str, int],
) -> tuple[dict, LiveReplayMeta]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = player_names(replay)
    normalized_targets = {normalize_name(name) for name in target_names}
    matching_seats = [
        seat
        for seat, name in enumerate(names)
        if normalize_name(name) in normalized_targets
    ]
    if len(matching_seats) != 1:
        raise ValueError(
            f"expected one target seat in {path}, found {matching_seats}: {names}"
        )
    target_seat = matching_seats[0]
    opponent_seat = 1 - target_seat
    observation = observation_at(replay, gate_step, target_seat)
    animals = observed_opponent_animals(observation, target_seat)
    gate_active = all(
        animals.get(animal, 0) == count
        for animal, count in gate_animals.items()
    )
    rewards = [float(value or 0) for value in replay.get("rewards", [])]
    target_bank = rewards[target_seat]
    opponent_bank = rewards[opponent_seat]
    info = replay.get("info", {}) or {}
    return replay, LiveReplayMeta(
        episode_id=int(info.get("EpisodeId", replay.get("id", 0)) or 0),
        path=str(path.resolve()),
        seed=int(info.get("seed", 0) or 0),
        target_name=names[target_seat],
        target_seat=target_seat,
        opponent_name=names[opponent_seat],
        opponent_animals=animals,
        gate_active=gate_active,
        recorded_target_bank=target_bank,
        recorded_opponent_bank=opponent_bank,
        recorded_outcome=outcome(target_bank, opponent_bank),
    )


def donor_case(
    replay: dict,
    meta: LiveReplayMeta,
    generated_dir: Path,
) -> object:
    from tools.evaluate_top_replay_counterfactuals import DonorCase

    generated_dir.mkdir(parents=True, exist_ok=True)
    target_tape = generated_dir / (
        f"episode-{meta.episode_id}-seat-{meta.target_seat}.py"
    )
    opponent_seat = 1 - meta.target_seat
    opponent_tape = generated_dir / f"episode-{meta.episode_id}-seat-{opponent_seat}.py"
    if not target_tape.is_file():
        target_tape.write_text(render_agent(replay, meta.target_seat), encoding="utf-8")
    if not opponent_tape.is_file():
        opponent_tape.write_text(render_agent(replay, opponent_seat), encoding="utf-8")
    return DonorCase(
        episode_id=meta.episode_id,
        seed=meta.seed,
        target_seat=meta.target_seat,
        target_name=meta.target_name,
        target_rank=0,
        target_submission_id=0,
        target_tape=str(target_tape.resolve()),
        opponent_name=meta.opponent_name,
        opponent_tape=str(opponent_tape.resolve()),
        recorded_target_bank=meta.recorded_target_bank,
        recorded_opponent_bank=meta.recorded_opponent_bank,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", action="append", type=Path, default=[])
    parser.add_argument("--replay-dir", action="append", type=Path, default=[])
    parser.add_argument("--episode-id", action="append", type=int, default=[])
    parser.add_argument("--target-name", action="append", required=True)
    parser.add_argument("--gate-step", type=int, default=120)
    parser.add_argument("--gate-animal", action="append", default=[])
    parser.add_argument("--active-only", action="store_true")
    parser.add_argument("--classify-only", action="store_true")
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        gate_animals = parse_gate_animals(args.gate_animal)
    except ValueError as error:
        parser.error(str(error))

    paths = list(args.replay)
    for replay_dir in args.replay_dir:
        paths.extend(sorted(replay_dir.glob("episode-*-replay.json")))
    paths = sorted({path.resolve() for path in paths})
    episode_filter = set(args.episode_id)

    classified: list[tuple[dict, LiveReplayMeta]] = []
    for path in paths:
        replay, meta = classify_replay(
            path,
            tuple(args.target_name),
            args.gate_step,
            gate_animals,
        )
        if episode_filter and meta.episode_id not in episode_filter:
            continue
        classified.append((replay, meta))
    if not classified:
        parser.error("no matching replay files")

    live_cohort = {
        "target_names": args.target_name,
        "gate_step": args.gate_step,
        "gate_animals": gate_animals,
        "active_only": args.active_only,
        "total_replays": len(classified),
        "active_replays": sum(meta.gate_active for _, meta in classified),
        "recorded_wins": sum(meta.recorded_outcome == 1 for _, meta in classified),
        "recorded_losses": sum(meta.recorded_outcome == 0 for _, meta in classified),
        "replays": [asdict(meta) for _, meta in classified],
    }
    if args.classify_only:
        report = {
            "schema": "live-replay-cohort-v1",
            "live_cohort": live_cohort,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            json.dumps(
                console_cohort_summary(live_cohort),
                indent=2,
                ensure_ascii=False,
            )
        )
        print(f"report={args.output}")
        return

    from tools.evaluate_top_replay_counterfactuals import evaluate, parse_named_path

    try:
        candidates = dict(parse_named_path(value) for value in args.candidate)
    except ValueError as error:
        parser.error(str(error))

    selected = [
        pair for pair in classified if pair[1].gate_active or not args.active_only
    ]
    if not selected:
        parser.error("no active replay files")
    cases = [
        donor_case(replay, meta, args.generated_dir)
        for replay, meta in selected
    ]
    report = evaluate(cases, candidates, max(1, args.jobs))
    report["live_cohort"] = live_cohort
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            console_cohort_summary(report["live_cohort"]),
            indent=2,
            ensure_ascii=False,
        )
    )
    print(
        json.dumps(
            {
                name: payload["summary"]
                for name, payload in report["candidates"].items()
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
