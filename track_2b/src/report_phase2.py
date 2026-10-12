"""Tables of the second round (stronger translator, hybrid); writes ``results/tables/phase2.md``.

Sources: ``results/translate/`` (translation accuracy), ``results/offline/*_probes*.json`` (decisions on
the probe sets) and ``results/eval/`` (closed loop). Nothing is computed that is not in those files; a
missing file gives a "–".

    uv run python src/report_phase2.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATORS = {
    "translate_few": "First translator, 7 examples",
    "translate_ft": "First translator, fine-tuned",
    "translate2_few": "Second translator, 11 examples",
    "translate2_ft": "Second translator, fine-tuned",
}
POLICIES = {
    "apertus_ft_probes": "Decider alone",
    "translate_ft_probes": "First translator, fine-tuned",
    "translate2_few_probes": "Second translator, 11 examples",
    "translate2_ft_probes": "Second translator, fine-tuned",
    "hybrid2_few_probes": "Hybrid: second translator (11 examples), then decider",
    "hybrid2_ft_probes": "Hybrid: second translator (fine-tuned), then decider",
}
TEMPLATE_SETS = ("heldout_indist", "heldout_paraphrase", "heldout_pairs")
SETS = {
    "templates": "Our wording",
    "independent": "Independent wording",
    "de": "German †",
    "fr": "French †",
    "it": "Italian †",
    "de_ind": "German, native",
    "fr_ind": "French, native",
    "it_ind": "Italian, native",
    "gsw": "Swiss German",
    "noisy": "Misspelt",
    "germany50": "Other topology",
}
TYPES = {"via_node": "Pass through a node", "avoid_node": "Avoid a node", "max_hops": "Hop limit",
         "max_km": "Length limit", "shortest_km": "Shortest in km", "path_index": "A given candidate",
         "all": "All six"}  # fmt: skip
CONDITIONS = {"I1": "Avoid link", "I2": "Fewest hops", "I3": "Least loaded", "I4": "Fewest slots",
              "mixed_heldout_paraphrases": "Unseen wording", "heldout_pairs": "Pairs"}  # fmt: skip
CLOSED = {"apertus_ft": "Decider", "translate_ft": "First translator, fine-tuned",
          "translate2_ft": "Second translator, fine-tuned"}  # fmt: skip


def read(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(part: float, whole: float, decimals: int = 1) -> str:
    return "–" if not whole else f"{100 * part / whole:.{decimals}f}"


def groups(results: Path, name: str) -> dict[tuple[str, str], dict]:
    """``(set, kind) -> counts`` for one translator; the held-out dataset splits are pooled as ``templates``."""
    out: dict[tuple[str, str], dict] = {}
    for suffix in ("", "_germany50"):
        for group in (read(results / "translate" / f"{name}{suffix}.json") or {}).get("groups", []):
            name_of_set = "templates" if group["set"] in TEMPLATE_SETS else group["set"]
            kind = "all" if group["lang"] == "all" else group["kind"]
            total = out.setdefault(
                (name_of_set, kind),
                dict.fromkeys(("n", "correct", "flagged", "wrong", "applied", "same_status"), 0),
            )
            for field in total:
                total[field] += group[field]
    return out


def splits(results: Path, name: str) -> dict:
    """Offline scores of one policy over all its probe files, plus the held-out splits pooled as ``templates``."""
    out: dict = {}
    for suffix in ("", "2", "_germany50"):
        out |= (read(results / "offline" / f"{name}{suffix}.json") or {}).get("splits", {})
    base = read(results / "offline" / f"{name.removesuffix('_probes')}.json")
    n = ok = 0.0
    for split in TEMPLATE_SETS if base else ():
        for key, scores in base["splits"].get(split, {}).items():
            if key not in ("all", "I0"):
                n += scores["n"]
                ok += scores["n"] * scores["admissible"]
    if n:
        out["templates"] = {"all": {"n": n, "admissible": ok / n}}
    return out


def tables(results: Path) -> list:
    out = []
    counts = {name: g for name in TRANSLATORS if (g := groups(results, name))}
    rows = [[TRANSLATORS[n]] + [pct(g.get((s, "all"), {}).get("correct", 0), g.get((s, "all"), {}).get("n", 0)) for s in SETS]
            for n, g in counts.items()]  # fmt: skip
    out.append(
        (
            "Instructions translated with the right meaning, % of distinct instructions",
            ["Translator", *SETS.values()],
            rows,
        )
    )
    two = {"templates": "Our wording", "independent": "Independent wording", "de_ind": "German, native",
           "fr_ind": "French, native", "it_ind": "Italian, native"}  # fmt: skip
    rows = [[TRANSLATORS[n]] + [pct(g.get((s, "I2+I3"), {}).get("correct", 0), g.get((s, "I2+I3"), {}).get("n", 0)) for s in two]
            for n, g in counts.items()]  # fmt: skip
    out.append(("Instructions with two preferences translated with the right meaning and order, %",
                ["Translator", *two.values()], rows))  # fmt: skip
    rows = []
    for name in ("translate2_few", "translate2_ft"):
        g = counts.get(name, {})
        cells = [TRANSLATORS[name]]
        for key in ("unseen", "unseen_impossible", "not_instruction"):
            c = g.get((key, "all"), {})
            n = c.get("n", 0)
            cells += [
                pct(c.get("same_status", 0), n),
                pct(c.get("flagged", 0) - c.get("same_status", 0), n),
                pct(c.get("applied", 0), n),
            ]
        rows.append(cells)
    header = ["Translator"] + [f"{what}: {col}" for what, right, other in (
        ("Unseen types", "to the decider", "dropped"), ("Unseen types that cannot be met", "to the decider", "dropped"),
        ("No instruction", "dropped", "to the decider")) for col in (right + " (right), %", other + ", %", "applied as a constraint (silent), %")]  # fmt: skip
    out.append(
        ("The gate: what the second translator does with instructions outside its format", header, rows)
    )

    found = {name: s for name in POLICIES if (s := splits(results, name))}
    rows = [[POLICIES[n]] + [pct(s["unseen"][t]["admissible"], 1) if t in s.get("unseen", {}) else "–" for t in TYPES]
            + [pct(s["unseen_impossible"]["all"]["admissible"], 1) if "unseen_impossible" in s else "–"]
            for n, s in found.items()]  # fmt: skip
    title = (
        "Instruction types nobody wrote a rule for: decisions that comply, % (200 requests per type on which the "
        "instruction changes the right answer; last column: rejected when it cannot be met, 200 requests)"
    )
    out.append((title, ["Policy", *TYPES.values(), "Cannot be met: rejected"], rows))
    rows = []
    for n, s in found.items():
        e = s.get("not_instruction", {}).get("all")
        rows.append([POLICIES[n]] + (["–"] * 4 if e is None else [
            pct(e["unchanged_without_instruction"], 1), pct(e["rejects"], 1), pct(e["flagged"], 1), pct(e.get("forwarded_to_decider", 0), 1)]))  # fmt: skip
    out.append(("Text that is no instruction (337 requests): what happens to the request, %",
                ["Policy", "Same decision as without it", "Rejected", "Flagged", "Sent to the decider"], rows))  # fmt: skip
    rows = [
        [POLICIES[n]] + [pct(s[k]["all"]["admissible"], 1) if k in s else "–" for k in SETS]
        for n, s in found.items()
    ]
    out.append(
        ("Supported instructions: decisions inside the admissible set, %", ["Policy", *SETS.values()], rows)
    )

    closed = {name: data for name in CLOSED if (data := read(results / "eval" / f"{name}.json"))}
    for load in sorted({e["load"] for d in closed.values() for e in d["summary"]}):
        rows = []
        for name, data in closed.items():
            index = {e["condition"]: e for e in data["summary"] if e["load"] == load}
            cells = [CLOSED[name]] + [
                f"{100 * index[c]['violation_rate_mean']:.2f}" if c in index else "–" for c in CONDITIONS
            ]
            pairs = index.get("heldout_pairs", {}).get("by_intent", {})
            cells += [
                pct(pairs[k]["violations"], pairs[k]["requests"], 2) if k in pairs else "–"
                for k in ("I1+I4", "I2+I3")
            ]
            ordered = read(results / "eval" / f"{name}_ordered.json")
            c = next(
                (e["by_intent"]["I2+I3"] for e in (ordered or {}).get("summary", []) if e["load"] == load),
                None,
            )
            cells.append("–" if c is None else pct(c["ordered_violations"], c["requests"], 2))
            rows.append(cells)
        out.append((f"Closed loop, intent violations, % of decisions, mean of three seeds — load {load} E",
                    ["Policy", *CONDITIONS.values(), "Avoid link + fewest slots", "Two preferences (intersection)",
                     "Two preferences (ordered reading)"], rows))  # fmt: skip
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    note = (
        "Rendered by `src/report_phase2.py`; do not edit by hand. The second translator has a second refusal "
        "(`no_instruction`), was shown two preferences, and its fine-tuned version was trained on English, German, "
        "French and Italian. † These German, French and Italian sentences were a test for the first translator and "
        "are training wording for the second; its test is the natively written sets. For the second translator the "
        "pairs of the closed loop are no longer unseen. The hybrid sends what the translator calls `unsupported` to "
        "the fine-tuned decider. Test sets: `src/corpora2.py`."
    )
    lines = ["# Second round: a stronger translator and a hybrid", "", note]
    for title, header, rows in tables(args.results):
        lines += ["", f"## {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
    out = args.results / "tables" / "phase2.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
