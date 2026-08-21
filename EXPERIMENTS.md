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

## E022 — H21 pressure-gated pre-EOD routing / promoted locally

- Exact engine audit clarified the action order: at day-28 EOD the Moon route's
  shed was empty and eleven inventories held 112 units. The automatic stable
  drop accepted 100 and discarded the final 12 WHEAT. A last-turn shed sale
  cannot help because there is nothing in the shed yet; a worker must reach a
  shed-access tile, `DROP`, and sell before the automatic drop.
- Added `tools/trace_terminal_state.py` and a reproducible fixed-actor generator
  `tools/make_terminal_route_variant.py`. The causal screen starts at step 689,
  routes hand 0 and hand 1 by shortest unlocked paths, and sells their dropped
  inventory on the same turn. On the original overflow seed, hand0, hand1 and
  both together improved both seats by +468, +424 and +647 coins respectively.
- Fresh Moon mirror seeds `20262600..20262607`, both seats: the two-worker route
  won 16/16 against the exact selector base with average margin +626.5 and
  paired bootstrap 95% CI [1.0, 1.0].
- The ungated route harmed X544-family games and low-pressure Moon games. A
  public/private-own-state gate fixed both failures: run only after the H22
  selector has frozen `moon`, and only when shed plus carried inventory is at
  least 90 on step 689. On a two-seed × both-seat × four-family transfer panel,
  V36, Soil and low-pressure Moon games were exactly neutral. In triggered
  Read/Choose games own-bank lift was +530 to +819 with no outcome regression.
- Exact post-promotion overflow audit on seed 20262400 removed both 12-WHEAT
  drops and increased own bank by +577 in each seat. The promoted artifact
  passes 23/23 tests, `py_compile`, the official insertion-order loader and
  full path-loaded games on both selector branches. Size is 305,555 bytes;
  SHA-256 is `541d421f272666da360699e365a26cba96721577a957ed51f15c0f442586aa9f`.
- Decision: H21 local pass and promote. This is an own-state terminal overlay;
  it does not inspect opponent private state and is inert outside the gated
  Moon pressure regime.

## E023 — H03 natural same-turn dependency audit / trigger absent

- Added `tools/audit_same_turn_chains.py`, which reconstructs official executed
  unit order from each pre-action observation and detects only causal co-located
  chains: `PLANT→WATER`, ripe `HARVEST→PLANT`, and matching
  `BUILD_{COOP,BARN}→PLACE_{animal}`. Synthetic unit tests pin each classifier.
- Seeds `20262900..20262902`, both seats, were audited separately on the frozen
  X544 and Moon selector branches: 12 full games and 8,628 executed candidate
  turns in total. The number of qualifying dependency chains was exactly zero.
- Therefore the engine mechanism remains valid (E008), but it cannot explain
  the incumbent routes and there is no existing second action to ablate. Adding
  chains would require co-locating units and rescheduling upstream movement,
  which is H06's rolling scheduler rather than a safe local overlay.
- Decision: H03 partial reject for the current fixed-route candidate. Do not
  mutate `main.py`; revisit only together with an H06 scheduler/layout search.

## E024–E027 — public refresh and market-timing causal split

- Full replacement by the public V27 and C95 artifacts lost all 16 paired
  games per candidate to the incumbent, with average margins -14,725.9 and
  -14,088.1. Both routes already differ from the incumbent at step 0, so a
  state-compatible midgame graft is unavailable.
- A small screen advanced an already scheduled sale by exactly one turn and
  removed the same quantity from the following turn. WHEAT and the combined
  WHEAT+FERTILIZER variant won their clone mirror, but transferred badly to
  X544/Moon/Choose: WHEAT cost as much as 4,847 margin and 0.50 outcome.
- FERTILIZER-only was non-negative on every affected family: +87.5 margin vs
  X544, +126.5 and +0.25 outcome vs Moon, and +55.5 vs Choose on the exact
  same seeds and seats. All advanced quantities were fully repaid.
- Moving the initial feed purchase to the first market slot lost 3/4 games;
  changing six feed wheat to five was effectively neutral (+6 average).
