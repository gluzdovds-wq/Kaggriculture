# Historical Kaggle agent competitions — transfer to Kaggriculture

Research date: 2026-08-21.  The purpose of this note is not to catalogue every
simulation competition, but to identify which methods actually reached the top
and which parts transfer to Kaggriculture.

## Clear answer

Top Kaggle game agents have used all three families: hand-written planners,
deep imitation learning, and deep reinforcement learning.  The winning method
depends mainly on the structure of the joint action space and the amount of
exact simulation available.

- Long-horizon resource games with many simultaneous units often favor a
  hierarchical rule/search agent.  Halite 2020's winner abandoned Deep RL
  after a month and used `scores -> plans -> actions`; Lux S2's winner used
  forward simulation plus persistent roles, goals and prioritized action
  locking.
- Compact spatial games can be won by large-scale self-play RL.  Hungry Geese's
  winner used HandyRL after roughly three weeks and about 16M self-play games.
  Lux S1's winner used distributed IMPALA-style RL with UPGO/TD-lambda,
  curriculum reward shaping and teacher-policy KL regularization.
- Imitation learning is a strong shortcut when high-quality replays exist.
  Lux S3's third-place agent surpassed its rule-based predecessor after a few
  hours of UNet imitation training on carefully reconstructed observable
  states.  Kore's 13th-place solution treated joint actions as a token sequence
  and stopped at imitation learning because the action space made RL expensive.
- The strongest learned systems were not naive end-to-end PPO.  Repeated
  ingredients were legal-action masks, curriculum from dense to sparse reward,
  replay-state initialization, historical opponent pools/PFSP, teacher KL,
  symmetry augmentation, and a rule/search layer around the network.

Kaggriculture is structurally closer to Halite and Lux S2 than to Hungry Geese:
720 turns, many workers, long service dependencies, a large joint action, exact
economic constraints and a shared adversarial market.  Therefore the highest
expected-value route is a reactive hierarchical planner with learned residual
or macro decisions.  Pure end-to-end RL remains a later experiment, not the
primary line.

## Primary write-ups reviewed

### Halite by Two Sigma — 1st place, rule/planner

The winner first attempted Deep RL, but credit assignment across an arbitrary
number of ships, long games and a dynamic opponent pool was too difficult.  The
final 11k-line agent scored long-term tasks on every square, assigned each ship
a plan, resolved conflicts, then translated plans into low-level actions.  It
also used phase-specific overrides and opponent-risk logic.

Source: https://www.kaggle.com/competitions/halite/writeups/ttvand-1st-place-winning-solution

Transfer: score tasks, not raw unit actions; persist assignments; separate
strategic scoring, coordination and execution; allow exact tactical overrides.

### Hungry Geese — 1st place, self-play RL

HandyRL used a toroidal convolutional policy/value network and distributed
off-policy policy-gradient self-play.  Public reports describe roughly 16M
games over three weeks.  An 11th-place hybrid used imitation learning, HandyRL
fine-tuning and short-horizon MCTS, with a deterministic-public-agent detector
at the root.

Sources:

- https://www.kaggle.com/c/hungry-geese/discussion/263279
- https://www.kaggle.com/competitions/hungry-geese/writeups/the-wisdom-of-manjushri-if-three-ducks-approach-11
- https://github.com/DeNA/HandyRL

Transfer: RL can work when exact rollouts are extremely cheap, but it needs a
league, millions of games and a compact masked action space.  Root-level public
family exploitation is directly relevant to Kaggriculture.

### Lux AI Season 1 — 1st and 2nd, deep RL

The winner replaced its rule-based line after distributed RL overtook it.  The
system used a spatial ResNet, IMPALA-derived training, UPGO and TD-lambda,
teacher-policy KL, legal action masks, and a dense-to-sparse curriculum.  The
second-place PPO solution used a hand-crafted dense reward and
Prioritized-Fictitious Self-Play against previous versions.

Sources:

- https://www.kaggle.com/competitions/lux-ai-2021/writeups/toad-brigade-toad-brigade-s-approach-deep-reinforc
- https://www.kaggle.com/competitions/lux-ai-2021/writeups/rl-is-all-you-need-rliayn-s-approach-online-deep-r
- https://github.com/IsaiahPressman/Kaggle_Lux_AI_2021

Transfer: warm-start with shaped rewards, anneal toward win/loss, retain a
teacher KL to prevent catastrophic route drift, and train against historical
opponents rather than only the newest self.

### Lux AI Season 2 — 1st, forward simulation and roles/goals

The winner was not ML.  It repeatedly simulated future states for roughly 2.9
seconds, maintained persistent unit roles and multi-step goals, reassigned only
when invalid, and selected actions in a priority order so low-value units could
not block critical ones.  Fourth and tenth place showed that PPO/IL/RL could be
competitive, but the tenth-place system plateaued and emphasized how silently
complex RL stacks fail.

Sources:

