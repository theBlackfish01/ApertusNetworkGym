#!/bin/bash
# Start one stage of jobs/run.sh as a Hugging Face Job and print its id.
#   bash jobs/launch.sh <stage> <flavor> <timeout>      e.g.  bash jobs/launch.sh smoke a100-large 25m
# Needs HF_TOKEN, WORK_REPO and (for train/eval) ADAPTER_REPO in the environment; MODEL, TRAIN_ARGS,
# EVAL_ARGS, ZS_ARGS, SKIP_ZERO_SHOT, TRANSLATOR_REPO and CLOSED_POLICIES are passed through when set. The timeout is the spending cap of the job.
# Follow it with:  hf jobs logs -f <id>     Stop it with:  hf jobs cancel <id>
set -euo pipefail
stage=${1:?stage} flavor=${2:?flavor} timeout=${3:?timeout}
: "${WORK_REPO:?set WORK_REPO}" "${HF_TOKEN:?set HF_TOKEN}"
env_flags=(-e "WORK_REPO=$WORK_REPO")
for name in ADAPTER_REPO MODEL TRAIN_ARGS EVAL_ARGS ZS_ARGS SKIP_ZERO_SHOT TRANSLATOR_REPO CLOSED_POLICIES READER \
    SECOND_REPO BIG_MODEL; do
    [ -n "${!name:-}" ] && env_flags+=(-e "$name=${!name}")
done
uvx --from "huggingface_hub[cli]" hf jobs run --detach --flavor "$flavor" --timeout "$timeout" \
    --secrets HF_TOKEN "${env_flags[@]}" --name "lightpath-$stage" \
    ghcr.io/astral-sh/uv:python3.12-bookworm \
    bash -c 'uvx --from "huggingface_hub[cli]" hf download "$WORK_REPO" --repo-type dataset --local-dir /work --quiet && bash /work/jobs/run.sh '"$stage"
