# Prior work, and whether this is worth publishing

Written 13 October 2026 for the owner. Based on about twenty web searches along the project's
separate claims and on reading the abstract and introduction of the closest papers. No paper was
read in full, so "does not do X" below means "the abstract, introduction and summary do not say
it does". Dates and venues are as the publishers' pages gave them on this day.

## 1. The short answer

- **No paper was found that describes this project.** In particular, none conditions lightpath
  provisioning (routing and spectrum assignment) on an operator's natural-language instruction and
  measures compliance in closed loop. Language models in optical networking are used for device and
  controller configuration, lifecycle agents, log analysis and explanations; learning for routing
  and spectrum assignment is reinforcement learning without language.
- **The architecture is not new.** "The model translates the sentence into a typed intermediate
  form, a deterministic engine enforces it" is an established pattern, with one 2026 preprint that
  is close in shape (routing constraints for satellite constellations) and one 2026 position paper
  that argues the same thesis in its title.
- **What appears to be new is the measurement.** The same model as translator and as decider on
  the same requests; a closed-loop compliance metric on a stream that includes what the model was
  never shown; asking by consequence with its cost counted, including the negative result with a
  fair operator; the closed-loop price of misreading scope and lifetime; four languages on an open
  sovereign model in 4 bits on a laptop.
- **Worth submitting: yes, as a conference paper or demonstration in the optical-networking or
  network-management community.** A journal article would need more evidence than there is now
  (sentences written by people, a controller or testbed behind the TAPI object, more than one
  training run).

## 2. The closest papers

