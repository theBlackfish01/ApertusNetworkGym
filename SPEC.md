# Intent-conditioned lightpath provisioning with Apertus 8B

Implementation spec. Written 2026-10-08 for a fresh project. Self-contained; the research background is in the owner's vault and is not needed to build this.

Owner: Wadood Ranjha. Deadlines: **Hack Apertus Track 2B, Oct 16, 12:00 CEST (15:00 PKT)**. Stretch: **OFC 2027 3-page summary, Oct 20, 12:00 EDT (21:00 PKT)**. Budget for rented GPUs: USD 25, up to 40.

## 1. What we are building

A small open language model (Apertus v1.5 8B) that makes routing-and-spectrum decisions for an elastic optical network **in one shot**, and that follows operator intents written in plain language ("avoid the Zurich–Milan link", "fewest hops for this service"). Labels come from heuristic teachers inside a simulator. We measure what matters: closed-loop blocking probability, intent-violation rate, invalid-output rate and latency, against the heuristics and a small numeric model trained on the same data.

Claim we are testing: **one fine-tuned 8B model can follow a family of provisioning intents, including combinations it never saw, with blocking close to the matching heuristic.** We are not claiming to beat heuristics on raw blocking.

Two outputs from the same experiments: a Track 2B submission (repo, 6-page report, 2-minute video) and a 3-page OFC summary.

## 2. Fixed decisions

These are settled. Change them only if something breaks, and record why.

