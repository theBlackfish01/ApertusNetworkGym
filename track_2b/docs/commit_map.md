# Commit hashes before and after 15 October 2026

Before the repository was published, the author e-mail of every commit was changed to the GitHub
no-reply address (`git filter-branch --env-filter`, on the owner's request). Content, dates and
messages are unchanged (every pair below has the same tree and subject), but every hash changed.
Results files written before then record the old hash in `repo_commit`; this table gives the
commit it now has. The documents quote the new hashes.

| Old | New | Date | Subject |
| --- | --- | --- | --- |
| `cfbe505` | `7d784d4` | 2026-10-10 | Start from the Hack Apertus template (track 2B) and add the spec |
| `a340b9e` | `1285a18` | 2026-10-10 | Build the intent-conditioned lightpath provisioning pipeline |
| `68009a1` | `bb9db30` | 2026-10-10 | Run Apertus stages as resumable Hugging Face Jobs |
| `b749ff5` | `0b88a2b` | 2026-10-10 | Record smoke-test measurements and the budget-driven training and evaluation plan |
| `07339c6` | `e566548` | 2026-10-10 | Record the Discord answer on the text-only Apertus checkpoint |
| `7e00486` | `6251cb0` | 2026-10-10 | Fine-tune Apertus for one epoch: gate passed; record results and failure modes |
| `1262c9f` | `4e816cb` | 2026-10-10 | Evaluate the fine-tuned and the zero-shot Apertus model; fill in the results |
| `7718764` | `8906729` | 2026-10-10 | Diagnose the avoid-link over-rejection and record the plan for a second pass |
| `29ee844` | `37a9cc0` | 2026-10-10 | Second pass: filter-then-rank for avoid-link pairs; freeze the first pass |
| `f9c48c9` | `05ca929` | 2026-10-10 | Second pass: baselines, control model and zero-shot re-scored under the new rule |
| `485b3f6` | `3e84db6` | 2026-10-11 | Second pass: two epochs on the relabelled data, closed-loop results, report |
| `ac15ce9` | `595e1ac` | 2026-10-11 | Phase 1: instruction format, rule engine and translator arm |
| `18e552a` | `03a28ed` | 2026-10-11 | Phase 1: harder test sets, probes, unseen topology, job stages |
| `6920462` | `8fce72b` | 2026-10-11 | Phase 1: laptop pipeline, report tables, two-preference analysis in closed loop |
| `efd5be8` | `9382c89` | 2026-10-11 | Phase 1: translator prompt says how to treat foreign or misspelt node names; README |
| `8d34c13` | `b03cd13` | 2026-10-12 | Phase 1 results: translator against decider |
| `ad911c3` | `3e57e33` | 2026-10-12 | Phase 1: by-pair table, main tables without single-condition runs, runbook |
| `0402165` | `026c826` | 2026-10-12 | Analysis of the existing answers for the choice of next steps, with charts |
| `1564305` | `d071500` | 2026-10-12 | Second translator: answer format with no_instruction, training wording, hybrid policy |
| `b43703c` | `8a0f9fd` | 2026-10-12 | Second round: test sets for unseen instruction types, non-instructions and native German, French, Italian; job stages |
| `3423da2` | `ee2f49b` | 2026-10-12 | Mixed closed-loop condition, hybrid with a live decider, result fetcher, second-round report |
| `fc831a6` | `24d453d` | 2026-10-12 | Second round results: stronger translator, decider on unseen instruction types, hybrid in closed loop |
| `9e393e4` | `926253e` | 2026-10-12 | make run: keep mixed-condition result files out of the main tables, name the second translator, render phase2.md |
| `e9a4ba4` | `1022a3d` | 2026-10-12 | Sanity check: instruction-blind baselines for the unseen types and the mixed stream; corrected claim |
| `7ab1e66` | `88336ca` | 2026-10-12 | Third format of the translator: a line of slots; training data for two readers |
| `471d8ad` | `366c4cd` | 2026-10-12 | Third round: test sets from independent sources, mixed condition 3, second reader and guarded fallback, job stages |
| `1e74b75` | `b50137c` | 2026-10-12 | Third round: a server client for the translator (GBNF grammar), reader analysis, job stages for GGUF and a larger Apertus |
| `3a782eb` | `715a21a` | 2026-10-12 | Third round: a second instruction-blind baseline, and new-type requests on which neither blind choice complies |
| `ccf8826` | `53f75a5` | 2026-10-12 | Third round: table script; offline results record guard actions and rejects |
| `fda197b` | `dd85a88` | 2026-10-12 | Third round: the scoring job runs its four model processes side by side |
| `06ced47` | `12a2e89` | 2026-10-12 | Third round: design decisions logged; template for the owner's own test instructions |
| `a8d3326` | `b21b59b` | 2026-10-12 | Third round: readers and decider behind one llama.cpp server; demo output for translator policies; 70B and adapter stages |
| `800e76b` | `f92d1e5` | 2026-10-12 | Third round, first results: both readers and the reader with examples on the test instructions; the decider on the new types; replays on the laptop |
| `fed1fa2` | `712c412` | 2026-10-12 | Third round, results: policy language, gate, two readers, decider on new types, closed loop, laptop, Apertus 70B |
| `b07b2df` | `6ab4e81` | 2026-10-12 | Third round: Apertus 70B of generation 1.5 as reader and as check; report draft of six pages; README, runbook, ledger |
| `96d0a38` | `fcf7239` | 2026-10-12 | make run: keep the third mixed condition out of the main tables |
| `1ee5fc4` | `86fef99` | 2026-10-12 | The owner's own instructions as a test set, scored on the laptop; ONG issue text checked again |
| `cfc6de6` | `6263c4a` | 2026-10-12 | ONG issue text: one line per paragraph, as GitHub renders line breaks in issues |
| `ee65aa8` | `940de40` | 2026-10-12 | Job stage phase5: the hybrid that asks in closed loop with another second reader from its cache; the instructions of the load-390 episodes |
| `335ae9c` | `551a576` | 2026-10-12 | Closed loop with the untrained Apertus 70B as second reader, load 390 |
| `76203e4` | `7ad2033` | 2026-10-12 | Decisions log: the owner's decisions of 12 October (AI-assistance statement stays, report on hold) and a check of the ledger against the job list |
| `039a6b4` | `4d1e6ad` | 2026-10-12 | TAPI export: a line of the policy language as a TAPI 2.1.3 topology and routing constraint |
| `f497433` | `b0cfc24` | 2026-10-12 | Operator console: the hybrid on a map, read-back, TAPI, impact preview on a copy of the simulator, audit trail; make console |
| `8912abf` | `dfde339` | 2026-10-13 | Asking by consequence (translator and hybrid policies, replays of the translator in closed loop); Swiss topology, names in four languages, test sets and stream |
| `630d50f` | `aeba3cc` | 2026-10-13 | Standing policies: the fourth format (scope, lifetime), its training data and blind test sets, the policy table with conflicts and report, the closed-loop stream with arrivals and expiry, the console's policy mode; self-consistency analysis script |
| `140399e` | `16f5d16` | 2026-10-13 | Benchmark export with a dataset card; README sections for standing policies, the Swiss network and the benchmark; adapter-to-GGUF stage takes a name |
| `e28e4d2` | `8ee84cb` | 2026-10-13 | Console: test of the standing-policy mode; README note on where the GGUF files must sit in WSL |
| `a4d08a0` | `4bbcda6` | 2026-10-13 | Report script: tables for standing policies, the Swiss network and the self-consistency check; score4 job stage |
| `e7f5e14` | `30782f7` | 2026-10-13 | Fourth-format reader scored; standing policies in closed loop (truth, ablations, baselines, the reader); hybrid that asks on the laptop; ledger |
| `8768ce4` | `7be0f9e` | 2026-10-13 | Report rewritten for the fourth round (standing policies, console, TAPI, asking by consequence, Swiss network, benchmark, related work); README status |
| `e5398fb` | `6d23af5` | 2026-10-13 | Report, decisions and README with the laptop hybrid results; fourth-round section in the lesson |
| `61cf878` | `017277c` | 2026-10-13 | Swiss network: reader scores and closed loop at 600 E; report script renders them |
| `a0b4897` | `b80107c` | 2026-10-13 | README: the fourth adapter on the laptop server; GPU-hours corrected |
| `9cd62be` | `a5522c7` | 2026-10-13 | Reader analysis and tables include the fourth-format reader; the live policy console checked; report notes the gate lead |
| `417658c` | `543a7be` | 2026-10-13 | Standing policies with the laptop readers: the third-format reader on the policy stream, the fourth-format reader in 4 bits; report, README, decisions, lesson |
| `dc4785a` | `803085d` | 2026-10-13 | Self-consistency check: five temperature samples of reader 1 on the laptop; the analysis, reader tables and benchmark export; reader 1's laptop score file restored; report, README and decisions filled |
| `fcb125d` | `42e572a` | 2026-10-13 | Decisions: the console checked through Docker |
| `1b4e2c2` | `05aa912` | 2026-10-13 | The console rebuilt: one stream under standing policies and per-request instructions, a dark operations view with a feed of what the model does, questions by consequence, play; results overview; root Makefile |
| `6ceeb4b` | `3d22ff4` | 2026-10-13 | Submission material and the fresh-eyes reviews: README glossary and compact status, one project name, run requirements, report with figure, helper-model paragraph and audit rewordings, references checked; model cards, benchmark dataset card, video script, submission guide, results overview; five reader score files re-scored with the current parser; a fair simulated operator (askfair); laptop translators on the European network; PDF rendering script |
| `7aa14ed` | `2ce5ba3` | 2026-10-13 | Replays the rigour audit asked for: a fair simulated operator (questions and both-wrong counts), the laptop readers on the European network, ten seeds of the standing stream; fresh-clone make run checked; report, overview, decisions and README updated; PDF re-rendered |
| `38fc349` | `2afc878` | 2026-10-13 | Report header: team ApertusNetworkGym; the submission commit named by the tag; the report rendered as ApertusNetworkGym_Report.pdf |
| `fa9dfd6` | `fd37363` | 2026-10-13 | Prior-work survey (docs/prior_work.md); the KDDI JOCN reference restored after a second search found it; decisions row; PDF re-rendered |
| `13671f2` | `d421323` | 2026-10-13 | Ten seeds of the standing stream for the two laptop readers; console wording for a reading that rejects and for the class of the pending instruction; decisions row |
| `ab18f6d` | `90cff4d` | 2026-10-14 | Decisions row: the true policy table's 2 violations traced to the evaluator's record of a combined policy (one via node); not fixed, owner decides |
| `b1d9238` | `99528c5` | 2026-10-14 | Template and guide for routing instructions written by network people (per request and standing policies) |
| `2a37d7b` | `90f1397` | 2026-10-14 | Matched decider: data from the first decider's states and the routing-field reader's sentences (decider3_data.py); job stages read4, train-d3, eval-d3, check6; the fourth format ranks preferences in order; the full-format reader on the stored probes; decisions rows |
| `2ec2803` | `d871e8f` | 2026-10-14 | Matched decider and the full-format reader on the mixed stream: results of both experiments |
| `b69be95` | `79068c0` | 2026-10-14 | The two experiments in the report, tables, cards and submission checklist |
| `e8d5d14` | `3a08604` | 2026-10-14 | Why a decider breaks far more in closed loop than on the probes |
| `b046725` | `b843e51` | 2026-10-14 | Lines written by people: the owner's other 18 and a contributor's 40 |
| `24dcd2a` | `888fc08` | 2026-10-14 | The fourth-format reader at 16 bits on the lines written by people |
| `2372063` | `74e1fb3` | 2026-10-14 | Format report_phase3.py |
| `7ce5691` | `4a6ba61` | 2026-10-14 | Decisions row: a three-page version of the OFC paper (outside git) |
| `fd645f4` | `e85e9a6` | 2026-10-14 | Console reorganised: header, counters, cards per request and policy, rail, panels and tabs |
| `9cd6891` | `67f2b88` | 2026-10-14 | Answer caches of the live console sessions of 14 October |
| `53a5bc5` | `05c2e89` | 2026-10-15 | The console's frontend in Svelte and TypeScript: inspector, race, tour |
| `309964e` | `6571708` | 2026-10-15 | Docs brought up to the console's frontend; a new console screenshot |
| `45337c9` | `8a3de2a` | 2026-10-15 | README: compute through the follow-ups of 14 October (about 20.7 GPU-hours, USD 51.73) |
| `00ccea2` | `021caef` | 2026-10-15 | Two more sets of 40 lines from the template; Urdu out of the console's autofill |
| `576efe5` | `580cdd6` | 2026-10-15 | Template lines named for what they are; 250 of them; the same 60 items in eight languages; the template's layout |
