# Load calibration — `jocn_benchmark`

Generated from `results/calibration/day1_sweep.json` (run 20261009T192712Z). Rendered by `src/calibrate.py`; do not edit by hand.

ONG commit `f7c4491caa9090577fe451a6f9f57a8f60edc81e`, seeds [1, 2, 3], mean ± sample std across seeds. SBP = service blocking probability, BBP = bit-rate blocking probability.

## Mode `cold`

Policy decides requests 1–1000 on an empty network (ONG JOCN sweep style).

| Load (E) | SBP % KSP-BM-FF (baseline) | BBP % KSP-BM-FF (baseline) | SBP % BM-LS-KSP (teacher) | BBP % BM-LS-KSP (teacher) | Teacher better (seeds) | Slots in use at last request % (teacher) |
|---|---|---|---|---|---|---|
| 150 | 0.67 ± 0.21 | 1.90 ± 0.62 | 0.30 ± 0.10 | 0.85 ± 0.29 | 3/3 | 23.8 |
| 210 | 1.57 ± 0.67 | 4.47 ± 1.95 | 0.53 ± 0.31 | 1.52 ± 0.88 | 3/3 | 30.8 |
| 270 | 3.03 ± 0.15 | 8.62 ± 0.40 | 1.53 ± 0.06 | 4.36 ± 0.16 | 3/3 | 37.1 |

## Mode `window`

Teacher warm-up of 1000 requests, counters reset, policy decides the next 2000 (SPEC section 7 protocol).

| Load (E) | SBP % KSP-BM-FF (baseline) | BBP % KSP-BM-FF (baseline) | SBP % BM-LS-KSP (teacher) | BBP % BM-LS-KSP (teacher) | Teacher better (seeds) | Slots in use at last request % (teacher) |
|---|---|---|---|---|---|---|
| 150 | 0.57 ± 0.13 | 1.66 ± 0.32 | 0.28 ± 0.20 | 0.83 ± 0.58 | 3/3 | 17.9 |
| 210 | 1.58 ± 0.53 | 4.62 ± 1.42 | 0.60 ± 0.30 | 1.75 ± 0.85 | 3/3 | 27.1 |
| 270 | 3.88 ± 0.80 | 11.35 ± 1.94 | 2.00 ± 0.61 | 5.83 ± 1.59 | 3/3 | 31.9 |
