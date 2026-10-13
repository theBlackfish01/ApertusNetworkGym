# Results overview — every result of the four rounds, what it means, and what it does not show

> Written 13 October 2026 for the owner's review. Every number is copied from the results file
> named next to its table; nothing here was computed afresh. The technical report
> (`technical_report.md`) is the six-page version of this; `docs/report_rounds_1_2.md` the long
> account of the first two rounds; `results/tables/phase3.md` the rendered tables of rounds three
> and four; `docs/decisions.md` the log of every deviation and its cost.

## Terms used throughout

- **Lightpath provisioning:** for each connection request (source, destination, bit rate) the
  controller picks a route among candidate paths and a block of spectrum slots on it, or rejects
  the request. The simulator is the Optical Networking Gym, preset `jocn_benchmark`: the
  nobel-eu network of 28 nodes and 41 links, five candidate paths per request, 320 slots.
- **Erlang (E):** the offered load, arrivals per unit time times holding time. 240 E is a quiet
  network, 390 E a busy one, 600 E on the Swiss network a busy one for its size.
- **Blocking:** the share of requests rejected for lack of spectrum. **Violation:** a decision
  that breaks the operator's instruction (a route through a link told to be avoided, a candidate
  taken when the instruction excluded it). **Complies:** the decision lies in the set of paths
  the instruction allows; when none is allowed, only a reject complies.
- **Closed loop:** the policy decides every request of a live simulated stream and its decisions
  change the network state the next requests see. **Offline (probe):** the policy answers a
  fixed set of request snapshots; nothing is applied.
- **First fit:** the instruction-blind baseline that takes the first candidate path with free
  spectrum. **Teacher:** a rule that ignores the instruction and picks by load or hops.
  **Oracle / true table:** the decision with the instruction known exactly.
- **Decider:** Apertus 8B fine-tuned to answer each request directly (`path=1 slot=120` or
  `reject`). **Reader (translator):** Apertus 8B fine-tuned to turn the instruction once into one
  line of a small policy language, which a rule engine then enforces. **Hybrid:** the reader
  first, the decider for what the reader marks as outside the language, with a **guard** that
  replaces a decider's choice if it breaks the part the line does carry.
- **LoRA / QLoRA:** fine-tuning that trains small added matrices (rank 32 here, 79.7 M parameters)
  on top of a frozen base; QLoRA keeps the base in 4-bit precision while training. An **adapter**
  is the trained addition, 160 MB each.
- **Grammar-constrained decoding:** the model may only produce tokens that keep the output a
  valid line of the policy language (node names from the topology, slots in order). **Greedy:**
  the most likely token each step. **Temperature 0.8:** sampling with randomness, used here only
  to get varied readings for the self-consistency check.
- **Held-out:** clause combinations (pairs, triples) or instruction types fixed before testing and
  never present in training. **Blind:** test sentences written by separate AI instances that saw
  neither the repository nor our wording.
- **GGUF, 4-bit, llama.cpp:** the file format and runtime used on the laptop (RTX 4060, 8 GB);
  the base is quantised to 4 bits, each adapter travels as its own GGUF file.

## 1. What was built

Apertus 8B reads an operator's policy sentence, in any of four languages, into one line of a
policy language. A rule engine enforces that line for every request the policy covers, for as
long as it holds; the line is also a TAPI 2.1.3 constraint, the object a transport SDN controller
takes. A second reader reads the sentence again and the operator is asked when a request would be
decided differently under the two readings. Instructions outside the language go to a fine-tuned
decider with a guard. A policy table holds standing policies with scope and lifetime, names
conflicts and reports per policy. An operator console shows the network on a map, reads back each
reading, previews its effect on a copy of the network, and keeps an audit trail per lightpath.
Everything runs on a laptop GPU.

Four adapters were trained on one rented A100 (Hugging Face Jobs): the decider on 12,000
simulator decisions (138 min), two readers of the third format on 5,570 instructions each (34 min
each), one reader of the fourth format (scope and lifetime) on 7,170 (65 min). Total 17.3
GPU-hours, about USD 43.18 of 45 (`docs/decisions.md`, budget rows).

