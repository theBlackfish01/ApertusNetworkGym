"""Test sets of the third round, from the independently written sources (``mixed3.sources``).

Every set puts instructions on held-out requests (``data/full/heldout_*.jsonl``, seeds 107-108).
A request is taken for an instruction when the instruction is *restrictive* there: at least one
feasible path complies and at least one does not. That condition looks at the instruction and
the request only, never at what a policy would do, so no policy is favoured or handicapped by
the selection; the tables report instruction-blind baselines on the same requests.

    v3_en v3_de v3_fr v3_it   every sentence of the policy language (one clause, pairs, triples,
                              two preferences) on FILLS requests each; ``intent_key`` is the group
                              of the combination: atom, pair (seen in training), heldout_pair,
                              triple, two_preferences
    v3_new                    the four new types, PER_TYPE requests each
    v3_new_impossible         the three new constraints on requests where no path complies
    v3_partial                one clause the slots carry with one they cannot
    v3_other v3_not v3_faulty instruction rows only (no decision is scored): routing instructions
                              of yet other kinds, text that is no instruction, places outside the
                              network

Probes go to ``data/probes/``, the distinct instructions with the spec they mean to
``data/instructions/`` (what ``translate.py score`` reads).
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import mixed3
from corpora import HELDOUT, TEST_OUTSIDE
from corpora3 import NEW_TYPES
from generate import read_jsonl, write_jsonl
from intents import Intent
from prompt import chat_messages, format_choice
from spec import Spec, Topology
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]
FILLS, PER_TYPE, PER_IMPOSSIBLE, PER_PARTIAL, FAULTY = 4, 200, 70, 25, 150
SCAN = 300  # requests tried for one instruction before a non-restrictive one is accepted
GROUPS = ("atom", "pair", "heldout_pair", "triple", "two_preferences")


def probe3(item: dict, instruction: mixed3.Instruction, name: str) -> dict:
    """A held-out request with an instruction of the third round and the paths that comply."""
    meta = item["meta"]
    view = RequestView.from_json(meta["view"])
    allowed = list(mixed3.allowed(view, instruction))
    choice = mixed3.oracle(view, instruction)
    plain = tuple(meta["no_intent_choice"]) if meta["no_intent_choice"] else None
    intent = Intent(text=instruction.text)
    return {
        "id": f"{item['id']}-{name}-{instruction.key}",
        "prompt": chat_messages(view, intent),
        "completion": [{"role": "assistant", "content": format_choice(choice)}],
        "meta": {
            **{k: meta[k] for k in ("load", "seed", "request_index", "no_intent_choice", "view")},
            "group": name, "intent_key": instruction.key, "intent": intent.to_json(),
            "admissible_paths": allowed, "teacher_choice": list(choice) if choice else None,
            "spec": mixed3.expected(instruction).to_json(),
            "probe": {"set": name, "lang": instruction.lang, "apply": True, "allowed": allowed,
                      "source": item["id"], "clauses": list(instruction.clauses),
                      # whether the decision without an instruction breaks this one
                      "binding": not mixed3.respected(view, instruction, plain)},
        },
    }  # fmt: skip


def place(clauses: tuple, text: str, lang: str, kind: str, pool: list[dict], rng: random.Random, count: int,
          *, impossible: bool = False) -> list[mixed3.Instruction | tuple]:  # fmt: skip
    """``count`` requests on which the sentence is restrictive (or, with ``impossible``, cannot be met)."""
    found, spare = [], []
    for item in rng.sample(pool, len(pool))[:SCAN]:
        view = RequestView.from_json(item["meta"]["view"])
        made = mixed3.instance(clauses, text, lang, view, rng, kind=kind, meetable=not impossible, tries=4)
        if made is None:
            continue
        feasible = sum(p.feasible for p in view.paths)
        if impossible or 0 < len(mixed3.allowed(view, made)) < feasible:
            found.append((item, made))
        elif len(spare) < count:
            spare.append((item, made))
        if len(found) == count:
            break
    return (found + spare)[:count]


def row3(record: dict) -> dict:
    meta = record["meta"]
    return {"text": meta["intent"]["text"], "expect": meta["spec"], "set": meta["probe"]["set"],
            "lang": meta["probe"]["lang"], "kind": meta["intent_key"]}  # fmt: skip


def build_tests(topology: Topology, data: Path = ROOT / "data") -> None:
    pool = sorted(
        (r for name in HELDOUT for r in read_jsonl(data / "full" / f"{name}.jsonl")), key=lambda r: r["id"]
    )
    sources = mixed3.sources()
    english = sources["en"]
    probes: dict[str, list[dict]] = {}
    for lang in ("en", "de", "fr", "it"):
        name, rng = f"v3_{lang}", random.Random(f"v3-{lang}")
        probes[name] = [
            probe3(item, made, name)
            for group in GROUPS
            for clauses, text in sources[lang]["grouped"][group]
            for item, made in place(clauses, text, lang, "supported", pool, rng, FILLS)
        ]
    rng = random.Random("v3-new")
    probes["v3_new"] = [
        probe3(item, made, "v3_new")
        for kind in NEW_TYPES
        for item, made in _spread(english["new_types"][kind], (kind,), "new", pool, rng, PER_TYPE)
    ]
    probes["v3_new_impossible"] = [
        probe3(item, made, "v3_new_impossible")
        for kind in ("min_mod", "not_first", "min_free")
        for item, made in _spread(english["new_types"][kind], (kind,), "new", pool, rng, PER_IMPOSSIBLE, True)
    ]
    rng = random.Random("v3-partial")
    probes["v3_partial"] = [
        probe3(item, made, "v3_partial")
        for entry in english["partial"]
        for item, made in place(
            tuple(entry["clauses"]), entry["text"], "en", "partial", pool, rng, PER_PARTIAL
        )
    ]
    for name, records in probes.items():
        write_jsonl(data / "probes" / f"{name}.jsonl", records)
        rows = {r["text"]: r for r in map(row3, records)}
        write_jsonl(data / "instructions" / f"{name}.jsonl", [rows[t] for t in sorted(rows)])
        kinds = Counter(r["meta"]["intent_key"] for r in records)
        binding = sum(r["meta"]["probe"]["binding"] for r in records)
        print(f"{name:18s} {len(records):5d} probes ({binding} binding), {len(rows):5d} distinct instructions  "
              f"{dict(sorted(kinds.items()))}")  # fmt: skip

    # Rows without a scored decision.
    rng = random.Random("v3-rows")
    rows = {
        "v3_other": [{"text": text, "expect": Spec(status="unsupported").to_json(), "set": "v3_other",
                      "lang": "en", "kind": "other_routing"} for text in english["other_routing"]],
        "v3_not": [{"text": text, "expect": Spec(status="no_instruction").to_json(), "set": "v3_not",
                    "lang": "en", "kind": "not_instruction"} for text in english["not_instruction"]],
        "v3_faulty": [],
    }  # fmt: skip
    named = [s for s in english["grouped"]["atom"] if s[0][0] in mixed3.NAMED]
    seen = set()
    while len(rows["v3_faulty"]) < FAULTY:
        (kind,), text = rng.choice(named)
        outside = rng.choice(TEST_OUTSIDE)
        if kind == "avoid_link":
            ends = [rng.choice(topology.nodes), outside]
            rng.shuffle(ends)
            fills = {"a": ends[0], "b": ends[1]}
        else:
            fills = {"c" if kind == "avoid_node" else "v": outside}
        filled = mixed3.render(text, fills, "en")
        if filled not in seen:
            seen.add(filled)
            rows["v3_faulty"].append({"text": filled, "expect": Spec(status="unresolved").to_json(),
                                      "set": "v3_faulty", "lang": "en", "kind": f"faulty_{kind}"})  # fmt: skip
    for name, items in rows.items():
        write_jsonl(data / "instructions" / f"{name}.jsonl", items)
        print(f"{name:18s} {len(items):5d} instructions (rows only)")


def _spread(sentences: list[str], clauses: tuple, kind: str, pool: list[dict], rng: random.Random, count: int,
            impossible: bool = False) -> list:  # fmt: skip
    """``count`` requests for one clause kind, spread evenly over its sentences."""
    per = -(-count // len(sentences))
    out = [pair for text in sentences
           for pair in place(clauses, text, "en", kind, pool, rng, per, impossible=impossible)]  # fmt: skip
    rng.shuffle(out)
    return out[:count]


if __name__ == "__main__":
    from spec import load_topology

    build_tests(load_topology("nobel-eu"))
