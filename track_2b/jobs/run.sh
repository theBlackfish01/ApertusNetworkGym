#!/bin/bash
# Runs inside a Hugging Face Job, from the root of the work repo (code, data, earlier results).
#
#   check   the whole pipeline on a tiny open model, CPU only: validates the image, the plumbing
#           and the failure/resume path (a training run is killed on purpose and resumed)
#   smoke   a few training steps and a short closed loop with the real model: measures throughput
#   train   full fine-tuning; resumes from the Hub if an earlier job left a checkpoint
#   eval    closed-loop and offline evaluation of the fine-tuned and the zero-shot model
#   phase1  translate versus decide: the translator (as is, and with examples in the prompt) on the
#           test and closed-loop instructions; the fine-tuned decider on the probe sets; the
#           few-shot decider on the held-out splits
#   phase1-ft  fine-tune the translator and run it on the same instructions
#   check2  the second translator format and the new probe sets on a tiny model, CPU only
#   phase2  second translator format with examples on all instruction sets; the fine-tuned
#           decider on the new probe sets (unseen instruction types, text that is no instruction,
#           independently written German, French and Italian)
#   phase2-ft  fine-tune the second translator and run it on all instruction sets
#   check3  the mixed closed-loop condition with a live decider behind the translator, tiny model
#   phase3  the mixed condition (mixed.py) in closed loop: the decider alone, and the hybrid of the
#           second fine-tuned translator and the decider; the translator's answers are computed first
#   check4  the third translator format on a tiny model, CPU only: examples, training, adapter
#   train3  fine-tune one reader of the third translator (READER = 1 or 2: its training data and
#           seed); two readers are trained so that their disagreement can be used
#   check5  the third round's evaluation on a tiny model, CPU only: two readers, the guarded
#           fallback, closed loops that share one machine
#   phase4  the third round: both fine-tuned readers and the reader with examples on the test
#           instructions; the decider on the probes of the new types; the mixed condition
#           operations_mix3 in closed loop for the decider alone, the hybrid, and the hybrid that
#           asks when its two readers disagree (three processes on one GPU)
#   train4  fine-tune the reader of the fourth format (scope and lifetime of a standing policy) and
#           score it on the fourth and third rounds' test sets
#   phase5  the same mixed condition in closed loop for the hybrid that asks with another second
#           reader (SECOND, default few70b: the untrained Apertus 70B, read beforehand by the
#           stage big); EVAL_ARGS narrows the episodes, e.g. "--loads 390"
#   gguf    CPU only: both readers' adapters and the base model as GGUF files for llama.cpp
#           (the adapters first; the base is converted from the published weights and quantised
#           to 4 bits), uploaded to GGUF_REPO. This is what runs on a laptop
#   gguf-lora  CPU only: the decider's adapter (ADAPTER_REPO) as a GGUF file in GGUF_REPO, so the
#           whole hybrid can run behind one llama.cpp server
#   big     a larger Apertus as a reader with examples and no training: BIG_MODEL is
#           "<repo>:<file>" of a GGUF build, served by llama.cpp on the GPU under the same
#           grammar; BIG_NAME names the reader (its answers go to results/cache/<name>.jsonl)
#   phase1-closed  the translators named in CLOSED_POLICIES answer every instruction of the
#           closed-loop protocol (the closed loop itself is then replayed on a laptop)
#   read4   the fourth-format reader (TRANSLATOR_REPO) reads the mixed condition's instructions and
#           is scored again on all its sets (the cached ones are replayed, not recomputed)
#   train-d3  the matched decider (data/full3: the first decider's states, the routing-field reader's
#           training sentences) for one epoch, pushed to ADAPTER_REPO; TRAIN_ARGS can start from an
#           earlier epoch's adapter (--init-adapter)
#   eval-d3  the matched decider (ADAPTER_REPO) on the probes and alone in the mixed condition; the
#           full-format reader in front of the first decider (DECIDER_REPO) and of the matched one
#   check6  CPU only, tiny model: the plumbing of read4, train-d3 and eval-d3
#
# Nothing a job computes is kept only in the job. Training pushes a checkpoint (adapter, optimizer,
# scheduler) every 100 optimizer steps and the adapter at every epoch; evaluation appends every
# model answer to a cache that is copied to the work repo every two minutes; and whatever exists
# is copied once more when the script exits, whether it finished or failed. Launching the same
# stage again continues from there.
#
# Environment: WORK_REPO (dataset repo holding this bundle; results are copied back to it),
# ADAPTER_REPO (model repo for the adapter), HF_TOKEN (secret); optional MODEL, TRAIN_ARGS,
# EVAL_ARGS (fine-tuned closed loop), ZS_ARGS (zero-shot closed loop), SKIP_ZERO_SHOT (any value:
# the eval stage evaluates the fine-tuned model only); for phase1: TRANSLATOR_REPO (model repo for
# the translator's adapter), CLOSED_POLICIES.
set -euo pipefail
STAGE=${1:?stage: check | check2 | check3 | check4 | smoke | train | eval | phase1 | phase1-ft | phase1-closed | phase2 | phase2-ft | phase3 | train3 | train4 | score4 | check5 | phase4 | phase5 | gguf | gguf-lora | big | read4 | train-d3 | eval-d3 | hybrids-d3 | check6}
: "${WORK_REPO:?set WORK_REPO}"
MODEL=${MODEL:-andreasmartin/apertus-v1.5-8b-text}
cd "$(dirname "$0")/.."
export UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PYTHONUNBUFFERED=1
export HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
stamp() { echo "=== $(date -u +%H:%M:%S) $*"; }
PY=/opt/venv/bin/python

# CPUs this container may actually use. In a job, nproc and os.cpu_count() can report the host's
# cores; sizing thread pools from them makes numerical libraries thrash (the first check job did
# not finish one CPU training step in 18 minutes).
CPUS=$(python3 - <<'PYEOF'
import os
n = os.cpu_count() or 1
try:
    quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
    if quota != "max":
        n = min(n, max(1, round(int(quota) / int(period))))
except (OSError, ValueError):
    pass
try:
    n = min(n, len(os.sched_getaffinity(0)))
except AttributeError:
    pass
print(n)
PYEOF
)
echo "cpus: usable $CPUS | nproc $(nproc) | cpu.max $(cat /sys/fs/cgroup/cpu.max 2>/dev/null || echo n/a) | mem $(free -g 2>/dev/null | awk '/Mem:/{print $2 " GB"}')"
export OMP_NUM_THREADS=$CPUS MKL_NUM_THREADS=$CPUS OPENBLAS_NUM_THREADS=$CPUS NUMEXPR_NUM_THREADS=$CPUS

