# Technical report — Intent-conditioned lightpath provisioning with Apertus 8B

> DRAFT for the owner's review. Method, data and protocol sections describe what is built and
> measured. Everything about the fine-tuned and zero-shot Apertus models is still to be filled
> in from `results/` after the GPU runs; those places are marked TODO. Numbers in this file are
> copied from the files named next to them.

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
beat heuristics on raw blocking. TODO: headline result (violation rate and blocking of the
fine-tuned model against the oracle, the zero-shot model and the MLP control).

## 2. Architecture

```
operator intent (text) ─┐
new lightpath request ──┼─> request view ─> prompt ─> Apertus 8B + LoRA ─> "path=1 slot=120"
network state (ONG) ────┘        │                     (vLLM, regex-constrained)      │
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
- **Policy**: the language model behind an OpenAI-compatible endpoint, with the answer format
  enforced by a regular expression at decode time. An answer that is not a valid action is
  counted and replaced by first fit, so the network never receives an invalid allocation.
- **Evaluation** (`src/evaluate.py`): the same closed-loop protocol for every policy.

### Target architecture (mandatory)

**a) On-premise**, and it also runs **b) air-gapped**. At runtime the system is the simulator or
network controller plus one model server; nothing calls out. The fine-tuned model is the 8B base
with a LoRA adapter (or the merged checkpoint): it fits one 24 GB GPU in bf16 and runs as a 4-bit
GGUF build on a laptop GPU or CPU. TODO: measured memory and decisions per second on each.
Build-time dependencies (Python packages, the ONG source, the base model weights from Hugging
Face) are fetched once; the container built by `make run` then needs no network.

## 3. Use of Apertus

- **Model:** `andreasmartin/apertus-v1.5-8b-text`, the text-only conversion of
  `swiss-ai/Apertus-v1.5-8B` (same backbone weights, loads with stock Transformers). TODO: state
  the organisers' answer on whether the conversion is accepted, or switch to the official
  checkpoint.
- **How it is used:** fine-tuning (QLoRA) and inference. No other model is used; the MLP control
  is trained from scratch on the same data.
- **Where it runs:** fine-tuning and evaluation serving on one rented A100 80 GB; demo locally.
- **Prompt:** fixed system message, then the request, the intent, the network free ratio, one line
  per candidate path and the links of each path (example in `README.md`). Answer: one line.
- **Fine-tuning** (`src/train.py`): 4-bit NF4 base, LoRA r = 32, α = 32, dropout 0.05 on the seven
  projection matrices, learning rate 2e-4 with cosine decay and 5 % warm-up, 2 epochs, effective
  batch 32, bf16, completion-only loss, maximum length 768. Label ids 131072–131271 are masked
  (untrained head rows in the text-only conversion).
- **Serving:** vLLM with the regex `^(path=[0-4] slot=\d{1,3}|reject)$` as structured output,
  temperature 0, at most 16 new tokens.

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

TODO: paste the tables of `results/tables/results.md` and `docs/figures/blocking.png` once the
Apertus rows exist. The baselines are complete (`results/tables/results.md`, load 390 E, mean ±
std over seeds):

| Policy | Blocking %, no intent | Violations %, avoid link | Violations %, least loaded | Violations %, unseen pairs |
| --- | --- | --- | --- | --- |
| First fit (ignores intents) | 8.23 ± 0.80 | 24.5 ± 0.9 | 43.2 ± 2.4 | 33.9 ± 2.2 |
| No-intent teacher | 5.98 ± 0.65 | 25.8 ± 1.3 | 34.7 ± 1.0 | 33.5 ± 1.0 |
| Intent-aware teacher (oracle) | 5.97 ± 0.68 | 0.0 | 0.0 | 0.0 |
| MLP control | 6.28 ± 0.85 | 0.9 ± 0.2 | 11.8 ± 0.4 | 28.7 ± 1.5 |
| Apertus 8B zero-shot | TODO | TODO | TODO | TODO |
| Apertus 8B fine-tuned | TODO | TODO | TODO | TODO |

Following an intent costs capacity: the oracle blocks 9.95 ± 0.75 % when every request must
avoid a link and 14.65 ± 1.26 % on unseen pairs, against 5.97 % with no intent, so blocking is
read next to the violation rate, never alone.

Offline (`results/offline/mlp.json`): the MLP control picks an
admissible path in 96.4 % of in-distribution held-out records, 95.7 % with unseen wording (it
does not read the wording) and 70.0 % for unseen intent pairs. That last number is the one the
language model has to beat to show that pretraining helps with composition.

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
- TODO after the GPU runs: failure modes of the fine-tuned model.

## 7. Reproducibility

`make run` rebuilds every table from the JSON files in `results/` in a container without a GPU
and runs a 50-request demo. Each results file records the command, the ONG commit
(`f7c4491`), the repository commit, seeds and loads. The full pipeline and the GPU steps are in
`README.md` and `docs/gpu_runbook.md`; deviations from the plan, with the measurements behind
them, in `docs/decisions.md`. Simulation and the CPU baselines ran on a laptop (WSL2, 16
logical CPUs). TODO: GPU type, GPU-hours, cost, exact commit of the submission.

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
