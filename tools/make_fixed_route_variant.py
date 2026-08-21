"""Freeze the H22 selector to one compatible route for causal A/B tests.

The generated agent keeps the exact common step-0 opening and all overlays in
the source artifact.  Only the step-1 selector decision is replaced.  This is
useful for learning or validating an opponent-conditioned macro selector
without confounding the comparison with a different opening or executor.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SELECTOR_BLOCK = '''        pasture_opening = _selector_opponent_has_opening_pasture(obs)
        _SELECTED_ROUTE = "moon" if pasture_opening else "x544"
'''


def freeze_route(source: str, route: str) -> str:
    if source.count(SELECTOR_BLOCK) != 1:
        raise ValueError("expected exactly one H22 selector block")
    replacement = f'''        pasture_opening = _selector_opponent_has_opening_pasture(obs)
        _SELECTED_ROUTE = {route!r}
'''
    frozen = source.replace(SELECTOR_BLOCK, replacement, 1)
    versions = list(re.finditer(
        r'^__version__ = "([^"\r\n]+)"$', frozen, flags=re.MULTILINE
    ))
    if not versions:
        raise ValueError("expected at least one version marker")
    final = versions[-1]
    replacement = f'__version__ = "{final.group(1)}-fixed-{route}"'
    return frozen[:final.start()] + replacement + frozen[final.end():]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--route", choices=("x544", "moon"), required=True)
    args = parser.parse_args()

    generated = freeze_route(args.source.read_text(encoding="utf-8"), args.route)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(generated, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
