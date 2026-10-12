"""Third round: results JSON -> ``results/tables/phase3.md``.

Reads only files under ``results/``: ``design/readers3.json`` (what each reader does with every
test instruction, written by ``readers3.py``), ``translate/`` (the first two translators on the
earlier sets), ``offline/*_probes3.json`` (decisions on stored requests), ``eval/*_mix3.json``
(closed loop) and ``design/owner.json`` (the owner's own instructions). Cells without data are
shown as a dash.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READERS = {
    "translate3_few": "Apertus 8B, 15 examples, no training",
    "translate3_few70": "Apertus 70B (first generation), 15 examples, no training",
    "translate3_few70b": "Apertus 70B (generation 1.5), 15 examples, no training",
    "translate3_ft": "Apertus 8B fine-tuned (reader 1)",
    "translate3_ft2": "Apertus 8B fine-tuned (reader 2)",
    "translate3_ft_laptop": "Reader 1 on the laptop (4-bit GGUF, llama.cpp)",
}
LANGUAGES = {"v3_en": "English", "v3_de": "German", "v3_fr": "French", "v3_it": "Italian"}
GROUPS = {"atom": "One clause", "pair": "Pair seen in training", "heldout_pair": "Pair never seen together",
          "triple": "Three clauses, never seen together", "two_preferences": "Two preferences"}  # fmt: skip
EARLIER = {"independent": "Independent wording", "de_ind": "German, native", "fr_ind": "French, native",
           "it_ind": "Italian, native", "gsw": "Swiss German", "noisy": "Misspelt"}  # fmt: skip
NEW = {"largest_block": "Largest free block", "not_first": "Not the first candidate",
       "min_free": "A minimum of free slots", "min_mod": "A modulation threshold"}  # fmt: skip
OFFLINE = {
    "first_candidate_probes3": "First candidate that fits (ignores the instruction)",
    "no_intent_probes3": "Decision without an instruction (ignores it)",
    "apertus_ft_probes3": "Decider alone",
    "translate3_ft_probes3": "Translator alone (reader 1)",
    "hybrid3_ft_noguard_probes3": "Hybrid without the guard",
    "hybrid3_ft_probes3": "Hybrid",
    "hybrid3_ft_laptop_probes3": "Hybrid, all three models on the laptop",
}
CLOSED = {
    "oracle_mix3": "Rules for every kind (reference)",
    "first_fit_mix3": "First fit (ignores the instruction)",
    "teacher_mix3": "No-intent teacher (ignores the instruction)",
    "apertus_ft_mix3": "Decider alone",
    "translate3_ft_mix3": "Translator alone (reader 1)",
    "translate3_ft_ask-ft2_mix3": "Translator that asks when its two readers disagree",
    "translate3_ft_askif-ft2_mix3": "Translator that asks only when a request tells the readings apart",
    "hybrid3_ft_mix3": "Hybrid",
    "hybrid3_ft_ask-ft2_mix3": "Hybrid that asks when its two readers disagree",
    "hybrid3_ft_ask-few70b_mix3": "Hybrid that asks, the untrained Apertus 70B as second reader",
    "hybrid3_ft_laptop_ask-ft2_laptop_mix3": "Hybrid that asks, all three models on the laptop (4-bit)",
    "hybrid3_ft_laptop_askif-ft2_laptop_mix3": "Hybrid that asks only when a request tells the readings apart, on the laptop",
}
KINDS = {
    "In the format": ("atom", "pair", "heldout_pair", "triple", "two_preferences"),
    "Combinations never seen": ("heldout_pair", "triple"),
    "New types": tuple(NEW),
    "Carried in part": ("partial",),
    "No instruction": ("not_instruction",),
    "Place outside the network": ("faulty",),
    "All requests": ("all",),
}


def read(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(part: float, whole: float, decimals: int = 1) -> str:
    return "–" if not whole else f"{100 * part / whole:.{decimals}f}"


def pooled(rows: list[dict], reader: str, sets: tuple | list, kinds: tuple | list | None = None) -> dict:
    """Outcome counts of one reader over several sets (and kinds), from readers3.json."""
    total: dict = {}
    for row in rows:
        if row["reader"] != reader or row["set"] not in sets:
            continue
        if (kinds is None and row["lang"] == "all") or (
            kinds is not None and row["lang"] != "all" and row["kind"] in kinds
        ):
            for key, value in row.items():
                if isinstance(value, int):
                    total[key] = total.get(key, 0) + value
    return total


def reader_tables(design: dict, results: Path) -> list:
    rows, out = design["readers"], []
    found = [name for name in READERS if any(r["reader"] == name for r in rows)]
    table = []
    for name in found:
        cells = [READERS[name]]
        for group in GROUPS:
            c = pooled(rows, name, list(LANGUAGES), (group,))
            cells.append(pct(c.get("right", 0), c.get("n", 0)))
        c = pooled(rows, name, list(LANGUAGES))
        table.append(
            cells
            + [
                pct(c.get("right", 0), c.get("n", 0)),
                pct(c.get("silent", 0), c.get("n", 0)),
                str(c.get("n", 0)),
            ]
        )
    out.append((("The policy language: instructions translated with the right meaning, % of distinct instructions, "
                "four languages together"), ["Reader", *GROUPS.values(), "All", "Applied with a wrong meaning", "Instructions"],
                table))  # fmt: skip
    table = []
    for name in found:
        cells = [READERS[name]]
        for language in LANGUAGES:
            for kinds in (None, ("heldout_pair", "triple")):
                c = pooled(rows, name, [language], kinds)
                cells.append(pct(c.get("right", 0), c.get("n", 0)))
        table.append(cells)
    header = ["Reader"] + [
        f"{lang}: {what}" for lang in LANGUAGES.values() for what in ("all", "never seen together")
    ]
    out.append(
        ("The same by language: all instructions, and the combinations never seen together", header, table)
    )

    earlier = {
        "First translator, fine-tuned": "translate_ft",
        "Second translator, fine-tuned": "translate2_ft",
    }
    table = []
    for label, name in earlier.items():
        groups = {(g["set"], g["kind"]): g for suffix in ("", "_germany50")
                  for g in (read(results / "translate" / f"{name}{suffix}.json") or {}).get("groups", [])
                  if g["lang"] == "all" or g["kind"] == "all"}  # fmt: skip
        cells = [label] + [pct(groups.get((s, "all"), {}).get("correct", 0), groups.get((s, "all"), {}).get("n", 0))
                           for s in (*EARLIER, "germany50")]  # fmt: skip
        table.append(cells)
    other = (read(results / "translate" / "translate3_ft_germany50.json") or {}).get("groups", [])
    transfer = next((g for g in other if g["kind"] == "all"), {})
    for name in found:
        cells = [READERS[name]]
        for s in EARLIER:
            c = pooled(rows, name, [s])
            cells.append(pct(c.get("right", 0), c.get("n", 0)))
        cells.append(
            pct(transfer.get("correct", 0), transfer.get("n", 0)) if name == "translate3_ft" else "–"
        )
        table.append(cells)
    out.append(("The test sets of the earlier rounds (not trained on by any translator): right meaning, %",
                ["Translator", *EARLIER.values(), "Other topology"], table))  # fmt: skip

    table = []
    for name in found:
        new = pooled(rows, name, ["v3_new", "v3_new_hard", "v3_new_impossible"])
        part = pooled(rows, name, ["v3_partial"])
        other, nothing, faulty = (pooled(rows, name, [s]) for s in ("v3_other", "v3_not", "v3_faulty"))
        table.append([
            READERS[name],
            pct(new.get("right", 0), new.get("n", 0)), pct(new.get("other_refusal", 0), new.get("n", 0)),
            pct(new.get("silent", 0), new.get("n", 0)),
            pct(part.get("right", 0), part.get("n", 0)), pct(part.get("handed_on", 0), part.get("n", 0)),
            pct(part.get("part_only", 0), part.get("n", 0)),
            pct(part.get("silent", 0) + part.get("flagged", 0), part.get("n", 0)),
            pct(other.get("right", 0), other.get("n", 0)), pct(nothing.get("right", 0), nothing.get("n", 0)),
            pct(nothing.get("silent", 0), nothing.get("n", 0)), pct(faulty.get("right", 0), faulty.get("n", 0)),
            pct(faulty.get("silent", 0), faulty.get("n", 0)),
        ])  # fmt: skip
    out.append((("The gate: what a reader does with instructions that are not, or not wholly, in the format, % of "
                "distinct instructions"),
                ["Reader", "New type: handed to the decider (right)", "New type: dropped", ("New type: applied as "
                 "something else (silent)"), "Part carried: part and marker right", "Part carried: all handed on",
                 "Part carried: part right, rest dropped silently", "Part carried: other",
                 "Other routing instruction: handed on (right)", "No instruction: dropped (right)",
                 "No instruction: applied (silent)", "Place outside the network: flagged (right)",
                 "Place outside the network: applied (silent)"], table))  # fmt: skip

    table = []
    groups = {"The policy language, four languages": list(LANGUAGES), "Carried in part": ["v3_partial"],
              "New types": ["v3_new", "v3_new_hard", "v3_new_impossible"],
              "Earlier sets (independent, native German, French, Italian)": ["independent", "de_ind", "fr_ind", "it_ind"],
              "Instructions of the closed loop": ["operations_mix3"]}  # fmt: skip
    for first, second in (("translate3_ft", "translate3_ft2"), ("translate3_ft", "translate3_few"),
                          ("translate3_ft", "translate3_few70"), ("translate3_ft", "translate3_few70b")):  # fmt: skip
        for label, sets in groups.items():
            c: dict = {}
            for row in design["pairs"]:
                if row["first"] == first and row["second"] == second and row["set"] in sets:
                    for key, value in row.items():
                        if isinstance(value, int):
                            c[key] = c.get(key, 0) + value
            # only where the second reader answered every instruction of the group
            if c.get("n") and c["n"] == pooled(rows, first, sets).get("n"):
                table.append([f"{READERS[first]} / {READERS[second]}", label, str(c["n"]),
                              pct(c["wrong_alone"], c["n"]), pct(c["wrong_left"], c["n"]),
                              pct(c["silent_alone"], c["n"]), pct(c["silent_left"], c["n"]),
                              pct(c["asked"], c["n"]), pct(c["right_but_asked"], c["n"])])  # fmt: skip
    out.append(("Two readers: the operator is asked when their readings differ. % of distinct instructions",
                ["First reader / second reader", "Instructions", "n", "Not right, first reader alone",
                 "Not right and not asked", "Applied wrongly, first reader alone", "Applied wrongly and not asked",
                 "Asked", "Asked although right"], table))  # fmt: skip
    if design.get("latency"):
        names = {
            "translate3_ft_laptop": "Reader 1",
            "translate3_ft2_laptop": "Reader 2",
            "apertus_ft_laptop": "Decider",
        }
        out.append((("On the laptop (RTX 4060, 8 GB; llama.cpp, 4-bit base model, adapters switched per request): "
                    "seconds per answer"), ["Model", "Answers", "Median", "Mean", "95th percentile"],
                    [[names.get(r["policy"], r["policy"]), str(r["answers"]), f"{r['median_s']:.2f}",
                      f"{r['mean_s']:.2f}", f"{r['p95_s']:.2f}"] for r in design["latency"]]))  # fmt: skip
    return out


def offline_tables(results: Path) -> list:
    found = {name: data["splits"] for name in OFFLINE if (data := read(results / "offline" / f"{name}.json"))}
    out = []
    for split, title in (("v3_new", "New types, on requests where the instruction is restrictive"),
                         ("v3_new_hard", "New types, on requests where neither instruction-blind choice complies")):  # fmt: skip
        table = [[OFFLINE[name]] + [pct(s[split][t]["admissible"], 1) if t in s.get(split, {}) else "–"
                                    for t in (*NEW, "all")] for name, s in found.items()]  # fmt: skip
        counts = next((s[split] for s in found.values() if split in s), {})
        header = ["Policy"] + [f"{NEW[t]} ({counts.get(t, {}).get('n', 0)})" for t in NEW] + ["All"]
        out.append((f"{title}: decisions that comply, %", header, table))
    table = []
    for name, s in found.items():
        impossible, partial = s.get("v3_new_impossible", {}).get("all"), s.get("v3_partial", {}).get("all")
        table.append([OFFLINE[name],
                      pct(impossible["admissible"], 1) if impossible else "–",
                      pct(partial["admissible"], 1) if partial else "–",
                      pct(partial.get("forwarded_to_decider", 0), 1) if partial else "–",
                      pct(partial.get("guarded", 0), 1) if partial else "–"])  # fmt: skip
    out.append((("A new constraint that no path meets (reject is right), and instructions carried in part: decisions "
                "that comply, %"), ["Policy", "Cannot be met: rejected", "Carried in part: complies",
                                   "Carried in part: sent to the decider", "Carried in part: guard replaced the choice"],
                table))  # fmt: skip
    table = []
    for name, s in found.items():
        cells = [OFFLINE[name]]
        for group in (*GROUPS, "all"):
            cells.append(pct(s["v3_en"][group]["admissible"], 1) if group in s.get("v3_en", {}) else "–")
        cells += [
            pct(s[lang]["all"]["admissible"], 1) if lang in s else "–" for lang in ("v3_de", "v3_fr", "v3_it")
        ]
        table.append(cells)
    out.append(("The policy language on stored requests: decisions that comply, %",
                ["Policy", *(f"English: {g.lower()}" for g in GROUPS.values()), "English: all", "German", "French",
                 "Italian"], table))  # fmt: skip
    return out


def closed_tables(results: Path) -> list:
    found = {name: data for name in CLOSED if (data := read(results / "eval" / f"{name}.json"))}
    out = []
    for load in sorted({e["load"] for d in found.values() for e in d["summary"]}):
        table, binding, seeds = [], [], []
        for name, data in found.items():
            entry = next((e for e in data["summary"] if e["load"] == load), None)
            if entry is None:
                continue
            counts = entry["by_intent"]

            def total(keys, field, counts=counts):
                return sum(counts.get(k, {}).get(field, 0) for k in keys)

            n = total(("all",), "requests")
            table.append([CLOSED[name]] + [pct(total(keys, "violations"), total(keys, "requests")) for keys in KINDS.values()]
                         + [f"{100 * entry['service_blocking_rate_mean']:.2f}", pct(total(("all",), "forwarded"), n),
                            pct(total(("all",), "guarded"), n), pct(total(("all",), "asked"), n)])  # fmt: skip
            binding.append([CLOSED[name]] + [pct(total(keys, "binding_violations"), total(keys, "binding"))
                                             for keys in list(KINDS.values())[:4]]
                           + [str(total(keys, "binding")) for keys in list(KINDS.values())[:4]])  # fmt: skip
            runs = sorted((e["seed"], e["violation_rate"]) for e in data["episodes"] if e["load"] == load)
            seeds.append([CLOSED[name]] + [f"{100 * rate:.2f}" for _, rate in runs])
        if table:
            out.append(((f"The mixed stream of the third round in closed loop: violations, % of the requests of each "
                        f"kind — load {load} E"), ["Policy", *KINDS, "Blocking, %", "Sent to the decider, %",
                                                 "Guard replaced the choice, %", "Operator asked, %"], table))  # fmt: skip
            kinds = list(KINDS)[:4]
            out.append((f"The same, only requests on which the instruction changes the right answer — load {load} E",
                        ["Policy", *(f"{k}: violations, %" for k in kinds), *(f"{k}: such requests" for k in kinds)],
                        binding))  # fmt: skip
            out.append((f"All requests, violations in % per seed — load {load} E", ["Policy", "Seed 1", "Seed 2", "Seed 3"],
                        seeds))  # fmt: skip
    return out


NOTES = (
    "Rendered by `src/report_phase3.py`; do not edit by hand. The third format of the translator is a line of slots "
    "(links and nodes to avoid, a node to pass through, limits on hops and length, a candidate by its number, ordered "
    "preferences, and a marker for a part the slots cannot carry). Two readers were fine-tuned with different seeds "
    "and training samples. Test wording: `data/instructions/v3_source_*.json`, written by separate AI instances "
    "that never saw the repository. Which combinations of clauses are trained and which are held out was fixed "
    "before those sources were opened (`src/corpora3.py`). Preferences are read in the order stated (constraints, "
    "then objectives); a request is selected for an instruction by a condition on the instruction and the request "
    "only (`src/corpora3_tests.py`), and instruction-blind baselines are shown on the same requests."
)


STANDING = {
    "standing_oracle_standing4": "The true policy table (reference)",
    "first_fit_standing4": "First fit (ignores the policies)",
    "teacher_standing4": "No-intent teacher (ignores the policies)",
    "standing_noscope_standing4": "True policies, scope ignored (every policy covers every request)",
    "standing_nountil_standing4": "True policies, lifetime ignored (no policy ever expires)",
    "standing3_ft_laptop_standing4": "Policies read by the third-format reader (no scope, no lifetime)",
    "standing4_ft_standing4": "Policies read by the fourth-format reader",
    "standing4_ft_laptop_standing4": "Policies read by the fourth-format reader, on the laptop",
}


def standing_tables(results: Path) -> list:
    """Standing policies in closed loop: violations against the true policy table."""
    found = {name: data for name in STANDING if (data := read(results / "eval" / f"{name}.json"))}
    out = []
    for load in sorted({e["load"] for d in found.values() for e in d["summary"]}):
        table = []
        for name, data in found.items():
            entry = next((e for e in data["summary"] if e["load"] == load), None)
            if entry is None:
                continue
            b = entry["by_intent"]["all"]
            runs = sorted((e["seed"], e["violation_rate"]) for e in data["episodes"] if e["load"] == load)
            dropped = data["metadata"]["policy"].get("dropped_policies")
            table.append([STANDING[name], pct(b["violations"], b["requests"]), pct(b["binding_violations"], b["binding"]),
                          pct(b["rejects"], b["requests"]), f"{100 * entry['service_blocking_rate_mean']:.2f}",
                          "–" if dropped is None else str(dropped),
                          " / ".join(f"{100 * rate:.1f}" for _, rate in runs)])  # fmt: skip
        if table:
            title = ("Standing policies in closed loop (policies arrive, hold for the hours they state or until "
                     f"withdrawn, and cover the requests their scope names): violations against the true table, % — load {load} E")  # fmt: skip
            out.append((title,
                        ["Policy", "Violations, % of requests", "Where a policy changes the right answer, %",
                         "Rejected, %", "Blocking, %", "Policies the reader dropped", "Per seed"], table))  # fmt: skip
    return out


def consistency_tables(results: Path) -> list:
    """Self-consistency of reader 1 against the two other checks (``design/consistency3.json``)."""
    data = read(results / "design" / "consistency3.json")
    if not data:
        return []
    names = {"translate3_ft2_laptop": "reader 2 (same recipe, on the laptop)", "translate3_few70b": "untrained Apertus 70B",
             **{f"samples>={t}": f"{t} or more of {data['samples']} samples of reader 1 differ" for t in range(1, 6)},
             "translate3_ft2_laptop+samples>=1": "reader 2, or a sample differs",
             "translate3_few70b+samples>=1": "the 70B, or a sample differs"}  # fmt: skip
    rows = [[e["group"], names.get(e["signal"], e["signal"]), str(e["n"]), pct(e["asked"], e["n"]), pct(e["wrong"], e["n"]),
             pct(e["wrong_left"], e["n"]), pct(e["silent_left"], e["n"]), pct(e["right_asked"], e["n"])]
            for e in data["signals"] if e["group"] in ("policy language", "types never shown", "carried in part")
            and e["signal"] in names]  # fmt: skip
    return [("Three signals that could make the system ask, on the laptop's greedy reading of reader 1: % of instructions",
             ["Instructions", "Signal", "n", "Asked", "Not right alone", "Not right and not asked",
              "Applied wrongly and not asked", "Asked although right"], rows)]  # fmt: skip


def swiss_tables(results: Path) -> list:
    """The readers on the Swiss network (``translate/<reader>_swiss.json``)."""
    names = {
        "translate3_ft_laptop": "Reader 1 on the laptop",
        "translate3_ft2_laptop": "Reader 2 on the laptop",
    }
    langs = {"en": "English", "de": "German", "fr": "French", "it": "Italian"}
    rows = []
    for reader, label in names.items():
        data = read(results / "translate" / f"{reader}_swiss.json")
        if not data:
            continue
        for lang, language in langs.items():
            total = next(
                (g for g in data["groups"] if g["set"] == f"v3_swiss_{lang}" and g["lang"] == "all"), None
            )
            if not total:
                continue
            kinds = {
                g["kind"]: g for g in data["groups"] if g["set"] == f"v3_swiss_{lang}" and g["lang"] == lang
            }
            rows.append([label, language, str(total["n"]), pct(total["correct"], total["n"]), pct(total["wrong"], total["n"]),
                         pct(total["flagged"], total["n"])]
                        + [pct(kinds[k]["correct"], kinds[k]["n"]) if k in kinds else "–" for k in GROUPS])  # fmt: skip
    if not rows:
        return []
    title = ("The policy language on a Swiss network (24 cities named in each language's own form, never in training): "
             "right meaning, % of instructions")  # fmt: skip
    return [(title, ["Reader", "Language", "n", "Right", "Applied with another meaning", "Not applied",
                     *GROUPS.values()], rows)]  # fmt: skip


def owner_tables(results: Path) -> list:
    """The project owner's own instructions (``design/owner.json``, written by ``corpora3_owner.py``)."""
    owner = read(results / "design" / "owner.json")
    if not owner:
        return []
    names = {"translate3_ft_laptop": "Reader 1", "translate3_ft2_laptop": "Reader 2",
             "translate3_few_laptop": "Apertus 8B, 15 examples, no training"}  # fmt: skip
    groups = {"all": "All", "en": "English", "ur": "Urdu in Latin script"}
    summary = [[names[r["reader"]], groups[r["group"]], str(r["n"]), str(r.get("right", 0)),
                str(r.get("silent", 0) + r.get("part_only", 0)),
                str(r["n"] - r.get("right", 0) - r.get("silent", 0) - r.get("part_only", 0))]
               for r in owner["readers"] if r["group"] in groups]  # fmt: skip
    summary.sort(key=lambda row: (list(names.values()).index(row[0]), list(groups.values()).index(row[1])))
    asking = [[f"Reader 1 / {names[p['second']]}", str(p["n"]), str(p["wrong_alone"]), str(p["wrong_left"]),
               str(p["asked"]), str(p["right_but_asked"])] for p in owner["pairs"]]  # fmt: skip
    first, second = list(names)[:2]
    lines = [[e["text"].replace("|", "/"), e["expect"], e[first]["answer"] if e[first]["outcome"] != "right" else "=",
              e[first]["outcome"], "yes" if e[second]["asked"] else ""] for e in owner["lines"]]  # fmt: skip
    where = "on the laptop (4-bit base model, llama.cpp)"
    return [
        (f"The project owner's own instructions, {where}: number of instructions",
         ["Reader", "Lines", "n", "Right", "Applied with another meaning", "Not applied"], summary),
        ("The owner's instructions, two readers: the operator is asked when their readings differ",
         ["First reader / second reader", "n", "Not right, first reader alone", "Not right and not asked", "Asked",
          "Asked although right"], asking),
        ("The owner's instructions, line by line (= : reader 1 wrote what was meant)",
         ["Instruction", "Meant", "Reader 1 wrote", "Outcome", "Reader 2 differs: asked"], lines),
    ]  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    design = read(args.results / "design" / "readers3.json")
    tables = (reader_tables(design, args.results) if design else []) + offline_tables(args.results)
    tables += closed_tables(args.results) + standing_tables(args.results) + swiss_tables(args.results)
    tables += consistency_tables(args.results) + owner_tables(args.results)
    lines = ["# Third round: a policy language, two readers, and a guarded fallback", "", NOTES, ""]
    for title, header, rows in tables:
        lines += [f"## {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(row) + " |" for row in rows] + [""]
    text = "\n".join(lines)
    out = args.out or args.results / "tables" / "phase3.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main()
