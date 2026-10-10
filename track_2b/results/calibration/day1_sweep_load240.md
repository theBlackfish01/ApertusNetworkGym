# Load calibration — `jocn_benchmark`

Generated from `results/calibration/day1_sweep_load240.json` (run 20261009T193210Z). Rendered by `src/calibrate.py`; do not edit by hand.

ONG commit `f7c4491caa9090577fe451a6f9f57a8f60edc81e`, seeds [1, 2, 3], mean ± sample std across seeds. SBP = service blocking probability, BBP = bit-rate blocking probability.

## Mode `window`

Teacher warm-up of 1000 requests, counters reset, policy decides the next 2000 (SPEC section 7 protocol).

| Load (E) | SBP % KSP-BM-FF (baseline) | BBP % KSP-BM-FF (baseline) | SBP % BM-LS-KSP (teacher) | BBP % BM-LS-KSP (teacher) | Teacher better (seeds) | Slots in use at last request % (teacher) |
|---|---|---|---|---|---|---|
| 240 | 2.68 ± 0.40 | 7.85 ± 0.92 | 1.22 ± 0.45 | 3.54 ± 1.22 | 3/3 | 29.4 |
