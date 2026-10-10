# Results

Rendered by `src/report_tables.py` from `results/eval/` and `results/offline/`; do not edit by hand.

Closed loop: 1000-request warm-up by the no-intent teacher, then 2000 measured requests per condition, load and seed. Cells are mean ± sample standard deviation over seeds; a cell without ± comes from a single seed (see the Seeds column of the latency table). An invalid answer is replaced by first fit; a violation is an executed decision outside the intent's admissible set. An intent binds on a request when the no-intent teacher's own choice is not admissible, so the no-intent teacher's violation rate is the share of binding requests; first fit ignores the intent in its own way.

## Service blocking probability, % — load 240 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 |
| BM-LS-KSP (no-intent teacher) | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 |
| Intent-aware teacher (oracle) | 1.20 ± 0.44 | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.52 ± 0.54 | 11.52 ± 0.43 |
| MLP control | 1.33 ± 0.38 | 4.57 ± 0.67 | 1.75 ± 0.66 | 1.27 ± 0.36 | 2.12 ± 0.88 | 2.38 ± 0.28 | 2.83 ± 0.65 |
| Apertus 8B zero-shot | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned | 1.13 ± 0.33 | 18.88 ± 1.07 | 1.92 ± 0.51 | 1.42 ± 0.46 | 2.30 ± 0.78 | 3.75 ± 0.75 | 13.03 ± 0.68 |

## Intent violations, % of decisions — load 240 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.0 ± 0.0 | 26.2 ± 1.1 | 12.1 ± 0.2 | 49.5 ± 1.1 | 0.1 ± 0.1 | 22.3 ± 0.6 | 38.9 ± 1.4 |
| BM-LS-KSP (no-intent teacher) | 0.0 ± 0.0 | 28.2 ± 0.4 | 21.2 ± 0.8 | 41.1 ± 0.7 | 3.8 ± 0.5 | 23.6 ± 1.3 | 39.2 ± 1.5 |
| Intent-aware teacher (oracle) | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| MLP control | 0.0 ± 0.0 | 0.6 ± 0.2 | 2.5 ± 0.4 | 12.2 ± 0.8 | 0.2 ± 0.1 | 3.3 ± 0.5 | 31.2 ± 1.5 |
| Apertus 8B zero-shot | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned | 0.0 ± 0.0 | 18.4 ± 1.3 | 0.4 ± 0.1 | 1.2 ± 0.2 | 0.1 ± 0.0 | 3.0 ± 0.3 | 24.2 ± 1.4 |

## Invalid answers, % of decisions — load 240 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| BM-LS-KSP (no-intent teacher) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Intent-aware teacher (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| MLP control | 0.00 ± 0.00 | 0.07 ± 0.06 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.03 ± 0.06 | 0.32 ± 0.29 |
| Apertus 8B zero-shot | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned | 0.00 ± 0.00 | 0.07 ± 0.08 | 0.33 ± 0.03 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.08 ± 0.03 | 0.07 ± 0.06 |

## Service blocking probability, % — load 390 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 |
| BM-LS-KSP (no-intent teacher) | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 |
| Intent-aware teacher (oracle) | 5.97 ± 0.68 | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.73 ± 0.58 | 14.65 ± 1.26 |
| MLP control | 6.28 ± 0.85 | 9.37 ± 0.91 | 6.90 ± 0.93 | 6.27 ± 0.58 | 7.48 ± 0.83 | 7.78 ± 0.63 | 7.90 ± 0.98 |
| Apertus 8B zero-shot | 9.20 | 14.60 | 8.50 | 9.05 | 8.95 | 9.05 | 9.25 |
| Apertus 8B fine-tuned | 5.85 ± 0.71 | 21.43 ± 1.07 | 7.10 ± 0.85 | 6.43 ± 0.86 | 7.53 ± 0.81 | 9.33 ± 0.55 | 15.80 ± 1.05 |

## Intent violations, % of decisions — load 390 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.0 ± 0.0 | 24.5 ± 0.9 | 10.4 ± 0.3 | 43.2 ± 2.4 | 0.1 ± 0.1 | 19.3 ± 1.5 | 33.9 ± 2.2 |
| BM-LS-KSP (no-intent teacher) | 0.0 ± 0.0 | 25.8 ± 1.3 | 18.4 ± 1.2 | 34.7 ± 1.0 | 2.0 ± 0.3 | 20.3 ± 0.8 | 33.5 ± 1.0 |
| Intent-aware teacher (oracle) | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| MLP control | 0.0 ± 0.0 | 0.9 ± 0.2 | 2.4 ± 0.2 | 11.8 ± 0.4 | 0.1 ± 0.1 | 3.7 ± 0.2 | 28.7 ± 1.5 |
| Apertus 8B zero-shot | 0.1 | 28.1 | 10.2 | 42.1 | 0.1 | 19.2 | 32.6 |
| Apertus 8B fine-tuned | 0.0 ± 0.0 | 17.5 ± 0.5 | 0.5 ± 0.1 | 1.5 ± 0.2 | 0.1 ± 0.1 | 3.4 ± 0.4 | 20.4 ± 0.3 |

## Invalid answers, % of decisions — load 390 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| BM-LS-KSP (no-intent teacher) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Intent-aware teacher (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| MLP control | 0.00 ± 0.00 | 0.03 ± 0.03 | 0.02 ± 0.03 | 0.00 ± 0.00 | 0.05 ± 0.09 | 0.03 ± 0.06 | 1.28 ± 0.39 |
| Apertus 8B zero-shot | 94.05 | 87.95 | 96.50 | 98.25 | 97.85 | 96.65 | 96.95 |
| Apertus 8B fine-tuned | 0.00 ± 0.00 | 0.32 ± 0.13 | 0.63 ± 0.19 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.08 ± 0.06 | 0.10 ± 0.10 |

## Decision latency and violations on binding requests (all loads and conditions)

| Policy | ms per decision | Violations on binding requests, % (pooled) | Seeds |
|---|---|---|---|
| KSP-BM-FF first fit | 0.03 | 58.0 | 1, 2, 3 |
| BM-LS-KSP (no-intent teacher) | 0.28 | 99.9 | 1, 2, 3 |
| Intent-aware teacher (oracle) | 0.01 | 0.0 | 1, 2, 3 |
| MLP control | 0.05 | 23.0 | 1, 2, 3 |
| Apertus 8B zero-shot | 690.10 | 59.6 | 1 |
| Apertus 8B fine-tuned | 2697.84 | 20.7 | 1, 2, 3 |

## Offline agreement with the teacher on the held-out splits

| Policy | In distribution: exact % | In distribution: admissible % | Unseen wording: exact % | Unseen wording: admissible % | Unseen pairs: exact % | Unseen pairs: admissible % |
|---|---|---|---|---|---|---|
| Intent-aware teacher (oracle) | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| MLP control | 90.0 | 96.4 | 91.5 | 95.7 | 70.0 | 70.0 |
| Apertus 8B zero-shot | 1.0 | 3.3 | 0.7 | 2.5 | 1.5 | 4.8 |
| Apertus 8B zero-shot, no answer constraint | 1.0 | 3.3 | 0.7 | 2.5 | 1.5 | 4.8 |
| Apertus 8B fine-tuned | 93.2 | 95.8 | 89.2 | 95.7 | 77.5 | 78.0 |
| Apertus 8B fine-tuned, no answer constraint | 92.9 | 95.9 | 89.2 | 95.7 | 77.0 | 77.5 |
