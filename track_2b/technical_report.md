# Technical report — Operator instructions for lightpath provisioning with Apertus 8B

> DRAFT for the owner's review. Every number is copied from the file named next to it. Open
> items are marked TODO: team, video, public links, the final commit. The long account of the
> first two rounds is in `docs/report_rounds_1_2.md`.

- **Track:** Track 2B — Intent-conditioned lightpath provisioning
- **Event:** Online
- **Team:** `team name` — Wadood Ranjha, `member`, `member`
- **Demo:** `link to video`

## 1. Summary

Operators of optical transport networks state provisioning policy in plain language ("the
Zurich–Milan span is under maintenance", "at most four hops, then the shortest in km"), in the
language they work in. We built a system in which Apertus 8B reads such an instruction while the
network still follows fixed, checkable rules. Apertus translates the instruction once into one
line of a small policy language, and a rule engine enforces that line for every lightpath
request. A second reader, trained separately, translates it again; where the two readings differ
the operator is asked. An instruction outside the language goes to a fine-tuned Apertus that
decides the request itself, and its choice is checked against whatever part of the instruction
the language does carry. The whole system runs on a laptop GPU.

Measured in the Optical Networking Gym simulator, on instructions written by separate AI
instances in English, German, French and Italian: the translator reads 94.8 % of 2,078
instructions right, and combinations of clauses it never saw together as well as those it was
trained on (96.5 against 95.6 %). Its decisions comply with the instruction in 99.6 % of cases;
those of the model that decides alone in 91.1 %, falling from 96 % for one clause to 76 % for
three. On a mixed stream of instructions in closed loop the hybrid that asks breaks 8.5 % of
requests, the translator alone 10.6 %, the decider alone 16.8 %, and first fit, which ignores
instructions, 28.6 %. The weak point is measured too: of instruction types that no component was
ever shown, the translator silently applies 47 % as something else. A second reader of the same
size brings that to 16 %, and an untrained Apertus 70B as the second reader to zero, at the price
of more questions to the operator.

## 2. Architecture

```
operator instruction ──> reader 1 ─┐                        ┌─ in the language ───────> rule engine ─┐
       (any language) ──> reader 2 ─┴─ same reading? ─ yes ─┤                                        ├─> allocation
                                          │ no              └─ outside it, or only in part ─> decider ┘
                                    ask the operator             (choice checked against the part carried)
request and network state ───────────────────────────────────────────────────────────────────┘
```

- **Simulator** (`src/sim.py`): Optical Networking Gym, preset `jocn_benchmark` (nobel-eu, 28
  nodes, 41 links, five candidate paths per request, 320 slots, six modulation formats). Each
  request is reduced to a **request view** (`src/view.py`): per candidate its hops, length, best
  modulation, slots needed, free slots and free blocks.
- **Policy language** (`src/spec.py`): one line of slots,
  `avoid=Berlin-Prague,Paris; via=Lyon; hops=4; km=any; path=any; prefer=km,load; rest=none`.
  Links and nodes to avoid, a node to pass through, limits on hops and length, one candidate by
  number, and preferences in order. `rest=more` marks an instruction of which only a part fits;
  `unsupported` and `no_instruction` are the two refusals. A name that is not a node of the
  network makes the instruction *unresolved*: it is not applied and the operator is told.
- **Readers** (`src/translate.py`): Apertus 8B with a LoRA adapter, decoding under a grammar
  built from the node list (`src/grammar.py`), so every answer is a line of the language.
- **Rule engine**: constraints filter the candidates (none left: reject), preferences then apply
  in the order stated. With a correct line it cannot break the instruction.
- **Decider** (`src/policies.py`): Apertus 8B with another adapter answers `path=1 slot=120` or
  `reject` from the request view and the instruction text. **Guard:** a path that breaks the
  constraints the line carries is replaced by the rule engine's choice.

### Target architecture (mandatory)

**a) On-premise**, and it runs **b) air-gapped**. At runtime the system is the network controller
(here the simulator) and one model server; nothing calls out. The server holds one base model,
quantised to 4 bits (5.1 GB), and three adapters of 160 MB (two readers, the decider), switched
per request. Measured on a laptop with an RTX 4060 (8 GB) under llama.cpp
(`results/design/readers3.json`): 0.89 s per instruction (95th percentile 1.03 s) and 0.97 s per
decision. A reader is called once per instruction, not per request; the decider only for
instructions outside the language (17 % of requests in our mixed stream). On an A100 with
Transformers the decider takes 64 ms of GPU time per decision in batches of 42
(`results/eval/apertus_ft.json`). Build-time dependencies (Python packages, the simulator's
source, the model weights) are fetched once; the container built by `make run` needs no network.

