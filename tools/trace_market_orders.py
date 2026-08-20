"""Print before/action/after transitions for selected market products."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def load_agent(path: Path):
    spec = importlib.util.spec_from_file_location("market_trace_candidate", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("opponent")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    parser.add_argument("--items", default="CARROT,TOMATO,EGG")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    players = [load_agent(args.candidate.resolve()), args.opponent]
    if args.seat == 1:
        players.reverse()
    env = make("kaggriculture", configuration={"seed": args.seed}, debug=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(players)
    selected = set(args.items.split(","))
    rows = []
    for step in range(len(env.steps) - 1):
        action = env.steps[step + 1][args.seat].action or {}
        orders = [
            list(order)
            for order in (action.get("market") or [])
            if len(order) >= 3 and str(order[1]) in selected
        ]
        if not orders:
            continue
        before = env.steps[step][args.seat].observation
        after = env.steps[step + 1][args.seat].observation
        rows.append(
            {
                "step": step,
                "orders": orders,
                "money": [before.farms[args.seat]["money"], after.farms[args.seat]["money"]],
                "shed": [
                    {item: before.private["shed"].get(item, 0) for item in selected},
                    {item: after.private["shed"].get(item, 0) for item in selected},
                ],
                "market_inventory": [
                    {item: before.market["inventory"].get(item) for item in selected},
                    {item: after.market["inventory"].get(item) for item in selected},
                ],
                "market_price": [
                    {item: before.market["prices"].get(item) for item in selected},
                    {item: after.market["prices"].get(item) for item in selected},
                ],
            }
        )
        if len(rows) >= args.limit:
            break
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
