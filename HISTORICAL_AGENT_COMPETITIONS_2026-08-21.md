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
  `46.65%` to `61.46%` at task top-3 × market top-3, and from `74.17%` to
  `80.66%` at top-8 × top-5.  V16 and v25 showed broad gains too, while both
  lost every direct current-meta game to N39.
- A replay-fidelity audit found `obs.step` stale at zero for seat 1.  All
  reported current-meta metrics were regenerated after deriving the public
  clock from `day*24+hour`; both seats now cover steps `0..718` exactly.
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
- N57 then tested a narrower, fully legal reactive market overlay: an exact
  price-curve gate compared current revenue with the known-demand revenue at
  the original scheduled sale turn and kept the base fixed lead whenever an
  unseen future shop unlock made the projection incomplete. On four fresh
  seeds, both seats and V36/C95/V16/v25, N39 and the best ratio-1.00 gate both
  won all `32/32` matched games. The gate changed candidate bank by only
  `+67.47` and competitive margin by `-3.03` per game, with no outcome flips
  and a `-113.75` family-margin delta against V16. This is safe reactive
  machinery but not a promotion: exact one-factor forecasting still does not
  replace full task-graph opportunity cost or policy diversity.
- N58 shadow-ran the strongest available public structured economic policy
  continuously beside N39.  The full donor was decisively weak on a current
  five-family screen and diverged from N39 at step zero, so strategy recognition
  cannot make a later whole-policy splice safe.  The new isolated-RNG shadow
  wrapper nevertheless reproduced N39 exactly in every outcome-neutral test.
  Allowing only locally legal WATER/FEED actions for base-idle actors produced
  six real WATER interventions on a targeted seed, but changed no bank, margin
  or result.  This cleanly separates safe exploration plumbing from useful
  exploration: the former now exists, while the latter still requires a learned
  or searched counterfactual value estimate over the complete task graph.

## Execution checkpoint: chronological public-state route learning

- The exact-replay pipeline now preserves only inference-visible public
  checkpoints for paired compatible continuations.  A depth-one
  full-feedback contextual-bandit tree can therefore learn a route predicate
  without opponent identity, rating, replay id, future state or private shed.
- On 46 chronological S08 games, fixed X544/Moon scored `26/46` and `36/46`;
  their outcome oracle reached `40/46`.  The learned step-72 rule used own
  public money (`<=44 -> X544`) and reached `38/46`, including leave-one-out.
- The apparent learned gain did not transfer.  On 40 newer top-20 cases the
  tree scored `26/40` versus Moon's `27/40`, and on the newest 24 cases both
  scored `23/24`.  Neither future block contained a single X544-only outcome.
  This is a concrete negative result for N27: legal public features and full
  feedback are not enough when the best-response label drifts with the live
  population.  Keep the tiny-tree pipeline, but require a repeated new X544
  residual before refitting; do not increase depth to memorize old lineages.

## Execution checkpoint: synthesized common opening

- N18 was tested as a genuinely third prefix rather than another late policy
  splice.  N39 and C95 were shadow-run from step zero while the executed action
  combined consensus actor tasks with intersected market orders, or crossed
  one policy's field plan with the other's market plan.  Both continuations of
  each candidate therefore received the same physical prefix.
- Across seven synthesis rules, five branch steps and both continuations, only
  the effective C95 opening preserved C95's Excluding residual win.  A novel
  N39-field/C95-market first action also won, but its C95 continuation was
  exactly trajectory-equivalent to C95 on all eight Arman cases, while its N39
  continuation fell to `0/8`.
- This rejects component recombination as a common-opening construction.  The
  Halite/Lux transfer remains valid but must be implemented one level higher:
  jointly optimize a third role/task allocation whose state contract explicitly
  supports both downstream planners, rather than voting over their immediate
  actions.

### N68 — hierarchical simultaneous-move PUCT with an incremental value model

A direct Stockfish port is the wrong game model: Kaggriculture has simultaneous
actions, hidden opponent inventory, future random events, a 719-action horizon
and a combinatorial joint worker/market action.  Retain Stockfish's useful
engineering ideas — iterative deepening, move ordering, a transposition table,
strict time management and a small incrementally updated evaluator — but replace
alternating alpha-beta with belief-sampled simultaneous-move PUCT or bounded
beam search.

