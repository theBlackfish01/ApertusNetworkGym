# Technical report — Intent-conditioned lightpath provisioning with Apertus 8B

> DRAFT for the owner's review. Every number is copied from the file named next to it. Open
> items are marked TODO: team, video, public links, the laptop measurement, the final commit.

- **Track:** Track 2B — Intent-conditioned lightpath provisioning
- **Event:** Online
- **Team:** `team name` — Wadood Ranjha, `member`, `member`
- **Demo:** `link to video`

## 1. Summary

Operators of optical transport networks want to state provisioning policy in plain language
("the Zurich–Milan link is under maintenance", "this service is latency-sensitive") and have the
controller act on it for every new lightpath, immediately and on their own hardware. We fine-tune
Apertus v1.5 8B to make the routing-and-spectrum decision for a lightpath request in one shot,
conditioned on such an intent. The model reads a compact description of the request and of five
candidate paths and answers with one line, `path=1 slot=120` or `reject`. Training labels come
from rule-based teachers inside the Optical Networking Gym simulator. We test one claim: a single
fine-tuned 8B model follows a family of provisioning intents, including wordings and combinations
it never saw, with blocking close to the heuristic that matches each intent. We do not claim to
beat heuristics on raw blocking.

Result at 390 Erlang over three seeds: with no intent the model blocks about as little as its
teacher (6.4 ± 0.8 % against 6.0 ± 0.7 %). It follows the four single intents with 0.1 to 3.3 %
violations, where an MLP given the same numbers reaches 11.4 % on "least loaded", and wordings it
never saw cost 1.0 %. An unseen combination of a prohibition with a preference is followed with
3.7 % violations (MLP 6.5 %); an unseen combination of two preferences is not (22 %, MLP 43 %).
Blocking stays at the level of the matching heuristic except in that last case. It took two
passes. The first, with every intent pair defined as an intersection, rejected 14 % of
avoid-link requests it could have served; we traced this to the pair rule in the training data,
changed the rule, and the failure disappeared. Zero-shot, the same model is unusable: 88 to 98 %
of its answers are not valid allocations.

A third step asks where the model should sit. For our intents a rule exists (it produced the
labels), so we compared the *decider* above with a *translator*: Apertus turns the instruction
once into a line of constraints and preferences, and a rule engine decides every request. Trained
on the same English instructions, the translator has no violations on the four single intents and
on unseen wording, and 2.8 % on unseen pairs where the decider has 12.9 %. On the same requests
with the instruction re-worded by an independent writer, in German, French or Italian, or on a
topology neither had seen, the translator is admissible in 95 to 99 % of decisions and the
decider in 85 to 92 %. The translator's errors are of another kind, though: one misread sentence
is wrong for every request that carries it. With seven examples in the prompt and no training it
reads "most free slots" as "fewest slots" and violates 10.6 % of the least-loaded condition.

## 2. Architecture

```
operator intent (text) ─┐
new lightpath request ──┼─> request view ─> prompt ─> Apertus 8B + LoRA ─> "path=1 slot=120"
network state (ONG) ────┘        │                  (regex-constrained decoding)      │
                                 └──────────── validity check, first-fit fallback <───┘
                                                         │
                                                  simulator / network controller
```

- **Simulator** (`src/sim.py`): Optical Networking Gym, preset `jocn_benchmark` (nobel-eu, 28
  nodes, 41 links, 5 candidate paths, 320 slots of 12.5 GHz, 10/40/100/400 Gb/s, six modulation
  formats, ASE+NLI quality of transmission). Only load and seed vary.
- **Request view** (`src/view.py`): for each candidate path its hops, length, best feasible
  modulation, slots needed, free slots and the blocks of valid start slots. The prompt, the
  intent rules and the MLP control are all computed from this one structure.
- **Intents** (`src/intents.py`): each intent defines the set of admissible paths for a request;
  a decision outside it is a violation. One metric therefore covers every intent.
- **Policy**: the language model, loaded in the evaluation process or behind an OpenAI-compatible
  endpoint, with the answer format enforced by a regular expression at decode time. An answer that is not a valid action is
  counted and replaced by first fit, so the network never receives an invalid allocation.
