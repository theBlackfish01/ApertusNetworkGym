# Results

Rendered by `src/report_tables.py` from `results/eval/` and `results/offline/`; do not edit by hand.

Second pass (avoid-link pairs are filter-then-rank, two epochs). The first pass is in results/pass1/. The translator rows are from phase 1; its own tables are in phase1.md.

Closed loop: 1000-request warm-up by the no-intent teacher, then 2000 measured requests per condition, load and seed. Cells are mean ± sample standard deviation over seeds; a cell without ± comes from a single seed (see the Seeds column of the latency table). An invalid answer is replaced by first fit; a violation is an executed decision outside the intent's admissible set. An intent binds on a request when the no-intent teacher's own choice is not admissible, so the no-intent teacher's violation rate is the share of binding requests; first fit ignores the intent in its own way.

## Service blocking probability, % — load 240 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 | 2.68 ± 0.40 |
| BM-LS-KSP (no-intent teacher) | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 | 1.22 ± 0.45 |
| Intent-aware teacher (oracle) | 1.20 ± 0.44 | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.52 ± 0.54 | 10.32 ± 0.20 |
| MLP control | 1.17 ± 0.40 | 4.70 ± 0.66 | 1.82 ± 0.68 | 1.30 ± 0.45 | 2.15 ± 0.83 | 2.55 ± 0.79 | 3.08 ± 0.58 |
| Apertus 8B zero-shot | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned | 1.32 ± 0.43 | 5.00 ± 0.66 | 2.18 ± 0.64 | 1.30 ± 0.15 | 2.27 ± 0.86 | 2.53 ± 0.55 | 3.43 ± 0.51 |
| Translator: keyword parser + rule engine | 1.20 ± 0.44 | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.22 ± 0.31 | 10.32 ± 0.20 |
| Translator: Apertus as is + rule engine | 1.20 ± 0.44 | 6.55 ± 0.56 | 1.78 ± 0.66 | 1.73 ± 0.42 | 2.05 ± 0.59 | 2.62 ± 0.55 | 7.07 ± 0.86 |
| Translator: Apertus with 7 examples + rule engine | 1.20 ± 0.44 | 4.75 ± 0.87 | 1.78 ± 0.66 | 1.68 ± 0.65 | 2.28 ± 0.84 | 2.57 ± 0.45 | 9.03 ± 0.29 |
| Translator: Apertus fine-tuned + rule engine | 1.20 ± 0.44 | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.52 ± 0.54 | 8.85 ± 0.43 |

## Intent violations, % of decisions — load 240 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.0 ± 0.0 | 26.2 ± 1.1 | 12.1 ± 0.2 | 49.5 ± 1.1 | 0.1 ± 0.1 | 22.3 ± 0.6 | 38.9 ± 1.4 |
| BM-LS-KSP (no-intent teacher) | 0.0 ± 0.0 | 28.2 ± 0.4 | 21.2 ± 0.8 | 41.1 ± 0.7 | 3.8 ± 0.5 | 23.6 ± 1.3 | 39.0 ± 1.5 |
| Intent-aware teacher (oracle) | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| MLP control | 0.0 ± 0.0 | 0.4 ± 0.1 | 2.9 ± 0.6 | 10.9 ± 1.0 | 0.2 ± 0.0 | 3.5 ± 0.5 | 27.1 ± 1.1 |
| Apertus 8B zero-shot | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned | 0.0 ± 0.0 | 3.9 ± 0.3 | 0.7 ± 0.1 | 0.5 ± 0.2 | 0.2 ± 0.1 | 0.9 ± 0.0 | 14.2 ± 0.7 |
| Translator: keyword parser + rule engine | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 13.4 ± 0.7 | 0.0 ± 0.0 |
| Translator: Apertus as is + rule engine | 0.0 ± 0.0 | 2.8 ± 0.2 | 0.0 ± 0.0 | 27.3 ± 2.2 | 0.5 ± 0.1 | 8.1 ± 1.2 | 11.4 ± 0.7 |
| Translator: Apertus with 7 examples + rule engine | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 13.0 ± 0.6 | 0.0 ± 0.0 | 3.8 ± 0.7 | 4.7 ± 0.6 |
| Translator: Apertus fine-tuned + rule engine | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 3.0 ± 0.2 |

