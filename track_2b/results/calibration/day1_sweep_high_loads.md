# Load calibration — `jocn_benchmark`

Generated from `results/calibration/day1_sweep_high_loads.json` (run 20261009T192739Z). Rendered by `src/calibrate.py`; do not edit by hand.

ONG commit `f7c4491caa9090577fe451a6f9f57a8f60edc81e`, seeds [1, 2, 3], mean ± sample std across seeds. SBP = service blocking probability, BBP = bit-rate blocking probability.

## Mode `window`

Teacher warm-up of 1000 requests, counters reset, policy decides the next 2000 (SPEC section 7 protocol).

| Load (E) | SBP % KSP-BM-FF (baseline) | BBP % KSP-BM-FF (baseline) | SBP % BM-LS-KSP (teacher) | BBP % BM-LS-KSP (teacher) | Teacher better (seeds) | Slots in use at last request % (teacher) |
|---|---|---|---|---|---|---|
| 330 | 6.08 ± 0.88 | 17.84 ± 2.30 | 4.08 ± 0.88 | 11.93 ± 2.19 | 3/3 | 36.3 |
| 390 | 8.23 ± 0.80 | 23.99 ± 1.71 | 5.98 ± 0.65 | 17.53 ± 1.33 | 3/3 | 38.6 |
| 450 | 9.50 ± 0.83 | 27.56 ± 1.43 | 7.68 ± 0.83 | 22.31 ± 1.91 | 3/3 | 41.6 |
| 510 | 11.60 ± 0.95 | 33.11 ± 2.31 | 9.92 ± 0.99 | 28.52 ± 2.28 | 3/3 | 43.9 |
