---
base_model: andreasmartin/apertus-v1.5-8b-text
library_name: peft
license: apache-2.0
language:
  - en
  - de
  - fr
  - it
pipeline_tag: text-generation
tags:
  - lora
  - apertus
  - optical-networks
  - intent-based-networking
  - hack-apertus
---

# Apertus 8B lightpath decider, matched to the reader

A LoRA adapter that decides a lightpath request directly, like
`blackfish021/apertus-lightpath-lora-v2-e2`, but trained on the sentences the reader of the
policy language learned from. It exists for one comparison: translating an operator's
instruction into a line that a rule engine enforces, against deciding every request with the
instruction in the prompt, with both models trained on the same instructions. It is not part of
the deployed system. Built for Hack Apertus 2026 (online, Track 2B) by the project *Operator
instructions for lightpath provisioning with Apertus 8B*.

Given the request (source, destination, bit rate), the candidate paths with their state (hops,
length, free spectrum, modulation, the free blocks) and an instruction in plain language, it
answers `path=1 slot=120` or `reject`.

## Model details

- **Base model:** `andreasmartin/apertus-v1.5-8b-text` (text-only conversion of
  `swiss-ai/Apertus-v1.5-8B`).
- **Method:** QLoRA, 4-bit NF4 base, rank 32, alpha 32, 79.7 M trainable parameters,
  completion-only loss; one A100 80 GB, two epochs as two jobs of 64 minutes each (the second
  from the first's adapter at learning rate 1e-4, taken because the first complied on 94.0 % of
  held-out decisions, under the 98 % fixed beforehand). Greedy decoding constrained to the
  decision line.
- **Training data** (`src/decider3_data.py`): the 12,000 Optical Networking Gym states of the
  first decider (preset `jocn_benchmark`, nobel-eu, seeds 101–106). The 4,000 without an
  instruction keep their labels. On the other 8,000, the 5,570 training sentences of the reader
  `blackfish021/apertus-lightpath-translator-v3` (3,903 distinct, English, German, French,
  Italian), each at least once, placed where possible on a state where it is restrictive (at
  least one feasible path complies and at least one does not): 6,792 restrictive, 80 impossible,
  124 neutral, 1,004 sentences that do not apply. The label is the rule engine's decision under
  the reader's line for the sentence, with preferences in the order stated. No test sentence is
  used.
- **Files:** `adapter_model.safetensors` and `adapter_config.json` at the root.
- **Developed by:** Wadood Ranjha. **License:** Apache-2.0.

## Results (from the project's results files)

- Held-out decisions (states of seeds 107 and 108 with the reader's held-out sentences) that
  comply: 95.8 % with training templates, 99.3 % with unseen wording, 94.7 % with pairs of
  clauses never seen together (the reader with the rule engine: 99.8 / 100.0 / 93.7 %).
- Stored requests with blind test sentences written by separate AI instances (672 per language):
  it complies on 96.4 / 94.8 / 95.2 / 95.4 % (en / de / fr / it), the first decider on 91.1 /
  87.1 / 86.0 / 86.6 %, the reader with the rule engine on 99.6 / 98.2 / 99.1 / 99.3 %. Matched
  training data closes 62–70 % of the gap. With three clauses it complies on 90.0 % (first
  decider 76.2 %, reader 100.0 %).
- Instruction types outside the policy language: about as the first decider (new types 77.6
  against 78.8 %).
- Closed loop on a mixed stream at 390 Erlang, three seeds: it breaks 14.4 % of requests (first
  decider 16.8, reader with the rule engine 10.6, first fit 28.6), 14.1 % of those with an
  instruction inside the policy language (first decider 19.2, reader 0.9). Most of that is one
  case the probes do not contain: on 11.4 % of those requests no feasible path complies and only a
  reject does, and it takes a path on 93.5 % of them (10.65 of its 14.09 points); it was taught to
  reject on 2.4 % of its training examples. Where some path complies it breaks 4.7 %. Behind a reader, as
  the fallback for instructions outside the language, it is no better than the first decider
  (9.7 against 9.1 %).

## How to use

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "andreasmartin/apertus-v1.5-8b-text"
tok = AutoTokenizer.from_pretrained(base)
model = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(base), "blackfish021/apertus-lightpath-decider-v3-e2")
```

The prompt is rendered by `src/prompt.py` of the project repository from the simulator's request
analysis; `src/policies.py` parses the answer.

## Intended use and limits

Research on a simulator: the model ranks candidate paths the simulator has already checked for
feasibility, it computes no physics. One topology, one traffic model, synthetic sentences, one
training run. Other models' role: Claude (Anthropic) wrote the project's code and documentation
under the author's direction and the wording templates of the reader's training data; no other
model is part of the system.

Repository: *filled at submission*.
