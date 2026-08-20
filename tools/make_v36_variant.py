"""Create a reproducible V36 config-only ablation without executing its code."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


CONFIG_KEYS = {
    "clone_horizon",
    "clone_detection_start",
    "clone_active_stop",
    "clone_distance_threshold",
    "clone_streak_required",
    "maximum_sell_batch",
    "maximum_market_orders",
    "market_item",
    "market_quantity",
    "market_reserve",
    "market_start",
    "market_stop",
    "feed_days_reserve",
    "investment_horizon",
    "shed_headroom",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--set", dest="changes", action="append", required=True, metavar="KEY=VALUE"
    )
    parser.add_argument("--append-overlay", type=Path)
    args = parser.parse_args()

    text = args.source.read_text(encoding="utf-8")
    for change in args.changes:
        key, separator, raw_value = change.partition("=")
        if not separator or key not in CONFIG_KEYS:
            raise ValueError(f"unsupported config change: {change!r}")
        value = ast.literal_eval(raw_value)
        replacement = f"    {key}={value!r},"
        pattern = rf"(?m)^    {re.escape(key)}=.*,$"
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise ValueError(f"expected exactly one assignment for {key}, got {count}")

    if args.append_overlay:
        overlay = args.append_overlay.read_text(encoding="utf-8")
        text = text.rstrip() + "\n\n" + overlay.rstrip() + "\n"

    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(text, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
