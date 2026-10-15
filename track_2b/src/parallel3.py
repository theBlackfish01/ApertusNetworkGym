"""The same 60 instructions in eight languages and scripts: what the language alone does to the readers.

The English items were written blind by a separate AI instance and each translation by another one,
from the English sentences only (``data/instructions/parallel_<code>_source.txt``). Every line keeps
its English item's label, so the eight versions of an item mean the same line and differ only in
language and script. Urdu appears twice, in its own script and in Latin letters; Hindi, close to
Urdu as spoken, in Devanagari; Arabic shares the script of written Urdu. German, French and Italian
are the languages the readers were trained on besides English; the other four never occur in
training.

    uv run python src/parallel3.py              # data/instructions/parallel_<code>[_standing].jsonl
    uv run python src/parallel3.py --score      # results/design/parallel.json, docs/figures/languages.png

``--score`` reads the laptop readers' answer caches (filled by ``translate.py parse``): reader 1
and the untrained 8B with 15 examples on the 40 per-request items, the fourth-format reader on all
60. Per language and reader: right of n with a 95 % Wilson interval; against English, item by item,
an exact McNemar test (two-sided binomial on the items one version gets right and the other wrong);
and for every wrong answer to an instruction that should be applied, whether it names a different
city (the set of cities in the line differs) or gets only a field wrong.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from corpora3_owner import build
from generate import write_jsonl
from readers3 import Answers, outcome
from spec import Spec, format_spec, load_topology

ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = ROOT / "data" / "instructions"
LANGUAGES = {  # code -> label, in the order of the figure
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "ur_latn": "Urdu, Latin script",
    "ur_arab": "Urdu, Urdu script",
    "hi": "Hindi, Devanagari",
    "ar": "Arabic",
}
TRAINED = ("en", "de", "fr", "it")
READERS = {
    "translate3_ft_laptop": "Reader 1 (fine-tuned)",
    "translate4_ft_laptop": "Full-format reader (fine-tuned)",
    "translate3_few_laptop": "Apertus 8B, 15 examples, no training",
}
FULL = "translate4_ft_laptop"  # the only reader of standing policies
CONTRASTS = (
    ("ur_latn", "ur_arab", "one language, two scripts"),
    ("ur_arab", "hi", "Urdu and Hindi, two scripts"),
)


def rows(topology) -> dict[str, list[dict]]:
    out = {}
    for code in LANGUAGES:
        made = build(topology, f"parallel_{code}", INSTRUCTIONS / f"parallel_{code}_source.txt")
        if len(made) != 60:
            raise SystemExit(f"parallel_{code}: {len(made)} lines, expected 60")
        for item, row in enumerate(made, 1):
            row["item"] = item
        out[code] = made
    expects = {code: [json.dumps(r["expect"], sort_keys=True) for r in made] for code, made in out.items()}
    if any(e != expects["en"] for e in expects.values()):
        raise SystemExit("the versions of an item must mean the same line")
    return out


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    centre, half = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided p of b items right only in one version against c right only in the other."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def cities(spec: Spec) -> set[str]:
    named = {n for link in spec.avoid for n in link} | set(spec.nodes) | set(spec.via)
    if spec.scope and spec.scope.split(":")[0] in ("from", "to"):
        named.add(spec.scope.split(":", 1)[1])
    return named


def error(expect: Spec, got: Spec, result: str) -> str:
    if result == "right":
        return ""
    if not expect.applies:
        return "applied" if got.applies else "other refusal"
    if not got.applies:
        return "not applied"
    return "wrong city" if cities(got) != cities(expect) else "wrong field"


def score(by_lang: dict[str, list[dict]]) -> dict:
    answers = {name: Answers(name) for name in READERS}
    lines, right = [], {}  # right[(reader, code)] = {item: bool}
    for code, made in by_lang.items():
        for row in made:
            standing = row["set"].endswith("_standing")
            expect = Spec.from_json(row["expect"])
            entry = {"item": row["item"], "lang": code, "kind": row["kind"], "text": row["text"],
                     "expect": format_spec(expect, 4) if expect.applies else expect.status}  # fmt: skip
            for name in READERS:
                if standing and name != FULL:
                    continue
                got = answers[name].spec(row["text"])
                if got is None:
                    raise SystemExit(f"no cached answer of {name} for {row['text']!r}")
                result = outcome(expect, got)
                entry[name] = {"answer": format_spec(got, 4 if name == FULL else 3) if got.applies else got.status,
                               "outcome": result, "error": error(expect, got, result)}  # fmt: skip
                right.setdefault((name, code), {})[row["item"]] = result == "right"
            lines.append(entry)
    groups = {"request": range(1, 41), "in_language": [*range(1, 29), *range(41, 61)], "refusal": range(29, 41),
              "standing": range(41, 61), "all": range(1, 61)}  # fmt: skip
    summary, tests = [], []
    for name in READERS:
        for group, items in groups.items():
            if name != FULL and group in ("standing", "all"):
                continue
            items = [i for i in items if name == FULL or i <= 40]
            for code in LANGUAGES:
                marks = [right[(name, code)][i] for i in items]
                k, n = sum(marks), len(marks)
                low, high = wilson(k, n)
                errors = Counter(e[name]["error"] for e in lines if e["lang"] == code and name in e
                                 and e["item"] in items and e[name]["error"])  # fmt: skip
                summary.append({"reader": name, "group": group, "lang": code, "n": n, "right": k,
                                "share": round(k / n, 4), "ci95": [round(low, 4), round(high, 4)],
                                "errors": dict(sorted(errors.items()))})  # fmt: skip
            pairs = [("en", code, "against English") for code in LANGUAGES if code != "en"] + list(CONTRASTS)
            for a, b, what in pairs:
                only_a = sum(right[(name, a)][i] and not right[(name, b)][i] for i in items)
                only_b = sum(right[(name, b)][i] and not right[(name, a)][i] for i in items)
                tests.append({"reader": name, "group": group, "a": a, "b": b, "what": what, "n": len(items),
                              "right_only_a": only_a, "right_only_b": only_b, "p_exact": round(mcnemar(only_a, only_b), 4)})  # fmt: skip
    return {
        "lines": lines,
        "summary": summary,
        "tests": tests,
        "metadata": {
            "command": "src/parallel3.py --score",
            "items": 60,
            "languages": LANGUAGES,
            "trained": list(TRAINED),
            "readers": READERS,
            "groups": {
                "request": "items 1-40, one request",
                "in_language": "items 1-28 and 41-60, a line the language carries",
                "refusal": "items 29-40, the language cannot carry it (6) or no instruction (6)",
                "standing": "items 41-60, a scope or a lifetime",
                "all": "items 1-60",
            },
            "note": (
                "laptop readers: 4-bit base, llama.cpp b11558, grammar-constrained, greedy; sentences and "
                "translations by separate AI instances, not checked by native speakers"
            ),
        },
    }


def figure(data: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = {
        "translate3_ft_laptop": "#2a78d6",
        "translate4_ft_laptop": "#eb6834",
        "translate3_few_laptop": "#1baf7a",
    }
    markers = {"translate3_ft_laptop": "o", "translate4_ft_laptop": "s", "translate3_few_laptop": "^"}
    codes = list(LANGUAGES)
    fig, ax = plt.subplots(figsize=(7.4, 2.5))
    plt.rcParams.update({"font.size": 7.5})
    ax.axvspan(len(TRAINED) - 0.5, len(codes) - 0.5, color="#f0efec", zorder=0, lw=0)
    for x, text in ((1.5, "trained languages"), (5.5, "never in training")):
        ax.text(
            x,
            1.035,
            text,
            ha="center",
            va="bottom",
            fontsize=6.8,
            color="#52514e",
            transform=ax.get_xaxis_transform(),
        )
    for offset, name in zip((-0.2, 0.0, 0.2), READERS, strict=True):
        rows = {r["lang"]: r for r in data["summary"] if r["reader"] == name and r["group"] == "request"}
        xs = [i + offset for i in range(len(codes))]
        ys = [100 * rows[c]["share"] for c in codes]
        low = [100 * (rows[c]["share"] - rows[c]["ci95"][0]) for c in codes]
        high = [100 * (rows[c]["ci95"][1] - rows[c]["share"]) for c in codes]
        ax.errorbar(xs, ys, yerr=[low, high], fmt=markers[name], ms=4.5, color=colours[name], ecolor=colours[name],
                    elinewidth=1, capsize=0, lw=0, label=READERS[name], zorder=3, markeredgecolor="#fcfcfb", markeredgewidth=0.6)  # fmt: skip
    ax.set_xticks(range(len(codes)), [LANGUAGES[c].replace(", ", ",\n") for c in codes], fontsize=6.6)
    ax.set_xlim(-0.5, len(codes) - 0.5)
    ax.set_ylim(0, 105)
    ax.set_ylabel("right, % of 40 items", fontsize=7.5)
    ax.yaxis.grid(True, color="#e1e0d9", lw=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c3c2b7")
    ax.tick_params(axis="y", labelsize=7, colors="#52514e")
    ax.tick_params(axis="x", colors="#0b0b0b", length=0)
    ax.legend(fontsize=6.6, frameon=False, loc="lower left", ncol=3, bbox_to_anchor=(0.0, -0.02))
    fig.tight_layout(pad=0.6)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220, facecolor="#ffffff")
    print(f"wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--score", action="store_true", help="results/design/parallel.json and the figure")
    args = parser.parse_args()
    by_lang = rows(load_topology("nobel-eu"))
    if not args.score:
        for made in by_lang.values():
            for set_name in sorted({r["set"] for r in made}):
                part = [r for r in made if r["set"] == set_name]
                write_jsonl(INSTRUCTIONS / f"{set_name}.jsonl", part)
                print(
                    f"{set_name}: {len(part)} instructions",
                    dict(sorted(Counter(r["kind"] for r in part).items())),
                )
        return
    data = score(by_lang)
    out = ROOT / "results" / "design" / "parallel.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
    for r in data["summary"]:
        if r["group"] in ("request", "standing"):
            print(f"{r['reader']:22s} {r['group']:8s} {r['lang']:8s} {r['right']:2d}/{r['n']}  "
                  f"[{100 * r['ci95'][0]:.0f}, {100 * r['ci95'][1]:.0f}]  {r['errors']}")  # fmt: skip
    for t in data["tests"]:
        if t["group"] == "request":
            print(
                f"{t['reader']:22s} {t['a']:8s} vs {t['b']:8s} only-a {t['right_only_a']:2d} only-b {t['right_only_b']:2d} p={t['p_exact']}"
            )
    figure(data, ROOT / "docs" / "figures" / "languages.png")


if __name__ == "__main__":
    main()
