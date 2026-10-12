"""Test instructions of the fourth format: the independently written routing sentences of the third
round with a scope or lifetime phrase written by another separate AI instance
(``data/instructions/v4_scope_source.json``), attached before or after the sentence.

    uv run python src/corpora4_tests.py      # data/instructions/v4_{en,de,fr,it}.jsonl

Each phrase is attached to ``PER_PHRASE`` routing sentences drawn from the language's ``v3_<lang>``
rows (distinct texts, every clause kind and combination), with the placeholders filled: ``{g}`` a
bit rate of the preset, ``{f}``/``{t}`` a node in the language's own name, ``{h}`` a number of
hours. The expected line is the sentence's spec with the scope and lifetime added. A row's
``kind`` is the scope kind; ``group`` the routing combination it was attached to.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from corpora import LANGUAGES
from generate import write_jsonl
from spec import RATES, Spec, load_topology
from translate import read_rows

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("en", "de", "fr", "it")
PER_PHRASE = 4
JOIN_BEFORE = ("{clause}, {sentence}", "{clause}: {sentence}", "{clause}. {sentence}")
JOIN_AFTER = ("{sentence} {clause}.", "{sentence}, {clause}", "{sentence} ({clause})")


def build(seed: int = 4) -> dict[str, list[dict]]:
    topology = load_topology("nobel-eu")
    source = json.loads((ROOT / "data" / "instructions" / "v4_scope_source.json").read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for lang in LANGS:
        rng = random.Random(f"v4-{lang}-{seed}")
        names = LANGUAGES[lang]["names"] if lang != "en" else {}
        sentences = {r["text"]: r for r in read_rows([ROOT / "data" / "instructions" / f"v3_{lang}.jsonl"])}
        texts = sorted(sentences)
        rows, seen = [], set()
        for kind, phrases in source[lang].items():
            for phrase in phrases:
                for sentence in rng.sample(texts, PER_PHRASE):
                    base = sentences[sentence]
                    expect = Spec.from_json(base["expect"])
                    f, t = rng.sample(topology.nodes, 2)
                    fills = {
                        "g": rng.choice(RATES),
                        "f": names.get(f, f),
                        "t": names.get(t, t),
                        "h": rng.randint(1, 72),
                    }
                    clause = phrase.format(**fills)
                    if rng.random() < 0.5:
                        join = rng.choice(JOIN_BEFORE)
                        rest = (
                            sentence if join.startswith("{clause}.") else sentence[0].lower() + sentence[1:]
                        )
                        text = join.format(clause=clause[0].upper() + clause[1:], sentence=rest)
                    else:
                        text = rng.choice(JOIN_AFTER).format(sentence=sentence.rstrip("."), clause=clause)
                    if text in seen:
                        continue
                    seen.add(text)
                    scope = {"rate": f"rate:{fills['g']}", "from": f"from:{f}", "to": f"to:{t}"}.get(kind)
                    until = fills["h"] if kind == "hours" else None
                    spec = Spec(**{**expect.__dict__, "scope": scope, "until": until})
                    rows.append({"text": text, "expect": spec.to_json(), "set": f"v4_{lang}", "lang": lang, "kind": kind,
                                 "group": base.get("kind", "")})  # fmt: skip
        out[f"v4_{lang}"] = rows
    return out


if __name__ == "__main__":
    for name, rows in build().items():
        write_jsonl(ROOT / "data" / "instructions" / f"{name}.jsonl", rows)
        print(f"{name}: {len(rows)} instructions", dict(Counter(r["kind"] for r in rows)))
        print("  ", rows[0]["text"], "->", rows[0]["expect"].get("scope"), rows[0]["expect"].get("until"))
