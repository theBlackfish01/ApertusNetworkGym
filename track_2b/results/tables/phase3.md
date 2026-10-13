# Third round: a policy language, two readers, and a guarded fallback

Rendered by `src/report_phase3.py`; do not edit by hand. The third format of the translator is a line of slots (links and nodes to avoid, a node to pass through, limits on hops and length, a candidate by its number, ordered preferences, and a marker for a part the slots cannot carry). Two readers were fine-tuned with different seeds and training samples. Test wording: `data/instructions/v3_source_*.json`, written by separate AI instances that never saw the repository. Which combinations of clauses are trained and which are held out was fixed before those sources were opened (`src/corpora3.py`). Preferences are read in the order stated (constraints, then objectives); a request is selected for an instruction by a condition on the instruction and the request only (`src/corpora3_tests.py`), and instruction-blind baselines are shown on the same requests.

## The policy language: instructions translated with the right meaning, % of distinct instructions, four languages together

| Reader | One clause | Pair seen in training | Pair never seen together | Three clauses, never seen together | Two preferences | All | Applied with a wrong meaning | Instructions |
|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 15 examples, no training | 89.5 | 81.0 | 91.1 | 85.6 | 90.6 | 87.2 | 9.6 | 2078 |
| Apertus 70B (first generation), 15 examples, no training | 77.3 | 71.7 | 65.0 | 67.8 | 75.0 | 71.9 | 6.3 | 2078 |
| Apertus 70B (generation 1.5), 15 examples, no training | 92.8 | 87.6 | 85.7 | 86.6 | 93.8 | 89.2 | 7.6 | 2078 |
| Apertus 8B fine-tuned (reader 1) | 94.6 | 95.6 | 96.5 | 91.2 | 96.9 | 94.8 | 4.6 | 2078 |
| Apertus 8B fine-tuned (reader 2) | 93.4 | 93.6 | 94.9 | 90.9 | 87.5 | 93.3 | 5.9 | 2078 |
| Reader 1 on the laptop (4-bit GGUF, llama.cpp) | 96.6 | 96.4 | 90.2 | 83.8 | 84.4 | 93.1 | 6.5 | 2078 |
| Apertus 8B fine-tuned, fourth format (scope and lifetime) | 97.1 | 95.6 | 93.7 | 91.2 | 96.9 | 95.1 | 4.4 | 2078 |

## The same by language: all instructions, and the combinations never seen together

| Reader | English: all | English: never seen together | German: all | German: never seen together | French: all | French: never seen together | Italian: all | Italian: never seen together |
|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 15 examples, no training | 94.6 | 97.3 | 82.7 | 82.8 | 88.5 | 88.8 | 82.9 | 86.2 |
| Apertus 70B (first generation), 15 examples, no training | 77.7 | 72.7 | 73.0 | 68.8 | 72.5 | 65.2 | 64.4 | 58.0 |
| Apertus 70B (generation 1.5), 15 examples, no training | 93.5 | 90.4 | 84.8 | 84.4 | 91.6 | 86.6 | 86.7 | 83.0 |
| Apertus 8B fine-tuned (reader 1) | 96.7 | 97.3 | 91.4 | 88.7 | 96.0 | 97.3 | 94.8 | 93.6 |
| Apertus 8B fine-tuned (reader 2) | 96.2 | 96.3 | 89.5 | 88.2 | 94.5 | 95.2 | 92.9 | 93.1 |
| Reader 1 on the laptop (4-bit GGUF, llama.cpp) | 93.7 | 88.2 | 90.5 | 82.3 | 96.2 | 92.5 | 91.9 | 86.7 |
| Apertus 8B fine-tuned, fourth format (scope and lifetime) | 96.7 | 93.6 | 93.2 | 91.4 | 96.0 | 95.7 | 94.6 | 89.9 |

## The test sets of the earlier rounds (not trained on by any translator): right meaning, %

| Translator | Independent wording | German, native | French, native | Italian, native | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|
| First translator, fine-tuned | 88.5 | – | – | – | 76.0 | 76.6 | 92.6 |
| Second translator, fine-tuned | 95.0 | 96.6 | 94.5 | 98.0 | 76.9 | 86.9 | 98.3 |
| Apertus 8B, 15 examples, no training | – | – | – | – | – | – | – |
| Apertus 70B (first generation), 15 examples, no training | – | – | – | – | – | – | – |
| Apertus 70B (generation 1.5), 15 examples, no training | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned (reader 1) | 96.0 | 93.3 | 98.9 | 94.5 | 72.7 | 85.9 | 97.3 |
| Apertus 8B fine-tuned (reader 2) | 94.3 | 92.5 | 96.9 | 90.7 | – | 83.3 | – |
| Reader 1 on the laptop (4-bit GGUF, llama.cpp) | – | – | – | – | – | – | – |
| Apertus 8B fine-tuned, fourth format (scope and lifetime) | – | – | – | – | – | – | – |

