# Submission: what is prepared, what is yours to do, and what a fresh pair of eyes said

Written 13 October 2026 for the owner, updated 14 and 15 October. The organisers' requirements are in `track_2b/README.md` (the template's challenge text);
this page maps them to the material in the repository and lists the steps only the owner can take.

## 1. What you are submitting, in one page

| Piece | What it is | Where |
| --- | --- | --- |
| The idea | An operator states a routing policy in plain language; Apertus 8B reads it once into one line of a seven-slot policy language; a rule engine enforces the line on every request the policy covers, for as long as it holds. Two readers, and a question to the operator only when their readings would route a request differently. What the language cannot express goes to a fine-tuned decider with a guard. | `README.md` at the repository root (first page), `technical_report.md` §1–2 |
| The models | Four LoRA adapters on `andreasmartin/apertus-v1.5-8b-text`: reader 1 and reader 2 (third format), the reader of standing policies (fourth format: scope and lifetime), the decider. Each 160 MB; all four as GGUF for llama.cpp with the 4-bit base. A fifth, the matched decider (`apertus-lightpath-decider-v3-e2`), was trained only for the comparison of translating and deciding on the same sentences and is not part of the system. | Hub repos `blackfish021/apertus-lightpath-*` (private until you flip them); cards in `docs/cards/` |
| The evidence | Blind test sentences in four languages written by separate AI instances; held-out clause combinations fixed before the sentences were opened; closed-loop runs in the simulator with instruction-blind baselines; a standing-policy stream judged against the true table; a 4-bit laptop build measured beside the job build. | `results/` (every number), `results/tables/phase3.md`, `docs/results_overview.md` |
| The standards link | The policy line maps onto TAPI 2.1.3 constraints. | `src/tapi.py`, the console |
| The console | A dark operations view in Svelte and TypeScript: the map as the stage, a feed of what the model does, the policies in force with remaining hours, questions that pause the stream, play at a chosen pace; an inspector that shows why each candidate path was kept or dropped and the spectrum a lightpath took; a race of the four methods on the evaluation's stream, each lane checked against its stored run; a guided tour. From recorded answers in Docker, or live on the laptop. | `src/console.py`, `src/console_extras.py`, `src/console_ui/`, `make console` |
| The benchmark | 5,480 test instructions (48 sets), every reader's answers, metadata, a card in the HackApertus format. | `data/benchmark/`; Hub dataset `blackfish021/apertus-lightpath-benchmark` (private until you flip it) |
| The report | Five pages, rendered by `src/report_pdf.py`; one figure (`docs/figures/violations.png`). | `technical_report.md`, `ApertusNetworkGym_Report.pdf` |
| The record | Every deviation, mistake and cost; the full status history. | `docs/decisions.md`, `docs/status_history.md` |

Cost: about USD 51.7 of GPU time for everything, about 20.7 GPU-hours on one rented A100 (USD 8.5 of it on 14 October: the matched decider, the fourth-format reader in the mixed stream, and the owner set and template set 1 at 16 bits).

## 2. The deliverables, against the brief

