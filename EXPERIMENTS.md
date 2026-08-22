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

## E061 — N41 common-opening and reactive-cleaner diagnostics / rejected

- Preserving N39's shared step-0 action did not make a donor continuation
  compatible. Switching to C95 at step 1 and back to N39 at steps 12, 24 or
  48 scored `-130678`, `-72670` and `-88936` on the Johnson replay, versus
  N39's `-11745`.
- A public-fingerprint weed task was then tested only after Johnson was
  identified at step 12. Idle-worker routing never triggered. Allowing the
  nearest empty worker to leave an existing movement task produced 26--39
  extra DIG actions but worsened the best replay to `-22497`.
- Hiring and routing one extra nominal cleaner also failed. Thresholds 3, 5
  and 8 weeds scored `-34574`, `-24316` and `-19657`; the least aggressive
  form still lost 7,912 more coins than N39.
- Decision: reject N41 without a broad holdout or leaderboard slot. Weed
  removal has an opportunity cost coupled to hiring, travel and production;
  nearest-task overrides are not a compatible reactive planner. Keep N39.

## E062 — fourth chronological S08 replay holdout

- Downloaded fourteen later S08 public episodes, disjoint from the prior 32.
  Exact S08 again reproduced every recorded final bank before candidates were
  accepted. S08 and N39 each won `8/14`; N31 also won `8/14`, while N36 won
  `7/14`.
- N39 improved one S08 loss (digitalChaos, `-469` to `+169`) and regressed one
  narrow S08 win (Audric LOKO, `+151` to `-2560`). Its average margin was
  `+1065.93`, versus S08's `+370.79`, a `+695.14` mean delta.
- Across all 46 disjoint chronological S08 episodes, S08/N36/N39 won `36/46`,
  `36/46`, and `38/46`; average margins were `+3267.09`, `+3813.41`, and
  `+3907.70`. N39 remains the strongest aggregate candidate, but the shop
  selector now has one documented live-meta regression.

## E063 — N42 one-turn YARN response probe / rejected

- The kevin park improvement and Audric regression are observationally
  identical through step 72: both opponents expose the same farm and first
  `YARN_STORE`. Under a common Moon action at step 72, their step-73 public
  responses differ: kevin has five active hands and Audric two.
- N42 used Moon's step-72 action as a probe, then selected X544 for at least
  four opponent hands and Moon otherwise. The signal classified the two tapes
  as intended and retained Audric at `+161`, but the late X continuation was
  state-incompatible and worsened kevin from N39's `+6111` to `-9945`.
- Decision: reject N42. The distinguishing information arrives after the
  first incompatible action. Randomizing that action only trades the two
  outcomes; it does not improve their expected win rate. Keep deterministic
  N39 and retain N31 as policy diversity.

## E064 — current-meta donor matrix and portfolio correction

- On the six S08 losses in the newest fourteen-episode block, four independent
  whole-policy donors all won `6/6`: C95, V36, Soil and V16. On the other eight
  episodes, they retained `6/8`, `7/8`, `6/8` and `4/8`; N39 retained `7/8`.
  The complete latest-block outcomes were therefore V36 `13/14`, C95 and Soil
  `12/14`, V16 `10/14`, and N39 `8/14`.
- This is a temporal meta shift, not universal V36 dominance. Exact V36 won
  only `15/20` on the first two S08 blocks and `8/12` on the third, versus
  N39's `19/20` and `11/12`. Across all 46 episodes V36 and S08 both finish
  `36/46`, while N39 remains `38/46`.
- Rechecking V36's previously tested market quantity 20 reproduced the exact
  S03 hash `8c27bc4e...`. It improved V36's only newest loss from `-875` to
  `-597` but did not flip it, so no N43 variant was promoted.
- Decision: after the quota reset, use N39 first and exact V36 second. They
  are distinct from step 0 and cover different current-meta modes; N31 becomes
  the held validation/repair reserve. Do not blend them with per-turn epsilon
  noise or spend a slot on V36 q20.

## E065 — N39/V36 complement and V36 quantity sweep

- Across all 46 chronological replays, N39-only wins account for nine episodes,
  V36-only wins for seven, and both win 29. Their two-policy outcome oracle is
  `45/46`; the only shared loss is Rikito Kanda. This quantifies genuine policy
  complement rather than merely different average margins.
- V36 market quantities 15, 20, 25, 30, 40 and 60 were tested on its only
  newest loss. Quantity 40 was best, monotonically improving the relevant
  range from exact V36's `-875` to `-423`, but no value flipped the outcome;
  quantity 60 regressed to `-1309`.
- Decision: reject N44 quantity tuning without a broad gate or LB slot. The
  45/46 oracle cannot be implemented inside one agent because N39 and V36
  diverge on the simultaneous step-0 action. Preserve the two deterministic
  submissions as the exploration/exploitation portfolio.

## E066 — shared Rikito loss reserve-donor control

- Tested the only N39/V36 shared loss against full C95, Soil, V16 and V25.
  Every donor also lost: margins were `-10725`, `-14837`, `-14482` and
  `-7770`, versus V36 `-5180`, S08 `-478` and N39 `-371`.
- Decision: no third donor earns the reserve slot. N39 is already the closest
  whole policy on this tape, and the earlier N38 timing diagnostic's best
  `-51` did not flip it. Keep N31/repair capacity in reserve rather than
  chasing the final oracle miss.

## E067 — official ladder/final-evaluation audit

- The official Evaluation page confirms a five-submission daily limit, but
  only the latest two valid submissions are tracked and used for final
  evaluation. The public leaderboard displays the better-scoring one of those
  two; duplicating a policy does not create an ensemble or average its rating.
- Each episode changes a policy's skill rating from only win/loss/tie and the
  opponent rating. Final-bank margin is deliberately ignored. Newer agents
  receive episodes more frequently, and the displayed rating can therefore
  rise or fall as evidence accumulates.
- There is no private leaderboard. After the September 30 deadline, new
  submissions are locked and games continue until approximately October 15
  or rating convergence, followed by a Bradley-Terry fit over the episodes.
- Four submissions already counted in the current UTC day (S05, S07, S06r
  and S08), so the fifth slot remains unused for validation failure recovery.
  After the UTC reset, submit N39 and then exact V36: this makes the tested
  complementary pair, rather than copies, the two simultaneously active
  final-evaluation candidates. N31 remains a local artifact/repair reserve.

## E068 — fifth chronological S08 replay holdout

- Downloaded the ten public S08 episodes completed after the E062 cutoff.
  Exact S08 reproduced all recorded final banks before candidate results were
  accepted, so this is another fidelity-gated chronological holdout.
- Outcomes were exact V36 `9/10`, N39 `5/10`, N31 `4/10`, and S08 `3/10`.
  V36 improved seven S08 outcomes and regressed one; N39 improved two with no
  regression. The newest 24-episode regime is now V36 `22/24` versus N39
  `13/24`, strengthening the evidence for the current-meta V36 slot.
- The policies remain genuinely complementary. V36 uniquely won five of the
  new episodes; N39 uniquely won V36's sole loss (clarkzhang1031, episode
  `96284690`). Their two-policy oracle was `10/10` on this block and `55/56`
  across all five chronological S08 blocks.
- Decision: keep the post-reset order N39 then exact V36, so the stronger
  current-meta policy is also the newest submission and receives the most
  frequent early matchmaking. Do not replace N39 with a second V36 copy: its
  unique clarkzhang1031 win is direct evidence for portfolio diversity.

## E069 — V36 clarkzhang quantity retune / rejected

- V36's sole E068 loss was narrow (`-657`), so the existing
  `market_quantity` variants 15, 20, 25, 30, 40 and 60 were replayed on exact
  episode `96284690` before considering a broader gate.
- Every quantity still lost. Quantity 40 was best at `-410`, followed by 60
  at `-424`; the remaining margins ranged from `-533` to `-605`.
- Decision: reject the retune without spending a full holdout or leaderboard
  slot. Exact V36 keeps its `9/10` result, while N39 already wins this episode
  by `+9540`; the right mechanism here is the two-policy portfolio.

## E070 — current-meta V36 terminal-overlay transfer / rejected

