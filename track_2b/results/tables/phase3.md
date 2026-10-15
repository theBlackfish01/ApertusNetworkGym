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
| Reader 1 | 8991 | 0.89 | 0.99 | 1.70 |
| Reader 2 | 8191 | 0.82 | 0.87 | 1.19 |
| Decider | 134 | 0.97 | 0.97 | 1.20 |
| Reader of the fourth format | 962 | 1.22 | 1.30 | 1.80 |

## New types, on requests where the instruction is restrictive: decisions that comply, %

| Policy | Largest free block (200) | Not the first candidate (200) | A minimum of free slots (200) | A modulation threshold (200) | All |
|---|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 25.5 | 0.0 | 77.0 | 100.0 | 50.6 |
| Decision without an instruction (ignores it) | 18.0 | 43.0 | 85.0 | 86.5 | 58.1 |
| Decider alone | 30.0 | 88.0 | 99.0 | 98.0 | 78.8 |
| Decider alone (German, French, Italian) | – | – | – | – | – |
| Matched decider (trained on reader 1's sentences) | 29.5 | 86.0 | 96.5 | 98.5 | 77.6 |
| Translator alone (reader 1) | 28.5 | 53.5 | 79.5 | 88.5 | 62.5 |
| Hybrid without the guard | 30.0 | 72.5 | 90.5 | 97.5 | 72.6 |
| Hybrid | 30.0 | 72.5 | 90.5 | 97.5 | 72.6 |

## New types, on requests where neither instruction-blind choice complies: decisions that comply, %

| Policy | Largest free block (100) | Not the first candidate (100) | A minimum of free slots (100) | A modulation threshold (2) | All |
|---|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Decision without an instruction (ignores it) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Decider alone | 11.0 | 75.0 | 98.0 | 100.0 | 61.6 |
| Decider alone (German, French, Italian) | – | – | – | – | – |
| Matched decider (trained on reader 1's sentences) | 11.0 | 72.0 | 89.0 | 100.0 | 57.6 |
| Translator alone (reader 1) | 6.0 | 13.0 | 0.0 | 0.0 | 6.3 |
| Hybrid without the guard | 11.0 | 51.0 | 61.0 | 100.0 | 41.4 |
| Hybrid | 11.0 | 51.0 | 61.0 | 100.0 | 41.4 |

## A new constraint that no path meets (reject is right), and instructions carried in part: decisions that comply, %

| Policy | Cannot be met: rejected | Carried in part: complies | Carried in part: sent to the decider | Carried in part: guard replaced the choice |
|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 21.2 | 43.8 | 0.0 | 0.0 |
| Decision without an instruction (ignores it) | 21.2 | 44.5 | 0.0 | 0.0 |
| Decider alone | 49.5 | 67.2 | 0.0 | 0.0 |
| Decider alone (German, French, Italian) | – | – | – | – |
| Matched decider (trained on reader 1's sentences) | 42.9 | 72.2 | 0.0 | 0.0 |
| Translator alone (reader 1) | 21.7 | 68.0 | 0.0 | 0.0 |
| Hybrid without the guard | 42.4 | 63.5 | 35.5 | 0.0 |
| Hybrid | 42.4 | 70.5 | 35.5 | 7.2 |

## The policy language on stored requests: decisions that comply, %

| Policy | English: one clause | English: pair seen in training | English: pair never seen together | English: three clauses, never seen together | English: two preferences | English: all | German | French | Italian |
|---|---|---|---|---|---|---|---|---|---|
| First candidate that fits (ignores the instruction) | 70.6 | 63.3 | 62.5 | 57.5 | 81.2 | 66.8 | 68.5 | 66.8 | 66.7 |
| Decision without an instruction (ignores it) | 61.9 | 66.4 | 52.7 | 46.2 | 75.0 | 60.0 | 58.2 | 55.7 | 56.2 |
| Decider alone | 96.2 | 90.6 | 85.7 | 76.2 | 96.9 | 91.1 | – | – | – |
| Decider alone (German, French, Italian) | – | – | – | – | – | – | 87.1 | 86.0 | 86.6 |
| Matched decider (trained on reader 1's sentences) | 98.8 | 95.3 | 95.5 | 90.0 | 96.9 | 96.4 | 94.8 | 95.2 | 95.4 |
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
| Matched decider alone (trained on reader 1's sentences) | 13.4 | 28.9 | 25.7 | 37.1 | 0.2 | 3.8 | 13.8 | 2.58 | 0.0 | 0.0 | 0.0 |
| Translator alone (reader 1) | 1.2 | 2.4 | 35.6 | 42.7 | 0.0 | 6.1 | 10.5 | 6.03 | 0.0 | 0.0 | 0.0 |
| Translator alone (the fourth-format reader) | 1.5 | 3.2 | 38.8 | 40.3 | 0.0 | 7.0 | 10.9 | 6.15 | 0.0 | 0.0 | 0.0 |
| Translator that asks when its two readers disagree | 0.8 | 1.5 | 35.6 | 40.6 | 0.0 | 5.1 | 10.1 | 6.13 | 0.0 | 0.0 | 9.5 |
| Translator that asks only when a request tells the readings apart | 0.9 | 1.7 | 35.7 | 41.1 | 0.0 | 5.1 | 10.2 | 5.97 | 0.0 | 0.0 | 8.1 |
| Hybrid | 1.1 | 1.9 | 27.3 | 37.1 | 0.0 | 6.1 | 8.7 | 6.47 | 11.6 | 0.9 | 0.0 |
| Hybrid, the fourth-format reader in front | 1.6 | 3.6 | 29.6 | 35.0 | 0.0 | 7.0 | 9.1 | 6.43 | 16.6 | 1.1 | 0.0 |
| Hybrid, the fourth-format reader and the matched decider | 1.3 | 3.0 | 29.8 | 36.9 | 0.0 | 7.3 | 9.2 | 6.47 | 16.6 | 0.3 | 0.0 |
| Hybrid that asks when its two readers disagree | 0.8 | 1.5 | 28.7 | 32.4 | 0.0 | 5.1 | 8.2 | 6.60 | 17.2 | 1.1 | 9.5 |

## The same, only requests on which the instruction changes the right answer — load 240 E

| Policy | In the format: violations, % | Combinations never seen: violations, % | New types: violations, % | Carried in part: violations, % | In the format: such requests | Combinations never seen: such requests | New types: such requests | Carried in part: such requests |
|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 1182 | 469 | 349 | 361 |
| First fit (ignores the instruction) | 64.2 | 73.9 | 85.0 | 80.9 | 1201 | 486 | 306 | 356 |
| No-intent teacher (ignores the instruction) | 99.7 | 100.0 | 100.0 | 100.0 | 1185 | 491 | 341 | 367 |
| Decider alone | 40.3 | 60.1 | 54.7 | 59.6 | 1201 | 476 | 362 | 364 |
| Matched decider alone (trained on reader 1's sentences) | 29.0 | 49.9 | 56.7 | 57.7 | 1203 | 485 | 365 | 366 |
| Translator alone (reader 1) | 2.1 | 3.6 | 91.9 | 65.1 | 1216 | 497 | 321 | 378 |
| Translator alone (the fourth-format reader) | 2.7 | 4.8 | 96.3 | 61.3 | 1201 | 480 | 347 | 372 |
| Translator that asks when its two readers disagree | 1.6 | 2.5 | 91.3 | 64.9 | 1182 | 477 | 335 | 356 |
| Translator that asks only when a request tells the readings apart | 1.8 | 2.9 | 91.9 | 62.3 | 1162 | 476 | 334 | 374 |
| Hybrid | 2.1 | 3.1 | 62.0 | 57.2 | 1221 | 490 | 353 | 369 |
| Hybrid, the fourth-format reader in front | 3.0 | 5.3 | 65.0 | 54.6 | 1206 | 486 | 363 | 357 |
| Hybrid, the fourth-format reader and the matched decider | 2.2 | 4.4 | 65.9 | 56.9 | 1207 | 482 | 358 | 369 |
| Hybrid that asks when its two readers disagree | 1.6 | 2.5 | 65.5 | 49.9 | 1206 | 488 | 348 | 361 |

## All requests, violations in % per seed — load 240 E

| Policy | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| Rules for every kind (reference) | 0.00 | 0.00 | 0.00 |
| First fit (ignores the instruction) | 31.05 | 29.10 | 26.50 |
| No-intent teacher (ignores the instruction) | 32.85 | 31.85 | 29.80 |
| Decider alone | 17.40 | 16.95 | 14.85 |
| Matched decider alone (trained on reader 1's sentences) | 14.40 | 14.15 | 13.00 |
| Translator alone (reader 1) | 10.60 | 11.60 | 9.30 |
| Translator alone (the fourth-format reader) | 11.25 | 11.35 | 10.10 |
| Translator that asks when its two readers disagree | 10.70 | 10.40 | 9.10 |
| Translator that asks only when a request tells the readings apart | 10.40 | 10.50 | 9.55 |
| Hybrid | 8.90 | 9.10 | 8.00 |
| Hybrid, the fourth-format reader in front | 9.25 | 9.30 | 8.60 |
| Hybrid, the fourth-format reader and the matched decider | 9.15 | 9.15 | 9.15 |
| Hybrid that asks when its two readers disagree | 8.85 | 8.15 | 7.60 |

## The mixed stream of the third round in closed loop: violations, % of the requests of each kind — load 390 E

| Policy | In the format | Combinations never seen | New types | Carried in part | No instruction | Place outside the network | All requests | Blocking, % | Sent to the decider, % | Guard replaced the choice, % | Operator asked, % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 14.58 | 0.0 | 0.0 | 0.0 |
| First fit (ignores the instruction) | 35.3 | 48.6 | 47.6 | 55.3 | 0.0 | 0.0 | 28.6 | 8.23 | 0.0 | 0.0 | 0.0 |
| No-intent teacher (ignores the instruction) | 42.8 | 54.1 | 42.5 | 55.4 | 0.0 | 0.0 | 31.2 | 5.98 | 0.0 | 0.0 | 0.0 |
| Decider alone | 19.2 | 34.8 | 27.9 | 36.3 | 3.1 | 0.4 | 16.8 | 8.27 | 0.0 | 0.0 | 0.0 |
| Matched decider alone (trained on reader 1's sentences) | 14.1 | 26.4 | 29.0 | 35.7 | 0.2 | 1.9 | 14.4 | 7.92 | 0.0 | 0.0 | 0.0 |
| Translator alone (reader 1) | 0.9 | 1.5 | 36.7 | 43.6 | 0.0 | 6.7 | 10.6 | 11.73 | 0.0 | 0.0 | 0.0 |
| Translator alone (the fourth-format reader) | 0.7 | 1.5 | 38.4 | 42.5 | 0.0 | 8.2 | 10.7 | 11.65 | 0.0 | 0.0 | 0.0 |
| Translator that asks when its two readers disagree | 0.8 | 1.3 | 35.8 | 42.4 | 0.0 | 6.3 | 10.3 | 11.73 | 0.0 | 0.0 | 8.9 |
| Translator that asks only when a request tells the readings apart | 0.8 | 1.3 | 35.6 | 42.4 | 0.0 | 6.3 | 10.2 | 11.78 | 0.0 | 0.0 | 7.8 |
| Hybrid | 1.0 | 1.6 | 31.6 | 40.4 | 0.0 | 6.7 | 9.5 | 12.12 | 11.5 | 0.7 | 0.0 |
| Hybrid, the fourth-format reader in front | 0.7 | 1.4 | 31.2 | 37.7 | 0.0 | 7.8 | 9.1 | 12.00 | 16.1 | 0.7 | 0.0 |
| Hybrid, the fourth-format reader and the matched decider | 0.6 | 1.4 | 34.0 | 39.4 | 0.0 | 7.4 | 9.7 | 12.48 | 16.1 | 0.3 | 0.0 |
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
| Matched decider alone (trained on reader 1's sentences) | 33.4 | 47.6 | 63.0 | 58.9 | 1117 | 468 | 381 | 336 |
| Translator alone (reader 1) | 2.1 | 2.6 | 88.5 | 67.8 | 1155 | 453 | 365 | 338 |
| Translator alone (the fourth-format reader) | 1.4 | 2.3 | 95.3 | 61.4 | 1165 | 475 | 359 | 355 |
| Translator that asks when its two readers disagree | 1.7 | 2.1 | 89.1 | 64.6 | 1181 | 479 | 357 | 345 |
| Translator that asks only when a request tells the readings apart | 1.7 | 2.1 | 89.2 | 65.6 | 1185 | 481 | 353 | 337 |
| Hybrid | 2.0 | 2.3 | 68.7 | 63.5 | 1169 | 476 | 383 | 348 |
| Hybrid, the fourth-format reader in front | 1.1 | 1.9 | 66.6 | 57.5 | 1193 | 486 | 377 | 348 |
| Hybrid, the fourth-format reader and the matched decider | 1.3 | 2.3 | 72.4 | 60.8 | 1163 | 471 | 392 | 347 |
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
| Matched decider alone (trained on reader 1's sentences) | 14.85 | 14.55 | 13.75 |
| Translator alone (reader 1) | 9.95 | 11.20 | 10.65 |
| Translator alone (the fourth-format reader) | 10.10 | 10.65 | 11.45 |
| Translator that asks when its two readers disagree | 10.15 | 10.60 | 10.10 |
| Translator that asks only when a request tells the readings apart | 10.15 | 10.60 | 10.00 |
| Hybrid | 8.50 | 10.25 | 9.85 |
| Hybrid, the fourth-format reader in front | 8.55 | 9.15 | 9.65 |
| Hybrid, the fourth-format reader and the matched decider | 9.95 | 9.25 | 9.85 |
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
| Policies read by the third-format reader (no scope, no lifetime) | 21.4 | 15.2 | 52.0 | 52.03 | 0 | 13.5 / 25.6 / 25.1 |
| Policies read by the fourth-format reader | 1.1 | 2.1 | 30.7 | 30.67 | 0 | 0.9 / 0.0 / 2.4 |
| Policies read by the fourth-format reader, on the laptop | 2.4 | 2.8 | 31.8 | 31.75 | 0 | 0.9 / 3.9 / 2.4 |

## Standing policies in closed loop (policies arrive, hold for the hours they state or until withdrawn, and cover the requests their scope names): violations against the true table, % — load 390 E

| Policy | Violations, % of requests | Where a policy changes the right answer, % | Rejected, % | Blocking, % | Policies the reader dropped | Per seed |
|---|---|---|---|---|---|---|
| The true policy table (reference) | 0.0 | 0.0 | 34.7 | 34.73 | 0 | 0.0 / 0.0 / 0.1 |
| First fit (ignores the policies) | 38.1 | 75.2 | 8.2 | 8.23 | – | 38.6 / 43.2 / 32.6 |
| No-intent teacher (ignores the policies) | 45.6 | 99.9 | 6.0 | 5.98 | – | 50.9 / 51.9 / 33.9 |
| True policies, scope ignored (every policy covers every request) | 30.0 | 17.1 | 61.4 | 61.37 | 0 | 54.4 / 0.0 / 35.5 |
| True policies, lifetime ignored (no policy ever expires) | 6.4 | 5.3 | 39.8 | 39.80 | 0 | 6.0 / 7.6 / 5.5 |
| Policies read by the third-format reader (no scope, no lifetime) | 36.9 | 22.2 | 68.1 | 68.10 | 0 | 53.7 / 7.6 / 49.2 |
| Policies read by the fourth-format reader | 1.5 | 2.4 | 34.2 | 34.18 | 0 | 0.0 / 4.4 / 0.1 |
| Policies read by the fourth-format reader, on the laptop | 1.6 | 2.6 | 34.2 | 34.17 | 0 | 0.4 / 4.4 / 0.1 |

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

## Three signals that could make the system ask, on the laptop's greedy reading of reader 1: % of instructions

| Instructions | Signal | n | Asked | Not right alone | Not right and not asked | Applied wrongly and not asked | Asked although right |
|---|---|---|---|---|---|---|---|
| carried in part | 1 or more of 5 samples of reader 1 differ | 212 | 68.9 | 70.3 | 30.2 | 30.2 | 28.8 |
| carried in part | 2 or more of 5 samples of reader 1 differ | 212 | 58.5 | 70.3 | 36.3 | 36.3 | 24.5 |
| carried in part | 3 or more of 5 samples of reader 1 differ | 212 | 32.1 | 70.3 | 51.9 | 51.9 | 13.7 |
| carried in part | 4 or more of 5 samples of reader 1 differ | 212 | 10.4 | 70.3 | 66.0 | 66.0 | 6.1 |
| carried in part | 5 or more of 5 samples of reader 1 differ | 212 | 1.4 | 70.3 | 69.3 | 69.3 | 0.5 |
| carried in part | untrained Apertus 70B | 212 | 77.8 | 70.3 | 17.5 | 17.5 | 25.0 |
| carried in part | the 70B, or a sample differs | 212 | 89.6 | 70.3 | 10.4 | 10.4 | 29.7 |
| carried in part | reader 2 (same recipe, on the laptop) | 212 | 31.1 | 70.3 | 50.5 | 50.5 | 11.3 |
| carried in part | reader 2, or a sample differs | 212 | 72.2 | 70.3 | 27.4 | 27.4 | 29.2 |
| policy language | 1 or more of 5 samples of reader 1 differ | 2078 | 8.0 | 6.9 | 3.5 | 3.4 | 4.6 |
| policy language | 2 or more of 5 samples of reader 1 differ | 2078 | 6.3 | 6.9 | 4.0 | 3.9 | 3.4 |
| policy language | 3 or more of 5 samples of reader 1 differ | 2078 | 2.6 | 6.9 | 5.4 | 5.0 | 1.0 |
| policy language | 4 or more of 5 samples of reader 1 differ | 2078 | 0.7 | 6.9 | 6.4 | 6.0 | 0.2 |
| policy language | 5 or more of 5 samples of reader 1 differ | 2078 | 0.2 | 6.9 | 6.8 | 6.4 | 0.0 |
| policy language | untrained Apertus 70B | 2078 | 15.1 | 6.9 | 0.6 | 0.4 | 8.8 |
| policy language | the 70B, or a sample differs | 2078 | 18.8 | 6.9 | 0.1 | 0.1 | 12.0 |
| policy language | reader 2 (same recipe, on the laptop) | 2078 | 5.4 | 6.9 | 4.2 | 4.0 | 2.7 |
| policy language | reader 2, or a sample differs | 2078 | 10.1 | 6.9 | 2.9 | 2.8 | 6.1 |
| types never shown | 1 or more of 5 samples of reader 1 differ | 108 | 88.0 | 43.5 | 2.8 | 2.8 | 47.2 |
| types never shown | 2 or more of 5 samples of reader 1 differ | 108 | 75.0 | 43.5 | 4.6 | 4.6 | 36.1 |
| types never shown | 3 or more of 5 samples of reader 1 differ | 108 | 22.2 | 43.5 | 22.2 | 22.2 | 0.9 |
| types never shown | 4 or more of 5 samples of reader 1 differ | 108 | 7.4 | 43.5 | 36.1 | 36.1 | 0.0 |
| types never shown | 5 or more of 5 samples of reader 1 differ | 108 | 0.9 | 43.5 | 42.6 | 42.6 | 0.0 |
| types never shown | untrained Apertus 70B | 108 | 59.3 | 43.5 | 0.9 | 0.9 | 16.7 |
| types never shown | the 70B, or a sample differs | 108 | 91.7 | 43.5 | 0.0 | 0.0 | 48.1 |
| types never shown | reader 2 (same recipe, on the laptop) | 108 | 37.0 | 43.5 | 8.3 | 8.3 | 1.9 |
| types never shown | reader 2, or a sample differs | 108 | 88.0 | 43.5 | 2.8 | 2.8 | 47.2 |

## Instructions written by the project owner (40 lines), on the laptop (4-bit base model, llama.cpp), and the fourth-format reader at 16 bits: number of instructions

| Reader | Lines | n | Right | Applied with another meaning | Not applied |
|---|---|---|---|---|---|
| Reader 1 | All | 40 | 33 | 7 | 0 |
| Reader 1 | English | 35 | 31 | 4 | 0 |
| Reader 1 | Urdu in Latin script | 5 | 2 | 3 | 0 |
| Reader 2 | All | 40 | 35 | 5 | 0 |
| Reader 2 | English | 35 | 32 | 3 | 0 |
| Reader 2 | Urdu in Latin script | 5 | 3 | 2 | 0 |
| Apertus 8B, 15 examples, no training | All | 40 | 27 | 5 | 8 |
| Apertus 8B, 15 examples, no training | English | 35 | 26 | 4 | 5 |
| Apertus 8B, 15 examples, no training | Urdu in Latin script | 5 | 1 | 1 | 3 |
| Reader of the fourth format | All | 40 | 31 | 8 | 1 |
| Reader of the fourth format | English | 35 | 29 | 5 | 1 |
| Reader of the fourth format | Urdu in Latin script | 5 | 2 | 3 | 0 |
| Reader of the fourth format, 16 bits (A100) | All | 40 | 34 | 6 | 0 |
| Reader of the fourth format, 16 bits (A100) | English | 35 | 32 | 3 | 0 |
| Reader of the fourth format, 16 bits (A100) | Urdu in Latin script | 5 | 2 | 3 | 0 |

## The same, two readers of the third format: the operator is asked when their readings differ

| First reader / second reader | n | Not right, first reader alone | Not right and not asked | Asked | Asked although right |
|---|---|---|---|---|---|
| Reader 1 / Reader 2 | 40 | 7 | 2 | 6 | 1 |
| Reader 1 / Apertus 8B, 15 examples, no training | 40 | 7 | 1 | 13 | 7 |

## Instructions written by the project owner (40 lines), line by line (= : wrote what was meant; – : not read: a standing policy, or a set the 16-bit reader has not read)

| Instruction | Language | Meant | Reader 1 wrote | Reader 2 differs: asked | Fourth format wrote | Fourth format, 16 bits, wrote |
|---|---|---|---|---|---|---|
| go from London to Lyon via Oslo, at most 4 hops | en | avoid=none; via=Oslo; hops=4; km=any; path=any; prefer=none; rest=none | = |  | avoid=none; via=Oslo; hops=4; km=any; path=any; prefer=none; scope=from:London; until=open; rest=none | avoid=none; via=Oslo; hops=4; km=any; path=any; prefer=none; scope=to:Lyon; until=open; rest=none |
| to prague freom neighborsd but avoid berlin | en | avoid=Berlin; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | avoid=Berlin; via=none; hops=any; km=any; path=any; prefer=none; scope=from:Prague; until=open; rest=none | avoid=Berlin; via=none; hops=any; km=any; path=any; prefer=none; scope=to:Prague; until=open; rest=none |
| prague se belin liken munich nahee | ur | avoid=Munich; via=none; hops=any; km=any; path=any; prefer=none; rest=none | avoid=Prague-Berlin,Munich; via=none; hops=any; km=any; path=any; prefer=none; rest=none | yes | avoid=Prague; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | avoid=Berlin; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none |
| prefer fewer hops, rouite between central european cities to munich | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | avoid=none; via=Munich; hops=any; km=any; path=any; prefer=hops; rest=none |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; scope=from:Munich; until=open; rest=none | = |
| berlin prague link is out, dont send anything over that | en | avoid=Berlin-Prague; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| least busy route pls, if its a tie just take fewer hops | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=load,hops; rest=none | = |  | = | = |
| needs to touch vienna, 5 hops max though | en | avoid=none; via=Vienna; hops=5; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| save spectrum on this one, as few slots as poss | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | = | yes | = | = |
| actually just pick the 2nd option in the list | en | avoid=none; via=none; hops=any; km=any; path=2; prefer=none; rest=none | = |  | = | = |
| 1800km max, not bothered about the hop count | en | avoid=none; via=none; hops=any; km=1800; path=any; prefer=none; rest=none | = |  | = | = |
| can u set up protection for this too | en | no_instruction | = |  | = | = |
| paris se mat guzarna, baqi jo kam busy hai woh le lo | ur | avoid=Paris; via=none; hops=any; km=any; path=any; prefer=load; rest=none | avoid=none; via=Paris; hops=any; km=any; path=any; prefer=none; rest=none | yes | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=from:Paris; until=open; rest=none | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; scope=any; until=open; rest=none |
| zurich-milan pe maintenance hai, us link ko skip kar do | ur | avoid=Zurich-Milan; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| paris brussels span mat lena aur hops minimum rakho | ur | avoid=Paris-Brussels; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | yes | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; scope=any; until=open; rest=none | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; scope=any; until=open; rest=none |
| shortest in km pls, load doesnt matter for this one | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=km; rest=none | = |  | = | = |
| route it via frankfurt, avoid munich-vienna and keep it to 6 hops | en | avoid=Munich-Vienna; via=Frankfurt; hops=6; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| load first then spectrum use if both routes are equally busy | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=load,slots; rest=none | = |  | = | = |
| 4 hops se zyada nahi aur hamburg se nahi guzarna | ur | avoid=Hamburg; via=none; hops=4; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| start at slot 12 if that whole block is free | en | unsupported | = |  | = | = |
| keep modulation on qpsk for this req | en | unsupported | = |  | no_instruction | = |
| candidate 3 looks fine, use that | en | avoid=none; via=none; hops=any; km=any; path=3; prefer=none; rest=none | = |  | = | = |
| any update on that outage ticket | en | no_instruction | = |  | = | = |
| ops note: keep hamburg-berlin out of the route for now | en | avoid=Hamburg-Berlin; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| Please leave the Rome-Milan span unused on this request. | en | avoid=Rome-Milan; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| pick whichever path has the least traffic on it | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; rest=none | = |  | = | = |
| less congested route please, this ones not urgent | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; rest=none | = |  | = | = |
| need the option that eats up the fewest spectrum slots | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | = |  | = | = |
| make sure this goes through amsterdam | en | avoid=none; via=Amsterdam; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| cap this at 3 hops pls | en | avoid=none; via=none; hops=3; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| lyon-zurich is unavailable, go around that and use as few slots as you can | en | avoid=Lyon-Zurich; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | = |  | = | = |
| pass through budapest but dont go through zagreb | en | avoid=Zagreb; via=Budapest; hops=any; km=any; path=any; prefer=none; rest=none | avoid=none; via=Budapest; hops=any; km=any; path=any; prefer=none; rest=none | yes | = | = |
| 6 hops is the limit, within that choose the least loaded path | en | avoid=none; via=none; hops=6; km=any; path=any; prefer=load; rest=none | = |  | = | = |
| fewest hops first. if thats tied use the shorter distance in km | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops,km; rest=none | = |  | = | = |
| allocate from the high end of the spectrum this time | en | unsupported | = |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; scope=any; until=open; rest=none | = |
| leave one empty slot either side of this allocation | en | unsupported | = |  | = | = |
| 16qam only for this one, reject it if that wont reach | en | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | yes | = | = |
| dont split this over seperate chunks, needs one continuous block | en | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none |
| how many slots are free at the moment? | en | no_instruction | = |  | = | = |
| cheers, handing over to the evening shift now | en | no_instruction | = |  | = | = |
| can someone explain what qpsk means again | en | no_instruction | = |  | = | = |

## Instructions written by a contributor (40 lines, 15 of them standing policies), on the laptop (4-bit base model, llama.cpp), and the fourth-format reader at 16 bits: number of instructions

| Reader | Lines | n | Right | Applied with another meaning | Not applied |
|---|---|---|---|---|---|
| Reader 1 | All | 25 | 20 | 4 | 1 |
| Reader 1 | English | 7 | 6 | 0 | 1 |
| Reader 1 | German | 6 | 4 | 2 | 0 |
| Reader 1 | Italian | 6 | 6 | 0 | 0 |
| Reader 1 | Swedish | 6 | 4 | 2 | 0 |
| Reader 2 | All | 25 | 22 | 3 | 0 |
| Reader 2 | English | 7 | 7 | 0 | 0 |
| Reader 2 | German | 6 | 5 | 1 | 0 |
| Reader 2 | Italian | 6 | 6 | 0 | 0 |
| Reader 2 | Swedish | 6 | 4 | 2 | 0 |
| Apertus 8B, 15 examples, no training | All | 25 | 16 | 4 | 5 |
| Apertus 8B, 15 examples, no training | English | 7 | 5 | 0 | 2 |
| Apertus 8B, 15 examples, no training | German | 6 | 3 | 2 | 1 |
| Apertus 8B, 15 examples, no training | Italian | 6 | 4 | 1 | 1 |
| Apertus 8B, 15 examples, no training | Swedish | 6 | 4 | 1 | 1 |
| Reader of the fourth format | All | 40 | 35 | 3 | 2 |
| Reader of the fourth format | Standing policies | 15 | 14 | 1 | 0 |
| Reader of the fourth format | English | 10 | 9 | 0 | 1 |
| Reader of the fourth format | German | 10 | 10 | 0 | 0 |
| Reader of the fourth format | Italian | 10 | 9 | 1 | 0 |
| Reader of the fourth format | Swedish | 10 | 7 | 2 | 1 |
| Reader of the fourth format, 16 bits (A100) | All | 40 | 36 | 2 | 2 |
| Reader of the fourth format, 16 bits (A100) | Standing policies | 15 | 14 | 1 | 0 |
| Reader of the fourth format, 16 bits (A100) | English | 10 | 8 | 0 | 2 |
| Reader of the fourth format, 16 bits (A100) | German | 10 | 9 | 1 | 0 |
| Reader of the fourth format, 16 bits (A100) | Italian | 10 | 10 | 0 | 0 |
| Reader of the fourth format, 16 bits (A100) | Swedish | 10 | 9 | 1 | 0 |

## The same, two readers of the third format: the operator is asked when their readings differ

| First reader / second reader | n | Not right, first reader alone | Not right and not asked | Asked | Asked although right |
|---|---|---|---|---|---|
| Reader 1 / Reader 2 | 25 | 5 | 3 | 2 | 0 |
| Reader 1 / Apertus 8B, 15 examples, no training | 25 | 5 | 3 | 6 | 4 |

## Instructions written by a contributor (40 lines, 15 of them standing policies), line by line (= : wrote what was meant; – : not read: a standing policy, or a set the 16-bit reader has not read)

| Instruction | Language | Meant | Reader 1 wrote | Reader 2 differs: asked | Fourth format wrote | Fourth format, 16 bits, wrote |
|---|---|---|---|---|---|---|
| For this one, leave the London–Paris span out of the route. | en | avoid=London-Paris; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| Die Verbindung Frankfurt–Hamburg für diesen Auftrag bitte nicht nutzen. | de | avoid=Frankfurt-Hamburg; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| Den här förbindelsen får inte gå genom Prag. | sv | avoid=Prague; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| Fai passare questa richiesta da Zurigo. | it | avoid=none; via=Zurich; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| cap this one at 4 hops pls | en | avoid=none; via=none; hops=4; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| Max. 1800 km Gesamtlänge für diese Strecke, darüber bitte ablehnen. | de | avoid=none; via=none; hops=any; km=1800; path=any; prefer=none; rest=none | = |  | = | = |
| Ta den andra rutten i kandidatlistan för den här beställningen. | sv | avoid=none; via=none; hops=any; km=any; path=1; prefer=none; rest=none | avoid=none; via=none; hops=any; km=any; path=2; prefer=none; rest=none |  | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none |
| Per questo circuito scegli il percorso con meno salti possibile. | it | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | = |  | = | = |
| Use whichever path has the lowest total distance in km for this request. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=km; rest=none | = |  | = | = |
| Für diesen Lightpath möglichst den Pfad mit der geringsten Auslastung nehmen. | de | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; rest=none | = |  | = | = |
| Kör den här via Köpenhamn, men inte mer än fem hopp totalt. | sv | avoid=none; via=Copenhagen; hops=5; km=any; path=any; prefer=none; rest=none | = |  | = | = |
| Niente tratta Milano–Roma per questa richiesta; tra le alternative scegli quella che richiede meno slot. | it | avoid=Milan-Rome; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | = |  | = | = |
| Keep this request out of Berlin, six hops max, and favour the least loaded path. | en | avoid=Berlin; via=none; hops=6; km=any; path=any; prefer=load; rest=none | = |  | = | = |
| Bitte über Wien führen, München auslassen und unter den passenden Routen die kürzeste nach km nehmen. | de | avoid=Munich; via=Vienna; hops=any; km=any; path=any; prefer=km; rest=none | avoid=Munich; via=Warsaw; hops=any; km=any; path=any; prefer=km; rest=none |  | = | = |
| Undvik länken Bryssel–Paris för den här och håll hela sträckan inom 2200 km. | sv | avoid=Brussels-Paris; via=none; hops=any; km=2200; path=any; prefer=none; rest=none | = |  | = | = |
| Passa da Lione. Prima minimizza gli slot richiesti, poi la lunghezza in km a parità di slot. | it | avoid=none; via=Lyon; hops=any; km=any; path=any; prefer=slots,km; rest=none | = |  | avoid=none; via=Lyon; hops=any; km=any; path=any; prefer=slots; scope=any; until=open; rest=none | = |
| Allocate a contiguous block of spectrum slots for this lightpath, using the same slot indices on every link. | en | unsupported | = |  | = | no_instruction |
| Für diesen Auftrag QPSK fest einstellen, keine automatische Wahl der Modulation. | de | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none | yes | = | = |
| Lägg till en reservväg för den här förbindelsen som inte delar någon länk med huvudvägen. | sv | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | = |
| Per questo lightpath lascia due slot di guardia liberi su ciascun lato del blocco assegnato. | it | unsupported | = |  | = | = |
| Reassign the spectrum slots on this existing circuit, but keep its current route exactly as it is. | en | unsupported | no_instruction | yes | no_instruction | no_instruction |
| Ist das Wartungsfenster in Frankfurt schon bestätigt? | de | no_instruction | = |  | = | = |
| Överlämning: larmet i Oslo är kvitterat och ärendet ligger hos nästa skift. | sv | no_instruction | = |  | = | = |
| Oggi il caffè del turno di notte è meglio del solito. | it | no_instruction | = |  | = | = |
| Anyone know where the spare transceiver for Amsterdam ended up? | en | no_instruction | = |  | = | = |
| In den nächsten 3 Std. keine neuen Lightpaths über Zürich–Mailand legen. | de | avoid=Zurich-Milan; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=3h; rest=none | – |  | = | = |
| Alla nya förbindelser ska gå via Berlin under de kommande två timmarna. | sv | avoid=none; via=Berlin; hops=any; km=any; path=any; prefer=none; scope=any; until=2h; rest=none | – |  | = | = |
| Per le prossime quattro ore, massimo cinque salti per ogni nuova richiesta. | it | avoid=none; via=none; hops=5; km=any; path=any; prefer=none; scope=any; until=4h; rest=none | – |  | = | = |
| For the next six hours, favour paths that need the fewest spectrum slots for all new requests. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; scope=any; until=6h; rest=none | – |  | = | = |
| Bis diese Regel ausdrücklich aufgehoben wird, Straßburg bei allen neuen Routen auslassen. | de | avoid=Strasbourg; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |  | = | = |
| Länken Oslo–Köpenhamn ska inte användas för nya förbindelser förrän spärren hävs. | sv | avoid=Oslo-Copenhagen; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |  | = | = |
| Fino alla revoca della regola, dai priorità al percorso più corto in km per tutte le nuove richieste. | it | avoid=none; via=none; hops=any; km=any; path=any; prefer=km; scope=any; until=open; rest=none | – |  | = | = |
| All new requests must stay within 2500 km total route length until we lift this limit. | en | avoid=none; via=none; hops=any; km=2500; path=any; prefer=none; scope=any; until=open; rest=none | – |  | = | = |
| Für alle 400G-Anfragen gilt: Die direkte Strecke Frankfurt–München darf nicht verwendet werden. | de | avoid=Frankfurt-Munich; via=none; hops=any; km=any; path=any; prefer=none; scope=rate:400; until=open; rest=none | – |  | = | = |
| För alla beställningar med start i Stockholm ska vi prioritera vägen med lägst belastning. | sv | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; scope=from:Stockholm; until=open; rest=none | – |  | = | = |
| Tutte le richieste con destinazione Roma devono passare da Milano. | it | avoid=none; via=Milan; hops=any; km=any; path=any; prefer=none; scope=to:Rome; until=open; rest=none | – |  | = | = |
| Apply a six-hop ceiling to every 10G request. | en | avoid=none; via=none; hops=6; km=any; path=any; prefer=none; scope=rate:10; until=open; rest=none | – |  | = | = |
| Für die nächsten acht Stunden Brüssel–Paris sperren und für neue Anfragen möglichst wenige Hops wählen. | de | avoid=Brussels-Paris; via=none; hops=any; km=any; path=any; prefer=hops; scope=any; until=8h; rest=none | – |  | = | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; scope=any; until=8h; rest=none |
| Alla nya förbindelser till Zagreb ska gå via Wien och inte genom München. | sv | avoid=Munich; via=Vienna; hops=any; km=any; path=any; prefer=none; scope=to:Zagreb; until=open; rest=none | – |  | avoid=none; via=Vienna; hops=any; km=any; path=any; prefer=none; scope=to:Zagreb; until=open; rest=none | = |
| Per le prossime 12 ore, tutte le richieste da 100G devono evitare Amburgo e restare entro sette salti. | it | avoid=Hamburg; via=none; hops=7; km=any; path=any; prefer=none; scope=rate:100; until=12h; rest=none | – |  | = | = |

## Instructions written by the writer of set 2 (40 lines in English and German, 15 of them standing policies), on the laptop (4-bit base model, llama.cpp); not read at 16 bits: number of instructions

| Reader | Lines | n | Right | Applied with another meaning | Not applied |
|---|---|---|---|---|---|
| Reader 1 | All | 25 | 20 | 5 | 0 |
| Reader 1 | English | 12 | 10 | 2 | 0 |
| Reader 1 | German | 13 | 10 | 3 | 0 |
| Reader 2 | All | 25 | 21 | 4 | 0 |
| Reader 2 | English | 12 | 11 | 1 | 0 |
| Reader 2 | German | 13 | 10 | 3 | 0 |
| Apertus 8B, 15 examples, no training | All | 25 | 17 | 5 | 3 |
| Apertus 8B, 15 examples, no training | English | 12 | 8 | 2 | 2 |
| Apertus 8B, 15 examples, no training | German | 13 | 9 | 3 | 1 |
| Reader of the fourth format | All | 40 | 33 | 5 | 2 |
| Reader of the fourth format | Standing policies | 15 | 12 | 3 | 0 |
| Reader of the fourth format | English | 20 | 18 | 1 | 1 |
| Reader of the fourth format | German | 20 | 15 | 4 | 1 |

## The same, two readers of the third format: the operator is asked when their readings differ

| First reader / second reader | n | Not right, first reader alone | Not right and not asked | Asked | Asked although right |
|---|---|---|---|---|---|
| Reader 1 / Reader 2 | 25 | 5 | 3 | 2 | 0 |
| Reader 1 / Apertus 8B, 15 examples, no training | 25 | 5 | 2 | 6 | 3 |

## Instructions written by the writer of set 2 (40 lines in English and German, 15 of them standing policies), line by line (= : wrote what was meant; – : not read: a standing policy, or a set the 16-bit reader has not read)

| Instruction | Language | Meant | Reader 1 wrote | Reader 2 differs: asked | Fourth format wrote | Fourth format, 16 bits, wrote |
|---|---|---|---|---|---|---|
| Don't put this one over Amsterdam-Hamburg, still seeing errors on that span. | en | avoid=Amsterdam-Hamburg; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Rom-Zagreb bitte bei der Anfrage rauslassen. | de | avoid=Rome-Zagreb; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Can we keep Vienna out of this path? | en | avoid=Vienna; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Die hier muss über Budapest laufen. | de | avoid=none; via=Budapest; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| 5 hops is the limit for this circuit. | en | avoid=none; via=none; hops=5; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Für die Verbindung sind 2100 km das Maximum, nicht pro Abschnitt. | de | avoid=none; via=none; hops=any; km=2100; path=any; prefer=none; rest=none | = |  | = | – |
| use the last candidate on the list for this one | en | avoid=none; via=none; hops=any; km=any; path=4; prefer=none; rest=none | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none |  | unsupported | – |
| Nimm hier die Route mit den wenigsten Hops. | de | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | = |  | = | – |
| Pick the one that burns the fewest slots. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | = |  | = | – |
| Hauptsache möglichst wenig ausgelastet, die Länge ist hier egal. | de | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; rest=none | = |  | = | – |
| Via Brussels please, and don't use the Amsterdam-London link. | en | avoid=Amsterdam-London; via=Brussels; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Ohne Hamburg, max. 4 Hops. Sonst die kürzeste in km. | de | avoid=Hamburg; via=none; hops=4; km=any; path=any; prefer=km; rest=none | = |  | = | – |
| Avoid Paris-Lyon for this one. 1900 km total max. | en | avoid=Paris-Lyon; via=none; hops=any; km=1900; path=any; prefer=none; rest=none | = |  | = | – |
| Die Anfrage bitte über Berlin, aber nicht über Warschau. | de | avoid=Warsaw; via=Berlin; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Für die hier erstmal die Auslastung minimieren, bei Gleichstand die Hops. Maximal 6 Hops insgesamt. | de | avoid=none; via=none; hops=6; km=any; path=any; prefer=load,hops; rest=none | = |  | avoid=none; via=none; hops=6; km=any; path=any; prefer=load; scope=any; until=open; rest=none | – |
| Route this through Strasbourg and use as few slots as possible. | en | avoid=none; via=Strasbourg; hops=any; km=any; path=any; prefer=slots; rest=none | = |  | = | – |
| Use slots 32 through 39 for this circuit, nothing else. | en | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | yes | = | – |
| Für diesen Lightpath bitte kein 16QAM verwenden. | de | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none |  | = | – |
| Put this circuit in the lowest-index free slot block that fits. | en | unsupported | = |  | = | – |
| Die Verbindung darf keine Regeneration brauchen, das muss optisch durchgehen. | de | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |
| Für die hier: nach dem Schalten max. 70 % Spektrumbelegung auf jedem Link. | de | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none | yes | = | – |
| Did the London maintenance actually finish, or is the ticket just closed? | en | no_instruction | = |  | = | – |
| Zur Übergabe: Ticket in Madrid ist noch offen, letzte Rückmeldung fehlt. | de | no_instruction | = |  | unsupported | – |
| Coffee machine's dead again. Long shift ahead. | en | no_instruction | = |  | = | – |
| Ich bin gleich in der Übergabe, danach wieder erreichbar. | de | no_instruction | = |  | = | – |
| For the next two hours, no new paths over Bordeaux-Paris. | en | avoid=Bordeaux-Paris; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=2h; rest=none | – |  | = | – |
| Ab jetzt für 3 Std. alle neuen Anfragen über München führen. | de | avoid=none; via=Munich; hops=any; km=any; path=any; prefer=none; scope=any; until=3h; rest=none | – |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=3h; rest=none | – |
| Next 4 hours: prefer the least loaded route for new requests. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; scope=any; until=4h; rest=none | – |  | = | – |
| Für die nächsten 2 Stunden bei allen neuen Lightpaths max. 1800 km. | de | avoid=none; via=none; hops=any; km=1800; path=any; prefer=none; scope=any; until=2h; rest=none | – |  | = | – |
| Keep Barcelona-Lyon out of new routes until this restriction is explicitly lifted. | en | avoid=Barcelona-Lyon; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |  | = | – |
| Prag bleibt für neue Verbindungen tabu, bis wir die Sperre aufheben. | de | avoid=Prague; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |  | = | – |
| From now on, optimise new requests for fewest hops until we withdraw that policy. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; scope=any; until=open; rest=none | – |  | = | – |
| Ab sofort bei neuen Anfragen Kandidat 0 nehmen. Gilt bis zum Widerruf. | de | avoid=none; via=none; hops=any; km=any; path=0; prefer=none; scope=any; until=open; rest=none | – |  | = | – |
| All 40G requests should avoid the Berlin-Copenhagen span. | en | avoid=Berlin-Copenhagen; via=none; hops=any; km=any; path=any; prefer=none; scope=rate:40; until=open; rest=none | – |  | = | – |
| Alles, was in Dublin startet, soll über London gehen. | de | avoid=none; via=London; hops=any; km=any; path=any; prefer=none; scope=from:Dublin; until=open; rest=none | – |  | = | – |
| For requests ending in Zurich, pick the shortest route in km. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=km; scope=to:Zurich; until=open; rest=none | – |  | = | – |
| Bei 100G grundsätzlich die Route mit dem kleinsten Slotbedarf nehmen. | de | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; scope=rate:100; until=open; rest=none | – |  | = | – |
| Next 5 hours, route all new requests via Frankfurt and keep Munich out. | en | avoid=Munich; via=Frankfurt; hops=any; km=any; path=any; prefer=none; scope=any; until=5h; rest=none | – |  | = | – |
| Für Anfragen nach Stockholm Oslo auslassen und höchstens 7 Hops zulassen. | de | avoid=Oslo; via=none; hops=7; km=any; path=any; prefer=none; scope=to:Stockholm; until=open; rest=none | – |  | avoid=none; via=none; hops=7; km=any; path=any; prefer=none; scope=from:Stockholm; until=open; rest=none | – |
| For the next 8 hours, keep 400G off Belgrade-Zagreb and favour the route with the fewest hops. | en | avoid=Belgrade-Zagreb; via=none; hops=any; km=any; path=any; prefer=hops; scope=rate:400; until=8h; rest=none | – |  | avoid=Belgrade-Zagreb; via=none; hops=any; km=any; path=any; prefer=hops; scope=any; until=8h; rest=none | – |

## Instructions written by the writer of set 3 (40 lines in English and German, 15 of them standing policies), on the laptop (4-bit base model, llama.cpp); not read at 16 bits: number of instructions

| Reader | Lines | n | Right | Applied with another meaning | Not applied |
|---|---|---|---|---|---|
| Reader 1 | All | 25 | 20 | 4 | 1 |
| Reader 1 | English | 19 | 17 | 1 | 1 |
| Reader 1 | German | 6 | 3 | 3 | 0 |
| Reader 2 | All | 25 | 20 | 4 | 1 |
| Reader 2 | English | 19 | 17 | 1 | 1 |
| Reader 2 | German | 6 | 3 | 3 | 0 |
| Apertus 8B, 15 examples, no training | All | 25 | 18 | 2 | 5 |
| Apertus 8B, 15 examples, no training | English | 19 | 14 | 2 | 3 |
| Apertus 8B, 15 examples, no training | German | 6 | 4 | 0 | 2 |
| Reader of the fourth format | All | 40 | 34 | 5 | 1 |
| Reader of the fourth format | Standing policies | 15 | 14 | 1 | 0 |
| Reader of the fourth format | English | 30 | 28 | 1 | 1 |
| Reader of the fourth format | German | 10 | 6 | 4 | 0 |

## The same, two readers of the third format: the operator is asked when their readings differ

| First reader / second reader | n | Not right, first reader alone | Not right and not asked | Asked | Asked although right |
|---|---|---|---|---|---|
| Reader 1 / Reader 2 | 25 | 5 | 3 | 2 | 0 |
| Reader 1 / Apertus 8B, 15 examples, no training | 25 | 5 | 1 | 7 | 3 |

## Instructions written by the writer of set 3 (40 lines in English and German, 15 of them standing policies), line by line (= : wrote what was meant; – : not read: a standing policy, or a set the 16-bit reader has not read)

| Instruction | Language | Meant | Reader 1 wrote | Reader 2 differs: asked | Fourth format wrote | Fourth format, 16 bits, wrote |
|---|---|---|---|---|---|---|
| Lyon-Zürich für die Schaltung bitte außen vor lassen, da sind noch Fehler drauf. | de | avoid=Lyon-Zurich; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Keep this order off the Brussels-Frankfurt span, pleae. | en | avoid=Brussels-Frankfurt; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Milan's a no-go for this one. | en | avoid=Milan; via=none; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Make sure this circuit goes through Warsaw. | en | avoid=none; via=Warsaw; hops=any; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| No more than three hops on this order. | en | avoid=none; via=none; hops=3; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Distance budget on this order is 1600 km end to end. | en | avoid=none; via=none; hops=any; km=1600; path=any; prefer=none; rest=none | = |  | = | – |
| Der dritte Vorschlag passt, den bitte nehmen. | de | avoid=none; via=none; hops=any; km=any; path=2; prefer=none; rest=none | avoid=none; via=none; hops=any; km=any; path=3; prefer=none; rest=none |  | avoid=none; via=none; hops=any; km=any; path=3; prefer=none; scope=any; until=open; rest=none | – |
| Just give me the shortest one in km for this circuit. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=km; rest=none | = |  | = | – |
| Keep the slot count as low as you can on this request. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; rest=none | = |  | = | – |
| Go with the fewest hops for this one. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=hops; rest=none | = |  | = | – |
| Die hier bittte über Frankfurt, den direkten Link Paris-Straßburg aber nicht nutzen. | de | avoid=Paris-Strasbourg; via=Frankfurt; hops=any; km=any; path=any; prefer=none; rest=none | avoid=Paris-Strasbourg,Frankfurt; via=none; hops=any; km=any; path=any; prefer=none; rest=none | yes | avoid=Paris-Strasbourg; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |
| Through Hamburg, five hops max. That's for the whole path. | en | avoid=none; via=Hamburg; hops=5; km=any; path=any; prefer=none; rest=none | = |  | = | – |
| Keep Zurich out of it and take whichever remaining path is least busy. | en | avoid=Zurich; via=none; hops=any; km=any; path=any; prefer=load; rest=none | = |  | = | – |
| 2400 km ceiling on this one, then take the option needing the fewest slots. | en | avoid=none; via=none; hops=any; km=2400; path=any; prefer=slots; rest=none | = |  | = | – |
| Don't use Budapest-Belgrade on this order. Six hops max, then pick the shortest route in km. | en | avoid=Budapest-Belgrade; via=none; hops=6; km=any; path=any; prefer=km; rest=none | = |  | = | – |
| Über Prag; möglichst wenig Auslastung, bei Gleichstand die kürzere Strecke in km. | de | avoid=none; via=Prague; hops=any; km=any; path=any; prefer=load,km; rest=none | = |  | = | – |
| Need this circuit at 12 ms one-way latency or better. | en | unsupported | no_instruction |  | no_instruction | – |
| Beim neuen Pfad keine SRLG gemeinsam mit dem bestehenden Backup. | de | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |
| Put this one in the upper half of the spectrum. | en | unsupported | = |  | = | – |
| Try 16QAM first; if the reach doesn't work, fall back to QPSK. | en | unsupported | = |  | = | – |
| Don't defrag the spectrum to fit this one; use what's free already. | en | unsupported | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=none | yes | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |
| Have they finished testing Hamburg-Frankfurt yet? | en | no_instruction | = |  | = | – |
| Handover: Glasgow alarm cleared, waiting on the test results. | en | no_instruction | = |  | = | – |
| Ich hol mir kurz was zu essen, bin in zehn Minuten wieder da. | de | no_instruction | = |  | = | – |
| Is anyone from the late shift availble for the handover? | en | no_instruction | = |  | = | – |
| No new circuits on Madrid-Barcelona for the next 6 hours. | en | avoid=Madrid-Barcelona; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=6h; rest=none | – |  | = | – |
| New circuits get a seven-hop cap for the next 3 hours. | en | avoid=none; via=none; hops=7; km=any; path=any; prefer=none; scope=any; until=3h; rest=none | – |  | = | – |
| In den näcshten 4 Std. alle neuen Anfragen über Straßburg schicken. | de | avoid=none; via=Strasbourg; hops=any; km=any; path=any; prefer=none; scope=any; until=4h; rest=none | – |  | avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=to:Strasbourg; until=4h; rest=none | – |
| Next 12 hours, go for the shortest routes in km on new orders. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=km; scope=any; until=12h; rest=none | – |  | = | – |
| Leave Berlin-Warsaw blocked for new orders until the restriction is explicitly removed. | en | avoid=Berlin-Warsaw; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |  | = | – |
| No new paths through Munich until we explicitly lift that rule. | en | avoid=Munich; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none | – |  | = | – |
| Bis auf Widerruf bei neuen Schaltungen die am wenigsten ausgelastete Route bevorzugen. | de | avoid=none; via=none; hops=any; km=any; path=any; prefer=load; scope=any; until=open; rest=none | – |  | = | – |
| Until this policy is withdrawn, minimise slot use on all new requests. | en | avoid=none; via=none; hops=any; km=any; path=any; prefer=slots; scope=any; until=open; rest=none | – |  | = | – |
| For 40G orders, don't go above 4 hops. | en | avoid=none; via=none; hops=4; km=any; path=any; prefer=none; scope=rate:40; until=open; rest=none | – |  | = | – |
| For anything starting in Bordeaux, keep Paris out of the route. | en | avoid=Paris; via=none; hops=any; km=any; path=any; prefer=none; scope=from:Bordeaux; until=open; rest=none | – |  | = | – |
| Anfragen mit Ziel Kopenhagen immer über Berlin führen. | de | avoid=none; via=Berlin; hops=any; km=any; path=any; prefer=none; scope=to:Copenhagen; until=open; rest=none | – |  | = | – |
| For every 400G order, use candidate 3. | en | avoid=none; via=none; hops=any; km=any; path=3; prefer=none; scope=rate:400; until=open; rest=none | – |  | = | – |
| For the next 2 hours, keep new circuits off Glasgow-Amsterdam and pick routes with the fewest hops. | en | avoid=Glasgow-Amsterdam; via=none; hops=any; km=any; path=any; prefer=hops; scope=any; until=2h; rest=none | – |  | = | – |
| New requests out of Rome need to go via Vienna, eight hops max. | en | avoid=none; via=Vienna; hops=8; km=any; path=any; prefer=none; scope=from:Rome; until=open; rest=none | – |  | = | – |
| Für 100G gilt die nächsten 10 Stunden: maximal 2000 km, von den passenden Routen die am wenigsten ausgelastete nehmen. | de | avoid=none; via=none; hops=any; km=2000; path=any; prefer=load; scope=rate:100; until=10h; rest=none | – |  | = | – |
