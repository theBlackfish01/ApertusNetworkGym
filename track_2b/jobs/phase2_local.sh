#!/bin/bash
# Second round, laptop side (no GPU): the second translators and the hybrid, from the answer caches
# that the phase2 jobs left in results/cache/ (a missing answer stops the run with an error).
#
#   bash jobs/phase2_local.sh              # KINDS="few ft" by default
set -euo pipefail
cd "$(dirname "$0")/.."
PY="uv run --no-sync python"
I=data/instructions
OLD="$I/templates.jsonl $I/independent.jsonl $I/de.jsonl $I/fr.jsonl $I/it.jsonl $I/gsw.jsonl $I/noisy.jsonl $I/faulty.jsonl $I/out_of_scope.jsonl"
NEW="$I/unseen.jsonl $I/unseen_impossible.jsonl $I/not_instruction.jsonl $I/de_ind.jsonl $I/fr_ind.jsonl $I/it_ind.jsonl"
PROBES="independent de fr it gsw noisy faulty out_of_scope"
PROBES2="unseen unseen_impossible not_instruction de_ind fr_ind it_ind"
WORKERS=${WORKERS:-3}
for kind in ${KINDS:-few ft}; do
    policy=translate2_$kind
    closed=""
    [ "$kind" = ft ] && closed="$I/closed_loop.jsonl"
    echo "=== $policy: translation accuracy"
    # shellcheck disable=SC2086
    $PY src/translate.py score --policy "$policy" --sets $OLD $NEW $closed
    echo "=== $policy and hybrid2_$kind: decisions on the held-out splits and the probe sets"
    $PY src/evaluate.py offline --policy "$policy"
    for arm in "$policy" "hybrid2_$kind"; do
        # shellcheck disable=SC2086
        $PY src/evaluate.py offline --policy "$arm" --data data/probes --splits $PROBES $PROBES2 \
            --out "results/offline/${arm}_probes.json"
    done
    if [ "$kind" = ft ]; then
        $PY src/translate.py score --policy "$policy" --topology germany50 --sets $I/germany50.jsonl \
            --out "results/translate/${policy}_germany50.json"
        $PY src/evaluate.py offline --policy "$policy" --topology germany50 --data data/probes --splits germany50 \
            --out "results/offline/${policy}_probes_germany50.json"
        echo "=== $policy: closed loop"
        $PY src/evaluate.py closed --policy "$policy" --workers "$WORKERS"
        $PY src/evaluate.py closed --policy "${policy}_ordered" --conditions heldout_pairs --workers "$WORKERS"
    fi
done
# shellcheck disable=SC2086
$PY src/evaluate.py offline --policy oracle --data data/probes --splits $PROBES2 --out results/offline/oracle_probes2.json
echo "done"