## 2. Rounds one and two: the decider, and translate against decide

**Decider, closed loop** (`results/eval/*.json` of the second pass; 390 E, three seeds,
violations % of requests; `docs/report_rounds_1_2.md` section 5):

| Policy | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
| --- | --- | --- | --- | --- | --- | --- |
| First fit (ignores intents) | 24.5 | 10.4 | 43.2 | 0.1 | 19.3 | 33.9 |
| MLP control (small classifier, no language model) | 0.8 | 2.7 | 11.4 | 0.1 | 3.2 | 24.9 |
| Apertus 8B, no fine-tuning | 28.1 | 10.2 | 42.1 | 0.1 | 19.2 | 32.6 |
| Apertus 8B fine-tuned, second pass | 3.3 | 0.6 | 0.7 | 0.1 | 1.0 | 12.9 |
| Apertus 8B fine-tuned, first pass | 17.5 | 0.5 | 1.5 | 0.1 | 3.4 | 20.4 |

What it shows: fine-tuning is what makes the model follow an intent at all (the untrained model
is first fit with extra invalid answers); the second pass, which taught avoid-link pairs as
filter-then-rank, fixed the first pass's avoid-link weakness. Offline compliance of the second
pass: 98.9 % on new traffic, 98.7 % on unseen wording, 85.8 % on unseen pairs (the MLP control
97.3 / 96.3 / 72.5). The open weakness is composition: two intents never seen together cost the
decider 12.9 % violations.

**Translate or decide** (`results/tables/phase1.md`; closed loop, 390 E, violations %):

| Where the model sits | Avoid link | Fewest hops | Least loaded | Fewest slots | Unseen wording | Unseen pairs |
| --- | --- | --- | --- | --- | --- | --- |
| Decides every request, fine-tuned | 3.27 | 0.63 | 0.67 | 0.13 | 1.03 | 12.88 |
| Translates once, fine-tuned | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 2.77 |
| Translates, 7 examples, no training | 0.03 | 0.00 | 10.58 | 0.00 | 3.50 | 4.17 |
| Keyword parser, no model | 0.00 | 0.00 | 0.00 | 0.00 | 11.33 | 0.00 |

Right meaning on harder sets (independent wording, native German, French, Italian, Swiss German,
misspelt cities, another topology): the fine-tuned translator 97.5 / 96.6 / 98.4 / 97.5 / 95.3 /
95.5 / 98.9 %, the decider 91.3 / 89.6 / 92.0 / 90.9 / 85.3 / 89.8 / 92.3 %, a keyword parser
87.5 / 74.5 / 73.4 / 70.1 / 72.5 / 79.0 / 95.7 %. What it shows: the model reads better than it
decides, and a rule engine with a correct line cannot violate; the parser fails on anything but
the trained wording. This decided the architecture: translate first.

**Second translator and the first hybrid** (round two): the second translator reads 95.0 % of
independently worded and 96.6 / 94.5 / 98.0 % of native German / French / Italian instructions,
86.4 % with two preferences (first translator 41.6 %); closed loop 0.20 % violations on pairs
(first 2.77 %). The decider follows three instruction types it was never trained on (pass through
a node 94.0 %, avoid a node 83.5 %, a given candidate 84.0 % compliance, where first fit gives
16.5 / 32.5 / 11.5) and is no better than the shortest candidate on hop or length limits. On a
mixed stream the hybrid breaks 4.0 % of requests, the translator alone 9.3 %, the decider alone
6.3 %, first fit 19.4 %. What it shows: the decider is worth keeping as the fallback for what the
language does not carry.

## 3. Round three: a policy language, two readers, a guarded fallback, the laptop

Third answer format: `avoid=…; via=…; hops=…; km=…; path=…; prefer=…; rest=…`. Test sentences:
168 per language from four separate AI instances. Held-out combinations fixed and committed before
the sentences were opened (`7ab1e66`).

**Reader 1 by composition and the decider's compliance** (`results/offline/*_probes3.json`,
672 English requests):