- Audited the original scored-donor requirements against executable evidence.
  E036 proves the exact V16-RC5/v25 version IDs, hashes, direct S05 panels and
  both-seat eight-family shootout. E015/E021/E022/E024--E033 separately prove
  the weed, terminal, FERTILIZER and opponent-family-selector mechanisms on
  the selected S05 lineage. The remaining useful question was transfer to the
  now current-meta exact V36 policy.
- H21 is the only existing overlay that can wrap V36 without depending on
  X544/Moon private globals or a missing fixed action schedule. Generated
  V36+H21 used the established step-689, actors 1/2, pressure-90 rule and was
  screened against exact V36 on eight fresh seeds from both seats.
- The candidate scored paired outcome `0.375` with bootstrap 95% interval
  `[0.1875, 0.5]` and average margin `-23.875`. On every triggered farm it
  spent twelve route moves to recover/sell only six WHEAT; paired triggered
  deltas were negative on all three affected seeds (`-146`, `-104`, `-132`).
- Decision: reject N47 before a broad pool or leaderboard slot. H21 is a
  route-specific task-graph improvement, not a portable terminal primitive.
  A V36 terminal repair would need actor opportunity-cost scoring and an
  inventory-value-aware route planner, not fixed worker indexes.

## E071 — trace-guided V36 terminal worker selection / rejected

- Traced exact V36 at step 689 on the three E070 trigger seeds.  The terminal
  state was structurally stable: actors 1/2 were five and seven moves from
  shed access with only six and four WHEAT, while actor 9 was one move away
  carrying nine items (one WHEAT, two FERTILIZER and six MILK).  This explains
  the fixed-route loss as opportunity cost rather than a bad pressure trigger.
- Fixed actors 8/9 were neutral (`0.500`, `-7.6` mean margin), while actor 9
  alone passed the original 16-game mirror (`0.625`, `+12.6`).  On a matched
  32-game eight-family control, however, N49 changed no outcome and triggered
  only four times: its mean margin delta versus exact V36 was `+2.4`, split
  between `-7` against Choose and `+46` against C95.
- Exact-replay evaluation on the ten newest S08 episodes preserved V36's
  `9/10` but improved only one triggered margin by 11 coins (`+1.1` mean).
  N50 replaced the fixed index with a conservative planner that selects at
  most one loaded hand within one move of shed access.  It reproduced N49 on
  the original mirror and scored `0.531` with `+2.8` mean margin on sixteen
  fresh paired seeds; every one of its ten combined trigger cases still chose
  actor 9 because V36's late task graph is effectively deterministic.
- Decision: keep exact V36 for the second post-reset submission.  N49/N50 are
  tiny positive diagnostics but do not clear a submission-risk threshold:
  they produce no outcome gain on 42 broad/replay games and the dynamic
  selector has not encountered a genuinely different useful worker.  Retain
  `make_terminal_nearby_variant.py` as the safer reactive-planner scaffold.

## E072 — sixth chronological S08 holdout and donor refresh

- Downloaded the five public S08 episodes completed after E068 (`96286975` to
  `96296132`).  Exact S08 reproduced all recorded final banks before accepting
  any candidate result.  S08 won `2/5`; N39 won `5/5`, N31 `4/5`, and exact
  V36 `3/5`.  N39 flipped all three S08 losses with no regression.
- The N50 nearby-worker terminal planner preserved V36's `3/5` and improved
  only the kumanomi loss by 35 coins (`+7` mean), again without an outcome
  flip.  Its trigger selected actor 9 and liquidated the same nine items, so
  the new live block does not justify the terminal overlay.
- Re-evaluated exact V36, Soil and C95 on the combined latest fifteen episodes.
  V36 won `12/15` with `+4043.5` average margin, versus Soil `9/15` and
  `-1410.7`, C95 `8/15` and `+1838.1`, and S08 `5/15`.  N39 is `10/15` on the
  same span.  Thus V36 remains the strongest current-meta whole-policy donor
  despite N39's perfect newest-five rebound.
- Across all 61 disjoint chronological S08 episodes, N39 and V36 are now both
  `48/61`, but their time profiles differ sharply.  Their outcome oracle wins
  all five new episodes and rises from `55/56` to `60/61` overall.
- Decision: keep the post-reset pair and order unchanged: submit N39 first,
  then exact V36.  The newest-five shift strengthens the need for diversity;
  it does not support replacing V36 with the more correlated N31, Soil or C95.

## E073 — compatible BAKERY whole-policy shadow selector / promoted

- Extended the only N39/V36 shared Rikito loss donor control with X544, Moon,
  Choose and Read.  All four full policies also lost (`-627`, `-1104`,
  `-1040`, and `-1354`), so another incompatible whole-policy submission was
  not supported.
- A residual subset search inside the existing N38 market overlay found that
  advancing only FERTILIZER and WOOL with lead 11 flipped Rikito from N39's
  `-371` to `+127`.  Used globally as N52 it won the older latest-ten block
  `10/10`, but only `7/15` on the current latest-fifteen and regressed one N39
  outcome.  N52 was therefore rejected as a global replacement.
- N39 and N52 emit the same actions through the first shop reveal at step 72
  (and through step 239 on Rikito).  N53 embeds both policies, gives each an
  isolated RNG stream, shadow-runs both from step zero, verifies the action
  prefix, and selects N52 only when the first shop is `BAKERY`; an incompatible
  prefix falls back to N39.
- All eight BAKERY episodes in the 61-game chronological S08 corpus passed
  exact baseline reproduction.  N53 won `8/8`, versus N39 `7/8` and S08
  `5/8`, flipping Rikito with no outcome regression.  All eight reported a
  compatible prefix and zero mismatches.  On thirteen non-BAKERY episodes in
  the newest-fifteen, N53 exactly reproduced N39.  A separate 32-game,
  eight-family two-seat panel contained no BAKERY seeds and reproduced every
  N39 outcome and final margin exactly (`31/32` wins).
- The final generated file is 511,698 bytes, SHA-256 `10868816...`, passed
  `py_compile`, all 69 unit tests, exact replay loading, and stayed below
  290 ms maximum local action latency.  Its retrospective corpus result is
  `49/61`, one above N39; the N53/V36 outcome oracle is `61/61`.
- Decision: promote N53 to the first post-reset slot instead of N39, followed
  by exact V36.  This is deterministic contextual exploitation, not per-turn
  epsilon noise: the selector changes policy only at a verified compatible
  checkpoint and otherwise remains byte-for-byte N39 in game outcomes.

## E074 — fresh BAKERY transfer gate / N53 promotion reversed

- A pass-agent seed screen was intentionally not accepted: three seeds that
  revealed `BAKERY` under pass/pass produced other shops with real agents,
  because farm evolution changes environment RNG consumption before step 72.
  Fresh context discovery must therefore run the actual N39/opponent pair.
- An eight-seed, four-family N39 screen produced no BAKERY cases.  A second
  sixteen-seed screen against V36 and X544 found three independent BAKERY
  matchup-seeds.  Because N39 and N53 are identical before the reveal, each
  could then be repeated as a controlled two-seat A/B.
- Against V36 seed `20266047`, N53 preserved both wins but changed the margin
  from `+3614` to `+3309` (`-305` per seat).  Against X544 seed `20266047`, it
  preserved both wins and improved `+2392` to `+2558` (`+166`).  Against X544
  seed `20266040`, however, it regressed both seats from N39's `+4148` win to
  a `-97` loss (`-4245` per seat).
- Every case selected the override with a compatible prefix and zero mismatch,
  so this is not a state-grafting bug.  `BAKERY` alone is insufficient context:
  the FERTILIZER+WOOL timing response also depends on the opponent task graph
  and later shared-market trajectory.
- Decision: reject N53 for leaderboard submission despite its historical 8/8
  BAKERY result.  Restore the post-reset plan to deterministic N39 followed by
  exact V36, retain one repair slot, and keep the generic shadow-selector tool
  for future policies with a broader context gate.

## E075 — seventh chronological S08 holdout / final pre-submit check

- Downloaded the two S08 episodes completed after E072 (`96314456` and
  `96328165`).  Exact S08 reproduced both recorded final banks before candidate
  results were accepted.
- S08, N39 and exact V36 all won `2/2`.  N39 margins were `+3110` and `+2152`
  (`+2631` average); V36 margins were `+21806` and `+6777` (`+14291.5`
  average), versus S08's `+1503` average.  Margin remains diagnostic only.
