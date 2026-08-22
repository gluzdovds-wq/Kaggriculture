"""Verify exact Python/C++ parity for all frozen N75 legal leaf features."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import tempfile

try:
    from rl.audit_hidden_state import replay_paths
    from rl.evaluate_leaf_value import legal_value_features
    from rl.evaluate_macro_plan_recall import export_replay_trace
except ModuleNotFoundError:
    from audit_hidden_state import replay_paths  # type: ignore
    from evaluate_leaf_value import legal_value_features  # type: ignore
    from evaluate_macro_plan_recall import export_replay_trace  # type: ignore


def native_features(
    engine: Path, trace: Path, checkpoint: int, seat: int
) -> dict[str, float]:
    completed = subprocess.run(
        [
            str(engine.resolve()),
            str(trace.resolve()),
            "--root-features",
            str(checkpoint),
            str(seat),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output: dict[str, float] = {}
    expected_index = 0
    for row in csv.DictReader(completed.stdout.splitlines(), delimiter="\t"):
        index = int(row["index"])
        if index != expected_index:
            raise ValueError(f"native feature index {index} != {expected_index}")
        name = str(row["feature"])
        if name in output:
            raise ValueError(f"duplicate native feature {name}")
        output[name] = float(row["value"])
        expected_index += 1
    if not output:
        raise ValueError("native engine returned no features")
    return output


def verify(
    engine: Path,
    paths: list[Path],
    checkpoints: tuple[int, ...],
    tolerance: float,
    work_dir: Path,
) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    comparisons = 0
    feature_comparisons = 0
    maximum_error = 0.0
    maximum_location = None
    episode_ids = []
    for path in paths:
        replay = json.loads(path.read_text(encoding="utf-8"))
        episode_id = int((replay.get("info", {}) or {}).get("EpisodeId", 0) or 0)
        if not episode_id:
            raise ValueError(f"missing EpisodeId: {path}")
        episode_ids.append(episode_id)
        trace = work_dir / f"episode-{episode_id}.trace"
        export_replay_trace(replay, trace)
        steps = list(replay.get("steps", []) or [])
        for checkpoint in checkpoints:
            if checkpoint < 0 or checkpoint >= len(steps) - 1:
                raise ValueError(
                    f"episode {episode_id}: checkpoint {checkpoint} outside trace"
                )
            for seat in (0, 1):
                observation = dict(
                    steps[checkpoint][seat].get("observation", {}) or {}
                )
                expected = legal_value_features(observation)
                actual = native_features(engine, trace, checkpoint, seat)
                if tuple(actual) != tuple(expected):
                    missing = sorted(set(expected) - set(actual))
                    extra = sorted(set(actual) - set(expected))
                    raise AssertionError(
                        f"episode {episode_id} c{checkpoint} s{seat}: "
                        f"feature order/set mismatch; missing={missing}, extra={extra}"
                    )
                for name, wanted in expected.items():
                    error = abs(float(actual[name]) - float(wanted))
                    if error > maximum_error:
                        maximum_error = error
                        maximum_location = {
                            "episode_id": episode_id,
                            "checkpoint": checkpoint,
                            "seat": seat,
                            "feature": name,
                            "python": float(wanted),
                            "native": float(actual[name]),
                        }
                    if error > tolerance:
                        raise AssertionError(
                            f"episode {episode_id} c{checkpoint} s{seat} {name}: "
                            f"native={actual[name]:.17g}, python={wanted:.17g}, "
                            f"error={error:.3g} > {tolerance:.3g}"
                        )
                    feature_comparisons += 1
                comparisons += 1
    return {
        "schema": "kaggriculture-native-leaf-feature-parity-v1",
        "replay_count": len(paths),
        "episode_ids": episode_ids,
        "checkpoints": list(checkpoints),
        "seat_checkpoint_cases": comparisons,
        "feature_count": feature_comparisons // comparisons if comparisons else 0,
        "feature_comparisons": feature_comparisons,
        "tolerance": tolerance,
        "max_absolute_error": maximum_error,
        "max_error_location": maximum_location,
        "pass": maximum_error <= tolerance,
        "contract": {
            "python": "legal_value_features(controlled observation)",
            "native": "controlled farm private plus public farms/market/town",
            "forbidden": "opponent private, replay actions after root, identity, EpisodeId, source seed",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--checkpoint", action="append", type=int)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.engine.is_file():
        parser.error(f"engine not found: {args.engine}")
    paths = replay_paths(args.replays)
    checkpoints = tuple(args.checkpoint or (24, 360, 600, 648))
    if args.work_dir:
        report = verify(
            args.engine, paths, checkpoints, args.tolerance, args.work_dir
        )
    else:
        with tempfile.TemporaryDirectory(prefix="kag-leaf-parity-") as value:
            report = verify(
                args.engine,
                paths,
                checkpoints,
                args.tolerance,
                Path(value),
            )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
