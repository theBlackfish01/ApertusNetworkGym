#!/bin/bash
# Upload what a job needs (code, lock file, dataset splits, MLP weights) to the private work repo.
# Run from track_2b/ with HF_TOKEN and WORK_REPO set, e.g.
#   WORK_REPO=<user>/apertus-lightpath-work bash jobs/push_bundle.sh "prompt v2"
set -euo pipefail
: "${WORK_REPO:?set WORK_REPO}" "${HF_TOKEN:?set HF_TOKEN}"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage"/{src,jobs,data/full,results/mlp}
cp src/*.py "$stage/src/"
cp jobs/run.sh "$stage/jobs/"
cp pyproject.toml uv.lock .python-version README.md "$stage/"
cp data/full/*.jsonl "$stage/data/full/"
cp results/mlp/* "$stage/results/mlp/"
uvx --from "huggingface_hub[cli]" hf upload "$WORK_REPO" "$stage" . --repo-type dataset --private \
    --commit-message "${1:-bundle}"
