"""Self-consistency as a third check: does disagreement among samples of reader 1 predict its errors?

For every test instruction, reader 1 answered once greedily (``translate3_ft_laptop``) and
several times at temperature 0.8 (``translate3_ft_laptop_s1`` ...). A sample that differs in
meaning from the greedy answer is a sign of doubt. This script compares three signals that could
make the system ask the operator: a second reader of the same recipe (``translate3_ft2_laptop``),
a larger untrained model (``translate3_few70b``, answered in a job), and the samples (ask when at
least ``t`` of them differ). For each signal: the share of instructions asked about, the errors of
the greedy reading that were caught, the errors left unasked, and the questions put although the
greedy reading was right. Written to ``results/design/consistency3.json``.

    uv run python src/consistency3.py
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from readers3 import Answers, outcome
from spec import Spec
from translate import read_rows

ROOT = Path(__file__).resolve().parents[1]
GREEDY = "translate3_ft_laptop"
SAMPLES = tuple(f"translate3_ft_laptop_s{k}" for k in range(1, 6))
CHECKS = {"translate3_ft2_laptop": "reader 2 (same recipe)", "translate3_few70b": "untrained 70B"}
GROUPS = {
    "policy language": ("v3_en", "v3_de", "v3_fr", "v3_it"),
    "types never shown": ("v3_new",),
    "carried in part": ("v3_partial",),
    "other routing": ("v3_other",),
    "no instruction": ("v3_not",),
    "place outside": ("v3_faulty",),
}


def analyse(rows: list[dict], greedy: Answers, samples: list[Answers], checks: dict[str, Answers]) -> dict:
    out: dict = {"signals": [], "samples": len(samples)}
    tallies: dict = defaultdict(Counter)  # (group, signal) -> counts
    for row in rows:
        group = next((g for g, sets in GROUPS.items() if row["set"] in sets), None)
        if group is None:
            continue
        expect, got = Spec.from_json(row["expect"]), greedy.spec(row["text"])
        if got is None:
            continue
        result = outcome(expect, got)
        wrong, silent = result != "right", result in ("silent", "part_only")
        drawn = [s.spec(row["text"]) for s in samples]
        drawn = [d for d in drawn if d is not None]
        differing = sum(d.meaning() != got.meaning() for d in drawn)
        signals = {}
        for name, answers in checks.items():
            other = answers.spec(row["text"])
            if other is not None:
                signals[name] = other.meaning() != got.meaning()
        if drawn:
            for t in range(1, len(drawn) + 1):
                signals[f"samples>={t}"] = differing >= t
            for name, answers in checks.items():
                if name in signals:
                    signals[f"{name}+samples>=1"] = signals[name] or differing >= 1
        for name, asked in signals.items():
            for g in (group, "all"):
                c = tallies[(g, name)]
                c["n"] += 1
                c["wrong"] += wrong
                c["silent"] += silent
                c["asked"] += asked
                c["wrong_caught"] += wrong and asked
                c["wrong_left"] += wrong and not asked
                c["silent_left"] += silent and not asked
                c["right_asked"] += (not wrong) and asked
    out["signals"] = [{"group": g, "signal": s, **dict(c)} for (g, s), c in sorted(tallies.items())]
    return out


def table(result: dict) -> str:
    lines = ["| Instructions | Signal that makes the system ask | n | Asked, % | Not right alone, % | Not right and not asked, % | Applied wrongly and not asked, % | Asked although right, % |",
             "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    names = {**{k: v for k, v in CHECKS.items()}, **{f"samples>={t}": f"{t}+ of {result['samples']} samples differ" for t in range(1, 6)},
             **{f"{k}+samples>=1": f"{v}, or a sample differs" for k, v in CHECKS.items()}}  # fmt: skip
    for entry in result["signals"]:
        n = entry["n"]
        if entry["group"] not in ("policy language", "types never shown", "carried in part"):
            continue
        lines.append(f"| {entry['group']} | {names.get(entry['signal'], entry['signal'])} | {n} | {100 * entry['asked'] / n:.1f} "
                     f"| {100 * entry['wrong'] / n:.1f} | {100 * entry['wrong_left'] / n:.1f} | {100 * entry['silent_left'] / n:.1f} "
                     f"| {100 * entry['right_asked'] / n:.1f} |")  # fmt: skip
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "design" / "consistency3.json")
    args = parser.parse_args()
    sets = [s for group in GROUPS.values() for s in group]
    rows = read_rows([ROOT / "data" / "instructions" / f"{s}.jsonl" for s in sets])
    greedy = Answers(GREEDY)
    samples = [a for name in SAMPLES if (a := Answers(name)).cache]
    checks = {name: a for name in CHECKS if (a := Answers(name)).cache}
    result = analyse(rows, greedy, samples, checks)
    result["metadata"] = {"command": "src/consistency3.py", "greedy": GREEDY, "samples": [a.name for a in samples],
                          "checks": list(checks), "instructions": len(rows)}  # fmt: skip
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
    print(table(result))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