stamp "setup"
uv sync --frozen --no-dev
uv pip install --python /opt/venv/bin/python -q "torch>=2.4" "transformers~=5.19" "peft~=0.21" \
    "accelerate~=1.15" "datasets~=5.1" "huggingface_hub~=2.2" "bitsandbytes~=0.50"
$PY -c "import torch; print('torch', torch.__version__, '| cuda', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu', '| threads', torch.get_num_threads())"
WORKERS=$((CPUS > 3 ? CPUS - 2 : 1))
SYNC="--sync-repo $WORK_REPO --sync-every 120"
# Phase 1: instruction files (data/instructions) and probe sets (data/probes), built by corpora.py.
I=data/instructions
TESTS="$I/templates.jsonl,$I/independent.jsonl,$I/de.jsonl,$I/fr.jsonl,$I/it.jsonl,$I/gsw.jsonl,$I/noisy.jsonl,$I/faulty.jsonl,$I/out_of_scope.jsonl"
PROBES="independent de fr it gsw noisy faulty out_of_scope germany50"
# Second round (corpora2.py): instruction types without a rule, text that is no instruction, and the
# supported instructions written natively in German, French and Italian.
NEW="$I/unseen.jsonl,$I/unseen_impossible.jsonl,$I/not_instruction.jsonl,$I/de_ind.jsonl,$I/fr_ind.jsonl,$I/it_ind.jsonl"
PROBES2="unseen unseen_impossible not_instruction de_ind fr_ind it_ind"
# Third round (corpora3_tests.py, mixed3.py): the policy language in four languages, the new types.
V3="$I/v3_en.jsonl,$I/v3_de.jsonl,$I/v3_fr.jsonl,$I/v3_it.jsonl,$I/v3_new.jsonl,$I/v3_new_hard.jsonl,$I/v3_new_impossible.jsonl,$I/v3_partial.jsonl,$I/v3_other.jsonl,$I/v3_not.jsonl,$I/v3_faulty.jsonl"
EARLIER="$I/independent.jsonl,$I/de_ind.jsonl,$I/fr_ind.jsonl,$I/it_ind.jsonl"
together() {  # run the given commands at the same time on this machine and fail if one fails
    local pids=() pid
    for command in "$@"; do
        bash -c "$command" &
        pids+=($!)
    done
    for pid in "${pids[@]}"; do wait "$pid"; done
}

# Copy files or folders (paths relative to the repo root) back to the work repo.
keep() {
    $PY - "$@" <<'PYEOF'
import os, sys
from pathlib import Path
from huggingface_hub import HfApi
api, repo = HfApi(), os.environ["WORK_REPO"]
for name in sys.argv[1:]:
    path = Path(name)
    if path.is_dir():
        api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=name, path_in_repo=name,
                          allow_patterns=["*.json", "*.jsonl", "*.md", "*.tex", "*.npz"],
                          ignore_patterns=["*checkpoints/*", "*merged/*", "*adapter*/*", "*resume/*"])
        print("kept", name + "/")
    elif path.exists():
        api.upload_file(repo_id=repo, repo_type="dataset", path_or_fileobj=name, path_in_repo=name)
        print("kept", name)
PYEOF
}
# On any exit, finished or failed, copy every result and log that exists.
finish() {
    code=$?
    stamp "exit code $code: copying results and logs to $WORK_REPO"
    keep results runs || true
}
trap finish EXIT

case "$STAGE" in
check)
    : "${ADAPTER_REPO:?set ADAPTER_REPO}"
    TINY=HuggingFaceTB/SmolLM2-135M-Instruct
    CHECK_REPO="${ADAPTER_REPO}-check" # throwaway repo for the failure/resume test
    $PY -c "from huggingface_hub import HfApi; HfApi().delete_repo('$CHECK_REPO', missing_ok=True)"
    TRAIN="$PY src/train.py --model $TINY --data-dir data/full --out runs/check --no-4bit --limit-train 32
        --limit-heldout 4 --max-steps 4 --save-steps 2 --batch 4 --accumulation 1 --eval-records 4
        --hub-adapter $CHECK_REPO"
    stamp "train (tiny model), killed on purpose at step 3"
    $TRAIN --die-at-step 3 && { echo "the simulated failure did not happen" >&2; exit 1; }
    rm -rf runs/check # a new job starts with an empty disk
    stamp "train again with --resume: must continue from the checkpoint on the Hub"
    $TRAIN --resume 2>&1 | tee /tmp/resume.log
    grep -q "resuming training from the checkpoint at optimizer step 2" /tmp/resume.log
    rm -rf runs/check
    stamp "and once more: training is finished, only the predictions are redone"
    $TRAIN --resume 2>&1 | tee /tmp/finished.log
    grep -q "training already finished on the Hub" /tmp/finished.log
    stamp "a further epoch from the finished adapter (--init-adapter)"
    $PY src/train.py --model $TINY --data-dir data/full --out runs/check-more --no-4bit --limit-train 16 \
        --limit-heldout 4 --max-steps 2 --save-steps 0 --batch 4 --accumulation 1 --eval-records 4 \
        --init-adapter "$CHECK_REPO" --lr 1e-4 --skip-merge 2>&1 | tee /tmp/more.log
    grep -q "starting from the adapter" /tmp/more.log
    $PY src/evaluate.py offline --policy check_ft --predictions runs/check/heldout_predictions.jsonl --limit 4
    stamp "closed loop (tiny model + adapter)"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy check_local --backend transformers --model $TINY \
        --adapter runs/check/adapter --conditions I0 I1 --loads 390 --seeds 1 --warmup 50 --window 10 \
        --sim-workers 2 $SYNC
    stamp "phase 1 plumbing: translator (grammar, examples, shared model), probes, few-shot decider"
    $PY src/translate.py batch --model $TINY --batch 8 --jobs \
        "translate_check_few:nobel-eu:regex:$I/out_of_scope.jsonl" \
        "translate_check_zero:germany50:regex:$I/out_of_scope.jsonl" \
        "translate_check_few_free:nobel-eu:none:$I/out_of_scope.jsonl"
    $PY src/train.py --model $TINY --data-dir data/translate --out runs/check-translator --no-4bit \
        --limit-train 16 --limit-heldout 4 --max-steps 2 --save-steps 0 --batch 4 --accumulation 1 \
        --eval-records 4 --max-length 1024 --max-new-tokens 48
    $PY src/translate.py batch --model $TINY --adapter runs/check-translator/adapter --batch 8 --jobs \
        "translate_check_ft:nobel-eu:regex:$I/out_of_scope.jsonl"
    $PY src/evaluate.py offline --policy check_probes --backend transformers --model $TINY \
        --adapter runs/check/adapter --data data/probes --splits faulty germany50 --limit 8
    $PY src/evaluate.py offline --policy check_fewshot --backend transformers --model $TINY \
        --shots data/fewshot/decider.jsonl --limit 4 --batch-envs 4
    $PY src/evaluate.py offline --policy translate_check_few --model $TINY --data data/probes \
        --splits out_of_scope --limit 8
    $PY -c "from huggingface_hub import HfApi; HfApi().delete_repo('$CHECK_REPO', missing_ok=True)"
    ;;