## The gate: what a reader does with instructions that are not, or not wholly, in the format, % of distinct instructions

| Reader | New type: handed to the decider (right) | New type: dropped | New type: applied as something else (silent) | Part carried: part and marker right | Part carried: all handed on | Part carried: part right, rest dropped silently | Part carried: other | Other routing instruction: handed on (right) | No instruction: dropped (right) | No instruction: applied (silent) | Place outside the network: flagged (right) | Place outside the network: applied (silent) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 15 examples, no training | 43.9 | 8.3 | 47.8 | 30.7 | 2.4 | 8.5 | 58.5 | 18.8 | 100.0 | 0.0 | 64.7 | 33.3 |
| Apertus 70B (first generation), 15 examples, no training | 65.6 | 7.5 | 26.9 | 30.7 | 21.7 | 4.7 | 42.9 | 56.2 | 96.7 | 0.0 | 57.3 | 11.3 |
| Apertus 70B (generation 1.5), 15 examples, no training | 65.2 | 28.1 | 6.7 | 15.6 | 24.1 | 17.5 | 42.9 | 18.8 | 100.0 | 0.0 | 63.3 | 11.3 |
| Apertus 8B fine-tuned (reader 1) | 51.0 | 2.4 | 46.6 | 27.4 | 0.0 | 31.1 | 41.5 | 18.8 | 96.7 | 3.3 | 77.3 | 20.0 |
| Apertus 8B fine-tuned (reader 2) | 54.9 | 1.2 | 43.9 | 24.1 | 0.0 | 13.7 | 62.3 | 50.0 | 96.7 | 3.3 | 78.0 | 19.3 |
| Reader 1 on the laptop (4-bit GGUF, llama.cpp) | 54.9 | 0.0 | 45.1 | 29.7 | 0.0 | 54.2 | 16.0 | 50.0 | 96.7 | 3.3 | 88.0 | 10.0 |
| Apertus 8B fine-tuned, fourth format (scope and lifetime) | 81.8 | 1.2 | 17.0 | 47.6 | 0.0 | 24.1 | 28.3 | 50.0 | 96.7 | 3.3 | 79.3 | 19.3 |

## Two readers: the operator is asked when their readings differ. % of distinct instructions

| First reader / second reader | Instructions | n | Not right, first reader alone | Not right and not asked | Applied wrongly, first reader alone | Applied wrongly and not asked | Asked | Asked although right |
|---|---|---|---|---|---|---|---|---|
| Apertus 8B fine-tuned (reader 1) / Apertus 8B fine-tuned (reader 2) | The policy language, four languages | 2078 | 5.2 | 4.3 | 4.6 | 3.7 | 2.8 | 1.9 |
| Apertus 8B fine-tuned (reader 1) / Apertus 8B fine-tuned (reader 2) | Carried in part | 212 | 72.6 | 36.3 | 72.2 | 36.3 | 50.9 | 14.6 |
| Apertus 8B fine-tuned (reader 1) / Apertus 8B fine-tuned (reader 2) | New types | 253 | 49.0 | 17.4 | 46.6 | 16.2 | 31.6 | 0.0 |
| Apertus 8B fine-tuned (reader 1) / Apertus 8B fine-tuned (reader 2) | Earlier sets (independent, native German, French, Italian) | 2935 | 4.3 | 3.4 | 3.4 | 2.6 | 3.7 | 2.8 |
| Apertus 8B fine-tuned (reader 1) / Apertus 8B fine-tuned (reader 2) | Instructions of the closed loop | 4599 | 13.5 | 7.5 | 12.7 | 7.0 | 8.6 | 2.6 |
| Apertus 8B fine-tuned (reader 1) / Apertus 8B, 15 examples, no training | The policy language, four languages | 2078 | 5.2 | 2.0 | 4.6 | 1.5 | 12.7 | 9.5 |
| Apertus 8B fine-tuned (reader 1) / Apertus 8B, 15 examples, no training | Carried in part | 212 | 72.6 | 33.5 | 72.2 | 33.0 | 54.2 | 15.1 |
| Apertus 8B fine-tuned (reader 1) / Apertus 8B, 15 examples, no training | New types | 253 | 49.0 | 20.6 | 46.6 | 19.4 | 44.7 | 16.2 |
| Apertus 8B fine-tuned (reader 1) / Apertus 70B (first generation), 15 examples, no training | The policy language, four languages | 2078 | 5.2 | 0.4 | 4.6 | 0.2 | 30.3 | 25.5 |
| Apertus 8B fine-tuned (reader 1) / Apertus 70B (first generation), 15 examples, no training | Carried in part | 212 | 72.6 | 17.0 | 72.2 | 17.0 | 72.6 | 17.0 |
| Apertus 8B fine-tuned (reader 1) / Apertus 70B (first generation), 15 examples, no training | New types | 253 | 49.0 | 17.8 | 46.6 | 17.8 | 44.3 | 13.0 |
| Apertus 8B fine-tuned (reader 1) / Apertus 70B (generation 1.5), 15 examples, no training | The policy language, four languages | 2078 | 5.2 | 0.5 | 4.6 | 0.2 | 13.4 | 8.7 |
| Apertus 8B fine-tuned (reader 1) / Apertus 70B (generation 1.5), 15 examples, no training | Carried in part | 212 | 72.6 | 33.0 | 72.2 | 33.0 | 53.3 | 13.7 |
| Apertus 8B fine-tuned (reader 1) / Apertus 70B (generation 1.5), 15 examples, no training | New types | 253 | 49.0 | 1.2 | 46.6 | 0.0 | 69.2 | 21.3 |

