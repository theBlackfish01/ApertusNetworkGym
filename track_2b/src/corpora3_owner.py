"""The owner's own instructions as a test set (``data/instructions/owner_source.txt``).

One instruction per line, a bar, then what the owner meant in the words the file's header lists.
Each line becomes an instruction row with the spec it means (``data/instructions/owner.jsonl``,
what ``translate.py score`` and ``readers3.py`` read). ``kind`` says how the instruction relates
to the readers' training: ``atom`` one clause, ``trained`` a combination of clause kinds that
occurs in training, ``heldout`` one that was held out, ``new`` one in neither list;
``other_routing`` and ``not_instruction`` as in the other sets. ``lang`` is ``ur`` for Urdu in
Latin script (told by a few function words), otherwise ``en``.

    uv run python src/corpora3_owner.py            # the rows
    uv run python src/corpora3_owner.py --score    # what the readers on the laptop made of them

``--score`` reads the answer caches (``results/cache/<reader>.jsonl``, filled by
``translate.py parse``) and writes ``results/design/owner.json``: every line with what each
reader understood, the outcome as ``readers3.outcome`` names it, and whether a second reader
would have made the system ask.
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
SOURCE = ROOT / "data" / "instructions" / "owner_source.txt"
READERS = ("translate3_ft_laptop", "translate3_ft2_laptop", "translate3_few_laptop")  # first, then the checks
URDU = {"se", "hai", "mat", "nahi", "nahee", "aur", "kar", "lena", "rakho", "liken", "lekin", "baqi"}


def _node(name: str, topology: Topology) -> str:
    found = [node for node in topology.nodes if node.lower() == name.strip().lower()]
    if not found:
        raise ValueError(f"{name!r} is not a node of the network")
    return found[0]


def meant(text: str, topology: Topology) -> tuple[Spec, tuple[str, ...]]:
    """The spec of what stands after the bar, and the kinds of its clauses."""
    text = text.strip()
    if text == "none":
        return Spec(status="no_instruction"), ()
    if text.startswith("other:"):
        return Spec(status="unsupported"), ()
    slots: dict = {"avoid": [], "nodes": [], "via": [], "prefer": []}
    kinds = []
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
        else:
            raise ValueError(f"cannot read {part!r} in {text!r}")
    spec = validate(Spec(**{k: tuple(v) if isinstance(v, list) else v for k, v in slots.items()}), topology)
    if not spec.applies:
        raise ValueError(f"{text!r} names a link that is not in the network")
    return spec, tuple(kinds)


def kind_of(spec: Spec, kinds: tuple[str, ...]) -> str:
    if not spec.applies:
        return "not_instruction" if spec.status == "no_instruction" else "other_routing"
    if len(kinds) == 1:
        return "atom"
    combination = signature(kinds)
    return "trained" if combination in TRAINED else "heldout" if combination in HELDOUT else "new"


def build(topology: Topology, source: Path = SOURCE) -> list[dict]:
    rows = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        text, bar, after = line.rpartition(" | ")
        if not bar:
            raise ValueError(f"no ' | ' in {line!r}")
        spec, kinds = meant(after, topology)
        lang = "ur" if URDU & set(text.lower().split()) else "en"
        rows.append({"text": text.strip(), "expect": spec.to_json(), "set": "owner", "lang": lang,
                     "kind": kind_of(spec, kinds)})  # fmt: skip
    return rows


def score(rows: list[dict], readers: tuple[str, ...] = READERS) -> dict:
    from readers3 import Answers, outcome

    answers = {name: Answers(name) for name in readers}
    first, lines = readers[0], []
    counts: dict[str, Counter] = {name: Counter() for name in readers}
    asked: dict[str, Counter] = {name: Counter() for name in readers[1:]}
    for row in rows:
        expect = Spec.from_json(row["expect"])
        got = {name: answers[name].spec(row["text"]) for name in readers}
        if any(spec is None for spec in got.values()):
            raise SystemExit(f"no cached answer for {row['text']!r}")
        result = {name: outcome(expect, spec) for name, spec in got.items()}
        line = {"text": row["text"], "lang": row["lang"], "kind": row["kind"],
                "expect": format_spec(expect, 3) if expect.applies else expect.status}  # fmt: skip
        for name, spec in got.items():
            line[name] = {
                "answer": format_spec(spec, 3) if spec.applies else spec.status,
                "outcome": result[name],
            }
            for group in ("all", row["lang"], row["kind"]):
                counts[name][(group, "n")] += 1
                counts[name][(group, result[name])] += 1
        for name in readers[1:]:
            differs = got[first].meaning() != got[name].meaning()
            line[name]["asked"] = differs
            asked[name]["asked"] += differs
            asked[name]["wrong_alone"] += result[first] != "right"
            asked[name]["wrong_left"] += result[first] != "right" and not differs
            asked[name]["right_but_asked"] += result[first] == "right" and differs
        lines.append(line)
    return {
        "lines": lines,
        "readers": [{"reader": name, "group": group, **{k: v for (g, k), v in sorted(c.items()) if g == group}}
                    for name, c in counts.items() for group in sorted({g for g, _ in c})],
        "pairs": [{"first": first, "second": name, "n": len(rows), **dict(c)} for name, c in asked.items()],
        "metadata": {"command": "src/corpora3_owner.py --score", "source": SOURCE.name, "instructions": len(rows)},
    }  # fmt: skip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--score", action="store_true", help="write results/design/owner.json from the caches"
    )
    args = parser.parse_args()
    made = build(load_topology("nobel-eu"))
    if not args.score:
        write_jsonl(ROOT / "data" / "instructions" / "owner.jsonl", made)
        print(
            f"owner: {len(made)} instructions",
            dict(sorted(Counter((r["lang"], r["kind"]) for r in made).items())),
        )
    else:
        scored = score(made)
        out = ROOT / "results" / "design" / "owner.json"
        out.write_text(json.dumps(scored, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
        for entry in scored["lines"]:
            print(f"[{entry['lang']} {entry['kind']}] {entry['text']}")
            print(f"    meant   {entry['expect']}")
            for name in READERS:
                mark = " (asked)" if entry[name].get("asked") else ""
                print(f"    {name:22s} {entry[name]['outcome']:13s} {entry[name]['answer']}{mark}")
        for entry in scored["readers"]:
            if entry["group"] == "all":
                print(entry)
        for entry in scored["pairs"]:
            print(entry)
        print(f"wrote {out}")