smoke)
    stamp "train, 4-bit QLoRA, 10 optimizer steps"
    $PY src/train.py --model "$MODEL" --data-dir data/full --out runs/smoke-4bit --limit-train 480 \
        --limit-heldout 32 --max-steps 10 --eval-records 32 --save-steps 0
    keep runs/smoke-4bit/training_log.json runs/smoke-4bit/heldout_predictions.jsonl
    stamp "train, bf16 LoRA, 10 optimizer steps (speed comparison)"
    $PY src/train.py --model "$MODEL" --data-dir data/full --out runs/smoke-bf16 --no-4bit --limit-train 480 \
        --limit-heldout 8 --max-steps 10 --eval-records 32 --save-steps 0 --skip-merge
    keep runs/smoke-bf16/training_log.json
    stamp "zero-shot: offline agreement on 64 records per split"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy smoke_zero_shot --backend transformers --model "$MODEL" --limit 64 $SYNC
    stamp "zero-shot: all 42 environments, 20 requests each (throughput)"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy smoke_zero_shot --backend transformers --model "$MODEL" \
        --warmup 100 --window 20 --sim-workers "$WORKERS" $SYNC
    stamp "adapter from the 10 steps: short closed loop (checks the merge path)"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy smoke_ft --backend transformers --model "$MODEL" \
        --adapter runs/smoke-4bit/adapter --conditions I0 I1 --loads 390 --seeds 1 --warmup 100 --window 20 \
        --sim-workers 2 $SYNC
    ;;
train)
    : "${ADAPTER_REPO:?set ADAPTER_REPO}"
    stamp "train (resumes from $ADAPTER_REPO if a checkpoint is there)"
    # shellcheck disable=SC2086
    $PY src/train.py --model "$MODEL" --data-dir data/full --out runs/apertus-ft --hub-adapter "$ADAPTER_REPO" \
        --resume --save-steps 100 ${TRAIN_ARGS:-}
    keep runs/apertus-ft/training_log.json runs/apertus-ft/heldout_predictions.jsonl
    ;;
eval)
    : "${ADAPTER_REPO:?set ADAPTER_REPO}"
    stamp "download adapter"
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$ADAPTER_REPO', local_dir='runs/adapter', allow_patterns=['adapter_*', '*.jinja']))"
    stamp "fine-tuned: offline agreement on the held-out splits"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy apertus_ft --backend transformers --model "$MODEL" --adapter runs/adapter $SYNC
    # The short steps come first, so a job that runs out of time has already delivered them.
    stamp "fine-tuned: demo answers for make run"
    $PY src/evaluate.py demo --policy apertus_ft_demo --backend transformers --model "$MODEL" --adapter runs/adapter
    keep results/cache/apertus_ft_demo.jsonl
    if [ -z "${SKIP_ZERO_SHOT:-}" ]; then
        stamp "zero-shot: offline agreement, with and without the answer constraint"
        # shellcheck disable=SC2086
        $PY src/evaluate.py offline --policy apertus_zero_shot --backend transformers --model "$MODEL" $SYNC
        # shellcheck disable=SC2086
        $PY src/evaluate.py offline --policy apertus_zero_shot_unconstrained --backend transformers \
            --model "$MODEL" --structured none $SYNC
    fi
    stamp "fine-tuned: closed loop"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy apertus_ft --backend transformers --model "$MODEL" --adapter runs/adapter \
        --sim-workers "$WORKERS" $SYNC ${EVAL_ARGS:-}
    # The zero-shot answers do not depend on the adapter or on the intent rules, so a later pass
    # sets SKIP_ZERO_SHOT=1 and re-scores the cached answers on a laptop instead.
    if [ -n "${SKIP_ZERO_SHOT:-}" ]; then
        stamp "done"
        exit 0
    fi
    # All environments of one call advance together and finish on the same tick, so the heavy load
    # runs alone first: a timeout in the second call still leaves a results file. The second call
    # replays the heavy-load answers from the cache and only asks the model for the light load.
    stamp "zero-shot: closed loop, load 390"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy apertus_zero_shot --backend transformers --model "$MODEL" \
        --sim-workers "$WORKERS" $SYNC ${ZS_ARGS:-} --loads 390
    stamp "zero-shot: closed loop, both loads"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy apertus_zero_shot --backend transformers --model "$MODEL" \
        --sim-workers "$WORKERS" $SYNC ${ZS_ARGS:-}
    ;;
phase1)
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the decider)}"
    # One process per model state, so the weights are loaded three times. Short steps first.
    stamp "translator as is: the test instructions, with and without examples in the prompt"
    $PY src/translate.py batch --model "$MODEL" --batch 96 --sync-repo "$WORK_REPO" --jobs \
        "translate_few:nobel-eu:regex:$TESTS" "translate_zero:nobel-eu:regex:$TESTS" \
        "translate_few:germany50:regex:$I/germany50.jsonl" "translate_zero:germany50:regex:$I/germany50.jsonl" \
        "translate_few_free:nobel-eu:none:$TESTS" \
        "translate_few:nobel-eu:regex:$I/closed_loop.jsonl" "translate_zero:nobel-eu:regex:$I/closed_loop.jsonl"
    keep results/translate
    stamp "fine-tuned decider: the probe sets"
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$ADAPTER_REPO', local_dir='runs/adapter', allow_patterns=['adapter_*', '*.jinja']))"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy apertus_ft_probes --backend transformers --model "$MODEL" \
        --adapter runs/adapter --data data/probes --splits $PROBES --batch-envs 64 $SYNC
    stamp "few-shot decider: the held-out splits"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy apertus_fewshot --backend transformers --model "$MODEL" \
        --shots data/fewshot/decider.jsonl --batch-envs 16 $SYNC
    ;;
phase1-ft)
    : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO}"
    stamp "fine-tune the translator (resumes from $TRANSLATOR_REPO if a checkpoint is there)"
    # shellcheck disable=SC2086
    $PY src/train.py --model "$MODEL" --data-dir data/translate --out runs/translator \
        --hub-adapter "$TRANSLATOR_REPO" --resume --save-steps 50 --max-length 640 --max-new-tokens 48 \
        --eval-records 100 ${TRAIN_ARGS:-}
    keep runs/translator/training_log.json runs/translator/heldout_predictions.jsonl
    stamp "fine-tuned translator: the test instructions"
    $PY src/translate.py batch --model "$MODEL" --adapter runs/translator/adapter --batch 96 \
        --sync-repo "$WORK_REPO" --jobs "translate_ft:nobel-eu:regex:$TESTS" \
        "translate_ft:germany50:regex:$I/germany50.jsonl" "translate_ft_free:nobel-eu:none:$TESTS" \
        "translate_ft:nobel-eu:regex:$I/closed_loop.jsonl"
    ;;