- Decision: reject whole-route refresh, WHEAT, the combined overlay and both
  opening changes. Continue only with the conserved FERTILIZER mechanism.

## E028–E029 — FERTILIZER cap/window and eight-family transfer

- Cap 10 beat cap 5 in all eight paired games by +7 to +21 coins. Start 0 was
  identical to start 120 because no earlier natural trigger existed; start 240
  was consistently one coin worse. Keep the bounded step 120–714 window.
- Against eight public families on the exact E026 seeds, cap-10 FERTILIZER had
  no outcome regression and improved every same-seed average margin: V36 +6,
  Soil +5, X544 +98.5, Moon +134, Choose +64.5, V16 +5, V27 +20 and C95 +1.5.
  Telemetry recorded roughly 62 units advanced and exactly 62 repaid per game.
- Decision: local pass for FERTILIZER-only cap 10; require a fresh holdout.

## E030–E032 — H21 terminal parameter and final-call audit

- Adding a third routed worker lost 8/8 with average margin -68.5. Starting at
  step 688 instead of 689 lost 8/8 with average margin -471.2.
- Threshold 80 was mirror-neutral when pressure was 92–108, but added a real
  trigger at pressure 81 against related families and reduced their margin by
  about 31 coins. Retain threshold 90.
- At steps 717–718, Moon/X544 branches already carried zero inventory. The
  other branch already sold 33 units at step 717 and the remaining five at
  step 718. A new terminal relay would be inert or duplicate existing code.
- Decision: reject all four terminal variants and retain H21 unchanged.

## E033 — FERTILIZER cap-10 independent holdout / promotion gate pass

- Fresh seeds `20263700..20263703`, both seats: FERTILIZER beat the exact
  incumbent in 7/8 games with average margin +139.75. One seed exposed the
  expected first-seller interaction (-3,213 from one seat, +3,887 from the
  other), while the paired mean remained positive.
- Exact incumbent controls on the same public-family games showed unchanged
  outcomes and positive candidate margin deltas: X544 +71.75, Moon +139.75,
  Choose +50.75. Average telemetry was 65 advanced and 65 repaid units.
- Decision: promote the one-turn, debt-conserved FERTILIZER sale with cap 10,
  steps 120–714. Do not include WHEAT or alter H21.

## E034 — promoted artifact preflight and S05 submission

- Promoted `main.py` is byte-identical to the E028–E033 candidate: 309,836
  bytes, SHA-256 `4ddec3eafa9840e4bb7b07b9d37d4af2835c8bbcf8cf2411c776f96e662788aa`.
- Passed 26/26 unit tests, `py_compile`, official last-callable loading and full
  path-loaded games on both selector branches. Observed maximum action latency
  was 62.76 ms; preflight telemetry repaid exactly 62/62 and 68/68 advanced
  FERTILIZER units.
- Submitted once as S05, Kaggle ref `55666404`, at 2026-08-21 09:51 UTC+7.
  Initial Kaggle status: `PENDING`; four daily submissions remained afterward.
- Decision: do not spend another authorized submission while S05 is pending.

## E035 — historical Kaggle agent-solution review / no submission

- Reviewed primary top-solution write-ups from Halite, Hungry Geese, Lux AI
  Seasons 1–3 and Kore 2022.  Winning methods span hierarchical rule/planning,
  imitation learning and distributed self-play RL; method choice follows joint
  action structure and rollout budget rather than the competition label.
- Closest structural analogues are Halite 2020 and Lux S2: both favored a
  `score/role -> plan/goal -> coordinated actions` architecture after exposing
  the difficulty of long-horizon multi-unit credit assignment.
- Successful RL solutions used millions to billions of steps plus legal masks,
  curriculum, teacher KL and historical opponent pools.  Replay IL was a much
  cheaper warm start in Lux S3 and Kore, but required inference-visible state
  reconstruction and still benefited from a rule layer.
- Added concrete N16–N29 experiments in
  `HISTORICAL_AGENT_COMPETITIONS_2026-08-21.md`: shadow policies, compatibility
  graph, common opening, reactive task planner, scored donor extraction,
  donor/overlay shootout, replay residual IL, public-medoid best-response RL,
  replay-state curriculum, opponent conditioning, safe macro mixtures and
  short-horizon forward simulation.