- Across all 63 chronological S08 episodes, N39 and V36 now each win `50/63`;
  their outcome union rises from `60/61` to `62/63`.
- Decision: no last-minute policy change.  Submit N39 first and exact V36
  second after the UTC quota reset, then preserve at least one repair slot.

## E076 — post-reset N39/V36 portfolio deployment

- At `2026-08-22 00:01 UTC`, submitted N39 SHA-256 `6073f67f...` as S09.
  Kaggle ref `55679129` completed validation episode `96366918` successfully.
- After N39 reached `COMPLETE`, submitted exact V36 SHA-256 `47ebf290...` as
  S10 at `00:07 UTC`.  Kaggle ref `55679350` completed validation episode
  `96369219` successfully.
- The intended complementary policies are now the latest two valid
  submissions, ordered N39 then V36.  Both display the initial `600.0` rating
  before public matchmaking supplies meaningful evidence.  Three of five
  UTC-day slots remain unused.
- Decision: do not submit copies or react to the initial rating.  Preserve the
  remaining slots for validated repairs, monitor public episodes separately,
  and compare ratings only after sufficient game accumulation.

## E077 — public-context BAKERY full-feedback gate / N53 final reject

- Extended `arena.py` with public-only selector checkpoints containing both
  farm signatures, shops and shared market state; own private inventory is
  excluded and covered by a unit test.  The complete suite now passes 70 tests.
- Ran N39 over twelve fresh seeds, four public families and both seats (96
  matches).  This produced 24 BAKERY matches across V36, Soil and C95.  Replayed
  the same 72 relevant family/seed/seat matches with N53; every non-BAKERY
  match reproduced N39 exactly.
- On the 24 BAKERY matches N53 produced zero outcome improvements, four outcome
  regressions and `-328.4` average margin delta.  Soil seed `20266073` regressed
  one seat from `+1016` to `-119`; Soil seed `20266083` regressed both seats
  from `+927/+1703` to `-1008/-256` after the override (deltas `-1935/-1959`).  V36 seed
  `20266073` added another narrow win-to-loss regression.
- Shadow comparison shows the first actual divergence is step 216 for the
  V36/Soil opening and step 240 for X544.  Waiting for two or three shop reveals
  still gives no positive fresh outcome class: later shop sequences correlate
  with seed but do not predict the future stochastic market/task trajectory.
- Decision: N53 is conclusively rejected, not merely held.  Do not fit a tree
  to its historical 8/8 result.  Reuse the public-context and shadow machinery
  only for a candidate pair that demonstrates multiple fresh outcome gains and
  zero regressions before model fitting.

## E078 — first S09/S10 public episodes and cross-replay check

- Downloaded the first four public episodes for both new submissions.  N39 and
  exact V36 each won their recorded `4/4`; all eight submitted-policy baselines
  reproduced the recorded final banks exactly.
- Counterfactual cross-evaluation also won every episode: V36 won all four N39
  tapes, while N39 won all four V36 tapes.  Average margins were N39 `+108749.5`
  versus V36 `+101866.0` on S09's opponents, and N39 `+75454.5` versus V36
  `+37796.25` on S10's opponents.  These early opponents are therefore too weak
  to distinguish policy quality by outcomes.
- Ratings after the first few games were N39 `970.3` and V36 `1092.0`, still
  far below convergence and unsuitable for promotion/rejection decisions.
- Decision: retain both active submissions and all three remaining daily
  slots.  Wait for stronger opponents or an actual loss before building a
  best-response residual from live data.

## E079 — bounded X544-route timing sweep / N39 x2 retained

- Reused the same twelve fresh seeds, four public families and both seats for
  a controlled sweep of the X544-route market-sale lead.  N31 and the
  shop-aware N36 provide the `x1` arms; N39 is `x2`; newly generated variants
  provide `x3` and `x4`.  Moon-route timing and all other policy code remain
  fixed.
- Relative to N39, both `x1` arms produced zero outcome improvements and six
  regressions over 96 matches, with `-351.9` average margin delta.  Their
  largest damage was against Soil, where outcome rate fell from `22/24` to
  `17/24`.
- `x3` and `x4` preserved all 96 outcomes, but improved none.  They changed
  margins on 74/96 matches and reduced average margin by `-81.9` and `-106.1`
  respectively.  Every family had a negative average delta; no public-context
  branch supplied a positive class for a conditional selector.
- Decision: retain deterministic `x2` in N39.  Reject `x1`, `x3` and `x4` for
  leaderboard use.  This is a local discrete optimum on the controlled panel,
  not evidence that random per-action exploration is safe.

## E080 — stronger live matchmaking / no-loss evidence still non-discriminative

- Downloaded four further completed public episodes for each of S09 and S10.
  N39 is now `10/10` on the locally archived S09 episodes and exact V36 is
  `9/9` on S10.  All new games were wins; two additional S09 games were still
  in progress at capture time.
- Matchmaking is visibly strengthening.  N39's first four archived margins
  averaged `+108749.5`, while its newest four averaged only `+11113.5`.
  V36's first four averaged `+37796.25`, while its newest four averaged
  `+12545.0`.  The latest single margins were `+11665` for N39 and `+9788` for
  V36.
- The live trajectory widgets briefly reached about `1756` for N39 and `1688`
  for V36 while cached submission rows displayed lower values.  Both ratings
  are still moving rapidly, and neither has yet reached the older S08/S05
  region around `2200+`.
- Decision: keep N39 and V36 as the two active policies and preserve all three
  remaining UTC-day slots.  Do not submit copies or infer superiority from the
  current ordering; wait for a completed loss, stable score, or the 24-hour
  gate before spending the next two research slots.

## E081 — live cross-policy complement and common-opening graft rejection

- Exact-replayed nine S09 episodes completed after the original four-game
  cross-check.  N39 reproduced `9/9`; V36 won `8/9`.  On episode `96400727`
  against Cultuurstelsel, N39's `+26509` win became a V36 `-6275` loss.
- Exact-replayed the five corresponding new S10 episodes.  V36 reproduced
  `5/5`; N39 won `4/5`.  On episode `96389348` against LittleScottyy, V36's
  `+10954` win became an N39 `-1434` loss.  Across the fourteen fresh tapes,
  each policy alone is `13/14`, while their outcome oracle is `14/14`.
- A two-policy shadow trace disproves a delayed classifier over the existing
  routes: N39 and V36 first disagree at step zero and disagree on `714/719` or
  `718/719` calls on the two decisive tapes.  There is no observation of the
  opponent before the route commitment.
- Tested both required graft directions at steps `1`, `24` and `72`.  Starting
  V36 then switching to N39 lost the Cultuurstelsel tape at all checkpoints
  (margins `-29006`, `-76253`, `-124493`).  Starting N39 then switching to V36
  also lost the LittleScottyy tape at all checkpoints (margins `-167692`,
  `-88458`, `-53179`).
- Decision: keep both active submissions; they are genuinely complementary.
  Reject a post-hoc N39/V36 opponent selector and any one-action graft.  A
  future common opening must be synthesized and jointly optimized from step
  zero with branch compatibility as a hard constraint, not copied from either
  incumbent.

## E082 — first live losses and residual third-policy gate

- S09/N39 reached a live trajectory near `2291` before its first archived
  loss, episode `96407577` against weichy7 (`-3291`).  Exact donor replay
  showed that active V36 already covers it at `+8071`; Soil and C95 also win,
  while S05, N29, N31, X544 and Moon lose.  This is direct live evidence that
  the two deployed policies remain complementary rather than redundant.
