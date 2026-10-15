"""The test instructions and every reader's answers as a benchmark: ``data/benchmark/``.

Three files, as the hackathon's dataset guidelines ask: ``evaluation.jsonl`` (one row per test
instruction with the line it means), ``responses.jsonl`` (one row per instruction and reader, with
the reader's line and its outcome), ``metadata.json`` (how the sets were written, the licence, the
outcome definitions, counts). ``README.md`` next to them is the dataset card. Everything comes
from files in ``data/instructions/`` and ``results/cache/``; nothing is written by hand.

    uv run python src/benchmark_export.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from readers3 import Answers, outcome
from spec import Spec, format_spec
from translate import read_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "benchmark"
SETS = {
    # set -> (how the sentences were written, topology)
    "v3_en": (
        "a separate AI instance, from a brief naming the clause kinds and none of the project's wording",
        "nobel-eu",
    ),
    "v3_de": ("a separate AI instance (German)", "nobel-eu"),
    "v3_fr": ("a separate AI instance (French)", "nobel-eu"),
    "v3_it": ("a separate AI instance (Italian)", "nobel-eu"),
    "v3_new": ("a separate AI instance: four instruction types shown to no component", "nobel-eu"),
    "v3_new_hard": ("as v3_new, on requests where neither instruction-blind choice complies", "nobel-eu"),
    "v3_new_impossible": ("as v3_new, on requests no path can satisfy", "nobel-eu"),
    "v3_partial": ("a separate AI instance: one clause the language carries with one it cannot", "nobel-eu"),
    "v3_other": ("a separate AI instance: routing instructions of yet other kinds", "nobel-eu"),
    "v3_not": ("a separate AI instance: text that is no routing instruction", "nobel-eu"),
    "v3_faulty": ("v3 sentences naming a place outside the network", "nobel-eu"),
    "owner": (
        "the project's author, partly with an AI assistant (ChatGPT 6.1 Sol): 35 English, 5 Urdu/Hindi in Latin letters",
        "nobel-eu",
    ),
    "template1": (
        (
            "the author on the project's template, partly with ChatGPT 6.1 Sol, set 1: one request each, English, "
            "German, Italian, Swedish"
        ),
        "nobel-eu",
    ),
    "template1_standing": ("set 1: standing policies with a scope or a lifetime", "nobel-eu"),
    "template2": (
        "the author on the project's template, partly with ChatGPT 6.1 Sol, set 2: one request each, English and German",
        "nobel-eu",
    ),
    "template2_standing": ("set 2: standing policies with a scope or a lifetime", "nobel-eu"),
    "template3": (
        "the author on the project's template, partly with ChatGPT 6.1 Sol, set 3: one request each, English and German",
        "nobel-eu",
    ),
    "template3_standing": ("set 3: standing policies with a scope or a lifetime", "nobel-eu"),
    "template4": (
        (
            "the author on the project's template, partly with ChatGPT 6.1 Sol, set 4: one request each, English, "
            "Swiss German, French, Italian"
        ),
        "nobel-eu",
    ),
    "template4_standing": ("set 4: standing policies with a scope or a lifetime", "nobel-eu"),
    "template5": (
        (
            "the author on the project's template, partly with ChatGPT 6.1 Sol, set 5: one request each, English, "
            "Swiss German, French, Italian"
        ),
        "nobel-eu",
    ),
    "template5_standing": ("set 5: standing policies with a scope or a lifetime", "nobel-eu"),
    "v4_en": ("v3 sentences with a scope or lifetime phrase by another separate AI instance", "nobel-eu"),
    "v4_de": ("as v4_en (German)", "nobel-eu"),
    "v4_fr": ("as v4_en (French)", "nobel-eu"),
    "v4_it": ("as v4_en (Italian)", "nobel-eu"),
    "v3_swiss_en": ("v3 sentences filled with Swiss cities in their English names", "swiss"),
    "v3_swiss_de": ("v3 sentences filled with Swiss cities in their German names", "swiss"),
    "v3_swiss_fr": ("v3 sentences filled with Swiss cities in their French names", "swiss"),
    "v3_swiss_it": ("v3 sentences filled with Swiss cities in their Italian names", "swiss"),
    **{
        f"parallel_{code}{part}": (
            (
                "60 items by a separate AI instance from a brief"
                if code == "en"
                else f"parallel_en translated into {language} by another separate AI instance, from the sentences alone"
            )
            + (": standing policies" if part else ": one request each"),
            "nobel-eu",
        )
        for code, language in (
            ("en", "English"),
            ("de", "German"),
            ("fr", "French"),
            ("it", "Italian"),
            ("ur_latn", "Urdu/Hindi in Latin letters (written as Roman Urdu)"),
            ("ur_arab", "Urdu in Urdu script"),
            ("hi", "Hindi in Devanagari"),
            ("ar", "Arabic"),
            ("ar_latn", "Arabic in Latin letters (Arabizi)"),
        )
        for part in ("", "_standing")
    },
}
READERS = {
    # reader -> (description, topology it answered for)
    "translate3_ft": ("Apertus v1.5 8B, fine-tuned reader 1 (third format), A100, bf16", "nobel-eu"),
    "translate3_ft2": ("Apertus v1.5 8B, fine-tuned reader 2 (third format), A100, bf16", "nobel-eu"),
    "translate3_few": ("Apertus v1.5 8B, 15 examples, no training", "nobel-eu"),
    "translate3_few70": ("Apertus 70B (first generation), 15 examples, no training, 4-bit GGUF", "nobel-eu"),
    "translate3_few70b": ("Apertus v1.5 70B, 15 examples, no training, 4-bit GGUF", "nobel-eu"),
    "translate3_ft_laptop": ("reader 1, 4-bit GGUF under llama.cpp on an RTX 4060 laptop", "nobel-eu"),
    "translate3_ft2_laptop": ("reader 2, 4-bit GGUF on the laptop", "nobel-eu"),
    "translate3_ft_laptop_s1": ("reader 1 on the laptop, sample 1 at temperature 0.8", "nobel-eu"),
    "translate3_ft_laptop_s2": ("reader 1 on the laptop, sample 2 at temperature 0.8", "nobel-eu"),
    "translate3_ft_laptop_s3": ("reader 1 on the laptop, sample 3 at temperature 0.8", "nobel-eu"),
    "translate3_ft_laptop_s4": ("reader 1 on the laptop, sample 4 at temperature 0.8", "nobel-eu"),
    "translate3_ft_laptop_s5": ("reader 1 on the laptop, sample 5 at temperature 0.8", "nobel-eu"),
    "translate4_ft": (
        "Apertus v1.5 8B, fine-tuned reader of the fourth format (scope, lifetime), A100",
        "nobel-eu",
    ),
    "translate4_ft_laptop": ("the fourth-format reader, 4-bit GGUF on the laptop", "nobel-eu"),
}
OUTCOMES = {
    "right": "the reader's line means what the sentence means (status, links, nodes, limits, preferences in order, scope, lifetime)",
    "silent": "the reader applied the sentence with another meaning, without saying so",
    "part_only": "the reader carried a part and said that a part was not carried",
    "flagged": "the reader did not apply the sentence and said so (unsupported, no_instruction or unresolved)",
    "handed_on": "a sentence outside the language that the reader handed on to the decider (unsupported)",
    "other_refusal": "a sentence that should not be applied, refused with another status than expected",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, by_set = [], Counter()
    for name, (how, topology) in SETS.items():
        path = ROOT / "data" / "instructions" / f"{name}.jsonl"
        if not path.exists():
            continue
        for row in read_rows([path]):
            spec = Spec.from_json(row["expect"])
            rows.append({"id": f"{name}:{by_set[name]:04d}", "set": name, "lang": row.get("lang", "en"),
                         "kind": row.get("kind", ""), "text": row["text"], "topology": topology,
                         "means": format_spec(spec, 4) if spec.applies else spec.status, "spec": spec.to_json(),
                         "written_by": how} | ({"item": row["item"]} if "item" in row else {}))  # fmt: skip
            by_set[name] += 1
    (OUT / "evaluation.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                         encoding="utf-8", newline="\n")  # fmt: skip
    responses, by_reader = [], Counter()
    for reader in READERS:
        answers = {}
        for topology in ("nobel-eu", "swiss"):
            cached = Answers(reader, topology)  # one cache file; the key carries the node list
            if cached.cache:
                answers[topology] = cached
        if not answers:
            continue
        for row in rows:
            cached = answers.get(row["topology"])
            spec = cached.spec(row["text"]) if cached else None
            if spec is None:
                continue
            expect = Spec.from_json(row["spec"])
            responses.append({"id": row["id"], "reader": reader, "line": format_spec(spec, 4) if spec.applies else spec.status,
                              "outcome": outcome(expect, spec)})  # fmt: skip
            by_reader[reader] += 1
    (OUT / "responses.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in responses),
                                        encoding="utf-8", newline="\n")  # fmt: skip
    metadata = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "license": "CDLA-Permissive-2.0 for every instance; the sentences are synthetic (AI-written or AI-translated from briefs, or the author's, partly with ChatGPT 6.1 Sol)",
        "no_personal_data": True,
        "topologies": {"nobel-eu": "SNDlib reference network, 28 nodes, 41 links (shipped with Optical Networking Gym)",
                       "swiss": "24 Swiss cities, 33 links along the main corridors, built for this project from public geography"},
        "sets": {name: {"rows": by_set[name], "written_by": how, "topology": topology}
                 for name, (how, topology) in SETS.items() if by_set[name]},
        "readers": {name: {"rows": by_reader[name], "model": description} for name, (description, _) in READERS.items()
                    if by_reader[name]},
        "outcomes": OUTCOMES,
        "line_format": "avoid=<links,nodes>; via=<node>; hops=<n|any>; km=<n|any>; path=<0-4|any>; prefer=<hops,km,load,slots>; "
                       "scope=<any|rate:G|from:node|to:node>; until=<open|Nh>; rest=<none|more> | unsupported | no_instruction",
    }  # fmt: skip
    (OUT / "metadata.json").write_text(
        json.dumps(metadata, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"evaluation: {len(rows)} instructions in {len([s for s in by_set if by_set[s]])} sets; "
          f"responses: {len(responses)} from {len(by_reader)} readers")  # fmt: skip
    for reader, n in by_reader.items():
        print(f"  {reader}: {n}")


if __name__ == "__main__":
    main()