- Decision: do not start pure end-to-end PPO.  First execute N20/N21/N23 while
  building N16/N17; learned work begins with N24 residual imitation and then
  N25 masked macro best response.

## E036 — exact scored donor extraction and N21/N22 shootout

- Kaggle's version UI ties V16-RC5's Best Score `2913.3` to V2,
  `scriptVersionId=341905759`, and v25's current Best/Public Score `3009.0` to
  V2, `scriptVersionId=341206423`.  Latest source is V2 in both cases; the
  earlier `2905.7` v25 card snapshot was stale.
- CLI-pulled notebooks and metadata are frozen under `research/scored_versions`.
  The exact extracted agent hashes are V16
  `f029fa0cb66a9eb509afbe44e3f59b800332d0419db91607183410e4089c4d19`
  and v25
  `9bdfbafb6755067182d88ce594fd46fb1d712713ffd6931e83d5d50e84bc6fb2`.
  `extract_embedded_agent.py` was extended to recognise a literal
  `"".join((...))` payload without executing notebook code.
- Fresh direct panel `20264000..20264007`, both seats: S05 beat V16 14/16,
  paired outcome 0.875 and average margin +7,607.6; S05 beat v25 16/16 and
  +12,921.3.  v25 lost to V16 0/16 with -26,273.1 average margin.
- Fresh eight-family screen `20264100..20264101`, both seats, 32 games per
  candidate: S05 won 32/32 with average margin +5,917.3 and worst-family
  outcome 1.0; V16 scored 8/32 (0.25), -5,061.0 and a zero worst family; v25
  scored 0/32, -16,857.7.
- Decision: N20/N21 complete and N22 passes for S05.  Keep S05 as route base;
  donor-card rating is not a cross-play selector.  Transfer only independently
  justified mechanisms, never the whole V16/v25 tapes.

## E037 — N16/N17 shadow-run compatibility graph

- Added `tools/make_shadow_switch.py`.  Both embedded policies receive every
  live observation from step 0 on deep copies, maintain independent RNG
  streams and internal state, while only the selected branch's action is
  executed.  Generated artifacts compile and all 26 repository tests pass.
- Against exact S05 on seed `20264200`, both seats, every V16/v25↔S05 switch at
  steps 1, 72 or 240 lost 0/2.  Average margins ranged from -26,451 to
  -106,601.  Even step 1 was unsafe: the first action had already moved the
  physical route into an incompatible state.  Shadow memory cannot repair a
  different farm geometry.
- Positive control at the known shared X544/Moon prefix used step 72.  On
  `20264300..20264301`, both directed switches had paired outcome 0.5 and
  exactly zero paired average margin versus the target family.  Maximum action
  latency was 156.3 ms, below the one-second limit.
- Decision: N16 mechanism works, but N17 admits only evidence-backed compatible
  edges.  X544↔Moon at 72 is safe in paired outcome; S05↔V16/v25 has no safe
  tested edge.  N18's common-opening condition is mandatory, not optional.

## E038 — cap-diverse preflight and S06r/S07 submissions

- Chose two conservative active variants after rejecting donor replacement:
  FERT cap5 SHA-256
  `48985f00cc312f2703b4d6cfa8260c56ceaead6d394abf67b89ee59438f7eeb3`
  and the exact S05/cap10 SHA-256
  `4ddec3eafa9840e4bb7b07b9d37d4af2835c8bbcf8cf2411c776f96e662788aa`.
  They differ only in the debt-conserved one-turn FERTILIZER quantity cap.
- Cap5 passed `py_compile`, the official last-callable loader and 16 fresh
  paired games.  Against X544/Moon/Choose its outcomes were 1.0/0.75/1.0;
  maximum action latency was 91.4 ms.  Versus cap10 it scored 0.25 with only
  -10.0 average margin, consistent with the earlier small cap10 advantage.