- S10/V36 accumulated fifteen wins, one draw and two losses over eighteen
  archived episodes.  N39 flips the earlier Efnutrrionpy loss but still loses
  the new Kevin Park episode (`-6534` versus V36's `-25986`).  C95 and X544
  are the only tested donors to flip Kevin Park, at `+27338` and `+9609`.
- On all eighteen exact S10 tapes, V36 scores `15.5/18`, N39 `16/18`, C95
  `12/18` and X544 `15/18`.  Relative to V36, C95 has one improvement and five
  regressions; X544 has three improvements and three regressions.  The
  V36+N39 outcome oracle is `17/18`; adding either C95 or X544 raises the
  retrospective oracle to `18/18`, but neither donor is safe as a replacement.
- A shadow-compatible V36-to-C95 switch still flips Kevin Park at steps `1`,
  `12` and `24` (`+12239`, `+27330`, `+27330`), but step `72` is too late.
  X544 switches at all four checkpoints lose.  The apparent C95 adaptation
  window therefore exists mechanically, but it has no valid opponent label:
  Kevin Park and seven other S10 opponents have an identical complete public
  opponent-farm trace through step 72, including cases where C95 regresses.
- The old N34 file was also re-audited after an ambiguous filename suggested a
  V36 animal variant.  It is an N31-based COW-to-SHEEP overlay.  Against the
  fifteen original S10 tapes it preserves every N31 outcome and activates only
  twice, improving margins by `+2263` and `+9163`; it does not explain V36's
  loss or justify a slot.
- Decision: retain N39 and V36 and keep all three remaining UTC-day slots.
  Record C95 as a real residual third-policy class, but reject an early
  opponent classifier because the relevant opponents are observationally
  aliased throughout the usable switch window.  Seek repeated public
  market-context evidence or a jointly optimized common policy before
  promoting a third submission.

## E083 — Orbit Wars transfer and factorized macro-action audit

- Reviewed the primary 2026 Orbit Wars write-ups.  First place used a 200M
  transformer and 15B PPO self-play steps; second used a 4.3M model and 10B
  steps.  Both rewrote the simulator and changed the action representation.
  Sixth/seventh combined RL with forward features, analytic planning or
  inference search; the 19th-place BC+PPO pipeline reported a GPU simulator
  around three orders of magnitude faster than the reference CPU engine.
- Benchmarked the current official Kaggriculture Python environment with eight
  `pass/pass` games and four workers.  It processed 5,760 transitions in
  12.489 seconds, about 461 transitions/s including startup overhead.  Even at
  that optimistic no-policy rate, 10B steps would take roughly 251 days.
- Added `rl/analyze_macro_vocabulary.py` and three unit tests.  Across both N24
  imitation splits, the 8,376 non-noop rows contain 258 flat task+market
  labels.  Top-8/top-32 joint labels cover only `40.3%/69.4%`, so a flat macro
  classifier remains too diffuse.
- Factorized coverage is much stronger: top-16 task families cover `83.7%`
  and top-8 market operations cover `96.5%`.  This supports separate
  task/market/route/quantity heads beneath a rule-based legality and
  conservation layer, matching the strongest attainable Orbit Wars pattern.
- Decision: do not launch raw-action PPO in the official engine.  Gate serious
  RL on a parity-tested native/vectorized simulator, and next build a
  factorized macro candidate ranker with exact forward ETA/cashflow features.
  Continue selecting candidates by the existing historical/recent opponent
  league, not imitation loss or one live rating.

## E084 — learned factorized macro shortlist / analysis-only pass

- Added `rl/evaluate_factorized_macro_shortlist.py` with three focused unit
  tests.  It reconstructs the existing disjoint-season N24 task and market
  residuals, excludes `__OTHER__` from executable candidates, measures exact
  pair recall for several top-k products and filters combinations through the
  train-season pair vocabulary.
- On S05's 1,388 non-noop holdout turns, task top-3 × market top-3 covers
  `52.95%` of exact macro pairs with `6.51` candidates on average; top-5 ×
  top-3 covers `66.71%` with `10.46`; top-8 × market top-5 reaches `80.12%`
  with `21.57`.
- Transfer is much weaker.  The widest tested shortlist covers `60.53%` for
  V16 and `30.23%` for v25.  All raw holdout pairs occur in their respective
  train seasons, so pair filtering reduces shortlist size but leaves recall
  unchanged; the limiting factor is model ranking, not unseen vocabulary.
- The complete suite now passes `76/76`.  Decision: accept N56 only as an
  analysis/candidate-generation primitive.  Reject top-1 or epsilon-driven
  live control from the current linear heads.  N54 forward ETA, feasibility,
  cashflow and deadline features are the next promotion gate.

## E085 — N54 forward geometry/cashflow feature ablation

- Added an inference-visible forward layer in two parts.  The replay builder
  now records 32 position/object-clock features: static lower-bound worker ETA,
  service/harvest reachability before end of day, ready yield/value, critical
  service streaks, production/decay clocks and carried-inventory return ETA.
  `rl/augment_forward_features.py` adds 37 clock, feasibility, storage,
  hire/land and 6/12/24-turn known-demand/liquidation features.
- The copied default market formula reproduced every observed price for all
  nine products on 25,884 rows across the old and new train/holdout corpora:
  zero parity mismatches.  Projections crossing a future random shop unlock
  are explicitly flagged incomplete rather than presented as exact.
- On the old S05 disjoint season, adding the reconstructable 37 features
  improved decision-turn joint top-3×3 from `52.95%` to `58.72%` and top-8×5
  from `80.12%` to `82.85%`.  V16/v25 also improved at the wide shortlist.
- Collected a larger current-meta corpus on four fresh seeds: N39, exact V16
  and exact v25 on both seats against current N39, 8,628 rows per split.  V16
  and v25 lost all eight direct games each, independently reconfirming that
  their historical notebook scores do not make them a current base.
- An audit caught that the local replay object left `obs.step` stale at zero
  for seat 1 even while the shared day/hour advanced.  The collector and
  projector now derive the seat-stable clock as `day*24+hour`; regenerated
  train and holdout rows contain all 719 steps (`0..718`) for both seats.
- On 2,776 non-noop N39 holdout turns, the best broad-shortlist hybrid uses all
  forward features for the task head but geometry/object clocks only for the
  market head.  Joint top-3×3 rose `46.65% → 61.46%`, and top-8×5
  `74.17% → 80.66%`; full-forward top-1 rose `17.36% → 27.88%`.  Full forward
  heads raised V16 top-3×3 `33.01% → 45.22%` and v25 `40.26% → 53.20%`.
- Added process-parallel `--jobs` dataset collection and repeatable
  `--exclude-prefix` feature ablations; the full suite passes `84/84`.
  Decision: N54 passes as an offline
  ranking feature layer, but no learned action is deployed.  Cashflow features
  must remain head-specific; the next gate is a legal candidate generator plus
  official-engine outcome, latency and worst-family testing.

## E086 — N57 exact known-demand gate for bounded scheduled sales

- Extended `tools/make_market_timing_variant.py` with the official nine-product
  price curve, exact sequential-sale revenue and visible-shop demand projection.
  A generated overlay can now advance an already scheduled sale only when its
  current revenue clears a configurable fraction of the known-demand future
  revenue. Horizons crossing an unobserved random shop unlock retain the
  previously validated fixed-lead behavior instead of pretending the forecast
  is complete.
- Screened ratios `1.00`, `0.98` and `0.95` against V36, C95, exact V16 and
  exact v25. Ratio `1.00` was the strongest threshold, so it and unmodified
  N39 were extended to four fresh seeds, both seats and all four families.
- Across the resulting 32 matched games both policies won `32/32`; no outcome
  changed. The gate added only `+67.47` to candidate bank per game and changed
  competitive margin by `-3.03` on average. Family margin deltas were V36
  `-2.75`, C95 `-17.25`, V16 `-113.75` and v25 `+121.63`.
- Telemetry confirms the gate was active, especially rejecting future MILK
  and some WOOL advances, so the null result is not an identity-test artifact.
  Decision: keep N57 as legal market-planning infrastructure, but reject it as
  a submission candidate because it changes no outcomes and has no robust
  worst-family gain. The full suite passes `87/87`. Preserve the N39/V36 live
  pair and submission reserve.

## E087 — N58 structured-policy shadow audit and bounded service overlay

- Screened the complete public structured economic policy as a possible
  reactive task-graph donor against N39, V36, C95, exact V16 and exact v25 on
  three fresh seeds and both seats.  It lost all six games in each of the first
  four families; against v25 its paired outcome rate was only `0.333`.  Average
  margins ranged from `-2,654.67` to `-35,699.33`, so the whole policy is not a
  viable current-meta base.
- Added `tools/make_shadow_policy_audit.py`, which runs a second policy from
  step zero with isolated RNG and copied observations, records compatible-state
  and base-PASS opportunities, and normally returns the unchanged base action.
  Optional interventions are restricted to an explicit operation allowlist,
  locally legal actions and actors that the base leaves idle; redundant
  same-tile operations are rejected.
- The outcome-neutral wrapper exactly reproduced N39 across 12 matched games
  (two seeds, both seats, N39/V36/C95): zero bank, margin or outcome mismatch
  and zero candidate errors.  The two policies nevertheless disagreed on the
  joint field+market action from step zero and matched on only roughly 3% of
  turns, confirming that a late whole-policy switch would be state-incompatible.
- A WATER/FEED-only service overlay was then tested in 16 matched games.  Ten
  broad-screen games contained no eligible intervention.  A targeted seed
  produced exactly one locally valid WATER in each of six games, but all six
  banks, margins and outcomes remained exactly unchanged.  Candidate p99 was
  below 39 ms in every run; there were no shadow-policy errors.
- Decision: reject N58 as a submission candidate.  Keep the shadow runner and
  legality gate as research infrastructure for candidate extraction and future
  planner/model audits.  Random action-level exploration remains unjustified;
  only counterfactual-tested, opportunity-cost-aware interventions should be
  eligible for live control.  The complete suite passes `92/92`.

## E088 — N59 single-fertilizer DROP shadow intervention

- Extended the N58 shadow-audit generator with item and total-quantity gates
  for DROP interventions.  The candidate may execute a structured-policy DROP
  only when N39 leaves that actor idle, the action is locally legal, the actor
  carries FERTILIZER only and the total dropped quantity is one.
- On eight train seeds against N39 mirror, N59 scored `0.8125` with average
  margin `+1.2`.  On the next eight untouched seeds it improved paired outcome
  from `0.50` to `0.75` with two wins and no regression; average margin rose by
  `+1.5`.
- On the ten exact top-five replay seeds/seats N59 preserved N39's `8/10`
  outcomes and changed average margin from `+12971.6` to `+12972.5`.  The
  intervention is intentionally tiny and does not reproduce a whole donor
  route.
- On the matched 48-game current-public panel, N59 preserved every N39
  outcome.  It changed only the 12 Moon games, adding exactly `+2` margin in
  each, and was identical against Soil, V39 and Barnyard.  The intervention is
  safe in this sample but does not flip an outcome or address a top residual.
- Decision: keep N59 as a narrow audited primitive, but reject it as the next
  live submission.  A deterministic two-coin diagnostic gain does not justify
  evicting either member of the active N39/V36 pair.

## E089 — top-20 public replay meta audit

- Collected two public player-games for every current top-20 submission plus
  two each for S09/N39 and S10/exact-V36: 44 requested targets, 35 unique
  replay files, zero missing.  Added reproducible collection, parsing and
  exact-seed opponent-tape tooling with focused tests for action alignment and
  donor reproduction.
- Seventy percent of top-20 policies did not buy the fourth quadrant in either
  sampled game.  Top-20 equal-weight means were 3.3 quadrants, 283 hires, 8.2
  cows, 6.9 sheep, 0.18 geese and 962 WATER actions.  The top-five means were
  3.1 quadrants, 296 hires, 8.0 cows, 7.7 sheep and 1052 WATER actions.
- In 25 decisive top20-vs-top20 games, same-replay winners averaged only +0.04
  quadrants but +0.84 cow purchases, +2.60 tomato seed buys and +86.8 WATER
  actions.  Policy-level score associations were strongest for tomato use,
  WATER and hires, while fourth-land use was effectively zero.
- Against exact opponent tapes on the ten original top-five seeds/seats, N39
  scored `8/10` versus the donors' `6/10`, improved competitive margin by
  `+11209.4` on average and nevertheless earned 4127 fewer coins.  This
  demonstrates why unrelated final-bank totals cannot rank policies.
- Decision: reject the fourth-field hypothesis and keep N39 as the base.  Mine
  bounded, state-compatible task opportunities rather than action-count or
  asset-count targets; prioritize the two Arman cases where N39 regressed.

## E090 — literal top-1 tape and current-public transfer controls

- Extracted the exact top-1 action tape from attached episode `96487653` and
  played it against N39 on six fresh seeds from both seats.  The tape lost all
  `12/12` games with average margin `-15541.7`, despite often producing high
  raw coin totals.  Replay actions are seed/shop/weed/state-specific and are
  not a transferable policy.
- Pulled current versions of Moon Counts Melons, Soil Remembers Rain, V39
  History Gate and Strong Barnyard Economist.  Across six fresh seeds and both
  seats, N39 scored `11/12`, `8/12`, `7/12` and `12/12` respectively, or
  `38/48` overall.
- Decision: use replays and notebooks as opponent panels and donors of bounded
  predicates/tasks, not wholesale replacements.  Do not submit a top-1 clone;
  preserve the live N39/V36 pair while the new submissions are still rapidly
  rating.

## E091 — top-three residual and MiMi opponent donor matrices

- Replayed the six exact top-three target cases with N39, V36, C95, exact V16,
  exact v25, Moon, Soil, V39, X544 and the current multi-route policy.  The two
  N39 regressions were both Arman cases, but they are not one route family.
  Against tetsuya, N39 scored `-8582` while V36 scored `+12203`; against MiMi,
  the original Arman tape won by `+8313`, N39 was the closest reusable policy
  at `-3811`, and every other known policy lost by between `-4271` and
  `-36474`.
- Reframed every available episode containing MiMi so that MiMi's exact tape
  remained the opponent.  Across three such seeds, N39 scored `1/3` with
  average margin `+4503.3`; Moon and the multi-route policy produced the same
  outcomes, while V36/C95/V16/v25/Soil/V39 each improved one outcome and
  regressed two.  No whole-policy donor transferred consistently.
- Extended the exact-replay evaluator with normalized target/opponent filters,
  arbitrary named-seat replacement and tests.  This permits counterfactuals
  against a policy wherever it appears in a public replay, rather than only
  when that policy was the requested leaderboard target.
- Decision: reject a MiMi-specific whole-route switch.  The Arman win is a
  state-specific trajectory, not evidence that its action tape or a known
  route generalizes to new MiMi seeds.

## E092 — current 24-replay N39/V36 full-feedback panel

- Downloaded the eight newest public games for each of S09/N39, S10/V36 and
  MiMi: 24 unique exact-seed cases and 743 MB of replay state.  N39 won `22/24`
  with average margin `+12258.8`; V36 won `18/24` at `+7833.7`; the recorded
  donors won `17/24`.  By source cohort N39 scored `7/8`, `7/8`, `8/8`, versus
  V36 `7/8`, `6/8`, `5/8` respectively.
- Their outcome oracle is `24/24`: V36 fixes both N39 losses, tetsuya
  (`-3984` to `+44449`) and Andrey Chankin (`-206` to `+7574`).  But V36 also
  loses six cases that N39 wins.  A global 95/5 start-of-game mixture therefore
  has expected score `21.8/24`, below deterministic N39's `22/24`.
- N39 and V36 diverge at step zero.  The legal public start state is otherwise
  identical across the panel: both farms have 3000 coins, one unlocked NW
  quadrant, no hands, crops or animals, fixed initial market and no shop.  The
  only available split is seat; choosing V36 on seat 0 and N39 on seat 1 scores
  only `20/24`.
- Decision: retain N39 as the deterministic base and V36 as portfolio
  diversity, but reject a combined public selector.  The `24/24` oracle is not
  implementable without future information or opponent identity leakage.

## E093 — V36 shadow-task extraction on the two N39 residuals

- Added replay episode filters and candidate telemetry to the exact-replay
  evaluator.  The shadow audit now keeps a separate bounded sample of valid
  late interventions instead of filling its sample buffer with early invalid
  actions.  The full 24-game outcome-neutral audit exactly reproduced N39.
- V36 and N39 matched their complete joint action on only `5/719` turns.  V36
  proposed 269–360 non-PASS actions for actors idle under N39, but only 6–9
  were locally valid and non-redundant per game.  The two N39 losses averaged
  8.0 such opportunities versus 8.3 in the 22 wins, so opportunity count does
  not identify the residual family.
- On the two losses, screened separate allowlisted HARVEST, CARE, WATER,
  COLLECT_FERTILIZER and DROP overlays.  CARE/WATER/COLLECT/DROP executed the
  eligible actions but changed neither loss.  HARVEST executed three and four
  actions; it left tetsuya at `-3984` and worsened Andrey from `-206` to
  `-910`.
- Decision: reject all five V36 task grafts and make no new submission.  The
  active ratings are still moving (`2541.0` N39, `2158.1` V36), today's two
  autonomous slots are already used, and the reserve remains intact.  The
  complete suite passes `102/102`.

## E094 — top-20 complement and expanded Arman residual class

- Completed exact counterfactuals for both N39 and V36 on all 40 target
  seeds/seats from the current top-20 replay panel.  N39 won `27/40` with
  average margin `+6397.5`; V36 won `29/40` at `+5881.1`; their outcome oracle
  won `39/40`.  They disagreed on 22 outcomes (`10` N39-only and `12`
  V36-only), so the complement is substantial rather than a marginal tie.
- Rank bands separated the routes better than seat but are unavailable at
  inference time: N39/V36 scored `8/10`/`6/10` on ranks 1--5 and
  `5/10`/`8/10` on ranks 16--20.  By legal seat, both won `15/21` from seat 0;
  from seat 1 N39/V36 won `12/19`/`14/19`.  Seat selection therefore cannot
  realize the oracle, and opponent rank/name must not enter a submitted agent.
- Downloaded the eight newest public Arman games and exactly reproduced every
  donor baseline.  N39 won `4/8` at average margin `+7203.8`, V36 won `3/8`
  at `-824.0`, and their oracle won `6/8`.  A new shared loss against Excluding
  was distinct from the earlier MiMi loss.  C95, scored V16 and Soil each
  flipped Excluding (`+5795`, `+7103`, `+6387`) but still lost MiMi; each won
  `4/8`, and adding any one raised the three-policy oracle only to `7/8`.
- Continuously shadow-ran C95 from step zero and swept N39-to-C95 switches at
  steps `1,12,24,48,72,120,240,360`.  None flipped Excluding; margins ranged
  from `-21037` to `-87831`.  The reverse C95-to-N39 common-opening sweep at
  steps `1,12,24,48,72` scored `0/8`, `0/8`, `2/8`, `0/8`, `0/8` and suffered
  very large negative margins.  No compatible branch point exists in the
  tested range despite both policies receiving every live observation.
- Decision: retain C95/V16/Soil as a genuine third residual-policy class but
  reject both a whole-policy base replacement and the N39/C95 hybrid.  The
  extra oracle coverage currently requires an independent deterministic
  portfolio slot; it cannot be implemented by a legal online selector.  Do
  not submit: today's two autonomous slots are already used, the active pair
  is still rating, and no new single agent passed the regression gate.

## E095 — scored-policy shootout and fixed-Moon temporal transfer

- Recovered and SHA-256 verified the exact scored V16 (`f029fa0c...`, public
  score `2913.3`) and v25 (`9bdfbafb...`, public score `3009.0`) sources, then
  replayed them with C95, Soil, X544, V39, Barnyard and Moon on all 40 current
  top-20 target seeds/seats.  No candidate beat V36's `29/40`: V39, V16, Soil,
  C95, Moon and v25 scored `27`, `26`, `26`, `25`, `26` and `21` wins.  Adding
  any one to N39/V36 left the three-policy outcome oracle at `39/40`; every
  policy still lost the shared Arman-versus-MiMi case.
- Removed the overlay confound by freezing the current N39 source to each
  route after its common opening.  Fixed X544 scored only `17/40`.  Fixed Moon
  scored `27/40` at average margin `+6156.6`, exactly preserving all N39
  outcomes on the top-20 panel, while N39's public selector scored `27/40` at
  `+6397.5`.  On the newer independent 24-game live-focus panel Fixed Moon
  improved N39 from `22/24` to `23/24` without an outcome regression, flipping
  episode `96458078` from `-3984` to `+2933`.
- The chronological 46-game S08 replay holdout rejected the apparent transfer.
  N39 won `38/46` at average margin `+3907.7`; Fixed Moon fell to `36/46` at
  `+3273.5`.  Relative to N39 it flipped one loss (Audric LOKO) but regressed
  three wins (Dariush Afshar, kevin park and One-For-All).  On the eight-game
  Arman panel it matched N39's `4/8` outcomes exactly and reduced margin in the
  two changed trajectories.
- Across the three independent panels Fixed Moon therefore scored `86/110`
  versus N39's `87/110`, with two outcome improvements and three regressions.
  Decision: reject a global Moon freeze and do not fit an opponent-name or
  replay-specific selector to five changed cases.  Preserve N39/V36, the
  reserve slot and today's already-used two autonomous submissions; retain the
  opening-response idea only as a future pre-registered public-state hypothesis.

## E096 — chronological public-state route-tree transfer / rejected

- Extended both exact-replay evaluators to retain the arena's inference-legal
  public-context checkpoints and shop events.  Added a standalone full-feedback
  contextual-bandit fitter that verifies X544/Moon contexts are identical at
  the step-72 branch, excludes identity/rank/replay/future/private-opponent
  fields, and limits the learned policy to one split with minimum leaf five.
- Generated complete fixed-route labels on a chronological S08 training block
  of 46 games, the independent current top-20 holdout of 40 target seats and
  the still-newer 24-game live-focus holdout.  Every donor baseline reproduced
  exactly and all `110/110` paired step-72 contexts matched.  X544/Moon/oracle
  outcomes were `26/36/40`, `17/27/27` and `15/23/23` respectively: both future
  panels contained zero X544-only wins.
- The frozen depth-one model learned the legal rule `candidate money <= 44 ->
  X544; otherwise Moon`.  It scored `38/46` on train and also `38/46` under
  leave-one-out, improving two Moon losses without a train regression.  On the
  unseen top-20 panel it fell to `26/40` versus Moon's `27/40`, changing the
  peikopon seat in episode `96487659` from `+457` to `-8071`.  On live-focus it
  tied Moon at `23/24`; five X544 choices added no outcome and had mixed margin.
- Across the three panels the learned selector and N39 both score `87/110`, but
  the selector merely exchanges one current top-20 win for N39's fresh loss.
  Decision: reject candidate generation and submission.  Public-state ML is
  viable infrastructure, but this label is temporally non-stationary; require a
  repeated X544-only gain in a later frozen block before retraining or adding a
  deeper tree.  Full suite passes `106/106`.

## E097 — N39/C95 synthesized common-prefix lattice / rejected

- Added a deterministic common-prefix generator that shadow-runs N39 and C95
  with isolated RNG from step zero, executes a third action before branching,
  and then fixes either continuation.  Screened seven component rules across
  steps `1,12,24,48,72`: per-actor consensus with PASS on disagreement, N39 or
  C95 field actions, market-order intersection, and both cross combinations of
  one policy's field with the other's market.  Both generated branches share
  the exact executed prefix by construction.
- The first residual screen evaluated `70` synthesized branches on the exact
  Arman-versus-Excluding episode.  Only two C95 continuations won: exact C95's
  effective step-0 action and the new `N39 field + C95 market` step-0 hybrid,
  both at `+5795`.  Every later prefix and every N39 continuation lost; the
  best non-winning N39 branch was still `-14488`.
- The hybrid pair was then run on all eight current Arman games.  Its C95
  branch exactly reproduced original C95 in every final bank and outcome,
  scoring `4/8`.  The N39 branch, from the identical hybrid opening, collapsed
  from N39's `4/8` to `0/8` with average margin `-37493.1`.  The opening is
  therefore only a trajectory-equivalent way to enter C95, not a state from
  which both task graphs can continue.
- Decision: reject N64's component-level common opening and do not spend a
  broad holdout or submission slot.  Shadow memory is functioning, but the
  incompatibility is a coupled farm/market/task-allocation contract established
  on the first action.  A real shared opening must be optimized as a third
  reactive task planner with both downstream values in its objective; mixing
  incumbent joint-action components is insufficient.  Full suite passes
  `110/110`.

## E098 — native midgame snapshot/fork search gate / throughput pass

- Added `fast_sim/branch_bench.cpp`, a reproducible competitive-trace benchmark
  for copying a complete midgame simulator, applying four distinct root-action
  variants, and rolling each branch forward for `6`, `12` or `24` turns.  The
  test uses semantic field-by-field state equality: raw `memcmp` was rejected
  after correctly exposing irrelevant C++ padding differences near the terminal
  prefix.
- The patched 1.32.7 simulator still reproduces all `13/13` official traces at
  every one of `719` transitions (`9,347` total).  `State` is `7,672` bytes,
  complete `Sim` is `7,728` bytes, and both are trivially copyable.  Snapshot
  forks at steps `72`, `360` and `648`, covering both candidate seats, matched
  independent linear replay on all `12/12` horizon checks.
- With cheap result evaluation, the worst measured optimistic capacity inside
  `600 ms` was `33,489` six-turn, `17,613` twelve-turn and `6,990` twenty-four-
  turn branches.  The midgame step-360 cases reached about `7,601–8,310`
  twenty-four-turn branches per 600 ms; early step 72 reached `15,255`.
- Decision: N68 passes the native snapshot/throughput gate for offline search,
  but not the online-agent gate.  These numbers exclude task-graph generation,
  value inference and, most importantly, reconstructing a legal belief over the
  hidden opponent private inventory and unknown future RNG seed.  Build and
  validate observation-to-belief initialization before implementing PUCT or
  spending a submission slot.  No candidate was submitted.

## E099 — top-20 hidden-state observability audit / particles required

- Added a leakage-explicit auditor and four synthetic tests.  It reads the
  opponent private payload from the other replay seat only as an offline audit
  label, verifies every duplicated public farm/market/town view, and never
  presents that label as a legal policy feature.  Evaluated `40` top-20 replays,
  both target seats and checkpoints `72/360/648`: `240` seat-checkpoint cases,
  with `0/120` shared-view mismatches.
- At step 72 the hidden opponent state was non-empty in `96.25%` of cases, with
  mean `8.49` units and gross marked value `$500`.  At step 360 it was non-empty
  in `100%`, averaging `64.89` units and `$3,980`; at step 648 it averaged
  `82.64` units and `$4,007`, with a `$19,858` maximum.  Opponent shed alone
  averaged `54.96` and `72.05` units at the two later checkpoints; hidden seeds
  averaged `9.93` and `10.59`.
- All three checkpoints are day boundaries, and hidden carried inventory was
  exactly zero in all `240/240` target-seat cases.  This is the main positive
  result: day-boundary search can omit opponent per-hand inventory and model
  only shed/seeds plus the unknown future random stream.  The source seed was
  present in offline replay metadata in `100%` of cases and in the legal target
  observation in `0%`.
- Decision: reject an empty or single neutral full-state initialization.  Keep
  N69 and narrow it to history-conditioned shed/seed particles at day-boundary
  search nodes, with sampled future RNG.  A full-state oracle remains only an
  upper bound.  No live candidate or submission was produced.

## E100 — grouped legal snapshot priors for hidden shed/seeds / partial pass

- Added a grouped-by-episode evaluator for `17` hidden shed/seed counts.  The
  label is still other-seat private replay state, but all `116` distance
  features come only from the target seat's legal current observation.  Names,
  replay IDs, source seed and opponent private values are explicitly forbidden;
  both viewpoints of a held-out episode are excluded from its neighbours.
- On `40` top-20 replays (`80` seat cases per checkpoint), checkpoint median
  crushed the blank prior: item L1 fell from `8.49/64.89/82.64` to
  `2.11/25.79/36.44` at steps `72/360/648`.  Public kNN's best point choices
  were k=5 at step 72 (`1.76`, +16.6%) and k=10 at 360 (`24.45`, +5.2%) and 648
  (`35.76`, +1.9%).  Gross-value error for k=10 improved from `$827` to `$760`
  at 360 and from `$1,327` to `$1,024` at 648.
- A fair 128-draw marginal particle baseline showed that ten public-nearest
  particles improved best-particle item L1 over ten random checkpoint particles
  at every checkpoint: `0.44 vs 1.34`, `13.93 vs 16.44`, and `21.68 vs 26.52`.
  Gross coverage improved at 72 (`$14.7 vs $37.8`) and 648 (`$402 vs $451`) but
  regressed at 360 (`$283 vs $249`).  Same-episode neighbour violations were
  `0` and hidden carried inventory remained zero throughout.
- Decision: retain checkpoint median and public kNN-10 as reproducible particle
  baselines, but do not call snapshot kNN a sufficient posterior or implement
  PUCT yet.  Its modest/mixed transfer, especially the step-360 value regression,
  requires inference-visible observation-history features before the macro-plan
  recall gate.  No submission was produced.

## E101 — legal observation-history particles / disjoint transfer pass

- Added cumulative and recent-72 history features computed solely from the
  target seat's observation stream: visible opponent plant/harvest, animal,
  fertilizer, land, hand and money changes plus shared market inventory/price
  deltas.  Tests prove invariance to replay actions, metadata/source seed and
  arbitrary changes in the other seat's private payload.  Complete EpisodeId
  grouping and the E100 snapshot-kNN10 baseline remain unchanged.
- On the 40-game top-20 grouped set, history improved point item/gross error at
  every checkpoint and best-particle item coverage at every checkpoint.  At
  step 360 it fixed the earlier value problem: particle gross error fell
  `$283 → $214` (+24.4%).  At step 648, however, particle gross error rose
  `$402 → $433` (-7.7%), so the internal pre-registered late gate failed despite
  better point (`35.76 → 34.08`) and particle item (`21.68 → 19.65`) errors.
- The fixed history-kNN10 was then transferred without refitting from all 40
  top-20 training replays to 23 disjoint live-focus replays (four overlapping
  EpisodeIds removed).  It improved all four registered metrics at both late
  checkpoints.  At 360: point item `19.79 → 18.42` (+6.9%), point gross
  `$834 → $774` (+7.1%), particle item `4.43 → 4.37`, particle gross
  `$101 → $82` (+19.0%).  At 648: `31.23 → 24.70` (+20.9%), `$1,031 → $954`
  (+7.5%), `10.00 → 8.83` (+11.7%), and `$125.00 → $124.78` (+0.17%).
- Decision: N71 passes the disjoint belief-transfer gate and history-kNN10 is
  now the best legal shed/seed particle proposal.  The tiny late gross edge and
  mixed internal CV forbid direct rollout integration or submission.  Next
  require full-state-oracle macro-plan top-3 recall and official-engine outcome;
  hidden-state reconstruction accuracy alone is not a strength metric.

## E102 — reactive particle-to-oracle macro-plan recall / reject

- Added `fast_sim/macro_plan_eval.cpp` and
  `rl/evaluate_macro_plan_recall.py`.  Nine fixed reactive task graphs cover
  maintenance, liquidation, four crop cycles and three animal routes.  Replay
  actions are used only to reconstruct the day-boundary root; after that both
  seats are reactive.  The candidate reads only its own farm/private state and
  shared market, while the opponent alternates maintenance/liquidation response
  graphs using its particle-private state.  Full state is an offline label;
  future randomness uses two shared synthetic seeds rather than the replay seed.
- The fixed E101 top20-to-live transfer was preserved: `40` training games and
  `23` disjoint live games after removing four overlapping EpisodeIds.  Both
  seats, steps `360/648`, horizons `6/12/24`, ten marginal/snapshot/history
  particles, a blank-private sanity particle and the forbidden oracle produced
  `92` seat-checkpoint cases.  All methods use the same lower-quartile objective
  over hidden particles, synthetic RNG and two reactive opponent responses.
  `27/27` exported live traces reproduced official money and market inventory
  at every one of `719` transitions (`19,413` exact transitions total).
- The registered history gate failed.  At step 360 / horizon 24 even blank,
  marginal, snapshot and history all had `100%` top-3 recall, `100%` top-1
  agreement and zero oracle regret.  At step 648 / horizon 24, blank was
  `97.8%/91.3%` top-3/top-1 with mean regret `19.46`; marginal was
  `100%/93.5%/6.38`; snapshot was `100%/95.7%/1.18`; history regressed to
  `100%/93.5%/3.21`.  History had one small six-turn late advantage, but did not
  beat snapshot at the registered 24-turn decision horizon.
- Oracle-best plans also exposed a proposal/value bottleneck.  At horizon 24,
  step 360 selected maintenance in `39/46`, strawberry in `6/46` and carrot in
  `1/46`; step 648 selected maintenance in `28/46`, liquidation in `15/46`,
  strawberry in `2/46` and melon in `1/46`.  No animal route was oracle-best.
  The full 3,456-branch case took mean `533 ms`, p95 `577 ms` and max `609 ms`
  including process startup but excluding Python feature construction, so the
  strict all-cases 600 ms gate also failed.
- Decision: reject N72 for online integration and do not run official paired
  outcomes or spend a submission.  N71 remains a valid legal particle proposal,
  but current plan choice does not benefit from its extra history information.
  Move to N73: calibrate an inference-visible learned leaf value and enrich the
  policy-derived task vocabulary before revisiting belief search.

## E103 — inference-visible residual leaf value / partial transfer, gate failed

- Added `rl/evaluate_leaf_value.py` with an explicit deployment contract: all
  `119` inputs come from the controlled seat's legal observation (public farms,
  market and town plus its own shed, seeds and carried inventories).  Replay
  actions, names, EpisodeId, source seed and the other seat's private payload
  are forbidden.  Ridge, kNN and shallow trees predict either the absolute
  target or a residual to current money / a hand-marked farm value.  Complete
  EpisodeIds, including both seats and all checkpoints, stay in one of five CV
  folds; the fixed transfer is `40` top-20 games to `23` disjoint live-focus
  games after excluding four overlapping EpisodeIds.
