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
- Orbit Wars 2026 is the clearest recent scaling result: first place trained a
  200M-parameter transformer for 15B PPO self-play steps, while second place
  trained a 4.3M model for 10B steps.  Both first rewrote the environment and
  simplified or structured the action representation; several other gold
  solutions combined RL with analytic planning, forward features or search.
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

### Orbit Wars 2026 — 1st/2nd/6th/7th RL, 19th BC+RL

The first-place agent is a genuine end-to-end scaling result: a 200M-parameter
entity transformer trained for 15B PPO self-play steps.  The author rewrote the
environment in Rust and parity-tested it against replays, changed the original
angle action into target selection, trained on up to four 8xB200 nodes, and
used quantization plus a small-model runtime fallback to satisfy submission
limits.  This establishes that pure RL can win, but only after roughly 2,400
B200-hours and substantial systems engineering.

Second place followed a useful progression: heuristics reached top 50,
behavior cloning reached top 10, RL fine-tuning reached top 5, and a final
4.3M-parameter model trained from scratch for 10B steps placed second.  Its
action space was deliberately reduced to no-op or all-in target selection.  A
19-turn no-action forward rollout was encoded as input, and a local arena plus
pool leaderboard replaced training loss as the selection metric.

Sixth place combined a 2.5M transformer, league RL, engineered pairwise
forward features and a two-step inference search worth roughly 30–40 rating
points.  Seventh place combined a 9M PPO policy with an analytic planner that
generated/masked feasible targets; nearly 200 isolated 100M-step experiments
were judged by local round robins of about 512 games per matchup.  Observation
features, model size and planner improvements were the largest levers.

The 19th-place pipeline is the most attainable template for Kaggriculture.  It
rewrote the simulator from roughly 150–300 CPU transitions/s to 300k–700k
batched GPU transitions/s, used behavior cloning as an architecture and action
space gate, then PPO against historical checkpoints.  The policy had separate
heads for launch count, target and fleet size; deterministic deployment biases
were calibrated by direct head-to-head games.

Sources:

- https://www.kaggle.com/competitions/orbit-wars/writeups/1st-place-solution-scaling-reinforcement-learnin
- https://www.kaggle.com/competitions/orbit-wars/writeups/2nd-place-solution-for-orbit-wars
- https://www.kaggle.com/competitions/orbit-wars/writeups/6th-rl-league-search-with-a-custom-edge-atte
- https://www.kaggle.com/competitions/orbit-wars/writeups/7th-place-solution-how-structured-experiments-sa
- https://www.kaggle.com/competitions/orbit-wars/writeups/19th-place-gold-writeup

Transfer: do not train PPO on raw farmer/worker actions in the official Python
environment.  First build a parity-tested fast simulator, expose rule-generated
task-graph candidates through factorized heads, feed exact ETA/cashflow/service
lookahead to the ranker, and select checkpoints by a historical-opponent
round-robin rather than training loss or one live rating.

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

## Orbit Wars addendum — new experiment bank

### N51 — parity-tested native simulator throughput gate

Reimplement the exact Kaggriculture transition core in a vectorized native
backend.  Require replay/official-engine parity on random and edge-case
trajectories before training.  A serious RL line starts only after at least
50k transitions/s locally; otherwise spend compute on replay counterfactuals,
macro bandits and search rather than pretending hundreds of games are PPO.

### N56 — factorized macro action heads

Do not classify the complete joint action or even one flat task+market macro.
Generate legal task-graph candidates in rules and predict separate task-family,
market-operation, route/target and bounded quantity scores.  Recombine only
through the conservation/legality layer.  Gate with held-out replay top-k
coverage, critical-action recall and official-engine outcome.

### N54 — exact forward features beneath the learned ranker

For every candidate task graph compute 6–24-turn ETA, resource feasibility,
cashflow, service deadlines, predicted shared-market collision and terminal
inventory using the exact simulator.  The model ranks these consequences; it
does not relearn movement, crop timing or accounting from pixels/state alone.

### N55 — checkpoint league as the model-selection metric

Every learned or searched checkpoint must play a fixed historical pool plus
recent baselines on both seats.  Use isolated changes, fixed seeds, direct
head-to-head confidence and a local BT/OpenSkill-style table.  Training loss,
imitation accuracy and a single live rating are diagnostics, never promotion
criteria.

## Execution checkpoint: N51/N56 pilot