## Invalid answers, % of decisions — load 240 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| BM-LS-KSP (no-intent teacher) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Intent-aware teacher (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| MLP control | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.02 ± 0.03 | 0.02 ± 0.03 | 0.33 ± 0.19 |
| Apertus 8B zero-shot | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned | 0.00 ± 0.00 | 0.10 ± 0.00 | 0.20 ± 0.05 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.05 ± 0.05 | 0.03 ± 0.06 |
| Translator: keyword parser + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Translator: Apertus as is + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Translator: Apertus with 7 examples + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Translator: Apertus fine-tuned + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Service blocking probability, % — load 390 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 |
| BM-LS-KSP (no-intent teacher) | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 |
| Intent-aware teacher (oracle) | 5.97 ± 0.68 | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.73 ± 0.58 | 13.45 ± 0.56 |
| MLP control | 5.93 ± 0.98 | 9.58 ± 1.09 | 7.20 ± 0.58 | 6.37 ± 0.71 | 7.37 ± 0.78 | 7.52 ± 0.68 | 8.30 ± 0.85 |
| Apertus 8B zero-shot | 9.20 | 14.60 | 8.50 | 9.05 | 8.95 | 9.05 | 9.25 |
| Apertus 8B fine-tuned | 6.42 ± 0.83 | 10.23 ± 0.85 | 7.40 ± 0.78 | 6.25 ± 1.13 | 7.52 ± 0.78 | 7.67 ± 0.83 | 8.72 ± 1.10 |
| Translator: keyword parser + rule engine | 5.97 ± 0.68 | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.12 ± 0.80 | 13.45 ± 0.56 |
| Translator: Apertus as is + rule engine | 5.97 ± 0.68 | 10.97 ± 0.86 | 7.05 ± 0.79 | 7.07 ± 0.65 | 7.30 ± 0.48 | 8.00 ± 0.78 | 10.72 ± 0.72 |
| Translator: Apertus with 7 examples + rule engine | 5.97 ± 0.68 | 10.03 ± 0.83 | 7.05 ± 0.79 | 6.68 ± 0.63 | 7.53 ± 0.73 | 7.72 ± 0.48 | 12.45 ± 0.30 |
| Translator: Apertus fine-tuned + rule engine | 5.97 ± 0.68 | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.73 ± 0.58 | 12.22 ± 1.01 |

## Intent violations, % of decisions — load 390 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.0 ± 0.0 | 24.5 ± 0.9 | 10.4 ± 0.3 | 43.2 ± 2.4 | 0.1 ± 0.1 | 19.3 ± 1.5 | 33.9 ± 2.2 |
| BM-LS-KSP (no-intent teacher) | 0.0 ± 0.0 | 25.8 ± 1.3 | 18.4 ± 1.2 | 34.7 ± 1.0 | 2.0 ± 0.3 | 20.3 ± 0.8 | 33.3 ± 0.9 |
| Intent-aware teacher (oracle) | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| MLP control | 0.0 ± 0.0 | 0.8 ± 0.2 | 2.7 ± 0.5 | 11.4 ± 1.0 | 0.1 ± 0.1 | 3.2 ± 0.4 | 24.9 ± 1.6 |
| Apertus 8B zero-shot | 0.1 | 28.1 | 10.2 | 42.1 | 0.1 | 19.2 | 32.6 |
| Apertus 8B fine-tuned | 0.0 ± 0.0 | 3.3 ± 0.2 | 0.6 ± 0.2 | 0.7 ± 0.1 | 0.1 ± 0.0 | 1.0 ± 0.1 | 12.9 ± 0.7 |
| Translator: keyword parser + rule engine | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 11.3 ± 0.5 | 0.0 ± 0.0 |
| Translator: Apertus as is + rule engine | 0.0 ± 0.0 | 2.2 ± 0.3 | 0.0 ± 0.0 | 22.5 ± 1.5 | 0.4 ± 0.1 | 7.2 ± 1.0 | 10.4 ± 0.4 |
| Translator: Apertus with 7 examples + rule engine | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 10.6 ± 1.6 | 0.0 ± 0.0 | 3.5 ± 0.4 | 4.2 ± 0.8 |
| Translator: Apertus fine-tuned + rule engine | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 2.8 ± 0.4 |