## 3. Use of Apertus

- **Model:** `andreasmartin/apertus-v1.5-8b-text`, the text-only conversion of
  `swiss-ai/Apertus-v1.5-8B` (the same language-model weights without the image components, so it
  loads with stock Transformers). The organisers answered on Discord (7 Oct 2026) that this is
  acceptable if the fine-tuned weights are published and the procedure is explained.
- **Three adapters** (QLoRA: 4-bit NF4 base, r = 32, α = 32, dropout 0.05 on six projection
  matrices per block, 79.7 M trainable parameters, effective batch 32, completion-only loss;
  `src/train.py`): the decider on 12,000 simulator decisions (two epochs, 138 min); two readers
  on 5,570 instructions each (one epoch, 34 min each, seeds and training samples differ).
  TODO: public links.
- **Decoding:** greedy, constrained token by token to the decision line or to the policy
  language (an automaton compiled from the grammar; the same grammar as GBNF for llama.cpp).
- **Serving:** Transformers inside Hugging Face Jobs (one A100) for training and evaluation;
  llama.cpp with our own 4-bit GGUF conversion of the base and GGUF adapters on the laptop. The
  prompt the laptop server renders is identical to the training prompt apart from the start
  token, which llama.cpp adds itself (`results/train/rendered_prompt3.txt`).
- **Larger Apertus as a reference and as a check:** Apertus 70B of both generations (4-bit GGUF,
  15 examples in the prompt, no training) translated the same test instructions under the same
  grammar, served by llama.cpp on the A100.
- **Other models:** none is part of the system or produced a result. Claude (Anthropic) wrote
  code and documentation under the author's direction, the sentence templates of the readers'
  training data, and, as separate instances that never saw the repository, the test instructions
  (section 4).

## 4. Data

Synthetic, no personal data; licence CDLA-Permissive-2.0; card in `data/README.md`.

| Data | Size | How it was made |
| --- | --- | --- |
| Decider, training | 12,000 decisions | simulator episodes (loads 150–390 Erlang, seeds 101–106) labelled by rule-based teachers; five intents, ten paraphrases each |
| Readers, training | 5,570 instructions per reader | templates in four languages filled with nodes and limits (`src/corpora3.py`); every clause alone, eight pairs, two preferences, refusals |
| Readers, test | 2,078 + 661 instructions | 168 sentences per language written by four separate AI instances from a brief that named the clause kinds and none of our wording; placed on held-out requests (seeds 107–108) |
| Closed loop | 6 episodes × 2,000 requests | traffic seeds 1–3, never trained on; 4,599 distinct instructions |

Three things were fixed before any test sentence was opened and committed first
(`src/corpora3.py`, commit `7ab1e66`): the training wording; which combinations of clauses are
trained (eight pairs) and which are held out (seven pairs, five triples); and four instruction
types that appear nowhere in training, not even as examples of a refusal (a modulation threshold,
"not the first candidate", a minimum of free slots, the largest free block). A request is used
for a test instruction when the instruction is *restrictive* there: at least one feasible path
complies and one does not. That depends on the instruction and the request only, not on any
policy.

## 5. Evaluation

**Protocol.** A decision *complies* when it lies in the set of paths the instruction allows; when
no path is allowed, only a reject complies. The rules that define this set also exist for the
four types outside the language, for scoring only. Closed loop: the no-intent teacher fills the
network for 1,000 requests, then the policy decides 2,000, each with an instruction; loads 240
and 390 Erlang (the teacher blocks 1.2 and 6.0 %), three seeds. Two choices that ignore the
instruction are scored everywhere: the first candidate that fits, and the decision without an
instruction. Tables: `results/tables/phase3.md`.

**Translate or decide.** Right meaning is counted per distinct instruction, four languages
together; decisions on 672 English requests (`results/offline/*_probes3.json`).