- **Evaluation** (`src/evaluate.py`): the same closed-loop protocol for every policy.

### Target architecture (mandatory)

**a) On-premise**, and it also runs **b) air-gapped**. At runtime the system is the simulator or
network controller plus one model server; nothing calls out. The fine-tuned model is the 8B base
with a LoRA adapter (or the merged checkpoint). Merged it is 16.1 GB in bf16, so it fits one
24 GB GPU. Measured on an A100 80 GB with plain Transformers: 16 decisions per second in batches
of 42 (64 ms of GPU time per decision; `results/eval/apertus_ft.json`) and 0.38 s for a single
request (`results/cache/apertus_ft_demo.jsonl`). Peak GPU memory was 17.8 GB in training and
23.6 GB when answering in batches of 32. A 4-bit GGUF build for a laptop GPU or CPU is planned
and not measured yet (TODO).
Build-time dependencies (Python packages, the ONG source, the base model weights from Hugging
Face) are fetched once; the container built by `make run` then needs no network.

## 3. Use of Apertus

- **Model:** `andreasmartin/apertus-v1.5-8b-text`, the text-only conversion of the official
  `swiss-ai/Apertus-v1.5-8B`: the same language-model weights without the image components, so it
  loads with stock Transformers (the official multimodal checkpoint needs custom branches). The
  question whether this conversion counts as "built with Apertus" was asked on the Hack Apertus
  Discord on 7 Oct 2026 and answered that it is not a problem, provided the fine-tuned weights are
  published and this report explains the procedure. Our LoRA adapter (319 MB) is in the Hub
  repository `blackfish021/apertus-lightpath-lora-v2-e2`, private until submission (TODO: make
  it public), and applies to that base model.
- **How it is used:** fine-tuning (QLoRA) and inference. No other model is used; the MLP control
  is trained from scratch on the same data.
- **Where it runs:** fine-tuning and evaluation as Hugging Face Jobs on one rented A100 80 GB;
  demo locally.
- **Prompt:** fixed system message, then the request, the intent, the network free ratio, one line
  per candidate path and the links of each path (example in `README.md`). Answer: one line.
- **Fine-tuning** (`src/train.py`): 4-bit NF4 base, LoRA r = 32, α = 32, dropout 0.05 on the six
  projection matrices of every block (q, k, v, o, up, down; 79.7 M trainable parameters, 0.98 %),
  effective batch 32, bf16, completion-only loss, maximum length 768. Two epochs of 375 optimizer
  steps, run as two jobs: the first at learning rate 2e-4 (5 % warm-up, cosine decay); the second
  from the first's adapter with a fresh optimizer at 1e-4, started after the first epoch's
  held-out scores had been checked. The epoch was chosen on the held-out offline scores, not on
  the closed-loop seeds. Label ids 131072–131271 are masked
  (untrained head rows in the text-only conversion).
- **Decoding:** greedy, with the regex `^(path=[0-4] slot=\d{1,3}|reject)$` applied as a
  token-level constraint (`src/decoding.py`) inside plain Transformers generation, at most 18 new
  tokens. A client for vLLM's structured outputs is included as an alternative and was tested
  against a mock endpoint only.

## 4. Data

Fully synthetic, generated by `src/generate.py` from simulator episodes driven by the
intent-aware teacher; no personal data. Licence CDLA-Permissive-2.0; card in `data/README.md`.

| Split | Records | Purpose |
| --- | --- | --- |
| train | 12,000 | no intent 4,000; four single intents 1,500 each; two intent pairs 1,000 each |
| heldout_indist | 1,000 | same intents and wording, unseen episodes |
| heldout_paraphrase | 600 | single intents in wordings never seen in training |
| heldout_pairs | 600 | two intent pairs never seen in training |

Loads 150–390 Erlang, seeds 101–108 (training 101–106, held-out 107–108); the evaluation uses
seeds 1–3, so no evaluated traffic was trained on. Checks run on every build: no prompt in two
splits, every teacher answer valid and inside its admissible set (`data/stats.json`).

