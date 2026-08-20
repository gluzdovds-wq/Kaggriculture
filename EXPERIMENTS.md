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

Ten tests currently pass. Targeted fixtures cover the 719-executed-action
boundary, atomic seed over-demand, plant-day watering, ordered shed overflow,
zero-profit unchanged-market round trips, sparse animal feeding, action shape
and a full 720-state match. Two regression tests additionally guarantee that
arena timing instrumentation preserves both one- and two-argument agents.
