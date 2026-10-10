#!/bin/bash
# Runs inside a Hugging Face Job, from the root of the work repo (code, data, earlier results).
#
#   check   the whole pipeline on a tiny open model, CPU only: validates the image, the plumbing
#           and the failure/resume path (a training run is killed on purpose and resumed)
#   smoke   a few training steps and a short closed loop with the real model: measures throughput
#   train   full fine-tuning; resumes from the Hub if an earlier job left a checkpoint
#   eval    closed-loop and offline evaluation of the fine-tuned and the zero-shot model
#
# Nothing a job computes is kept only in the job. Training pushes a checkpoint (adapter, optimizer,
# scheduler) every 100 optimizer steps and the adapter at every epoch; evaluation appends every
# model answer to a cache that is copied to the work repo every two minutes; and whatever exists
# is copied once more when the script exits, whether it finished or failed. Launching the same
# stage again continues from there.
#
# Environment: WORK_REPO (dataset repo holding this bundle; results are copied back to it),
# ADAPTER_REPO (model repo for the adapter), HF_TOKEN (secret); optional MODEL, TRAIN_ARGS,
# EVAL_ARGS (fine-tuned closed loop), ZS_ARGS (zero-shot closed loop).
set -euo pipefail
STAGE=${1:?stage: check | smoke | train | eval}
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
    $PY src/evaluate.py offline --policy check_ft --predictions runs/check/heldout_predictions.jsonl --limit 4
    stamp "closed loop (tiny model + adapter)"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy check_local --backend transformers --model $TINY \
        --adapter runs/check/adapter --conditions I0 I1 --loads 390 --seeds 1 --warmup 50 --window 10 \
        --sim-workers 2 $SYNC
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
    stamp "fine-tuned: closed loop"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy apertus_ft --backend transformers --model "$MODEL" --adapter runs/adapter \
        --sim-workers "$WORKERS" $SYNC ${EVAL_ARGS:-}
    stamp "fine-tuned: demo answers for make run"
    $PY src/evaluate.py demo --policy apertus_ft_demo --backend transformers --model "$MODEL" --adapter runs/adapter
    keep results/cache/apertus_ft_demo.jsonl
    stamp "zero-shot: offline agreement, with and without the answer constraint"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy apertus_zero_shot --backend transformers --model "$MODEL" $SYNC
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy apertus_zero_shot_unconstrained --backend transformers --model "$MODEL" \
        --structured none $SYNC
    stamp "zero-shot: closed loop"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy apertus_zero_shot --backend transformers --model "$MODEL" \
        --sim-workers "$WORKERS" $SYNC ${ZS_ARGS:-}
    ;;
*)
    echo "unknown stage $STAGE" >&2
    exit 2
    ;;
esac
stamp "done"