- Eight `pass/pass` games in the official Python environment, run with four
  worker processes, completed 5,760 environment transitions in 12.489 seconds:
  only about 461 transitions/s including process/import overhead.  At that
  optimistic rate 10B transitions would take roughly 251 days before policy
  inference.  Full self-play RL is therefore blocked on N51, not on the choice
  between PPO and another algorithm.
- The combined N24 pilot/holdout corpus contains 8,376 non-noop decision turns
  from scored S05, V16 and v25.  A flat task+market label has 258 values; top-8
  and top-32 cover only 40.3% and 69.4%.  Flat macro classification is rejected.
  Factorization is materially better: top-16 task families cover 83.7%, while
  top-8 market operations cover 96.5%.  N56 should therefore use separate
  heads plus rule-based recombination, not a fixed shortlist of joint labels.

## Execution checkpoint: N56 learned shortlist

- Reused the already trained, disjoint-season N24 linear residuals rather than
  fitting a second model to the same labels.  A new evaluator reconstructs the
  task and market rankings independently, removes the non-executable
  `__OTHER__` class, forms top-k Cartesian candidates and optionally filters
  pairs not observed in the training season.
- On 1,388 non-noop S05 holdout turns, task top-8 plus market top-5 contains the
  exact donor pair `80.1%` of the time with `21.57` seen-pair candidates on
  average.  The tighter top-5/top-3 shortlist covers `66.7%` with `10.46`
  candidates.  Corresponding top-8/top-5 coverage is only `60.5%` for V16 and
  `30.2%` for v25.
- Every holdout pair was present in the corresponding training season, so the
  failure is ranking error rather than unseen joint vocabulary.  Filtering to
  seen pairs reduces candidate count but cannot improve recall.
- Decision: N56 passes as a candidate generator and replay-analysis tool, not
  as an autonomous policy selector.  Do not splice its top-1 choice into the
  live agent.  Prioritize N54 exact ETA/cashflow/deadline features and require
  official-engine league gains before any learned head controls behavior.

## Execution checkpoint: N54 forward-feature ablation

- Implemented only inference-visible consequences.  New full-observation rows
  retain static worker-to-task ETA, end-of-day reachability, object production
  and decay clocks, ready yield/value and carried-inventory return ETA.  A
  second deterministic layer computes hire/land affordability, storage
  overflow and sequential liquidation values after 6/12/24 turns of demand
  from currently visible shops.
- The copied official price curve has zero mismatches across all nine products
  on both old and new corpora.  A horizon crossing a not-yet-visible random
  shop unlock is marked incomplete.  It is not silently labeled an exact
  forecast.
- On four new seeds with N39/V16/v25 playing both seats against current N39,
  the N39 target-specific hybrid improved exact-pair shortlist recall from
  `46.76%` to `61.28%` at task top-3 × market top-3, and from `74.06%` to
  `79.47%` at top-8 × top-5.  V16 and v25 showed broad gains too, while both
  lost every direct current-meta game to N39.
- Geometry/object clocks provide most of N39's gain.  Adding cashflow to both
  heads slightly hurts its broad market shortlist, while helping V16/v25.
  Therefore features and regularization must be head-specific: all forward
  features for N39 task ranking, geometry/object clocks for market ranking.
- N54 passes its offline ablation gate, not its deployment gate.  Next generate
  legal candidate task graphs, rank them with these features, and require
  direct official-engine outcome lift with latency and worst-family controls.

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
- At the final checkpoint of this run S08 had moved to `2086.9` and S06r to
  `1919.2`.  The last current-day submission remained unused as the required
  validation/repair reserve.

## Execution checkpoint: N32–N36

- N32/N33 demonstrated the limit of opponent fingerprints: delayed
  classification and compatible shadow switching can win exact replay
  counterfactuals while failing on a fresh seed with the same visible farm
  shape.  Public-state aliasing, not internal policy memory, is now the main
  constraint on live counter-strategy selection.
- N34 confirmed that a single COW-to-SHEEP substitution cannot reproduce the
  winning Moon continuation; reactive planning must represent the coupled
  purchase, care, harvest and routing task graph.  N35 likewise showed that a
  broader sale horizon merely transfers performance between replay opponents.
- N36 adds a robust context that is known before compatible routes diverge:
  the first public shop.  The deterministic rule is X544 for non-pasture
  openings, Moon for pasture openings, and X544 again for pasture plus
  `YARN_STORE`.  It shadow-runs both routes through step 72 with isolated RNG.
