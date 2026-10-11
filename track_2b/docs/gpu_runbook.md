# GPU runbook: fine-tune and evaluate Apertus on Hugging Face Jobs

Everything that needs a GPU runs as a Hugging Face Job: a container that downloads a private
"work repo" (code, lock file, dataset splits), runs one stage of [`jobs/run.sh`](../jobs/run.sh),
and copies its results back to that repo. Nothing has to stay up, and every job has a timeout
that caps what it can spend.

## Why the model runs inside the job, not behind a server

SPEC §2 asks for vLLM with a structured-output regex. A job has no cheap way to serve an endpoint
to a simulator elsewhere, so the evaluator runs next to the GPU and loads the model itself
(`policies.LocalLLMPolicy`, `--backend transformers`). The decoding constraint is the same regex,
applied token by token (`src/decoding.py`); unconstrained, the decoder reproduces
`model.generate` exactly (checked on a small model). The simulator steps in parallel worker
processes (`--sim-workers`) so the GPU is not left waiting, and every answer is written to
`results/cache/<policy>.jsonl` and copied to the work repo every few minutes, so a job that dies
loses nothing: rerunning the stage replays the cached answers without the model and continues.
The endpoint client (`--backend endpoint`, vLLM) is still there for a rented machine.

## 0. Prerequisites (done on 2026-10-10)

- Access conditions of `andreasmartin/apertus-v1.5-8b-text` accepted on the account.
- `HF_TOKEN` (write) in the repository's root `.env`; credits on the account.
- `uv` installed; the `hf` CLI is run as `uvx --from "huggingface_hub[cli]" hf`.

```bash
export HF_TOKEN=...            # or source a file that reads it from .env
export WORK_REPO=<user>/apertus-lightpath-work
export ADAPTER_REPO=<user>/apertus-lightpath-lora
```

## 1. Dry run, no GPU

```bash
uv run src/train.py --data-dir data/full --dry-run
```

Prints one rendered example, the end token and the token statistics. Result on 2026-10-10 with
the model's own tokenizer: target `path=2 slot=56<|assistant_end|>` (end token id 68, outside the
masked label range), user message 413 tokens on average and 501 at most, every sequence under 768.

## 2. Push the bundle

```bash
bash jobs/push_bundle.sh "what changed"
```

Run it again whenever `src/`, `jobs/run.sh` or the dataset changes; jobs always download the
latest version.

## 3. Stages

```bash
bash jobs/launch.sh <stage> <flavor> <timeout>
```

| Stage | Flavor, timeout | What it does | What to check before the next stage |
| --- | --- | --- | --- |
| `check` | `cpu-upgrade`, 20m | Whole pipeline on a 135M open model: install, ONG build, train 2 steps, merge, predict, closed loop with adapter, upload. About 1 cent. | It ends with `=== ... done`. |
| `smoke` | `a100-large`, 25m | Real model: 10 optimizer steps with 4-bit QLoRA and with bf16 LoRA, zero-shot offline agreement on 64 records per split, a short closed loop over all 42 environments. | Seconds per step and decisions per second; they fix the timeouts and the budget of the next two stages. |
| `train` | `a100-large` | Full fine-tuning. The adapter goes to `ADAPTER_REPO` after every epoch and at the end, with the log and the held-out predictions. Extra arguments in `TRAIN_ARGS`. | Loss falls; score the predictions (below); stop if admissible-set agreement is under 60 % (SPEC §9). |
| `eval` | `a100-large` | Short steps first: fine-tuned offline agreement, the demo answers for `make run`, zero-shot offline agreement. Then the fine-tuned closed loop on the full grid, then the zero-shot closed loop, load 390 alone before both loads. `EVAL_ARGS` and `ZS_ARGS` restrict the grids, e.g. `ZS_ARGS="--seeds 1"`. Measured on 2026-10-10: 95 min for the fine-tuned grid (14.8 decisions/s end to end), 24 min for seven zero-shot episodes. | At least 10 decisions/s (SPEC §9). |

Follow a job with `hf jobs logs -f <id>`, stop it with `hf jobs cancel <id>`, list them with
`hf jobs ps -a`.