| | One clause | Pair seen | Pair never seen | Three clauses, never seen | All |
| --- | --- | --- | --- | --- | --- |
| Reader 1, right meaning, % | 94.6 | 95.6 | 96.5 | 91.2 | 94.8 |
| Apertus 8B, 15 examples, no training, % | 89.5 | 81.0 | 91.1 | 85.6 | 87.2 |
| Comply: first candidate that fits, % | 70.6 | 63.3 | 62.5 | 57.5 | 66.8 |
| Comply: decider alone, % | 96.2 | 90.6 | 85.7 | 76.2 | 91.1 |
| Comply: reader 1 and rule engine, % | 99.4 | 100.0 | 99.1 | 100.0 | 99.6 |

By language reader 1 is right on 96.7 (en), 91.4 (de), 96.0 (fr), 94.8 (it) %
(`results/translate/translate3_ft.json`). Apertus 70B with 15 examples and no training: 89.2 %
(generation 1.5), 71.9 % (generation 1). What it shows: the slots carry composition (pairs never
seen read as well as trained ones), the decider loses ground with every clause, and the
fine-tuned 8B reads better than an untrained model nine times its size.

**The gate and the second reader** (`results/design/readers3.json`; "left" = applied wrongly
although two readers were compared; in brackets the share of instructions asked about):

| | Reader 1 alone | Left with reader 2 | Left with the untrained 8B | Left with the untrained 70B |
| --- | --- | --- | --- | --- |
| Policy language, applied wrongly % | 4.6 | 3.7 (2.8) | 1.5 (12.7) | 0.2 (13.4) |
| Types never shown to any component | 46.6 | 16.2 (31.6) | 19.4 (44.7) | 0.0 (69.2) |
| Carried in part | 72.2 | 36.3 (50.9) | 33.0 (54.2) | 33.0 (53.3) |

What it shows: the reader does not recognise what it was never shown (it silently reads 46.6 % of
unknown types as something in the language). Two readers of one recipe share most misreadings; a
reader that differs (the 70B) catches more, at the price of many more questions.

**Closed loop, mixed stream** (`results/eval/*_mix3.json`; 45 % in the language, 15 % unknown
types, 10 % carried in part, 10 % no instruction, 5 % places outside the network, 15 % none;
390 E, three seeds; violations % of requests):

| Policy | Violations | Asked, % of requests |
| --- | --- | --- |
| First fit | 28.6 | – |
| Decider alone | 16.8 | – |
| Translator alone | 10.6 | – |
| Hybrid with guard | 9.5 | – |
| Hybrid that asks when the readers differ | 8.5 | 8.9 |
| Hybrid with the untrained 70B as the check | 8.3 | 24.1 |

Inside the language the hybrid breaks 0.8 %, on unknown types 28.9 %; a better gate does not move
the latter (28.3 %). What it shows: the remaining violations are what the decider cannot follow,
not what the gate misses. A second reader of the same size buys most of the gain of the 70B at a
third of the questions.

**The laptop** (`results/design/readers3.json`, `results/eval/*_laptop_mix3.json`): 4-bit base
and GGUF adapters under llama.cpp on an RTX 4060: 0.89 s per instruction, 0.97 s per decision.
The 4-bit readers lose 1.7 points on the third-format sets. The hybrid that asks, run live with
the 4-bit models, breaks 9.18 % (job: 8.47 %) with 225 questions over the three seeds.

## 4. Round four: console, TAPI, asking by consequence, Swiss network, standing policies, self-consistency, benchmark

**Asking by consequence** (`results/eval/translate3_ft_askif-ft2_mix3.json` and the `_ask-ft2_`
file, both loads, one process). Instead of asking whenever the two readers differ, the first
reading is applied provisionally and the operator is asked on the first request that the two
readings would decide differently:

| Translator with two readers | Questions (both loads) | Asked, % at 390 E | Violations, % at 390 E |
| --- | --- | --- | --- |
| Asks whenever the readings differ | 397 | 8.9 | 10.28 |
| Asks on the first request that tells them apart | 332 | 7.8 | 10.25 |