- The full evaluation used every day boundary from step `24` through `648`:
  `2,160` train and `1,242` holdout rows.  For the +24-turn margin, grouped CV
  selected ridge residual-to-current-money and improved MAE `1,182.23 →
  1,152.41` (+2.5%).  It transferred at `1,248.39 → 1,218.00` (+2.4%) and
  Spearman `0.725 → 0.727`, but paired winner accuracy regressed `81.5% →
  80.4%`.  It beat current money at only `11/27` individual checkpoints and
  was worse at both registered anchors: step 360 `1,337.91 → 1,354.36` and
  step 648 `1,145.13 → 1,193.31`; late winner accuracy fell `95.7% → 91.3%`.
- For final margin, grouped CV selected ridge residual-to-legal-marked-value.
  Overall holdout MAE improved over the strongest simple holdout baseline
  `4,026.44 → 3,888.57` (+3.4%) and Spearman improved `0.386 → 0.443`.  The
  useful signal is concentrated in midgame: at step 360 it beat checkpoint
  mean on MAE `4,292.26 → 4,084.29` and all simple baselines on paired winner
  accuracy (`73.9%` versus at most `65.2%`).  It failed catastrophically near
  terminal: at step 648 current-money MAE/winner were `1,798.57 / 87.0%`, while
  the learned head scored `3,786.26 / 65.2%`.
