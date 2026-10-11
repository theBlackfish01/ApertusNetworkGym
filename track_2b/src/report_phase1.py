"""Tables of phase 1 (translate versus decide) from the result files; writes ``results/tables/phase1.md``.

Sources: ``results/translate/*.json`` (translation accuracy, ``translate.py score``),
``results/offline/*_probes.json`` (decisions on the probe sets, ``evaluate.py offline --data
data/probes``), ``results/offline/*.json`` (held-out splits) and ``results/eval/*.json`` (closed
loop). Nothing is computed here that is not in those files; a missing file gives a "–".

    uv run python src/report_phase1.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATORS = {
    "translate_keyword": "Keyword parser (no model)",
    "translate_zero": "Apertus as is",
    "translate_few": "Apertus, 7 examples in the prompt",
    "translate_ft": "Apertus fine-tuned",
    "translate_few_free": "Apertus, 7 examples, no answer grammar",
    "translate_ft_free": "Apertus fine-tuned, no answer grammar",
}
DECIDERS = {
    "oracle_probes": "Rule engine given the true instruction (oracle)",
    "apertus_ft_probes": "Decider: Apertus fine-tuned",
    "translate_keyword_probes": "Translator: keyword parser",
    "translate_zero_probes": "Translator: Apertus as is",
    "translate_few_probes": "Translator: Apertus, 7 examples",
    "translate_ft_probes": "Translator: Apertus fine-tuned",
}
TEMPLATE_SETS = ("heldout_indist", "heldout_paraphrase", "heldout_pairs")
SETS = {
    "templates": "Dataset wording",
    "independent": "Independent wording",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "gsw": "Swiss German",
    "noisy": "Misspelt",
    "closed_loop": "Closed-loop instructions",
    "germany50": "Other topology",
}
PROBES = ("independent", "de", "fr", "it", "gsw", "noisy", "germany50")
CLOSED = {"translate_keyword": "Translator: keyword parser", "translate_zero": "Translator: Apertus as is",
          "translate_few": "Translator: Apertus, 7 examples", "translate_ft": "Translator: Apertus fine-tuned",
          "apertus_ft": "Decider: Apertus fine-tuned", "oracle": "Rule engine given the true instruction (oracle)"}  # fmt: skip
CONDITIONS = {"I1": "Avoid link", "I2": "Fewest hops", "I3": "Least loaded", "I4": "Fewest slots",
              "mixed_heldout_paraphrases": "Unseen wording", "heldout_pairs": "Unseen pairs"}  # fmt: skip


def read(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(part: float, whole: float, decimals: int = 1) -> str:
    return "–" if not whole else f"{100 * part / whole:.{decimals}f}"


def translation_counts(results: Path, name: str) -> dict[str, dict]:
    """Counts per test set for one translator (the three held-out dataset splits pooled as ``templates``)."""
    counts: dict[str, dict] = {}
    for suffix in ("", "_germany50"):
        data = read(results / "translate" / f"{name}{suffix}.json")
        for group in (data or {}).get("groups", []):
            key = group["set"] if group["lang"] == "all" else f"{group['set']}/{group['kind']}"
            if group["set"] in TEMPLATE_SETS and group["lang"] == "all":
                key = "templates"
            total = counts.setdefault(
                key, dict.fromkeys(("n", "correct", "flagged", "wrong", "applied", "malformed"), 0)
            )
            for field in total:
                total[field] += group[field]
    return counts


def translation_tables(results: Path) -> list:
    counts = {name: translation_counts(results, name) for name in TRANSLATORS}
    counts = {name: c for name, c in counts.items() if c}
    tables = []
    for field, title in (("correct", "Instructions translated with the right meaning, %"),
                         ("wrong", "Instructions applied with a wrong meaning (silent), %"),
                         ("flagged", "Valid instructions the translator refused (visible), %")):  # fmt: skip
        rows = [[TRANSLATORS[name]] + [pct(c.get(s, {}).get(field, 0), c.get(s, {}).get("n", 0)) for s in SETS]
                for name, c in counts.items()]  # fmt: skip
        tables.append((title, ["Translator", *SETS.values()], rows))
    sizes = next(iter(counts.values()), {})
    tables[0] = (tables[0][0] + " — distinct instructions per set: "
                 + ", ".join(f"{label} {sizes.get(s, {}).get('n', 0)}" for s, label in SETS.items()), *tables[0][1:])  # fmt: skip
    kinds = {"faulty/not_a_link": "Two nodes that are not adjacent", "faulty/unknown_place": "Place outside the network",
             "out_of_scope": "Out of scope"}  # fmt: skip
    rows = [[TRANSLATORS[name]] + [pct(c.get(k, {}).get("flagged", 0), c.get(k, {}).get("n", 0)) for k in kinds]
            + [pct(c.get("templates", {}).get("malformed", 0) + c.get("independent", {}).get("malformed", 0),
                   c.get("templates", {}).get("n", 0) + c.get("independent", {}).get("n", 0))]
            for name, c in counts.items()]  # fmt: skip
    title = (
        "Instructions that must not be applied: flagged, % (the rest was applied silently); and answers "
        "outside the format on English instructions, %"
    )
    tables.append((title, ["Translator", *kinds.values(), "Malformed answers"], rows))
    return tables


def probe_tables(results: Path) -> list:
    found = {}
    for name in DECIDERS:  # a translator's scores on the other topology are a run of their own (--topology)
        files = [read(results / "offline" / f"{name}{suffix}.json") for suffix in ("", "_germany50")]
        splits = {split: scores for data in files if data for split, scores in data["splits"].items()}
        if splits:
            found[name] = splits
            # The same requests with the dataset's own wording: the held-out splits without the
            # requests that carry no instruction (the probe sets have none of those either).
            base = read(results / "offline" / f"{name.removesuffix('_probes')}.json")
            pooled = {"n": 0, "admissible": 0.0, "admissible_ordered": 0.0}
            for split in TEMPLATE_SETS if base else ():
                for key, scores in base["splits"].get(split, {}).items():
                    if key not in ("all", "I0"):
                        pooled["n"] += scores["n"]
                        for field in ("admissible", "admissible_ordered"):
                            pooled[field] += scores["n"] * scores.get(field, float("nan"))
            if pooled["n"]:
                splits["templates"] = {
                    "all": {f: pooled[f] / pooled["n"] for f in ("admissible", "admissible_ordered")}
                }
    if not found:
        return []
    tables = []
    spec_rule = (
        "Decisions inside the admissible set on the probe sets (same requests, instruction re-worded), % "
        "— rule of SPEC section 3"
    )
    ordered_rule = "The same under the ordered reading of two preferences, %"
    for field, title in (("admissible", spec_rule), ("admissible_ordered", ordered_rule)):
        columns = ("templates", *PROBES)
        rows = [[DECIDERS[name]] + [pct(s[p]["all"][field], 1) if p in s and s[p]["all"][field] == s[p]["all"][field]
                                    else "–" for p in columns]
                for name, s in found.items()]  # fmt: skip
        tables.append((title, ["Policy", *(SETS[p] for p in columns)], rows))
    rows = []
    for name, splits in found.items():
        cells = [DECIDERS[name]]
        for split, kind in (
            ("faulty", "not_a_link"),
            ("faulty", "unknown_place"),
            ("out_of_scope", "out_of_scope"),
        ):
            entry = splits.get(split, {}).get(kind)
            cells += ["–", "–"] if entry is None or "unchanged_without_instruction" not in entry else [
                pct(entry["unchanged_without_instruction"], 1), pct(entry["flagged"], 1)]  # fmt: skip
        rows.append(cells)
    header = ["Policy"] + [f"{what}: {col}" for what in ("Not adjacent", "Outside the network", "Out of scope")
                           for col in ("same decision as without instruction %", "flagged %")]  # fmt: skip
    tables.append(("Instructions that must not be applied: what happens to the request", header, rows))
    return tables


def decider_table(results: Path) -> list:
    """Does the decider need fine-tuning? The same model with no, seven and 12,000 solved requests."""
    names = {"apertus_zero_shot": "Apertus as is", "apertus_fewshot": "Apertus, 7 solved requests in the prompt",
             "apertus_ft": "Apertus fine-tuned on 12,000 requests"}  # fmt: skip
    labels = {
        "heldout_indist": "New traffic",
        "heldout_paraphrase": "Unseen wording",
        "heldout_pairs": "Unseen pairs",
    }
    rows = []
    for name, label in names.items():
        data = read(results / "offline" / f"{name}.json")
        if data:
            cells = [label]
            for split in labels:
                entry = data["splits"].get(split, {}).get("all")
                cells += (
                    ["–", "–"] if entry is None else [pct(entry["admissible"], 1), pct(entry["invalid"], 1)]
                )
            rows.append(cells)
    if len(rows) < 2:
        return []
    header = ["Decider"] + [
        f"{label}: {kind}" for label in labels.values() for kind in ("admissible %", "invalid %")
    ]
    return [
        (
            "The decider with and without fine-tuning: decisions on the held-out splits (answer format enforced)",
            header,
            rows,
        )
    ]


def closed_tables(results: Path) -> list:
    found = {name: read(results / "eval" / f"{name}.json") for name in CLOSED}
    found = {name: data for name, data in found.items() if data}
    if not any(name.startswith("translate_") for name in found):
        return []
    tables = []
    for load in sorted({e["load"] for data in found.values() for e in data["summary"]}):
        for metric, title in (("violation_rate", "Intent violations, % of decisions"),
                              ("service_blocking_rate", "Service blocking probability, %")):  # fmt: skip
            rows = []
            for name, data in found.items():
                index = {e["condition"]: e for e in data["summary"] if e["load"] == load}
                rows.append([CLOSED[name]] + [
                    "–" if c not in index else f"{100 * index[c][f'{metric}_mean']:.2f} ± {100 * index[c][f'{metric}_std']:.2f}"
                    for c in CONDITIONS])  # fmt: skip
            tables.append((f"Closed loop, {title} — load {load} E", ["Policy", *CONDITIONS.values()], rows))
        # The two unseen pairs apart, and the pair of two preferences under both readings.
        rows = []
        for name, data in found.items():
            entry = next(
                (e for e in data["summary"] if e["load"] == load and e["condition"] == "heldout_pairs"), None
            )
            if entry is None:
                continue
            pairs = entry["by_intent"]
            cells = [CLOSED[name]] + [
                pct(pairs[k]["violations"], pairs[k]["requests"]) for k in ("I1+I4", "I2+I3")
            ]
            ordered = read(results / "eval" / f"{name}_ordered.json")
            counts = next(
                (e["by_intent"]["I2+I3"] for e in (ordered or {}).get("summary", []) if e["load"] == load),
                None,
            )
            cells.append("–" if counts is None else pct(counts["ordered_violations"], counts["requests"]))
            rows.append(cells)
        header = ["Policy", "Avoid link + fewest slots", "Two preferences, intersection (SPEC section 3)",
                  "Two preferences, ordered reading (engine and scoring)"]  # fmt: skip
        tables.append(
            (f"Closed loop, the unseen pairs apart: violations, % of decisions — load {load} E", header, rows)
        )
        # A translator's violations split by whether it had flagged the instruction (pooled over seeds).
        rows = []
        for name, data in found.items():
            if not name.startswith("translate_"):
                continue
            cells = [CLOSED[name]]
            for condition in CONDITIONS:
                episodes = [e for e in data["episodes"] if e["load"] == load and e["condition"] == condition]
                window = sum(e["window"] for e in episodes)
                silent = sum(e["silent_violations"] for e in episodes)
                flagged = sum(e["violations"] - e["silent_violations"] for e in episodes)
                cells.append(f"{pct(silent, window, 2)} / {pct(flagged, window, 2)}" if window else "–")
            rows.append(cells)
        title = (
            f"Closed loop, a translator's violations: instruction applied with a wrong meaning (silent) / "
            f"instruction flagged and not applied (visible), % of decisions — load {load} E"
        )
        tables.append((title, ["Policy", *CONDITIONS.values()], rows))
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    tables = (
        translation_tables(args.results)
        + probe_tables(args.results)
        + decider_table(args.results)
        + closed_tables(args.results)
    )
    note = (
        "Rendered by `src/report_phase1.py` from `results/translate/`, `results/offline/` and `results/eval/`; "
        "do not edit by hand. A translator turns the instruction into constraints and preferences once and the "
        "rule engine decides; a decider reads the instruction with every request. Test sets: `src/corpora.py`."
    )
    lines = ["# Phase 1: translate versus decide", "", note]
    for title, header, rows in tables:
        lines += ["", f"## {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
    out = args.results / "tables" / "phase1.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