## On the laptop (RTX 4060, 8 GB; llama.cpp, 4-bit base model, adapters switched per request): seconds per answer

| Model | Answers | Median | Mean | 95th percentile |
|---|---|---|---|---|
| Reader 1 | 8598 | 0.89 | 0.98 | 1.71 |
| Reader 2 | 8098 | 0.82 | 0.87 | 1.19 |
| Decider | 134 | 0.97 | 0.97 | 1.20 |
| Reader of the fourth format | 2 | 4.87 | 3.72 | 4.87 |

## New types, on requests where the instruction is restrictive: decisions that comply, %

| Policy | Largest free block (200) | Not the first candidate (200) | A minimum of free slots (200) | A modulation threshold (200) | All |
|---|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 25.5 | 0.0 | 77.0 | 100.0 | 50.6 |
| Decision without an instruction (ignores it) | 18.0 | 43.0 | 85.0 | 86.5 | 58.1 |
| Decider alone | 30.0 | 88.0 | 99.0 | 98.0 | 78.8 |
| Translator alone (reader 1) | 28.5 | 53.5 | 79.5 | 88.5 | 62.5 |
| Hybrid without the guard | 30.0 | 72.5 | 90.5 | 97.5 | 72.6 |
| Hybrid | 30.0 | 72.5 | 90.5 | 97.5 | 72.6 |

## New types, on requests where neither instruction-blind choice complies: decisions that comply, %

| Policy | Largest free block (100) | Not the first candidate (100) | A minimum of free slots (100) | A modulation threshold (2) | All |
|---|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Decision without an instruction (ignores it) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Decider alone | 11.0 | 75.0 | 98.0 | 100.0 | 61.6 |
| Translator alone (reader 1) | 6.0 | 13.0 | 0.0 | 0.0 | 6.3 |
| Hybrid without the guard | 11.0 | 51.0 | 61.0 | 100.0 | 41.4 |
| Hybrid | 11.0 | 51.0 | 61.0 | 100.0 | 41.4 |

## A new constraint that no path meets (reject is right), and instructions carried in part: decisions that comply, %

| Policy | Cannot be met: rejected | Carried in part: complies | Carried in part: sent to the decider | Carried in part: guard replaced the choice |
|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 21.2 | 43.8 | 0.0 | 0.0 |
| Decision without an instruction (ignores it) | 21.2 | 44.5 | 0.0 | 0.0 |
| Decider alone | 49.5 | 67.2 | 0.0 | 0.0 |
| Translator alone (reader 1) | 21.7 | 68.0 | 0.0 | 0.0 |
| Hybrid without the guard | 42.4 | 63.5 | 35.5 | 0.0 |
| Hybrid | 42.4 | 70.5 | 35.5 | 7.2 |

## The policy language on stored requests: decisions that comply, %

