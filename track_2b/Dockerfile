# Image for `make run`: rebuilds the results tables and runs the closed-loop demo. CPU only.
FROM python:3.12-slim-bookworm

# build-essential: Optical Networking Gym compiles its Cython kernels when it is installed.
# git: ONG is a git dependency pinned to a commit in pyproject.toml / uv.lock.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

# Dependencies first, so editing the code does not rebuild ONG.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev

COPY src ./src
# The topology and the independently written sentences of the third round's instruction stream
# (.dockerignore keeps the rest of data/ out).
COPY data ./data
COPY results ./results
COPY run.sh ./
RUN mkdir -p docs/figures

CMD ["sh", "run.sh"]
