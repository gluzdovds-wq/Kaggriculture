# Current local solution

`main.py` is the current Kaggriculture submission candidate. The original
carrot baseline remains documented below as the execution/calibration anchor;
the promoted candidate is generated reproducibly from the public X544 agent
plus our observation-only H04 end-of-day harvest overlay.

## Promoted candidate

- Public base: `stevenleehans/kaggriculture-x544-nah-i-d-win` (X544/X562).
- Local change: at hour 23, replace only movement/PASS by HARVEST when the unit
  is already standing on a mature crop with available yield. Daily position
  reset and auto-drop preserve the next-day route.
- Generator: `tools/make_x544_variant.py --eod-harvest`.
- Packaging gate: the generator places a callable alias after all helpers so
  Kaggle's `get_last_callable` selects the intended wrapper. The test suite
  verifies this exact loader behavior and runs a full game from the file path.
- Local evidence: X544 won 16/16 against exact V36 (+10,417 average margin);
  X544+H04 won 6/6 against Soil (+8,459). It lost 0/6 against both Moon and
  ReadTown, so the candidate is a broad-policy promotion with a known
  adversarial-family weakness, not a claim of universal dominance.
- H04 itself is intentionally small: +5.2 average coins in the X544 paired
  trigger panel. The large expected improvement over S02 comes from the newer
  X544 route family, not from overstating the overlay.

To regenerate the exact entry point:

```powershell
C:\Users\Dmitry\.venvs\kg\Scripts\python.exe tools\make_x544_variant.py `
  research\public_agents\kaggriculture-x544-nah-i-d-win\main.py main.py `
  --eod-harvest
```

Corrected local candidate SHA-256:
`839d2244af3498541624a70c156bf8801c22838dc67eefa6641a9e97ca1f1efa`.
It has passed local validation but has not been submitted: S04 (`55652287`)
failed before play because the previous artifact exposed a helper as Kaggle's
last callable. See E016 in `EXPERIMENTS.md`.

## Original baseline strategy

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
