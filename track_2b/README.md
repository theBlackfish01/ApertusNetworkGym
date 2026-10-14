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
gets 94.8 % of 2,078 independently written instructions right, and pairs of clauses it never saw
together as well as trained pairs (triples three points lower); its decisions comply in 99.6 %, those of the model
that decides alone in 91.1 %, and in 96.4 % when that model learns from the reader's own sentences (in closed loop it still
breaks 14.1 % of in-language requests, the reader 0.9 %). On a mixed stream in closed loop the hybrid that asks breaks 8.5 %
of requests, the translator alone 10.6 %, the decider alone 16.8 %, first fit 28.6 %. Instruction
types that no component was ever shown remain the weak point. In 4 bits on a laptop GPU, the build a
judge can run, the reader reads 93.1 % of the same sentences and the hybrid breaks 9.2 %; the reader of
standing policies reads 90.6 % of its blind sentences against 93.5 % in the job. Both builds are
reported wherever both were measured.

The project was built in four rounds, and the earlier ones are kept: a model that decides every
request (`results/tables/results.md`), the same model as a translator (`phase1.md`, `phase2.md`),
the policy language with two readers and a guarded fallback (`phase3.md`), and standing policies
with scope and lifetime, the console, the Swiss network and the benchmark (sections below). Every
result with its source file, what it shows and what it does not, is in
[`docs/results_overview.md`](docs/results_overview.md); the original plan is in
[`../SPEC.md`](../SPEC.md); every deviation from it, every mistake and its cost is in
[`docs/decisions.md`](docs/decisions.md); the challenge text from the template is in
[`docs/challenge.md`](docs/challenge.md); the submission checklist is
[`docs/submission.md`](docs/submission.md).

## Terms used below

- **Lightpath request:** a connection to set up between two nodes at a bit rate; the controller
  picks one of five candidate paths and a block of spectrum slots on it, or rejects it.
- **Erlang (E):** the offered load; 240 E is a quiet network, 390 E a busy one. **Blocking:** the
  share of requests rejected for lack of spectrum.
- **Instruction / policy:** what the operator says about routing; an instruction comes with one
  request, a standing policy covers the requests its scope names for as long as it holds.
- **Reader:** Apertus 8B fine-tuned to translate the instruction into one line of the policy
  language. **Decider:** Apertus 8B fine-tuned to pick the route itself. **Rule engine:** applies
  a line exactly. **Hybrid:** reader first, decider for what the language cannot carry, with a
  **guard** that replaces the decider's route if it breaks the part the line does carry.
- **Gate:** whatever makes the system not apply a reading silently: the reader's own refusals, a
  second reader that disagrees, or a question to the operator. **Carried in part:** an instruction
  the language can express only partly (`rest=more`).
- **Asking by consequence:** when two readers differ, apply the first reading and ask the operator
  on the first request that the two readings would route differently.
- **Formats:** the answer line changed four times; the third format is the slots above, the fourth
  adds `scope` and `until` for standing policies. Policy names in results files carry the format
  (`translate3_ft`, `hybrid3_ft_askif-ft2`: reader 1 of format 3, asking by consequence with reader 2).
- **Violation:** a decision that breaks what was meant; **complies:** the chosen path is one the
  instruction allows, or a reject when none is. **Oracle / true table:** the decision with the
  meaning known exactly. **First fit:** the instruction-blind baseline. **I1–I4:** the first round's
  four intents (avoid a link, fewest hops, least loaded, fewest slots). **nobel-eu:** the 28-node
  European network of the simulator's benchmark preset.

## Status

| Round | What it built | Where measured |
| --- | --- | --- |
| 1 (9–11 Oct) | Simulator, load calibration, dataset, an MLP control, the closed-loop evaluator; Apertus 8B fine-tuned as a decider, two passes; `make run` | `results/tables/results.md`, `docs/report_rounds_1_2.md` |
| 2 (11–12 Oct) | The same model as a translator into a line of constraints and preferences, measured against the decider; a stronger translator; the first hybrid | `results/tables/phase1.md`, `phase2.md` |
| 3 (12 Oct) | The policy language in slots, two readers, the guarded fallback, blind test sets in four languages, the mixed closed-loop stream, the 4-bit laptop build, Apertus 70B as a reference | `results/tables/phase3.md`, `docs/decisions.md` |
| 4 (13 Oct) | The console, the line as a TAPI constraint, asking by consequence, the Swiss network, standing policies with scope and lifetime, self-consistency, the benchmark dataset | `results/tables/phase3.md`, `results/design/`, `data/benchmark/` |
| 4b (14 Oct) | A decider trained on the reader's own sentences (the matched comparison); the full-format reader and its hybrids on the mixed stream | `docs/results_overview.md` section 4b, `results/design/matched3.json` |
| Deliverables | Report rendered to PDF by `src/report_pdf.py` (five pages); model cards (`docs/cards/`) and the benchmark on the Hub, private until submission; video script (`docs/video_script.md`); checklist (`docs/submission.md`) | |