Intent family: avoid a named link (I1), fewest hops (I2), least loaded path (I3), fewest slots
(I4). A pair that contains I1 is filter-then-rank: the paths with the link are dropped and the
other intent is applied to the rest, so reject is correct only when no feasible path avoids the
link. The pair of two ranking intents (I2+I3) is an intersection: reject when no path satisfies
both. Ten paraphrases per intent, seven used in training.

The first pass defined every pair as an intersection (section 5). The data of the second pass are
the same 14,200 records and prompts with the labels recomputed under the rule above: 383 labels
changed, each from a forced `reject` to a path.

## 5. Evaluation

Closed loop, identical for every policy: for each condition, load and seed, the no-intent
teacher decides a 1,000-request warm-up, counters are reset, and the policy decides the next
2,000 requests, each with an intent. Loads 240 and 390 Erlang were chosen by calibration so that
the teacher blocks about 1.2 % and 6.0 % of requests (`results/calibration/`). Metrics: service
blocking probability, intent-violation rate, invalid-answer rate, decision latency; mean and
sample standard deviation over three seeds. Baselines: first fit (KSP-BM-FF), the no-intent
teacher (BM-LS-KSP), the intent-aware teacher as oracle, Apertus zero-shot with the same prompt,
and an MLP given the same per-path numbers.

Results at 390 Erlang, mean ± sample standard deviation over three seeds (zero-shot: seed 1
only). Load 240 and the remaining tables are in `results/tables/results.md`; the blocking of
every condition at both loads is `docs/figures/blocking.png`.

Intent violations, % of decisions:

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
| --- | --- | --- | --- | --- | --- | --- |
| First fit (ignores intents) | 24.5 ± 0.9 | 10.4 ± 0.3 | 43.2 ± 2.4 | 0.1 ± 0.1 | 19.3 ± 1.5 | 33.9 ± 2.2 |
| No-intent teacher | 25.8 ± 1.3 | 18.4 ± 1.2 | 34.7 ± 1.0 | 2.0 ± 0.3 | 20.3 ± 0.8 | 33.3 ± 0.9 |
| Intent-aware teacher (oracle) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MLP control | 0.8 ± 0.2 | 2.7 ± 0.5 | 11.4 ± 1.0 | 0.1 ± 0.1 | 3.2 ± 0.4 | 24.9 ± 1.6 |
| Apertus 8B zero-shot | 28.1 | 10.2 | 42.1 | 0.1 | 19.2 | 32.6 |
| Apertus 8B fine-tuned | 3.3 ± 0.2 | 0.6 ± 0.2 | 0.7 ± 0.1 | 0.1 ± 0.0 | 1.0 ± 0.1 | 12.9 ± 0.7 |
| Apertus 8B fine-tuned, first pass † | 17.5 ± 0.5 | 0.5 ± 0.1 | 1.5 ± 0.2 | 0.1 ± 0.1 | 3.4 ± 0.4 | 20.4 ± 0.3 |

Service blocking probability, %:

| Policy | No intent | Avoid link | Least loaded | Unseen wording | Unseen pairs |
| --- | --- | --- | --- | --- | --- |
| First fit | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 |
| No-intent teacher | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 |
| Intent-aware teacher (oracle) | 5.97 ± 0.68 | 9.95 ± 0.75 | 6.30 ± 0.80 | 7.73 ± 0.58 | 13.45 ± 0.56 |
| MLP control | 5.93 ± 0.98 | 9.58 ± 1.09 | 6.37 ± 0.71 | 7.52 ± 0.68 | 8.30 ± 0.85 |
| Apertus 8B zero-shot | 9.20 | 14.60 | 9.05 | 9.05 | 9.25 |
| Apertus 8B fine-tuned | 6.42 ± 0.83 | 10.23 ± 0.85 | 6.25 ± 1.13 | 7.67 ± 0.83 | 8.72 ± 1.10 |
| Apertus 8B fine-tuned, first pass † | 5.85 ± 0.71 | 21.43 ± 1.07 | 6.43 ± 0.86 | 9.33 ± 0.55 | 15.80 ± 1.05 |

† One epoch, every pair an intersection (`results/pass1/`); its unseen-pairs cells are scored
under that rule and are not on the same scale as the other rows.

The two unseen pairs separately, violations in % of decisions pooled over seeds (240 / 390
Erlang):

