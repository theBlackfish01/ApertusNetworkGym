# Second round: a stronger translator and a hybrid

Rendered by `src/report_phase2.py`; do not edit by hand. The second translator has a second refusal (`no_instruction`), was shown two preferences, and its fine-tuned version was trained on English, German, French and Italian. † These German, French and Italian sentences were a test for the first translator and are training wording for the second; its test is the natively written sets. For the second translator the pairs of the closed loop are no longer unseen. The hybrid sends what the translator calls `unsupported` to the fine-tuned decider. Test sets: `src/corpora2.py`.

## Instructions translated with the right meaning, % of distinct instructions

| Translator | Our wording | Independent wording | German † | French † | Italian † | German, native | French, native | Italian, native | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|---|---|---|---|
| First translator, 7 examples | 92.2 | 91.2 | 87.6 | 93.6 | 93.3 | – | – | – | 71.5 | 83.4 | 92.0 |
| First translator, fine-tuned | 94.6 | 88.5 | 86.5 | 96.5 | 85.2 | – | – | – | 76.0 | 76.6 | 92.6 |
| Second translator, 11 examples | 89.3 | 88.1 | 82.7 | 90.5 | 81.4 | 84.1 | 92.9 | 89.5 | 70.2 | 78.1 | – |
| Second translator, fine-tuned | 99.6 | 95.0 | 99.2 | 100.0 | 91.6 | 96.6 | 94.5 | 98.0 | 76.9 | 86.9 | 98.3 |

## Instructions with two preferences translated with the right meaning and order, %

| Translator | Our wording | Independent wording | German, native | French, native | Italian, native |
|---|---|---|---|---|---|
| First translator, 7 examples | 65.6 | 74.4 | – | – | – |
| First translator, fine-tuned | 52.7 | 41.6 | – | – | – |
| Second translator, 11 examples | 51.6 | 52.0 | 52.9 | 59.7 | 45.7 |
| Second translator, fine-tuned | 96.8 | 86.4 | 95.6 | 97.0 | 87.1 |

## The gate: what the second translator does with instructions outside its format

| Translator | Unseen types: to the decider (right), % | Unseen types: dropped, % | Unseen types: applied as a constraint (silent), % | Unseen types that cannot be met: to the decider (right), % | Unseen types that cannot be met: dropped, % | Unseen types that cannot be met: applied as a constraint (silent), % | No instruction: dropped (right), % | No instruction: to the decider, % | No instruction: applied as a constraint (silent), % |
|---|---|---|---|---|---|---|---|---|---|
| Second translator, 11 examples | 64.8 | 26.5 | 8.8 | 65.6 | 21.4 | 13.0 | 99.1 | 0.9 | 0.0 |
| Second translator, fine-tuned | 71.7 | 23.1 | 5.2 | 72.7 | 20.8 | 6.5 | 95.7 | 4.3 | 0.0 |

## Instruction types nobody wrote a rule for: decisions that comply, % (200 requests per type on which the instruction changes the right answer; last column: rejected when it cannot be met, 200 requests)

| Policy | Pass through a node | Avoid a node | Hop limit | Length limit | Shortest in km | A given candidate | All six | Cannot be met: rejected |
|---|---|---|---|---|---|---|---|---|
| Decider alone | 94.0 | 83.5 | 76.5 | 66.5 | 98.0 | 84.0 | 83.8 | 18.5 |
| First translator, fine-tuned | – | – | – | – | – | – | – | – |
| Second translator, 11 examples | 0.0 | 0.0 | 39.0 | 0.0 | 21.0 | 0.0 | 10.0 | 0.0 |
| Second translator, fine-tuned | 0.0 | 3.5 | 9.5 | 0.0 | 54.0 | 0.0 | 11.2 | 0.0 |
| Hybrid: second translator (11 examples), then decider | 76.5 | 2.0 | 81.5 | 66.5 | 94.0 | 65.5 | 64.3 | 2.5 |
| Hybrid: second translator (fine-tuned), then decider | 92.0 | 5.5 | 76.5 | 66.5 | 82.5 | 80.0 | 67.2 | 2.5 |

## Text that is no instruction (337 requests): what happens to the request, %

| Policy | Same decision as without it | Rejected | Flagged | Sent to the decider |
|---|---|---|---|---|
| Decider alone | 89.3 | 5.9 | 0.0 | 0.0 |
| First translator, fine-tuned | – | – | – | – |
| Second translator, 11 examples | 100.0 | 1.2 | 100.0 | 0.0 |
| Second translator, fine-tuned | 100.0 | 1.2 | 100.0 | 0.0 |
| Hybrid: second translator (11 examples), then decider | 100.0 | 1.2 | 99.4 | 0.6 |
| Hybrid: second translator (fine-tuned), then decider | 97.3 | 2.1 | 92.3 | 7.7 |

## Supported instructions: decisions inside the admissible set, %