65 pairs of differing readings were never told apart by any request. On the laptop (4-bit, decider
live): the hybrid that asks 9.18 % with 225 questions; by consequence 9.53 % with 152 questions
(73 pairs never told apart), asking on 7.4 % of requests instead of 9.6 %. What it shows: 16 %
fewer questions at the same error in the job; a small cost on the laptop, with a known cause: when
both readers are wrong in different ways, asking at once fixes the reading, asking by consequence
only once the two wrong readings diverge.

**Standing policies.** A fourth format adds `scope=<any|rate:G|from:node|to:node>` and
`until=<open|Nh>`. The reader trained on it, on 800 blind policy sentences
(`results/translate/translate4_ft.json`): right meaning including scope and lifetime 95.0 (en),
92.0 (de), 95.0 (fr), 92.0 (it) %, 93.5 % overall; by kind, a bit rate 90–97.5, requests from a
node 72.5–90 (the weakest), to a node 92.5–100, a number of hours 90–100, until further notice
92.5–100. On the third round's sets it is at least as good as reader 1 (96.7 / 93.2 / 96.0 /
94.6 %). In 4 bits on the laptop: 90.6 %.

Closed loop on a policy stream (`results/eval/*_standing4.json`; policies arrive three at the
start and one every two simulated hours, at most four active, hold for the hours they state or
until withdrawn, cover the requests their scope names; three seeds):

| Policy, violations % of requests against the true table | 240 E | 390 E | Rejected, % |
| --- | --- | --- | --- |
| The true policy table | 0.0 | 0.0 | 31.4 / 34.7 |
| First fit (ignores the policies) | 42.0 | 38.1 | 2.7 / 8.2 |
| Teacher (ignores the policies) | 47.9 | 45.6 | – |
| True policies, scope ignored | 12.7 | 30.0 | 43.5 / 61.4 |
| True policies, lifetime ignored | 11.9 | 6.4 | 42.7 / 39.8 |
| Policies read by the fourth-format reader | 1.1 | 1.5 | 30.7 / 34.2 |
| The same reader in 4 bits on the laptop | 2.4 | 1.6 | 31.8 / 34.2 |
| Policies read by the third-format reader (no scope, no lifetime) | 21.4 | 36.9 | 52.0 / 68.1 |

What it shows: reading scope and lifetime right is what makes a standing policy safe. The reader's
table stays within 1.5 points of the truth (per seed 0.9 / 0.0 / 2.4 and 0.0 / 4.4 / 0.1); ignoring
scope costs 13–30 points, ignoring lifetime 6–12; the old reader, with no slot for either, applies
every policy to every request for ever and rejects half to two thirds of them. Caveat: the stream's
policies are restrictive by construction (a third of requests rejected under the truth), so the
absolute numbers describe this stream, the differences describe the slots.

**The fourth-format reader as gate and check** (`results/design/readers3.json`): on the types
never shown it silently applies 16.7 % (reader 1 46.3 %); as the check behind reader 1 it leaves
10.2 % of them at 38.0 % asked and 1.5 % inside the language at 3.3 % asked, better than reader 2
on both counts. One training run with 1,600 more sentences, so a lead, not a result.

**Self-consistency as a third check** (`results/design/consistency3.json`; five readings of
reader 1 at temperature 0.8 on the laptop). On 2,078 policy-language sentences, where the greedy
reading is wrong on 6.9 %, and 108 instructions of never-shown types, wrong on 43.5 %:

| Signal that makes the system ask | Language: asked, % | Language: wrong and not asked, % | Never shown: asked, % | Never shown: wrong and not asked, % |
| --- | --- | --- | --- | --- |
| Reader 2 disagrees | 5.4 | 4.2 | 37.0 | 8.3 |
| Any of five samples differs | 8.0 | 3.5 | 88.0 | 2.8 |
| Two or more of five differ | 6.3 | 4.0 | 75.0 | 4.6 |
| Reader 2 disagrees, or a sample differs | 10.1 | 2.9 | 88.0 | 2.8 |
| The untrained 70B disagrees | 15.1 | 0.6 | 59.3 | 0.9 |

