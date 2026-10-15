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

# Apertus 8B lightpath translator, fourth format (standing policies)

A LoRA adapter that reads a standing policy for an optical transport network, in English,
German, French or Italian, into one line of the policy language of the project *Operator
instructions for lightpath provisioning with Apertus 8B* (Hack Apertus 2026, Track 2B), with
two slots the third format lacks, a **scope** and a **lifetime**:

```
avoid=Zurich-Milan; via=none; hops=any; km=any; path=any; prefer=none; scope=rate:400; until=6h; rest=none
```

`scope` is `any`, a bit rate (`rate:400`), requests from a node (`from:Zurich`) or to a node
(`to:Milan`); `until` is `open` (until withdrawn) or a number of hours. "For the next 6 hours,
400G services avoid the Zurich–Milan link" is the sentence above. A policy table (`src/standing.py`
in the repository) holds such lines: which policies are active, which cover a request, the one
line they combine to, the conflicts a new policy raises, and a report per policy.

## Model details

- **Base model:** `andreasmartin/apertus-v1.5-8b-text` (text-only conversion of
  `swiss-ai/Apertus-v1.5-8B`).
- **Method:** QLoRA, 4-bit NF4 base, rank 32, alpha 32, 79.7 M trainable parameters,
  completion-only loss; one A100 80 GB, 65 minutes; grammar-constrained greedy decoding.
- **Training data:** 7,170 records: the third format's training material re-answered in the
  fourth format, plus 1,600 sentences that carry a scope or lifetime clause, in four languages,
  from templates filled with the topology. Scoped sentences of the held-out paraphrase pool were
  kept out of training.
- **Files:** `adapter_model.safetensors` and `adapter_config.json` at the root are the released
  adapter; `adapter-epoch1/` and `checkpoint/` are training artefacts.
- **Developed by:** Wadood Ranjha. **License:** Apache-2.0.

## Results (from the project's results files)

- On 800 blind policy sentences (200 scope and lifetime phrases written by a separate AI
  instance, attached to the third round's blind sentences): right meaning, scope and lifetime
  included, 93.5 % (en 95.0, de 92.0, fr 95.0, it 92.0); by kind, a bit rate 90–97.5, requests
  from a node 72.5–90 (the weakest), to a node 92.5–100, a number of hours 90–100, until further
  notice 92.5–100.
- On the third format's test sets it is at least as good as reader 1: 96.7 / 93.2 / 96.0 /
  94.6 % (en / de / fr / it); of instruction types shown to no component it silently applies
  16.7 % (reader 1: 46.3 %).
- Closed loop on a stream of standing policies (three at the start, one every two simulated
  hours, at most four active; 240 and 390 Erlang, three seeds): the policy table built from its
  readings breaks 1.1 / 1.5 % of requests against the true table, where ignoring scope breaks
  12.7 / 30.0 %, ignoring lifetime 11.9 / 6.4 %, first fit 42.0 / 38.1 %, and a reader of the
  third format (no scope, no lifetime) 21.4 / 36.9 %.
- In 4-bit GGUF form on a laptop GPU it reads 90.6 % of the policy sentences and its table stays
  within 2.4 points of the truth.
- On the third round's mixed stream of per-request instructions (390 Erlang, three seeds) it can
  replace reader 1: alone it breaks 10.7 % of requests (reader 1: 10.6 %), in front of the decider
  9.1 % (9.5 %), passing 16.1 % of requests to the decider instead of 11.5 %.
- Template lines (by the author, partly with ChatGPT 6.1 Sol), at 16 bits: right on 34 of the owner set's 40 and on 36 of template set 1's
  40 (English, German, Italian, Swedish; 15 standing policies), Swedish 9 of 10, although no
  training sentence is Swedish. In 4 bits on the laptop: 31, 35, and 33 and 34 of two more sets of
  40 in English and German (English 46 of 50, German 21 of 30), 61 of 70 and 17 of 20 of sets 4
  and 5 (English, Swiss German, French, Italian): 211 of all 250.
- The same 60 items in eight languages and scripts (written and translated by separate AI
  instances; 4 bits on the laptop; `results/design/parallel.json`): right on 55 in English, 52–53
  in German, French and Italian, 43 in Urdu script, 45 in Hindi and Arabic, 32 in Roman Urdu.
- Known error: "to Prague, avoid Berlin" is read as a scope (`to:Prague`) where an operator means
  the current request's destination; the language has no word yet for a request's own end points.

## How to use

As reader 1 (`blackfish021/apertus-lightpath-translator-v3`, see its card), with this
repository's name and the fourth format's prompt (`src/translate.py`, `SYSTEM4`). A GGUF of the
adapter for llama.cpp is in `blackfish021/apertus-lightpath-translator-v3-gguf`
(`lightpath-translator-v4-lora-f16.gguf`).

## Intended use and limits

Research and prototyping on a simulator; synthetic sentences; one training run; no second reader
of this format yet, so scope and lifetime are read once. Other models' role: Claude (Anthropic)
wrote the project's code and documentation under the author's direction, the sentence templates
of the training data and, as separate instances that never saw the repository, the test
sentences; no other model is part of the system.

Repository: *filled at submission*.
