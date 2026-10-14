#!/bin/bash
# Upload what a job needs (code, lock file, dataset splits, MLP weights) to the private work repo.
# Run from track_2b/ with HF_TOKEN and WORK_REPO set, e.g.
#   WORK_REPO=<user>/apertus-lightpath-work bash jobs/push_bundle.sh "prompt v2"
set -euo pipefail
: "${WORK_REPO:?set WORK_REPO}" "${HF_TOKEN:?set HF_TOKEN}"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage"/{src,jobs,data/full,results/mlp,data/instructions,data/probes,data/translate,data/translate2,data/fewshot,data/topologies}
cp src/*.py "$stage/src/"
cp jobs/run.sh "$stage/jobs/"
cp pyproject.toml uv.lock .python-version README.md "$stage/"
cp data/full/*.jsonl "$stage/data/full/"
# The matched decider's data (decider3_data.py); absent before that.
[ -d data/full3 ] && mkdir -p "$stage/data/full3" && cp data/full3/*.json* "$stage/data/full3/"
# Phase 1 (built by corpora.py, transfer.py and "translate.py texts"); absent before that.
for dir in instructions probes translate translate2 fewshot topologies; do
    cp data/$dir/*.json* "$stage/data/$dir/" 2>/dev/null || true
done
# Third round: one training set per reader (corpora3.py).
for reader in data/translate3/s* data/translate4/s*; do
    [ -d "$reader" ] && mkdir -p "$stage/$reader" && cp "$reader"/*.jsonl "$stage/$reader/"
done
cp results/mlp/* "$stage/results/mlp/"
uvx --from "huggingface_hub[cli]" hf upload "$WORK_REPO" "$stage" . --repo-type dataset --private \
    --commit-message "${1:-bundle}"
