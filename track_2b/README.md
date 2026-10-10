# Intent-conditioned lightpath provisioning with Apertus 8B

Hack Apertus Track 2B. A fine-tuned Apertus v1.5 8B model chooses the path and start slot for
each lightpath request in an elastic optical network, in one shot, while following an operator
intent written in plain language ("avoid the Berlin–Prague link", "fewest hops"). Labels come
from heuristic teachers inside the [Optical Networking Gym](https://github.com/carlosnatalino/optical-networking-gym)
(ONG) simulator. We report closed-loop blocking, intent-violation rate, invalid-output rate and
latency against the heuristics and a small MLP trained on the same data.

The plan is in [`../SPEC.md`](../SPEC.md). Every deviation from it, with the measurement behind
it, is in [`docs/decisions.md`](docs/decisions.md), which also lists the open questions for the
owner. The challenge text from the template is in [`docs/challenge.md`](docs/challenge.md).

## Status

| Workstream | State |
| --- | --- |
| Simulator: ONG from source, compiled kernels, memory fix | done |
| Load calibration; evaluation loads 240 and 390 E | done, loads fixed |
| Intents, prompt format, intent-aware teacher | done; wording and three definitions await the owner's review |
| Dataset: 12,000 train + 2,200 held-out records, sanity checks | done |
| MLP control: training, offline agreement | done |
| Closed-loop evaluator; runs for first fit, teacher, oracle, MLP | done (4 policies × 7 conditions × 2 loads × 3 seeds) |
| Tables and figure from results files | done |
| `make run` (Docker) | done: the image builds from the working tree, prints the tables and replays the fine-tuned model's recorded answers in the 50-request demo (checked on 2026-10-10 with `docker compose run --rm --build lightpath`; `make` itself is not installed on the dev machine, and a fresh clone is untested until the repository is public) |
| Fine-tuning script, in-process and endpoint backends, job pipeline | done: training, constrained decoding and the job stages tested on a tiny open model (CPU `check` job, including a kill-and-resume) and smoke-tested on Apertus; endpoint client tested against a mock only |
| Fine-tuning of Apertus | done in two passes. First pass: 1 epoch, every intent pair an intersection (held-out admissible agreement 95.9 / 95.7 / 77.5 %). Second pass: avoid-link pairs are filter-then-rank, 2 epochs: **99.0 % new traffic, 98.5 % unseen wording, 85.7 % unseen pairs**, no invalid answers. Adapters in private Hub repos |
| Apertus closed-loop results, fine-tuned and zero-shot | done for both passes: fine-tuned model on the full grid (42 episodes); zero-shot model at 390 E on seed 1 (its answers are invalid 88–98 % of the time, so the first-fit fallback decides). 7.4 GPU-hours, USD 18.61 in total |
| Report | draft with all results in `technical_report.md`; awaits the owner's review (team, video, public links and the laptop measurement are marked TODO) |
| Video, dataset and model cards on the Hub | not started (`data/README.md` is a draft card) |

Results are in [`results/tables/results.md`](results/tables/results.md) and
[`docs/figures/blocking.png`](docs/figures/blocking.png). In short, at 390 Erlang: with no intent
the fine-tuned model blocks about like its teacher (6.4 against 6.0 %); it follows the four single
intents with 0.1–3.3 % violations (the MLP control: up to 11 %); unseen wordings cost 1.0 %; an
unseen pair of a prohibition and a preference is followed with 3.7 % violations (MLP 6.5 %); an
unseen pair of two preferences is not (22 %, MLP 43 %).

There were two passes. The first trained one epoch with every intent pair defined as an
intersection and failed on "avoid link" by rejecting about 14 % of requests it could have served.
That was traced to the pair rule leaking into the single intent
(`results/design/pair_rule_leak_apertus_ft.json`); the second pass changed the rule for avoid-link
pairs, relabelled the same records and trained two epochs. The first pass is kept under
[`results/pass1/`](results/pass1/) with its own tables; `LIGHTPATH_PAIR_RULE=intersection`
reproduces its rule.

## Run it

```bash
make run
```

Builds the image (ONG compiled from source), prints the results tables rebuilt from the JSON
files in `results/`, then runs a 50-request closed-loop demo. No GPU is needed. With
`LLM_BASE_URL` set (see below) the demo queries that endpoint live; without it, it replays the
fine-tuned model's recorded answers if they are in `results/cache/`, else it uses the MLP
control.

## Pipeline

All commands run from `track_2b/` in the uv environment (see Development setup).

| Step | Command | Output |
| --- | --- | --- |
| Calibrate loads | `uv run python src/calibrate.py` | `results/calibration/` |
| Generate the dataset | `uv run python src/generate.py` | `data/full/`, `data/sample/`, `data/stats.json` |
| Train the MLP control | `uv run python src/mlp.py` | `results/mlp/` |
| Offline agreement | `uv run python src/evaluate.py offline --policy mlp` | `results/offline/mlp.json` |
| Closed loop, CPU policies | `uv run python src/evaluate.py closed --policy oracle` (also `mlp`, `teacher`, `first_fit`) | `results/eval/<policy>.json` |
| Fine-tune Apertus (GPU job) | `bash jobs/launch.sh train a100-large <timeout>` | adapter and held-out predictions on the Hub |
| Closed loop, Apertus (GPU job) | `bash jobs/launch.sh eval a100-large <timeout>` | `results/eval/apertus_*.json`, `results/cache/` |
| Tables and figure | `uv run python src/report_tables.py` | `results/tables/`, `docs/figures/` |

The GPU steps, with the checks between them, are in [`docs/gpu_runbook.md`](docs/gpu_runbook.md).
Long runs checkpoint every finished episode and resume when the same command is run again.

Every number quoted anywhere comes from a JSON file under `results/` or `data/stats.json`; the
markdown tables are rendered from those files and are not edited by hand.

### The evaluation protocol

For each condition (no intent, each of four intents, unseen wording, unseen intent pairs), load
(240 and 390 E) and seed (1–3): the no-intent teacher decides a 1,000-request warm-up, the
counters are reset, and the policy under test decides the next 2,000 requests, each carrying an
intent. An answer that is not a valid action counts as invalid and is replaced by first fit. A
violation is an executed decision outside the intent's admissible set. The intent of a given
request is identical for every policy.

### What the model sees

```
Request: Bordeaux -> Munich, 10 Gb/s.
Intent: The Brussels-Paris link is out of bounds for now; stay clear of it.
Network: 320 slots per link, free ratio 0.76.
Candidates (path: hops, km, best modulation, slots needed, free slots on path, free blocks [start-length]):
0: 4 hops, 1359 km, 64QAM, 1 slot, 150 free, blocks [63-1] [94-1] [122-4]
1: 4 hops, 1386 km, 64QAM, 1 slot, 147 free, blocks [122-4] [133-1] [158-13]
...
Route per path: 0: Bordeaux-Paris-Brussels-Frankfurt-Munich ; 1: Bordeaux-Paris-Strasbourg-Frankfurt-Munich ; ...
Answer format: path=<0-4> slot=<n>  or  reject
```

and answers `path=1 slot=122`. Intent definitions and wording are in `src/intents.py`.

## Layout

```
track_2b/
  README.md  Makefile  Dockerfile  compose.yaml  run.sh     `make run`
  pyproject.toml  uv.lock  .python-version                  uv project; ONG pinned to a commit
  .env.example                                              LLM_* variables (copy to .env)
  src/
    sim.py             ONG adapter: the jocn_benchmark env (with a memory fix), request view, actions
    view.py            what a policy sees for one request (plain data)
    intents.py         intent wording, admissible sets, intent-aware teacher
    prompt.py          view -> prompt text; answer text -> choice
    calibrate.py       load calibration of first fit vs BM-LS-KSP
    generate.py        dataset generation, splits, sanity checks
    mlp.py             MLP control: features, training, inference (numpy)
    policies.py        heuristics, oracle, MLP, and Apertus (in-process or behind an endpoint) with an answer cache
    decoding.py        the answer regex as a token-level constraint for in-process decoding
    evaluate.py        closed-loop protocol (optionally with parallel simulator workers), offline agreement, demo
    train.py           QLoRA fine-tuning (self-contained script)
    report_tables.py   results JSON -> markdown/LaTeX tables and the figure
  jobs/                run.sh (stages run inside a Hugging Face Job), push_bundle.sh, launch.sh
  tests/               pytest (`make test`)
  data/                sample/ and stats.json are committed; full/ is git-ignored (goes to the Hub)
  results/
    calibration/  eval/  offline/  mlp/  tables/  cache/    one JSON per run, rendered tables
    train/             training logs and held-out answers of the fine-tuning runs
    pass1/             everything of the first pass (intersection rule, one epoch), frozen
    design/            one-off measurements behind the design decisions
  docs/
    decisions.md       deviations from SPEC.md, their evidence, open questions
    gpu_runbook.md     fine-tuning and evaluation as Hugging Face Jobs, step by step
    challenge.md       Track 2B challenge text and submission requirements
  technical_report.md  report (exported to TeamName_Report.pdf, at most 6 pages)
```

## Development setup

ONG compiles Cython kernels and is supported on Linux, so everything Python runs in WSL2. The
repository can stay on the Windows drive; commands below run from `track_2b/` inside WSL.

Requirements: WSL2 with Ubuntu 24.04 (gcc, make and the Python 3.12 headers are present in the
stock image), [uv](https://docs.astral.sh/uv/) ≥ 0.12, git.

```bash
# once: install uv for the current user (no sudo needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# from track_2b/ (e.g. /mnt/c/Users/<you>/PycharmProjects/ApertusNetworkGym/track_2b)
UV_LINK_MODE=copy uv sync      # creates .venv, builds ONG and its Cython kernels from source
uv run pytest -q               # 28 tests, about 15 s
```

`UV_LINK_MODE=copy` only silences uv's hardlink warning when the cache (WSL disk) and the project
(Windows disk) are on different filesystems.

Check that the compiled kernels, not the pure-Python fallbacks, are loaded:

```bash
uv run python -c "import optical_networking_gym.optical.kernels.qot_kernel as k; print(k.__file__)"
# ... qot_kernel.cpython-312-x86_64-linux-gnu.so
```

Two things to know on a small machine:

- Build environments with `src/sim.py:build_env`, not ONG's `make_env`. ONG at the pinned commit
  keeps every request's analysis until reset (about 0.9 GB per 3,000-request episode);
  `ProvisioningEnv` clears that cache after each step without changing any decision. With the fix
  a worker needs about 150 MB.
- If WSL commands start failing with `Wsl/Service/E_UNEXPECTED` during long runs, the Windows
  host is short of memory: close memory-heavy apps, run `wsl --shutdown` from Windows (this also
  stops Docker Desktop's engine), and rerun the same command.

## Environment variables

Copy `.env.example` to `.env`.

| Variable | Meaning |
| --- | --- |
| `LLM_NAME` | Model name the endpoint serves (`andreasmartin/apertus-v1.5-8b-text` is the text-only Apertus v1.5 8B) |
| `LLM_BASE_URL` | OpenAI-compatible endpoint (vLLM), e.g. `http://host.docker.internal:8000/v1` from inside the container. Empty: `make run` uses only files in the image |
| `LLM_API_KEY` | Key for that endpoint |
| `HF_TOKEN` | Hugging Face token: gated model download, HF Jobs, dataset and adapter uploads |

## Hardware used

| Purpose | Machine |
| --- | --- |
| Simulation, data generation, MLP, CPU evaluation | Windows 11 laptop, WSL2 Ubuntu 24.04, 16 logical CPUs, 7.6 GB RAM visible to WSL |
| Fine-tuning and evaluation | One rented NVIDIA A100 80 GB as Hugging Face Jobs, 7.4 GPU-hours over both passes (peak memory 17.8 GB training, 23.6 GB answering) |
| Demo video (llama.cpp Q4_K_M) | RTX 4060 laptop GPU (planned) |

## AI assistance

Code and documentation in this repository were written with the help of Claude Code (Anthropic),
under the owner's direction and review. This is disclosed again in the technical report.

## License

Code: Apache-2.0. Documentation: CC-BY-4.0. ONG (a dependency, not vendored) is GPL-3.0.