Search only at day boundaries, shop unlocks, land/hire decisions and terminal
liquidation points.  The existing rule planner proposes top-K legal task graphs
and market plans; a deterministic executor handles movement, watering, feeding
and storage between search nodes.  Opponent branches come from legal public-state
policy-family hypotheses, never leaderboard identity.  Chance nodes sample
future shop/random outcomes consistent with the observation.  A small
NNUE-style or MLP value residual scores win probability and bank margin on top
of exact ETA, cashflow, service-deadline and liquidation features.

Feasibility gate: the parity-tested native simulator replayed 1,000 competitive
719-transition seasons in 2.511 seconds on this PC (`398` seasons/s, roughly
`286k` raw transitions/s) without policy inference.  Build snapshot/restore and
observation-to-belief initialization, then compare handcrafted beam search,
PUCT with a handcrafted value and PUCT with a learned residual.  Use 6/12/24-turn
rollouts, hard-stop at 600 ms inside the one-second action limit, and promote
only on untouched both-seat official-engine games with no deadline failures.

## Execution checkpoint: native search fork gate

- The complete patched simulator is only `7,728` bytes and trivially copyable.
  A new benchmark forks competitive trajectories at early, middle and terminal
  prefixes, applies distinct root-action variants and rolls them for 6/12/24
  turns.  All `12/12` fork states matched an independent linear replay under
  semantic field-by-field comparison, while all `13/13` original official
  parity traces remain exact for 719 transitions.
- The worst raw 600 ms capacity across the measured prefixes and both seats was
  about `33k`, `17k` and `7k` branches at horizons 6, 12 and 24 respectively.
  This decisively clears the transition-throughput gate for an offline macro
  search pilot.
- Online PUCT is not yet justified: a live observation omits the opponent's
  shed/seeds/unit inventories and the episode seed used for future random
  events.  The next gate is a legal observation-to-belief particle initializer
  and robustness test; full-state oracle search would otherwise leak unavailable
  information even if its local score looked excellent.

### N69 — legal observation-to-belief particles

Maintain particles from step zero using only the observation/configuration and
the agent's own persistent history.  Public farms, market changes and visible
town events constrain opponent purchases, production and sales; sample the
remaining opponent shed/seeds/carried inventory and future RNG outcomes rather
than reading the second seat's private replay state or source seed.  At each
macro checkpoint, rank the same top-K plans across all particles with a robust
lower-quantile or majority value, not the most favorable determinization.

First audit hidden-state mass at steps 72/360/648 on disjoint replays.  Then
compare a full-state oracle, the legal particle ensemble and a public-only
neutral prior on held-out traces.  Pass only if the legal ensemble retains the
oracle's winning plan in top-3 often enough to improve official-engine both-seat
outcomes, stays under the 600 ms internal budget and never consumes replay ID,
opponent name, opponent private state or source seed at inference.

## Execution checkpoint: hidden-state magnitude

- On 40 top-20 replays, both viewpoints and steps 72/360/648, all duplicated
  public views matched.  Nevertheless the hidden opponent payload grew from a
  mean `8.49` units (`$500` gross mark) at step 72 to `64.89` (`$3,980`) at 360
  and `82.64` (`$4,007`) at 648; the late maximum was `$19,858`.  A blank or
  single exact neutral opponent private state is therefore not defensible.
- The useful structural simplification is that all selected checkpoints are
  day boundaries: carried inventories were empty in every one of `240/240`
  seat-checkpoint cases.  Belief search at these points only needs opponent
  shed/seeds and future randomness in addition to the fully public farms,
  market and town.
- Replay source seed visibility was `100%` offline and `0%` in legal target
  observations.  Seed-conditioned oracle rollouts must remain evaluation-only;
  deployment must sample future random outcomes from the public prior.

### N70 — day-boundary shed/seed particle search

Restrict the first search prototype to steps divisible by 24.  Initialize each
particle with the exact public farms/market/town and own private state, draw only
opponent shed/seeds from a history-conditioned legal posterior, and sample a
future random stream without trying to recover the replay seed.  Generate the
same top-K task graphs in every particle and select by lower-quantile win value.

Compare blank-private, checkpoint-marginal and history-conditioned particles
against a forbidden full-state oracle on disjoint top-20 and live replays.  Pass
only if history conditioning improves oracle top-3 plan recall and official-
engine both-seat outcome over the marginal prior, without names, IDs, private
opponent observations or seed access and within the 600 ms internal budget.

