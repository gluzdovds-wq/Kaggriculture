# Kaggriculture top-20 replay audit — 2026-08-22

## Executive conclusion

Public replays are much more useful than raw notebook code, but they should be
treated as paired behavioral observations, not as transferable action tapes.
The strongest repeated pattern is a three-quadrant, livestock-heavy economy;
buying the fourth quadrant is neither necessary nor associated with rating.
The current N39 already matches that structural pattern and, on the exact
public seeds, beats the recorded top-five opponent tapes in 8 of 10 cases.

The remaining gap is not explained by a single visible knob.  Top agents tend
to hire slightly more, own a little more livestock, and water more.  Tomato use
is concentrated in a small number of high-rated policies and is positively
associated with rating in this small sample.  None of those associations is a
safe direct intervention: earlier crop and animal substitutions damaged the
coordinated task graph, while a literal top-1 action tape lost all 12 transfer
games against N39 on fresh seeds.

## Data and method

- Leaderboard snapshot: top 20 on 2026-08-22, rating range 2763.4–3131.9.
- Requested sample: two public games for every top-20 submission plus two
  games each for S09/N39 and S10/exact-V36.
- Coverage: 44 requested player-games, 35 unique replay files, zero missing.
- Replay parser uses `steps[t + 1].action` as the action executed from
  `steps[t].observation`; focused tests protect this one-step alignment.
- Aggregate summaries are equal-weighted by policy, so a duplicated replay or
  a policy sharing a game with another target does not receive extra weight.
- Winner-minus-loser differences are computed only within the same replay,
  controlling for the random seed, shop schedule and shared market path.
- Exact counterfactuals replace a leaderboard policy on its original seed and
  seat while the other player follows the extracted opponent action tape.
  The donor tape reproduces every archived final bank exactly.

Raw replay files and generated action tapes are intentionally git-ignored.
The tracked leaderboard snapshot and the collection/analysis scripts are the
reproducible inputs.

## What top policies have in common

Across the top 20, the equal-weight average policy:

- finishes with 3.3 quadrants; 70% of policies did not buy the fourth quadrant
  in either sampled game;
- hires 283 workers over the season and reaches a peak of 12.3 hands;
- buys 8.2 cows, 6.9 sheep and only 0.18 geese;
- buys about 134 wheat, 37 strawberry, 15 melon and 1.4 tomato seeds;
- issues about 962 WATER, 323 FEED, 317 CARE and 318 fertilizer-collection
  actions.

The top five are more heterogeneous but average 3.1 quadrants, 296 hires,
8.0 cows, 7.7 sheep, 5.3 tomato seed buys and 1052 WATER actions.  Only one of
their ten sampled player-games bought the fourth quadrant.

N39's two public games finish with exactly three quadrants in both cases,
average 277 hires and 12 peak hands, buy 10 cows and 4 sheep, and issue about
907 WATER actions.  Thus the visible difference from the top-five average is
approximately +19 hires, +1.7 total livestock and +145 WATER actions—not a
missing fourth field.  Ryo Hasegawa is closer to N39's cow-heavy split than the
top-five average: 11.5 cows, 4.5 sheep, no fourth quadrant, 289 hires and 1134
WATER actions over the two sampled games.

## Attached episode 96487653

Top-1 Ryo Hasegawa beat tetsuya 118,044 to 114,205 on seed 844211544.

- Both policies bought NW, NE and SW only; neither bought the fourth quadrant.
- Ryo bought 12 cows and 7 sheep; tetsuya bought 7 cows and 8 sheep.  Neither
  bought geese.
- Ryo hired 290 workers and peaked at 12 hands; tetsuya hired 305 and also
  peaked at 12.
- Ryo bought 151 wheat, 11 melon, 19 strawberry and 20 tomato seeds.
- tetsuya bought 148 wheat, 17 melon, 32 strawberry and no tomato seeds.

The episode supports the broad livestock/three-field pattern, but it does not
show a unique top-1 recipe: the two strong policies use meaningfully different
animal and crop mixes on the same seed.

## Paired evidence from decisive top-20 games