| | One clause | Pair seen in training | Pair never seen together | Three clauses, never seen together | All |
| --- | --- | --- | --- | --- | --- |
| Reader 1, instructions with the right meaning, % | 94.6 | 95.6 | 96.5 | 91.2 | 94.8 |
| Apertus 8B with 15 examples, no training, % | 89.5 | 81.0 | 91.1 | 85.6 | 87.2 |
| Decisions that comply: first candidate that fits, % | 70.6 | 63.3 | 62.5 | 57.5 | 66.8 |
| Decisions that comply: decider alone, % | 96.2 | 90.6 | 85.7 | 76.2 | 91.1 |
| Decisions that comply: reader 1 and rule engine, % | 99.4 | 100.0 | 99.1 | 100.0 | 99.6 |

The slots carry the composition: clauses the reader never saw together cost nothing. The
decider, which reads the instruction again for every request, loses ground with every clause.
By language the reader is right on 96.7 % (English), 91.4 % (German), 96.0 % (French) and 94.8 %
(Italian); with examples alone the same model reaches 94.6 % in English and 82.7 to 88.5 % in the
others, so training buys the other languages and halves the instructions applied with a wrong
meaning (9.6 to 4.6 %). Apertus 70B with the same examples and no training is right on 89.2 %
(generation 1.5; the first generation 71.9 %): the fine-tuned 8B, which runs on a laptop, reads
better than a model nine times its size.

**What the reader must not apply, and the second reader.** % of distinct instructions
(`results/design/readers3.json`); "left" is applied wrongly although two readers were compared.

| | Applied wrongly, reader 1 alone | Left with reader 2 (asked) | Left with the untrained 8B (asked) | Left with the untrained 70B (asked) |
| --- | --- | --- | --- | --- |
| Policy language | 4.6 | 3.7 (2.8) | 1.5 (12.7) | 0.2 (13.4) |
| Types never shown to any component | 46.6 | 16.2 (31.6) | 19.4 (44.7) | 0.0 (69.2) |
| Carried in part | 72.2 | 36.3 (50.9) | 33.0 (54.2) | 33.0 (53.3) |

A learned gate does not recognise what it was never shown: it writes almost half of the unknown
types as something the language has. Two readers of the same recipe share most misreadings. A
reader that differs catches more: the untrained 70B (generation 1.5) leaves 0.2 % inside the
language and none of the unknown types, of which it applies only 6.7 % itself. A larger model
earns its place as the check, not as the translator. Text that is no instruction is dropped in
96.7 %, a place outside the network flagged in 77.3 %.

**The fallback.** On the unknown types the decider alone complies as follows, on requests where
neither instruction-blind choice does (100 each, `v3_new_hard`): a minimum of free slots 98 %,
"not the first candidate" 75 %, the largest free block 11 %. It follows two of three and fails
where block sizes must be compared. A new constraint no path meets is rejected in 49.5 %. On
instructions carried in part the hybrid complies in 70.5 % with the guard and 63.5 % without
(decider alone 67.2 %, translator alone 68.0 %).

**Closed loop.** One stream mixes 45 % instructions in the language (four languages, a third of
them combinations never seen), 15 % unknown types, 10 % carried in part, 10 % text that is no
instruction, 5 % places outside the network and 15 % nothing. Violations, % of requests, three
seeds (`results/eval/*_mix3.json`):

| Policy, 390 Erlang | In the language | Unknown types | Carried in part | All requests | All, per seed |
| --- | --- | --- | --- | --- | --- |
| First fit (ignores the instruction) | 35.3 | 47.6 | 55.3 | 28.6 | 28.0 / 30.1 / 27.9 |
| Decider alone | 19.2 | 27.9 | 36.3 | 16.8 | 16.5 / 16.9 / 17.2 |
| Translator alone | 0.9 | 36.7 | 43.6 | 10.6 | 10.0 / 11.2 / 10.7 |
| Hybrid (with guard) | 1.0 | 31.6 | 40.4 | 9.5 | 8.5 / 10.3 / 9.9 |
| Hybrid that asks | 0.8 | 28.9 | 34.7 | 8.5 | 8.0 / 9.0 / 8.5 |