- The first cap5 upload failed before ref creation due an SSL EOF and consumed
  no quota.  Retry S06r is Kaggle ref `55673154`; S07 exact cap10 copy is ref
  `55673148`.  Both were `PENDING` immediately after upload and two daily
  submissions remained, preserving the required reserve.
- Decision: monitor S06r/S07; do not spend either remaining slot without a new
  stable candidate or a validation-error repair.

## E039 — identical-artifact leaderboard variance / submission policy correction

- S06r/cap5 moved `600.0 → 1646.6 → 1737.0`; S07/cap10 moved
  `692.1 → 1451.1 → 1476.5`.  Most
  importantly, S07 is byte-identical to S05 (same SHA-256
  `4ddec3eafa9840e4bb7b07b9d37d4af2835c8bbcf8cf2411c776f96e662788aa`),
  while S05 previously completed at `2252.1`.
- The same executable therefore changed by `-1560.0` rating points across two
  submissions.  This is direct evidence that a Kaggriculture LB score is not a
  deterministic evaluation of the artifact on a frozen private test set; the
  live opponent sample, current population and/or rating context materially
  affect the displayed result.
- The cap5/cap10 comparison is not identifiable from these two independent LB
  scores: their 92.1-point gap is confounded by different matches.  Controlled
  paired local games remain the causal selector; the LB is a noisy live-meta
  probe and deployment check.
- Decision: reject blind duplicate resubmission as a way to lock a good score.
  Keep the strongest validated policy active when possible, submit only
  materially distinct locally gated candidates, retain one repair slot, and
  treat a last-minute refresh as risk rather than guaranteed score recovery.

## E040 — N27 contextual-bandit route selector

- Added a causal route-control generator and collected full-feedback results
  for frozen X544 and Moon routes on fresh two-seat games.  A depth-one policy
  learned only from public step-1 features selected X544 when starting money
  was at most 12 and Moon otherwise, independently reproducing H22's pasture
  opening rule.
- Training exact-route accuracy, outcome-optimal rate and leave-one-family-out
  accuracy were all `1.0`.  On unseen V16/V25/V27/C95/V20/Tie lineages the
  exact margin-tiebreak route accuracy was `4/6`, but all six choices were
  outcome-optimal with zero outcome regret; both apparent misses were tied
  wins whose routes differed only in margin.
- Decision: N27 passes as an independently learned selector, but it introduces
  no main-policy change because its learned stump is equivalent to H22.

## E041 — N24 macro imitation / residual pilot

- Added inference-aligned replay extraction: each public observation at turn
  `t` is paired with the task and market macro executed at `t+1`.  Scored V16,
  scored v25 and S05 produced 4,314 rows per split, 1,438 per agent, with
  disjoint-season pilot and holdout seeds.
- Small class-balanced linear rankers did not reproduce critical task actions.
  Holdout task accuracy/top-3 was S05 `0.321/0.606`, V16 `0.204/0.415` and v25
  `0.111/0.225`.  S05's market model was stronger at `0.660/0.917`, with sell
  recall `0.892` and hire recall `0.815`, but buy-product recall was only
  `0.268`; donor market models were weaker and missed important rare classes.
- Decision: reject the pilot as an action executor.  Retain only the S05 market
  top-3 ranker as a possible proposal signal beneath the legal/rule executor;
  do not graft learned actions into `main.py`.

## E042 — N29 short-horizon FERT lead factorial

- Clone mirrors showed that a global two-turn lead beat the incumbent for cap
  5/10/20, while a global three-turn lead was stronger in-clone.  The broader
  family panel exposed the causal split: lead 2 improved Moon-routed families
  but mildly hurt X544-routed families; global lead 3 caused roughly -314
  margin on X544 and Choose and was rejected.
- A route-gated candidate therefore kept X544 at lead 1 and used lead 2 only
  on Moon.  It exactly reproduced the incumbent on the X544 route and the
  tested lead-2 behavior on Moon.
- Decision: reject global horizon changes and advance only route-conditioned
  timing.

## E043 — N29 route-conditioned holdout

- Fresh seeds `20265000..20265002`, both seats, covered V36, Soil, X544, Moon,
  Choose, Read, V25 and C95.  The route-gated candidate had no outcome
  regression: exact zero margin delta on all X544-routed families and positive
  deltas of about +21 to +24 on the tested Moon-routed families.