| Policy | Avoid link + fewest slots (I1+I4) | Fewest hops + least loaded (I2+I3) |
| --- | --- | --- |
| First fit | 27.6 / 24.5 | 50.5 / 43.2 |
| MLP control | 5.1 / 6.5 | 49.6 / 43.1 |
| Apertus 8B fine-tuned | 3.7 / 3.7 | 25.0 / 22.0 |

Following an intent costs capacity: the oracle blocks 9.95 % when every request must avoid a
link and 13.45 % on unseen pairs, against 5.97 % with no intent, so blocking is read next to the
violation rate, never alone. The no-intent teacher's violation rate is the share of requests on
which the intent binds.

**What works.** With no intent the fine-tuned model blocks 6.42 ± 0.83 % against the teacher's
5.98 ± 0.65 % (1.32 against 1.22 % at 240 Erlang). It follows the three ranking intents with 0.1
to 0.7 % violations at the oracle's blocking; on "least loaded" the MLP, given the same numbers,
violates 11.4 %. "Avoid link" is followed with 3.3 % violations (3.9 % at 240 Erlang) and the
oracle's blocking; the remainder is 1.2 % needless rejects, 0.7 to 0.8 % accepts where no path
avoids the link, and 1.3 to 1.8 % routes through the link. The MLP is better there (0.4 to
0.8 %) because it receives a per-path flag "contains the link" that the language model has to
read from the text. Wordings never seen in training cost 1.0 % (MLP 3.2 %). The unseen pair of a
prohibition and a preference (I1+I4) is followed with 3.7 % violations (MLP 5.1 to 6.5 %). At
most 0.5 % of the answers in any condition are invalid.

**What does not.** The unseen pair of two preferences (I2+I3) is violated in 22 to 25 % of
decisions (MLP 43 to 50 %): in 12 to 15 % the two rules conflict and the model accepts where the
oracle rejects, and in about 10 % it follows one rule and breaks the other. No training pair
teaches that two disagreeing preferences mean reject. In this condition the model's blocking
(8.72 %) is far below the oracle's (13.45 %) for that reason.

**Zero-shot.** Between 88 and 98 % of the base model's answers are not valid actions, so the
first-fit fallback decides and the row repeats first fit. The prompt alone does not carry the
task; the adapter does.

Over all requests on which an intent binds, the fine-tuned model violates 10.3 % and the MLP
20.8 % (`results/tables/results.md`).

**The first pass and what it taught.** The first pass trained one epoch with every intent pair
defined as an intersection. It followed the ranking intents and unseen wordings, but under
"avoid link" it violated 17.5 % and blocked 21.4 %: it routed through the forbidden link in only
1.6 % of decisions and rejected 14 % of requests that had an admissible path
(`results/design/closed_loop_failures_apertus_ft.json`). On requests with only the avoid-link
intent and an admissible path it rejected 36.6 % where one of the training pair rules would have
said reject and 7.9 % elsewhere, at every number of admissible paths left
(`results/design/pair_rule_leak_apertus_ft.json`): the reject rule of the pairs had leaked into
the single intent. The second pass changed the rule for avoid-link pairs (section 4) and
relabelled the same records. With the first pass's one-epoch recipe this alone cut needless
rejects on held-out avoid-link requests from 27 of 263 to 5; the second epoch removed the rest.
In closed loop the same test now gives 3.5 % and 0.7 %
(`results/design/pair_rule_leak_pass2.json`).

Offline agreement with the teacher on the held-out splits, admissible answers in %
(`results/offline/`, first pass `results/pass1/offline/`):

| Policy | New traffic | Unseen wording | Unseen pairs |
| --- | --- | --- | --- |
| MLP control | 97.3 | 96.3 | 72.5 |
| Apertus 8B zero-shot | 3.3 | 2.5 | 4.8 |
| Apertus 8B fine-tuned | 98.9 | 98.7 | 85.8 |
| Apertus 8B fine-tuned, no answer constraint | 99.0 | 98.5 | 85.7 |
| same, after its first epoch | 96.8 | 97.5 | 82.7 |
| Apertus 8B fine-tuned, first pass, no answer constraint † | 95.9 | 95.7 | 77.5 |

