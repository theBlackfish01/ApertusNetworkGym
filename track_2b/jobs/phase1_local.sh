#!/bin/bash
# Phase 1, laptop side: score translators and replay their closed loop. No GPU, no model: the
# keyword parser needs none, and Apertus' answers come from the caches a phase1 job left in
# results/cache/ (a missing answer stops the run with an error).
#
#   bash jobs/phase1_local.sh translate_keyword translate_zero translate_few translate_ft
#
# Per translator: translation accuracy on every instruction set; decisions on the held-out
# splits, the probe sets and the other topology; the closed-loop protocol (42 episodes), and the
# unseen-pairs condition once more under the ordered reading of two preferences.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="uv run --no-sync python"
I=data/instructions
SETS="$I/templates.jsonl $I/independent.jsonl $I/de.jsonl $I/fr.jsonl $I/it.jsonl $I/gsw.jsonl $I/noisy.jsonl $I/faulty.jsonl $I/out_of_scope.jsonl $I/closed_loop.jsonl"
PROBES="independent de fr it gsw noisy faulty out_of_scope"
WORKERS=${WORKERS:-3}
for policy in "$@"; do
    echo "=== $policy: translation accuracy"
    # shellcheck disable=SC2086
    $PY src/translate.py score --policy "$policy" --sets $SETS
    $PY src/translate.py score --policy "$policy" --topology germany50 --sets $I/germany50.jsonl \
        --out "results/translate/${policy}_germany50.json"
    echo "=== $policy: decisions on the held-out splits, the probe sets and the other topology"
    $PY src/evaluate.py offline --policy "$policy"
    # shellcheck disable=SC2086
    $PY src/evaluate.py offline --policy "$policy" --data data/probes --splits $PROBES \
        --out "results/offline/${policy}_probes.json"
    $PY src/evaluate.py offline --policy "$policy" --topology germany50 --data data/probes --splits germany50 \
        --out "results/offline/${policy}_probes_germany50.json"
    echo "=== $policy: closed loop"
    $PY src/evaluate.py closed --policy "$policy" --workers "$WORKERS"
    $PY src/evaluate.py closed --policy "${policy}_ordered" --conditions heldout_pairs --workers "$WORKERS"
done
$PY src/evaluate.py offline --policy oracle --data data/probes --splits $PROBES germany50 \
    --out results/offline/oracle_probes.json
$PY src/report_phase1.py > /dev/null
echo "wrote results/tables/phase1.md"
