# Dataset: intent-conditioned lightpath provisioning

Draft of the dataset card. The full dataset (`data/full/`, not in git) is to be published on the
Hugging Face Hub from the Hack Apertus dataset template; this folder keeps a 50-record sample of
every split in `sample/` and the statistics of the full set in `stats.json`.

## What it is

Prompt/answer pairs for one-shot routing and spectrum assignment in an elastic optical network.
Each record is one lightpath request seen by a provisioning controller: the request, an optional
operator intent in plain English, five candidate paths with their free spectrum, and the answer
of a rule-based teacher that respects the intent.

- Source: generated with the Optical Networking Gym simulator (commit `f7c4491`), preset
  `jocn_benchmark`: nobel-eu topology (28 nodes, 41 links), 5 shortest paths, 320 slots of
  12.5 GHz, bit rates 10/40/100/400 Gb/s, six modulation formats, ASE+NLI quality of transmission.
- No personal data, no human subjects; fully synthetic. City names are those of the public
  nobel-eu reference topology.
- Licence: CDLA-Permissive-2.0.
- Generator: `src/generate.py` in the project repository; deterministic given the seeds.

## Splits

| Split | Records | Contents |
| --- | --- | --- |
| `train` | 12,000 | no intent 4,000; avoid-link, fewest-hops, least-loaded, fewest-slots 1,500 each; avoid-link + fewest-hops and avoid-link + least-loaded 1,000 each. Seeds 101–106. |
| `heldout_indist` | 1,000 | same intents and wording as train, unseen episodes (seeds 107–108) |
| `heldout_paraphrase` | 600 | the four single intents in three paraphrases each that never appear in train |
| `heldout_pairs` | 600 | avoid-link + fewest-slots and fewest-hops + least-loaded, combinations never seen in train |

Loads 150, 210, 270, 330 and 390 Erlang; requests 300–999 of each 1,000-request episode. No
prompt appears twice anywhere, and no generation seed is used in the evaluation.

## Record format

JSON lines, usable directly as a prompt/completion chat dataset:

```json
{"id": "L270-S103-R0457",
 "prompt": [{"role": "system", "content": "You are a lightpath provisioning controller. ..."},
            {"role": "user", "content": "Request: Berlin -> Prague, 100 Gb/s.\nIntent: ...\n..."}],
 "completion": [{"role": "assistant", "content": "path=1 slot=120"}],
 "meta": {"group": "train", "load": 270, "seed": 103, "request_index": 457,
          "intent_key": "I1", "intent": {"ids": ["I1"], "text": "...", "link": ["Berlin", "Munich"],
                                         "paraphrases": [3], "link_form": 0},
          "admissible_paths": [1, 2], "teacher_choice": [1, 120], "no_intent_choice": [0, 12],
          "valid_actions": 1834, "view": {"...": "the structured request the prompt was rendered from"}}}
```

`admissible_paths` are the candidate paths the intent allows (empty: the request must be
rejected); `teacher_choice` is `[path, start slot]` or `null` for reject; `valid_actions` is the
size of the simulator's full action mask; `view` holds everything needed to re-render the prompt
or compute features without the simulator.

## Known properties

See `stats.json` for the numbers. The fewest-hops and fewest-slots teachers answer path 0 in
83 % and 96 % of the training records, because candidates are ordered by length. Pair intents
combine by intersection, which leaves no admissible path in 4–28 % of pair records (the answer
is then `reject`).
