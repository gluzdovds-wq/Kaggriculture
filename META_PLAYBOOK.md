# Kaggriculture live meta playbook

Last updated: 2026-08-25 18:30 Asia/Novosibirsk.

This is the persistent evidence log for deciding which standalone policies are
robust enough for the live ladder.  It is intentionally separated from raw
experiment history: claims below must be tied to replay evidence and their
confidence must be stated.

## Current evidence base

- Current leaderboard snapshot: top ten ratings `2837.2..3070.6`; the live
  `2300` boundary was around ranks `214..221`.
- Two newest public replays were requested for each current top-ten submission,
  plus S20/v48 and S21/v43.  Duplicate pairings produced 19 unique replay files
  and 24 target-game observations.
- Equal-weight top-ten aggregates and matched winner/loser deltas are in
  `artifacts/top10-replay-meta-2026-08-25.json`.
- Exact leaderboard identities and submission IDs are in
  `research/top10_leaderboard_2026-08-25.json`.
- Replay download provenance is in
  `artifacts/top10-replay-manifest-2026-08-25.json`.
- The sample is small (roughly two public games per policy), so correlations
  are hypotheses for intervention tests, not causal conclusions.

## High-confidence common structure

Every sampled top-ten policy:

- unlocked exactly three quadrants and never bought the fourth;
- used no geese;
- ran a broad production loop rather than a single-product farm;
- used both cattle and sheep, with average peak counts `8.30` cows and `7.85`
  sheep;
- maintained substantial labor throughput (average peak hands `13.3`, average
  hires `278.9` over a game).

The top-ten equal-weight mean bought the first two extra quadrants at steps
`151.3` and `249.7`.  The top-five means were earlier: `143.4` and `242.1`.
S20/S21 were later at approximately `159` and `258.5`.  Earlier expansion is
therefore a credible direction, provided it is tested as a complete policy and
does not create an early cash or maintenance failure.

The top-ten production means per game were approximately:

- water `983`, care `342`, feed `352`, harvest `391`;
- fertilizer collection `342` and fertilize `302`;
- sales: wheat `807`, fertilizer `302`, strawberry `296`, milk `234`, wool
  `232`.

Absolute product volumes vary strongly between policies.  The robust signal is
the diversified production engine and continuous servicing, not one universal
sale mix.

## Matched-game signals (medium confidence)

Across 13 decisive top-ten-vs-top-ten games, winners relative to losers had on
average:

- `+1.38` peak cows and `-0.54` peak sheep;
- `+1.92` final cows and `-1.23` final sheep;
- `+14.8` fertilizer collections, `+14.4` feeds and `+8.3` fertilizations;
- `+33.7` milk sales and `+223` wheat sales;
- first expansion `7.3` steps earlier.

This supports a cow-heavy, fertilizer-supported, early-three-quadrant policy.
It does **not** support buying the fourth quadrant, adding geese, or blindly
maximizing final coins in unmatched games.

Leaderboard-score correlations across only ten policies agree directionally:
earlier first land (`r=-0.927`), fewer dropped items (`r=-0.907`), lower peak
hands (`r=-0.845`), more animal purchases (`r=+0.683`) and more fertilizing
(`r=+0.540`).  These coefficients are especially vulnerable to sample size and
policy-family confounding; use them only to generate ablations.

## Robustness gate for promotion

A candidate is eligible for a two-submission batch only if it is a strong
standalone policy, not merely the other half of a complementary union.

Minimum evidence:

1. Exact official loader and action-shape checks pass.
2. Full 720-turn games finish from both seats.
3. Fresh replay counterfactuals reproduce donor banks exactly before candidate
   comparisons are accepted.
4. Prefer outcome stability first, competitive margin second, isolated bank
   third.  A high mean with several new losses is rejected.
5. Record first-action divergence.  Early route changes require materially
   stronger outcome evidence than late guards.

## 2026-08-25 candidate screen

The latest S20/S21 agents were exact open-code notebook artifacts.  Their
mature displayed ratings were `2297.5` and `2269.1`.

On 24 fresh S20/S21 public episodes with exact opponent tapes:

- v48 control: `22/24`, average margin `+5752.1`, worst margin `-20223`;
- Adaptive Shop Guard: `23/24`, average margin `+6818.4`, worst margin `-110`,
  zero outcome regressions versus the donor paths;
- X594: `10/24`; Premium Queue Split: `15/24`; Adaptive Champion V2: `16/24`.

On the exact current top-five panel, Adaptive Shop Guard won `8/10` with
average margin `+6942.9`, matching the best robust outcome count while
improving margin.  Aggressive Counterbook and Sell-Divergence branches showed
higher conditional margins but only `5/10` and `6/10`; they are rejected as
standalone policies.

Adaptive Shop Guard is therefore the current robust promotion anchor.  Its
only loss in the 24-game fresh cohort was by `110` coins.  Premium Queue Split
flipped that one game but lost too many others; this is insufficient evidence
for a route-level switch.

A new fertilizer-exposure preemption was then enabled on the same frozen farm
backbone.  It activates only after step 216 when the public opponent farm has
at least eight animals and fertilizer still has at least 80% of base price.
Across the 24 fresh games it preserved the exact `23/24` outcome set, changed
only three games, added 10 own-bank coins and 20 competitive-margin coins in
total, and had minimum margin delta `0` versus Shop Guard.  On the current
top-five panel it also preserved `8/10`.  This is a safe but deliberately thin
online test; its benefit is not yet statistically established.

The 2026-08-25 live batch is S22 Adaptive Shop Guard (`55769293`) and S23 Shop
Guard Fertilizer Exposure (`55769295`).  Both were accepted as `PENDING` at
18:37 local time.  Do not replace either for several hours.

## Update protocol

After each two-bot batch has accumulated several hours of games:

1. Save displayed rating, match count and W/L record for each agent.
2. Download at least the latest 12 public episodes per submission.
3. Append new matched outcome/margin evidence here; do not overwrite old
   cohorts.
4. Recompute common-structure claims after each top-ten snapshot.
5. Treat any single displayed rating as provisional.  Prefer replicated
   matched outcomes and confidence intervals for final-agent selection.

## Replay-ML evidence (2026-08-25)

The first current-meta replay ML corpus covers 74 unique public episodes and
12 complete policies.  A broad early route classifier failed complete-policy
transfer (`0.500` balanced accuracy), so opponent adaptation must not be based
on that head.  Narrow 24-turn event gates for land and animal buying were much
more transferable and beat day-only schedules, while fertilizer and premium
sale prediction was largely calendar-driven.

Use factorized binary event gates plus a conditional type head; do not use a
flat joint action label or independent OVR heads for mutually incompatible
top-level actions.  OVR is retained only inside the conditional
`COW/SHEEP/MIX` head, where it won the policy-held comparison.  All current
heads are imitation signals, not outcome policies.  Promotion requires a new
counterfactual dataset with KEEP_BASE and bounded residual continuations.
