---
base_model: andreasmartin/apertus-v1.5-8b-text
library_name: peft
license: apache-2.0
language:
  - en
pipeline_tag: text-generation
tags:
  - lora
  - apertus
  - optical-networks
  - intent-based-networking
  - hack-apertus
---

# Apertus 8B lightpath decider

A LoRA adapter that decides a lightpath request directly: given the request (source,
destination, bit rate), the candidate paths with their state (hops, length, free spectrum,
modulation, the free blocks), and an operator's instruction in plain language, it answers
`path=1 slot=120` or `reject`. Built for Hack Apertus 2026 (online, Track 2B) by the project
*Apertus Lightpath*. In the final system it is the
**fallback**: instructions the policy language can express are translated by a reader
(`blackfish021/apertus-lightpath-translator-v3`) and enforced by a rule engine; instructions
outside the language, or carried only in part, go to this decider, whose choice a guard checks
against the part the language does carry.

## Model details

- **Base model:** `andreasmartin/apertus-v1.5-8b-text` (text-only conversion of
  `swiss-ai/Apertus-v1.5-8B`).
- **Method:** QLoRA, 4-bit NF4 base, rank 32, alpha 32, 79.7 M trainable parameters,
  completion-only loss; one A100 80 GB, 138 minutes (two epochs, the second pass of two). Greedy
  decoding constrained to the decision line.
- **Training data:** 12,000 decisions from Optical Networking Gym episodes (preset
  `jocn_benchmark`, nobel-eu, seeds 101–106) labelled by rule-based teachers that follow the
  intent: no intent, four single intents (avoid a link, fewest hops, least loaded, fewest slots)
  and two intent pairs, with the avoid-link cases taught as filter-then-rank. Test episodes use
  other seeds.
- **Files:** `adapter_model.safetensors` and `adapter_config.json` at the root are the released
  adapter; `adapter-epoch1/` and `checkpoint/` are training artefacts.
- **Developed by:** Wadood Ranjha. **License:** Apache-2.0.

## Results (from the project's results files)

- Closed loop at 390 Erlang, three seeds, violations of the intent in % of requests: avoid link
  3.3, fewest hops 0.6, least loaded 0.7, fewest slots 0.1, unseen wording 1.0, intent pairs
  never seen together 12.9 (first fit: 24.5 / 10.4 / 43.2 / 0.1 / 19.3 / 33.9; the base model
  without fine-tuning answers invalidly 88–98 % of the time).
- Offline agreement with the teacher's admissible set: 98.9 % on new traffic, 98.7 % on unseen
  wording, 85.8 % on unseen pairs.
- It follows three instruction types it was never trained on (pass through a node 94.0 %, avoid
  a node 83.5 %, a given candidate 84.0 % compliance, where an instruction-blind choice complies
  on 16.5 / 32.5 / 11.5 %) and is no better than the shortest candidate on hop or length limits.
- On the third round's probes it complies on 91.1 % of requests against 99.6 % for the reader
  with the rule engine; composition is its weakness (one clause 96.2 %, three clauses 76.2 %),
  which is why the system translates first and decides only what it cannot translate.
- A decider trained on the reader's own sentences (`blackfish021/apertus-lightpath-decider-v3-e2`)
  complies on 96.4 % of the same probes, so about two thirds of that gap is training data; in
  closed loop it still breaks 14.1 % of in-language requests against the reader's 0.9 %.

## How to use

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "andreasmartin/apertus-v1.5-8b-text"
tok = AutoTokenizer.from_pretrained(base)
model = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(base), "blackfish021/apertus-lightpath-lora-v2-e2")
```

The prompt is rendered by `src/prompt.py` of the [project repository](https://github.com/theBlackfish01/ApertusNetworkGym) from the simulator's request
analysis; `src/policies.py` parses the answer. A GGUF of the adapter for llama.cpp is in
`blackfish021/apertus-lightpath-translator-v3-gguf` (`lightpath-decider-v2-lora-f16.gguf`).

## Intended use and limits

Research and prototyping on a simulator: the model ranks candidate paths the simulator has
already checked for feasibility, it computes no physics. Trained on one topology and one traffic
model; English instructions; synthetic data. Other models' role: Claude (Anthropic) wrote the
project's code and documentation under the author's direction and the wording templates; no
other model is part of the system.

Repository: [github.com/theBlackfish01/ApertusNetworkGym](https://github.com/theBlackfish01/ApertusNetworkGym) (`track_2b/`).
