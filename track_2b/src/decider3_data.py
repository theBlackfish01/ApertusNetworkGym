"""Training data for the matched decider: the reader's own sentences, as decisions (``data/full3``).

The comparison of translating and deciding was matched only in the first round: there, the decider
and the reader learned from the same 12,000 decisions of four instruction types. From the third
round on, the reader of the routing fields learned the whole policy language from 5,570 sentences
(``data/translate3/s1/train.jsonl``) while the decider kept the four types. This module builds the
decider's side of a matched pair for the policy language:

* the same 12,000 network states as the first decider (``data/full/train.jsonl``, seeds 101 to 106);
  the 4,000 that carried no instruction keep none;
* on the other 8,000, the reader's training sentences, every one of the 5,570 at least once and
  2,430 a second time, each on a state where it is *restrictive*: at least one feasible path
  complies and at least one does not (the rule the test sets were placed by, ``corpora3_tests``);
  a sentence that does not apply (``unsupported``, ``no_instruction``, a place outside the network)
  goes on any state;
* the label is the decision of the rule engine under the sentence's meaning (``spec.choose`` with
  ordered preferences, the rule the evaluator judges by); for a sentence carried in part
  (``rest=more``), under the carried part, which is all the line states; a sentence that does not
  apply gets the decision without an instruction.

The held-out splits for the training curve and for the decision about a second epoch take their
states from ``data/full/heldout_*.jsonl`` (seeds 107 and 108) and their sentences from the
reader's own held-out sets: ``heldout_indist`` (the training templates), ``heldout_paraphrase``
(unseen wording), ``heldout_pairs`` (pairs of clauses absent from training). No test sentence is
used anywhere.

    uv run python src/decider3_data.py      # writes data/full3/{train,heldout_*}.jsonl, stats.json
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from generate import read_jsonl, write_jsonl
from intents import Intent
from prompt import chat_messages, format_choice
from spec import EMPTY, Spec, admissible, choose, load_topology, parse_spec, validate
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "data" / "translate3" / "s1"
STATES = ROOT / "data" / "full"
OUT = ROOT / "data" / "full3"
SCAN = 300  # states tried for one sentence before a non-restrictive one is accepted
TRAIN_WITH_SENTENCE = 8000  # of the 12,000 training states; the other 4,000 carry no instruction
HELDOUT_COPIES = 2  # placements of each held-out sentence
HELDOUT_NONE = 100  # held-out states without an instruction, in heldout_indist


def sentences(split: str, topology) -> list[dict]:
    """The reader's sentences of one split, with the meaning the reader was taught."""
    rows = []
    for record in read_jsonl(READER / f"{split}.jsonl"):
        line = record["completion"][0]["content"]
        spec = validate(parse_spec(line), topology)
        rows.append({"text": record["meta"]["text"], "kind": record["meta"]["kind"], "line": line, "spec": spec})
    return rows


def placement(view: RequestView, spec: Spec) -> str:
    """``restrictive``, ``impossible`` (no feasible path complies) or ``neutral`` for a spec that applies."""
    feasible = [p.index for p in view.paths if p.feasible]
    allowed = admissible(view, spec)
    if not allowed:
        return "impossible" if feasible else "neutral"
    return "restrictive" if len(allowed) < len(feasible) else "neutral"


class Pool:
    """States not used yet, drawn in a fixed random order."""

    def __init__(self, records: list[dict], rng: random.Random) -> None:
        self.records = list(records)
        rng.shuffle(self.records)
        self.views = {r["id"]: RequestView.from_json(r["meta"]["view"]) for r in self.records}
        self.free = list(self.records)

    def take(self, spec: Spec, rng: random.Random) -> tuple[dict, str]:
        """A state for the spec: the first restrictive one among SCAN tries, else an impossible one,
        else any (a spec that does not apply takes the next state)."""
        if not spec.applies:
            return self.free.pop(), "not applied"
        tries = rng.sample(range(len(self.free)), min(SCAN, len(self.free)))
        spare: dict[str, int] = {}
        for i in tries:
            kind = placement(self.views[self.free[i]["id"]], spec)
            if kind == "restrictive":
                return self.free.pop(i), kind
            spare.setdefault(kind, i)
        i = spare.get("impossible", spare.get("neutral", tries[0]))
        kind = "impossible" if "impossible" in spare else "neutral"
        return self.free.pop(i), kind