| Paper | What it does | Overlap with this project | What it does that this project does not | What this project does that it does not |
| --- | --- | --- | --- | --- |
| Y. Li, [*Validated intent compilation for constrained routing in LEO mega-constellations*](https://arxiv.org/abs/2604.07264), arXiv, April 2026 | A 9B model (Qwen, six examples, no fine-tuning) compiles an operator sentence into a typed constraint program (ten hard constraint types and soft ones); an eight-pass deterministic validator accepts, repairs or abstains; a router applies the constraints. 240-intent benchmark: 87.6 % full semantic match; 46 points better than a rule-based parser on compositional intents; 81.8 % on out-of-distribution phrasing; zero constraint violations end to end | The closest in shape: sentence → typed constraints → deterministic enforcement; the compositional claim; a rule-based parser as baseline; a small open model | A formal validator with feasibility certification and adversarial tests; a repair loop; a learned router | Optical provisioning; fine-tuning (94.8 % against our own few-shot 87.2 %, consistent with their 87.6 %); the model as decider on the same requests; held-out combinations fixed in advance; four languages; a second reader and questions; scope and lifetime in closed loop; a laptop build |
| H. Hè, M. Apostolaki, [*Let AI agents translate networks, not reason about them*](https://arxiv.org/abs/2607.22947), arXiv, July 2026 (eight pages, a position paper) | Argues that models should be confined to translation into formal logic and a solver should do the reasoning; builds a symbolic model of an emulated WAN and shows it answers reachability and change-impact questions faster, cheaper and more reliably than a model reasoning directly | The thesis of our "translate or decide" result, stated as a position | A solver-backed network model; root-cause analysis | A measured instance of the thesis on a different task, with the same fine-tuned model in both roles, closed loop, and the case where translation is not possible (the decider as fallback) |
| A. Jacobs et al., [*Hey, Lumi!*](https://www.usenix.org/conference/atc21/presentation/jacobs), USENIX ATC 2021; and *Establishing trust for using natural language for intent-based networking*, IEEE TNSM 2025 | Operators state intents in natural language; entities are extracted (before large language models); the intent is written in an intermediate language, Nile, confirmed with the operator, compiled and deployed; a user study | The intermediate language, the read-back and confirmation, feedback from the operator. Nile's grammar has targets (`for client(...)`, a traffic class), locations (`from endpoint(...) to endpoint(...)`) and an interval (`start hour('09:00')`, `end hour('18:00')`; [Jacobs et al., 2020](https://arxiv.org/abs/2008.05509)), so scope and lifetime in an intent language are not new in themselves | A user study with real operators; campus policies; deployment | A language model as reader; routing constraints for optical provisioning; disagreement between two readers as the trigger for asking; closed-loop cost of each kind of misreading |
| Y. Zhang, H. Hu, G. Gu, [*NetInspector*](https://arxiv.org/abs/2609.21103), arXiv, September 2026 | Fine-tuned models translate intents into the Lumi schema well, but miss 35 to 48 % of violations when asked whether a new intent conflicts with an existing security policy; grounding each decision in retrieved network facts cuts that by over 30 points; a 2,224-sample benchmark over three kinds of topology, tested under shifts in phrasing | Fine-tuned translation into a fixed schema; a new policy checked against those in force; robustness to phrasing | Conflict checking studied as the main question, with a model in the loop and a large benchmark | The conflict check is a rule over the parsed lines (so it has no false negatives of that kind, and a narrower notion of conflict); provisioning, not access control; closed loop |
| R. Mondal, N. Bjørner, T. Millstein, A. Tang, G. Varghese, [*Tackling ambiguity in user intent for LLM-based network configuration synthesis*](https://conferences.sigcomm.org/hotnets/2025/papers/hotnets25-final189.pdf) (Clarify), HotNets 2025 | A "disambiguator" asks the user targeted behavioural questions, found by differential analysis, to decide where a synthesised stanza goes in an existing route map or access list | Asking by showing the consequence rather than the sentence | Formal verification of the stanza (Batfish); ambiguity that comes from interaction with existing configuration | Two readers' disagreement as the source of the candidates; asking deferred to the first live request that tells them apart; the number of questions and the error measured in closed loop, including with an operator who can only choose between the two readings |
| M. Ahmadian, P. Monti, C. Natalino, [*A T-API-compliant ReAct agentic loop for optical networks*](https://arxiv.org/abs/2606.18000), arXiv, June 2026 | The first agent loop on the standard TAPI northbound interface; compares generic HTTP tools with domain-specific ones for correctness, token use and hallucination | TAPI as the interface between a model and an optical controller. From the group that wrote the simulator this project uses | A controller actually driven; tool design measured | A policy language that maps onto TAPI constraints, rather than an agent calling tools; fine-tuned small model; closed-loop traffic |
| C. Wang et al. (KDDI Research), [*Cross-vendor telecom optical network configuration automation from intentions*](https://opg.optica.org/jocn/abstract.cfm?uri=jocn-18-10-1042), JOCN 18(10), October 2026 | Open models (32B to 72B) fine-tuned with a reinforcement-learning scheme produce device configurations from intentions; perfect accuracy reported on a deployed network of 256 nodes from 12 vendors | Fine-tuned open models, intention to configuration, optical | A deployed multi-vendor network; equipment verification | Small model (8B) on a laptop; routing policy rather than device configuration; what happens with instructions the system was never shown |
| C. Sun et al. (Huawei, EURECOM, Politecnico di Milano), [*Local AI-agents for lifecycle management of optical networks*](https://opg.optica.org/jocn/abstract.cfm?uri=jocn-17-8-C82), JOCN 17(8), 2025 | Locally fine-tuned models call management APIs (100 % on the calls tested), with a digital twin to check changes, on a commercial testbed | Local fine-tuned model, digital twin before applying, on-premise argument | A commercial testbed; lifecycle breadth | As above |

Further work in the same neighbourhood, each overlapping one aspect:

- **Translation into an intermediate form, generally:** NetConfEval (Wang et al., CoNEXT 2024: a
  benchmark; models translate intents to formal specifications well and silently drop conflicts);
  NetIntent and IBNBench (Hossain et al., 2025: 33 open models on intent-to-flow-rule translation
  and conflict detection); INTA (2025); ChatGosen (Liu et al., 2026: "semantic-computation
  decoupling" through an intermediate representation for router configuration); Emergence
  (Dzeparoska et al., 2024: intents decomposed into policies).
- **Small fine-tuned models on premises:** SLM_netconfig (Lira, Caicedo, Da Fonseca,
  [arXiv:2512.02861](https://arxiv.org/abs/2512.02861): fine-tuned small models beat a larger
  prompted one on configuration, privately); AlSamarneh et al. (2026: intent translation with LoRA).
- **Optical, language models:** Di Cicco et al. (ECOC 2024: an open model with constrained
  generation as a natural-language interface to an optical testbed, over 80 %); Liu et al. (JOCN
  2026: field trial, three modes of agent); IntentLLM in TeraFlowSDN (Adanza et al., NetSoft 2024
  and a journal version: sentences to transport-slice intents, including a duration, 93 % factual
  accuracy); Bekri et al. ([arXiv:2509.22834](https://arxiv.org/abs/2509.22834): models with
  formal methods for optical network *design*); HuGLEN (Rezaei et al.,
  [arXiv:2607.18068](https://arxiv.org/abs/2607.18068): choosing a model for operator-facing
  explanations).
- **Asking, outside networking:** cost-gated clarification in text-to-SQL (DASG,
  [arXiv:2508.05061](https://arxiv.org/abs/2508.05061): ask only when the expected saving exceeds
  the cost of the exchange); the abstention literature the report already cites.
- **Routing and spectrum assignment by learning:** DeepRMSA and its successors, up to graph
  transformers (2026): reinforcement learning, no language, no operator instruction.

## 3. What is new, what is not, and what a reviewer will say

**Not new, and should be cited as such:** the translate-then-enforce architecture; an intermediate
intent language with confirmation (Lumi); constrained decoding for valid output (Di Cicco et al.);
locally fine-tuned small models (Sun et al., SLM_netconfig); clarification through differential
examples (Clarify); conflict detection between intents; time-bounded intents; agents on TAPI.

**Not found anywhere, so a fair claim of contribution:**

1. Operator language as a condition on lightpath provisioning, with a compliance metric in closed
   loop on an open simulator, and instruction-blind baselines on the same requests.
2. The same fine-tuned model measured as translator and as decider (99.6 against 91.1 % compliance;
   0 against 3.3 % violations in closed loop), with clause combinations held out in advance. The
   position paper argues it; the satellite paper compares against a rule-based parser, not against
   the model deciding.
3. Asking by consequence from two readers' disagreement, with the questions and the error counted,
   and the sober finding that with a fair operator most of the translator's gain disappears (167
   of 397 questions showed two wrong readings).
4. What a misread scope or lifetime costs in closed loop (ablations over ten seeds), and a reader
   that keeps the policy table within one to two points of the truth.
5. The negative results: a learned gate does not recognise what it was never shown; self-consistency
   marks unfamiliar input more than error; a second reader of the same recipe shares most errors.
6. Four languages on an open Swiss model, 4-bit on a laptop, with the cost of quantisation stated.
7. The benchmark: 4,850 instructions with the line each means and every reader's answers.

**What a reviewer will push on:**

- The sentences are synthetic and written by a language model. This is the first objection in
  every venue; 30 to 50 sentences from people would not remove it but would answer it.
- Simulator only. The optical community's flagship venues favour testbeds; the TAPI object was
  never sent to a controller.
- One training run per adapter; the decider was trained on an earlier round's intents, so the
  translate-or-decide comparison is confounded with a training mismatch (the report says so).
- Baselines: no strong general-purpose model as a few-shot translator beyond Apertus 70B. A
  reviewer will ask what a frontier model does with fifteen examples.
- Breadth against depth: a paper cannot carry four rounds. The publishable core is items 1 and 2,
  with either item 3 or item 4 as the second result.

## 4. Where it could go

| Venue | Date and deadline (as found today) | Fit | Notes |
| --- | --- | --- | --- |
| OFC 2027, Los Angeles, 7–11 March 2027 | Summary deadline **20 October 2026, 12:00 EDT**; three pages | The largest audience for exactly this topic; network-control subcommittees take simulation studies, though testbed work is favoured | [OFC treats anything already on a preprint server or other online archive as published](https://www.ofcconference.org/submit-a-paper/submission-guidelines/). Whether a public hackathon repository with the technical report counts is a question for the OFC rules, not one I can answer; it should be checked before either is made public if OFC is wanted. Seven days from today |
| ONDM 2027, Castelldefels (hosted by CTTC), 25–28 May 2027 | Regular papers **18 January 2027**; demo track **12 March 2027** | The best fit: optical network design and modelling, where simulation is the norm; CTTC is the home of TeraFlowSDN, the controller the TAPI object would go to | Time for sentences from people, a second fourth-format reader and a controller behind the TAPI object. The console suits the demo track |
| ECOC 2027 | Deadline usually in spring; not found today | As OFC, European | |
| JOCN (journal) | No deadline | Has published the three closest optical papers | Needs the extensions of section 3; often reached by invitation from an OFC or ONDM paper |
| IEEE NetSoft 2027 (Seoul), NOMS, CNSM; IEEE TNSM (journal) | NetSoft 2027 deadline not posted; the 2026 one was 12 January | The intent-based-networking community: Lumi, NetIntent, IntentLLM are theirs | Would lead with the intent language, asking and standing policies, less with optics |
| HotNets | Usually early summer | The translate-or-decide and asking-by-consequence arguments as a six-page position with evidence | Highly selective |
| arXiv | Any time | Fixes the date of the idea; the related 2026 preprints show the area is moving monthly | Conflicts with OFC's rule if done first; fine for ONDM and IEEE venues under their usual preprint policies, to be confirmed per venue |

A practical point about people: the three most relevant optical preprints of 2026 that involve the
simulator used here (the TAPI agent, HuGLEN) and the simulator itself come from one group (Natalino
and Monti, Chalmers). A project that is the first to put operator language on their simulator is
of direct interest to them.

## 5. A correction made while doing this

One reference removed from the report earlier today as "not found", the KDDI article in JOCN
18(10), does exist; the second search found the publisher's page. It is restored in the report
(`docs/decisions.md`, last row). The other removed item, an OFC 2026 demonstration, was again not
found and stays out.
