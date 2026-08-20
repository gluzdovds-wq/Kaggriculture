# S03 — V36 with wider reserve-safe WHEAT batching

- Base: public Kaggle code `kaitofukami/106-130-multi-generation-v36-robust-hybrid`.
- Only policy change: `market_quantity=20` instead of `10`.
- All V36 cash, feed, investment, capacity and market-order reserves remain.
- Generated with `tools/make_v36_variant.py`.
- SHA-256 of `main.py`:
  `8c27bc4e0f95bb56a188b43ee4624a7b04cfdabe8a53f850a19a5b1bfc76f92c`.
- Kaggle submission reference: `55651309`.
- Initial completed public score: `600.0`; exact V36 S02 was `1537.0` in the
  same poll. This is a negative online calibration signal despite the small
  positive paired local margin, so q20 was not promoted to incumbent.

Pre-submission local evidence: six paired seeds against exact V36 gave outcome
0.75 and average margin about +67 coins. On matched public-pool games, average
margin improved by +127 to +134 coins without changing the per-style outcome.