| Policy | English: one clause | English: pair seen in training | English: pair never seen together | English: three clauses, never seen together | English: two preferences | English: all | German | French | Italian |
|---|---|---|---|---|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 70.6 | 63.3 | 62.5 | 57.5 | 81.2 | 66.8 | 68.5 | 66.8 | 66.7 |
| Decision without an instruction (ignores it) | 61.9 | 66.4 | 52.7 | 46.2 | 75.0 | 60.0 | 58.2 | 55.7 | 56.2 |
| Decider alone | 96.2 | 90.6 | 85.7 | 76.2 | 96.9 | 91.1 | – | – | – |
| Translator alone (reader 1) | 99.4 | 100.0 | 99.1 | 100.0 | 100.0 | 99.6 | 97.9 | 99.1 | 99.3 |
| Hybrid without the guard | 99.4 | 100.0 | 99.1 | 100.0 | 100.0 | 99.6 | – | – | – |
| Hybrid | 99.4 | 100.0 | 99.1 | 100.0 | 100.0 | 99.6 | – | – | – |

## The mixed stream of the third round in closed loop: violations, % of the requests of each kind — load 240 E

| Policy | In the format | Combinations never seen | New types | Carried in part | No instruction | Place outside the network | All requests | Blocking, % | Sent to the decider, % | Guard replaced the choice, % | Operator asked, % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 8.15 | 0.0 | 0.0 | 0.0 |
| First fit (ignores the instruction) | 36.0 | 50.2 | 45.6 | 58.5 | 0.0 | 0.0 | 28.9 | 2.68 | 0.0 | 0.0 | 0.0 |
| No-intent teacher (ignores the instruction) | 44.0 | 58.5 | 38.7 | 59.2 | 0.0 | 0.0 | 31.5 | 1.22 | 0.0 | 0.0 | 0.0 |
| Decider alone | 19.0 | 35.4 | 24.3 | 39.2 | 2.3 | 0.3 | 16.4 | 2.68 | 0.0 | 0.0 | 0.0 |
| Translator alone (reader 1) | 1.2 | 2.4 | 35.6 | 42.7 | 0.0 | 6.1 | 10.5 | 6.03 | 0.0 | 0.0 | 0.0 |
| Translator that asks when its two readers disagree | 0.8 | 1.5 | 35.6 | 40.6 | 0.0 | 5.1 | 10.1 | 6.13 | 0.0 | 0.0 | 9.5 |
| Translator that asks only when a request tells the readings apart | 0.9 | 1.7 | 35.7 | 41.1 | 0.0 | 5.1 | 10.2 | 5.97 | 0.0 | 0.0 | 8.1 |
| Hybrid | 1.1 | 1.9 | 27.3 | 37.1 | 0.0 | 6.1 | 8.7 | 6.47 | 11.6 | 0.9 | 0.0 |
| Hybrid that asks when its two readers disagree | 0.8 | 1.5 | 28.7 | 32.4 | 0.0 | 5.1 | 8.2 | 6.60 | 17.2 | 1.1 | 9.5 |

## The same, only requests on which the instruction changes the right answer — load 240 E

| Policy | In the format: violations, % | Combinations never seen: violations, % | New types: violations, % | Carried in part: violations, % | In the format: such requests | Combinations never seen: such requests | New types: such requests | Carried in part: such requests |
|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 1182 | 469 | 349 | 361 |
| First fit (ignores the instruction) | 64.2 | 73.9 | 85.0 | 80.9 | 1201 | 486 | 306 | 356 |
| No-intent teacher (ignores the instruction) | 99.7 | 100.0 | 100.0 | 100.0 | 1185 | 491 | 341 | 367 |
| Decider alone | 40.3 | 60.1 | 54.7 | 59.6 | 1201 | 476 | 362 | 364 |
| Translator alone (reader 1) | 2.1 | 3.6 | 91.9 | 65.1 | 1216 | 497 | 321 | 378 |
| Translator that asks when its two readers disagree | 1.6 | 2.5 | 91.3 | 64.9 | 1182 | 477 | 335 | 356 |
| Translator that asks only when a request tells the readings apart | 1.8 | 2.9 | 91.9 | 62.3 | 1162 | 476 | 334 | 374 |
| Hybrid | 2.1 | 3.1 | 62.0 | 57.2 | 1221 | 490 | 353 | 369 |
| Hybrid that asks when its two readers disagree | 1.6 | 2.5 | 65.5 | 49.9 | 1206 | 488 | 348 | 361 |

## All requests, violations in % per seed — load 240 E