check4)
    TINY=HuggingFaceTB/SmolLM2-135M-Instruct
    stamp "third translator format on the tiny model: examples, training of both readers' data, adapter"
    printf '%s\n' '{"text": "Do not pass through Paris. Limit the route to at most 4 hops.", "expect": {"status": "ok", "avoid": [], "prefer": [], "nodes": ["Paris"], "max_hops": 4}, "set": "check", "lang": "en", "kind": "avoid_node+max_hops"}' \
        '{"text": "Good morning, how are you?", "expect": {"status": "no_instruction", "avoid": [], "prefer": []}, "set": "check", "lang": "en", "kind": "not_instruction"}' > /tmp/check4.jsonl
    $PY src/translate.py batch --model $TINY --batch 8 --jobs "translate3_check_few:nobel-eu:regex:/tmp/check4.jsonl"
    for reader in 1 2; do
        $PY src/train.py --model $TINY --data-dir data/translate3/s$reader --out runs/check-translator3 --no-4bit \
            --limit-train 16 --limit-heldout 4 --max-steps 2 --save-steps 0 --batch 4 --accumulation 1 \
            --eval-records 4 --max-length 2048 --max-new-tokens 96 --seed $reader --skip-merge
    done
    $PY src/translate.py batch --model $TINY --adapter runs/check-translator3/adapter --batch 8 --jobs \
        "translate3_check_ft:nobel-eu:regex:/tmp/check4.jsonl"
    ;;
train3)
    : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO}" "${READER:?set READER (1 or 2)}"
    stamp "fine-tune reader $READER of the third translator (resumes from $TRANSLATOR_REPO if a checkpoint is there)"
    # shellcheck disable=SC2086
    $PY src/train.py --model "$MODEL" --data-dir data/translate3/s$READER --out runs/translator3 \
        --hub-adapter "$TRANSLATOR_REPO" --resume --save-steps 50 --max-length 1024 --max-new-tokens 96 \
        --eval-records 100 --seed "$READER" --skip-merge --epochs 1.15 ${TRAIN_ARGS:-}
    mkdir -p results/train/translator3-s$READER
    cp runs/translator3/training_log.json runs/translator3/heldout_predictions.jsonl results/train/translator3-s$READER/
    keep results/train/translator3-s$READER
    ;;
train4)
    : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO}"
    stamp "fine-tune the reader of the fourth format (standing policies: scope and lifetime), then score it"
    # shellcheck disable=SC2086
    $PY src/train.py --model "$MODEL" --data-dir data/translate4/s1 --out runs/translator4         --hub-adapter "$TRANSLATOR_REPO" --resume --save-steps 50 --max-length 1024 --max-new-tokens 120         --eval-records 100 --seed 1 --skip-merge --epochs 1.15 ${TRAIN_ARGS:-}
    mkdir -p results/train/translator4
    cp runs/translator4/training_log.json runs/translator4/heldout_predictions.jsonl results/train/translator4/
    keep results/train/translator4
    V4="$I/v4_en.jsonl,$I/v4_de.jsonl,$I/v4_fr.jsonl,$I/v4_it.jsonl"
    stamp "translate4_ft on the test sets of the fourth round, then those of the third"
    $PY src/translate.py batch --model "$MODEL" --adapter runs/translator4/adapter --batch 96         --jobs "translate4_ft:nobel-eu:regex:$V4,$I/owner.jsonl,$V3"
    keep results/translate results/cache
    ;;
score4)
    # The scoring half of train4 on its own (the adapter from the Hub), after a train4 whose scoring failed.
    : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO}"
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$TRANSLATOR_REPO', local_dir='runs/translator4', allow_patterns=['adapter_*', '*.jinja']))
print(snapshot_download('$MODEL', allow_patterns=['*.json', '*.safetensors', '*.jinja', 'tokenizer*']))"
    V4="$I/v4_en.jsonl,$I/v4_de.jsonl,$I/v4_fr.jsonl,$I/v4_it.jsonl"
    stamp "translate4_ft on the test sets of the fourth round, then those of the third"
    $PY src/translate.py batch --model "$MODEL" --adapter runs/translator4 --batch 96         --jobs "translate4_ft:nobel-eu:regex:$V4,$I/owner.jsonl,$V3"
    keep results/translate results/cache
    ;;
big)
    : "${BIG_MODEL:?set BIG_MODEL to <repo>:<file> of a GGUF build}"
    TAG=${LLAMA_TAG:-b11558}
    NAME=${BIG_NAME:-translate3_few70}
    stamp "llama.cpp $TAG with CUDA, and ${BIG_MODEL}"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    df -h /tmp | tail -1
    mkdir -p /tmp/llama
    for file in "llama-$TAG-bin-ubuntu-cuda-12.8-x64.tar.gz" "cudart-llama-$TAG-bin-ubuntu-cuda-12.8-x64.tar.gz"; do
        curl -sSL "https://github.com/ggml-org/llama.cpp/releases/download/$TAG/$file" | tar -xz -C /tmp/llama
    done
    SERVER=$(find /tmp/llama -name llama-server -type f | head -1)
    CUDA_LIBS=$(dirname "$(find /tmp/llama -name 'libcublas.so*' | head -1)")
    export LD_LIBRARY_PATH="$(dirname "$SERVER"):$CUDA_LIBS:${LD_LIBRARY_PATH:-}"
    "$SERVER" --version  # fails here, before the model is downloaded, if the image's C library is too old
    BIG_MODEL="$BIG_MODEL" $PY -c "
