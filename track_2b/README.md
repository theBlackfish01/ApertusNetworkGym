# Operator instructions for lightpath provisioning with Apertus 8B

Hack Apertus Track 2B. An operator of an optical transport network types an instruction in plain
language ("the Zurich–Milan span is under maintenance", "at most four hops, then the shortest in
km"), in English, German, French or Italian. Apertus v1.5 8B translates it once into one line of
a small policy language, and a rule engine enforces that line for every lightpath request. A
second reader translates it again, and the operator is asked when the two readings differ. An
instruction outside the language goes to a fine-tuned Apertus that decides the request itself,
with its choice checked against the part of the instruction the language carries. Everything runs
on a laptop GPU. Requests, network and blocking come from the
[Optical Networking Gym](https://github.com/carlosnatalino/optical-networking-gym) (ONG) simulator.

```
operator instruction ──> reader 1 ─┐                        ┌─ in the language ───────> rule engine ─┐
       (any language) ──> reader 2 ─┴─ same reading? ─ yes ─┤                                        ├─> allocation
                                          │ no              └─ outside it, or only in part ─> decider ┘
                                    ask the operator             (choice checked against the part carried)
```

What the numbers say, in short (`technical_report.md`, `results/tables/phase3.md`): the reader
gets 94.8 % of 2,078 independently written instructions right, and combinations of clauses it
never saw together as well as trained ones; its decisions comply in 99.6 %, those of the model
that decides alone in 91.1 %. On a mixed stream in closed loop the hybrid that asks breaks 8.5 %
of requests, the translator alone 10.6 %, the decider alone 16.8 %, first fit 28.6 %. Instruction
types that no component was ever shown remain the weak point.

The project was built in three rounds, and the first two are kept: a model that decides every
request (`results/tables/results.md`), the same model as a translator (`phase1.md`, `phase2.md`),
and the policy language with two readers and a guarded fallback (`phase3.md`). The original plan
is in [`../SPEC.md`](../SPEC.md); every deviation from it, every mistake and its cost is in
[`docs/decisions.md`](docs/decisions.md). The challenge text from the template is in
[`docs/challenge.md`](docs/challenge.md).

## Status

| Workstream | State |
| --- | --- |
| Simulator: ONG from source, compiled kernels, memory fix | done |
| Load calibration; evaluation loads 240 and 390 E | done, loads fixed |
| Intents, prompt format, intent-aware teacher | done |
| Dataset: 12,000 train + 2,200 held-out records, sanity checks | done |
| MLP control: training, offline agreement | done |
| Closed-loop evaluator; runs for first fit, teacher, oracle, MLP | done (4 policies × 7 conditions × 2 loads × 3 seeds) |
| Tables and figure from results files | done |
| `make run` (Docker) | done: the image builds, prints the tables and replays a 50-request episode of the hybrid as recorded on a laptop, then a few decisions of the decider alone (checked from a fresh clone on 2026-10-12 with `docker compose run --rm --build lightpath`; `make` itself is not installed on the dev machine) |
| Fine-tuning script, in-process and endpoint backends, job pipeline | done: training, constrained decoding and the job stages tested on a tiny open model (CPU `check` job, including a kill-and-resume) and smoke-tested on Apertus; endpoint client tested against a mock only |
| Fine-tuning of Apertus | done in two passes. First pass: 1 epoch, every intent pair an intersection (held-out admissible agreement 95.9 / 95.7 / 77.5 %). Second pass: avoid-link pairs are filter-then-rank, 2 epochs: **99.0 % new traffic, 98.5 % unseen wording, 85.7 % unseen pairs**, no invalid answers. Adapters in private Hub repos |
| Apertus closed-loop results, fine-tuned and zero-shot | done for both passes: fine-tuned model on the full grid (42 episodes); zero-shot model at 390 E on seed 1 (its answers are invalid 88–98 % of the time, so the first-fit fallback decides). USD 18.61 of GPU time |
| Phase 1: translate versus decide | done. The same model as a *translator* (instruction -> one line of constraints and preferences, executed by a rule engine) against the fine-tuned *decider*, on harder test sets: independent wording, German, French, Italian, Swiss German, misspelt cities, instructions that must not be applied, and a topology no model saw. Closed loop at 390 E: fine-tuned translator 0 % violations on single intents and unseen wording, 2.8 % on unseen pairs (decider 0.1–3.3 %, 1.0 %, 12.9 %); with 7 examples and no training the translator misreads one wording family (10.6 % on least loaded). Tables in [`results/tables/phase1.md`](results/tables/phase1.md); USD 4.88 of GPU time |
| Second round: stronger translator and hybrid | done. A second translator (taught two preferences, German, French, Italian, and to tell an unsupported routing instruction from text that is no instruction) translates 95 % of independently worded and 94–98 % of natively written German, French and Italian instructions; closed loop 0.0–0.2 % violations. The fine-tuned decider follows three instruction types it never saw (pass through a node, avoid a node, a given candidate) on 87 % of 600 requests, where a choice that ignores the instruction complies on 20 %; on three further types it is no better than the shortest candidate. A hybrid (translator first, decider for what the translator calls unsupported) has 4.0 % violations on a mixed stream at 390 E, the decider alone 6.3 %, the translator alone 9.3 %, first fit 19.4 %. Tables in [`results/tables/phase2.md`](results/tables/phase2.md); analysis behind the plan in [`docs/analysis/next_steps.html`](docs/analysis/next_steps.html); USD 4.85 of GPU time |
| Third round: policy language, two readers, guarded fallback, laptop | done. A third answer format in slots (links and nodes to avoid, a node to pass through, limits on hops and length, a candidate by number, ordered preferences, a marker for a part that does not fit). Two readers fine-tuned in 34 min each: 94.8 % of 2,078 independently written instructions in four languages right; pairs of clauses never seen together 96.5 %, triples 91.2 %; decisions comply in 99.6 % (decider alone 91.1 %). Of four instruction types shown to no component the reader silently applies 46.6 % as something else; asking the operator when two readers differ leaves 16.2 %. Mixed stream at 390 E: hybrid that asks 8.5 % violations, hybrid 9.5 %, translator alone 10.6 %, decider alone 16.8 %, first fit 28.6 %. On an RTX 4060 laptop under llama.cpp: 0.89 s per instruction, 93.1 % right. Of 22 instructions typed by the owner (17 English, 5 Urdu in Latin script, a language in no training data) reader 1 on the laptop is right on 18: 16 of 17 and 2 of 5. Apertus 70B with examples and no training: 71.9 % (first generation). Tables in [`results/tables/phase3.md`](results/tables/phase3.md); USD 10.02 of GPU time |
| Report | draft of six pages in `technical_report.md`; awaits the owner's review (team, video and public links are marked TODO). The long account of the first two rounds is `docs/report_rounds_1_2.md` |
| Video, dataset and model cards on the Hub | not started (`data/README.md` is a draft card) |

The decider of the first round is in [`results/tables/results.md`](results/tables/results.md) and
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
files in `results/`, then shows 50 requests flowing through the hybrid: the instruction, the line
each reader understood, whether the operator was asked, who decided, and whether the decision
respects the instruction. No GPU is needed: the episode is replayed from the answers recorded on
a laptop (`results/cache/*_laptop.jsonl`). With `LLM_BASE_URL` pointing at a llama.cpp server
(next section) the same episode runs live. A few decisions of the decider alone follow.

## On a laptop

One base model and three adapters behind one [llama.cpp](https://github.com/ggml-org/llama.cpp)
server (build 11558 or later; Apertus needs b6686 or later). Measured on an RTX 4060 with 8 GB:
0.89 s per instruction, 0.97 s per decision.

```bash
# the files (private until submission): the 4-bit base and the adapters as GGUF
hf download blackfish021/apertus-lightpath-translator-v3-gguf --local-dir models

llama-server -m models/apertus-v1.5-8b-text-Q4_K_M.gguf \
    --lora models/lightpath-translator-v3-reader1-lora-f16.gguf \
    --lora models/lightpath-translator-v3-reader2-lora-f16.gguf \
    --lora models/lightpath-decider-v2-lora-f16.gguf \
    --lora-init-without-apply -ngl 999 -c 4096 -np 1 --port 8089 --jinja

# the hybrid, live: two readers, rule engine, decider with guard (in the uv environment)
export LLM_LORA_IDS='{"translate3_ft_live": 0, "translate3_ft2_live": 1, "apertus_ft_live": 2}'
uv run python src/evaluate.py demo --policy hybrid3_ft_live_ask-ft2_live --decider apertus_ft_live \
    --base-url http://127.0.0.1:8089/v1 --concurrency 1 \
    --conditions operations_mix3 --loads 390 --seeds 11 --warmup 300 --window 50 --show 50

# one reader on a file of instructions (JSON lines with "text" and "expect")
uv run python src/translate.py batch --base-url http://127.0.0.1:8089/v1 --concurrency 1 \
    --jobs "translate3_ft_live:nobel-eu:regex:data/instructions/v3_en.jsonl"
```

The server constrains every answer with the grammar the client sends (GBNF, exported from
`src/spec.py` by `grammar.gbnf`), and `LLM_LORA_IDS` tells the client which adapter belongs to
which policy name. The GGUF files were built by the `gguf` and `gguf-lora` job stages from the
published base weights and our adapters. On Windows the simulator runs in WSL, so the server
must run there too (the Linux build of llama.cpp); the readers alone also work from Windows.

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
| Phase 1: test sets and translator data | `uv run python src/corpora.py`; `uv run python src/transfer.py --loads 300 600 900 1200`; `uv run python src/translate.py texts` | `data/probes/`, `data/instructions/`, `data/translate/`, `data/fewshot/`, `data/topologies/` |
| Phase 1: Apertus as translator, decider on the probes (GPU jobs) | `bash jobs/launch.sh phase1 a100-large <timeout>`, then `phase1-ft` | answer caches in `results/cache/`, `results/translate/`, `results/offline/*_probes.json` |
| Second round: test sets, GPU jobs, laptop replay | `uv run python src/corpora2.py`; `uv run python src/translate.py texts --conditions operations_mix --out data/instructions/mix.jsonl`; `bash jobs/launch.sh phase2 ...`, `phase2-ft`, `phase3`; `bash jobs/phase2_local.sh`; `uv run python src/report_phase2.py` | `results/tables/phase2.md` |
| Third round: training data, test sets, GPU jobs, analysis | `uv run python src/corpora3.py` (training data of two readers, then the test sets from `data/instructions/v3_source_*.json`); `uv run python src/translate.py texts --conditions operations_mix3 --out data/instructions/mix3.jsonl`; `READER=1 bash jobs/launch.sh train3 ...` and `READER=2`; `bash jobs/launch.sh phase4 ...`; `gguf`, `gguf-lora`, `big` (Apertus 70B; `JOB_IMAGE=ghcr.io/astral-sh/uv:python3.12-trixie`); then on the laptop `uv run python src/readers3.py` and `uv run python src/report_phase3.py`. The owner's own lines (`data/instructions/owner_source.txt`): `uv run python src/corpora3_owner.py`, the readers on the laptop's server with `translate.py parse --sets data/instructions/owner.jsonl`, then `uv run python src/corpora3_owner.py --score` | `results/design/readers3.json`, `results/design/owner.json`, `results/tables/phase3.md` |
| Phase 1: translators on the laptop (keyword parser, or Apertus from its answer cache) | `bash jobs/phase1_local.sh translate_keyword translate_few ...` | `results/translate/`, `results/offline/`, `results/eval/translate_*.json`, `results/tables/phase1.md` |

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
    spec.py            phase 1: an instruction as constraints plus ordered preferences; the rule engine
    grammar.py         phase 1: regular grammars as token-level constraints (the translator's answer line)
    translate.py       phase 1: the translator arm (keyword parser, Apertus), its policy, scoring
    corpora.py         phase 1: re-worded, multilingual and inapplicable instructions; translator training data
    transfer.py        phase 1: held-out-style records on a topology no model has seen
    report_phase1.py   phase 1: results JSON -> results/tables/phase1.md
    corpora2.py        second round: training data of the second translator; tests for types without a rule
    mixed.py           second round: a closed-loop condition that mixes kinds of instructions
    report_phase2.py   second round: results JSON -> results/tables/phase2.md
    corpora3.py        third round: training data of two readers; trained and held-out clause combinations
    corpora3_tests.py  third round: test sets from the independently written sources
    mixed3.py          third round: instructions tied to a request, rules of the new types, the mixed stream
    corpora3_owner.py  third round: the owner's own instructions as a test set, and what the readers made of them
    readers3.py        third round: what each reader does with every test instruction; two readers
    report_phase3.py   third round: results JSON -> results/tables/phase3.md
  jobs/                run.sh (stages run inside a Hugging Face Job), push_bundle.sh, launch.sh,
                       phase1_local.sh (translators on the laptop, from the answer caches)
  tests/               pytest (`make test`)
  data/                sample/ and stats.json are committed; full/ is git-ignored (goes to the Hub)
                       instructions/ fewshot/ topologies/: phase 1 test instructions (committed);
                       probes/ translate/: rebuilt by corpora.py and transfer.py (git-ignored)
  results/
    calibration/  eval/  offline/  mlp/  tables/  cache/    one JSON per run, rendered tables
    translate/         phase 1: translation accuracy per translator and instruction set
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
| `LLM_BASE_URL` | A llama.cpp server with the base model and the three adapters (section "On a laptop"), e.g. `http://host.docker.internal:8089/v1` from inside the container. Empty: `make run` uses only files in the image |
| `LLM_LORA_IDS` | JSON that maps a policy name to the number of its adapter on that server; `run.sh` sets a default |
| `LLM_API_KEY` | Key for that endpoint |
| `HF_TOKEN` | Hugging Face token: gated model download, HF Jobs, dataset and adapter uploads |

## Hardware used

| Purpose | Machine |
| --- | --- |
| Simulation, data generation, MLP, CPU evaluation | Windows 11 laptop, WSL2 Ubuntu 24.04, 16 logical CPUs, 7.6 GB RAM visible to WSL |
| Fine-tuning and evaluation | One rented NVIDIA A100 80 GB as Hugging Face Jobs, 15.3 GPU-hours and about USD 38.36 over all three rounds (peak memory 18.8 GB training a reader, 23.6 GB answering) |
| The hybrid on a laptop (llama.cpp, 4-bit GGUF, three adapters) | RTX 4060 laptop GPU, 8 GB: 0.89 s per instruction, 0.97 s per decision |

## AI assistance

Code and documentation in this repository were written with the help of Claude Code (Anthropic),
under the owner's direction and review. The sentence templates of the readers' training data were
written the same way. The test instructions were written by separate instances of the same
assistant that never saw the repository (`data/instructions/*_source.json`), and two more such
instances reviewed the project before the third round (`docs/decisions.md`). No model other than
Apertus is part of the system or produced a result. This is disclosed again in the technical
report.

## License

Code: Apache-2.0. Documentation: CC-BY-4.0. ONG (a dependency, not vendored) is GPL-3.0.