| Policy | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| Rules for every kind (reference) | 0.00 | 0.00 | 0.00 |
| First fit (ignores the instruction) | 31.05 | 29.10 | 26.50 |
| No-intent teacher (ignores the instruction) | 32.85 | 31.85 | 29.80 |
| Decider alone | 17.40 | 16.95 | 14.85 |
| Translator alone (reader 1) | 10.60 | 11.60 | 9.30 |
| Translator that asks when its two readers disagree | 10.70 | 10.40 | 9.10 |
| Translator that asks only when a request tells the readings apart | 10.40 | 10.50 | 9.55 |
| Hybrid | 8.90 | 9.10 | 8.00 |
| Hybrid that asks when its two readers disagree | 8.85 | 8.15 | 7.60 |

## The mixed stream of the third round in closed loop: violations, % of the requests of each kind — load 390 E

| Policy | In the format | Combinations never seen | New types | Carried in part | No instruction | Place outside the network | All requests | Blocking, % | Sent to the decider, % | Guard replaced the choice, % | Operator asked, % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 14.58 | 0.0 | 0.0 | 0.0 |
| First fit (ignores the instruction) | 35.3 | 48.6 | 47.6 | 55.3 | 0.0 | 0.0 | 28.6 | 8.23 | 0.0 | 0.0 | 0.0 |
| No-intent teacher (ignores the instruction) | 42.8 | 54.1 | 42.5 | 55.4 | 0.0 | 0.0 | 31.2 | 5.98 | 0.0 | 0.0 | 0.0 |
| Decider alone | 19.2 | 34.8 | 27.9 | 36.3 | 3.1 | 0.4 | 16.8 | 8.27 | 0.0 | 0.0 | 0.0 |
| Translator alone (reader 1) | 0.9 | 1.5 | 36.7 | 43.6 | 0.0 | 6.7 | 10.6 | 11.73 | 0.0 | 0.0 | 0.0 |
| Translator that asks when its two readers disagree | 0.8 | 1.3 | 35.8 | 42.4 | 0.0 | 6.3 | 10.3 | 11.73 | 0.0 | 0.0 | 8.9 |
| Translator that asks only when a request tells the readings apart | 0.8 | 1.3 | 35.6 | 42.4 | 0.0 | 6.3 | 10.2 | 11.78 | 0.0 | 0.0 | 7.8 |
| Hybrid | 1.0 | 1.6 | 31.6 | 40.4 | 0.0 | 6.7 | 9.5 | 12.12 | 11.5 | 0.7 | 0.0 |
| Hybrid that asks when its two readers disagree | 0.8 | 1.4 | 28.9 | 34.7 | 0.0 | 6.3 | 8.5 | 12.25 | 17.3 | 1.0 | 8.9 |
| Hybrid that asks, the untrained Apertus 70B as second reader | 0.3 | 0.5 | 28.3 | 37.0 | 0.0 | 3.7 | 8.3 | 12.03 | 21.2 | 0.9 | 24.1 |
| Hybrid that asks, all three models on the laptop (4-bit) | 1.2 | 3.3 | 31.1 | 38.4 | 0.0 | 2.6 | 9.2 | 11.98 | 15.4 | 0.6 | 9.6 |
| Hybrid that asks only when a request tells the readings apart, on the laptop | 1.2 | 3.4 | 32.0 | 40.0 | 0.0 | 3.3 | 9.5 | 11.65 | 14.2 | 0.6 | 7.4 |

## The same, only requests on which the instruction changes the right answer — load 390 E

| Policy | In the format: violations, % | Combinations never seen: violations, % | New types: violations, % | Carried in part: violations, % | In the format: such requests | Combinations never seen: such requests | New types: such requests | Carried in part: such requests |
|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 1152 | 464 | 366 | 352 |
| First fit (ignores the instruction) | 67.2 | 76.9 | 92.3 | 78.7 | 1122 | 459 | 337 | 305 |
| No-intent teacher (ignores the instruction) | 100.0 | 100.0 | 100.0 | 100.0 | 1156 | 463 | 386 | 331 |
| Decider alone | 42.6 | 60.3 | 57.6 | 58.7 | 1143 | 469 | 394 | 339 |
| Translator alone (reader 1) | 2.1 | 2.6 | 88.5 | 67.8 | 1155 | 453 | 365 | 338 |
| Translator that asks when its two readers disagree | 1.7 | 2.1 | 89.1 | 64.6 | 1181 | 479 | 357 | 345 |
| Translator that asks only when a request tells the readings apart | 1.7 | 2.1 | 89.2 | 65.6 | 1185 | 481 | 353 | 337 |
| Hybrid | 2.0 | 2.3 | 68.7 | 63.5 | 1169 | 476 | 383 | 348 |
| Hybrid that asks when its two readers disagree | 1.8 | 2.3 | 65.3 | 55.5 | 1138 | 472 | 360 | 344 |
| Hybrid that asks, the untrained Apertus 70B as second reader | 0.7 | 0.9 | 60.2 | 58.9 | 1163 | 470 | 377 | 341 |
| Hybrid that asks, all three models on the laptop (4-bit) | 2.1 | 4.7 | 70.4 | 59.4 | 1179 | 472 | 379 | 352 |
| Hybrid that asks only when a request tells the readings apart, on the laptop | 2.0 | 4.5 | 71.1 | 61.0 | 1172 | 486 | 391 | 351 |