import os
from huggingface_hub import hf_hub_download
repo, name = os.environ['BIG_MODEL'].split(':')
path = hf_hub_download(repo, name, local_dir='/tmp/big')
print(path, os.path.getsize(path) // 2**30, 'GiB')
os.replace(path, '/tmp/big/model.gguf')"
    stamp "start the server (8 requests at a time)"
    "$SERVER" -m /tmp/big/model.gguf -ngl 999 -c 32768 -np 8 --port 8080 --jinja > /tmp/server.log 2>&1 &
    SERVER_PID=$!
    for _ in $(seq 1 120); do
        curl -sf http://127.0.0.1:8080/health > /dev/null && break
        kill -0 $SERVER_PID 2>/dev/null || { tail -30 /tmp/server.log; exit 1; }
        sleep 5
    done
    curl -sf http://127.0.0.1:8080/health || { tail -30 /tmp/server.log; exit 1; }
    grep -i -E "offloaded|model size|chat template|n_ctx_slot" /tmp/server.log | head -8 || true
    stamp "$NAME: the test instructions of the third round, with examples in the prompt"
    $PY src/translate.py batch --base-url http://127.0.0.1:8080/v1 --model "$BIG_MODEL" --concurrency 8 \
        --sync-repo "$WORK_REPO" --jobs "$NAME:nobel-eu:regex:${BIG_SETS:-$V3}"
    grep -E "prompt eval time|eval time" /tmp/server.log | tail -4 || true
    kill $SERVER_PID || true
    ;;
gguf-lora)
    : "${ADAPTER_REPO:?set ADAPTER_REPO}" "${GGUF_REPO:?set GGUF_REPO}"
    TAG=${LLAMA_TAG:-b11558}
    git clone --quiet --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp /tmp/llama.cpp
    uv venv /tmp/convert --python 3.12 -q
    uv pip install --python /tmp/convert/bin/python -q -r /tmp/llama.cpp/requirements/requirements-convert_lora_to_gguf.txt
    MODEL="$MODEL" $PY -c "
import os
from huggingface_hub import snapshot_download
print(snapshot_download(os.environ['MODEL'], local_dir='/tmp/base', allow_patterns=['*.json', '*.jinja', 'tokenizer*']))
print(snapshot_download(os.environ['ADAPTER_REPO'], local_dir='/tmp/decider', allow_patterns=['adapter_*']))"
    /tmp/convert/bin/python /tmp/llama.cpp/convert_lora_to_gguf.py /tmp/decider --base /tmp/base \
        --outtype f16 --outfile "/tmp/${LORA_NAME:-lightpath-decider-v2-lora-f16}.gguf"
    $PY -c "
import os
from huggingface_hub import HfApi
name = os.environ.get('LORA_NAME', 'lightpath-decider-v2-lora-f16') + '.gguf'
HfApi().upload_file(repo_id=os.environ['GGUF_REPO'], path_or_fileobj='/tmp/' + name, path_in_repo=name)
print('uploaded')"
    ;;
gguf)
    : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO (reader 1)}" "${SECOND_REPO:?set SECOND_REPO (reader 2)}"
    : "${GGUF_REPO:?set GGUF_REPO (model repo for the GGUF files)}"
    TAG=${LLAMA_TAG:-b11558}
    stamp "llama.cpp $TAG: conversion scripts and the quantiser"
    df -h /tmp | tail -1
    git clone --quiet --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp /tmp/llama.cpp
    uv venv /tmp/convert --python 3.12 -q
    uv pip install --python /tmp/convert/bin/python -q -r /tmp/llama.cpp/requirements/requirements-convert_lora_to_gguf.txt
    mkdir -p /tmp/out /tmp/bin
    curl -sSL "https://github.com/ggml-org/llama.cpp/releases/download/$TAG/llama-$TAG-bin-ubuntu-x64.tar.gz" | tar -xz -C /tmp/bin
    QUANTIZE=$(find /tmp/bin -name llama-quantize -type f | head -1)
    export LD_LIBRARY_PATH="$(dirname "$QUANTIZE"):${LD_LIBRARY_PATH:-}"
    MODEL="$MODEL" GGUF_REPO="$GGUF_REPO" $PY - <<'PYEOF'
import os
from huggingface_hub import HfApi, snapshot_download
HfApi().create_repo(os.environ["GGUF_REPO"], private=True, exist_ok=True)
print(snapshot_download(os.environ["MODEL"], local_dir="/tmp/base", allow_patterns=["*.json", "*.jinja", "tokenizer*"]))
for repo, where in ((os.environ["TRANSLATOR_REPO"], "/tmp/reader1"), (os.environ["SECOND_REPO"], "/tmp/reader2")):
    print(snapshot_download(repo, local_dir=where, allow_patterns=["adapter_*"]))
