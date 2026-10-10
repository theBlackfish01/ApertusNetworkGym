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

Result after one epoch of training, at 390 Erlang over three seeds: with no intent the model
blocks as little as its teacher (5.85 % against 5.98 %). It follows the three ranking intents
with at most 1.5 % violations, where an MLP given the same numbers reaches 11.8 %, and wordings
it never saw cost nothing. On unseen intent pairs it violates 20 % of decisions against the
MLP's 29 %. On the avoid-link intent it fails: it almost never uses the forbidden link, but it
rejects 14 % of requests it could have served, which doubles the blocking. Zero-shot, the same
model is unusable: 88 to 98 % of its answers are not valid allocations.

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
of 42 (64 ms of GPU time per decision; `results/eval/apertus_ft.json`) and 0.37 s for a single
request (`results/cache/apertus_ft_demo.jsonl`). A 4-bit GGUF build for a laptop GPU or CPU is planned
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
  repository `blackfish021/apertus-lightpath-lora`, private until submission (TODO: make it
  public), and applies to that base model.
- **How it is used:** fine-tuning (QLoRA) and inference. No other model is used; the MLP control
  is trained from scratch on the same data.
- **Where it runs:** fine-tuning and evaluation as Hugging Face Jobs on one rented A100 80 GB;
  demo locally.
- **Prompt:** fixed system message, then the request, the intent, the network free ratio, one line
  per candidate path and the links of each path (example in `README.md`). Answer: one line.
- **Fine-tuning** (`src/train.py`): 4-bit NF4 base, LoRA r = 32, α = 32, dropout 0.05 on the six
  projection matrices of every block (q, k, v, o, up, down; 79.7 M trainable parameters, 0.98 %),
  learning rate 2e-4 with cosine decay and 5 % warm-up, 1 epoch (375 optimizer steps; two epochs
  were planned and the budget covered one), effective batch 32, bf16, completion-only loss,
  maximum length 768. Label ids 131072–131271 are masked
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
(I4); pairs combine by intersection. Ten paraphrases per intent, seven used in training.

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
only). Load 240 and the invalid-answer tables are in `results/tables/results.md`; the blocking
of every condition at both loads is `docs/figures/blocking.png`.

Intent violations, % of decisions:

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
| --- | --- | --- | --- | --- | --- | --- |
| First fit (ignores intents) | 24.5 ± 0.9 | 10.4 ± 0.3 | 43.2 ± 2.4 | 0.1 ± 0.1 | 19.3 ± 1.5 | 33.9 ± 2.2 |
| No-intent teacher | 25.8 ± 1.3 | 18.4 ± 1.2 | 34.7 ± 1.0 | 2.0 ± 0.3 | 20.3 ± 0.8 | 33.5 ± 1.0 |
| Intent-aware teacher (oracle) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MLP control | 0.9 ± 0.2 | 2.4 ± 0.2 | 11.8 ± 0.4 | 0.1 ± 0.1 | 3.7 ± 0.2 | 28.7 ± 1.5 |
| Apertus 8B zero-shot | 28.1 | 10.2 | 42.1 | 0.1 | 19.2 | 32.6 |
| Apertus 8B fine-tuned | 17.5 ± 0.5 | 0.5 ± 0.1 | 1.5 ± 0.2 | 0.1 ± 0.1 | 3.4 ± 0.4 | 20.4 ± 0.3 |

Service blocking probability, %:

| Policy | No intent | Avoid link | Least loaded | Unseen wording | Unseen pairs |
| --- | --- | --- | --- | --- | --- |
| First fit | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 | 8.23 ± 0.80 |
| No-intent teacher | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 | 5.98 ± 0.65 |
| Intent-aware teacher (oracle) | 5.97 ± 0.68 | 9.95 ± 0.75 | 6.30 ± 0.80 | 7.73 ± 0.58 | 14.65 ± 1.26 |
| MLP control | 6.28 ± 0.85 | 9.37 ± 0.91 | 6.27 ± 0.58 | 7.78 ± 0.63 | 7.90 ± 0.98 |
| Apertus 8B zero-shot | 9.20 | 14.60 | 9.05 | 9.05 | 9.25 |
| Apertus 8B fine-tuned | 5.85 ± 0.71 | 21.43 ± 1.07 | 6.43 ± 0.86 | 9.33 ± 0.55 | 15.80 ± 1.05 |

Following an intent costs capacity: the oracle blocks 9.95 % when every request must avoid a
link and 14.65 % on unseen pairs, against 5.97 % with no intent, so blocking is read next to the
violation rate, never alone. The rows that ignore intents show how often an intent matters: the
no-intent teacher's violation rate is the share of requests on which the intent binds.

**What works.** With no intent the fine-tuned model blocks like its teacher. It follows the
three ranking intents with 0.1 to 1.5 % violations at the oracle's blocking; on "least loaded"
the MLP, given the same numbers, violates 11.8 %. Wordings never seen in training cost nothing
(3.4 % against 3.7 % for the MLP, which does not read the wording). At most 0.6 % of its answers
in any condition are invalid.