## All requests, violations in % per seed — load 390 E

| Policy | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| Rules for every kind (reference) | 0.00 | 0.00 | 0.00 |
| First fit (ignores the instruction) | 28.00 | 30.05 | 27.85 |
| No-intent teacher (ignores the instruction) | 30.70 | 31.85 | 31.15 |
| Decider alone | 16.45 | 16.90 | 17.15 |
| Translator alone (reader 1) | 9.95 | 11.20 | 10.65 |
| Translator that asks when its two readers disagree | 10.15 | 10.60 | 10.10 |
| Translator that asks only when a request tells the readings apart | 10.15 | 10.60 | 10.00 |
| Hybrid | 8.50 | 10.25 | 9.85 |
| Hybrid that asks when its two readers disagree | 7.95 | 8.95 | 8.50 |
| Hybrid that asks, the untrained Apertus 70B as second reader | 7.95 | 8.60 | 8.25 |
| Hybrid that asks, all three models on the laptop (4-bit) | 8.80 | 9.40 | 9.35 |
| Hybrid that asks only when a request tells the readings apart, on the laptop | 9.25 | 9.75 | 9.60 |

## Standing policies in closed loop (policies arrive, hold for the hours they state or until withdrawn, and cover the requests their scope names): violations against the true table, % — load 240 E

| Policy | Violations, % of requests | Where a policy changes the right answer, % | Rejected, % | Blocking, % | Policies the reader dropped | Per seed |
|---|---|---|---|---|---|---|
| The true policy table (reference) | 0.0 | 0.0 | 31.4 | 31.35 | 0 | 0.0 / 0.0 / 0.0 |
| First fit (ignores the policies) | 42.0 | 77.6 | 2.7 | 2.68 | – | 41.9 / 40.6 / 43.4 |
| No-intent teacher (ignores the policies) | 47.9 | 100.0 | 1.2 | 1.22 | – | 47.1 / 49.5 / 46.9 |
| True policies, scope ignored (every policy covers every request) | 12.7 | 8.9 | 43.5 | 43.55 | 0 | 7.2 / 17.0 / 13.7 |
| True policies, lifetime ignored (no policy ever expires) | 11.9 | 8.8 | 42.7 | 42.73 | 0 | 3.9 / 13.4 / 18.4 |
| Policies read by the fourth-format reader | 1.1 | 2.1 | 30.7 | 30.67 | 0 | 0.9 / 0.0 / 2.4 |

## Standing policies in closed loop (policies arrive, hold for the hours they state or until withdrawn, and cover the requests their scope names): violations against the true table, % — load 390 E

| Policy | Violations, % of requests | Where a policy changes the right answer, % | Rejected, % | Blocking, % | Policies the reader dropped | Per seed |
|---|---|---|---|---|---|---|
| The true policy table (reference) | 0.0 | 0.0 | 34.7 | 34.73 | 0 | 0.0 / 0.0 / 0.1 |
| First fit (ignores the policies) | 38.1 | 75.2 | 8.2 | 8.23 | – | 38.6 / 43.2 / 32.6 |
| No-intent teacher (ignores the policies) | 45.6 | 99.9 | 6.0 | 5.98 | – | 50.9 / 51.9 / 33.9 |
| True policies, scope ignored (every policy covers every request) | 30.0 | 17.1 | 61.4 | 61.37 | 0 | 54.4 / 0.0 / 35.5 |
| True policies, lifetime ignored (no policy ever expires) | 6.4 | 5.3 | 39.8 | 39.80 | 0 | 6.0 / 7.6 / 5.5 |
| Policies read by the fourth-format reader | 1.5 | 2.4 | 34.2 | 34.18 | 0 | 0.0 / 4.4 / 0.1 |

## The policy language on a Swiss network (24 cities named in each language's own form, never in training): right meaning, % of instructions

