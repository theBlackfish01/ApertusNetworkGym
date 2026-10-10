.PHONY: run test

# What the judges run, from a clean checkout: builds the image (ONG compiled from source),
# prints the results tables rebuilt from results/, then runs a 50-request closed-loop demo.
# No GPU needed. Set LLM_BASE_URL (and LLM_NAME, LLM_API_KEY) for a live Apertus demo.
run:
	docker compose run --rm --build lightpath

# Development: unit tests in the local uv environment (WSL2/Linux).
test:
	uv run pytest -q
