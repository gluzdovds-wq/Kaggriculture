"""Run one official match and print telemetry reachable from an agent policy."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import inspect
import io
import json
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def load(path: Path):
    spec = importlib.util.spec_from_file_location("telemetry_candidate", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect(root) -> list[dict]:
    rows: list[dict] = []
    seen: set[int] = set()

    def visit(value, label: str) -> None:
        if id(value) in seen:
            return
        seen.add(id(value))
        telemetry = getattr(value, "telemetry", None)
        if isinstance(telemetry, dict):
            rows.append({"component": label, "telemetry": dict(telemetry)})
        if inspect.isfunction(value) and value.__closure__:
            for name, cell in zip(value.__code__.co_freevars, value.__closure__):
                try:
                    child = cell.cell_contents
                except ValueError:
                    continue
                if inspect.isfunction(child) or hasattr(child, "telemetry"):
                    visit(child, f"{label}.{name}")
        for attribute in ("expert", "inner_preemption"):
            child = getattr(value, attribute, None)
            if child is not None:
                visit(child, f"{label}.{attribute}")

    visit(root, "policy")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("opponent")
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()

    module = load(args.candidate.resolve())
    policy = getattr(module, "_V36_POLICY", module.agent)
    players = [module.agent, args.opponent]
    if args.seat == 1:
        players.reverse()
    env = make("kaggriculture", configuration={"seed": args.seed}, debug=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)
    final = env.steps[-1]
    other = 1 - args.seat
    report = {
        "seed": args.seed,
        "seat": args.seat,
        "candidate_bank": final[args.seat].reward,
        "opponent_bank": final[other].reward,
        "components": collect(module.agent) + (
            collect(policy) if policy is not module.agent else []
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