There are 25 decisive top20-vs-top20 games in the archive.  Relative to the
loser in the same replay, the winner averages:

- +3511 final bank, +0.04 quadrants and +0.04 fourth-quadrant purchases;
- +0.8 hires, +0.16 peak hands and +0.36 total animal purchases;
- +0.84 cow purchases, -0.20 sheep and -0.28 geese;
- +9.04 wheat, +2.60 tomato, -1.60 melon and -1.36 strawberry seed buys;
- +86.8 WATER, +4.24 FEED and -8.48 FERTILIZE actions.

The near-zero land difference is the most stable negative result.  The other
differences are exploratory: 25 games are small, several policies are close
variants, and actions are endogenous to market and field state.

Across the 20 policy-level averages, leaderboard rating correlates most with
tomato sales (+0.683), peak tomato inventory (+0.678), tomato seed buys
(+0.672), WATER actions (+0.555) and hires (+0.490).  Strawberry seed buys
correlate negatively (-0.506).  Fourth-quadrant use is essentially unrelated
to rating (-0.003).  These are associations, not causal estimates.

## Counterfactual checks

On the ten original top-five seeds/seats against the exact opponent tapes:

- the archived donors score 0.60 outcome rate with average margin +1762;
- N39 scores 0.80 with average margin +12,972;
- exact V36 scores 0.60 with average margin +5508.

N39 lowers its own final bank by 4127 coins versus the recorded donor on
average, yet improves competitive margin by 11,209.  This is direct evidence
that raw coin totals across unrelated episodes are not a strength metric.  The
shared market makes opponent suppression and relative timing matter, while the
leaderboard itself uses outcomes rather than coin margin.

N39 wins both exact top-1 replacements:

- episode 96458075: N39 134,424 vs opponent tape 106,644; the recorded top-1
  policy had lost 97,314 vs 102,741;
- attached episode 96487653: N39 56,312 vs tetsuya tape 48,909.

N39's two regressions are both Arman Tuganbaev cases, so that family is a more
useful targeted residual than the top-1 tape.

## Transfer tests against current public notebooks

On six fresh seeds from both seats, N39 scores:

- 11/12 against the current Moon Counts Melons code;
- 8/12 against the current Soil Remembers Rain code;
- 7/12 against the current V39 History Gate code;
- 12/12 against Strong Barnyard Economist.

These current notebook files are useful opponents and donors of bounded ideas,
but N39 already beats the strongest of them often enough that wholesale
replacement is not justified.

As a negative control, the exact top-1 action tape from episode 96487653 was
played against N39 on six entirely fresh seeds and both seats.  It lost 0/12,
with average margin -15,542.  The tape still produced plausible farms and high
coin totals, but its actions were synchronized to another seed's shops, weeds
and actor state.  This rejects literal replay imitation.

## Implementation decision

Keep N39 as the live base.  Do not buy a fourth quadrant merely to imitate a
single replay, and do not transplant an animal/crop quota without the matching
feed, service, harvest and sale schedule.  The next top-meta work should be
bounded, state-compatible and counterfactual-tested:

1. Mine Arman cases and repeated N39 losses for the earliest state predicate
   that separates them from non-regressions.
2. Treat higher WATER/hire/tomato activity as candidate task opportunities,
   not fixed action-count targets.
3. Permit a new task only when it uses an idle actor, is locally legal, fits
   the current route's resource/deadline budget and passes matched replay plus
   fresh-seed family gates.
4. Continue exact-replay mining daily, because public matchups reveal current
   policy interactions that notebook source and isolated coin totals miss.

No new Kaggle submission is recommended from replay imitation alone.  S09/N39
and S10/V36 are only a few hours old in the current ladder and occupy the two
active slots; preserve the remaining daily reserve until a bounded candidate
passes the established broad gate or the live pair reaches the 24-hour/stable
rating checkpoint.

A first bounded shadow intervention, N59, confirms the gate's conservatism:
it preserves all 48 N39 outcomes against the four current public families and
adds exactly two margin coins in each Moon game, but changes no outcome.  It is
retained as research infrastructure rather than promoted to a live slot.