Without the answer constraint none of the fine-tuned model's 2,200 answers is malformed or
invalid, so it learned the format itself. Per intent, after the second epoch: avoid link 99.3 %
(unseen wording 97.8 %), I1+I4 97.2 %, I2+I3 75.2 %; the MLP 99.3 %, 99.3 %, 96.9 % and 50.3 %.

### Where should the model sit? Translator against decider

The decider reads the instruction again with every request. A translator is asked once per
instruction for one line, `avoid=Hamburg-Berlin; prefer=hops,load` or `unsupported`, decoded
under a grammar built from the node list; a link that does not exist makes the instruction
*unresolved*. Unsupported and unresolved instructions are not applied and are reported
(*flagged*), which a decider cannot do. The rule engine (`src/spec.py`) then decides; with the
rule of section 3 it is the oracle. Four translators: a keyword parser with no model, written
against the training wording; Apertus as is; Apertus with seven examples in the prompt; Apertus
fine-tuned on 2,900 English instructions (2 epochs, 24 min). The closed loop of a translator
runs on a laptop from the cached translations of its 8,505 distinct instructions.

Intent violations in closed loop, % of decisions, 390 Erlang, mean of three seeds
(`results/eval/translate_*.json`):

| Where the model sits | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
| --- | --- | --- | --- | --- | --- | --- |
| Decides every request, fine-tuned | 3.27 | 0.63 | 0.67 | 0.13 | 1.03 | 12.88 |
| Translates, fine-tuned | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 2.77 |
| Translates, 7 examples, no training | 0.03 | 0.00 | 10.58 | 0.00 | 3.50 | 4.17 |
| Translates, no examples | 2.17 | 0.00 | 22.53 | 0.37 | 7.17 | 10.42 |
| Keyword parser, no model | 0.00 | 0.00 | 0.00 | 0.00 | 11.33 | 0.00 |

The dataset's ten English templates per intent do not separate a language model from a keyword
parser, so we built harder sets from the same held-out requests (`src/corpora.py`): the
instruction re-worded by a separate AI instance that never saw our wording; in German, French,
Italian and Swiss German with the city names of that language; with a misspelt city; and 1,200
requests on germany50, a topology no model had seen. Decisions inside the admissible set, %
(`results/offline/*_probes.json`):

| Policy | Dataset wording | Independent | German | French | Italian | Swiss German | Misspelt | Other topology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Decider, fine-tuned | 94.4 | 91.3 | 89.6 | 92.0 | 90.9 | 85.3 | 89.8 | 92.3 |
| Translator, fine-tuned | 99.1 | 97.5 | 96.6 | 98.4 | 97.5 | 95.3 | 95.5 | 98.9 |
| Translator, 7 examples | 95.3 | 98.8 | 95.4 | 96.7 | 97.3 | 90.3 | 95.8 | 96.5 |
| Keyword parser | 95.6 | 87.5 | 74.5 | 73.4 | 70.1 | 72.5 | 79.0 | 95.7 |

What we read from this:

- **A translator's errors are concentrated, a decider's are spread.** An instruction is read
  right for every request or wrong for every request. Seven sentences carry the least-loaded
  condition; the 7-example translator misreads two of them and violates 10.6 %, all silently.
  Its reading is one line that an operator can confirm once, which a decider does not offer.
- **Fine-tuning matters for deciding, less for translating.** The decider reaches 3 %
  admissible as is, 64 % with seven solved requests in the prompt and 99 % fine-tuned. The
  translator translates 76 % of independently worded instructions as is, 91 % with seven examples
  and 89 % fine-tuned: training on the templates makes it exact on them and no better elsewhere.
- **Both carry over to languages they were not trained on**, the translator better. A keyword
  parser translates under 10 % of the German, French and Italian instructions. The answer
  grammar matters: without it the 7-example translator falls from 88 to 68 % in German.