- Mean margin delta across the eight-family panel was `+11.06`.  Candidate
  SHA-256 is
  `cfd922d83e6cc71d95f6441fe0581d3c2c730a76eedc49f17fa5c8bf6eccbe4e`.
- Submitted as S08, Kaggle ref `55674010`; it completed with an initial
  `600.0`, which is not yet a stable live rating.  Kaggle reported one
  remaining daily slot, so the refined S09 artifact is held as the
  repair/reserve submission until S08 has a meaningful live history.

## E044 — N29 late-window refinement / local promotion

- On top of the Moon lead-2 candidate, lead 3 was tested only in early, middle
  or late game.  Early was inert, middle lost badly, while steps 480–714 won
  all 8/8 clone-mirror games with exactly +19 average margin.
- An external five-family screen preserved all outcomes and had deltas
  `0/0/+2/0/+2` versus the route-gated base.  This bounded late window was
  promoted to `main.py`: X544 lead 1, Moon lead 2, and Moon lead 3 only for
  steps 480–714.  SHA-256 is
  `3bd8b8d3c66b5c9884953ac55a5d6e5eac4237e3b32662e777b570062afe43a1`.
- Preflight passed 35/35 tests, `py_compile`, official last-callable loading
  and content-equivalence against the tested candidate.  A final fresh
  path-loaded 8-game smoke versus S08 scored paired outcome `0.75` and average
  margin `+14.0`.  Decision: hold this as S09 until the final daily slot is
  justified by stable S08 evidence or the quota reset.

## E045 — N28 safe macro exploration

- Evaluated stochasticity only at the state-compatible H22 route branch using
  paired full-feedback X544/Moon reports.  The robust grid fit recovered the
  deterministic selector exactly: Moon probability `0` without an opening
  pasture and `1` with one.
- On training families deterministic H22 had mean expected outcome `0.8125`,
  worst-family outcome `0.25` and zero regret.  A 95/5 route flip reduced these
  to `0.79375`, `0.2375` and introduced `0.01875` mean regret.  On holdout the
  deterministic policy was `1.0/1.0`; 95/5 reduced the worst family to
  `0.9875`.
- Decision: reject epsilon exploration in live matches.  Exploration remains
  an offline experiment-selection mechanism; deployed play is deterministic.

## E046 — N25/N26 exact public replay league

- Downloaded ten public S05 ladder replays and added an extractor that maps the
  action stored at replay state `t+1` back to observation step `t`.  The
  generated tape is explicitly restricted to its original public seed and
  seat; it is not treated as recovered source code.
- Exact S05 (`4ddec3...`) reproduced all three recorded losses down to the
  final banks: `88377:89444`, `102375:102669` and `94909:96039`.  This fidelity
  gate must pass before counterfactual candidates are accepted.
- The first timing league found no outcome flips: current N29 improved average
  loss margin by `+19.3`, while removing the FERTILIZER overlay worsened it by
  `-56.7`.  A replay-state curriculum retained 74 unique inference-visible
  rows across negative bank swings, market collisions, storage pressure and
  terminal-market strata.
- Decision: use replay tapes as a high-value best-response screen and N26
  curriculum source, while retaining broad public-family holdouts against
  adaptive source agents.

## E047 — premium-sale best response and cap sweep

- Generalized the debt-conserved market overlay to all sellable products and
  screened MILK, WOOL and STRAWBERRY separately.  The combined premium overlay
  moved only quantities already scheduled for a later sale and repaid every
  advanced unit.
- On the three exact loss replays, premium `cap=24` improved average margin by
  `+687` and flipped the Himanshu loss to a `+1284` win.  The cap sweep kept the
  same one improvement and zero regressions at 5/10/24; `cap=10` was best on
  average at `+694.3` versus baseline and was selected as the smaller action.
- A seven-win replay holdout preserved all `7/7` wins and raised average margin
  from `+6321.0` to `+6663.7` (`+342.7`).  The replay evidence therefore
  contains both recovered losses and untouched wins.

## E048 — N31 broad holdout and local promotion

