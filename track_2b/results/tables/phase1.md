# Phase 1: translate versus decide

Rendered by `src/report_phase1.py` from `results/translate/`, `results/offline/` and `results/eval/`; do not edit by hand. A translator turns the instruction into constraints and preferences once and the rule engine decides; a decider reads the instruction with every request. Test sets: `src/corpora.py`.

## Instructions translated with the right meaning, % — distinct instructions per set: Dataset wording 819, Independent wording 827, German 653, French 656, Italian 656, Swiss German 242, Misspelt 320, Closed-loop instructions 8505, Other topology 528

| Translator | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Closed-loop instructions | Other topology |
|---|---|---|---|---|---|---|---|---|---|
| Keyword parser (no model) | 99.1 | 42.3 | 8.3 | 9.0 | 0.5 | 7.9 | 10.6 | 99.9 | 98.7 |
| Apertus as is | 80.5 | 75.9 | 64.6 | 72.0 | 67.7 | 46.3 | 68.8 | 89.9 | 79.7 |
| Apertus, 7 examples in the prompt | 92.2 | 91.2 | 87.6 | 93.6 | 93.3 | 71.5 | 83.4 | 99.5 | 92.0 |
| Apertus fine-tuned | 94.6 | 88.5 | 86.5 | 96.5 | 85.2 | 76.0 | 76.6 | 99.4 | 92.6 |
| Apertus, 7 examples, no answer grammar | 87.1 | 83.1 | 68.0 | 83.5 | 73.8 | 52.9 | 70.3 | – | – |
| Apertus fine-tuned, no answer grammar | 93.5 | 87.4 | 78.4 | 95.1 | 81.7 | 68.2 | 72.8 | – | – |

## Instructions applied with a wrong meaning (silent), %

| Translator | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Closed-loop instructions | Other topology |
|---|---|---|---|---|---|---|---|---|---|
| Keyword parser (no model) | 0.0 | 39.8 | 18.4 | 21.2 | 0.6 | 19.8 | 37.2 | 0.0 | 0.0 |
| Apertus as is | 16.8 | 22.5 | 19.8 | 22.9 | 24.7 | 40.5 | 20.6 | 6.0 | 17.4 |
| Apertus, 7 examples in the prompt | 7.7 | 5.3 | 4.9 | 4.1 | 5.3 | 22.3 | 8.4 | 0.4 | 7.6 |
| Apertus fine-tuned | 5.4 | 11.1 | 12.6 | 2.6 | 7.9 | 21.1 | 15.3 | 0.6 | 6.2 |
| Apertus, 7 examples, no answer grammar | 4.8 | 4.2 | 3.7 | 3.0 | 4.3 | 20.2 | 5.0 | – | – |
| Apertus fine-tuned, no answer grammar | 3.2 | 8.0 | 11.5 | 0.9 | 6.1 | 18.6 | 12.2 | – | – |

## Valid instructions the translator refused (visible), %

| Translator | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Closed-loop instructions | Other topology |
|---|---|---|---|---|---|---|---|---|---|
| Keyword parser (no model) | 0.9 | 17.9 | 73.4 | 69.8 | 98.9 | 72.3 | 52.2 | 0.1 | 1.3 |
| Apertus as is | 2.7 | 1.6 | 15.6 | 5.2 | 7.6 | 13.2 | 10.6 | 4.2 | 2.8 |
| Apertus, 7 examples in the prompt | 0.1 | 3.5 | 7.5 | 2.3 | 1.4 | 6.2 | 8.1 | 0.1 | 0.4 |
| Apertus fine-tuned | 0.0 | 0.4 | 0.9 | 0.9 | 6.9 | 2.9 | 8.1 | 0.0 | 1.1 |
| Apertus, 7 examples, no answer grammar | 8.2 | 12.7 | 28.3 | 13.4 | 22.0 | 26.9 | 24.7 | – | – |
| Apertus fine-tuned, no answer grammar | 3.3 | 4.6 | 10.1 | 4.0 | 12.2 | 13.2 | 15.0 | – | – |

## Instructions that must not be applied: flagged, % (the rest was applied silently); and answers outside the format on English instructions, %

| Translator | Two nodes that are not adjacent | Place outside the network | Out of scope | Malformed answers |
|---|---|---|---|---|
| Keyword parser (no model) | 92.9 | 93.3 | 99.1 | 0.0 |
| Apertus as is | 100.0 | 82.7 | 72.8 | 0.0 |
| Apertus, 7 examples in the prompt | 100.0 | 93.6 | 97.4 | 0.0 |
| Apertus fine-tuned | 100.0 | 94.2 | 86.0 | 0.0 |
| Apertus, 7 examples, no answer grammar | 100.0 | 100.0 | 98.2 | 8.6 |
| Apertus fine-tuned, no answer grammar | 100.0 | 97.9 | 93.0 | 3.8 |

