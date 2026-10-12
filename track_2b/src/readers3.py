"""What each reader of the third format does with every test instruction, and what a second reader adds.

Reads the instruction files (``text``, ``expect``, ``set``, ``lang``, ``kind``) and the readers'
answer caches; needs no model. For every reader and set it counts, per instruction:

    should be applied (expect is a spec):  right | flagged (not applied, visible) | silent (applied
                                           with another meaning)
    carried in part (expect has rest):     right | part_only (the carried part is right, the rest
                                           is not marked: dropped silently) | handed_on (called
                                           unsupported: the decider gets it without a guard) |
                                           silent (anything else that is applied) | flagged
    must not be applied:                   right (the expected refusal) | other_refusal | silent

and for every ordered pair of readers (first decides, second is the check) what asking the
operator on disagreement does to the first reader's silent errors, and what it costs.

    uv run python src/readers3.py                      # results/design/readers3.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from spec import Spec, load_topology, parse_spec, validate
from translate import format_version, messages, read_rows

ROOT = Path(__file__).resolve().parents[1]
READERS = ("translate3_ft", "translate3_ft2", "translate3_few", "translate3_few70", "translate3_ft_laptop")
SETS = ("v3_en", "v3_de", "v3_fr", "v3_it", "v3_new", "v3_new_impossible", "v3_partial", "v3_other", "v3_not",
        "v3_faulty", "independent", "de_ind", "fr_ind", "it_ind", "gsw", "noisy", "operations_mix3",
        "owner")  # fmt: skip


class Answers:
    """A reader's cached answer lines, looked up by instruction text."""

    def __init__(self, name: str, topology: str = "nobel-eu") -> None:
        self.name, self.topology = name, load_topology(topology)
        self.few, self.version = "_few" in name, format_version(name)
        path = ROOT / "results" / "cache" / f"{name}.jsonl"
        self.cache = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self.cache[entry["key"]] = entry["answer"]

    def spec(self, text: str) -> Spec | None:
        chat = messages(text, self.topology, self.few, self.version)
        line = self.cache.get(hashlib.sha256(json.dumps(chat, sort_keys=True).encode()).hexdigest())
        return None if line is None else validate(parse_spec(line), self.topology)


def outcome(expect: Spec, got: Spec) -> str:
    """One of the outcomes listed in the module docstring."""
    if not expect.applies:
        if got.applies:
            return "silent"
        return "right" if got.status == expect.status else "other_refusal"
    if got.meaning() == expect.meaning():
        return "right"
    if expect.rest:
        if got.status == "unsupported":
            return "handed_on"
        if got.applies and replace(got, rest=True).meaning() == expect.meaning():
            return "part_only"
    return "silent" if got.applies else "flagged"


def analyse(rows: list[dict], readers: dict[str, Answers]) -> dict:
    single: dict = defaultdict(Counter)  # (reader, set, lang, kind) -> outcomes
    pairs: dict = defaultdict(Counter)  # (first, second, set, lang) -> what asking does
    missing: Counter = Counter()
    for row in rows:
        expect = Spec.from_json(row["expect"])
        got = {name: answers.spec(row["text"]) for name, answers in readers.items()}
        for name, spec in got.items():
            if spec is None:
                missing[(name, row["set"])] += 1
                continue
            for key in (
                (name, row["set"], "all", "all"),
                (name, row["set"], row.get("lang", "en"), row["kind"]),
            ):
                single[key]["n"] += 1
                single[key][outcome(expect, spec)] += 1
        for first, a in got.items():
            for second, b in got.items():
                if first == second or a is None or b is None:
                    continue
                result, asked = outcome(expect, a), a.meaning() != b.meaning()
                counter = pairs[(first, second, row["set"], "all")]
                counter["n"] += 1
                counter["asked"] += asked
                counter["wrong_alone"] += result != "right"
                counter["silent_alone"] += result in ("silent", "part_only")
                counter["silent_left"] += result in ("silent", "part_only") and not asked
                counter["wrong_left"] += result != "right" and not asked
                counter["right_but_asked"] += result == "right" and asked
    return {
        "readers": [{"reader": r, "set": s, "lang": lang, "kind": k, **dict(c)} for (r, s, lang, k), c in sorted(single.items())],
        "pairs": [{"first": a, "second": b, "set": s, **dict(c)} for (a, b, s, _), c in sorted(pairs.items())],
        "missing": [{"reader": r, "set": s, "instructions": n} for (r, s), n in sorted(missing.items())],
    }  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--readers", nargs="+", default=list(READERS))
    parser.add_argument("--sets", nargs="+", default=list(SETS))
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "design" / "readers3.json")
    args = parser.parse_args()
    files = {"operations_mix3": "mix3"}
    paths = [ROOT / "data" / "instructions" / f"{files.get(name, name)}.jsonl" for name in args.sets]
    rows = read_rows([path for path in paths if path.exists()])
    readers = {name: answers for name in args.readers if (answers := Answers(name)).cache}
    result = analyse(rows, readers)
    result["metadata"] = {"command": "src/readers3.py", "readers": list(readers), "instructions": len(rows),
                          "finished_utc": datetime.now(UTC).isoformat()}  # fmt: skip
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
    for name in readers:
        got = [r for r in result["readers"] if r["reader"] == name and r["lang"] == "all"]
        print(name, " ".join(f"{r['set']}={100 * r.get('right', 0) / r['n']:.1f}%" for r in got))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