Scoring the fine-tuned model's held-out predictions, no GPU:

```bash
hf download $ADAPTER_REPO heldout_predictions.jsonl --local-dir runs/apertus-ft
uv run python src/evaluate.py offline --policy apertus_ft --predictions runs/apertus-ft/heldout_predictions.jsonl
```

For reference the MLP control scores 96.4 % in distribution, 95.7 % on unseen wording and 70.0 %
on unseen pairs (`results/offline/mlp.json`).

## 4. Bring the results home

```bash
hf download $WORK_REPO --repo-type dataset --include "results/*" --local-dir .
uv run python src/report_tables.py
```

Record GPU-hours and cost in `technical_report.md` §7.

## A further pass (how the second pass was run)

```bash
source ~/hfenv2.sh                      # same token, separate WORK_REPO and ADAPTER_REPO
uv run python src/generate.py --stage splits                 # relabel under the current rule
uv run python src/mlp.py                                      # retrain the control
bash jobs/push_bundle.sh "second pass"
bash jobs/launch.sh check cpu-upgrade 20m
TRAIN_ARGS="--epochs 1" bash jobs/launch.sh train a100-large 85m
# score the held-out answers on the laptop, then, if worth it, one more epoch from that adapter:
ADAPTER_REPO=<user>/...-e2 TRAIN_ARGS="--epochs 1 --lr 1e-4 --init-adapter <user>/..." \
    bash jobs/launch.sh train a100-large 85m
ADAPTER_REPO=<user>/...-e2 SKIP_ZERO_SHOT=1 bash jobs/launch.sh eval a100-large 125m
```

Use a new work repo for a new pass: answer caches are keyed by policy name and prompt, so an old
cache in the work repo would be replayed for a new model. Zero-shot answers depend neither on the
adapter nor on the intent rules; re-score them from `results/cache/` on the laptop
(`evaluate.py closed --policy apertus_zero_shot --backend transformers --seeds 1 --loads 390`).
Measured on 2026-10-10: 68.5 and 68.8 min per epoch, 100 min for the evaluation.

## Phase 1: translator against decider

```bash
# laptop, no GPU: test sets, the other topology, every instruction of the closed loop
uv run python src/corpora.py
uv run python src/transfer.py --loads 300 600 900 1200
uv run python src/translate.py texts --workers 3
bash jobs/phase1_local.sh translate_keyword          # the baseline through the whole pipeline

# GPU: a CPU dry run with a tiny model first (cents), then two A100 jobs
source ~/hfenv2.sh
bash jobs/push_bundle.sh "phase 1"
bash jobs/launch.sh check cpu-upgrade 30m
ADAPTER_REPO=<user>/...-e2 bash jobs/launch.sh phase1 a100-large 80m          # the decider's adapter
TRANSLATOR_REPO=<user>/apertus-lightpath-translator bash jobs/launch.sh phase1-ft a100-large 75m

# laptop again: fetch the answer caches, replay the translators, render results/tables/phase1.md
bash jobs/phase1_local.sh translate_zero translate_few translate_ft
```

Measured on 2026-10-11: `phase1` needs about 75 minutes (it was given 65 and lost its last step,
the few-shot decider, which a second launch finished from the caches in 8 minutes); `phase1-ft`
44 minutes, of which 24 are training. The two jobs are independent and can run side by side.

Fetch single files from the work repo with `huggingface_hub.hf_hub_download(...,
force_download=True)`. `hf download --include` with several patterns left one cache out and kept
a stale copy of another; a translator replay then stops with "No module named 'torch'", which
means an answer is missing from the cache and the model would have to be loaded.

## Alternative: a rented machine with vLLM

```bash
vllm serve andreasmartin/apertus-v1.5-8b-text --served-model-name apertus-base \
    --enable-lora --lora-modules apertus-ft=runs/apertus-ft/adapter --max-model-len 1024 --port 8000
uv run python src/evaluate.py closed --policy apertus_ft --base-url http://localhost:8000/v1 --model apertus-ft
```

Older vLLM takes `--structured guided_regex`. This path is tested only against a mock endpoint.