| Reader | Language | n | Right | Applied with another meaning | Not applied | One clause | Pair seen in training | Pair never seen together | Three clauses, never seen together | Two preferences |
|---|---|---|---|---|---|---|---|---|---|---|
| Reader 1 on the laptop | English | 287 | 90.6 | 9.1 | 0.3 | 95.9 | 95.3 | 86.5 | 72.5 | 87.5 |
| Reader 1 on the laptop | German | 288 | 92.0 | 6.9 | 1.0 | 96.7 | 93.7 | 85.2 | 85.0 | 87.5 |
| Reader 1 on the laptop | French | 293 | 90.8 | 7.2 | 2.0 | 94.4 | 93.8 | 92.9 | 70.0 | 100.0 |
| Reader 1 on the laptop | Italian | 283 | 89.0 | 8.8 | 2.1 | 92.4 | 93.8 | 88.5 | 75.0 | 75.0 |
| Reader 2 on the laptop | English | 287 | 90.6 | 9.1 | 0.3 | 94.3 | 95.3 | 84.6 | 80.0 | 87.5 |
| Reader 2 on the laptop | German | 288 | 90.6 | 9.0 | 0.3 | 91.9 | 95.2 | 87.0 | 82.5 | 100.0 |
| Reader 2 on the laptop | French | 293 | 86.0 | 12.3 | 1.7 | 89.6 | 90.6 | 85.7 | 65.0 | 100.0 |
| Reader 2 on the laptop | Italian | 283 | 86.6 | 12.0 | 1.4 | 84.9 | 90.6 | 94.2 | 75.0 | 87.5 |

## The mixed stream of the third round in closed loop on the Swiss network: violations, % of the requests of each kind — load 600 E

| Policy | In the format | Combinations never seen | New types | Carried in part | No instruction | Place outside the network | All requests | Blocking, % | Sent to the decider, % | Guard replaced the choice, % | Operator asked, % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 24.57 | 0.0 | 0.0 | 0.0 |
| First fit (ignores the instruction) | 30.4 | 45.2 | 37.3 | 49.9 | 0.0 | 0.0 | 24.7 | 17.83 | 0.0 | 0.0 | 0.0 |
| No-intent teacher (ignores the instruction) | 35.5 | 49.1 | 33.5 | 46.9 | 0.0 | 0.0 | 26.1 | 17.08 | 0.0 | 0.0 | 0.0 |
| Translator alone (reader 1 on the laptop) | 2.2 | 5.5 | 30.9 | 37.1 | 0.0 | 4.9 | 9.8 | 22.32 | 0.0 | 0.0 | 0.0 |
| Translator that asks when its two readers disagree | 1.2 | 2.7 | 31.1 | 33.2 | 0.0 | 5.2 | 9.0 | 22.45 | 0.0 | 0.0 | 12.6 |
| Translator that asks only when a request tells the readings apart | 1.4 | 3.5 | 30.9 | 35.3 | 0.0 | 4.9 | 9.3 | 22.15 | 0.0 | 0.0 | 8.0 |

## The same, only requests on which the instruction changes the right answer — load 600 E

| Policy | In the format: violations, % | Combinations never seen: violations, % | New types: violations, % | Carried in part: violations, % | In the format: such requests | Combinations never seen: such requests | New types: such requests | Carried in part: such requests |
|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 1047 | 467 | 298 | 332 |
| First fit (ignores the instruction) | 71.8 | 81.9 | 92.1 | 87.8 | 970 | 437 | 265 | 279 |
| No-intent teacher (ignores the instruction) | 100.0 | 100.0 | 100.0 | 100.0 | 959 | 425 | 296 | 308 |
| Translator alone (reader 1 on the laptop) | 4.5 | 8.3 | 95.3 | 70.3 | 1007 | 446 | 277 | 317 |
| Translator that asks when its two readers disagree | 2.6 | 4.2 | 95.4 | 64.8 | 1036 | 453 | 284 | 310 |
| Translator that asks only when a request tells the readings apart | 3.3 | 5.8 | 94.1 | 68.4 | 1022 | 449 | 288 | 320 |

## All requests, violations in % per seed — load 600 E

| Policy | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| Rules for every kind (reference) | 0.00 | 0.00 | 0.00 |
| First fit (ignores the instruction) | 24.10 | 25.50 | 24.40 |
| No-intent teacher (ignores the instruction) | 24.85 | 27.85 | 25.45 |
| Translator alone (reader 1 on the laptop) | 9.35 | 9.55 | 10.55 |
| Translator that asks when its two readers disagree | 8.80 | 8.85 | 9.30 |
| Translator that asks only when a request tells the readings apart | 8.50 | 10.05 | 9.30 |

## The project owner's own instructions, on the laptop (4-bit base model, llama.cpp): number of instructions