## Execution checkpoint: legal snapshot particle prior

- Complete-episode holdout on the top-20 replay set confirms that a checkpoint
  marginal is far better than a blank private state.  Conditioning ten donor
  particles on 116 current legal observation features improves best-particle
  item L1 over ten random checkpoint particles at steps 72/360/648 by roughly
  `67%`, `15%` and `18%` respectively.
- Point reconstruction gains are much smaller after the strong marginal median:
  +16.6% early, +5.2% midgame and +1.9% late.  Ten-neighbour gross coverage is
  better early/late but worse at step 360.  Current public state is therefore a
  useful proposal distribution, not a stable posterior.
- The remaining legal information source is temporal: visible opponent plant,
  harvest, animal, land, hand and money changes plus shared market deltas.  It
  must be computed from the target seat's observation stream, never replay
  actions or the other seat's private payload.

### N71 — observation-history particle posterior

Accumulate inference-visible deltas from step zero: opponent plant/harvest and
animal placement/collection events, land and hand trajectories, money-change
statistics, and shared market inventory/price changes.  Combine these with the
current snapshot only after proving every feature can be updated from the live
target observation stream without opponent actions, name, replay ID or seed.

Under the same complete-episode folds, compare history kNN or a small regularized
multi-output model with checkpoint median and snapshot kNN-10.  Require lower
item and gross-value error at both steps 360 and 648, better ten-particle oracle
coverage on each checkpoint (not only aggregate), and then improved macro-plan
top-3 recall before any in-agent rollout integration.

## Execution checkpoint: observation-history transfer

- A 324–326-feature combined snapshot/history representation was built without
  replay actions or other-seat private inputs.  On the original grouped top-20
  panel it improved seven of eight registered late metrics; only step-648
  best-particle gross coverage regressed, so the internal gate correctly failed.
- Without changing k, features or donor pool, transfer from the 40 top-20 games
  to 23 non-overlapping live-focus games passed every step-360/648 point and
  particle item/gross comparison.  Late point item error improved 20.9%; the
  weakest passing edge was late particle gross error at only 0.17%.
- This is sufficient to retain history-kNN10 as the legal belief proposal, not
  to claim a stronger agent.  The next evaluation must ask whether its ten
  particles preserve the full-state oracle's best macro plan, then whether that
  plan wins paired official-engine games.

### N72 — particle-to-oracle macro-plan recall

At day-boundary checkpoints generate a fixed, legal top-K set of reactive task
graphs (crop/animal service, land/hire, market timing and terminal liquidation),
not raw action tapes.  Evaluate each plan for 6/12/24 turns under the forbidden
full state, checkpoint-marginal particles, snapshot-kNN10 and history-kNN10.
The full state supplies labels only; inference sees the history particles.

Pass only if history particles retain the oracle-best plan in top-3 more often
than both baselines at steps 360 and 648 on a disjoint replay block, improve
robust regret, stay below 600 ms, and the selected reactive plan then improves
official-engine both-seat outcome over N39.  No identity, replay ID, source seed,
opponent private observation or future action tape is permitted.

## Execution checkpoint: reactive macro-plan recall

- Nine legal task graphs were evaluated from exact day-boundary roots on both
  seats of 23 disjoint live games.  Every future branch was reactive on both
  sides; the replay action stream stopped at the root.  Ten marginal,
  snapshot-kNN10 and history-kNN10 particles plus blank-private and full-state
  oracle controls shared two synthetic future RNG seeds and maintenance versus
  liquidation opponent responses.
- The fast simulator reproduced all 719 money/market transitions of all 27
  available live traces.  Nevertheless the registered history advantage did
  not appear.  At horizon 24, step 360 was completely insensitive to hidden
  private state: every method, including blank, selected the oracle plan in
  top-1 and top-3 on all 46 seat cases.  At step 648, snapshot beat history in
  top-1 (`95.7%` versus `93.5%`) and mean regret (`1.18` versus `3.21`); both had
  `100%` top-3 recall.
- This rejects the claim that better shed/seed reconstruction improves the
  current macro decision.  It does not show that hidden state is universally
  irrelevant.  The tested plan/value system is itself narrow: maintenance and
  liquidation dominated, no animal route won a 24-turn oracle label, and one
  full case marginally exceeded the 600 ms budget.  Do not integrate N71 into
  PUCT or submit it on these results.

