"""Build a single-file Shop Guard variant with the fertilizer exposure guard.

The source notebook artifact already bundles the complete runtime.  This
generator performs one auditable configuration change and refuses to write an
output if the expected frozen source is not found exactly once.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--wheat-market-maker", action="store_true")
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    replacements = {
        '"""Adaptive Shop Guard for Kaggriculture."""':
            '"""Adaptive Shop Guard with fertilizer exposure preemption."""',
        "'exposure_preempt': False": "'exposure_preempt': True",
    }
    for old, new in replacements.items():
        count = source.count(old)
        if count != 1:
            raise SystemExit(f"expected exactly one {old!r}, found {count}")
        source = source.replace(old, new, 1)

    if args.wheat_market_maker:
        old = "'wheat_market_maker': False"
        if source.count(old) != 1:
            raise SystemExit(f"expected exactly one {old!r}")
        source = source.replace(old, "'wheat_market_maker': True", 1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
