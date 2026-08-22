# Fast simulator gate (G02)

The simulator source comes from the public Kaggle notebook
`nikital7/4000x-environment-speedup-kaggriculture` and is intentionally kept
under the ignored `research/public_notebooks/` tree. This repository stores our
safe extractor, the narrow 1.32.7 patch and additional scanner, rather than
silently vendoring someone else's notebook.

## Reproduce on Windows

1. Pull the notebook with Kaggle CLI.
2. Extract only `%%writefile` cells without executing the notebook:

   `python tools/extract_writefile_notebook.py NOTEBOOK.ipynb OUTPUT_DIR`

3. Patch `OUTPUT_DIR/sim.hpp`:

   `python tools/patch_fast_sim_1327.py OUTPUT_DIR/sim.hpp`

4. Open an MSVC developer shell and compile `validate.cpp`, `bench.cpp`, and
   `fast_sim/scan_hinge.cpp` with `/O2 /std:c++17`.
5. Generate traces using the official `kaggle-environments==1.32.7`
   `export_trace.py`, then require `validate.exe` to print `719 steps exact` for
   every trace before using the simulator for research.

For the N68 midgame search gate, compile `fast_sim/branch_bench.cpp` against the
patched `sim.hpp`, then pass a competitive trace, prefix and repetition count.
The benchmark verifies semantically identical replay from two independent
midgame forks (field-by-field, excluding irrelevant C++ struct padding) and
reports 6/12/24-turn branch throughput plus an optimistic 600 ms capacity.
That capacity excludes candidate generation, belief construction and value
inference, so it is an upper bound rather than a submission latency claim.

## Evidence on this PC

- 13/13 official traces matched at every one of 719 transitions: nine
  `starter/random/pass` episodes and four competitive V36↔multi-route episodes
  in both seat orders.
- Total validated transitions: 9,347.
- MSVC benchmark: about 441 episodes/s (2.27 ms/episode) on a competitive trace.
- N68 midgame fork gate: `State` is 7,672 bytes and `Sim` is 7,728 bytes;
  both are trivially copyable.  Four early/middle/late, both-seat cases passed
  all `12/12` semantic fork-versus-linear replay checks.  Across the measured
  competitive cases, the worst optimistic 600 ms capacities were about 33,489
  six-turn, 17,613 twelve-turn and 6,990 twenty-four-turn branches.

For N72, compile `fast_sim/macro_plan_eval.cpp` against the same patched
`sim.hpp`.  `rl/evaluate_macro_plan_recall.py` exports downloaded replay roots,
selects disjoint marginal/snapshot/history particles and ranks nine reactive
task graphs.  Recorded actions stop at the checkpoint; both future seats use
reactive task graphs and shared synthetic RNG seeds.  On the 27 live-focus
traces, the validator reproduced `27/27 × 719 = 19,413` money/market transitions.
The full 23-game disjoint both-seat evaluation rejected history particles:
snapshot beat history on late 24-turn top-1 agreement and regret, while top-3
recall was saturated.  This executable is an offline value/proposal diagnostic,
not a promoted online planner.

This is a partial pass, not a blanket proof. New action families and every
future engine version still require fresh official traces.  The branch counts
exclude legal belief-state construction, policy proposals and value inference;
they prove offline search throughput, not a deployable online search agent.
