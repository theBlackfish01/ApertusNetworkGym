#!/bin/sh
# Entry point of `make run` (inside the container; also works in the uv environment).
# 1. Rebuild the results tables from the JSON files in results/. No GPU, no network.
# 2. Run a 50-request closed-loop demo through the simulator:
#    - with the endpoint in LLM_BASE_URL, if set (LLM_NAME, LLM_API_KEY as in .env.example);
#    - else by replaying the fine-tuned model's recorded answers, if results/cache has them;
#    - else with the MLP control, so the pipeline is still shown end to end.
set -e
cd "$(dirname "$0")"

python src/report_tables.py

echo
if [ -n "$LLM_BASE_URL" ]; then
    echo "=== Live demo: 50 requests decided by ${LLM_NAME:-the model} at $LLM_BASE_URL ==="
    python src/evaluate.py demo --policy live_demo
elif [ -f results/cache/apertus_ft_demo.jsonl ]; then
    echo "=== Demo: replaying the fine-tuned Apertus answers recorded in results/cache/ (LLM_BASE_URL not set) ==="
    python src/evaluate.py demo --policy apertus_ft_demo
else
    echo "=== Demo with the MLP control (LLM_BASE_URL not set and no recorded Apertus answers) ==="
    python src/evaluate.py demo --policy mlp
fi