**What works partly.** On unseen intent pairs it violates 20.4 % of decisions (24.2 % at 240
Erlang) against 28.7 % (31.2 %) for the MLP: pretraining helps with composition, and a fifth of
the decisions are still wrong. Its blocking is close to the oracle's, while the MLP's low
blocking comes from serving requests the intents forbid.

**What fails.** Under "avoid link", an intent it was trained on, it violates 17.5 % (18.4 % at
240 Erlang) where the MLP violates 0.9 %. Replaying the episodes from the answer cache
(`results/design/closed_loop_failures_apertus_ft.json`) shows the kind of error: it routes
through the forbidden link in only 1.6 % of decisions, but it rejects 14 % of requests that had
an admissible path, more often the fewer paths remain (6 to 7 % with four admissible paths left,
24 to 33 % with one or two). Blocking rises to 21.4 % against the oracle's 9.95 %.

**Zero-shot.** Between 88 and 98 % of the base model's answers are not valid actions, so the
first-fit fallback decides and the row repeats first fit. The prompt alone does not carry the
task; the adapter does.

Over all requests on which an intent binds, the fine-tuned model violates 20.7 % and the MLP
23.0 % (`results/tables/results.md`): similar totals from different failures.

Offline agreement with the teacher on the held-out splits, admissible answers in %
(`results/offline/`):

| Policy | New traffic | Unseen wording | Unseen pairs |
| --- | --- | --- | --- |
| MLP control | 96.4 | 95.7 | 70.0 |
| Apertus 8B zero-shot | 3.3 | 2.5 | 4.8 |
| Apertus 8B fine-tuned | 95.8 | 95.7 | 78.0 |
| Apertus 8B fine-tuned, no answer constraint | 95.9 | 95.7 | 77.5 |

Without the answer constraint none of the fine-tuned model's 2,200 answers is malformed or
invalid, so it learned the format itself. Per intent it beats the MLP on "least loaded" (97 to
98 % against 85 to 89 %) and on the unseen pair of two ranking rules (79.0 against 55.4 %), and
loses on "avoid link" (84 to 90 % against 98 to 99 %) and on the unseen pair that contains it
(75.9 against 86.0 %).

## 6. Limitations

- One topology, one traffic model, one simulator; results say nothing yet about other networks.
- The model chooses among candidates the simulator has already checked for spectrum and quality
  of transmission. It ranks; it does not compute physics.
- Two of the four intents (fewest hops, fewest slots) are usually satisfied by the shortest
  candidate, so they are an easy test (`data/stats.json`).
- Intent pairs combine by intersection, which forces a reject whenever no path satisfies both;
  blocking under pairs is therefore dominated by the rule, not by the network.
- Teachers are heuristics, so the model can at best match them; we measure imitation and intent
  following, not optimal provisioning.
- The model was trained for one epoch instead of the planned two (budget). Its failure on
  "avoid link" is over-rejection (section 5). A possible cause, not tested: in the training pairs
  that contain "avoid link" the correct answer is `reject` 19 to 28 % of the time. A second
  epoch or a different pair rule may or may not remove it.
- The zero-shot model was evaluated in closed loop on one seed at 390 Erlang only.
- The loss curve during training was monitored on 200 held-out records that are almost all from
  the lightest load; the reported agreement uses all 2,200.
- Decision latency is that of batched Transformers calls inside a job, not of a tuned server.

## 7. Reproducibility

`make run` rebuilds every table from the JSON files in `results/` in a container without a GPU
and runs a 50-request demo. Each results file records the command, the ONG commit
(`f7c4491`), the repository commit, seeds and loads. The full pipeline and the GPU steps are in
`README.md` and `docs/gpu_runbook.md`; deviations from the plan, with the measurements behind
them, in `docs/decisions.md`. Simulation and the CPU baselines ran on a laptop (WSL2, 16
logical CPUs). Fine-tuning and evaluation ran as Hugging Face Jobs on one NVIDIA A100 80 GB:
3.5 GPU-hours and USD 8.70 in total (smoke test 9 min, fine-tuning 69 min, evaluation 131 min).
TODO: exact commit of the submission.

AI assistance: code and documentation were written with Claude Code (Anthropic) under the
author's direction; the author reviewed the results before use.

## 8. Next steps

More topologies and a physical-layer model the simulator does not pre-digest; intents with
quantities ("keep at least 20 % of this link free"); letting the model explain a reject; a
comparison with a reinforcement-learning agent under the same protocol.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References

- C. Natalino et al., "Optical Networking Gym", JOCN 16(12), G40 (2024).
- Doherty et al., "Hype or Hope?", JOCN 17(9), D1 (2025).
- NetLLM (SIGCOMM 2024); Trailblazer (arXiv:2512.11839).
- Jiang et al., NeurIPS 2025 (arXiv:2509.16865).
