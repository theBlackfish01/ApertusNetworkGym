.PHONY: run test

# What the judges run, from a clean checkout: builds the image (ONG compiled from source),
# prints the results tables rebuilt from results/, then runs a 50-request closed-loop demo.
# No GPU needed. Set LLM_BASE_URL (and LLM_NAME, LLM_API_KEY) for a live Apertus demo.
run:
	docker compose run --rm --build lightpath

# The operator console in the browser (http://localhost:8090): one stream under standing policies and
# per-request instructions, a map and a feed of what the model does; recorded answers, or live with
# LLM_BASE_URL set to a llama.cpp server (README, "On a laptop").
console:
	docker compose run --rm --build --service-ports lightpath python src/console.py --host 0.0.0.0

# Development: unit tests in the local uv environment (WSL2/Linux).
test:
	uv run pytest -q