The full table, one row per piece of work, is in [`docs/status_history.md`](docs/status_history.md).

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
(next section) the same episode runs live. A few decisions of the decider alone follow. Needs
Docker with Compose v2 (`docker compose`) and GNU make; the first build fetches the base image, uv
and the simulator's source from the internet and compiles the simulator, three to five minutes;
later runs take seconds. The root `Makefile` forwards to this one, so `make run` works from either
directory.

## The operator console

```bash
make console                      # http://localhost:8090, from recorded answers (no GPU, no server)
make ui                           # the browser frontend, for running the console outside Docker (Node 22)
uv run python src/console.py --base-url http://127.0.0.1:8089/v1    # live, in the uv environment
```

The console is a Python server (`src/console.py`, standard library only) and a browser frontend in
Svelte and TypeScript (`src/console_ui`, built by Vite into `src/console_ui/dist`, which the server
serves). `make console` builds the frontend inside the image; outside Docker, `make ui` builds it
(and type-checks it and runs its unit tests), and without a build the server falls back to the
earlier single-file page, which also stays at `/legacy`. The frontend asks the server for every
step, so the simulator runs only when someone presses Play or Step.

Two views. **Operate** is the operator's view of one stream, built for a dark room. The header says
what runs (network, load, seed; live models or recorded answers, with the model names on hover;
the simulator's hour), switches the view, holds the transport (play at a chosen pace, step, ten
steps) and a Stream menu with the switches. The network is the stage: a map with link brightness
for occupation, red for what the policies in force avoid, green for what they require, the route
of the last decision drawn as it is set up and the next request's end points marked; it zooms on
the wheel and pans on a drag. Above it a row of counters (served, rejected, violations, policy
breaches, questions, decisions by the decider, guard, not applied); below it a timeline of every
decided request (violations red, questions amber, the guard violet, rejections grey, triangles
where a policy came into force, and the share of violations over the last 50); clicking a mark, or
pressing the arrow keys on it, shows the network as it was for that request. The feed on the left
narrates what the AI does, newest first, as one card per request (the instruction and its
language, the two readers agreeing or differing, a question, the decider or the guard, the route,
and a verdict badge: respects or breaks what was meant) and one card per policy (it arrives, the
reader reads it back, against the recorded meaning when there is one, a conflict is named, it is
in force); filters show all, requests, policies, or problems. The rail on the right shows the open
question (both readings, read back, with what each would do to the request), the next request,
the last decision, and the policies in force with their scope and remaining hours; hovering a
policy lights up on the map exactly what it avoids and requires. One command line takes a standing
policy or an instruction for the next request, in any language; what was read opens in a panel
above it. Four tabs at the bottom: the audit trail, the policy report, the policies over time (one
bar per policy from the hour it came into force to its expiry or withdrawal, coloured by scope),
and the metrics (violations, rejections, questions and decisions by the decider as shares of the
last 50 requests, along the stream).

**The inspector** opens any request, decided or next: the five candidate paths with their hops,
length, free slots and modulation, the constraint of the applied line that dropped each one (an
avoided link or node, a missing via, too many hops, too long, no free block), how the preferences
ranked the rest, the tie-break, which candidate the rule engine would take and which the decision
took (they differ when the decider or the guard decided), where the recorded meaning differs from
the line applied, field by field, and the spectrum of every link of the chosen route at the moment
of the decision: 320 slots, those in use, and the block this lightpath took.

