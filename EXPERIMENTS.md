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
- Kaggle submission: `55651309` (submitted 2026-08-20 17:29 UTC).
- Protocol against exact V36: two development and four untouched holdout seeds,
  both seats for every seed.
- Result: 9/12 wins, paired outcome 0.75 and average margin about +67 coins.
  The four-seed holdout alone produced outcome 0.75 and +61.9 average margin.
- Public-pool check: on matched games against multi-route, adaptive and
  choose-farm, the candidate improved average margin by +127 to +134 coins over
  exact V36 without changing the per-style paired outcome.
- Alternative: quantity 40 also scored 0.75 in a smaller screen, but improved
  average margin by only +70.8 versus +78.2 for quantity 20 on the same screen.
- LB result: COMPLETE at 600.0. In the same poll S02 was 1537.0 and S01 325.3.
  Immediately before S03 completed, S02/S01 were 1447.6/325.3. These snapshots
  differ sharply from earlier ones, confirming that absolute scores and match
  histories are dynamic; the initial same-poll gap S03−S02 is −937.0.
- Decision: negative calibration signal. Keep exact V36 as the online incumbent,
  do not promote q20 and do not spend S04 on another small market-only tweak.
  Require a substantially larger, multi-opponent holdout effect first.

## E010 — H12 crop-substitution probes / no submission

- Goal: test whether confirmed CARROT/TOMATO scarcity can pay for actual
  production rather than the illegal BUY_PRODUCT idea rejected in E004.
- Reproducible generator: `tools/make_v36_crop_variant.py`; it changes only
  bounded BUY_SEED/PLANT actions, can harvest a ripe replacement under the
  unit, and sells only replacement produce actually present in the shed.
- Target scenario: seed `20260619`, whose final CARROT inventory is about 9,196
  and price about 271 after repeated PET_CAFE/FARMERS_MARKET demand.
- Naive large substitutions lost both seats: late WHEAT→CARROT (70 plants)
  averaged -14,476; STRAWBERRY→TOMATO (37 plants) averaged -30,458.
- Balanced micro-windows without harvest repair also lost: day 12 (8 plants)
  -5,115 and day 15 (4 plants) -2,969.
- A local ripe-crop HARVEST repair reduced those losses to -2,824 and -2,332.
  The day-15 probe genuinely sold seven carrots, but the extra unit action
  desynchronized the fixed tape and left seven rather than eight cows.
- Decision: reject crop substitution on the open-loop V36 tape. H12 remains
  open only inside a position-aware scheduler that can replan downstream unit
  paths, feed and harvest timing.

## E011 — H14 sell-after-town delay / no submission

- Change: on a town-consumption step, defer an eligible SELL by one turn only
  when no same-action buy/hire needs its cash and current cash is at least 500.
- Telemetry on the targeted seed: six deferral events, 52 units and seven
  flush orders; the candidate was -412 in the inspected seat.
- Screen: two new seeds × both seats against exact V36.
- Result: paired outcome 0.25 and average margin -207.5.
- Observation: the deterministic town price lift is too small to compensate
  for giving the opponent first access to the post-consumption premium.
- Decision: reject naive one-turn delay. Any future H14 implementation must
  model opponent queue order and conserved inventory jointly with H16.

## E012 — H04 end-of-day harvest reuse / no submission

- Change: at hour 23 only, replace movement/PASS with a local service action.
  Positions reset and carried items auto-drop immediately after this action,
  so next-day route positions are preserved.
- Factorial screen, three new seeds × both seats versus exact V36: WATER-only
  was exactly neutral (paired 0.50, margin 0); peak-HARVEST-only and the full
  service rule both scored paired 0.833 and average margin +46.
- Holdout, six further seeds × both seats versus exact V36: paired outcome
  0.667, 95% bootstrap CI [0.50, 0.833], average margin +34.8.
- Matched public-pool check: two seeds × both seats × multi-route, adaptive and
  choose-farm produced exactly the same 12 banks as exact V36.