def record(state: dict, view: RequestView, sentence: dict | None, group: str, number: int) -> dict:
    meta = state["meta"]
    spec = sentence["spec"] if sentence else EMPTY
    meaning = spec if spec.applies else EMPTY
    choice = choose(view, meaning)
    intent = Intent(text=sentence["text"]) if sentence else Intent()
    allowed = list(admissible(view, meaning))
    return {
        "id": f"{state['id']}-d3-{number:05d}",
        "prompt": chat_messages(view, intent),
        "completion": [{"role": "assistant", "content": format_choice(choice)}],
        "meta": {
            **{k: meta[k] for k in ("load", "seed", "request_index", "no_intent_choice", "view")},
            "group": group,
            "intent_key": sentence["kind"] if sentence else "I0",
            "intent": intent.to_json(),
            "admissible_paths": allowed,
            "teacher_choice": list(choice) if choice else None,
            "spec": meaning.to_json(),
            "probe": {"set": f"full3_{group}", "apply": spec.applies, "allowed": allowed,
                      "source": state["id"], "reader_line": sentence["line"] if sentence else "none"},
        },
    }  # fmt: skip


def build() -> dict:
    topology = load_topology("nobel-eu")
    rng = random.Random("decider3")
    stats: dict = {}
    out: dict[str, list[dict]] = {}

    # training: the first decider's 12,000 states
    states = read_jsonl(STATES / "train.jsonl")
    none_states = [s for s in states if s["meta"]["intent_key"] == "I0"]
    pool = Pool([s for s in states if s["meta"]["intent_key"] != "I0"], rng)
    assert len(pool.free) == TRAIN_WITH_SENTENCE, len(pool.free)
    train_sentences = sentences("train", topology)
    order = list(train_sentences)
    rng.shuffle(order)
    order += rng.sample(train_sentences, TRAIN_WITH_SENTENCE - len(train_sentences))  # a second time
    placed, records = Counter(), []
    for number, sentence in enumerate(order):
        state, kind = pool.take(sentence["spec"], rng)
        placed[kind] += 1
        records.append(record(state, pool.views[state["id"]], sentence, "train", number))
    for number, state in enumerate(none_states, start=len(order)):
        view = RequestView.from_json(state["meta"]["view"])
        made = record(state, view, None, "train", number)
        teacher = state["meta"]["teacher_choice"]
        assert made["meta"]["teacher_choice"] == teacher, (state["id"], made["meta"]["teacher_choice"], teacher)
        records.append(made)
    records.sort(key=lambda r: r["id"])
    out["train"] = records
    stats["train"] = {"records": len(records), "with_sentence": len(order), "without": len(none_states),
                      "distinct_sentences": len({s["text"] for s in order}), "placement": dict(placed)}  # fmt: skip

    # held-out: states of seeds 107 and 108, the reader's held-out sentences
    held = Pool([r for name in ("heldout_indist", "heldout_paraphrase", "heldout_pairs")
                 for r in read_jsonl(STATES / f"{name}.jsonl")], rng)  # fmt: skip
    for split in ("heldout_indist", "heldout_paraphrase", "heldout_pairs"):
        items, placed = [], Counter()
        for copy in range(HELDOUT_COPIES):
            for number, sentence in enumerate(sentences(split, topology)):
                state, kind = held.take(sentence["spec"], rng)
                placed[kind] += 1
                items.append(record(state, held.views[state["id"]], sentence, split, copy * 1000 + number))
        if split == "heldout_indist":
            for number in range(HELDOUT_NONE):
                state = held.free.pop()
                items.append(record(state, held.views[state["id"]], None, split, 5000 + number))
        out[split] = sorted(items, key=lambda r: r["id"])
        stats[split] = {"records": len(items), "placement": dict(placed)}

    OUT.mkdir(parents=True, exist_ok=True)
    for split, items in out.items():
        write_jsonl(OUT / f"{split}.jsonl", items)
    train = out["train"]
    stats["labels"] = {
        "reject_share": round(sum(r["completion"][0]["content"] == "reject" for r in train) / len(train), 4),
        "path_of_label": dict(sorted(Counter(r["completion"][0]["content"].split()[0] for r in train).items())),
        "user_message_chars_mean": round(sum(len(r["prompt"][-1]["content"]) for r in train) / len(train)),
        "languages": dict(Counter(r["meta"]["intent_key"].split(":")[0] if ":" in r["meta"]["intent_key"] else "-"
                                  for r in train)),  # fmt: skip
    }
    stats["note"] = ("states: data/full (the first decider's); sentences: data/translate3/s1 (the reader's); "
                     "labels: spec.choose under the reader's line, ordered preferences")  # fmt: skip
    (OUT / "stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    return stats


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, ensure_ascii=False))
