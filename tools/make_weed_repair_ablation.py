"""Create a causal no-weed-repair ablation for Moon or embedded-X544 agents."""

from __future__ import annotations

import argparse
from pathlib import Path


MOON_OVERLAY = r'''
# Generated H09 ablation. The original repair is still evaluated only to count
# interventions, but its action is discarded; route, market, RNG and all other
# overlays remain unchanged.
import copy as _h09_copy
_H09_ORIGINAL_REPAIR = _weed_repair_action
_H09_TELEMETRY = {
    "calls": 0,
    "changed_actions": 0,
    "first_changed_step": None,
    "changed_steps": [],
}


def _weed_repair_action(obs, action, step):
    baseline = _align_hands(_h09_copy.deepcopy(action), obs)
    repaired = _H09_ORIGINAL_REPAIR(obs, _h09_copy.deepcopy(action), step)
    _H09_TELEMETRY["calls"] += 1
    if repaired != baseline:
        _H09_TELEMETRY["changed_actions"] += 1
        if _H09_TELEMETRY["first_changed_step"] is None:
            _H09_TELEMETRY["first_changed_step"] = int(step)
        if len(_H09_TELEMETRY["changed_steps"]) < 64:
            _H09_TELEMETRY["changed_steps"].append(int(step))
    return baseline


agent.telemetry = _H09_TELEMETRY
__version__ = "H09-moon-no-weed-repair-v1"
kaggle_entrypoint = agent
'''


X544_OVERLAY = r'''
# Generated H09 ablation for the repair inside embedded X540. As above, the
# counterfactual repair is evaluated for telemetry but its action is discarded.
import copy as _h09_copy
_H09_ORIGINAL_REPAIR = _X540_NS["_weed_repair_action"]
_H09_ALIGN_HANDS = _X540_NS["_align_hands"]
_H09_TELEMETRY = {
    "calls": 0,
    "changed_actions": 0,
    "first_changed_step": None,
    "changed_steps": [],
}


def _h09_no_weed_repair(obs, action, step):
    baseline = _H09_ALIGN_HANDS(_h09_copy.deepcopy(action), obs)
    repaired = _H09_ORIGINAL_REPAIR(obs, _h09_copy.deepcopy(action), step)
    _H09_TELEMETRY["calls"] += 1
    if repaired != baseline:
        _H09_TELEMETRY["changed_actions"] += 1
        if _H09_TELEMETRY["first_changed_step"] is None:
            _H09_TELEMETRY["first_changed_step"] = int(step)
        if len(_H09_TELEMETRY["changed_steps"]) < 64:
            _H09_TELEMETRY["changed_steps"].append(int(step))
    return baseline


_X540_NS["_weed_repair_action"] = _h09_no_weed_repair
agent.telemetry = _H09_TELEMETRY
__version__ = "H09-x544-no-weed-repair-v1"
kaggle_entrypoint = agent
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--layout", choices=("moon", "x544"), required=True)
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    required = "def _weed_repair_action" if args.layout == "moon" else "_X540_NS"
    if required not in source:
        raise ValueError(f"{args.source} does not look like a {args.layout} agent")
    overlay = MOON_OVERLAY if args.layout == "moon" else X544_OVERLAY
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        source.rstrip() + "\n\n" + overlay.lstrip(), encoding="utf-8"
    )
    print(args.destination)


if __name__ == "__main__":
    main()
