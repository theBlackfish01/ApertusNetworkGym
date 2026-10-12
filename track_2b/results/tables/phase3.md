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

## The same by language: all instructions, and the combinations never seen together

| Reader | English: all | English: never seen together | German: all | German: never seen together | French: all | French: never seen together | Italian: all | Italian: never seen together |
|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 15 examples, no training | 94.6 | 97.3 | 82.7 | 82.8 | 88.5 | 88.8 | 82.9 | 86.2 |
| Apertus 70B (first generation), 15 examples, no training | 77.7 | 72.7 | 73.0 | 68.8 | 72.5 | 65.2 | 64.4 | 58.0 |
| Apertus 70B (generation 1.5), 15 examples, no training | 93.5 | 90.4 | 84.8 | 84.4 | 91.6 | 86.6 | 86.7 | 83.0 |
| Apertus 8B fine-tuned (reader 1) | 96.7 | 97.3 | 91.4 | 88.7 | 96.0 | 97.3 | 94.8 | 93.6 |
| Apertus 8B fine-tuned (reader 2) | 96.2 | 96.3 | 89.5 | 88.2 | 94.5 | 95.2 | 92.9 | 93.1 |
| Reader 1 on the laptop (4-bit GGUF, llama.cpp) | 93.7 | 88.2 | 90.5 | 82.3 | 96.2 | 92.5 | 91.9 | 86.7 |

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

## The gate: what a reader does with instructions that are not, or not wholly, in the format, % of distinct instructions

| Reader | New type: handed to the decider (right) | New type: dropped | New type: applied as something else (silent) | Part carried: part and marker right | Part carried: all handed on | Part carried: part right, rest dropped silently | Part carried: other | Other routing instruction: handed on (right) | No instruction: dropped (right) | No instruction: applied (silent) | Place outside the network: flagged (right) | Place outside the network: applied (silent) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 15 examples, no training | 43.9 | 8.3 | 47.8 | 30.7 | 2.4 | 8.5 | 58.5 | 18.8 | 100.0 | 0.0 | 64.7 | 33.3 |
| Apertus 70B (first generation), 15 examples, no training | 65.6 | 7.5 | 26.9 | 30.7 | 21.7 | 4.7 | 42.9 | 56.2 | 96.7 | 0.0 | 57.3 | 11.3 |
| Apertus 70B (generation 1.5), 15 examples, no training | 65.2 | 28.1 | 6.7 | 15.6 | 24.1 | 17.5 | 42.9 | 18.8 | 100.0 | 0.0 | 63.3 | 11.3 |
| Apertus 8B fine-tuned (reader 1) | 51.0 | 2.4 | 46.6 | 27.4 | 0.0 | 31.1 | 41.5 | 18.8 | 96.7 | 3.3 | 77.3 | 20.0 |
| Apertus 8B fine-tuned (reader 2) | 54.9 | 1.2 | 43.9 | 24.1 | 0.0 | 13.7 | 62.3 | 50.0 | 96.7 | 3.3 | 78.0 | 19.3 |
| Reader 1 on the laptop (4-bit GGUF, llama.cpp) | 54.9 | 0.0 | 45.1 | 29.7 | 0.0 | 54.2 | 16.0 | 50.0 | 96.7 | 3.3 | 88.0 | 10.0 |

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
| Reader 1 | 2620 | 0.89 | 0.88 | 1.03 |
| Reader 2 | 38 | 1.19 | 1.09 | 1.34 |
| Decider | 134 | 0.97 | 0.97 | 1.20 |

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
| Hybrid | 1.0 | 1.6 | 31.6 | 40.4 | 0.0 | 6.7 | 9.5 | 12.12 | 11.5 | 0.7 | 0.0 |
| Hybrid that asks when its two readers disagree | 0.8 | 1.4 | 28.9 | 34.7 | 0.0 | 6.3 | 8.5 | 12.25 | 17.3 | 1.0 | 8.9 |

## The same, only requests on which the instruction changes the right answer — load 390 E

| Policy | In the format: violations, % | Combinations never seen: violations, % | New types: violations, % | Carried in part: violations, % | In the format: such requests | Combinations never seen: such requests | New types: such requests | Carried in part: such requests |
|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 1152 | 464 | 366 | 352 |
| First fit (ignores the instruction) | 67.2 | 76.9 | 92.3 | 78.7 | 1122 | 459 | 337 | 305 |
| No-intent teacher (ignores the instruction) | 100.0 | 100.0 | 100.0 | 100.0 | 1156 | 463 | 386 | 331 |
| Decider alone | 42.6 | 60.3 | 57.6 | 58.7 | 1143 | 469 | 394 | 339 |
| Translator alone (reader 1) | 2.1 | 2.6 | 88.5 | 67.8 | 1155 | 453 | 365 | 338 |
| Hybrid | 2.0 | 2.3 | 68.7 | 63.5 | 1169 | 476 | 383 | 348 |
| Hybrid that asks when its two readers disagree | 1.8 | 2.3 | 65.3 | 55.5 | 1138 | 472 | 360 | 344 |

## All requests, violations in % per seed — load 390 E

| Policy | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| Rules for every kind (reference) | 0.00 | 0.00 | 0.00 |
| First fit (ignores the instruction) | 28.00 | 30.05 | 27.85 |
| No-intent teacher (ignores the instruction) | 30.70 | 31.85 | 31.15 |
| Decider alone | 16.45 | 16.90 | 17.15 |
| Translator alone (reader 1) | 9.95 | 11.20 | 10.65 |
| Hybrid | 8.50 | 10.25 | 9.85 |
| Hybrid that asks when its two readers disagree | 7.95 | 8.95 | 8.50 |