| Requirement (`track_2b/README.md`) | State | Who |
| --- | --- | --- |
| Public Git repo from the template, `track_2b/` kept, other tracks deleted | Repository ready; `make run` works from the root and from `track_2b/`; `data/` as committed is 40 MB (limit 100) | **You:** create the public repo, push, keep `track_2b/` as is |
| `make run` runs end to end in Docker | Checked from a fresh clone on 12 Oct; the console through Docker on 13 Oct, and on 15 Oct with the frontend built in the image's Node stage; one more fresh-clone run is planned after the final commit | Me, then you on your machine once |
| Technical report, PDF, max. 6 pages without references (the template's text since 11 October), `TeamName_Report.pdf` in `track_2b/` | `ApertusNetworkGym_Report.pdf` renders at five pages; two placeholders remain (the video link, the public links); the commit is named by the tag `submission` | **You:** team name and members; then I fill, re-render and copy to `track_2b/<TeamName>_Report.pdf` |
| Demo video, max. 2 min | Script and shot list in `docs/video_script.md` | **You:** record; give me the link |
| Dataset (optional): evaluation, responses, metadata, card | Uploaded as a private dataset with the card | **You:** make it public; the link goes into the report and the README |
| Apertus weights published | Five adapters and the GGUF bundle with cards, private | **You:** make them public (the organisers accepted the text-only base on condition that the fine-tuned weights are published) |
| Other models' role described | Report §3 states what Claude did and did not do; the root `README.md`, "AI assistance" | done |
| Target architecture | On-premise and air-gapped: one llama.cpp server, no outbound call; report §2 | done |
| Licence | Apache-2.0 code, CC-BY-4.0 report, CDLA-Permissive-2.0 data | done |

## 3. Your steps, in order

1. ~~Team name and members~~: done, ApertusNetworkGym (Wadood Ranjha); the PDF is `track_2b/ApertusNetworkGym_Report.pdf`.
2. **Create the public repository** from the Hack Apertus template on GitHub (Use this template),
   then tell me its URL. I push, set the links in the report, README and cards, and run `make run`
   from a fresh clone of it.
3. **Make the six Hub repositories and the dataset public** (Settings, Change visibility) when
   you are ready: `apertus-lightpath-lora-v2-e2`, `-translator-v3`, `-translator-v3-b`,
   `-translator-v4`, `-translator-v3-gguf`, `-decider-v3-e2`, and the dataset
   `apertus-lightpath-benchmark`. `apertus-lightpath-decider-v3` holds the matched decider's first
   epoch, which no reported result uses; keep it private or delete it.
4. **Record the video** (`docs/video_script.md`): the console live on the laptop, one German
   standing policy, one question. If the server is not up, `make console` with recorded lines.
5. **Submit** at the organisers' URL: the repository URL, the PDF, the video URL, the dataset URL.

The template lines (`results/design/owner.json`, `template1.json` to `template5.json`): 250 lines
written outside the project's sentence generators, by the author, partly with an AI assistant
(ChatGPT 6.1 Sol), as the owner stated on 15 October; until then the documents called them
written by people, and the first three template sets were named `contributor1` to `contributor3`;
sets 4 and 5 (90 lines) came the same day. They
test phrasing the readers were not built from, not how operators write, so the reviewers' main
doubt (all evidence is synthetic) stands: the answer would still be **30 to 50 sentences typed by
other people** without an AI tool. The guide to hand out is
`data/instructions/contributor_template.txt`. Since no data was collected from people, the
consent rules of the terms (section 6, responsibly sourced datasets) do not apply.

The parallel set (15 October): the same 60 items in nine languages and scripts (English, German,
French, Italian, Urdu/Hindi in Latin letters, Urdu in Urdu script, Hindi in Devanagari, Arabic in
Arabic script and in Latin letters), written and translated by
separate AI instances, read on the laptop (`src/parallel3.py`, `results/design/parallel.json`,
`docs/figures/languages.png`). The translations have not been checked by a native speaker; the
owner could check the Urdu and the Urdu/Hindi in Latin letters.

## 4. What a fresh pair of eyes said

Three independent reviewers (sub-agents with no memory of the project, run on 13 October) read
the repository as a judge, as a rigour auditor and as a judge's assistant running a fresh clone.
Their reports are in the session's scratchpad; the substance:

- **The judge** scored 5, 5, 4, 4, 4 on the five criteria (22 of 25): the architectural question
  was measured rather than assumed, the evaluation discipline is rare at a hackathon, the artefact
  is standards-shaped and runs in 4 bits on a laptop. Points lost: value argued only inside a
  simulator on AI-written sentences; the model server not in the compose stack; TAPI not sent to a
  controller. Risk of dropping from top 5 % to top quarter if the deliverables are missing or the
  presentation stays too dense. Done since: a glossary and a five-row status table in the README,
  one project name, the 4-bit numbers beside the job numbers, a figure, run requirements stated.
- **The rigour auditor** verified 18 claims against the results files: 16 matched; two did not,
  both fixed: five reader score files predated a parser change and have been re-scored from the
  same recorded answers (`docs/decisions.md`), and one sentence compared an English-only figure with
  a four-language one and now compares like with like. Wordings tightened: triples cost three
  points, the asking gain is an upper bound because the simulated operator answers with the truth,
  "decider alone" also measures a training mismatch (answered on 14 October by a decider trained
  on the reader's own sentences: two thirds of the offline gap was training data, the closed-loop
  gap stays), the standing ablations swing with the seed,
  laptop and job figures labelled. Still running at the time of writing (CPU replays from recorded
  answers): a fair simulated operator that picks the right reading only when one of the two is
  right, the laptop translators on the European network for a like-with-like Swiss comparison, and
  ten seeds of the standing stream; their results go into the report when they land.
- **The fresh-clone check** traced `make run` from the root to the container and found the chain
  coherent, no secrets or GPU needed, 79 tests passing, licences and disclosure in order; it listed
  the stale README statements (fixed) and the missing deliverables (section 2).

## 5. What could still be done, with two days

| Item | Value | Effort / cost |
| --- | --- | --- |
| Sentences typed by other people without an AI tool (section 3; none so far) | The single best answer to "all synthetic" | an hour of yours to collect, an hour of mine |
| A second reader of the fourth format | Gives scope and lifetime the disagreement check the third format has; a training-variance estimate | about USD 2.7 of GPU (about 3.3 left) |
| The model server as a compose service | Sovereign deployment in one command; judges with a GPU could run the live mode | half a day |
| TAPI object sent to a controller (TeraFlowSDN) | Turns the mapping into an integration | a day or more; uncertain |
| Operators consulted | Value evidence beyond the simulator | depends on access |
