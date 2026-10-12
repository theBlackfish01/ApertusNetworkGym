#!/bin/sh
# Entry point of `make run` (inside the container; also works in the uv environment).
# 1. Rebuild the results tables from the JSON files in results/. No GPU, no network.
# 2. Show 50 requests flowing through the proposed system, the hybrid: two readers translate each
#    operator instruction into one line of the policy language, the rule engine decides, and what
#    lies outside the language goes to the decider. Without a server this replays the episode as it
#    was recorded on a laptop (RTX 4060, llama.cpp, 4-bit model): every answer is in results/cache/.
#    With LLM_BASE_URL pointing at a llama.cpp server that holds the base model and the three
#    adapters (README, "On a laptop"), the same episode runs live; LLM_LORA_IDS names the adapters.
# 3. Show a few requests decided by the fine-tuned decider alone, from its recorded answers.
set -e
cd "$(dirname "$0")"

python src/report_tables.py
python src/report_phase1.py > /dev/null && echo && echo "Translator against decider (phase 1): results/tables/phase1.md"
python src/report_phase2.py > /dev/null && echo "Stronger translator and hybrid (second round): results/tables/phase2.md"
python src/report_phase3.py > /dev/null && echo "Policy language, two readers, guarded fallback (third round): results/tables/phase3.md"

EPISODE="--conditions operations_mix3 --loads 390 --seeds 11 --warmup 300 --window 50 --show 14"
echo
if [ -n "$LLM_BASE_URL" ]; then
    echo "=== Live: 50 requests through the hybrid, models at $LLM_BASE_URL ==="
    # other names than the recorded run, so that nothing is replayed from its answers
    : "${LLM_LORA_IDS:={\"translate3_ft_live\": 0, \"translate3_ft2_live\": 1, \"apertus_ft_live\": 2}}"
    export LLM_LORA_IDS
    # shellcheck disable=SC2086
    python src/evaluate.py demo --policy hybrid3_ft_live_ask-ft2_live --decider apertus_ft_live $EPISODE         --base-url "$LLM_BASE_URL" --concurrency 1
elif [ -f results/cache/apertus_ft_laptop.jsonl ]; then
    echo "=== 50 requests through the hybrid, replayed as recorded on a laptop (LLM_BASE_URL not set) ==="
    # shellcheck disable=SC2086
    python src/evaluate.py demo --policy hybrid3_ft_laptop_ask-ft2_laptop --decider apertus_ft_laptop $EPISODE
fi
echo
if [ -f results/cache/apertus_ft_demo.jsonl ]; then
    echo "=== For comparison, the fine-tuned decider alone: recorded answers, dataset wording ==="
    python src/evaluate.py demo --policy apertus_ft_demo
else
    echo "=== The MLP control (no recorded Apertus answers) ==="
    python src/evaluate.py demo --policy mlp
fi
