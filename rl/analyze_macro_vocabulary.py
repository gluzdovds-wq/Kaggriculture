"""Measure how compact the replay-derived Kaggriculture macro action space is.

The imitation datasets keep mechanics in the rule engine and reduce each joint
action to a task macro plus a market macro.  This audit reports vocabulary size
and top-k coverage both for every turn and for turns with a non-pass decision.
It is intended to gate a learned macro ranker, not to claim that the compressed
label is sufficient to execute the underlying worker actions.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Hashable, Iterable


Label = tuple[str, str]


def label_key(row: dict) -> Label:
    label = row.get("label") or {}
    return str(label.get("task_macro", "pass")), str(label.get("market_macro", "none"))


def is_decision(label: Label) -> bool:
    return label != ("pass", "none")


def top_k_coverage(counts: Counter[Hashable], k: int) -> float:
    total = counts.total()
    if not total:
        return 0.0
    return sum(count for _, count in counts.most_common(k)) / total


def summarize_counter(counts: Counter[Label]) -> dict:
    task_counts: Counter[str] = Counter()
    market_counts: Counter[str] = Counter()
    for (task, market), count in counts.items():
        task_counts[task] += count
        market_counts[market] += count
    return {
        "rows": counts.total(),
        "joint_vocabulary": len(counts),
        "task_vocabulary": len(task_counts),
        "market_vocabulary": len(market_counts),
        "top_k_joint_coverage": {
            str(k): top_k_coverage(counts, k) for k in (1, 2, 4, 8, 16, 32)
        },
        "top_k_task_coverage": {
            str(k): top_k_coverage(task_counts, k) for k in (1, 2, 4, 8, 16, 32)
        },
        "top_k_market_coverage": {
            str(k): top_k_coverage(market_counts, k) for k in (1, 2, 4, 8, 16, 32)
        },
        "top_labels": [
            {"task_macro": task, "market_macro": market, "count": count}
            for (task, market), count in counts.most_common(12)
        ],
    }


def summarize_rows(rows: Iterable[dict]) -> dict:
    by_agent: dict[str, Counter[Label]] = defaultdict(Counter)
    overall: Counter[Label] = Counter()
    for row in rows:
        agent = str(row.get("agent", "unknown"))
        label = label_key(row)
        by_agent[agent][label] += 1
        overall[label] += 1

    def payload(counts: Counter[Label]) -> dict:
        decisions = Counter({label: count for label, count in counts.items() if is_decision(label)})
        return {
            "all_turns": summarize_counter(counts),
            "decision_turns": summarize_counter(decisions),
            "decision_rate": decisions.total() / counts.total() if counts.total() else 0.0,
        }

    return {
        "overall": payload(overall),
        "agents": {agent: payload(counts) for agent, counts in sorted(by_agent.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    datasets = []
    for path in args.dataset:
        payload = json.loads(path.read_text(encoding="utf-8"))
        batch = payload.get("rows") or []
        rows.extend(batch)
        datasets.append({"path": str(path), "rows": len(batch)})

    report = {
        "schema": "macro-vocabulary-audit-v1",
        "datasets": datasets,
        **summarize_rows(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