- Decision: mechanism pass and retain as a safe planner feature, but do not
  promote as a standalone incumbent or spend S04; its demonstrated effect is
  much smaller than the S03 local-to-LB calibration noise.

## E013 — H01 alternating-day WATER / rejected

- Change: on odd days only, replace WATER on a surviving previously watered
  plant with PASS; same-turn PLANT→WATER is preserved. A second variant reuses
  an already-ripe tile as HARVEST instead of PASS.
- Screen against exact V36: seed `20261240`, both seats. PASS averaged -31,213
  coins and HARVEST reuse -31,207. The first seat of seed `20261241` was also
  catastrophic (-32,593 and -32,581 respectively), so the screen stopped.
- Mechanism: one dry day preserves the plant, but the lost daily yield bonus
  dominates the saved action even before the second dry day would create a
  weed.
- Decision: reject naive alternating WATER. H01 now needs a real marginal
  scheduler that spends a skipped action on something worth more than the
  foregone yield, not a survival-only rule.

## E014 — fresh public-agent refresh / no submission

- Safely decoded six newly published notebook agents without executing
  notebook cells. The extractor now supports arbitrary literal `%%writefile
  *.py` cells, zlib/base85 payload variants, raw `SOURCE_B85`, and a compiled
  transparent-code fallback.
- One-seed screen versus V36 was highly unstable: Moon, ReadTown and X544
  initially showed margins from about +9,700 to +13,200, while later seeds
  reversed Moon/ReadTown sharply.
- Disjoint eight-seed panel (both seats) versus exact V36: X544 won 16/16 with
  average margin +10,417; Soil won 13/16 (+768); Moon and ReadTown each won
  only 4/16 and had negative average margins.
- Cross-family confirmation on three fresh seeds × both seats: X544+H04 won
  6/6 versus Soil (+8,459), but lost 0/6 to Moon (-4,415) and 0/6 to ReadTown
  (-3,761).
- Decision: X544 is the strongest broad local base found, but not universally
  dominant. Keep Moon/ReadTown as explicit adversarial holdouts.

## E015 — X544 local overlays and preemption factorial / candidate gate

- Reproducible generator: `tools/make_x544_variant.py`.
- Generalizing X544's feasible-window seed trim from WHEAT/CARROT to all crops
  was inert: both embedded routes already buy TOMATO/STRAWBERRY/MELON early
  enough, and the four-seed paired screen was byte-for-byte neutral.
- Porting H04 to X544 triggered on some seeds but produced only +5.2 average
  coins over four paired seeds and exactly 0.50 paired outcomes. It is retained
  because it changes only otherwise-dead final-hour movement and did not show
  a negative interaction.
- Lowering X544's preemption price ratio from 1.0 to 0.5 or 0.0, and separately
  matching Moon's fraction/batch settings, produced identical actions on the
  two-seed Moon screen. All variants lost 0/4 with average margin -6,167.
- Decision: the Moon weakness is route-level, not controlled by this threshold.
  Promote X544+H04 as the S04 candidate because of its broad V36/Soil evidence,
  while recording its explicit Moon/ReadTown failure mode.
- Generated candidate SHA-256:
  `fe21fb993be2ab819a31c0dfe29593487955c997e81a6ee659af85650387ef62`.

## E016 — S04 packaging failure / fixed locally, not resubmitted

- Kaggle ref `55652287` ended in `SubmissionStatus.ERROR` during its validation
  episode, before any strategic score was produced. Agent 0 logs showed
  `TypeError: _xv_eod_harvest() missing 1 required positional argument: 'step'`.
- Root cause: `kaggle_environments.agent.get_last_callable` executes the last
  callable inserted into the submission module's globals. Redefining the
  existing `agent` key does not move it to the end of Python's insertion-ordered
  dict, so the loader selected the later `_xv_eod_harvest` helper. The old local
  arena imported `module.agent` directly and therefore could not detect this.