| Policy | Our wording | Independent wording | German † | French † | Italian † | German, native | French, native | Italian, native | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Decider alone | 94.4 | 91.3 | 89.6 | 92.0 | 90.9 | 92.3 | 91.8 | 90.3 | 85.3 | 89.8 | 92.3 |
| First translator, fine-tuned | 99.1 | 97.5 | 96.6 | 98.4 | 97.5 | – | – | – | 95.3 | 95.5 | 98.9 |
| Second translator, 11 examples | 93.8 | 96.2 | 90.3 | 93.0 | 91.8 | 92.8 | 96.6 | 94.9 | 86.3 | 93.7 | – |
| Second translator, fine-tuned | 100.0 | 99.4 | 99.7 | 100.0 | 98.6 | 99.5 | 99.1 | 99.8 | 96.0 | 95.7 | 99.9 |
| Hybrid: second translator (11 examples), then decider | – | 96.3 | 90.3 | 93.0 | 92.1 | 92.8 | 96.6 | 94.9 | 86.2 | 94.2 | – |
| Hybrid: second translator (fine-tuned), then decider | – | 99.5 | 99.7 | 100.0 | 98.9 | 99.5 | 99.7 | 99.8 | 95.3 | 97.3 | – |

## Closed loop, intent violations, % of decisions, mean of three seeds — load 240 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Pairs | Avoid link + fewest slots | Two preferences (intersection) | Two preferences (ordered reading) |
|---|---|---|---|---|---|---|---|---|---|
| Decider | 3.85 | 0.73 | 0.50 | 0.25 | 0.85 | 14.17 | 3.65 | 24.96 | – |
| First translator, fine-tuned | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.02 | 0.03 | 6.08 | 4.29 |
| Second translator, fine-tuned | 0.05 | 0.00 | 0.00 | 0.00 | 0.00 | 0.13 | 0.03 | 0.24 | 0.57 |

## Closed loop, intent violations, % of decisions, mean of three seeds — load 390 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Pairs | Avoid link + fewest slots | Two preferences (intersection) | Two preferences (ordered reading) |
|---|---|---|---|---|---|---|---|---|---|
| Decider | 3.27 | 0.63 | 0.67 | 0.13 | 1.03 | 12.88 | 3.66 | 21.97 | – |
| First translator, fine-tuned | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 2.77 | 0.00 | 5.49 | 3.31 |
| Second translator, fine-tuned | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.20 | 0.00 | 0.40 | 0.50 |

## A mixed stream of instructions in closed loop: violations, % of the requests of each kind — load 240 E

| Policy | Supported, independent wording | Types without a rule | Text that is no instruction | Link that does not exist | Nothing typed | All requests | Blocking, % | Sent to the decider, % |
|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.95 | 0.0 |
| Decider alone | 9.4 | 7.8 | 5.1 | 0.7 | 0.0 | 6.6 | 3.15 | 0.0 |
| Second translator alone (fine-tuned) | 1.2 | 38.5 | 0.0 | 0.0 | 0.0 | 10.2 | 2.78 | 0.0 |
| Hybrid: second translator, then decider | 1.1 | 13.9 | 1.6 | 0.0 | 0.0 | 4.1 | 3.43 | 19.0 |

## The same, only requests on which the instruction changes the right answer — load 240 E

| Policy | Supported: violations, % | Types without a rule: violations, % | Supported: such requests | Types without a rule: such requests |
|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 903 | 622 |
| Decider alone | 24.1 | 17.1 | 866 | 614 |
| Second translator alone (fine-tuned) | 2.6 | 90.3 | 871 | 630 |
| Hybrid: second translator, then decider | 2.5 | 31.8 | 863 | 600 |

## A mixed stream of instructions in closed loop: violations, % of the requests of each kind — load 390 E

| Policy | Supported, independent wording | Types without a rule | Text that is no instruction | Link that does not exist | Nothing typed | All requests | Blocking, % | Sent to the decider, % |
|---|---|---|---|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 9.15 | 0.0 |
| Decider alone | 8.4 | 7.7 | 4.5 | 3.7 | 0.0 | 6.3 | 8.17 | 0.0 |
| Second translator alone (fine-tuned) | 0.7 | 36.2 | 0.0 | 0.0 | 0.0 | 9.3 | 7.80 | 0.0 |
| Hybrid: second translator, then decider | 0.7 | 13.8 | 2.0 | 0.6 | 0.0 | 4.0 | 8.50 | 18.5 |

## The same, only requests on which the instruction changes the right answer — load 390 E

| Policy | Supported: violations, % | Types without a rule: violations, % | Supported: such requests | Types without a rule: such requests |
|---|---|---|---|---|
| Rules for every kind (reference) | 0.0 | 0.0 | 769 | 610 |
| Decider alone | 23.7 | 16.1 | 777 | 628 |
| Second translator alone (fine-tuned) | 2.0 | 90.0 | 787 | 590 |
| Hybrid: second translator, then decider | 2.0 | 30.7 | 791 | 613 |