- Decision: retain the legal dataset, residual infrastructure and midgame
  signal, but reject N73's single phase-agnostic value for rollout integration,
  official paired games or submission.  Aggregate MAE cannot override a
  registered checkpoint failure, especially where the exact terminal money
  baseline becomes increasingly sufficient.  Next test N74 as a separately
  registered phase-gated value: horizon-delta / win heads in broad midgame and
  a deterministic current-money or exact short-to-terminal fallback after a
  training-CV-selected cutoff, then evaluate on newly downloaded unseen games.
  Full suite passes `131/131`; no submission was spent.

## E104 — frozen phase-consistent leaf value / partial transfer, rank gate failed

- Added `rl/phase_leaf_value.py`, five tests and the tracked frozen model
  `rl/frozen_phase_value_e104.json`.  Four season phases (`24–192`, `216–480`,
  `504–576`, `600–648`) independently select a ridge residual, legal fallback
  and shrinkage using only five-fold complete-EpisodeId CV on the 40 top-20
  games.  A candidate is ineligible if it worsens current-money MAE or paired
  winner accuracy at a registered anchor in its phase.  The separate rank head
  optimizes paired winner accuracy.  The model and training provenance were
  pushed as commit `7e5854b` before any new EpisodeId was requested.
- The frozen training gate passed.  Versus the strongest simple baseline,
  24-turn OOF MAE improved `1,182.23 → 1,121.82` (+5.1%); at steps
  `360/600/648` it improved `1,114.58 → 1,070.56`, `1,125.72 → 1,112.48`
  and `1,627.20 → 1,533.86` without a current-money winner regression.  Final
  OOF MAE improved `2,971.75 → 2,672.49` (+10.1%); anchor MAE also improved at
  all three points and rank accuracy was `60.6%` versus the best simple
  baseline's `56.0%` overall.