The order is the same in every seed and at 240 Erlang (16.4, 10.5, 8.7, 8.2). The hybrid that
asks puts a question to the operator for 8.9 % of requests and sends 17.3 % to the decider. Where
the instruction changes the right answer the decider alone breaks 42.6 % of the instructions in
the language and the hybrid 2.0 %.

**On the laptop.** With the 4-bit llama.cpp build reader 1 is right on 93.1 % of the 2,078
instructions (94.8 % in the job). A 50-request episode of the whole hybrid ran in 1 min 50 s;
`make run` replays it from the recorded answers.

**Earlier rounds** (`results/tables/results.md`, `phase1.md`, `phase2.md`). The decider was
built first. On the dataset's own wording it follows single intents with 0.1 to 3.3 % violations
at the teacher's blocking (6.4 against 6.0 %), where an MLP given the same numbers reaches 11.4 %
on "least loaded"; zero-shot the model is unusable (88 to 98 % invalid answers). A first training
pass rejected 14 % of avoid-link requests it could have served; we traced it to a rule in the
training labels, changed the rule, and the failure went. The translator came next: on independent
wording the decider broke 23.7 % of the instructions that mattered, a translator 2.0 %.

## 6. Limitations

- One topology in closed loop (a second one offline: 97.3 % right), one traffic model, one
  simulator. The model chooses among candidates the simulator has already checked for spectrum
  and quality of transmission; it ranks, it does not compute physics.
- Every test sentence but 22 was written by an AI model, not by an operator or a native speaker.
  Of 22 instructions typed by the author (`results/design/owner.json`, on the laptop) reader 1
  is right on 16 of 17 in English and on 2 of 5 in Urdu in Latin script, a language no reader
  was trained on; reader 2 disagrees with it on three of its four errors.
- Unknown types remain the weak point: the hybrid that asks still breaks 28.9 % of those requests
  in closed loop, and 65 % where the instruction changes the right answer.
- The share of each kind in the mixed stream is our choice. Limits are drawn at random, so part
  cannot be met; the reference that follows every instruction blocks 14.6 %.
- One training run per adapter. The simulated operator answers a question with the true meaning.
- Two readers of one recipe are a weak check inside the language; the better checks cost
  questions (12.7 to 30.3 % of instructions).
- The decider was not retrained in this round: it has never seen a limit, a node to avoid or two
  preferences, and it treats a constraint that cannot be met as a preference half of the time.
- Swiss German (72.7 % right) and misspelt names (85.9 %) are stress sets without training data.
- The 4-bit laptop build loses 1.7 points, more on combinations (three clauses: 83.8 %).
- The 70B ran from community 4-bit GGUF builds (generation 1.5: a text-only conversion by a Hub
  user) that we did not verify beyond their results; as a second reader it was scored on the test
  instructions, not in closed loop.

## 7. Reproducibility

`make run` rebuilds every table from the JSON files in `results/` in a container without a GPU
and replays a 50-request episode of the hybrid. Each results file records the command, the
simulator commit (`f7c4491`), seeds and loads; every model answer is in `results/cache/`. The
pipeline and the GPU steps are in `README.md` and `docs/gpu_runbook.md`; every deviation from the
plan, mistake and its cost in `docs/decisions.md`. Simulation, baselines and replays ran on a
laptop (WSL2); fine-tuning and evaluation as Hugging Face Jobs on one A100 80 GB: 15.3 GPU-hours
and about USD 38.36 over the three rounds (the third: 4.0 hours, USD 10.02, of which two readers
USD 3.14, evaluation USD 3.76, the two 70B runs USD 2.91). TODO: exact commit of the submission.

## 8. Next steps

Instructions written by operators; a gate that knows what it does not know (the second reader is
a first step); teaching the decider limits and rejects; standing policies with scope and
lifetime instead of one instruction per request; a second topology in closed loop; a
physical-layer model the simulator does not pre-digest.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References

- C. Natalino et al., "Optical Networking Gym", JOCN 16(12), G40 (2024).
- Doherty et al., "Hype or Hope?", JOCN 17(9), D1 (2025).
- NetLLM (SIGCOMM 2024); NetInspector (arXiv:2609.21103); VeriTrans (arXiv:2604.10341).
- Hamidieh et al., cross-model disagreement for uncertainty (2026); Qiu et al., model scale and
  compositional generalization in semantic parsing (2022).