- https://www.kaggle.com/competitions/lux-ai-season-2/writeups/ry-andy-1st-place-solution
- https://www.kaggle.com/competitions/lux-ai-season-2/writeups/flg-flg-s-approach-deep-reinforcement-learning-wit
- https://www.kaggle.com/competitions/lux-ai-season-2/writeups/deimos-10th-place-deimos-s-rl-approach

Transfer: replace open-loop worker tapes with persistent roles, goals,
reservation/priority locks and rolling forward simulation.  This is the most
direct historical analogue for Kaggriculture.

### Kore 2022 — rule-based top five and imitation learning

The fifth-place solution was explicitly rule-based.  It separated game phases,
used strategic thresholds and computed coordinated actions.  The 13th-place
solution encoded the joint shipyard action as a token sequence using a
ConvNeXt/Transformer imitation model; RL was planned but not reached because
the structured action space consumed the available development time.

Sources:

- https://www.kaggle.com/competitions/kore-2022/writeups/1-musketeer-1-musketeer-5th-place-solution-rules-b
- https://www.kaggle.com/competitions/kore-2022/writeups/sai11fkaneko-13th-place-solution-imitation-learning-with-language-modeling

Transfer: macro-action tokenization is viable, but an exact heuristic candidate
generator should reduce the learned output space before RL.

### Lux AI Season 3 — 1st/2nd RL, 3rd imitation learning

The winner used large-scale self-play with opponent pools, teacher/student
stabilization and more than 20B training steps.  Second place used PPO with
masked actions, teacher KL and stochastic test-time sampling.  Third place used
two UNets trained by imitation on top-team replays and carefully reconstructed
only inference-visible state.

Sources:

- https://www.kaggle.com/competitions/lux-ai-season-3/writeups/flat-neurons-1st-place-approach-by-flat-neurons
- https://www.kaggle.com/competitions/lux-ai-season-3/writeups/frog-parade-frog-parade-s-solution
- https://www.kaggle.com/competitions/lux-ai-season-3/writeups/adg4b-imitation-learning-3rd-place-solution

Transfer: replay IL is the fastest learned baseline; stochastic mixtures help
only at tactically uncertain, state-compatible decisions; opponent pools and
teacher KL are mandatory for a serious RL line.

## New experiment bank N16–N29

### N16 — shadow policy bank from step 0

Run every candidate policy on deep-copied observations from step 0, preserve
its internal state and RNG, but execute only the active branch.  First test:
X544, Moon, V16-RC5 and v25 shadows on both-seat public-family games.  Pass if
live actions/banks are byte-identical before switching and p99 latency remains
below the submission budget.

### N17 — compatibility graph and switch checkpoints

Record public/private-own state fingerprints and next-action equivalence at
steps 1/12/24/48/72/120/161/240/480/689.  Add an edge only when the target
policy can continue without illegal/no-op drift.  Pass if an actual switch
reproduces the target continuation on a fresh holdout; otherwise mark the edge
unsafe.

### N18 — common opening with delayed branching

Find or synthesize an opening shared by the best two route families, then
branch only after the first informative shops/opponent features.  Compare with
choosing the route at step 1.  Pass on outcome improvement without reducing the
worst-family result.

### N19 — persistent reactive task planner

Replace a bounded tape segment with roles/goals, task validity checks,
resource/cell reservations and priority action locking.  Start with terminal
logistics or weed/service recovery, not the whole season.  Pass if it reduces
deadline misses/route drift and improves paired outcome on a disjoint panel.

### N20 — exact scored donor versions

Identify the notebook versions tied to V16-RC5 score 2913.3 and v25's current
score 3009.0; extract source, output, metadata and hashes.  Do not treat the
latest notebook source as the scored artifact without version evidence.

### N21 — donor shootout versus S05 and broad pool

Run scored V16-RC5 and v25 against S05 and at least eight deduplicated public
families on fresh seeds and both seats.  Report paired outcome, family worst
case, BT estimate, latency and exact hashes.

### N22 — select a new route base

Promote the route with the strongest broad outcome, not the highest notebook
card score or mean bank.  Require no crash and no catastrophic unrelated-family
veto.

### N23 — overlay transfer factorial

On the selected base, ablate and add separately: bounded weed repair, H21
terminal liquidation, conserved FERTILIZER timing and H22 opponent selector.
Test singles first, then only interaction pairs justified by singles.

### N24 — replay imitation residual

Generate inference-visible state/action data from scored public agents.  Keep
all mechanics and legal actions in rules; train a small model only to rank
route/task/market macro candidates.  Compare IL alone with donor+residual and
reject if it cannot exactly reproduce critical service/terminal actions.

### N25 — RL best response to public medoid league

Freeze deduplicated public notebook agents as an opponent mixture.  Warm-start
from N24/donor behavior, use masked macro actions and teacher KL, train a best
response, then add it to a PSRO-style league.  Primary reward is match outcome;
dense shaping is annealed away.

### N26 — replay-state curriculum