## Decisions inside the admissible set on the probe sets (same requests, instruction re-worded), % — rule of SPEC section 3

| Policy | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|---|
| Rule engine given the true instruction (oracle) | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Decider: Apertus fine-tuned | 94.4 | 91.3 | 89.6 | 92.0 | 90.9 | 85.3 | 89.8 | 92.3 |
| Translator: keyword parser | 95.6 | 87.5 | 74.5 | 73.4 | 70.1 | 72.5 | 79.0 | 95.7 |
| Translator: Apertus as is | 90.0 | 92.7 | 88.5 | 89.9 | 88.3 | 81.5 | 89.8 | 90.3 |
| Translator: Apertus, 7 examples | 95.3 | 98.8 | 95.4 | 96.7 | 97.3 | 90.3 | 95.8 | 96.5 |
| Translator: Apertus fine-tuned | 99.1 | 97.5 | 96.6 | 98.4 | 97.5 | 95.3 | 95.5 | 98.9 |

## The same under the ordered reading of two preferences, %

| Policy | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|---|
| Rule engine given the true instruction (oracle) | 97.6 | 97.6 | 97.6 | 97.6 | 97.6 | 98.3 | 98.3 | 96.2 |
| Decider: Apertus fine-tuned | 96.2 | 93.2 | 90.9 | 93.5 | 92.5 | 86.3 | 90.8 | 94.6 |
| Translator: keyword parser | 93.2 | 87.6 | 75.5 | 74.3 | 71.1 | 73.3 | 78.8 | 91.9 |
| Translator: Apertus as is | 89.7 | 92.6 | 87.8 | 89.8 | 88.8 | 81.2 | 90.3 | 90.5 |
| Translator: Apertus, 7 examples | 94.0 | 96.9 | 94.0 | 94.7 | 95.2 | 90.3 | 94.7 | 94.2 |
| Translator: Apertus fine-tuned | 97.8 | 97.4 | 95.8 | 98.1 | 96.7 | 95.3 | 96.0 | 96.8 |

## Instructions that must not be applied: what happens to the request

| Policy | Not adjacent: same decision as without instruction % | Not adjacent: flagged % | Outside the network: same decision as without instruction % | Outside the network: flagged % | Out of scope: same decision as without instruction % | Out of scope: flagged % |
|---|---|---|---|---|---|---|
| Rule engine given the true instruction (oracle) | 100.0 | 0.0 | 100.0 | 0.0 | 100.0 | 0.0 |
| Decider: Apertus fine-tuned | 78.9 | 0.0 | 76.9 | 0.0 | 74.8 | 0.0 |
| Translator: keyword parser | 98.2 | 92.9 | 97.9 | 93.5 | 99.1 | 96.1 |
| Translator: Apertus as is | 100.0 | 100.0 | 96.1 | 83.1 | 89.0 | 73.6 |
| Translator: Apertus, 7 examples | 100.0 | 100.0 | 98.8 | 93.8 | 99.1 | 95.3 |
| Translator: Apertus fine-tuned | 100.0 | 100.0 | 99.4 | 94.4 | 94.7 | 82.2 |

## The decider with and without fine-tuning: decisions on the held-out splits (answer format enforced)

| Decider | New traffic: admissible % | New traffic: invalid % | Unseen wording: admissible % | Unseen wording: invalid % | Unseen pairs: admissible % | Unseen pairs: invalid % |
|---|---|---|---|---|---|---|
| Apertus as is | 3.3 | 96.1 | 2.5 | 97.0 | 4.8 | 94.0 |
| Apertus, 7 solved requests in the prompt | 64.2 | 16.9 | 61.5 | 28.0 | 48.8 | 26.8 |
| Apertus fine-tuned on 12,000 requests | 98.9 | 0.0 | 98.7 | 0.0 | 85.8 | 0.0 |