- Fix: the generator now emits a final `kaggle_entrypoint = agent` alias after
  every helper and metadata assignment. A regression test calls the official
  `get_last_callable` and the full-game test now loads `main.py` by path.
- Verification: 14/14 unit tests pass; `py_compile` passes; the exact loader
  selects a two-argument function named `agent`; full 720-turn path-loaded
  games in both seats finished `DONE` (145,162 and 173,763 versus `starter`).
- Corrected local candidate SHA-256:
  `839d2244af3498541624a70c156bf8801c22838dc67eefa6641a9e97ca1f1efa`.
- Decision: S04 supplies no evidence about strategy. Do not make a fifth
  submission without fresh user authorization.

## E017 — H22 early public family selector / promoted locally

- Compatibility discovery: public X544, Moon and Read agents emit identical
  actions through the opening; X544 and Moon first diverge at step 72, exactly
  when the first town shop becomes observable. V36/Soil use a distinct step-0
  opening.
- Legal public classifier: after the common step 0, inspect only the opponent's
  public tiles. An opening `PASTURE` selects Moon; no pasture selects X544. The
  selected whole-season route is frozen, avoiding mid-route state mismatch.
- Development evidence, four seeds × both seats: replacing X544 with Moon
  against the older pasture-opening family improved multi/adaptive from 0/8 to
  7/8 and choose from 7/8 to 8/8. Average margins changed from about -5,404 to
  +702 and from +547 to +6,715 respectively.
- Frozen holdout `20261800..20261803`, both seats, eight opponent families,
  64 games per candidate: fixed X544 outcome 0.390625, average margin +274 and
  worst-family outcome 0; selector outcome 0.78125, average margin +3,191.7 and
  worst-family outcome 0.375. Per-family selector outcomes were V36 0.875,
  Soil 0.75, X544 1.0, Moon 0.50, Read 0.375, multi 0.875, adaptive 0.875 and
  choose 1.0. V36/Soil match banks were byte-for-byte unchanged from X544.
- Shadow-init incident: omitting Moon's step-0 call destroyed its route state.
  Calling it on the live observation risked shared-process side effects. The
  final implementation initializes Moon on deep copies and restores Python's
  RNG; its 64 frozen results exactly reproduce the successful prototype.
- Arena improvements: `--jobs` multi-process evaluation, pinned
  `PYTHONHASHSEED=0`, and observable shop-unlock event capture.
- Artifact gate: 15/15 tests; `py_compile`; official loader selects `agent`;
  four full path-loaded matches against V36/Moon finished `DONE`; frozen-panel
  maximum action latency 143 ms. Candidate size 300,499 bytes, SHA-256
  `642e4209da47f755ae1d780a21bce679bb2ce716a88ca771fc6151797f59ff08`.
- Decision: H22/H11 pass with a large disjoint multi-family improvement. Promote
  locally, but do not make a fifth Kaggle submission without user permission.

## E018 — H22 transfer panel and public behavioral checkpoints

- Added deterministic, inference-visible opponent checkpoints at steps 1, 12,
  24, 48 and 72 to `arena.py`. They contain only public farm/money/layout/hire
  features; no opponent private inventory, replay seed or action is exposed to
  the policy. `tools/compare_openings.py` verifies exact first-action divergence
  while isolating shadow observations and Python's process-global RNG.
- Independent seeds `20262100..20262101`, both seats, the same eight-family
  panel: fixed X544 macro outcome was 0.375; the promoted selector was 0.750.
  Per-family selector outcomes were V36 0.50, Soil 1.0, X544 1.0, Moon 0.50,
  Read 1.0, multi 1.0, adaptive 1.0 and choose 0.0. This is a second disjoint
  panel, not a retune of E017.
- All pasture-opening families remained byte-identical in public farm features
  through step 72. Exact shadow comparison confirmed X544 first diverges from
  Moon/Choose at step 72, after the first shop is revealed; Read first diverges
  at step 152 on the inspected ICE_CREAM/PIZZA route. Therefore a perfect
  pre-divergence classifier inside that clone family is impossible from public
  state alone.