Initialize rollouts from sampled observable midgame/terminal public states as
well as step 0.  This targets rare weed, storage, first-sale and liquidation
regimes that naive self-play reaches too slowly.

### N27 — opponent-conditioned response head

Condition the macro-policy on a posterior over behavioral families derived
only from public features.  Hold out whole agent lineages, not random episodes.
Compare deterministic argmax, robust maximin fallback and calibrated mixture.

### N28 — safe stochastic mixture

Test randomness only at state-compatible macro branch points.  No epsilon
random unit actions.  Compare deterministic best response with 95/5 and learned
mixtures on cyclic cross-play; keep only if expected outcome and worst-family
uncertainty improve.

### N29 — short-horizon forward simulator

At a small set of market/terminal decision points, simulate rule-generated
macro candidates for 6–24 turns using the exact fast simulator and score them
with terminal feasibility plus a learned value residual.  Pass only if the
selected action improves official-engine paired outcome and stays within the
1-second action budget.

## Execution checkpoint: N16–N22

- V16-RC5 is exactly V2 / `scriptVersionId=341905759`, Best Score 2913.3,
  agent SHA-256
  `f029fa0cb66a9eb509afbe44e3f59b800332d0419db91607183410e4089c4d19`.
- v25 is exactly V2 / `scriptVersionId=341206423`, Best/Public Score 3009.0,
  agent SHA-256
  `9bdfbafb6755067182d88ce594fd46fb1d712713ffd6931e83d5d50e84bc6fb2`.
- S05 beat V16 14/16 and v25 16/16 on a fresh direct panel.  On a separate
  eight-family screen S05/V16/v25 scored 32/32, 8/32 and 0/32 respectively.
  Therefore N22 retains S05 despite the donor cards' much higher live ratings.
- A real two-policy shadow runner confirms the distinction between memory and
  state compatibility.  All tested S05↔V16/v25 switches were catastrophic,
  including step 1; X544↔Moon at their shared step-72 prefix was paired-neutral
  in both directions and stayed below 157 ms per action.
- Practical architecture: keep a compatibility graph, branch only along a
  verified edge, and use opponent classification to choose an entire compatible
  continuation.  Do not use 5% random unit actions or arbitrary late tape
  swaps.

### Live-rating checkpoint

An exact resubmission of S05 (identical SHA-256) initially scored `692.1` and
later moved through `1451.1` to `1476.5`, while the earlier copy remained at
`2252.1`.  Likewise S06r moved from `600.0` through `1646.6` to `1737.0`.
This falsifies the frozen-test-set
interpretation of the Kaggriculture leaderboard and makes blind duplicate
refreshes unsafe.  Use controlled paired cross-play for causal selection and
the leaderboard only as a noisy measurement of the current live meta.

## Execution checkpoint: N24–N29 and N31

- N27's full-feedback contextual selector independently relearned H22 from
  public step-1 features: starting money at most 12 selects X544, otherwise
  Moon.  It was outcome-optimal on every unseen held-out lineage; two of six
  exact-route misses were only margin tie-breaks between routes that both won.
- N24's linear residual-imitation pilot is not reliable enough to execute
  actions.  S05 holdout task accuracy/top-3 was `0.321/0.606`; its market
  ranker reached `0.660/0.917`, but rare buy actions remained weak.  Learned
  outputs may propose top-3 macros beneath the rule/legal layer, not replace
  it.  Scored V16/v25 imitation was weaker still.
- N29 found a stable timing interaction rather than a new route.  X544 keeps a
  one-turn FERTILIZER lead; Moon uses two turns, increasing to three only at
  steps 480–714.  The route-aware base had no outcome regression on an
  eight-family fresh holdout and the late window added a small non-negative
  external gain.  The route-aware base was submitted as S08 (`55674010`); the
  initial rating was `600.0`.  The locally promoted late-window refinement is
  held as the one remaining repair slot until S08 provides meaningful live
  history or the quota resets.
- N28's safe full-feedback mixture rejected online epsilon exploration.  The
  learned robust solution was exactly deterministic H22; a 95/5 route flip
  reduced both mean and worst-family expected outcome on training and holdout.
- N25 now has a fidelity-gated counterfactual league built from public ladder
  replays.  Exact S05 reproduced all three recorded loss banks; N31's bounded
  premium-sale overlay flipped one loss to a win, preserved seven independent
  recorded wins and improved their average margin by `+342.7`.
- N26 extracted 74 inference-visible rare-state rows across negative bank
  swings, market collisions, terminal sales and storage pressure.  They are a
  curriculum for masked macro work, not hidden opponent-state reconstruction.
- N31 advances only already scheduled FERTILIZER, MILK, WOOL and STRAWBERRY
  sales, capped at 10 and repaid through the same debt ledger.  It passed fresh
  public-family and real-replay holdouts without an outcome regression and is
  the current local artifact (`df06a07...`), ready after the quota reset.
- At the final checkpoint of this run S08 had moved to `1803.3` and S06r to
  `1815.2`.  The last current-day submission remained unused as the required
  validation/repair reserve.
