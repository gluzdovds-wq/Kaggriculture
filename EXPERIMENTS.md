# Experiment log

This local log mirrors the reproducible parts of the online Google Sheets
`Experiments` tab. Ladder ratings are timestamped snapshots because they move
as new matches are played.

## E001 — carrot-baseline-v1 / submission S01

- Commit: `9b0acd0`
- Kaggle submission: `55650390`
- Hypotheses: G03, G05
- Local protocol: four seeds × both seats against `starter`; two seeds × both
  seats against `random`.
- Local result: 8/8 and 4/4 wins respectively. Average bank was 11,640 against
  `starter` and 8,666 against `random`.
- Exact entry-point check: `env.run(["main.py", "starter"])` completed `DONE`
  with 8,220 vs 3,109.
- LB snapshots: 600.0 initially, then 496.9, 552.8 and 451.6 while the ladder
  continued to schedule games.
- Observation: built-in win rate has essentially no resolution at competitive
  strength; a single ladder value is also not a fixed target.
- Decision: reject as competitive incumbent, retain as a lower calibration
  anchor.

## E002 — exact public V36 / submission S02

- Public source: `kaitofukami/106-130-multi-generation-v36-robust-hybrid`
- Exact `main.py` SHA-256:
  `47ebf29039463dc0eb803ccf38d5a6f0c130d2b49f3698b20c53f495c1062dc8`
- Kaggle submission: `55650633`
- Hypotheses: G03, G04, G05
- Initial local protocol: two seeds × both seats against current public
  multi-route, adaptive, choose-farm and V16 agents.
- Invalidated result: the first instrumented run accidentally hid the official
  configuration argument from two-argument agents. Kaggle itself receives the
  configuration correctly, so these cross-play numbers are not evidence for
  S02 and must be recomputed after the arena fix.
- Corrected local protocol: two seeds × both seats against current public
  multi-route, adaptive, choose-farm and V16 agents. V36 scored 50% paired
  outcomes against each of the first three, with average margins from +2,650
  to +3,070 coins, and 100% with +7,113 against V16. The first three 95%
  bootstrap intervals remain [0, 1], so this is a smoke test rather than a
  ranking claim. Artifact: `artifacts/arena/v36-public-pool-2seeds-corrected.json`.
- Observation: exact execution parity includes the callable signature, not
  only identical source bytes. Instrumentation can change policy behavior.
- Decision: use as a public-ceiling LB calibration point. Do not treat it as a
  proven best public policy until the corrected pairs are expanded.
- LB snapshot: 717.7 after completion. The S01 snapshot at the same poll was
  385.1, for a +332.6 separation between the public ceiling and trivial anchor.

## Engine/runtime gate progress

Thirteen tests currently pass. Targeted fixtures cover the 719-executed-action
boundary, atomic seed over-demand, plant-day watering, ordered shed overflow,
zero-profit unchanged-market round trips, sparse animal feeding, action shape
and a full 720-state match. Two regression tests additionally guarantee that
arena timing instrumentation preserves both one- and two-argument agents.

## E003 — fast simulator 1.32.7 patch / no submission

- Hypothesis: G02.
- Change: safely extracted the public 1.32.6 C++ port and added the official
  1.32.7 hinge price shape for CARROT, TOMATO and EGG.
- Protocol: step-level comparison of money and all market inventories against
  official 1.32.7 traces.
- Result: 13/13 episodes and 9,347/9,347 transitions exact, including four
  V36↔multi-route competitive traces in both seat orders.
- Runtime: about 441 episodes/s (2.27 ms/episode) with MSVC on this PC.
- Decision: partial pass. Use for transition checks and search, but confirm
  promoted policies in the official Python arena.

## E004 — H12 non-producible hinge arbitrage / rejected implementation

- Hypothesis: H12 (JIT CARROT/TOMATO/EGG under 1.32.7 scarcity).
- Minimal experiment: append BUY_PRODUCT→town demand→SELL round trips to V36.
- Targeted seed selection: a 5,000-seed fast scan selected `20260619`, where
  CARROT reaches about 8,760 inventory and a quote near 994.
- Result: emitted orders produced no bank change. Official trace inspection
  showed they were silent no-ops.
