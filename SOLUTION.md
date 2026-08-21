# Current local solution

`main.py` is the current Kaggriculture submission candidate. The original
carrot baseline remains documented below as the execution/calibration anchor;
the promoted candidate combines the public-state route selector with bounded
own-state terminal and market-timing overlays.

## Promoted candidate

- Public branches: X544/X562 and Moon Counts Melons. They emit the same opening
  at step 0 and do not diverge until the first shop unlock at step 72.
- Original change (H22): after step 0, inspect only the opponent's public farm.
  An opening pasture selects Moon; otherwise select X544. The choice is then
  frozen for the season. No opponent private inventory or replay-only field is
  used.
- Moon's required step-0 initialization runs on a deep-copied observation and
  configuration with Python RNG restored afterward, so the discarded shadow
  call cannot mutate the live local opponent or its random stream.
- Both branches retain bounded weed-collision repair. A direct no-repair
  ablation (E021) fell to 0.34375 against each exact base, while all no-trigger
  games remained exactly neutral in final banks.
- H21 adds a Moon-only terminal pressure gate. If shed plus carried inventory
  is at least 90 on step 689, two fixed workers route to the shed, drop and sell
  before day-28 EOD. It removed the observed 12-WHEAT overflow and added +577
  coins per seat on the audited seed; all X544 and low-pressure transfer games
  stayed exactly neutral.
- N03 advances only an already scheduled FERTILIZER sale by one turn, capped at
  10 units, then subtracts the same quantity from the next turn. A per-seat debt
  ledger carries any unpaid amount forward, so the overlay changes timing but
  not scheduled quantity. It runs only on steps 120–714.
- On an exact eight-family transfer panel, N03 had no outcome regression and
  improved every same-seed family margin by +1.5 to +134. A separate four-seed,
  both-seat holdout preserved public-family outcomes and added +50.75 to
  +139.75 average margin; telemetry recorded 65 advanced and 65 repaid units.
- Frozen holdout: 4 untouched seeds × both seats × 8 opponent families for
  each candidate (64 games each). Macro/micro outcome rose from 0.390625 for
  fixed X544 to 0.78125; average margin rose from +274 to +3,192; worst-family
  outcome rose from 0 to 0.375. V36 and Soil banks were exactly unchanged.
- Runtime/artifact gate: 23/23 tests, `py_compile`, official
  `get_last_callable`, and path-loaded full games against V36 and Moon all
  pass. Maximum observed action time on the frozen panel was 143 ms.

To regenerate the exact entry point:

```powershell
C:\Users\Dmitry\.venvs\kg\Scripts\python.exe tools\make_family_selector.py `
  research\public_agents\kaggriculture-x544-nah-i-d-win\main.py `
  research\public_agents\kaggriculture-frontier-the-moon-counts-melons\main.py `
  research\generated\h22-selector-base.py
C:\Users\Dmitry\.venvs\kg\Scripts\python.exe tools\make_terminal_route_variant.py `
  research\generated\h22-selector-base.py main.py `
  --actor 1 --actor 2 --start-step 689 --min-total 90 --route moon
C:\Users\Dmitry\.venvs\kg\Scripts\python.exe tools\make_market_timing_variant.py `
  main.py main.py --items FERTILIZER --fertilizer-cap 10 `
  --start 120 --stop 715 --label n13_fert10
```

Current promoted artifact: 309,836 bytes, SHA-256
`4ddec3eafa9840e4bb7b07b9d37d4af2835c8bbcf8cf2411c776f96e662788aa`.
It is byte-identical to the E028–E033 tested candidate. Final preflight passed
26/26 unit tests, `py_compile`, official last-callable loading and full games on
both selector branches; observed maximum action latency was 62.76 ms.

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
diagnostic margins, per-action latency, optional agent telemetry, observable
shop-unlock history and public-only opponent route checkpoints at steps
1/12/24/48/72.
Use `--jobs N` for independent local worker processes; the arena pins
`PYTHONHASHSEED=0` before spawning them.

Use `tools/compare_openings.py` to find the exact first action divergence of
compatible public routes. Shadow calls receive deep-copied observations and
restore Python's global RNG, so this diagnostic does not perturb the live route.

Use `tools/audit_overflow.py` when testing storage changes. It measures the
exact items discarded by the official EOD drop; the arena's lighter pressure
counter is only a trigger screen because same-turn sales can remove apparent
pressure before the drop.

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
