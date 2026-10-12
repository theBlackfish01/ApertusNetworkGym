# Second round: a stronger translator and a hybrid

Rendered by `src/report_phase2.py`; do not edit by hand. The second translator has a second refusal (`no_instruction`), was shown two preferences, and its fine-tuned version was trained on English, German, French and Italian. † These German, French and Italian sentences were a test for the first translator and are training wording for the second; its test is the natively written sets. For the second translator the pairs of the closed loop are no longer unseen. The hybrid sends what the translator calls `unsupported` to the fine-tuned decider. Test sets: `src/corpora2.py`.

## Instructions translated with the right meaning, % of distinct instructions

| Translator | Our wording | Independent wording | German † | French † | Italian † | German, native | French, native | Italian, native | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|---|---|---|---|
| First translator, 7 examples | 92.2 | 91.2 | 87.6 | 93.6 | 93.3 | – | – | – | 71.5 | 83.4 | 92.0 |
| First translator, fine-tuned | 94.6 | 88.5 | 86.5 | 96.5 | 85.2 | – | – | – | 76.0 | 76.6 | 92.6 |

## Instructions with two preferences translated with the right meaning and order, %

| Translator | Our wording | Independent wording | German, native | French, native | Italian, native |
|---|---|---|---|---|---|
| First translator, 7 examples | 65.6 | 74.4 | – | – | – |
| First translator, fine-tuned | 52.7 | 41.6 | – | – | – |

## The gate: what the second translator does with instructions outside its format

| Translator | Unseen types: to the decider (right), % | Unseen types: dropped, % | Unseen types: applied as a constraint (silent), % | Unseen types that cannot be met: to the decider (right), % | Unseen types that cannot be met: dropped, % | Unseen types that cannot be met: applied as a constraint (silent), % | No instruction: dropped (right), % | No instruction: to the decider, % | No instruction: applied as a constraint (silent), % |
|---|---|---|---|---|---|---|---|---|---|
| Second translator, 11 examples | – | – | – | – | – | – | – | – | – |
| Second translator, fine-tuned | – | – | – | – | – | – | – | – | – |

## Instruction types nobody wrote a rule for: decisions that comply, % (200 requests per type on which the instruction changes the right answer; last column: rejected when it cannot be met, 200 requests)

| Policy | Pass through a node | Avoid a node | Hop limit | Length limit | Shortest in km | A given candidate | All six | Cannot be met: rejected |
|---|---|---|---|---|---|---|---|---|
| Decider alone | – | – | – | – | – | – | – | – |
| First translator, fine-tuned | – | – | – | – | – | – | – | – |

## Text that is no instruction (337 requests): what happens to the request, %

| Policy | Same decision as without it | Rejected | Flagged | Sent to the decider |
|---|---|---|---|---|
| Decider alone | – | – | – | – |
| First translator, fine-tuned | – | – | – | – |

## Supported instructions: decisions inside the admissible set, %

| Policy | Our wording | Independent wording | German † | French † | Italian † | German, native | French, native | Italian, native | Swiss German | Misspelt | Other topology |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Decider alone | 94.4 | 91.3 | 89.6 | 92.0 | 90.9 | – | – | – | 85.3 | 89.8 | 92.3 |
| First translator, fine-tuned | 99.1 | 97.5 | 96.6 | 98.4 | 97.5 | – | – | – | 95.3 | 95.5 | 98.9 |

## Closed loop, intent violations, % of decisions, mean of three seeds — load 240 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Pairs | Avoid link + fewest slots | Two preferences (intersection) | Two preferences (ordered reading) |
|---|---|---|---|---|---|---|---|---|---|
| Decider | 3.85 | 0.73 | 0.50 | 0.25 | 0.85 | 14.17 | 3.65 | 24.96 | – |
| First translator, fine-tuned | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.02 | 0.03 | 6.08 | 4.29 |

## Closed loop, intent violations, % of decisions, mean of three seeds — load 390 E

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Pairs | Avoid link + fewest slots | Two preferences (intersection) | Two preferences (ordered reading) |
|---|---|---|---|---|---|---|---|---|---|
| Decider | 3.27 | 0.63 | 0.67 | 0.13 | 1.03 | 12.88 | 3.66 | 21.97 | – |
| First translator, fine-tuned | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 2.77 | 0.00 | 5.49 | 3.31 |