## Closed loop, Intent violations, % of decisions — load 240 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 13.45 ± 0.74 | 0.00 ± 0.00 |
| Translator: Apertus as is | 2.80 ± 0.23 | 0.00 ± 0.00 | 27.30 ± 2.17 | 0.50 ± 0.13 | 8.12 ± 1.24 | 11.38 ± 0.68 |
| Translator: Apertus, 7 examples | 0.02 ± 0.03 | 0.00 ± 0.00 | 13.03 ± 0.59 | 0.00 ± 0.00 | 3.83 ± 0.68 | 4.67 ± 0.55 |
| Translator: Apertus fine-tuned | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 3.02 ± 0.25 |
| Decider: Apertus fine-tuned | 3.85 ± 0.30 | 0.73 ± 0.10 | 0.50 ± 0.23 | 0.25 ± 0.13 | 0.85 ± 0.05 | 14.17 ± 0.75 |
| Rule engine given the true instruction (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Closed loop, Service blocking probability, % — load 240 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.22 ± 0.31 | 10.32 ± 0.20 |
| Translator: Apertus as is | 6.55 ± 0.56 | 1.78 ± 0.66 | 1.73 ± 0.42 | 2.05 ± 0.59 | 2.62 ± 0.55 | 7.07 ± 0.86 |
| Translator: Apertus, 7 examples | 4.75 ± 0.87 | 1.78 ± 0.66 | 1.68 ± 0.65 | 2.28 ± 0.84 | 2.57 ± 0.45 | 9.03 ± 0.29 |
| Translator: Apertus fine-tuned | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.52 ± 0.54 | 8.85 ± 0.43 |
| Decider: Apertus fine-tuned | 5.00 ± 0.66 | 2.18 ± 0.64 | 1.30 ± 0.15 | 2.27 ± 0.86 | 2.53 ± 0.55 | 3.43 ± 0.51 |
| Rule engine given the true instruction (oracle) | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.52 ± 0.54 | 10.32 ± 0.20 |

## Closed loop, a translator's violations: instruction applied with a wrong meaning (silent) / instruction flagged and not applied (visible), % of decisions — load 240 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 13.45 | 0.00 / 0.00 |
| Translator: Apertus as is | 2.18 / 0.62 | 0.00 / 0.00 | 27.30 / 0.00 | 0.00 / 0.50 | 7.98 / 0.13 | 10.67 / 0.72 |
| Translator: Apertus, 7 examples | 0.00 / 0.02 | 0.00 / 0.00 | 13.03 / 0.00 | 0.00 / 0.00 | 3.80 / 0.03 | 4.67 / 0.00 |
| Translator: Apertus fine-tuned | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 3.02 / 0.00 |

## Closed loop, Intent violations, % of decisions — load 390 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 11.33 ± 0.53 | 0.00 ± 0.00 |
| Translator: Apertus as is | 2.17 ± 0.25 | 0.00 ± 0.00 | 22.53 ± 1.54 | 0.37 ± 0.08 | 7.17 ± 1.03 | 10.42 ± 0.41 |
| Translator: Apertus, 7 examples | 0.03 ± 0.03 | 0.00 ± 0.00 | 10.58 ± 1.63 | 0.00 ± 0.00 | 3.50 ± 0.40 | 4.17 ± 0.78 |
| Translator: Apertus fine-tuned | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 2.77 ± 0.43 |
| Decider: Apertus fine-tuned | 3.27 ± 0.21 | 0.63 ± 0.20 | 0.67 ± 0.13 | 0.13 ± 0.03 | 1.03 ± 0.10 | 12.88 ± 0.68 |
| Rule engine given the true instruction (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Closed loop, Service blocking probability, % — load 390 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.12 ± 0.80 | 13.45 ± 0.56 |
| Translator: Apertus as is | 10.97 ± 0.86 | 7.05 ± 0.79 | 7.07 ± 0.65 | 7.30 ± 0.48 | 8.00 ± 0.78 | 10.72 ± 0.72 |
| Translator: Apertus, 7 examples | 10.03 ± 0.83 | 7.05 ± 0.79 | 6.68 ± 0.63 | 7.53 ± 0.73 | 7.72 ± 0.48 | 12.45 ± 0.30 |
| Translator: Apertus fine-tuned | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.73 ± 0.58 | 12.22 ± 1.01 |
| Decider: Apertus fine-tuned | 10.23 ± 0.85 | 7.40 ± 0.78 | 6.25 ± 1.13 | 7.52 ± 0.78 | 7.67 ± 0.83 | 8.72 ± 1.10 |
| Rule engine given the true instruction (oracle) | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.73 ± 0.58 | 13.45 ± 0.56 |

## Closed loop, a translator's violations: instruction applied with a wrong meaning (silent) / instruction flagged and not applied (visible), % of decisions — load 390 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 11.33 | 0.00 / 0.00 |
| Translator: Apertus as is | 1.38 / 0.78 | 0.00 / 0.00 | 22.53 / 0.00 | 0.00 / 0.37 | 7.00 / 0.17 | 9.58 / 0.83 |
| Translator: Apertus, 7 examples | 0.00 / 0.03 | 0.00 / 0.00 | 10.58 / 0.00 | 0.00 / 0.00 | 3.50 / 0.00 | 4.15 / 0.02 |
| Translator: Apertus fine-tuned | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 2.77 / 0.00 |
