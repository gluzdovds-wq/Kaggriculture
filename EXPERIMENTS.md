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
- Local protocol: two seeds × both seats against current public multi-route,
  adaptive, choose-farm and V16 agents.
- Local result: 50% paired outcome against each of the three fresh styles and
  100% against V16. Average margins were +3,070, +3,070, +2,650.5 and +7,108.8.
- Runtime: 16 full games completed; median per-game candidate p99 was 1.55 ms,
  maximum observed action was 98.25 ms.
- Observation: outcomes against fresh public agents changed sign across only
  two seeds, leaving bootstrap intervals at `[0, 1]`. One or two seeds cannot
  select a submission reliably.
- Decision: use as a public-ceiling LB calibration point. Do not treat it as a
  proven best public policy until the disputed pairs are expanded.
- LB status: pending at the time of this log entry.

## Engine/runtime gate progress

Eight tests currently pass. Targeted fixtures cover the 719-executed-action
boundary, atomic seed over-demand, plant-day watering, ordered shed overflow,
zero-profit unchanged-market round trips, sparse animal feeding, action shape
and a full 720-state match.