- Only after the freeze, downloaded 17 new S09/S10 public episodes spanning 17
  distinct opponent matchups.  The block contains `918` seat-checkpoint rows,
  zero training/old-replay overlap and no refit.  24-turn MAE transferred well
  overall (`1,325.58 → 1,249.97`, +5.7%) and at steps 360/648, but failed at
  step 600 (`693.29 → 785.77`).  Overall paired winner also slipped `81.5% →
  80.0%`; at step 360 the candidate scored `76.5%` versus the strongest legal
  baseline's `88.2%`.
- Phase separation repaired N73's terminal failure for final value.  Fresh
  final MAE/winner at step 600 improved `3,535.82 / 76.5% → 2,912.61 / 82.4%`
  and at step 648 `3,321.82 / 82.4% → 2,921.34 / 88.2%`.  Yet step-360 final
  winner accuracy regressed `64.7% → 58.8%`, despite a small MAE gain, and the
  dedicated rank head made the same error.
- Decision: retain the frozen model as evidence that phase-specific residuals
  fix terminal calibration, but reject N74 for macro-plan integration,
  official games or submission.  MAE and outcome ranking are distinct gates;
  a lower absolute error cannot excuse more reversed winners.  Test N75 as an
  antisymmetric pairwise/ordinal value with a train-CV confidence gate back to
  current money, freeze it, and use a second untouched policy block.  Full
  suite passes `136/136`; no submission was spent.

