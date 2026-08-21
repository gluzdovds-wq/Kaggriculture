"""Extract one public Kaggle replay seat as a deterministic action-tape agent.

Kaggle stores the action selected for observation step ``t`` in replay state
``steps[t + 1]``.  Replaying that tape on the original public seed provides an
exact opponent control for counterfactual candidate tests.  The tape is not a
general reconstruction of the hidden source policy and must not be evaluated
as if it were one on unrelated states or seeds.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def actions_by_observation_step(payload: dict, seat: int) -> list[dict]:
    steps = payload.get("steps", [])
    if len(steps) < 2:
        raise ValueError("replay must contain at least two states")
    if seat not in (0, 1):
        raise ValueError("seat must be 0 or 1")
    actions = []
    for next_state in steps[1:]:
        if len(next_state) <= seat:
            raise ValueError("replay state lacks requested seat")
        action = next_state[seat].get("action") or PASS
        actions.append(action)
    return actions


def render_agent(payload: dict, seat: int) -> str:
    actions = actions_by_observation_step(payload, seat)
    names = payload.get("info", {}).get("TeamNames", []) or []
    source_name = names[seat] if len(names) > seat else f"seat-{seat}"
    episode_id = payload.get("info", {}).get("EpisodeId", payload.get("id"))
    seed = payload.get("info", {}).get("seed")
    compact = json.dumps(actions, separators=(",", ":"), ensure_ascii=False)
    return f'''"""Action tape extracted from public Kaggle episode {episode_id}."""

import copy as _replay_copy

_REPLAY_ACTIONS = {compact}
_REPLAY_PASS = {{"farmer": ["PASS"], "hands": [], "market": []}}
__source_episode__ = {episode_id!r}
__source_agent__ = {source_name!r}
__source_seed__ = {seed!r}
__version__ = "public-replay-tape-{episode_id}-seat-{seat}"


def agent(obs, configuration=None):
    if isinstance(obs, dict):
        step = int(obs.get("step", 0) or 0)
    else:
        step = int(getattr(obs, "step", 0) or 0)
    action = _REPLAY_ACTIONS[step] if 0 <= step < len(_REPLAY_ACTIONS) else _REPLAY_PASS
    return _replay_copy.deepcopy(action)
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--seat", type=int, choices=(0, 1), required=True)
    args = parser.parse_args()

    payload = json.loads(args.replay.read_text(encoding="utf-8"))
    source = render_agent(payload, args.seat)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(source, encoding="utf-8")
    print(args.destination)


if __name__ == "__main__":
    main()
