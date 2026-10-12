"""The policy language on a Swiss network: test instructions in four languages with the names an
operator would use (``Genf``, ``Genève``, ``Ginevra``, ``Geneva`` for the node ``Genève``).

The topology is ``data/topologies/swiss.xml`` (24 cities, 33 links along the main corridors,
built from public geography for this project); the names are ``data/topologies/swiss_names.json``.
The sentences are the independently written sources of the third round (``mixed3.sources``),
so a reader trained on the European network is tested here on nodes it never saw, named in a
language's own form, with every clause kind, pair and triple of the earlier sets.

    uv run python src/swiss.py                 # data/instructions/v3_swiss_{en,de,fr,it}.jsonl
    uv run python src/swiss.py --summary       # results/translate/<reader>_swiss.json -> a table

Each sentence is filled FILLS times with random nodes, links and limits of the Swiss network;
for a node, one of the language's forms is drawn at random (the first form is the usual one,
the others are what one also sees: ``Sankt Gallen``, ``Delsberg``, ``Yverdon-les-Bains``).
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import mixed3
from generate import write_jsonl
from spec import Spec, load_topology

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = "swiss"
LANGS = ("en", "de", "fr", "it")
GROUPS = ("atom", "pair", "heldout_pair", "triple", "two_preferences")
FILLS = 2


def names() -> dict[str, dict[str, list[str]]]:
    return json.loads((ROOT / "data" / "topologies" / f"{TOPOLOGY}_names.json").read_text(encoding="utf-8"))[
        "nodes"
    ]


def fill(clauses: tuple[str, ...], topology, rng: random.Random) -> dict:
    """Values for the placeholders, from the topology alone (there is no request here)."""
    links = sorted(tuple(sorted(link)) for link in topology.links)
    fills: dict = {}
    for kind in clauses:
        if kind == "avoid_link":
            a, b = rng.choice(links)
            fills["a"], fills["b"] = (a, b) if rng.random() < 0.5 else (b, a)
        elif kind in ("avoid_node", "via_node"):
            free = [
                n
                for n in topology.nodes
                if n not in (fills.get("c"), fills.get("v"), fills.get("a"), fills.get("b"))
            ]
            fills["c" if kind == "avoid_node" else "v"] = rng.choice(free)
        elif kind == "max_hops":
            fills["n"] = rng.randint(2, 6)
        elif kind == "max_km":
            fills["km"] = 50 * rng.randint(4, 16)
        elif kind == "path_index":
            fills["k"] = rng.randrange(5)
    return fills


def render(text: str, fills: dict, lang: str, table: dict, rng: random.Random) -> str:
    for key, value in fills.items():
        if isinstance(value, str):
            forms = table[value].get(lang) or [value]
            value = forms[0] if rng.random() < 0.7 else rng.choice(forms)
        text = text.replace("{" + key + "}", str(value))
    return text


def build(seed: int = 3) -> dict[str, list[dict]]:
    topology, table = load_topology(TOPOLOGY), names()
    sources = mixed3.sources()
    out: dict[str, list[dict]] = {}
    for lang in LANGS:
        rng, rows, seen = random.Random(f"swiss-{lang}-{seed}"), [], set()
        for group in GROUPS:
            for clauses, text in sources[lang]["grouped"][group]:
                for _ in range(FILLS):
                    fills = fill(tuple(clauses), topology, rng)
                    item = mixed3.Instruction(text="", kind="supported", clauses=tuple(clauses),
                                              fills=tuple(sorted(fills.items())), lang=lang, group=group)  # fmt: skip
                    spec: Spec = mixed3.expressed(item)
                    sentence = render(text, fills, lang, table, rng)
                    if sentence in seen:
                        continue
                    seen.add(sentence)
                    rows.append({"text": sentence, "expect": spec.to_json(), "set": f"v3_swiss_{lang}", "lang": lang,
                                 "kind": group})  # fmt: skip
        out[f"v3_swiss_{lang}"] = rows
    return out


def summary(readers: tuple[str, ...]) -> str:
    """One table: right meaning by language and by kind, per reader, from the score files."""
    lines = ["| Reader | Language | n | Right, % | Applied with another meaning, % | Not applied, % | By kind (right, %) |",
             "|---|---|---|---|---|---|---|"]  # fmt: skip
    for reader in readers:
        path = ROOT / "results" / "translate" / f"{reader}_{TOPOLOGY}.json"
        if not path.exists():
            continue
        groups = json.loads(path.read_text(encoding="utf-8"))["groups"]
        for lang in LANGS:
            total = next((g for g in groups if g["set"] == f"v3_swiss_{lang}" and g["lang"] == "all"), None)
            if not total:
                continue
            kinds = ", ".join(f"{g['kind']} {100 * g['correct'] / g['n']:.0f}" for g in groups
                              if g["set"] == f"v3_swiss_{lang}" and g["lang"] == lang)  # fmt: skip
            n = total["n"]
            lines.append(f"| {reader} | {lang} | {n} | {100 * total['correct'] / n:.1f} | {100 * total['wrong'] / n:.1f} "
                         f"| {100 * total['flagged'] / n:.1f} | {kinds} |")  # fmt: skip
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--readers", nargs="+", default=["translate3_ft_laptop", "translate3_ft2_laptop"])
    args = parser.parse_args()
    if args.summary:
        print(summary(tuple(args.readers)))
    else:
        for name, rows in build().items():
            write_jsonl(ROOT / "data" / "instructions" / f"{name}.jsonl", rows)
            print(f"{name}: {len(rows)} instructions", dict(Counter(r["kind"] for r in rows)))
