#!/bin/bash
# Runs inside a Hugging Face Job, from the root of the work repo (code, data, earlier results).
#
#   check   the whole pipeline on a tiny open model, CPU only: validates the image and the plumbing
#   smoke   a few training steps and a short closed loop with the real model: measures throughput
#   train   full fine-tuning; pushes the adapter, the log and the held-out predictions
#   eval    closed-loop and offline evaluation of the fine-tuned and the zero-shot model
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
PY=/opt/venv/bin/python
$PY -c "import torch; print('torch', torch.__version__, '| cuda', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu', '| threads', torch.get_num_threads())"
WORKERS=$((CPUS > 3 ? CPUS - 2 : 1))
SYNC="--sync-repo $WORK_REPO"

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
                          ignore_patterns=["checkpoints/*", "merged/*", "adapter-epoch*/*"])
    elif path.exists():
        api.upload_file(repo_id=repo, repo_type="dataset", path_or_fileobj=name, path_in_repo=name)
    print("kept", name)
PYEOF
}

case "$STAGE" in
check)
    TINY=HuggingFaceTB/SmolLM2-135M-Instruct
    stamp "train (tiny model)"
    $PY src/train.py --model $TINY --data-dir data/full --out runs/check --no-4bit --limit-train 32 \
        --limit-heldout 4 --max-steps 2 --batch 4 --accumulation 1 --eval-records 8
    $PY src/evaluate.py offline --policy check_ft --predictions runs/check/heldout_predictions.jsonl --limit 4
    stamp "closed loop (tiny model + adapter)"
    $PY src/evaluate.py closed --policy check_local --backend transformers --model $TINY \
        --adapter runs/check/adapter --conditions I0 I1 --loads 390 --seeds 1 --warmup 50 --window 10 \
        --sim-workers 2 $SYNC
    keep runs/check/training_log.json
    ;;
smoke)
    stamp "train, 4-bit QLoRA, 10 optimizer steps"
    $PY src/train.py --model "$MODEL" --data-dir data/full --out runs/smoke-4bit --limit-train 480 \
        --limit-heldout 32 --max-steps 10 --eval-records 32
    keep runs/smoke-4bit/training_log.json runs/smoke-4bit/heldout_predictions.jsonl
    stamp "train, bf16 LoRA, 10 optimizer steps (speed comparison)"
    $PY src/train.py --model "$MODEL" --data-dir data/full --out runs/smoke-bf16 --no-4bit --limit-train 480 \
        --limit-heldout 8 --max-steps 10 --eval-records 32 --skip-merge
    keep runs/smoke-bf16/training_log.json
    stamp "zero-shot: offline agreement on 64 records per split"
    $PY src/evaluate.py offline --policy smoke_zero_shot --backend transformers --model "$MODEL" --limit 64 $SYNC
    stamp "zero-shot: all 42 environments, 20 requests each (throughput)"
    $PY src/evaluate.py closed --policy smoke_zero_shot --backend transformers --model "$MODEL" \
        --warmup 100 --window 20 --sim-workers "$WORKERS" $SYNC
    stamp "adapter from the 10 steps: short closed loop (checks the merge path)"
    $PY src/evaluate.py closed --policy smoke_ft --backend transformers --model "$MODEL" \
        --adapter runs/smoke-4bit/adapter --conditions I0 I1 --loads 390 --seeds 1 --warmup 100 --window 20 \
        --sim-workers 2 $SYNC
    ;;
train)
    : "${ADAPTER_REPO:?set ADAPTER_REPO}"
    stamp "train"
    # shellcheck disable=SC2086
    $PY src/train.py --model "$MODEL" --data-dir data/full --out runs/apertus-ft --hub-adapter "$ADAPTER_REPO" \
        ${TRAIN_ARGS:-}
    keep runs/apertus-ft/training_log.json runs/apertus-ft/heldout_predictions.jsonl
    ;;
eval)
    : "${ADAPTER_REPO:?set ADAPTER_REPO}"
    stamp "download adapter"
    $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$ADAPTER_REPO', local_dir='runs/adapter', allow_patterns=['adapter_*', '*.json', '*.jinja']))"
    stamp "fine-tuned: closed loop"
    # shellcheck disable=SC2086
    $PY src/evaluate.py closed --policy apertus_ft --backend transformers --model "$MODEL" --adapter runs/adapter \
        --sim-workers "$WORKERS" $SYNC ${EVAL_ARGS:-}
    stamp "fine-tuned: demo answers for make run"
    $PY src/evaluate.py demo --policy apertus_ft_demo --backend transformers --model "$MODEL" --adapter runs/adapter
    keep results/cache/apertus_ft_demo.jsonl
    stamp "zero-shot: offline agreement"
    $PY src/evaluate.py offline --policy apertus_zero_shot --backend transformers --model "$MODEL" $SYNC
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
