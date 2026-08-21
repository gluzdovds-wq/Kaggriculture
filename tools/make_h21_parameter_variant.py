"""Create a mechanically verified H21 terminal-routing parameter variant."""

from __future__ import annotations

import argparse
import py_compile
from pathlib import Path


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one {old!r}, found {count}")
    return source.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, default=Path("main.py"))
    parser.add_argument("--actors", default="1,2")
    parser.add_argument("--start", type=int, default=689)
    parser.add_argument("--threshold", type=int, default=90)
    args = parser.parse_args()

    actors = tuple(int(value.strip()) for value in args.actors.split(",") if value.strip())
    if not actors or any(value < 0 for value in actors):
        parser.error("--actors must contain non-negative comma-separated indices")
    actors_literal = repr(actors)
    if len(actors) == 1:
        actors_literal = f"({actors[0]},)"

    source = args.source.read_text(encoding="utf-8")
    source = replace_once(source, "_H21_ACTORS = (1, 2)", f"_H21_ACTORS = {actors_literal}")
    source = replace_once(source, "_H21_START_STEP = 689", f"_H21_START_STEP = {args.start}")
    source = replace_once(source, "_H21_MIN_TOTAL = 90", f"_H21_MIN_TOTAL = {args.threshold}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    py_compile.compile(str(args.output), doraise=True)
    print(args.output)


if __name__ == "__main__":
    main()
