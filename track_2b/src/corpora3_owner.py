"""Instructions written by people as test sets: the owner's and a contributor's.

One instruction per line, a bar, then what the writer meant in the words the file's header lists;
a contributor's line may end with a second bar and its language (``| de``). Each line becomes an
instruction row with the spec it means (``data/instructions/<set>.jsonl``, what
``translate.py parse`` and ``readers3.py`` read). ``kind`` says how the instruction relates to the
readers' training: ``atom`` one clause, ``trained`` a combination of clause kinds that occurs in
training, ``heldout`` one that was held out, ``new`` one in neither list; ``other_routing`` and
``not_instruction`` as in the other sets. A standing policy (a scope: ``only rate N``, ``only from
A``, ``only to A``; a lifetime: ``for N hours``, ``until withdrawn``) goes to the set
``<name>_standing``, with the kind of its scope and lifetime phrases (``rate``, ``from``, ``to``,
``hours``, ``open``, joined by ``+``) as the fourth-format sets have them; only a reader of the
fourth format can write it. ``lang`` is the line's own language field, or for the owner's lines
``ur`` for Urdu in Latin script (told by a few function words), otherwise ``en``.

    uv run python src/corpora3_owner.py            # the rows
    uv run python src/corpora3_owner.py --score    # what the readers on the laptop made of them

``--score`` reads the answer caches (``results/cache/<reader>.jsonl``, filled by
``translate.py parse``) and writes ``results/design/<source>.json`` per source: every line with
what each reader understood, the outcome as ``readers3.outcome`` names it, and whether a second
reader would have made the system ask.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from corpora3 import HELDOUT, PREF, TRAINED, signature
from generate import write_jsonl
from spec import PREFERENCES3, Spec, Topology, format_spec, load_topology, validate

ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = ROOT / "data" / "instructions"
SOURCES = {
    "owner": INSTRUCTIONS / "owner_source.txt",
    "contributor1": INSTRUCTIONS / "contributor1_source.txt",
}
SOURCE = SOURCES["owner"]
# the laptop readers (4-bit base, llama.cpp), then the fourth-format reader at 16 bits (an A100 job)
READERS = (
    "translate3_ft_laptop",
    "translate3_ft2_laptop",
    "translate3_few_laptop",
    "translate4_ft_laptop",
    "translate4_ft",
)
STANDING_READERS = ("translate4_ft_laptop", "translate4_ft")  # the only format with scope and lifetime
URDU = {"se", "hai", "mat", "nahi", "nahee", "aur", "kar", "lena", "rakho", "liken", "lekin", "baqi"}


def _node(name: str, topology: Topology) -> str:
    found = [node for node in topology.nodes if node.lower() == name.strip().lower()]
    if not found:
        raise ValueError(f"{name!r} is not a node of the network")
    return found[0]


def meant(text: str, topology: Topology) -> tuple[Spec, tuple[str, ...], tuple[str, ...]]:
    """The spec of what stands after the bar, the kinds of its clauses and of its standing phrases."""
    text = text.strip()
    if text == "none":
        return Spec(status="no_instruction"), (), ()
    if text.startswith("other:"):
        return Spec(status="unsupported"), (), ()
    slots: dict = {"avoid": [], "nodes": [], "via": [], "prefer": []}
    kinds, standing = [], []
    for part in (p.strip() for p in text.split(",")):
        word, _, value = part.partition(" ")
        if word == "avoid" and "-" in value:
            slots["avoid"].append(tuple(_node(n, topology) for n in value.split("-")))
            kinds.append("avoid_link")
        elif word == "avoid":
            slots["nodes"].append(_node(value, topology))
            kinds.append("avoid_node")
        elif word == "via":
            slots["via"].append(_node(value, topology))
            kinds.append("via_node")
        elif word == "max" and value.endswith(" hops"):
            slots["max_hops"] = int(value.split()[0])
            kinds.append("max_hops")
        elif word == "max" and value.endswith(" km"):
            slots["max_km"] = int(value.split()[0])
            kinds.append("max_km")
        elif word == "candidate":
            slots["path"] = int(value)
            kinds.append("path_index")
        elif word in ("prefer", "then") and value in PREFERENCES3:
            slots["prefer"].append(value)
            kinds.append(PREF)
        elif word == "only" and value.startswith("rate "):
            slots["scope"] = f"rate:{int(value.split()[1])}"
            standing.append("rate")
        elif word == "only" and value.startswith(("from ", "to ")):
            side, city = value.split(" ", 1)
            slots["scope"] = f"{side}:{_node(city, topology)}"
            standing.append(side)
        elif word == "for" and value.endswith((" hours", " hour")):
            slots["until"] = int(value.split()[0])
            standing.append("hours")
        elif part == "until withdrawn":
            standing.append("open")  # the format's default lifetime: no field is written
        else:
            raise ValueError(f"cannot read {part!r} in {text!r}")
    spec = validate(Spec(**{k: tuple(v) if isinstance(v, list) else v for k, v in slots.items()}), topology)
    if not spec.applies:
        raise ValueError(f"{text!r} names a link that is not in the network")
    return spec, tuple(kinds), tuple(standing)


def kind_of(spec: Spec, kinds: tuple[str, ...]) -> str:
    if not spec.applies:
        return "not_instruction" if spec.status == "no_instruction" else "other_routing"
    if len(kinds) == 1:
        return "atom"
    combination = signature(kinds)
    return "trained" if combination in TRAINED else "heldout" if combination in HELDOUT else "new"


def build(topology: Topology, name: str = "owner", source: Path | None = None) -> list[dict]:
    rows = []
    for line in (source or SOURCES[name]).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = [f.strip() for f in line.split(" | ")]
        if len(fields) not in (2, 3):
            raise ValueError(f"expected 'text | meaning' or 'text | meaning | language' in {line!r}")
        text, after = fields[0], fields[1]
        spec, kinds, standing = meant(after, topology)
        if len(fields) == 3:
            lang = fields[2].lower()
        else:
            lang = "ur" if URDU & set(text.lower().split()) else "en"
        row = {"text": text, "expect": spec.to_json(), "set": f"{name}_standing" if standing else name, "lang": lang,
               "kind": "+".join(standing) if standing else kind_of(spec, kinds)}  # fmt: skip
        if standing:
            row["group"] = kind_of(spec, kinds)  # the routing part, as in the fourth-format sets
        rows.append(row)
    return rows


def score(rows: list[dict], readers: tuple[str, ...] = READERS) -> dict:
    from readers3 import Answers, outcome

    answers = {name: Answers(name) for name in readers}
    first, lines = readers[0], []
    counts: dict[str, Counter] = {name: Counter() for name in readers}
    asked: dict[str, Counter] = {name: Counter() for name in readers[1:3]}  # the two checks of reader 1
    for row in rows:
        standing = row["set"].endswith("_standing")
        names = [n for n in readers if not standing or n in STANDING_READERS]
        expect = Spec.from_json(row["expect"])
        got = {name: answers[name].spec(row["text"]) for name in names}
        if any(spec is None for spec in got.values()):
            raise SystemExit(f"no cached answer for {row['text']!r}")
        result = {name: outcome(expect, spec) for name, spec in got.items()}
        line = {"text": row["text"], "set": row["set"], "lang": row["lang"], "kind": row["kind"],
                "expect": format_spec(expect, 4 if standing else 3) if expect.applies else expect.status}  # fmt: skip
        for name, spec in got.items():
            line[name] = {
                "answer": format_spec(spec, 4 if name.startswith("translate4") else 3)
                if spec.applies
                else spec.status,
                "outcome": result[name],
            }
            for group in ("all", f"set:{row['set']}", f"lang:{row['lang']}", f"kind:{row['kind']}"):
                counts[name][(group, "n")] += 1
                counts[name][(group, result[name])] += 1
        if not standing:
            for name, tally in asked.items():
                differs = got[first].meaning() != got[name].meaning()
                line[name]["asked"] = differs
                tally["asked"] += differs
                tally["wrong_alone"] += result[first] != "right"
                tally["wrong_left"] += result[first] != "right" and not differs
                tally["right_but_asked"] += result[first] == "right" and differs
        lines.append(line)
    in_language = sum(1 for r in rows if not r["set"].endswith("_standing"))
    return {
        "lines": lines,
        "readers": [{"reader": name, "group": group, **{k: v for (g, k), v in sorted(c.items()) if g == group}}
                    for name, c in counts.items() for group in sorted({g for g, _ in c})],
        "pairs": [{"first": first, "second": name, "n": in_language, **dict(c)} for name, c in asked.items()],
        "metadata": {"command": "src/corpora3_owner.py --score", "instructions": len(rows),
                     "note": "laptop readers (4-bit base, llama.cpp) and translate4_ft at 16 bits; standing policies are read by the fourth-format reader only"},
    }  # fmt: skip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--score", action="store_true", help="write results/design/<source>.json from the caches"
    )
    args = parser.parse_args()
    topology = load_topology("nobel-eu")
    for name, source in SOURCES.items():
        made = build(topology, name)
        if not args.score:
            for set_name in sorted({r["set"] for r in made}):
                part = [r for r in made if r["set"] == set_name]
                write_jsonl(INSTRUCTIONS / f"{set_name}.jsonl", part)
                print(
                    f"{set_name}: {len(part)} instructions",
                    dict(sorted(Counter((r["lang"], r["kind"]) for r in part).items())),
                )
            continue
        scored = score(made) | {}
        scored["metadata"]["source"] = source.name
        out = ROOT / "results" / "design" / f"{name}.json"
        out.write_text(json.dumps(scored, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
        for entry in scored["lines"]:
            print(f"[{entry['set']} {entry['lang']} {entry['kind']}] {entry['text']}")
            print(f"    meant   {entry['expect']}")
            for reader in READERS:
                if reader in entry:
                    mark = " (asked)" if entry[reader].get("asked") else ""
                    print(f"    {reader:22s} {entry[reader]['outcome']:13s} {entry[reader]['answer']}{mark}")
        for entry in scored["readers"]:
            if entry["group"] in ("all", f"set:{name}", f"set:{name}_standing"):
                print(entry)
        for entry in scored["pairs"]:
            print(entry)
        print(f"wrote {out}")