Each sample reads about one point worse than greedy (92.1 % against 93.1 % in the language). What
it shows: disagreement among samples marks unfamiliar input more than it marks error; it catches
half of the errors in the language, a little more than reader 2 for a little more asking, and
nearly all on unknown types but by asking about almost everything. Reader 2 does with one reading
what the samples do with five; the samples need no second model; the 70B remains the strongest
signal per question.

**A Swiss network** (`data/topologies/swiss.xml`, 24 cities, 33 links; the test sentences filled
with Swiss cities in each language's own name, 1,151 sentences, `results/translate/*_swiss.json`):
reader 1 on the laptop is right on 90.6 (en), 92.0 (de), 90.8 (fr), 89.0 (it) %, against 93.1 % on
the network it was trained on; one clause 92–97 %, three clauses 70–85 %; reader 2 90.6 / 90.6 /
86.0 / 86.6 %. Closed loop at 600 E (`results/eval/*_mix3_swiss.json`, three seeds): first fit
24.7 %, translator alone 9.8 (2.2 inside the language, against 0.9 on the European network), the
translator that asks 9.0 (asked on 12.6 %), by consequence 9.3 (asked on 8.0 %). What it shows:
city names the reader never saw cost two to four points, mostly on three-clause sentences;
*Genf*, *Ginevra*, *Saint-Gall* land on their nodes.

**The owner's 22 lines** (`results/design/owner.json`; 17 English, 5 Urdu in Latin script):
reader 1 on the laptop right on 18 (16 of 17 English, 2 of 5 Urdu); the fourth-format reader on 17.
Its two new errors read "go from London to Lyon via Oslo" and "to Prague, avoid Berlin" as scopes
(`to:Lyon`, `to:Prague`) where the owner meant the current request's end points. The language has
no word for a request's own end points; that is the next slot to add.

**TAPI export** (`src/tapi.py`, `tests/test_tapi.py`): the line becomes a `topology-constraint`
and `routing-constraint` of TAPI 2.1.3 (`exclude-link`, `exclude-node`, `include-node`,
`max-allowed-hops`, `max-allowed-cost`, `route-objective-function`); what the standard cannot carry
travels in `name` entries. Checked by unit tests and shown in the console; not sent to a
controller.

**The console** (`src/console.py`, `make console`): checked live on the laptop with the
fourth-format reader (an English rate-and-hours policy and a German "everything from Zurich …
until withdrawn" read correctly, applied over eight requests), and through Docker from recorded
answers on 13 October (`docs/decisions.md`).

**The benchmark** (`data/benchmark/`): 4,712 test instructions in 20 sets with the line each
means, 40,332 reader answers with their outcome, metadata and a dataset card.

## 5. What the results do not show, and what is left

- One topology in closed loop for the mixed stream (the Swiss one at 600 E for the translators
  only; no hybrid there, since the decider would have to run live), one traffic model, one
  simulator; the model ranks candidates the simulator has checked, it computes no physics.
- Every test sentence but 22 was written by an AI instance. Four languages; Swiss German only on a
  stress set (72.7 %).
- Unknown instruction types remain the weak point in the mixed stream (28–37 % violations for
  every policy); the limit is what the decider can follow, not the gate.
- The fourth-format reader has no second reader, so scope and lifetime are read once; the policy
  stream is our construction; weekday and date phrases are not in the language; "to Prague" is a
  scope to the new reader and a destination to the operator.
- One training run per adapter; the simulated operator answers every question with the truth;
  the table's combination and conflict rules are our choices.
- The 4-bit laptop build loses 1.7 points on the third-format sets; the 70B ran from community
  GGUF builds; the TAPI object was never sent to a controller.
- Next steps named in the report: a slot for a request's own end points; a second fourth-format
  reader (about USD 2.7); calendar times; TAPI to a controller (TeraFlowSDN); instructions written
  by operators; the hybrid on the Swiss network.