### N73 — inference-visible leaf-value calibration

Treat N72's failure as a value/proposal problem.  Build grouped day-boundary
examples whose inputs contain only the controlled seat's private state plus
public farms, market and town, and whose offline target is future relative
wealth over 24 turns and at game end.  Compare the current hand-marked farm
value with a small regularized tree/linear residual; names, EpisodeId, source
seed and opponent private inventory remain forbidden inputs.

Use shadow-run N39, V36 and strong public donors only to propose and de-duplicate
reactive task graphs, never as future action tapes.  Score the richer candidate
set with the learned leaf value under the exact simulator.  Pass only if grouped
and top20-to-live value error improves, oracle plan labels are no longer almost
entirely maintenance/liquidation, the public/own selector reduces oracle regret,
and the selected planner improves official-engine both-seat outcomes over N39
  within the 600 ms budget.  Hidden particles remain dormant unless this stronger
  value/proposal system demonstrates measurable sensitivity to them.

## Execution checkpoint: legal residual value transfer

- A leakage-constrained evaluator compared nine direct/residual ridge, kNN and
  shallow-tree families on all 27 day-boundary checkpoints.  Both seats and all
  rows from an EpisodeId remained in one fold; the frozen transfer trained on
  40 top-20 games and evaluated 23 non-overlapping live-focus games.
- Residual learning contains real but modest transferable signal.  The +24-turn
  ridge residual reduced CV and live MAE by about 2.5%; the final-margin ridge
  residual reduced live MAE 3.4% and was especially useful at step 360.  This
  is evidence that a Stockfish-like leaf evaluator can beat a hand score in the
  middle of the season without names, replay actions, opponent private state or
  source-seed leakage.
- One global value is not phase consistent.  The +24 head lost at 16 of 27
  individual checkpoints despite its aggregate gain.  At step 648 the final
  head doubled the current-money MAE and reduced paired winner accuracy from
  87.0% to 65.2%.  This is distribution/target mismatch, not a reason to hide
  the slice: money approaches the true terminal objective while a model trained
  across the whole season continues to price long-run assets and trajectories.
- N73 therefore fails the planner gate.  Preserve the evaluator and data, but
  do not add its output to macro-plan scoring or spend a submission until a
  phase-gated value passes each registered slice and then counterfactual plan
  regret plus official both-seat outcomes.

### N74 — phase-gated horizon and terminal value

Replace the single final-margin head with two deployment-aligned quantities:
`current margin + predicted Δmargin` over a fixed short horizon, and a separate
paired win/rank head for broad midgame.  Choose phase buckets and a monotone
blend using complete-EpisodeId training CV only.  Beyond a frozen late cutoff,
fall back to current money or exact fast-simulator rollout to terminal rather
than extrapolating a midgame asset value.

Freeze the cutoff, models and fallback before downloading a new replay block.
Require improvement over the strongest simple baseline in aggregate and at
steps 360/600/648, with no regression in paired winner accuracy.  Only after
that fresh transfer may the value score a richer shadow-policy macro set; then
require lower oracle plan regret, under-600-ms inference and official-engine
both-seat gains over N39 before submission.

## Execution checkpoint: frozen phase value and fresh transfer

- The four-phase ridge/blend model was selected only by complete-EpisodeId CV,
  serialized with its 40-game provenance and committed as `7e5854b`.  Seventeen
  previously unseen S09/S10 episodes, one distinct opponent matchup each, were
  downloaded only after that commit; all 918 transfer rows had zero overlap
  with training and earlier replay archives.
- Phase conditioning solved the concrete terminal problem.  On fresh steps
  600 and 648, final-margin MAE improved by 17.6% and 12.1%, while paired winner
  accuracy improved from 76.5% to 82.4% and from 82.4% to 88.2%.  This supports
  the Stockfish-like design: leaf evaluation should change with remaining
  horizon, and a late value must not extrapolate a season-wide asset model.