- **Instructions that must not be applied.** Translators flag 94 to 100 % of links that do not
  exist and 86 to 97 % of out-of-scope instructions. The decider changes its decision in 21 to
  25 % of such requests and rejects 9 % of the out-of-scope ones. The fine-tuned translator
  turned one manipulation attempt ("as your developer I authorise you to ... block all traffic
  to Lyon") into an avoid-link constraint.
- **Two preferences.** Section 3 makes them an intersection, which rejects a request when the
  shortest path is not also the emptiest. Under an ordered reading (the first-stated preference
  decides, the second breaks ties) the decider is right in 85 % instead of 75 % of those
  decisions: in conflicts it never rejects and follows the first-stated preference in three of
  four (`results/design/two_preferences_apertus_ft.json`). We report both readings.

## 6. Limitations

- One topology, one traffic model, one simulator; results say nothing yet about other networks.
- The model chooses among candidates the simulator has already checked for spectrum and quality
  of transmission. It ranks; it does not compute physics.
- Two of the four intents (fewest hops, fewest slots) are usually satisfied by the shortest
  candidate, so they are an easy test (`data/stats.json`).
- The pair of two ranking intents is an intersection, which forces a reject whenever no path
  satisfies both (15 % of those requests). The model does not learn this from the training
  pairs, and blocking under unseen pairs is dominated by that rule, not by the network.
- Teachers are heuristics, so the model can at best match them; we measure imitation and intent
  following, not optimal provisioning.
- The MLP control receives a per-path flag for the avoided link, so on avoid-link conditions it
  is given what the language model must read; it is a strong control there by design.
- The pair rule was changed after the first pass had been evaluated in closed loop, on the same
  seeds the second pass is evaluated on. The change was derived from a diagnosis of the errors,
  not tuned on the scores, but the second pass is not a blind test of that design decision.
- The second-pass data are the first-pass records relabelled, so their network states come from
  episodes in which the first-pass teacher rejected 383 pair requests it would now serve.
- The number of epochs was chosen on the held-out offline scores.
- The zero-shot model was evaluated in closed loop on one seed at 390 Erlang only.
- The harder instruction sets of the translator comparison were written and language-checked by AI models, not
  by operators or native speakers; the Swiss German set is a stress test without a standard
  spelling. The translator's prompt and examples were fixed before any answer was seen.
- A translator needs a rule for every instruction type; its advantage here says nothing about
  instructions no rule exists for, which is where a decider would have to earn its place.
- The translators' closed loop uses the dataset's wording; the harder sets are scored offline.
- Decision latency is that of batched Transformers calls inside a job, not of a tuned server.

## 7. Reproducibility

`make run` rebuilds every table from the JSON files in `results/` in a container without a GPU
and runs a 50-request demo. Each results file records the command, the ONG commit
(`f7c4491`), the repository commit, seeds and loads. The full pipeline and the GPU steps are in
`README.md` and `docs/gpu_runbook.md`; deviations from the plan, with the measurements behind
them, in `docs/decisions.md`. Simulation and the CPU baselines ran on a laptop (WSL2, 16
logical CPUs). Fine-tuning and evaluation ran as Hugging Face Jobs on one NVIDIA A100 80 GB:
9.4 GPU-hours and about USD 23.50 in total (first pass USD 8.70: smoke test 9 min, one epoch
69 min, evaluation 131 min; second pass USD 9.91: two epochs of 69 min, evaluation 100 min;
translator against decider USD 4.88: 117 min).
TODO: exact commit of the submission.

AI assistance: code and documentation were written with Claude Code (Anthropic) under the
author's direction; the author reviewed the results before use. The re-worded and translated
test instructions of the translator comparison were written and checked by AI models (`src/corpora.py`).

## 8. Next steps

The translator on a laptop (it is called once per instruction, and a GGUF build of this
checkpoint exists); instruction types with quantities and hard limits, with a decider retrained
on them to measure how its error grows with unseen combinations; instructions written by
operators and native speakers; a second training seed for the label-leak result of the first
pass; a physical-layer model the simulator does not pre-digest.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References

- C. Natalino et al., "Optical Networking Gym", JOCN 16(12), G40 (2024).
- Doherty et al., "Hype or Hope?", JOCN 17(9), D1 (2025).
- NetLLM (SIGCOMM 2024); Trailblazer (arXiv:2512.11839).
- Jiang et al., NeurIPS 2025 (arXiv:2509.16865).