PYEOF
    upload() {
        GGUF_REPO="$GGUF_REPO" $PY -c "
import os, sys
from huggingface_hub import HfApi
for path in sys.argv[1:]:
    HfApi().upload_file(repo_id=os.environ['GGUF_REPO'], path_or_fileobj=path, path_in_repo=os.path.basename(path))
    print('uploaded', os.path.basename(path), os.path.getsize(path) // 2**20, 'MiB')" "$@"
    }
    for reader in 1 2; do
        stamp "reader $reader: LoRA adapter to GGUF"
        /tmp/convert/bin/python /tmp/llama.cpp/convert_lora_to_gguf.py /tmp/reader$reader --base /tmp/base             --outtype f16 --outfile /tmp/out/lightpath-translator-v3-reader$reader-lora-f16.gguf
        upload /tmp/out/lightpath-translator-v3-reader$reader-lora-f16.gguf
    done
    stamp "base model: published weights to GGUF (16 bit), then 4 bit (Q4_K_M)"
    MODEL="$MODEL" $PY -c "
import os
from huggingface_hub import snapshot_download
print(snapshot_download(os.environ['MODEL'], local_dir='/tmp/base', allow_patterns=['*.safetensors']))"
    df -h /tmp | tail -1
    /tmp/convert/bin/python /tmp/llama.cpp/convert_hf_to_gguf.py /tmp/base --outtype f16 --outfile /tmp/base-f16.gguf
    rm -f /tmp/base/*.safetensors
    "$QUANTIZE" /tmp/base-f16.gguf /tmp/out/apertus-v1.5-8b-text-Q4_K_M.gguf Q4_K_M
    rm -f /tmp/base-f16.gguf
    upload /tmp/out/apertus-v1.5-8b-text-Q4_K_M.gguf
    ;;
check5)
    TINY=HuggingFaceTB/SmolLM2-135M-Instruct
    SHORT="--conditions operations_mix3 --loads 390 --seeds 1 2 --warmup 30 --window 8"
    stamp "third round on the tiny model: instructions, two readers, decider alone, guarded hybrid that asks"
    # shellcheck disable=SC2086
    $PY src/translate.py texts $SHORT --workers 2 --out /tmp/mix3_check.jsonl
    $PY src/translate.py batch --model $TINY --batch 8 --jobs "translate3_check5:nobel-eu:regex:/tmp/mix3_check.jsonl"
    $PY src/translate.py batch --model $TINY --batch 4 --jobs "translate3_check5_few:nobel-eu:regex:/tmp/mix3_check.jsonl"
    # any adapter of the tiny model serves as "the decider's" here: this stage only checks the plumbing
    $PY src/train.py --model $TINY --data-dir data/translate3/s1 --out runs/check5 --no-4bit --limit-train 8 \
        --limit-heldout 2 --max-steps 1 --save-steps 0 --batch 4 --accumulation 1 --eval-records 2 \
        --max-length 2048 --max-new-tokens 8 --skip-merge
    together \
        "$PY src/evaluate.py closed --policy check5_alone_mix3 --backend transformers --model $TINY $SHORT --sim-workers 1" \
        "$PY src/evaluate.py closed --policy hybrid3_check5_ask-check5_few --decider check5_hybrid --decider-adapter runs/check5/adapter --model $TINY $SHORT --sim-workers 1 --out results/eval/hybrid3_check5_mix3.json"
    $PY src/evaluate.py offline --policy check_probes3 --backend transformers --model $TINY \
        --data data/probes --splits v3_new v3_partial --limit 6
    $PY src/translate.py batch --model $TINY --batch 8 --jobs "translate3_check5:nobel-eu:regex:$I/v3_partial.jsonl"
    $PY src/evaluate.py offline --policy hybrid3_check5 --decider check_probes3 --data data/probes \
        --splits v3_partial --limit 6
    ;;
phase4)
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the decider)}" "${TRANSLATOR_REPO:?set TRANSLATOR_REPO (reader 1)}"
    : "${SECOND_REPO:?set SECOND_REPO (reader 2)}"
    $PY -c "
from huggingface_hub import snapshot_download
for repo, where in (('$ADAPTER_REPO', 'runs/adapter'), ('$TRANSLATOR_REPO', 'runs/reader1'), ('$SECOND_REPO', 'runs/reader2')):
    print(snapshot_download(repo, local_dir=where, allow_patterns=['adapter_*', '*.jinja']))
# the base model once, before several processes load it at the same time
print(snapshot_download('$MODEL', allow_patterns=['*.json', '*.safetensors', '*.jinja', 'tokenizer*']))"
    # The prompt exactly as the tokenizer's chat template renders it, to compare with what a
    # llama.cpp server renders from the same messages on a laptop.
    MODEL="$MODEL" $PY - <<'PYEOF'
import os, sys
from pathlib import Path
sys.path.insert(0, "src")
from transformers import AutoTokenizer
from spec import load_topology
from translate import messages
chat = messages("Do not pass through Paris. Limit the route to at most 4 hops.", load_topology("nobel-eu"), version=3)
text = AutoTokenizer.from_pretrained(os.environ["MODEL"]).apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
Path("results/train").mkdir(parents=True, exist_ok=True)
Path("results/train/rendered_prompt3.txt").write_text(text, encoding="utf-8")
print("rendered prompt:", len(text), "characters; ends with", repr(text[-60:]))
PYEOF
    keep results/train/rendered_prompt3.txt
    # Two model processes at a time: one translator process with 128 prompts of 620 tokens peaked at
    # 32 GB, and four of them did not fit the 80 GB card. The answer caches are copied to the work
    # repo after each pair (one writer at a time).
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    BATCH="$PY src/translate.py batch --model $MODEL"
    stamp "two processes: reader 1 (all sets) and reader 2"
    together \
        "$BATCH --adapter runs/reader1 --batch 96 --jobs translate3_ft:nobel-eu:regex:$V3,$EARLIER,$I/gsw.jsonl,$I/noisy.jsonl,$I/mix3.jsonl translate3_ft:germany50:regex:$I/germany50.jsonl" \
        "$BATCH --adapter runs/reader2 --batch 96 --jobs translate3_ft2:nobel-eu:regex:$V3,$EARLIER,$I/mix3.jsonl"
    keep results/translate results/cache
    stamp "two processes: the reader with examples, and the decider on the probes"
    together \
        "$BATCH --batch 48 --jobs translate3_few:nobel-eu:regex:$V3" \
        "$PY src/evaluate.py offline --policy apertus_ft_probes --backend transformers --model $MODEL --adapter runs/adapter --data data/probes --splits v3_new v3_new_hard v3_new_impossible v3_partial v3_en --batch-envs 48 --out results/offline/apertus_ft_probes3.json"
    keep results/translate results/cache results/offline
    stamp "closed loop, mixed condition of the third round: decider alone, hybrid, hybrid that asks (one GPU)"
    CLOSED="--model $MODEL --conditions operations_mix3 --sim-workers 2"
    together \
        "$PY src/evaluate.py closed --policy apertus_ft_mix3 --backend transformers --adapter runs/adapter $CLOSED $SYNC" \
        "$PY src/evaluate.py closed --policy hybrid3_ft --decider apertus_ft_hybrid3 --decider-adapter runs/adapter $CLOSED --out results/eval/hybrid3_ft_mix3.json" \
        "$PY src/evaluate.py closed --policy hybrid3_ft_ask-ft2 --decider apertus_ft_hybrid3ask --decider-adapter runs/adapter $CLOSED --out results/eval/hybrid3_ft_ask-ft2_mix3.json"
    ;;
phase5)
    # Both readers answer from their caches only, so every instruction of the episodes must have
    # been read before (reader 1 in phase4; the larger model in the stage big with BIG_SETS). A
    # missing one stops the run. Only the decider is loaded.
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the decider)}"
    SECOND=${SECOND:-few70b}
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$ADAPTER_REPO', local_dir='runs/adapter', allow_patterns=['adapter_*', '*.jinja']))
print(snapshot_download('$MODEL', allow_patterns=['*.json', '*.safetensors', '*.jinja', 'tokenizer*']))"
    stamp "closed loop, operations_mix3: the hybrid that asks, second reader translate3_$SECOND from its cache"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy "hybrid3_ft_ask-$SECOND" --decider "apertus_ft_hybrid3ask${SECOND#few}" \
        --decider-adapter runs/adapter --model $MODEL --conditions operations_mix3 --sim-workers 2 \
        ${EVAL_ARGS:-} $SYNC --out "results/eval/hybrid3_ft_ask-${SECOND}_mix3.json"
    ;;
read4)
    # The full-format reader reads the mixed condition's instructions. The job re-scores every set it
    # was scored on before as well, because a batch replaces results/translate/translate4_ft.json:
    # those sentences come from the answer cache, only the new ones are asked of the model.
    : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO (the fourth-format reader)}"
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$TRANSLATOR_REPO', local_dir='runs/translator4', allow_patterns=['adapter_*', '*.jinja']))
print(snapshot_download('$MODEL', allow_patterns=['*.json', '*.safetensors', '*.jinja', 'tokenizer*']))"
    V4="$I/v4_en.jsonl,$I/v4_de.jsonl,$I/v4_fr.jsonl,$I/v4_it.jsonl"
    stamp "translate4_ft: the fourth and third rounds' test sets (cached) and the mixed condition (new)"
    $PY src/translate.py batch --model "$MODEL" --adapter runs/translator4 --batch 96 --sync-repo "$WORK_REPO" \
        --jobs "translate4_ft:nobel-eu:regex:$V4,$I/owner.jsonl,$V3,$I/mix3.jsonl"
    keep results/translate results/cache
    ;;
train-d3)
    # The matched decider: the first decider's 12,000 states with the routing-field reader's own
    # training sentences (data/full3, src/decider3_data.py). One epoch per job, as for the first
    # decider; a second epoch is TRAIN_ARGS="--init-adapter <the first epoch's repo> --lr 1e-4".
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the repo the matched decider is pushed to)}"
    stamp "fine-tune the matched decider on data/full3 (resumes from $ADAPTER_REPO if a checkpoint is there)"
    # shellcheck disable=SC2086
    $PY src/train.py --model "$MODEL" --data-dir data/full3 --out runs/decider3 --hub-adapter "$ADAPTER_REPO" \
        --resume --save-steps 100 --epochs 1 --skip-merge ${TRAIN_ARGS:-}
    OUT_DIR="results/train/$(basename "$ADAPTER_REPO")"
    mkdir -p "$OUT_DIR"
    cp runs/decider3/training_log.json runs/decider3/heldout_predictions.jsonl "$OUT_DIR/"
    keep "$OUT_DIR"
    ;;
eval-d3)
    # Needs read4 first (the full-format reader's answers to every instruction of the mixed
    # condition are in the work repo's cache; the hybrids answer from it and stop on a missing one).
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the matched decider)}" "${DECIDER_REPO:?set DECIDER_REPO (the first decider)}"
    $PY -c "
from huggingface_hub import snapshot_download
for repo, where in (('$ADAPTER_REPO', 'runs/decider3'), ('$DECIDER_REPO', 'runs/adapter')):
    print(snapshot_download(repo, local_dir=where, allow_patterns=['adapter_*', '*.jinja']))
print(snapshot_download('$MODEL', allow_patterns=['*.json', '*.safetensors', '*.jinja', 'tokenizer*']))"
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    stamp "offline: the matched decider on the probes (four languages, new types, carried in part); the first decider on German, French, Italian"
    together \
        "$PY src/evaluate.py offline --policy apertus3_ft_probes --backend transformers --model $MODEL --adapter runs/decider3 --data data/probes --splits v3_en v3_de v3_fr v3_it v3_new v3_new_hard v3_new_impossible v3_partial --batch-envs 48 --out results/offline/apertus3_ft_probes3.json" \
        "$PY src/evaluate.py offline --policy apertus_ft_probes --backend transformers --model $MODEL --adapter runs/adapter --data data/probes --splits v3_de v3_fr v3_it --batch-envs 48 --out results/offline/apertus_ft_probes3_langs.json"
    keep results/offline results/cache
    stamp "closed loop, mixed condition: the matched decider alone; the full-format reader in front of the first and of the matched decider"
    CLOSED="--model $MODEL --conditions operations_mix3 --sim-workers 2"
    # shellcheck disable=SC2086
    together \
        "$PY src/evaluate.py closed --policy apertus3_ft_mix3 --backend transformers --adapter runs/decider3 $CLOSED $SYNC" \
        "$PY src/evaluate.py closed --policy hybrid4_ft --decider apertus_ft_hybrid4 --decider-adapter runs/adapter $CLOSED --out results/eval/hybrid4_ft_mix3.json" \
        "$PY src/evaluate.py closed --policy hybrid4_ft --decider apertus3_ft_hybrid4 --decider-adapter runs/decider3 $CLOSED --out results/eval/hybrid4_ft_d3_mix3.json"
    ;;
hybrids-d3)
    # The two hybrids of eval-d3 on their own (they stopped there on a stale reader cache, 14 Oct).
    # Run it with no other job going: every job copies its whole results folder back when it ends.
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the matched decider)}" "${DECIDER_REPO:?set DECIDER_REPO (the first decider)}"
    $PY -c "
from huggingface_hub import snapshot_download
for repo, where in (('$ADAPTER_REPO', 'runs/decider3'), ('$DECIDER_REPO', 'runs/adapter')):
    print(snapshot_download(repo, local_dir=where, allow_patterns=['adapter_*', '*.jinja']))
print(snapshot_download('$MODEL', allow_patterns=['*.json', '*.safetensors', '*.jinja', 'tokenizer*']))"
    $PY - <<'PYEOF'
import sys
from pathlib import Path
cache = Path("results/cache/translate4_ft.jsonl")
lines = sum(1 for _ in cache.open(encoding="utf-8"))
print("translate4_ft cache:", lines, "answers")
if lines < 7000:
    sys.exit("the full-format reader's cache is the stale one: restore it first")
PYEOF
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    stamp "closed loop, mixed condition: the full-format reader in front of the first and of the matched decider"
    CLOSED="--model $MODEL --conditions operations_mix3 --sim-workers 2"
    # shellcheck disable=SC2086
    together \
        "$PY src/evaluate.py closed --policy hybrid4_ft --decider apertus_ft_hybrid4 --decider-adapter runs/adapter $CLOSED $SYNC --out results/eval/hybrid4_ft_mix3.json" \
        "$PY src/evaluate.py closed --policy hybrid4_ft --decider apertus3_ft_hybrid4 --decider-adapter runs/decider3 $CLOSED --out results/eval/hybrid4_ft_d3_mix3.json"
    ;;
check6)
    # CPU only, tiny model: the plumbing of read4, train-d3 and eval-d3 (data/full3, probes in four
    # languages, a fourth-format reader in front of a live decider in the mixed condition).
    TINY=HuggingFaceTB/SmolLM2-135M-Instruct
    SHORT="--conditions operations_mix3 --loads 390 --seeds 1 --warmup 30 --window 8"
    stamp "training on data/full3 (tiny model, two steps) and its held-out predictions"
    $PY src/train.py --model $TINY --data-dir data/full3 --out runs/check6 --no-4bit --limit-train 16 \
        --limit-heldout 4 --max-steps 2 --save-steps 0 --batch 4 --accumulation 1 --eval-records 4 --skip-merge
    $PY src/evaluate.py offline --policy check6_heldout --predictions runs/check6/heldout_predictions.jsonl \
        --data data/full3 --splits heldout_indist heldout_paraphrase heldout_pairs --limit 4
    stamp "the decider on probes in another language"
    $PY src/evaluate.py offline --policy check6_probes --backend transformers --model $TINY \
        --adapter runs/check6/adapter --data data/probes --splits v3_de v3_new --limit 6 --batch-envs 4
    stamp "a fourth-format reader (tiny) on the short episodes' instructions, then the hybrid with a live decider"
    # shellcheck disable=SC2086
    $PY src/translate.py texts $SHORT --workers 1 --out /tmp/mix3_check6.jsonl
    $PY src/translate.py batch --model $TINY --batch 8 --jobs "translate4_check6:nobel-eu:regex:/tmp/mix3_check6.jsonl"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy hybrid4_check6 --decider check6_hybrid --decider-adapter runs/check6/adapter \
        --model $TINY $SHORT --sim-workers 1 --out results/eval/hybrid4_check6_mix3.json
    ;;
check2)
    TINY=HuggingFaceTB/SmolLM2-135M-Instruct
    stamp "second translator format on the tiny model: examples, training, adapter, probes"
    $PY src/translate.py batch --model $TINY --batch 8 --jobs \
        "translate2_check_few:nobel-eu:regex:$I/not_instruction.jsonl"
    $PY src/train.py --model $TINY --data-dir data/translate2 --out runs/check-translator2 --no-4bit \
        --limit-train 16 --limit-heldout 4 --max-steps 2 --save-steps 0 --batch 4 --accumulation 1 \
        --eval-records 4 --max-length 1536 --max-new-tokens 48
    $PY src/translate.py batch --model $TINY --adapter runs/check-translator2/adapter --batch 8 --jobs \
        "translate2_check_ft:nobel-eu:regex:$I/not_instruction.jsonl"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy check_probes2 --backend transformers --model $TINY \
        --data data/probes --splits $PROBES2 --limit 6
    $PY src/evaluate.py offline --policy hybrid2_check_few --decider check_probes2 --data data/probes \
        --splits not_instruction --limit 6
    ;;
check3)
    TINY=HuggingFaceTB/SmolLM2-135M-Instruct
    SHORT="--conditions operations_mix --loads 390 --seeds 1 2 --warmup 30 --window 8"
    stamp "mixed condition on the tiny model: instructions, translation, decider alone, hybrid with a live decider"
    # shellcheck disable=SC2086
    $PY src/translate.py texts $SHORT --workers 2 --out /tmp/mix_check.jsonl
    $PY src/translate.py batch --model $TINY --batch 8 --jobs "translate2_check3:nobel-eu:regex:/tmp/mix_check.jsonl"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy check3_decider --backend transformers --model $TINY $SHORT --sim-workers 2
    # any adapter of the tiny model serves as "the decider's" here: this stage only checks the plumbing
    $PY src/train.py --model $TINY --data-dir data/translate2 --out runs/check3 --no-4bit --limit-train 8 \
        --limit-heldout 2 --max-steps 1 --save-steps 0 --batch 4 --accumulation 1 --eval-records 2 \
        --max-length 1536 --max-new-tokens 8
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy hybrid2_check3 --decider check3_hybrid --decider-adapter runs/check3/adapter \
        --model $TINY $SHORT --sim-workers 2 --out results/eval/hybrid2_check3_mix.json
    ;;
phase3)
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the decider)}" "${TRANSLATOR_REPO:?set TRANSLATOR_REPO}"
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$ADAPTER_REPO', local_dir='runs/adapter', allow_patterns=['adapter_*', '*.jinja']))
print(snapshot_download('$TRANSLATOR_REPO', local_dir='runs/translator2/adapter', allow_patterns=['adapter_*', '*.jinja']))"
    stamp "second translator, fine-tuned: the instructions of the mixed condition"
    $PY src/translate.py batch --model "$MODEL" --adapter runs/translator2/adapter --batch 96 \
        --sync-repo "$WORK_REPO" --jobs "translate2_ft:nobel-eu:regex:$I/mix.jsonl"
    stamp "decider alone: mixed condition, closed loop"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy apertus_ft_mix --backend transformers --model "$MODEL" --adapter runs/adapter \
        --conditions operations_mix --sim-workers "$WORKERS" $SYNC
    stamp "hybrid (second translator, then decider): mixed condition, closed loop"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy hybrid2_ft --decider apertus_ft_hybridmix --decider-adapter runs/adapter \
        --model "$MODEL" --conditions operations_mix --sim-workers "$WORKERS" \
        --out results/eval/hybrid2_ft_mix.json $SYNC
    ;;
phase2)
    : "${ADAPTER_REPO:?set ADAPTER_REPO (the decider)}"
    stamp "second translator format, with examples: all instruction sets"
    $PY src/translate.py batch --model "$MODEL" --batch 96 --sync-repo "$WORK_REPO" --jobs \
        "translate2_few:nobel-eu:regex:$TESTS,$NEW"
    keep results/translate
    stamp "fine-tuned decider: the new probe sets"
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$ADAPTER_REPO', local_dir='runs/adapter', allow_patterns=['adapter_*', '*.jinja']))"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy apertus_ft_probes --backend transformers --model "$MODEL" \
        --adapter runs/adapter --data data/probes --splits $PROBES2 --batch-envs 64 \
        --out results/offline/apertus_ft_probes2.json $SYNC
    ;;
phase2-ft)
    : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO}"
    stamp "fine-tune the second translator (resumes from $TRANSLATOR_REPO if a checkpoint is there)"
    # shellcheck disable=SC2086
    $PY src/train.py --model "$MODEL" --data-dir data/translate2 --out runs/translator2 \
        --hub-adapter "$TRANSLATOR_REPO" --resume --save-steps 50 --max-length 768 --max-new-tokens 48 \
        --eval-records 100 ${TRAIN_ARGS:-}
    keep runs/translator2/training_log.json runs/translator2/heldout_predictions.jsonl
    stamp "second translator, fine-tuned: all instruction sets"
    $PY src/translate.py batch --model "$MODEL" --adapter runs/translator2/adapter --batch 96 \
        --sync-repo "$WORK_REPO" --jobs "translate2_ft:nobel-eu:regex:$TESTS,$NEW" \
        "translate2_ft:germany50:regex:$I/germany50.jsonl" "translate2_ft:nobel-eu:regex:$I/closed_loop.jsonl"
    ;;
phase1-closed)
    : "${CLOSED_POLICIES:?set CLOSED_POLICIES, e.g. \"translate_few translate_ft\"}"
    for policy in $CLOSED_POLICIES; do
        adapter=()
        if [[ "$policy" == *_ft* ]]; then
            : "${TRANSLATOR_REPO:?set TRANSLATOR_REPO}"
            $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$TRANSLATOR_REPO', local_dir='runs/translator/adapter', allow_patterns=['adapter_*', '*.jinja']))"
            adapter=(--adapter runs/translator/adapter)
        fi
        stamp "$policy: every instruction of the closed-loop protocol"
        $PY src/translate.py batch --model "$MODEL" "${adapter[@]}" --batch 96 --sync-repo "$WORK_REPO" \
            --jobs "$policy:nobel-eu:regex:$I/closed_loop.jsonl"
    done
    ;;
*)
    echo "unknown stage $STAGE" >&2
    exit 2
    ;;
esac
stamp "done"