- A 24-seed, both-seat Moon-vs-Choose probe produced outcome 0.625, average
  margin +132.9 and bootstrap 95% CI [0.479, 0.771]. Narrow rules based on the
  first one or two shops were inconsistent and did not justify a third branch.
- Decision: retain the two-branch selector unchanged. H22 transfers across a
  second panel, but family-level uncertainty and CI must remain explicit.

## E019 — H02 schedule-blind alternate-day FEED / rejected

- Generated a reproducible V36 route ablation that replaces every `FEED` on
  odd days with `PASS`, preserving unit positions and all other actions.
- Fresh seeds `20262300..20262303`, both seats versus exact V36: outcome 0/8,
  average margin -70,983 and worst margin -77,955. On an inspected final state,
  the ablation retained only three cows while the reference retained eight cows
  and four sheep; most animals escaped after consecutive missed feeds.
- This is substantially worse than the earlier sparse-CARE screen. A calendar
  parity is not a safe proxy for each animal's `consecutive_unfed` state because
  the tape does not necessarily visit every animal on the following day.
- Decision: reject schedule-blind feed sparsity. H02 now requires a per-animal
  deadline ledger plus a guaranteed next-day service assignment; do not mutate
  an open-loop tape by day parity.

## E020 — H05 exact terminal overflow audit / mechanism pass, no overlay

- Added own-private storage-pressure summaries to `arena.py` and an exact
  engine hook in `tools/audit_overflow.py`. The hook replays the documented
  stable inventory/item insertion order immediately before the official EOD
  drop, reports discarded items, and then calls the unmodified engine function.
- Fresh seeds `20262400..20262403`, both seats: against Choose, 6/8 games
  discarded exactly 12 WHEAT on day-28 EOD; against V36, 4/8 discarded exactly
  7 WHEAT. Across 16 games the only 100 discarded units were WHEAT. CARROT,
  MILK, WOOL and FERTILIZER were already preserved by the current unit/item
  order, so the feared premium-item loss did not occur.
- A generated same-turn `PLACE WHEAT`→`SELL WHEAT` overlay forecast the exact
  12-unit overflow but was inert: no wheat-carrying unit was on a shed-access
  square at step 695. All such workers were several moves away. Recovering the
  low-value surplus therefore needs earlier terminal routing, not a safe local
  action substitution.
- Decision: H05 mechanism and natural trigger pass, but do not promote the
  overlay. The observed upper-bound value is small relative to six-figure
  scores and belongs in H21's multi-turn terminal solver.

## E021 — H09 bounded weed repair causal ablation / local pass

- Added `tools/make_weed_repair_ablation.py`, which disables only the returned
  weed-repair action while still evaluating the original repair for telemetry.
  The fixed route, market overlay, RNG and every other policy component remain
  unchanged. `arena.py` now snapshots optional agent telemetry in each match.
- Fresh seeds `20262500..20262507`, both seats, against the exact corresponding
  base agent: Moon without repair scored 0.34375 with average margin -414.0;
  X544 without repair also scored 0.34375 with average margin -454.2. Their
  paired bootstrap 95% intervals were [0.21875, 0.46875] and [0.15625, 0.50].
- The counterfactual repair changed at least one unit action in 9/16 matches in
  each branch. Across those triggered matches, disabling it cost an average
  -736.0 coins for Moon and -807.4 for X544. In all seven no-trigger matches per
  branch, candidate and exact-base banks were identical, confirming zero
  strategic side effect when no relevant weed collision occurred.
- A few triggered games were neutral or slightly better without repair, so the
  transaction is not pointwise optimal. Its aggregate effect is nevertheless
  clearly favorable on two separately wrapped routes, while the eight-step
  replay bound prevents unbounded route drift.
- Decision: H09 local pass. Retain the existing bounded repair in both branches
  of the promoted H22 selector; no `main.py` change is required.