## E105 — frozen antisymmetric pairwise leaf rank / fresh transfer pass

- Added `rl/pairwise_leaf_rank.py`, five tests and the tracked
  `rl/frozen_pairwise_rank_e105.json`.  Each training example subtracts the two
  independently legal controlled-seat feature vectors at one
  episode/checkpoint.  Fitting both `x,y` and `-x,-y` forces an antisymmetric
  scalar score.  The score can override current-money ordering only when the
  pair is within a frozen money threshold and the ridge confidence exceeds a
  frozen threshold.  Complete EpisodeIds remain in one CV fold; each phase
  requires a net repair of at least `max(2, 2% of pairs)` and no current-money
  regression at its registered anchors.
- On `1,080` grouped top-20 pairs, OOF accuracy improved `53.15% → 66.85%`.
  The four phases improved `39.06 → 60.00%`, `52.71 → 64.79%`, `66.88 →
  75.62%` and `74.17 → 81.67%`.  Registered anchors improved step 360
  `52.5 → 70.0%`, step 600 `72.5 → 77.5%`, and step 648 `80.0 → 87.5%`.
  All 80 EpisodeIds from training, prior live-focus and E104 fresh transfer
  were serialized as forbidden evaluation provenance.  Coefficients and
  thresholds were pushed in commit `3781215` before S08/S05 episodes were
  listed or downloaded.
- The second untouched block contains 20 S08/S05 games and `540` non-tied
  episode-checkpoint pairs with zero forbidden overlap.  The frozen ranker
  improved overall accuracy to `63.5%` versus current money `56.7%` and
  legal-marked value `58.9%`.  It passed every registered anchor against both
  baselines: step 360 `60%` versus `55%/55%`, step 600 `80%` versus `75%/70%`,
  and step 648 `90%` versus `85%/70%`.
- N74's magnitude head retained its terminal transfer on this new policy
  block.  At step 600 final MAE/winner were `2,979 / 80%` versus the best
  simple baselines' `4,093 / 75%`; at step 648 they were `2,301 / 90%` versus
  `3,655 / 85%`.  Some aggregate and short-horizon N74 gates remain failed,
  so only terminal magnitude—not the whole phase-value package—is retained.
- Decision: N75 passes the replay-level rank and terminal-magnitude
  prerequisite.  Do not submit yet: replay winner prediction is not evidence
  that the same score orders counterfactual branches.  Proceed to N76 with a
  richer shadow-policy macro vocabulary and require lower full-state-oracle
  plan regret, top-3 recall, under-600-ms latency and then official both-seat
  outcome over N39.  Full suite passes `141/141`; no submission was spent.