## Invalid answers, % of decisions — load 390 E

| Policy | No intent | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| BM-LS-KSP (no-intent teacher) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Intent-aware teacher (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| MLP control | 0.00 ± 0.00 | 0.03 ± 0.03 | 0.03 ± 0.06 | 0.02 ± 0.03 | 0.10 ± 0.09 | 0.02 ± 0.03 | 0.70 ± 0.54 |
| Apertus 8B zero-shot | 94.05 | 87.95 | 96.50 | 98.25 | 97.85 | 96.65 | 96.95 |
| Apertus 8B fine-tuned | 0.00 ± 0.00 | 0.12 ± 0.03 | 0.52 ± 0.13 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.10 ± 0.09 | 0.07 ± 0.06 |
| Translator: keyword parser + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Translator: Apertus as is + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Translator: Apertus with 7 examples + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Translator: Apertus fine-tuned + rule engine | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Unseen pairs by pair: intent violations, % of decisions (pooled over seeds)

| Policy | I1+I4, load 240 E | I2+I3, load 240 E | I1+I4, load 390 E | I2+I3, load 390 E |
|---|---|---|---|---|
| KSP-BM-FF first fit | 27.6 | 50.5 | 24.5 | 43.2 |
| BM-LS-KSP (no-intent teacher) | 31.7 | 46.4 | 27.3 | 39.3 |
| Intent-aware teacher (oracle) | 0.0 | 0.0 | 0.0 | 0.0 |
| MLP control | 5.1 | 49.6 | 6.5 | 43.1 |
| Apertus 8B zero-shot | – | – | 23.4 | 42.3 |
| Apertus 8B fine-tuned | 3.7 | 25.0 | 3.7 | 22.0 |
| Translator: keyword parser + rule engine | 0.0 | 0.0 | 0.0 | 0.0 |
| Translator: Apertus as is + rule engine | 1.4 | 21.6 | 1.8 | 18.9 |
| Translator: Apertus with 7 examples + rule engine | 0.0 | 9.5 | 0.0 | 8.2 |
| Translator: Apertus fine-tuned + rule engine | 0.0 | 6.1 | 0.0 | 5.5 |

## Needless rejects (a request with an admissible path is rejected), % of decisions (pooled over seeds)

| Policy | Avoid link, load 240 E | Avoid link, load 390 E | Unseen wording, load 240 E | Unseen wording, load 390 E | Unseen pairs, load 240 E | Unseen pairs, load 390 E |
|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BM-LS-KSP (no-intent teacher) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Intent-aware teacher (oracle) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MLP control | 0.1 | 0.2 | 0.1 | 0.1 | 0.1 | 0.1 |
| Apertus 8B zero-shot | – | 6.0 | – | 0.5 | – | 0.2 |
| Apertus 8B fine-tuned | 1.2 | 1.2 | 0.3 | 0.4 | 0.7 | 0.6 |
| Translator: keyword parser + rule engine | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Translator: Apertus as is + rule engine | 2.2 | 1.4 | 0.1 | 0.1 | 0.6 | 0.5 |
| Translator: Apertus with 7 examples + rule engine | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 0.1 |
| Translator: Apertus fine-tuned + rule engine | 0.0 | 0.0 | 0.0 | 0.0 | 0.3 | 0.3 |

## Accepts although the intent leaves no admissible path, % of decisions (pooled over seeds)

| Policy | Avoid link, load 240 E | Avoid link, load 390 E | Unseen wording, load 240 E | Unseen wording, load 390 E | Unseen pairs, load 240 E | Unseen pairs, load 390 E |
|---|---|---|---|---|---|---|
| KSP-BM-FF first fit | 4.0 | 4.2 | 0.9 | 1.0 | 9.9 | 7.9 |
| BM-LS-KSP (no-intent teacher) | 3.4 | 4.2 | 0.8 | 1.2 | 9.0 | 8.5 |
| Intent-aware teacher (oracle) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MLP control | 0.1 | 0.2 | 0.0 | 0.0 | 8.9 | 6.5 |
| Apertus 8B zero-shot | – | 3.7 | – | 0.8 | – | 8.2 |
| Apertus 8B fine-tuned | 0.8 | 0.7 | 0.1 | 0.2 | 8.1 | 6.6 |
| Translator: keyword parser + rule engine | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Translator: Apertus as is + rule engine | 0.0 | 0.1 | 0.0 | 0.0 | 4.8 | 4.1 |
| Translator: Apertus with 7 examples + rule engine | 0.0 | 0.0 | 0.0 | 0.0 | 2.1 | 1.8 |
| Translator: Apertus fine-tuned + rule engine | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 | 1.8 |

## Decision latency and violations on binding requests (all loads and conditions)

| Policy | ms per decision | Violations on binding requests, % (pooled) | Seeds |
|---|---|---|---|
| KSP-BM-FF first fit | 0.04 | 58.0 | 1, 2, 3 |
| BM-LS-KSP (no-intent teacher) | 0.31 | 99.9 | 1, 2, 3 |
| Intent-aware teacher (oracle) | 0.03 | 0.0 | 1, 2, 3 |
| MLP control | 0.07 | 20.8 | 1, 2, 3 |
| Apertus 8B zero-shot | 690.10 | 59.6 | 1 |
| Apertus 8B fine-tuned | 2693.54 | 10.3 | 1, 2, 3 |
| Translator: keyword parser + rule engine | 0.02 | 8.2 | 1, 2, 3 |
| Translator: Apertus as is + rule engine | 0.03 | 20.0 | 1, 2, 3 |
| Translator: Apertus with 7 examples + rule engine | 0.03 | 8.7 | 1, 2, 3 |
| Translator: Apertus fine-tuned + rule engine | 0.04 | 1.6 | 1, 2, 3 |

## Offline agreement with the teacher on the held-out splits

| Policy | In distribution: exact % | In distribution: admissible % | Unseen wording: exact % | Unseen wording: admissible % | Unseen pairs: exact % | Unseen pairs: admissible % |
|---|---|---|---|---|---|---|
| Intent-aware teacher (oracle) | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| MLP control | 91.4 | 97.3 | 93.3 | 96.3 | 72.0 | 72.5 |
| Apertus 8B zero-shot | 1.0 | 3.3 | 0.7 | 2.5 | 1.5 | 4.8 |
| Apertus 8B zero-shot, no answer constraint | 1.0 | 3.3 | 0.7 | 2.5 | 1.5 | 4.8 |
| Apertus 8B fine-tuned | 97.7 | 98.9 | 92.2 | 98.7 | 83.7 | 85.8 |
| Apertus 8B fine-tuned, after epoch 1, no answer constraint | 93.1 | 96.8 | 90.0 | 97.5 | 79.7 | 82.7 |
| Apertus 8B fine-tuned, after epoch 2, no answer constraint | 97.8 | 99.0 | 92.0 | 98.5 | 83.5 | 85.7 |
| Apertus 8B, 7 solved examples in the prompt | 47.7 | 64.2 | 51.3 | 61.5 | 42.8 | 48.8 |
| Translator: keyword parser + rule engine | 100.0 | 100.0 | 75.3 | 86.3 | 100.0 | 100.0 |
| Translator: Apertus as is + rule engine | 93.8 | 95.0 | 89.2 | 89.3 | 87.7 | 87.8 |
| Translator: Apertus with 7 examples + rule engine | 98.1 | 98.1 | 93.8 | 93.8 | 94.7 | 94.7 |
| Translator: Apertus fine-tuned + rule engine | 100.0 | 100.0 | 100.0 | 100.0 | 97.2 | 97.2 |
