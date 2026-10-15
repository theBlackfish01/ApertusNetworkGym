---
base_model: andreasmartin/apertus-v1.5-8b-text
license: apache-2.0
language:
  - en
  - de
  - fr
  - it
pipeline_tag: text-generation
tags:
  - gguf
  - llama.cpp
  - lora
  - apertus
  - optical-networks
  - hack-apertus
---

# Apertus 8B lightpath models for llama.cpp (GGUF)

Everything the project *Operator instructions for lightpath provisioning with Apertus 8B* (Hack
Apertus 2026, Track 2B) runs on a laptop GPU: the base model quantised to 4 bits and its four
LoRA adapters as GGUF files, switched per request by one llama.cpp server. This is the
on-premise, air-gapped deployment of the submission: one process, no network.

| File | What it is | Size |
| --- | --- | --- |
| `apertus-v1.5-8b-text-Q4_K_M.gguf` | the base model, `andreasmartin/apertus-v1.5-8b-text`, Q4_K_M | 5.1 GB |
| `lightpath-translator-v3-reader1-lora-f16.gguf` | reader 1, third format (`blackfish021/apertus-lightpath-translator-v3`) | 159 MB |
| `lightpath-translator-v3-reader2-lora-f16.gguf` | reader 2, third format (`...-translator-v3-b`) | 159 MB |
| `lightpath-translator-v4-lora-f16.gguf` | the reader of standing policies, fourth format (`...-translator-v4`) | 159 MB |
| `lightpath-decider-v2-lora-f16.gguf` | the decider (`...-lora-v2-e2`) | 159 MB |

The adapters were converted with llama.cpp's `convert_lora_to_gguf.py` (build b11558) from the
PEFT adapters; the base with `convert_hf_to_gguf.py` and `llama-quantize`. The rendered prompts
are identical to the Transformers path apart from the start token.

## How to run

```bash
llama-server -m apertus-v1.5-8b-text-Q4_K_M.gguf \
  --lora lightpath-translator-v3-reader1-lora-f16.gguf --lora lightpath-translator-v3-reader2-lora-f16.gguf \
  --lora lightpath-decider-v2-lora-f16.gguf --lora lightpath-translator-v4-lora-f16.gguf \
  --lora-init-without-apply -ngl 999 -c 4096 -np 1 --port 8089 --jinja
```

A request names the adapter it wants in its body (`"lora": [{"id": 0, "scale": 1.0}, ...]`) and
passes the answer grammar as GBNF; the project's client does both (`src/translate.py`,
`src/policies.py`, `LLM_LORA_IDS`). On an RTX 4060 laptop GPU (8 GB): 0.89 s per instruction,
0.97 s per decision. Note: with four adapters loaded the server holds about 7 GB of host RAM.

## Results in this form (from the project's results files)

- Reader 1 in 4 bits: 93.1 % right meaning on the 2,078 blind sentences (bf16 in the job: 94.8 %).
- The fourth-format reader in 4 bits: 90.6 % on 800 blind policy sentences (job: 93.5 %); its
  policy table in closed loop stays within 2.4 points of the true table.
- The hybrid (two readers, rule engine, decider with guard) run live on the laptop on a mixed
  stream at 390 Erlang: 9.18 % violations (job: 8.47 %).
- 250 template lines (written outside the sentence generators by the author, partly with ChatGPT 6.1 Sol); among them, of the owner set's 40 (35 English, 5 Urdu in Latin script)
  reader 1 is right on 33, reader 2 on 35, the fourth-format reader on 31; of template set 1's 40
  (English, German, Italian, Swedish) reader 1 on 20 of the 25 per-request lines and the
  fourth-format reader on 35, standing policies included; of two more sets of 40 (English and
  German) reader 1 on 20 of 25 in each and the fourth-format reader on 33 and 34; of sets 4 and 5
  (90 lines in English, Swiss German, French and Italian) reader 1 on 45 of the 57 per-request lines
  and the fourth-format reader on 78. Over all 250 the fourth-format reader is right on 211.

## Intended use and limits

Research and prototyping on a simulator; synthetic sentences; the 4-bit build loses about 1.7
points against the bf16 adapters. License Apache-2.0 for the adapters and this packaging; the
base model under its own licence (Apache-2.0). Other models' role: Claude (Anthropic) wrote the
project's code and documentation under the author's direction, the sentence templates of the
training data and, as separate instances, the test sentences; no other model is part of the
system.

Repository: *filled at submission*.