**Race** decides the evaluation's own stream (the mixed condition of the third round, load 240 or
390 Erlang, seed 1, 2 or 3; warm-up of 1,000 requests, window of 2,000) four times side by side:
by first fit, which ignores the instruction; by the decider alone (the first decider, instruction
in the prompt); by the reader with the rule engine; and by the hybrid. Each lane has its own
network and replays the answers stored when the closed loop was run, so no model is needed. Every
lane shows its route for the request just decided and its verdict, its violations and rejections,
and its violations on instructions inside the language and on types never shown; below them, the
violations so far along the stream and a table by class of instruction. At the end each lane is
checked against its stored run (`results/eval/<method>_mix3.json`, answers from `results/cache`): at 390 Erlang, seed 1, the four
replay 560, 329, 199 and 170 violations, exactly the stored counts.

Ctrl+K (⌘K on a Mac) opens a palette with every command by name ("inspect 37" opens request 37);
Tour walks through the system in nine steps, driving the stream to the moments worth seeing (a
policy arriving, a question, the decider, an inspection, the race). Keys: space plays or pauses
(in both views), s steps, Esc closes the inspector or returns the map to the live route.

One stream carries both kinds of operator text. Standing policies (the fourth format: scope and
lifetime) are typed, or arrive on the schedule of the closed-loop policy stream when "policies
arrive" is on; the reader of the fourth format translates each, the page reads it back, names
the conflicts with the policies in force, previews it on a copy of the network (the next 100
requests under the table with and without it) and adds it to the table, where it covers the
requests its scope names until it expires or is withdrawn. Per-request instructions (the third
format) are drawn with each request from the mixed stream of the third round when "instructions
with requests" is on, or typed for the next request; the two readers of the third format
translate each one, and where they differ the operator is asked by consequence: the first
reading stands until a request would be decided differently under the two, when the stream
pauses and the page shows both readings with the route each would take (a reading outside the
language or carried in part is asked about at once). "Simulated operator" answers every question
with the recorded meaning, as the evaluation does, so the stream can play unattended. Every
request is decided by the rule engine under the one line the covering policies and the
instruction combine to; an instruction outside the language or carried in part goes to the
decider with the guard, live only: without a model server the rule engine stands in and the
feed says so.