- The initial `cap=24` eight-family holdout improved mean family outcome from
  `0.8125` to `0.84375`, added `+172.4` average family margin and caused no
  family outcome regression.  Inventory naturally route-gated the products:
  X544-like farms advanced MILK/WOOL, while Moon-like farms advanced
  STRAWBERRY/WOOL; all debt was repaid exactly.
- A fresh cap10 panel on seeds `20265600..20265601`, both seats, preserved the
  V36/Moon/Read/C95 outcomes.  Margin deltas were `-146.0`, `+444.5`, `+467.8`
  and `-55.0`; the two small safety-family costs did not alter wins.
- Promoted N31 to `main.py`: FERTILIZER, MILK, WOOL and STRAWBERRY are advanced
  by at most 10 units, with X544 lead 1, Moon lead 2 and Moon lead 3 only on
  steps 480–714.  Artifact SHA-256 is
  `df06a07f9d83b07f504d00f5d9f742e0152bdc463e5d54ae6a6ac9f7b5b526c7`.
- Preflight passed 49/49 tests, `py_compile`, official last-callable loading,
  a changed-file secret scan and path-loaded games from both route families.
  The promoted smoke won 4/4 against V36 and Moon; maximum observed action
  latency in the replay holdout was 145 ms.  Decision: candidate is ready for
  the next autonomous daily slot, while the current final slot remains the
  required reserve.
- Latest read-only ladder checkpoint: S08 rose to `2086.9` and S06r to
  `1919.2`; both remain live ratings rather than frozen artifact scores.  No
  upload was made because the one remaining current-day slot is the reserve.

## E049 — N32 delayed public-state classifier / rejected

- Shadow-ran both compatible routes to step 112 and selected from the
  opponent's public active-hand count.  On the three exact loss replays this
  won `2/3` instead of N31's `1/3` and improved average margin to `+399.7`.
- A fresh V36 game exposed catastrophic transfer failure (about `-7996`
  average margin).  The public fingerprint correctly recognized the observed
  farm shape, but that shape did not make the fixed Moon continuation robust
  to a different shop/RNG trajectory.
- Decision: reject N32.  Delayed public classification is valid machinery,
  but a behavioral fingerprint is not proof that the counter-route is safe.

## E050 — N33 compatible switch localization / rejected

- Exact Uri replay sweeps localized the decisive X544/Moon macro divergence:
  switching through step 264 won, while step 268 and later lost.  Telemetry
  showed the step-264 choice was two COWs versus two SHEEP, followed by a
  different downstream task route.
- The step-264 switch flipped Uri to `+937`, but a fresh Soil screen lost both
  seats by `-613` despite an aliased public state.
- Decision: reject live switching at that state.  Compatibility prevents
  invalid internal memory, but it does not remove partial-observation aliasing.

## E051 — N34 bounded animal response / rejected

- Replaced only an already scheduled two-COW macro with two SHEEP on the
  recognized public state and translated exactly the matching pickup/place
  actions.  Telemetry confirmed `2/2/2` purchase, pickup and placement events.
- Uri nevertheless worsened from N31's `-718` to `-1751`.  The profitable
  Moon response is a coupled downstream task plan, not an isolated animal
  substitution.
- Decision: keep the bounded reactive-task infrastructure, reject this macro.

## E052 — N35 Moon premium-lead sweep / rejected

- Swept global and late-window Moon sale leads through 24 turns.  Lead 6
  improved Naru from `-998` to `-757` (`-749` at cap 24), but reduced the
  Himanshu win from `+1308` to `+703` (`+660` at cap 24).
- Across all three exact losses, cap-10 lead 6 averaged `-257.3`, worse than
  N31's `-136.0`; longer horizons deteriorated further.
- Decision: retain N31 timing and reject N35.

## E053 — N36 shop-aware compatible selector / local promotion

- Full-feedback route results revealed a stable public interaction: pasture
  openings normally prefer Moon, except when the first public shop at step 72
  is `YARN_STORE`, where X544 is safer.  Non-pasture openings remain X544.
  Both branches are shadow-run with isolated RNG until the decision.
