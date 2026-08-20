# First local solution

`main.py` is a deterministic, stateless carrot-farming baseline for the
Kaggriculture competition.

## Strategy

- Buy enough carrot seed to fill the unlocked 5x5 field.
- Hire five inexpensive farm hands at the beginning of every day.
- Prioritize watering, then ripe harvesting, weeds, and new planting.
- Assign distinct nearby jobs to units to avoid duplicate actions.
- Stop planting when a crop can no longer mature before the season ends.
- Return carried produce to the shed on the final day and sell shed stock on
  every turn.

## Local evaluation

Use the dedicated Kaggle Python environment:

```powershell
C:\Users\Dmitry\.venvs\kg\Scripts\python.exe evaluate.py --opponent starter --games 4
C:\Users\Dmitry\.venvs\kg\Scripts\python.exe -m unittest discover -s tests -v
```

Each seed is tested from both player seats. Add `--replay-dir artifacts/replays`
to keep replay JSON files for inspection.

For outcome-based evaluation against one or more real agent files, use
`arena.py`. It records exact hashes, paired outcomes, bootstrap intervals,
diagnostic margins and per-action latency.

The competition submission entry point is `main.py`. Local validation and Git
synchronization do not submit the agent to Kaggle.

## Baseline results

Measured locally with `kaggle-environments==1.32.7` on 2026-08-20:

- official `starter`: 8/8 wins across four seeds and both seats; average score
  11,640 and average margin +8,407.9;
- official `random`: 4/4 wins across two seeds and both seats; average score
  8,666 and average margin +8,666;
- direct Kaggle-style loading with `env.run(["main.py", "starter"])`: both
  agents finished with `DONE`, scoring 8,220 vs 3,109.

These local scores validate execution and provide a regression baseline; they
do not predict the public or private leaderboard score.

The first online calibration confirmed this limitation: the carrot baseline
won every built-in match but entered the live ladder around rating 600 and then
moved substantially as games accumulated. See `EXPERIMENTS.md` for timestamped
observations and the exact public-agent calibration.

For a Russian educational introduction to the game and a runnable first RL
example, see `RL_GUIDE_RU.md` and `rl/train_bandit.py`.
