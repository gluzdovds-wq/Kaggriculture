"""Educational one-state RL example on the real Kaggriculture environment.

The learner treats a whole farming policy as a macro action and learns its
expected terminal win reward with epsilon-greedy Q-learning.  This is small
enough to understand and run locally; it is a teaching example, not the main
competitive agent.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import random
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]
CROP_DATA = {
    "WHEAT": {"seed": 10, "max_yield_day": 4},
    "CARROT": {"seed": 20, "max_yield_day": 3},
    "MELON": {"seed": 80, "max_yield_day": 10},
}
POLICIES = [
    ("wheat-h3", "WHEAT", 3),
    ("wheat-h5", "WHEAT", 5),
    ("carrot-h3", "CARROT", 3),
    ("carrot-h5", "CARROT", 5),
    ("carrot-h7", "CARROT", 7),
    ("melon-h7", "MELON", 7),
]


def load_policy(crop: str, hands: int, episode: int):
    spec = importlib.util.spec_from_file_location(f"rl_policy_{episode}", ROOT / "main.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = CROP_DATA[crop]
    module.CROP = crop
    module.SEED_PRICE = data["seed"]
    module.MAX_YIELD_DAY = data["max_yield_day"]
    module.HANDS_PER_DAY = hands
    module.LAST_PLANTING_DAY = 29 - data["max_yield_day"]
    return module.agent


def terminal_reward(ours: float, theirs: float) -> float:
    if ours > theirs:
        return 1.0
    if ours < theirs:
        return 0.0
    return 0.5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=12)
    parser.add_argument("--epsilon", type=float, default=0.25)
    parser.add_argument("--alpha", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--opponent", choices=("starter", "random", "pass"), default="starter")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "rl_bandit.json")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    q = {name: 0.5 for name, _, _ in POLICIES}
    visits = {name: 0 for name, _, _ in POLICIES}
    history = []

    for episode in range(args.episodes):
        explore = rng.random() < args.epsilon
        if explore:
            selected = rng.choice(POLICIES)
        else:
            best_q = max(q.values())
            selected = rng.choice([policy for policy in POLICIES if q[policy[0]] == best_q])
        name, crop, hands = selected
        seat = episode % 2
        policy = load_policy(crop, hands, episode)
        players = [policy, args.opponent] if seat == 0 else [args.opponent, policy]
        env = make("kaggriculture", configuration={"seed": args.seed + episode}, debug=False)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env.run(players)
        final = env.steps[-1]
        ours = float(final[seat].reward)
        theirs = float(final[1 - seat].reward)
        reward = terminal_reward(ours, theirs)
        old_q = q[name]
        q[name] += args.alpha * (reward - q[name])
        visits[name] += 1
        row = {
            "episode": episode,
            "policy": name,
            "seat": seat,
            "explore": explore,
            "reward": reward,
            "ours": ours,
            "theirs": theirs,
            "q_before": old_q,
            "q_after": q[name],
        }
        history.append(row)
        print(
            f"episode={episode:02d} policy={name:10s} seat={seat} "
            f"reward={reward:.1f} bank={ours:.0f}:{theirs:.0f} Q={q[name]:.3f}"
        )

    ranking = sorted(q, key=lambda name: (q[name], visits[name]), reverse=True)
    result = {
        "algorithm": "epsilon-greedy one-state Q-learning",
        "opponent": args.opponent,
        "episodes": args.episodes,
        "epsilon": args.epsilon,
        "alpha": args.alpha,
        "q": q,
        "visits": visits,
        "ranking": ranking,
        "history": history,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"best={ranking[0]} Q={q[ranking[0]]:.3f}; report={args.output}")


if __name__ == "__main__":
    main()