- Root cause: official `_process_market` accepts `BUY_PRODUCT` only for WHEAT
  and FERTILIZER. Crops and eggs must be produced, not bought.
- Decision: reject and delete this implementation, not the economic H12 idea.
  Add a regression fixture; redesign H12 as actual JIT farming.

## E005 — H16 clone SELL preemption ablation / no submission

- Change: set `clone_detection_start=999`, leaving the V36 route and all other
  overlays unchanged.
- Protocol: two new seeds × both seats directly against exact V36.
- Result: 0/4 outcomes, average margin -2,331 and worst margin -3,206.
- Telemetry: exact V36 latched after the public-state clone streak and shifted
  roughly 580 route sell units; the ablation did not.
- Decision: strong causal pass for H16. Retain latched one-turn preemption.

## E006 — H17 market-maker feed reserve ablation / no submission

- Change: `feed_days_reserve=0` instead of 2; all other bytes are unchanged.
- Protocol: six seeds × both seats directly against exact V36 (two development,
  four untouched holdout).
- Result: paired outcome 0.75 and average margin +2.5 coins, but worst seat was
  -3,069. On that seed the opposite seat was +3,073, revealing strong order
  interaction rather than robust gain.
- Telemetry: one extra 9-unit WHEAT round-trip on a representative seed;
  expected edge +1 and observed paired edge only a few coins.
- Decision: do not promote. The tiny mean does not justify removing a feed
  safety reserve with a large worst-seat excursion.

## E007 — H02 CARE sparsity ablation / no submission

- Changes: (a) replace every route CARE with PASS; (b) replace CARE with PASS
  only on odd-numbered days. No freed action was reassigned, so this estimates
  the bonus value that a future scheduler must beat.
- Protocol: one new seed × both seats against exact V36.
- Result: no-CARE lost both seats by an average 93,992 coins; alternating-day
  CARE lost both by 19,876.
- Mechanism: every fed+cared day adds to `pending_care_bonus`; the accumulated
  bonus is consumed on a later fed production day. Non-production care days are
  therefore not automatically waste.
- Decision: reject naive sparse CARE for the V36 animal route. Keep the separate
  feed-parity/terminal-abandonment part of H02 open.

## E008 — H01/H03/H10 engine mechanisms / no submission

- H01: after a watered day, one dry day leaves a plant alive; the second
  consecutive dry day turns it into a weed.
- H03: two colocated units can execute PLANT→WATER in one turn and the new
  plant ends that turn watered.
- H10: an animal still exposes daily fertilizer after its first unfed day,
  before escaping on the second.
- Result: all targeted fixtures pass; full suite 13/13.
- Decision: mechanism pass only. Each policy-level economic claim still needs
  a paired route/planner experiment.

## E009 — H14/H15 wider reserve-safe WHEAT batching / submission S03

- Change: `market_quantity=20` instead of 10 in exact public V36. Cash, feed,
  investment, capacity and market-order reserves are unchanged.
- Candidate SHA-256:
  `8c27bc4e0f95bb56a188b43ee4624a7b04cfdabe8a53f850a19a5b1bfc76f92c`.
- Kaggle submission: `55651309` (submitted 2026-08-20 17:29 UTC; score pending
  at the time of this entry).
- Protocol against exact V36: two development and four untouched holdout seeds,
  both seats for every seed.
- Result: 9/12 wins, paired outcome 0.75 and average margin about +67 coins.
  The four-seed holdout alone produced outcome 0.75 and +61.9 average margin.
- Public-pool check: on matched games against multi-route, adaptive and
  choose-farm, the candidate improved average margin by +127 to +134 coins over
  exact V36 without changing the per-style paired outcome.
- Alternative: quantity 40 also scored 0.75 in a smaller screen, but improved
  average margin by only +70.8 versus +78.2 for quantity 20 on the same screen.
- Decision: promote quantity 20 to S03 for local-to-LB calibration. Do not
  spend S04 until S03 and S02 can be compared in the same LB snapshot.
- Same-poll pre-result LB snapshot: S02 1447.6, S01 325.3. These differ sharply
  from earlier snapshots, confirming that absolute public scores are dynamic.
