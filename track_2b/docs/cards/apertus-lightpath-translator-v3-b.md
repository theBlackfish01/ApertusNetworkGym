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

# Apertus 8B lightpath translator, third format (reader 2)

The second reader of the project *Operator instructions for lightpath provisioning with Apertus
8B* (Hack Apertus 2026, Track 2B): the same recipe as reader 1
(`blackfish021/apertus-lightpath-translator-v3`) with another random seed and another sample of
the training sentences. Its purpose is disagreement: every instruction is read by both readers,
and where the two lines differ in meaning the operator is asked instead of the system guessing.
The policy language and the format are those of reader 1; see its card.

## Model details

- **Base model:** `andreasmartin/apertus-v1.5-8b-text` (text-only conversion of
  `swiss-ai/Apertus-v1.5-8B`).
- **Method:** QLoRA, 4-bit NF4 base, rank 32, alpha 32, 79.7 M trainable parameters,
  completion-only loss; one A100 80 GB, 34 minutes; grammar-constrained greedy decoding.
- **Training data:** 5,570 instructions in four languages, a different draw from the same
  template pool as reader 1, same held-out clause combinations and never-shown types.
- **Files:** `adapter_model.safetensors` and `adapter_config.json` at the root are the released
  adapter; `adapter-epoch1/` and `checkpoint/` are training artefacts.
- **Developed by:** Wadood Ranjha. **License:** Apache-2.0.

## Results (from the project's results files)

- Right meaning on the 2,078 blind test sentences: 93.6 % (en 96.2, de 89.5, fr 94.5, it 92.9).
- As the check behind reader 1 (`results/design/readers3.json`): on the policy language the
  share of sentences applied wrongly without a question falls from 4.6 % to 3.7 % at 2.8 % of
  sentences asked about; on instruction types shown to no component from 46.6 % to 16.2 % at
  31.6 % asked. An untrained Apertus 70B as the second reader leaves 0.2 % and 0.0 % at 13.4 %
  and 69.2 % asked: two readers of one recipe share most misreadings, a reader that differs
  catches more, at the price of more questions.
- In closed loop on a mixed stream (390 Erlang, three seeds) the hybrid that asks when the two
  readers differ breaks 8.5 % of requests, asking on 8.9 %; asking only on the first request that
  tells the readings apart puts 16 % fewer questions at the same error.

## How to use

As reader 1 (see its card), with this repository's name. The project's console
(`src/console.py`) runs both readers side by side and asks when they differ. A GGUF of the
adapter for llama.cpp is in `blackfish021/apertus-lightpath-translator-v3-gguf`.

## Intended use and limits

Research and prototyping on a simulator; synthetic sentences; the language carries seven slots.
Other models' role: Claude (Anthropic) wrote the project's code and documentation under the
author's direction, the sentence templates of the training data and, as separate instances that
never saw the repository, the test sentences; no other model is part of the system. The author wrote the template lines (a test set) partly with ChatGPT 6.1 Sol (OpenAI).

Repository: [github.com/theBlackfish01/ApertusNetworkGym](https://github.com/theBlackfish01/ApertusNetworkGym) (`track_2b/`).