| Reader | Lines | n | Right | Applied with another meaning | Not applied |
|---|---|---|---|---|---|
| Reader 1 | All | 22 | 18 | 4 | 0 |
| Reader 1 | English | 17 | 16 | 1 | 0 |
| Reader 1 | Urdu in Latin script | 5 | 2 | 3 | 0 |
| Reader 2 | All | 22 | 18 | 4 | 0 |
| Reader 2 | English | 17 | 15 | 2 | 0 |
| Reader 2 | Urdu in Latin script | 5 | 3 | 2 | 0 |
| Apertus 8B, 15 examples, no training | All | 22 | 14 | 4 | 4 |
| Apertus 8B, 15 examples, no training | English | 17 | 13 | 3 | 1 |
| Apertus 8B, 15 examples, no training | Urdu in Latin script | 5 | 1 | 1 | 3 |

## The owner's instructions, two readers: the operator is asked when their readings differ

| First reader / second reader | n | Not right, first reader alone | Not right and not asked | Asked | Asked although right |
|---|---|---|---|---|---|
| Reader 1 / Reader 2 | 22 | 4 | 1 | 4 | 1 |
| Reader 1 / Apertus 8B, 15 examples, no training | 22 | 4 | 1 | 7 | 4 |

## The owner's instructions, line by line (= : reader 1 wrote what was meant)

| Instruction | Meant | Reader 1 wrote | Outcome | Reader 2 differs: asked |
|---|---|---|---|---|
| go from London to Lyon via Oslo, at most 4 hops | avoid=none; via=Oslo; hops=4; km=any; path=any; prefer=none; rest=none | = | right |  |
| to prague freom neighborsd but avoid berlin | avoid=Berlin; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = | right |  |
| prague se belin liken munich nahee | avoid=Munich; via=none; hops=any; km=any; path=any; prefer=none; rest=none | avoid=Prague-Berlin,Munich; via=none; hops=any; km=any; path=any; prefer=none; rest=none | silent | yes |
| prefer fewer hops, rouite between central european cities to munich | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | avoid=none; via=Munich; hops=any; km=any; path=any; prefer=hops; rest=none | silent |  |
| berlin prague link is out, dont send anything over that | avoid=Berlin-Prague; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = | right |  |
| least busy route pls, if its a tie just take fewer hops | avoid=none; via=none; hops=any; km=any; path=any; prefer=load,hops; rest=none | = | right |  |
| needs to touch vienna, 5 hops max though | avoid=none; via=Vienna; hops=5; km=any; path=any; prefer=none; rest=none | = | right |  |
| save spectrum on this one, as few slots as poss | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | = | right | yes |
| actually just pick the 2nd option in the list | avoid=none; via=none; hops=any; km=any; path=2; prefer=none; rest=none | = | right |  |
| 1800km max, not bothered about the hop count | avoid=none; via=none; hops=any; km=1800; path=any; prefer=none; rest=none | = | right |  |
| can u set up protection for this too | no_instruction | = | right |  |
| paris se mat guzarna, baqi jo kam busy hai woh le lo | avoid=Paris; via=none; hops=any; km=any; path=any; prefer=load; rest=none | avoid=none; via=Paris; hops=any; km=any; path=any; prefer=none; rest=none | silent | yes |
| zurich-milan pe maintenance hai, us link ko skip kar do | avoid=Zurich-Milan; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = | right |  |
| paris brussels span mat lena aur hops minimum rakho | avoid=Paris-Brussels; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | silent | yes |
| shortest in km pls, load doesnt matter for this one | avoid=none; via=none; hops=any; km=any; path=any; prefer=km; rest=none | = | right |  |
| route it via frankfurt, avoid munich-vienna and keep it to 6 hops | avoid=Munich-Vienna; via=Frankfurt; hops=6; km=any; path=any; prefer=none; rest=none | = | right |  |
| load first then spectrum use if both routes are equally busy | avoid=none; via=none; hops=any; km=any; path=any; prefer=load,slots; rest=none | = | right |  |
| 4 hops se zyada nahi aur hamburg se nahi guzarna | avoid=Hamburg; via=none; hops=4; km=any; path=any; prefer=none; rest=none | = | right |  |
| start at slot 12 if that whole block is free | unsupported | = | right |  |
| keep modulation on qpsk for this req | unsupported | = | right |  |
| candidate 3 looks fine, use that | avoid=none; via=none; hops=any; km=any; path=3; prefer=none; rest=none | = | right |  |
| any update on that outage ticket | no_instruction | = | right |  |