- N36 improved a fresh eight-family outcome from `0.7500` to `0.9375`, kept
  the independent two-seed panel at `0.84375`, preserved all seven recorded
  ladder wins and improved the three-loss replay average from `-136.0` to
  `+88.3`.  It is now `main.py` (`a51cc844...`), with N31 retained as the
  second post-reset candidate and the final daily slot reserved.
- A further isolated-shadow full-feedback audit on 32 new contexts selected an
  outcome-optimal branch `32/32` times.  N36 averaged `0.875` outcome versus
  `0.625` fixed X544 and `0.6875` fixed Moon, with zero regret separately for
  BAKERY, FARMERS_MARKET and PET_CAFE.  No extra N37 split was justified.
- On the chronologically latest ten public S08 ladder episodes, exact S08
  reproduced all banks at `8/10`; N31 remained `8/10`, while N36 reached
  `9/10`, flipped the kevin park loss to `+6136` and caused no regression.
  A route plus lead/cap sweep could not flip the remaining Rikito loss, so no
  N38 timing variant was promoted.

## Execution checkpoint: N39

- A second disjoint chronological batch extended the exact S08 replay holdout
  to twenty episodes.  S08 and N31 won `17/20`; N36 won `18/20`, averaged
  `+745.8` margin versus S08 and introduced no outcome regression.
- The remaining Dariush X-route loss exposed a narrow timing response.  A
  two-turn X lead flipped that replay from `-71` to `+897`.  It then preserved
  every outcome on a 32-match fresh eight-family panel, adding `+245.44` mean
  family margin, and preserved N36's `8/10` on the older S05 replay set.
- Across the twenty S08 episodes N39 won `19/20` versus N36's `18/20` and
  S08's `17/20`, with no regression.  The more aggressive lead 3 also won
  `19/20` but transferred less cleanly to V25/C95, so lead 2 was promoted.
- This supports a bounded reactive overlay rather than per-turn epsilon
  exploration: move only an already scheduled sale, keep a debt ledger, and
  gate the timing by a compatible macro route.  N39 is now `main.py`
  (`6073f67f...`); N31 remains the independent conservative candidate.

## Execution checkpoint: N40 diagnostics

- A third disjoint chronological batch of twelve exact public S08 replays
  preserved N39 at `11/12`. Across all 32 episodes, S08/N36/N39 are now
  `28/32`, `29/32`, and `30/32` respectively.
- The only new common loss has an easy public fingerprint at step 12, but the
  donor policies that beat it diverge at the unobservable simultaneous step-0
  opening. A C95-prefix hybrid won that tape and collapsed to `1/12` on the
  batch, demonstrating why opponent classification alone is insufficient.
- Bounded sheep-to-cow substitutions, route changes, broad sale leads and
  wool-only timing all failed. The successful donors combine animal mix,
  feeding, placement, cleaning and market timing as a coupled task graph; the
  pieces are not independently composable.
- No N40 candidate was promoted. The next useful architecture is a compatible
  reactive planner over whole task graphs, trained or searched beneath the
  legal rule layer, rather than a late policy splice or epsilon action noise.

## Execution checkpoint: N41 diagnostics

- Keeping N39's common step-0 opening and inserting even a short C95 prefix
  remained incompatible: return points 12, 24 and 48 all performed far worse
  than unchanged N39 on the exact Johnson loss.
- A bounded, opponent-conditioned weed task then tested the smallest useful
  reactive planner. Idle workers were unavailable; diverting moving empty
  workers added up to 39 DIG actions but reduced score. Hiring a nominally
  dedicated cleaner also reduced score at every weed threshold.
- This rejects distance-only task assignment, not reactive planning in
  general. A viable planner must compare the full opportunity cost of hiring,
  travel, current production and later harvest/sale tasks. N39 remains the
  promoted artifact and N31 the conservative independent candidate.

## Execution checkpoint: N42 and fourth live holdout

- Fourteen later exact S08 replays form a fourth disjoint holdout. N39 tied
  S08 at `8/14`, with one improvement and one regression, but added `+695.14`
  average margin. Across all 46 episodes N39 leads at `38/46`, versus `36/46`
  for both S08 and N36.
- The new Audric regression and the earlier kevin improvement expose an
  information-timing limit. Their public farms and YARN_STORE context are
  identical through the first incompatible route action. A common Moon probe
  reveals different hiring responses one step later, but switching to X at
  that point is already state-incompatible and loses badly.