Every decision is judged against what was meant: the instruction's recorded meaning (or the
line the operator confirmed) and the true policies together, combined by the table's own rule;
an instruction of a type the language cannot express is judged by its own rule, policies aside.
A policy's own "violations" count the routes that broke a constraint it truly states. The audit
trail keeps one row per lightpath: request, instruction, the line applied, the policies that
covered it, who decided, the decision, and both verdicts. "Show the model's lines" (in the Stream
menu) adds to the feed and the rail what an operator does not need: the lines of the policy
language, the recorded meaning, the TAPI constraint and the internal steps. Without a model server only texts the readers
answered before can be typed (the command line offers them); with `LLM_BASE_URL` pointing at the
llama.cpp server of the next section, anything can, and the decider runs. The defaults (load
390, seed 1, the evaluation's warm-up of 1,000 requests) make every drawn instruction and every
arriving policy a recorded one; seeds 2 and 3 at that load are recorded too.

## Asking only when it matters

Two readers translate every instruction; where their readings differ the operator is asked.
Policy names with `_ask-<reader>` ask at once (`hybrid3_ft_ask-ft2`). Names with `_askif-<reader>`
apply the first reading for the time being and ask on the first request on which the two
readings would decide differently; a reading outside the language or carried in part is asked
about at once, because what the decider would do with it cannot be foreseen. The console does
the same for a person: the stream pauses on the first request that tells the readings apart and
shows both routes.
Measured in `results/tables/phase3.md` (closed loop, `*_askif-*` rows). The simulated operator of
those runs answers with the true meaning, an upper bound; names with `_askfair-<reader>` use a fair
operator who picks the right reading only when one of the two is right and otherwise leaves the
first, which for the translator alone gives back most of the gain (`results/eval/translate3_ft_askfair-ft2_mix3.json`).

## Standing policies

An operator does not type an instruction per request. The fourth format of the policy language
adds a scope and a lifetime to the third: `scope=<any | rate:400 | from:Zurich | to:Milan>` and
`until=<open | 6h>`. A reader of that format (`translate4_ft`) was fine-tuned on the third round's
material re-answered in the fourth format plus sentences with a scope or lifetime clause; its
test sentences carry phrases written by a separate AI instance (`data/instructions/v4_*.jsonl`).
`src/standing.py` keeps the policy table: which policies are active, which cover a request, the
one line they combine to (constraints add up, the tighter limit wins, the newest preference
decides), the conflicts a new policy raises (a contradiction, an override, a node cut off), and a
report per policy. `src/standing_stream.py` is the closed-loop condition `standing4`: policies
arrive, hold for the hours they state or until withdrawn, and the evaluator judges every
decision against the true table; `standing_noscope` and `standing_nountil` are the ablations.
The console keeps the table, with policies typed or arriving on this stream's schedule.

## A Swiss network

`data/topologies/swiss.xml` is a 24-city, 33-link backbone built for this project from public
geography along the main corridors (the links are the author's construction, not an operator's).
`data/topologies/swiss_names.json` gives every city's name in German, French, Italian and
English, and `mixed3.set_topology("swiss")` makes the instruction stream use them, so an
instruction says *Genf*, *Genève*, *Ginevra* or *Geneva* for the node `Genève`. `src/swiss.py`
builds test sets of the third round's sentences on this network; any closed-loop run takes
`--topology swiss`.

## The benchmark

`uv run python src/benchmark_export.py` writes `data/benchmark/`: every test instruction with
the line it means, every reader's answer and its outcome, and the metadata, with a dataset card.

## The policy language as a standard constraint

One line of the policy language is also one TAPI constraint (ONF Transport API 2.1.3, the
northbound interface of transport SDN controllers): links and nodes to avoid become
`exclude-link` and `exclude-node`, a node to pass through `include-node`, the limits
`max-allowed-hops` and `max-allowed-cost`, a preference the `route-objective-function`
(`MIN_WORK_ROUTE_HOP`, `MIN_WORK_ROUTE_COST`, `LOAD_BALANCE_MAX_UNUSED_CAPACITY`). What the
standard cannot carry (the fewest-slots preference, the order of several preferences, a part
handed on) travels in TAPI `name` entries. `src/tapi.py` does the mapping; the operator console
shows it next to every reading.

```bash
uv run python src/tapi.py "avoid=Zurich-Milan; via=none; hops=any; km=any; path=any; prefer=load,hops; rest=none"
```

## On a laptop

One base model and four adapters behind one [llama.cpp](https://github.com/ggml-org/llama.cpp)
server (build 11558 or later; Apertus needs b6686 or later). Measured on an RTX 4060 with 8 GB:
0.89 s per instruction, 0.97 s per decision.

```bash
# the files (private until submission): the 4-bit base and the adapters as GGUF
hf download blackfish021/apertus-lightpath-translator-v3-gguf --local-dir models

llama-server -m models/apertus-v1.5-8b-text-Q4_K_M.gguf \
    --lora models/lightpath-translator-v3-reader1-lora-f16.gguf \
    --lora models/lightpath-translator-v3-reader2-lora-f16.gguf \
    --lora models/lightpath-decider-v2-lora-f16.gguf \
    --lora models/lightpath-translator-v4-lora-f16.gguf \
    --lora-init-without-apply -ngl 999 -c 4096 -np 1 --port 8089 --jinja

# the hybrid, live: two readers, rule engine, decider with guard (in the uv environment)
export LLM_LORA_IDS='{"translate3_ft_live": 0, "translate3_ft2_live": 1, "apertus_ft_live": 2, "translate4_ft_live": 3}'
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
must run there too (the Linux build of llama.cpp), and the GGUF files should sit on the WSL file
system (`~/models`), where llama.cpp can memory-map them; from the Windows drive it holds the
whole model in RAM. The readers alone also work from Windows.

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
| Third round: training data, test sets, GPU jobs, analysis | `uv run python src/corpora3.py` (training data of two readers, then the test sets from `data/instructions/v3_source_*.json`); `uv run python src/translate.py texts --conditions operations_mix3 --out data/instructions/mix3.jsonl`; `READER=1 bash jobs/launch.sh train3 ...` and `READER=2`; `bash jobs/launch.sh phase4 ...`; `phase5` (the closed loop with another second reader, read beforehand by `big` with `BIG_SETS`); `gguf`, `gguf-lora`, `big` (Apertus 70B; `JOB_IMAGE=ghcr.io/astral-sh/uv:python3.12-trixie`); then on the laptop `uv run python src/readers3.py` and `uv run python src/report_phase3.py`. The owner's own lines (`data/instructions/owner_source.txt`): `uv run python src/corpora3_owner.py`, the readers on the laptop's server with `translate.py parse --sets data/instructions/owner.jsonl`, then `uv run python src/corpora3_owner.py --score` | `results/design/readers3.json`, `results/design/owner.json`, `results/tables/phase3.md` |
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

The reader's prompt is short: a system text that names the slots of the policy language, the
list of the network's nodes, and the instruction; the answer is one line, decoded under a grammar
built from that node list, so it always parses (`src/translate.py`, `src/grammar.py`). The
decider's prompt, the first round's design, lists the request, the candidate paths with their
hops, length, modulation and free blocks, and answers `path=1 slot=122`; it is shown in
`docs/report_rounds_1_2.md`. Intent definitions and wording are in `src/intents.py`.

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
    corpora3_owner.py  instructions written by people (the owner's, a contributor's) as test sets, and what the readers made of them
    readers3.py        third round: what each reader does with every test instruction; two readers
    tapi.py            a line of the policy language as a TAPI 2.1.3 topology and routing constraint
    console.py         the operator console (http server); console.html is the earlier page, at /legacy
    console_extras.py  the console's inspector (why each candidate was kept or dropped, the spectrum) and race
    console_ui/        the console's browser frontend: Svelte 5 and TypeScript, built by Vite into dist/
    corpora4.py        fourth round: training data of the fourth format (scope and lifetime)
    corpora4_tests.py  fourth round: test sets from the separately written scope and lifetime phrases
    standing.py        the policy table: scope, lifetime, combination, conflicts, report
    standing_stream.py the closed-loop condition with standing policies and its policies
    swiss.py           the Swiss network: test sets with the cities in each language's name
    consistency3.py    self-consistency of reader 1 as a third check
    benchmark_export.py the test instructions and every reader's answers as a dataset
    decider3_data.py   the matched decider's data: the first decider's states, the reader's sentences
    report_matched3.py the matched decider and the full-format reader's hybrids -> results/design/matched3.json
    analyse_decider_gap.py why a decider breaks more in closed loop than on the probes -> results/design/decider_gap.json
    report_phase3.py   third round: results JSON -> results/tables/phase3.md
    report_pdf.py      the report as HTML and, through a headless browser, as PDF
    report_figure.py   the report's figure: violations on the two closed-loop streams
  jobs/                run.sh (stages run inside a Hugging Face Job), push_bundle.sh, launch.sh,
                       phase1_local.sh (translators on the laptop, from the answer caches)
  tests/               pytest (`make test`)
  data/                sample/ and stats.json are committed; full/ is git-ignored (rebuilt by generate.py)
                       benchmark/: the test sets and every reader's answers as a dataset, with its card
                       translate4/: the fourth format's training data (committed)
                       full3/: the matched decider's data (git-ignored, rebuilt by decider3_data.py)
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
    results_overview.md every result with its source file, what it shows and what it does not
    submission.md      the submission checklist and the material prepared for it
    video_script.md    the two-minute demo, shot by shot
    cards/             model cards of the four adapters and the GGUF bundle
    status_history.md  the round-by-round status table in full
    figures/           the report's figures (violations.png, console.png)
  technical_report.md  the report; ApertusNetworkGym_Report.pdf is its rendering (src/report_pdf.py, five pages)
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
uv run pytest -q               # 79 tests, about a minute
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
| `LLM_BASE_URL` | A llama.cpp server with the base model and the four adapters (section "On a laptop"), e.g. `http://host.docker.internal:8089/v1` from inside the container. Empty: `make run` uses only files in the image |
| `LLM_LORA_IDS` | JSON that maps a policy name to the number of its adapter on that server; `run.sh` sets a default |
| `LLM_API_KEY` | Key for that endpoint |
| `HF_TOKEN` | Hugging Face token: gated model download, HF Jobs, dataset and adapter uploads |

## Hardware used

| Purpose | Machine |
| --- | --- |
| Simulation, data generation, MLP, CPU evaluation | Windows 11 laptop, WSL2 Ubuntu 24.04, 16 logical CPUs, 7.6 GB RAM visible to WSL |
| Fine-tuning and evaluation | One rented NVIDIA A100 80 GB as Hugging Face Jobs, 17.3 GPU-hours and about USD 43.18 over all four rounds (peak memory 18.8 GB training a reader, 23.6 GB answering) |
| The hybrid on a laptop (llama.cpp, 4-bit GGUF, four adapters) | RTX 4060 laptop GPU, 8 GB: 0.89 s per instruction, 0.97 s per decision |

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
