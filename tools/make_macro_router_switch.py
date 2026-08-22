"""Append the frozen reactive macro router to a self-contained base agent."""

from __future__ import annotations

import argparse
from pathlib import Path


SUFFIX = """

# Frozen compatible macro-router wrapper.  Package macro_router_runtime.py
# beside this main.py for local/Kaggle execution.
from macro_router_runtime import wrap_agent as _macro_wrap_agent
agent = _macro_wrap_agent(agent, checkpoints={checkpoints})
__version__ = "{version}"
macro_router_kaggle_entrypoint = agent
"""


def render(source: str, checkpoints: tuple[int, ...]) -> str:
    if not checkpoints or any(value not in (360, 600, 648) for value in checkpoints):
        raise ValueError("checkpoints must be a non-empty subset of 360, 600, 648")
    if tuple(sorted(set(checkpoints))) != checkpoints:
        raise ValueError("checkpoints must be unique and increasing")
    if "def agent(" not in source:
        raise ValueError("base source has no agent")
    label = "-".join(str(value) for value in checkpoints)
    version = f"macro-router-e109-cp{label}"
    return source.rstrip() + SUFFIX.format(
        checkpoints=repr(checkpoints), version=version
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoints", type=int, nargs="+", required=True)
    args = parser.parse_args()
    rendered = render(
        args.source.read_text(encoding="utf-8"), tuple(args.checkpoints)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