| Item | Decision |
| --- | --- |
| Simulator | Optical Networking Gym (ONG), `github.com/carlosnatalino/optical-networking-gym`, GPL-3.0, Python ≥ 3.11, Cython kernels. Run on Linux/WSL2. |
| Scenario | Preset `jocn_benchmark`: nobel-eu (28 nodes, 41 links), K = 5, 320 slots × 12.5 GHz, bit rates 10/40/100/400 Gb/s, holding time 10,800, 6 modulations with OSNR thresholds, QoT = ASE+NLI. Vary `load` and `seed` only. |
| Teacher (no intent) | `select_jocn_ls_bm_ksp_action` (paper's BM-LS-KSP, best blocking in JOCN 2024). |
| Baseline | `first_fit` (paper's KSP-BM-FF). |
| Action space seen by the model | Path index (0–4) and start slot. Modulation is chosen automatically as the highest-efficiency format valid at that path/slot. `reject` allowed. |
| Model | `andreasmartin/apertus-v1.5-8b-text` (bit-identical v1.5 backbone, text-only, stock Transformers ≥ 4.56). State this in the report and set `LLM_NAME` to it. Day-1 task: ask on the Hack Apertus Discord whether the text-only conversion is accepted; if not, switch training to the official checkpoint via the swiss-ai Transformers fork. |
| Fine-tuning | QLoRA with TRL + PEFT + bitsandbytes on one rented A100 80 GB (HF Jobs `a100-large`, $2.50/h; RunPod A100 as alternative). |
| Serving for evaluation | vLLM on the same A100, structured-output regex on the answer. Local llama.cpp Q4_K_M on the RTX 4060 only for the demo video. |
| Repo | Fork of `github.com/HackApertus/project-template`, keep only `track_2b/`, public, Apache-2.0 code, CC-BY-4.0 docs. |
| Seeds | 3 per condition. Report mean ± std. |

## 3. Intent family

Each intent maps to a deterministic **admissible-action set** computed from the request analysis, then the base teacher chooses inside that set. Violation = chosen action not in the admissible set. This gives one uniform metric for every intent.

| Id | Intent (one of 6–10 paraphrases each) | Admissible set | Teacher inside the set |
| --- | --- | --- | --- |
| I0 | none | all valid actions | BM-LS-KSP |
| I1 | "Link A–B is under maintenance; do not route through it." (one random link on at least one candidate path) | actions on paths not containing the link | BM-LS-KSP |
| I2 | "Latency-sensitive: use the path with the fewest hops that fits." | actions on the minimum-hop feasible path(s); ties by km | best modulation, first fit |
| I3 | "Spread the load: use the least-loaded feasible path." | actions on the feasible path with the most free slots (ONG `select_load_balancing_action` ordering) | that heuristic |
| I4 | "Be spectrum-efficient: use the option needing the fewest slots." | actions with minimum `required_slots` across feasible paths; ties by km | first fit |
| Pairs | I1+I2, I1+I3 in training; **I1+I4 and I2+I3 held out** | intersection of sets; if empty, admissible = `reject` | as above |

Paraphrases: write 10 per intent; use 7 in training, hold out 3. Vary link naming ("the link between Berlin and Prague", "Berlin–Prague", "the Berlin-Prague span").

## 4. Prompt and answer format

System message (fixed): "You are a lightpath provisioning controller. Choose a path and start slot for the request, or reject. Answer with exactly one line."

User message, under ~450 tokens. Numbers rounded; no narrative.

```
Request: Berlin -> Prague, 100 Gb/s.
Intent: Link Berlin-Munich is under maintenance; do not route through it.
Network: 320 slots per link, free ratio 0.61.
Candidates (path: hops, km, best modulation, slots needed, free blocks [start-length]):
0: 3 hops, 1240 km, QPSK, 9 slots, blocks [12-15] [88-41] [220-100]
1: 4 hops, 1410 km, QPSK, 9 slots, blocks [120-30] [250-70]
2: 4 hops, 1890 km, BPSK, 17 slots, blocks [250-70]
3: 5 hops, 2100 km, BPSK, 17 slots, none
4: 5 hops, 2250 km, BPSK, 17 slots, none
Links per path: 0: Berlin-Munich, Munich-Vienna, Vienna-Prague ; 1: ...
Answer format: path=<0-4> slot=<n>  or  reject
```

Only blocks that are valid (resource and QoT) at the best modulation are listed, at most 3 per path. The model therefore chooses *among* valid options; the task is the ranking rule plus the intent. Links per path are needed for I1.

Assistant answer: `path=1 slot=120` or `reject`. Regex at decode: `^(path=[0-4] slot=\d{1,3}|reject)$`.

Mapping an answer to a simulator action: path index p, slot s, modulation offset = highest-efficiency modulation m with `qot_valid_starts[p, m, s]` and `resource_valid_starts[p, m, s]` true; encode with ONG's action codec (`path_index*(M*S) + modulation_offset*S + initial_slot`). If the answer is not in the mask: count as invalid, then fall back to `select_first_fit_action(mask)`. Invalid rate is a reported metric, not hidden.

## 5. Data

Generated with a subclass of `OpticalEnv` overriding `on_request_analysed(analysis)` (see `examples/JOCN_Benchmark_2024/generate_dataset.py` for the pattern). From `analysis`: `paths[k].hops/length_km/link_ids/node_names`, `required_slots_by_path_mod`, `resource_valid_starts`, `qot_valid_starts`, `modulation_indices`, `free_slots_ratio`.

- Episodes driven by the **intent-aware teacher**, across loads {150, 210, 270, 330} and seeds 1–8, 1,000 requests each, so states cover light to heavy load. Skip the first 300 requests of each episode (warm-up).
- Each record: prompt, completion, plus metadata: load, seed, request index, intent id, paraphrase id, admissible action list, teacher action, full mask size. Store JSONL. Keep `data/` under 100 MB in the repo (sample only; full set to a Hugging Face dataset under CDLA-Permissive-2.0).
- Sizes: train 12,000 (I0 4,000; I1–I4 1,500 each; I1+I2 and I1+I3 1,000 each). Held-out: in-distribution 1,000; unseen paraphrases 600; unseen pairs 600.
- Sanity checks before training: no duplicate prompts across splits; teacher action always inside the admissible set; distribution of chosen path index per intent printed.

## 6. Training

- 4-bit NF4 base, LoRA r = 32, alpha = 32, dropout 0.05, all seven projection matrices; lr 2e-4 cosine, warm-up 5%; `max_length` 768; per-device batch 8, grad accumulation 4; bf16; gradient checkpointing; `paged_adamw_8bit`; 2 epochs; completion-only loss (prompt/completion dataset format).
- Mask label ids 131072–131271 to −100 (untrained head rows in the text-only conversion).
- Chat template from the tokenizer; thinking off. End token `<|assistant_end|>`.
- Expected: ~5.5M tokens per epoch, roughly 45–60 minutes per epoch on the A100. Save adapter and a merged bf16 checkpoint. Push both to the Hub (public at submission time).
- Log train/eval loss; after training, offline exact-match agreement with the teacher on the three held-out splits, and agreement with the admissible set (the number that matters for intents).
- Estimated cost: 2–3 GPU hours ≈ $6–8.

## 7. Closed-loop evaluation

Protocol applied identically to every policy:

1. `make_env(scenario="jocn_benchmark", load=L, seed=s, episode_length=3000)`.
2. Warm-up: first 1,000 requests decided by the no-intent teacher (fills the network realistically; keeps model calls down). Not counted.
3. Evaluation window: requests 1,001–3,000 decided by the policy under test. Each request carries an intent drawn from the condition's intent distribution.
4. Metrics from `info`: `episode_service_blocking_rate` and `episode_bit_rate_blocking_rate` computed over the window (reset counters with `options={"only_episode_counters": True}` after warm-up), violation rate, invalid-output rate, mean decision latency.

Loads: calibrate on day 1 and fix two values where the teacher's blocking is roughly 1% and 5–10% (the JOCN sweep ran 50–650 on nobel-eu). Seeds 1–3.

Policies: `first_fit` baseline; no-intent teacher; intent-aware teacher (the oracle for each condition); Apertus text-only **zero-shot** with the same prompt; **fine-tuned Apertus**; **MLP control** (two hidden layers, inputs = the same per-path numbers plus one-hot intent ids; trained on the same 12k examples; for unseen pairs it receives both one-hots). The MLP is the "did pretraining buy anything" control and is required for the paper.

Conditions: I0; each of I1–I4; mixed single intents with held-out paraphrases; held-out pairs. Total model decisions ≈ 2 loads × 3 seeds × 7 conditions × 2,000 ≈ 84k; batch across env instances; at ~20 requests/s on the A100 that is about 70 minutes of serving, under $5.

Deliverable: one table (policy × condition → blocking, violation %, invalid %, ms/decision) and one figure (blocking vs condition for teacher, MLP, fine-tuned, zero-shot).

## 8. Repo layout and deliverables

```
track_2b/
  README.md                 what it is, how to run, hardware, LLM_* env vars
  Makefile                  make run -> docker compose up -> prints the results table
  Dockerfile, compose.yaml  Python 3.12, ONG built from source, our package
  technical_report.md       filled per template headings; export TeamName_Report.pdf (≤ 6 pages)
  src/
    intents.py              intent definitions, paraphrases, admissible sets
    prompt.py               analysis -> prompt text; answer -> action
    generate.py             dataset generation (ONG subclass)
    train.py                TRL/PEFT QLoRA; runs under `hf jobs`
    policies.py             heuristics, zero-shot, fine-tuned (vLLM client), MLP
    evaluate.py             closed-loop protocol, batching across envs, tables
    report_tables.py        results JSON -> markdown/LaTeX tables and the figure
  data/                     sample prompts (≤ 100 MB); full dataset on the Hub
  results/                  cached decisions and metrics JSON for every run
  docs/                     figures, video link
```

`make run` must work on a clean checkout with no GPU: it rebuilds the results table from `results/` and runs a 50-request live demo only if `LLM_BASE_URL` is set. Judges run exactly this.

Report sections follow the template: summary, architecture (with the mandatory deployment-target subsection: on-premise, one 24 GB GPU or a 4-bit CPU build), use of Apertus (model, adapter, serving), data, evaluation, limitations, reproducibility (seeds, commit, GPU hours), next steps. Video: one request with an intent flowing through prompt → answer → simulator, then the results table.

OFC summary (if the Oct 15 gate passes): 35-word abstract, 3 pages in the Optica template, category N3. Content = the table and figure above plus one paragraph of method; no new experiments.

## 9. Schedule and gates

Revised Oct 9 evening: work starts Saturday Oct 10, so there is no spare day. The weekend carries days 1–3.

| Day | Date | Work | Gate to continue |
| --- | --- | --- | --- |
| 1 | Sat Oct 10 (morning) | WSL2 + build tools; ONG installed, kernels compiled; `jocn_benchmark` runs; `first_fit` and BM-LS-KSP sweep at 3 loads; pick the two evaluation loads. Discord question on the text-only model. Register on Devpost and the submission site; GPU account with a test top-up. | Teacher beats first-fit; loads fixed |
| 2 | Sat Oct 10 (afternoon/evening) | `intents.py`, `prompt.py`, `generate.py`; 12k + held-out; sanity checks; 20 prompts hand-read; zero-shot Apertus on those 20 via Public AI or local GGUF | Zero-shot emits parseable answers; prompts under 450 tokens |
| 3 | Sun Oct 11 | `train.py` smoke test on 200 examples locally (CPU/4060) then full run on A100; offline agreement on held-out splits | Loss falls; fine-tuned ≫ zero-shot on in-distribution agreement; if admissible-set agreement < 60%, stop and diagnose before more spend |
| 4 | Mon Oct 12 (evening) | MLP control; `policies.py`; vLLM serving on A100 | ≥ 10 decisions/s |
| 5 | Tue Oct 13 (evening) | `evaluate.py` with batching; one full condition end to end, then launch the full grid | Metrics match hand checks |
| 6 | Wed Oct 14 (evening) | Results JSON; tables and figure; Docker and `make run` on a clean clone | Table complete with 3 seeds; judges' command works |
| 7 | Thu Oct 15 (evening) | Report, video. **OFC go/no-go** | |
| 8 | Fri Oct 16 | Submit before 15:00 PKT (work morning; submit early) | |
| 9–12 | Oct 17–20 | OFC summary draft, co-author review, submit by 21:00 PKT Oct 20 | |

If the weekend slips, drop the MLP control and the held-out pairs from the hackathon version first; they return for ONDM.

## 10. Who decides what

**Wadood decides:** go/no-go at each gate; the final intent family and wording; any spend beyond $25; the supervisor conversation and author list; what goes in the report and the paper. Reads every result table before it is used.

**Agents decide:** code structure, library choices within the fixed decisions, batching and caching details, Docker specifics, figure styling. They record each deviation from this spec in `docs/decisions.md` with one line of reason.

Suggested split into parallel streams: (A) simulator, intents, data; (B) training on the GPU; (C) serving and closed-loop evaluation; (D) repo hygiene, Docker, report and paper draft. A must finish day 2 before B and C start; D runs throughout.

Hard rules: no training on held-out splits; no editing results JSON by hand; every number in the report comes from `results/`; AI assistance is disclosed in the report; the project starts from an empty repo on Oct 9 (prior-work rule of Track 2B).

## 11. Risks and fallbacks

| Risk | Signal | Fallback |
| --- | --- | --- |
| Text-only conversion not accepted | Discord/email answer | Train on the official checkpoint with the swiss-ai Transformers fork on the A100; everything else unchanged |
| Model ignores intents (violations stay high) | day-4 admissible-set agreement < 60% | Add 1 epoch with intent-only data; if still failing, report I0 results plus the negative intent result honestly |
| vLLM + Apertus + LoRA problems | day-5 serving fails | Serve the merged bf16 checkpoint instead of base + adapter; last resort Transformers generate with batching (slower, still fits the budget) |
| Serving too slow | < 5 decisions/s | Cut to 1 load, 2 seeds, 1,000-request window; keep the condition set |
| ONG build fails on WSL2 | day 1 | Docker image for ONG; pure-Python fallback kernels exist but are slower |
| Numbers do not support any claim | day 6 | Hackathon still submits (rigour is judged, not wins); OFC skipped; ONDM Jan 18 with more work |
| Time | late nights by day 3 | Drop the MLP control and held-out pairs from the hackathon version; keep them for ONDM |

## 12. References the implementer will need

- ONG repo and `examples/JOCN_Benchmark_2024/`; JOCN 16(12) G40 (2024), Natalino et al.
- Hype or Hope? Doherty et al., JOCN 17(9) D1 (2025): why the baseline must be a tuned KSP-FF.
- NetLLM (SIGCOMM 2024) and Trailblazer (arXiv 2512.11839): precedent for distilling existing policies into LLMs.
- Jiang et al., NeurIPS 2025 (arXiv 2509.16865): supervised imitation alone yields infeasible outputs; why we constrain decoding and report invalid rate.
- Hack Apertus Track 2B page and `project-template/track_2b`; Apertus text-only model card; TRL SFT docs; vLLM structured outputs docs; HF Jobs docs.