- A first implementation mistakenly re-measured the opening pasture at step
  72; the broad screen caught the resulting V36 regression.  The promoted
  implementation freezes that feature at step 1 and observes only the shop at
  step 72.
- On fresh seed `20265700`, both seats, eight families, mean outcome improved
  from N31's `0.7500` to `0.9375`: X544 moved `0/2 -> 1/2`, Choose
  `0/2 -> 2/2`, and no family regressed.  On the independent two-seed E048
  panel, N36 exactly preserved mean outcome `0.84375` and slightly improved
  average family margin (`3047.4` versus `3039.6` for cap 24).
- The exact loss league retained the Himanshu flip and improved average margin
  from N31's `-136.0` to `+88.3`; all seven recorded wins remained wins.  The
  final artifact passed 56/56 tests, official loading and full-game screens.
- Promoted artifact: 312,211 bytes, SHA-256
  `a51cc84460a852301bfb46bb3bc6e1289181dbdace6d97402aa1aa90c6519a86`.
  It is the primary post-reset candidate; N31 remains the second independent
  candidate and one Kaggle submission remains reserved.

## E054 — N36 independent full-feedback regret audit / no N37 change

- Extended the fixed-route generator to preserve N36's isolated shadow RNG,
  then evaluated frozen X544 and Moon on seeds `20265800..20265801`, both
  seats, against eight public families.  This removes the earlier RNG-policy
  confound from route counterfactuals.
- Across 32 paired contexts, N36 selected an outcome-optimal route in `32/32`
  cases: outcome-optimal rate `1.0`, mean outcome regret `0.0`.  Mean outcome
  was `0.875` versus `0.625` for fixed X544 and `0.6875` for fixed Moon.
  The observed first shops were BAKERY, FARMERS_MARKET and PET_CAFE; every
  shop subgroup also had zero regret.
- Exact margin-tiebreak accuracy was `0.96875`; the single miss was an outcome
  tie and therefore is not evidence for a more complex selector.
- Decision: do not create N37.  Keep the simpler N36 rule and treat additional
  context splits as overfitting until they improve outcome on an independent
  full-feedback panel.

## E055 — latest-10 S08 live-meta replay league

- Downloaded the ten chronologically latest public S08 episodes before
  inspecting their outcomes: eight wins and losses to kevin park (`-526`) and
  Rikito Kanda (`-478`).  Exact S08 (`cfd922d8...`) reproduced all ten final
  banks, so the counterfactual fidelity gate passed.
- N31 preserved `8/10` and improved average margin from S08's `+3384.7` to
  `+3985.2`.  N36 reached `9/10`, average `+4728.8`, with one improvement and
  zero regressions.  The kevin loss became a `+6136` win; Rikito improved to
  `-371` but remained a loss.
- Decision: the current live meta independently supports N36 as the first
  post-reset submission and N31 as the second conservative candidate.

## E056 — N38 Rikito route/timing counterfactual / rejected

- Frozen isolated-shadow routes showed that Rikito is not a selector error:
  Moon scored `-371` versus X544's `-665`.  Swept global Moon sale leads
  `1,3..12,16,24`; lead 11 was best at `-51`, but none changed the outcome.
- Cap sweeps `5/15/20/24` at leads 10 and 11 were effectively inert and also
  failed to flip the replay.  The earlier N35 league already showed that long
  leads reduce margins against other opponents.
- Decision: reject N38 without spending a broad holdout or LB slot.  A
  51-coin tape-specific margin gain is not enough evidence for a risky global
  timing change.

## E057 — second chronological S08 replay holdout

- Downloaded the preceding ten public S08 episodes as a chronological holdout.
  Exact S08 reproduced all ten recorded banks, winning `9/10` with average
  margin `+9120.4`.  N31 and N36 also won `9/10`, both averaging `+9267.9`;
  the only shared loss was Dariush Afshar at `-71`.
- Across the combined twenty S08 ladder episodes, S08 and N31 each won
  `17/20`, while N36 won `18/20`.  N36 averaged `+6998.35`, a `+745.8`
  improvement over exact S08, with one outcome improvement and no regression.
