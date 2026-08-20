"""Find the first action divergence between public agents on one live route.

The first disagreement is exact: every shadow has seen the same public/private
observations as the live base up to that point.  Calls use deep copies and
restore Python's process-global RNG, matching the isolation required by a
single-file multi-route submission.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import inspect
import io
import json
import random
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def load(path: Path, tag: str):
    spec = importlib.util.spec_from_file_location(f"opening_{tag}", path.resolve())
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def call(agent, observation, configuration):
    positional = [
        parameter
        for parameter in inspect.signature(agent).parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) >= 2:
        return agent(observation, configuration)
    return agent(observation)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("shadow", type=Path, nargs="+")
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--opponent", default="starter")
    args = parser.parse_args()

    base = load(args.base, "base")
    shadows = {
        path.parent.name: load(path, f"shadow_{index}")
        for index, path in enumerate(args.shadow)
    }
    first_disagreement = {name: None for name in shadows}

    def diagnostic(observation, configuration=None):
        base_action = call(base, observation, configuration)
        for name, shadow in shadows.items():
            if first_disagreement[name] is not None:
                continue
            rng_state = random.getstate()
            try:
                shadow_action = call(
                    shadow,
                    copy.deepcopy(observation),
                    copy.deepcopy(configuration),
                )
            finally:
                random.setstate(rng_state)
            if shadow_action != base_action:
                first_disagreement[name] = {
                    "step": int(getattr(observation, "step", 0) or 0),
                    "day": int(getattr(observation, "day", 0) or 0),
                    "hour": int(getattr(observation, "hour", 0) or 0),
                    "shops": list((getattr(observation, "town", {}) or {}).get(
                        "unlocked_shops", []
                    )),
                    "base_action": base_action,
                    "shadow_action": shadow_action,
                }
        return base_action

    env = make("kaggriculture", configuration={"seed": args.seed}, debug=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run([diagnostic, args.opponent])
    print(json.dumps(first_disagreement, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
