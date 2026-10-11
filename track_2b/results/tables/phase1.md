# Phase 1: translate versus decide

Rendered by `src/report_phase1.py` from `results/translate/`, `results/offline/` and `results/eval/`; do not edit by hand. A translator turns the instruction into constraints and preferences once and the rule engine decides; a decider reads the instruction with every request. Test sets: `src/corpora.py`.

## Instructions translated with the right meaning, % — distinct instructions per set: Dataset wording 819, Independent wording 827, German 653, French 656, Italian 656, Swiss German 242, Misspelt 320, Closed-loop instructions 8505, Other topology 528

| Translator | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Closed-loop instructions | Other topology |
|---|---|---|---|---|---|---|---|---|---|
| Keyword parser (no model) | 99.1 | 42.3 | 8.3 | 9.0 | 0.5 | 7.9 | 10.6 | 99.9 | 98.7 |

## Instructions applied with a wrong meaning (silent), %

| Translator | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Closed-loop instructions | Other topology |
|---|---|---|---|---|---|---|---|---|---|
| Keyword parser (no model) | 0.0 | 39.8 | 18.4 | 21.2 | 0.6 | 19.8 | 37.2 | 0.0 | 0.0 |

## Valid instructions the translator refused (visible), %

| Translator | Dataset wording | Independent wording | German | French | Italian | Swiss German | Misspelt | Closed-loop instructions | Other topology |
|---|---|---|---|---|---|---|---|---|---|
| Keyword parser (no model) | 0.9 | 17.9 | 73.4 | 69.8 | 98.9 | 72.3 | 52.2 | 0.1 | 1.3 |

## Instructions that must not be applied: flagged, % (the rest was applied silently); and answers outside the format on English instructions, %

| Translator | Two nodes that are not adjacent | Place outside the network | Out of scope | Malformed answers |
|---|---|---|---|---|
| Keyword parser (no model) | 92.9 | 93.3 | 99.1 | 0.0 |

## Decisions inside the admissible set on the probe sets (same requests, instruction re-worded), % — rule of SPEC section 3

| Policy | Independent wording | German | French | Italian | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|
| Rule engine given the true instruction (oracle) | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Translator: keyword parser | 87.5 | 74.5 | 73.4 | 70.1 | 72.5 | 79.0 | 95.7 |

## The same under the ordered reading of two preferences, %

| Policy | Independent wording | German | French | Italian | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|
| Rule engine given the true instruction (oracle) | 97.6 | 97.6 | 97.6 | 97.6 | 98.3 | 98.3 | 96.2 |
| Translator: keyword parser | 87.6 | 75.5 | 74.3 | 71.1 | 73.3 | 78.8 | 91.9 |

## Instructions that must not be applied: what happens to the request

| Policy | Not adjacent: same decision as without instruction % | Not adjacent: flagged % | Outside the network: same decision as without instruction % | Outside the network: flagged % | Out of scope: same decision as without instruction % | Out of scope: flagged % |
|---|---|---|---|---|---|---|
| Rule engine given the true instruction (oracle) | 100.0 | 0.0 | 100.0 | 0.0 | 100.0 | 0.0 |
| Translator: keyword parser | 98.2 | 92.9 | 97.9 | 93.5 | 99.1 | 96.1 |

## Closed loop, Intent violations, % of decisions — load 240 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 13.45 ± 0.74 | 0.00 ± 0.00 |
| Decider: Apertus fine-tuned | 3.85 ± 0.30 | 0.73 ± 0.10 | 0.50 ± 0.23 | 0.25 ± 0.13 | 0.85 ± 0.05 | 14.17 ± 0.75 |
| Rule engine given the true instruction (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Closed loop, Service blocking probability, % — load 240 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.22 ± 0.31 | 10.32 ± 0.20 |
| Decider: Apertus fine-tuned | 5.00 ± 0.66 | 2.18 ± 0.64 | 1.30 ± 0.15 | 2.27 ± 0.86 | 2.53 ± 0.55 | 3.43 ± 0.51 |
| Rule engine given the true instruction (oracle) | 4.78 ± 0.90 | 1.78 ± 0.66 | 1.38 ± 0.18 | 2.28 ± 0.84 | 2.52 ± 0.54 | 10.32 ± 0.20 |

## Closed loop, Intent violations, % of decisions — load 390 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 11.33 ± 0.53 | 0.00 ± 0.00 |
| Decider: Apertus fine-tuned | 3.27 ± 0.21 | 0.63 ± 0.20 | 0.67 ± 0.13 | 0.13 ± 0.03 | 1.03 ± 0.10 | 12.88 ± 0.68 |
| Rule engine given the true instruction (oracle) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Closed loop, Service blocking probability, % — load 390 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
|---|---|---|---|---|---|---|
| Translator: keyword parser | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.12 ± 0.80 | 13.45 ± 0.56 |
| Decider: Apertus fine-tuned | 10.23 ± 0.85 | 7.40 ± 0.78 | 6.25 ± 1.13 | 7.52 ± 0.78 | 7.67 ± 0.83 | 8.72 ± 1.10 |
| Rule engine given the true instruction (oracle) | 9.95 ± 0.75 | 7.05 ± 0.79 | 6.30 ± 0.80 | 7.53 ± 0.73 | 7.73 ± 0.58 | 13.45 ± 0.56 |