- This is the precise place where epsilon exploration fails: it can reveal a
  latent class only after the decision it was meant to improve. Keep N39 for
  aggregate strength and N31 as a genuinely different conservative policy;
  do not spend a slot on the N42 probe.

## Execution checkpoint: current-meta portfolio

- A whole-policy donor matrix on the newest fourteen episodes found a sharp
  temporal shift: exact V36 won `13/14`, while N39 won `8/14`. V36 was weaker
  on the preceding 32 episodes (`23/32` versus N39's `30/32`), so neither
  policy universally dominates the other.
- C95 and Soil also won `12/14`, confirming that the six new S08 losses form a
  coherent weakness of the N39 route family rather than one overfit tape.
  These donors diverge at step 0; there is no inference-visible pre-action
  feature with which an in-match selector can safely graft them onto N39.
- The correct exploitation/exploration unit is therefore the submission
  portfolio: activate deterministic N39 and exact V36 as two independent
  ladder policies after reset. Keep N31 unused as the repair reserve. A q20
  V36 retry improved its sole fresh loss margin but did not flip the outcome.
- Across all 46 tapes, the N39/V36 outcome oracle reaches `45/46`: nine wins
  are unique to N39 and seven to V36. A wider V36 market-quantity sweep still
  could not flip its only newest loss, reinforcing policy diversity over
  another narrowly tuned copy.
- The sole shared Rikito loss was also replayed against C95, Soil, V16 and
  V25; all lost by much more than N39. No third donor therefore displaces the
  held N31/repair reserve.
- Ten still-later public episodes passed exact S08 reproduction and produced
  V36 `9/10`, N39 `5/10`, N31 `4/10`, and S08 `3/10`. N39 won V36's only loss;
  the combined portfolio now covers `55/56` chronological public tapes.
- A current-meta transfer audit then wrapped exact V36 with the existing H21
  terminal route. It scored only `0.375` paired on eight fresh two-seat mirror
  seeds: triggered cases spent twelve moves to liquidate six WHEAT and were
  negative in every paired trigger. This is further evidence that useful
  overlays must move with their compatible task graph, not just their trigger.
- Trace-guided repair found that a single one-step worker route was slightly
  positive, but it changed no outcome on a matched eight-family panel and
  added only 11 coins on one of ten exact current-meta replays. A conservative
  nearby-worker planner selected that same worker in every trigger because
  V36's late task graph is stable. This is too small for a leaderboard slot;
  exact V36 remains the lower-risk portfolio member.
- Five still-later S08 games reversed toward N39 (`5/5`) while V36 won `3/5`;
  nevertheless V36 led Soil and C95 decisively on the combined latest fifteen
  (`12/15` versus `9/15` and `8/15`). N39 and V36 now each win `48/61`
  chronological replays and their two-policy oracle covers `60/61`, confirming
  that temporal complementarity is more valuable than selecting one winner.
- A compatible policy-pool experiment then isolated the last shared loss.
  N39 and a FERTILIZER+WOOL timing variant share the complete prefix before the
  first shop reveal, so both can be shadow-run safely and the variant selected
  only for `BAKERY`.  This N53 selector won all eight historical BAKERY tapes
  versus N39's seven, exactly reproduced N39 on every tested non-BAKERY game,
  and raised the corpus result to `49/61`.  Paired with V36, its retrospective
  outcome oracle covers all `61/61`.  This is the safe form of in-match
  adaptation: deterministic context selection at a verified compatible state,
  not random action-level exploration or a late task-graph splice.
- A fresh matched BAKERY gate then overturned that apparent promotion.  On one
  V36 and two X544 BAKERY seeds N53 preserved four wins, but on the remaining
  X544 seed it changed both seats from N39's `+4148` win to `-97` loss.  The
  prefix was compatible in every case, proving that shop identity alone did
  not identify the future market/opponent regime.  N53 was rejected and the
  safer N39/V36 submission pair restored; the shadow runner remains useful as
  infrastructure, not as evidence that this particular classifier transfers.
- Two still-later S08 games completed immediately before the quota reset.  S08,
  N39 and V36 all won both after exact replay reproduction; V36's diagnostic
  average margin was `+14291.5` and N39's `+2631`.  The complementary pair now
  covers `62/63` chronological outcomes and remains the final submission plan.