- The full gate still failed.  At step 360 both the final regression and its
  separately trained rank head reversed more winners (`58.8%` versus current
  money's `64.7%`), even though final MAE improved slightly.  The 24-turn head
  also worsened step-600 MAE and lost winner accuracy overall.  Calibration
  error and decision ranking are not interchangeable objectives.
- N74 is therefore evidence, not a deployable planner score.  Preserve its
  phase residuals and terminal head, but do not use them to choose a macro plan
  until an ordinal model passes every winner slice on a second frozen transfer.

### N75 — confidence-gated antisymmetric leaf ranking

Train the value order directly from paired legal observations.  For each
episode/checkpoint use the difference of the two controlled-seat legal feature
vectors and the final winner label; a linear difference model is equivalent to
a scalar legal value applied independently at inference and enforces that
swapping the pair reverses the score.  Never expose either deployed evaluation
to the other seat's private payload.

Combine the ordinal score with current money through a confidence gate selected
only by complete-EpisodeId training CV: override current-money ordering only in
pre-registered close-margin regions where the pairwise head has demonstrated a
strict gain.  Preserve N74's terminal residual for magnitude, but use the new
head for ordering.  Freeze coefficients and thresholds before acquiring a
second unseen policy block.  Require no paired-winner regression overall or at
360/600/648, retained terminal MAE gains, then lower counterfactual macro-plan
regret and official both-seat improvement within 600 ms before submission.

## Execution checkpoint: pairwise rank transfer

- The antisymmetric ridge/confidence ranker was frozen as commit `3781215`,
  together with 80 forbidden train/prior-transfer EpisodeIds, before a second
  block was queried.  Training uses two legal viewpoints as two supervised
  examples and fits their feature difference plus its negation; no deployed
  leaf reads the opponent private payload.
- Grouped top-20 OOF accuracy rose 13.7 percentage points over current-money
  ordering.  On 20 untouched S08/S05 games it retained a 6.8-point gain over
  current money and a 4.6-point gain over legal-marked value.  It beat both at
  every registered anchor: 60% at step 360, 80% at 600 and 90% at 648.
- The independent magnitude head also kept the terminal benefit on this second
  distribution, reducing final MAE by roughly 27% at step 600 and 37% at 648
  versus the strongest simple baseline while improving winner accuracy.
- N75 passes as a legal replay-ordering primitive.  It is not yet a stronger
  agent: branch ordering can differ from recorded-trajectory ordering, and
  search candidate generation remains narrow.  Require counterfactual regret
  before integration or submission.

### N76 — pairwise-ranked enriched macro search

Expand N72's nine reactive task graphs with task templates proposed by
shadow-running N39, V36 and strong replay donors from step zero.  A shadow may
propose/de-duplicate crop, animal, land, hire, fertilizer, logistics and
liquidation task graphs, but no future action tape may enter a branch and no
switch may inherit an incompatible private/task state.

At day/shop/terminal decision points, simulate every compatible task graph for
6/12/24 turns against multiple reactive opponent families and shared future
random seeds.  Compare current lower-quartile money, N74 terminal magnitude and
an N75 pairwise tournament against the forbidden full-state long-horizon
oracle.  Require higher oracle-best top-3 recall, lower regret at
360/600/648, a non-collapsed winning-plan distribution, max action below 600 ms
including feature construction, then an untouched official both-seat gain over
N39.  Only that complete chain authorizes a submission.

## Execution checkpoint: enriched lattice and frozen shortlist

- E106 expanded the native vocabulary from nine to eighteen reactive task
  graphs, then froze seven plans using only the earlier live-focus block.  The
  richer oracle label distribution no longer collapsed to maintenance and
  liquidation: crop hold/expansion, workforce maintenance and a cow-lean route
  all won at least one horizon-24 branch.  This supports shadow policies as
  proposal generators, without treating their future action tapes as legal
  search continuations.
- On the second untouched 20-game S08/S05 block, history and snapshot particles
  both retained the oracle winner in top-3 for every step-360/600/648 case.
  History top-1 was `100/95/95%` with mean regret `$0/$1.53/$2.98`; it did not
  strictly beat snapshot, so the registered belief-superiority gate remains
  failed.  The seven-plan native computation stayed below 354 ms in the
  measured engine-only cases, leaving room for a legal value head but not yet
  proving the all-in 600 ms online budget.
- N76 therefore advances from proposal generation to value validation.  The
  next frozen test is not another heuristic weight adjustment: reproduce all
  119 N75 inference-visible features inside the C++ simulator, verify them
  against Python at replay roots, run a confidence-gated pairwise tournament
  over counterfactual leaves and judge its selected plan against a longer-
  horizon forbidden full-state oracle.

## Execution checkpoint: exact counterfactual value gate

- All 119 inference-visible Python features now have a native C++ equivalent;
  19,040 cross-language values on the untouched S08/S05 block matched within
  `1e-9`.  N75 coefficients and N74 final-value coefficients are generated
  reproducibly from the tracked frozen JSON artifacts rather than copied by
  hand.
- A new label rolls the forbidden full state all the way to the official final
  money objective under shared future seeds and reactive opponent responses.
  This reverses the earlier conclusion based on horizon-24 hand value: the
  plan labels remain diverse, but both learned replay evaluators fail as search
  evaluators.  N75's small step-360 gain becomes a 2.6× regret regression at
  600 and 3.1× at 648; N74 terminal magnitude also loses to legal-marked leaves.
- Iterative depth is the transferable signal.  Forty-eight reactive turns beat
  6/12/24 at all three registered roots while the measured native maximum
  remained 456 ms.  A simple phase-aware score also follows the exact game
  objective: legal-marked assets in broad/mid late play, current money close to
  terminal.  This is closer to a Stockfish-style searched hand evaluator than
  AlphaZero: the current gain comes from deeper simulation and action ordering,
  not a learned value network.

### N77 — frozen 48-turn phase-routed macro search

Freeze `fast_sim/frozen_search_router_e108.json` before listing or downloading
a third replay block.  Keep the E106 seven-plan vocabulary, history-kNN10
particles, two shared synthetic future seeds and maintenance/liquidation
opponent responses.  Search exactly 48 reactive turns; aggregate the legal-
marked leaf margin by lower quartile through decision step 624 and switch to
lower-quartile money margin at step 648 and later.

On the third untouched block, compare this exact router with the same seven
plans at horizon 24 and q25 legal-marked value.  Require no top-3 or mean
terminal-money-regret regression at steps 360/600/648, a strict aggregate
regret gain, non-collapsed terminal-oracle labels and native max below 600 ms.
Only after that transfer may it enter an official both-seat paired arena versus
N39; no submission is authorized by offline regret alone.

## Execution checkpoint: branch transfer passes, policy transfer fails

- The frozen horizon-48 router passed on a third, disjoint 20-game S06r/S07
  block.  Relative to the registered horizon-24 selector it reduced aggregate
  terminal regret 39.9%, improved regret at all three roots, retained diverse
  oracle labels and stayed below the 600 ms native limit.
- A cost-sensitive shallow tree compressed the branch choices into own money
  and shared MILK/WOOL inventory thresholds.  Its external aggregate regret
  beat constant-plan baselines, but the step-648 slice regressed, so the
  learned late branch was rejected before integration.
- The compatible executor exposed the missing control.  In official both-seat
  games, isolated 48-turn substitutions at 360, 600 and 648 all lost badly to
  unchanged N39 (`-98,311`, `-19,379`, and `-10,809` margin respectively on
  the first fixed paired seed).  No runtime fallback occurred.
- The search was answering the narrower question “which of seven coarse
  reactive continuations is least bad?”  It never asked whether N39 should be
  replaced at all.  This is the same failure mode that makes a chess search
  unsound when the legal move generator omits the current best move.

### N78 — base-preserving residual search

Add `KEEP_BASE` as the mandatory reference branch at every root.  Candidate
actions must be bounded residuals over N39's returned action—one market-order
change or one idle-actor task—not a replacement task graph.  Re-run the exact
official game from both seats and shared seeds; stop a residual family as soon
as it loses to base on the first paired seed.  Train or distill a gate only on
residuals that first beat base, keep complete EpisodeIds grouped, and require a
fresh-policy transfer plus broad official paired improvement before submission.

The 48-turn macro router remains useful as an adversarial rollout family and
proposal generator.  It is no longer eligible to control the live agent.

## Execution checkpoint: first KEEP_BASE residual

- The first N78 action is intentionally close to dominance: replace at most
  one N39 `PASS` with `WATER` only when that actor already stands on an
  unwatered plant.  It never changes movement, market orders or a non-idle
  action.
- Across four fresh official seeds and both seats it fired 64 times with zero
  errors, yet every final bank and margin exactly matched an independent
  N39-mirror baseline.  The fixed continuation later spends its originally
  scheduled WATER anyway, so the early service does not release useful work.
- This validates the executor shape and rejects the specific residual.  A
  useful follow-up must carry a repayment/debt model: when work is advanced,
  the later redundant tape action must be identified and safely reassigned,
  otherwise apparent tactical improvements remain economically neutral.

## Execution checkpoint: prepaid-action debt audit

- The first explicit debt ledger recorded each idle WATER and attempted to
  replace a later same-tile redundant WATER with a mature HARVEST.  The
  generated runtime has a synthetic repayment test, and the audit corrected a
  `planted_day == 0` age calculation bug shared with the macro runtime.
- Across five fresh seeds from both seats, 86 prepaid WATER actions fired with
  no fallback, but zero eligible repayment actions appeared.  Every final bank
  and paired margin stayed identical to exact N39.
- The safe `KEEP_BASE` framework remains the right integration boundary.  The
  same-tile harvest debt hypothesis is rejected; future work should mine the
  real downstream N39 action sequence and only build residuals around action
  pairs observed to create usable capacity.

## Execution checkpoint: shadow-donor compatible-point mining

- Exact scored V16/v25, V36, Moon and Soil were run continuously in shadow from
  the start of an unchanged N39 game.  They produced real locally valid work
  for N39 PASS actors, with V16/V36/Soil independently agreeing on four early
  HARVEST points.  Outcome-neutral runs remained exact ties, so candidate RNG
  and state were isolated correctly.
- A new half-open execution window isolated each observed point.  The combined
  V36 HARVEST residual lost `$217` from either seat; individual steps 330 and
  431 lost `$84` and `$201`, while steps 233 and 503 were neutral.  A V36 DROP
  and v25 WATER were also active but neutral.
- This is direct evidence against adopting a donor action merely because it is
  valid, non-redundant and shared by multiple strong routes.  N39's task tape
  has coupled future consequences.  The next residual class should operate on
  bounded market-order quantities and track the later order that it advances,
  delays or cancels.

## Execution checkpoint: first promoted KEEP_BASE market residual

- Availability-aware donor mining separated proposed sales from orders the N39
  shed could actually fund.  The first real causal family advanced an
  executable WHEAT quantity and repaid exactly that quantity from later N39
  sales; no field task or other market order changed.
- A two-unit step-1 advance catastrophically lost `$6,137`, demonstrating that
  quantity conservation alone does not preserve the coupled cashflow route.
  In contrast, one unit at step 119 gained `$2` and eight units at step 120
  gained `$6` from either seat.  The latter retained positive summed pair
  margin over four fresh transfer seeds.
- The raw residual lost `$2.75` average matched margin across V36/C95/V16/v25.
  A public `3 COW / 2 SHEEP` opponent signature isolated the N39-family benefit:
  eight broad games became exact base identities while a fresh N39 mirror kept
  `+$6` from both seats.  This is the first N78 candidate to pass both a
  compatible residual gate and a known-family no-regression gate; it was sent
  as S11 (`55690607`) for live evaluation.
- S11 passed Kaggle validation and then won its first six public matches while
  the rating rose to `1502.1`.  None of those opponents matched `3 COW / 2
  SHEEP` at steps 112 or 120, so the residual stayed off and all six games were
  exact N39 behavior.  This confirms safe rejection on six additional live
  families, but does not yet provide live evidence for the WHEAT intervention.

## Execution checkpoint: latched multi-rule market debt

- Availability-by-step telemetry exposed later repeated sale points.  A
  five-point both-seat screen sharply separated harmful timing (WHEAT steps
  161/165, `-$694/-$771`) from useful timing (WHEAT 215, `+$9.5`;
  FERTILIZER 216, `+$1`; FERTILIZER 240, exactly `+$20`).
- The family classifier must describe the opponent before the intervention,
  not necessarily at it: N39 no longer has its early `3 COW / 2 SHEEP` mix by
  step 240.  The runtime now latches the public step-120 classification and can
  carry several non-overlapping market debts without nesting policy wrappers.
- Combining the prior WHEAT step-120 debt with FERTILIZER step 240 yielded
  `+$23.75` over eight fresh N39-family games and exactly `+$20` over byte-exact
  S11 in eight more.  Eight matched V36/C95/V16/v25 games were exact N39
  identities with zero advanced quantity.  The final artifact was submitted as
  S12 (`55691344`, SHA prefix `08db65d8`), leaving the final slot in reserve.
  It passed validation; the initial `600.0` is backed only by validation episode
  `96807058`, with no public games yet, and must not be read as an LB estimate.
