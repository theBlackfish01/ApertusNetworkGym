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

# Apertus 8B lightpath translator, third format (reader 1)

A LoRA adapter that turns an operator's routing instruction for an optical transport network,
in English, German, French or Italian, into one line of a small policy language that a rule
engine enforces:

```
avoid=Zurich-Milan,Basel; via=Lyon; hops=4; km=any; path=any; prefer=load,hops; rest=none
```

The slots: links and nodes to avoid, a node to pass through, limits on hops and length, a
candidate by its number, preferences in the order stated, and `rest=more` for a part the slots
cannot carry. Three answers refuse: `unsupported` (about the route, but outside the language),
`no_instruction` (not a routing instruction), and a name that is not a node leaves the line
*unresolved*. Built for Hack Apertus 2026 (online, Track 2B) by the project *Operator
instructions for lightpath provisioning with Apertus 8B*; this is reader 1 of its two readers.

## Model details

- **Base model:** `andreasmartin/apertus-v1.5-8b-text`, the text-only conversion of
  `swiss-ai/Apertus-v1.5-8B` (accepted by the organisers for the hackathon).
- **Method:** QLoRA, 4-bit NF4 base, rank 32, alpha 32, 79.7 M trainable parameters,
  completion-only loss; one A100 80 GB, 34 minutes. Decoding is greedy and constrained by a
  grammar built from the network's node list, so the answer is always a line of the language.
- **Training data:** 5,570 instructions in four languages from templates filled with the
  topology (nobel-eu, 28 nodes), with the line each means; eight clause pairs trained, seven pairs
  and five triples held out, four instruction types absent from all training. The split was fixed
  and committed before any test sentence was opened.
- **Files:** `adapter_model.safetensors` and `adapter_config.json` at the root are the released
  adapter; `adapter-epoch1/` and `checkpoint/` are training artefacts kept for the record.
- **Developed by:** Wadood Ranjha. **License:** Apache-2.0.

## Results (from the project's results files)

- Right meaning on 2,078 blind test sentences written by separate AI instances: 94.8 % (one
  clause 94.6, clause pairs seen in training 95.6, pairs never seen together 96.5, triples 91.2);
  by language 96.7 (en), 91.4 (de), 96.0 (fr), 94.8 (it) %.
- Decisions of the rule engine under its lines comply with the instruction on 99.6 % of 672
  probe requests (the fine-tuned decider alone: 91.1 %; first fit: 66.8 %).
- Apertus 70B with 15 examples and no training reads 89.2 % of the same sentences.
- Weak point: of four instruction types no component was ever shown, it silently reads 46.6 %
  as something in the language; a second reader of the same recipe (`...-translator-v3-b`)
  catches part of that by disagreeing.
- In 4-bit GGUF form on a laptop GPU (RTX 4060, llama.cpp) it reads 93.1 % of the same
  sentences at 0.89 s each.

## How to use

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "andreasmartin/apertus-v1.5-8b-text"
tok = AutoTokenizer.from_pretrained(base)
model = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(base), "blackfish021/apertus-lightpath-translator-v3")
```

The prompt (system text, the node list, the instruction) and the answer grammar are in the
project repository, `src/translate.py` and `src/grammar.py`; without the grammar the model still
answers in the format, with it the answer is guaranteed to parse. A GGUF of the adapter for
llama.cpp is in `blackfish021/apertus-lightpath-translator-v3-gguf`.

## Intended use and limits

For research and prototyping of intent-based control of optical networks on a simulator. The
training and test sentences are synthetic; no operator wrote them. The language carries seven
slots; everything else is refused or handed on. Trained once; no second training run for error
bars. Other models' role: Claude (Anthropic) wrote the project's code and documentation under
the author's direction, the sentence templates of the training data and, as separate instances
that never saw the repository, the test sentences; no other model is part of the system.

Repository: *filled at submission*. Report: `technical_report.md` in that repository.
