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

## Evidence on this PC

- 13/13 official traces matched at every one of 719 transitions: nine
  `starter/random/pass` episodes and four competitive V36↔multi-route episodes
  in both seat orders.
- Total validated transitions: 9,347.
- MSVC benchmark: about 441 episodes/s (2.27 ms/episode) on a competitive trace.

This is a partial pass, not a blanket proof. New action families and every
future engine version still require fresh official traces.
