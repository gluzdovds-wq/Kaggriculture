# S26 — V48/V43 first-shop router

- SHA-256: `df7c5d5ab336ecd67149d8ab81e88061c3ffc1d5b45a9cbb1100974e138ba558`.
- Size: 169,215 bytes.
- Exact embedded policies: V48 `dadee25a...` and V43 `69f06a80...`.
- Route rule: shadow-run both policies from step zero; after the first town
  shop appears, use V43 only for `FARMERS_MARKET` or `ICE_CREAM_SHOP`, and use
  V48 otherwise.
- Safety: any pre-shop action mismatch, exception, or invalid V43 action
  permanently latches V48 for that seat.
- Offline gate: `27/28`, average margin `+22,272.1` on frozen-28; `8/10`,
  `+6,819.0` on the prior top-five panel; `3/5`, `+182.8` on the first fresh
  top-five panel.  Prefix mismatches were `0` across all 43 replay games.
- Single-process paired smoke versus exact V48 was identical from both seats;
  candidate p95 action latency was about `12.4 ms`, maximum `16.6 ms`.

Generated reproducibly by `tools/make_v48_v43_shop_router.py`.  Upload
`main.py` directly and do not edit it after the hash is recorded.

Submitted on 2026-08-26 09:11 Asia/Novosibirsk as Kaggle ref `55783237`.