- Decision: the selector gain persists across two disjoint chronological
  batches and is not explained by the latest-ten sample alone.

## E058 — N39 X-route lead-2 promotion

- On the exact Dariush loss, advancing already scheduled X-route sales by
  2--6 turns flipped `-71` to a win; lead 3 was best on that single tape at
  `+921`, while lead 2 scored `+897`.  This was treated only as a diagnostic,
  not sufficient promotion evidence.
- Fresh seeds `20265900..20265901`, both seats and eight public families gave
  32 matches per candidate.  Lead 2 and lead 3 caused zero outcome changes
  versus N36; lead 2 was the safer variant, adding `+245.44` mean family
  margin versus `+196.94` for lead 3 and having smaller V25/C95 costs.
- On twenty exact S08 ladder replays, N36 won `18/20`; both lead variants won
  `19/20` with no regression.  Lead 2 averaged `+7028.85`, flipped Dariush to
  `+897`, and retained the selector's kevin park flip.  On ten older S05
  replays it preserved N36's `8/10` and improved average margin by `+3.9`.
- Promoted the conservative lead-2 variant as N39: only X544-route timing
  changes from one turn to two; the Moon route and shop selector are unchanged.
  The evaluated candidate is 312,190 bytes / `e56a070f...`; the promoted
  `main.py` is text-identical after newline normalization, 312,188 bytes and
  SHA-256 `6073f67f394f7f6161dd60c8406106b130e7ca702974a4accbe1e8e163b8fa1d`.

## E059 — third chronological S08 replay holdout

- Downloaded the next twelve completed public S08 episodes after the two
  previously frozen ten-episode batches. Exact S08 reproduced every recorded
  final bank, so counterfactual fidelity passed again.
- S08 won `11/12` with average margin `+1670.33`; N31 and N36 each won
  `11/12` at `+2018.25`; N39 won `11/12` at `+2021.17`. There were no outcome
  improvements or regressions inside this batch; the common loss was Johnson
  Chishimba at seed `1934914969` from seat 0.
- Across all 32 disjoint chronological S08 episodes, S08 won `28/32`, N36
  won `29/32`, and N39 won `30/32`. This third batch independently preserves
  N39's earlier gains and gives no reason to roll back the promoted lead-2
  artifact.

## E060 — N40 Johnson public-response diagnostics / rejected

- The losing opening is publicly distinctive by step 12: six active hands,
  money near 285, four pastures, eight plant tiles, seven wheat, one
  strawberry, one cow and three sheep. The fingerprint is observable and uses
  no private or replay-only field, but it arrives after the simultaneous
  step-0 opening.
- Full-policy donors proved that the loss is not unavoidable: C95 scored
  `+53201`, V36 `+29029`, Soil `+27728`, and scored V16 `+23386`. They do not
  transfer globally: on the complete twelve-episode batch they won only
  `7/12`, `8/12`, `6/12`, and `6/12`, versus N39's `11/12`.
- Simple policy switching was incompatible. Only C95 through step 24 and then
  N39 flipped Johnson (`+7452`); applied to all twelve episodes that hybrid
  won `1/12`, with eleven regressions. N39-to-donor switches never flipped the
  loss. A donor prefix is therefore not a safe online counter-policy.
- Public farm traces showed a coupled difference: N39 finished with six cows,
  eight sheep and 19 DIG actions, versus nine/four/47 for C95 and eight/four/42
  for V36. Four opponent-conditioned sheep-to-cow windows were then tested.
  Even the smallest two-animal change worsened margin by `-11590`; wider
  windows lost `-20934` to `-24383`. The production mix cannot be transplanted
  without its feed, placement, care and cleaning plan.
- X-route sale leads 1--24 and wool-only timing also failed to flip Johnson;
  the best observed global lead improved the S08 margin by only 326 coins.
  Stacking a second generated market overlay exposed recursive global-name
  capture and produced an invalid 3000-bank candidate, which the exact replay
  gate rejected before any leaderboard use.
- Decision: no N40 promotion. Keep N39 and require a compatible task-graph
  continuation or a genuinely common step-0 opening before adding another
  opponent-classified branch.
