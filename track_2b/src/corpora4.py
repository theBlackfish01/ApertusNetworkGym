"""Training data of the fourth format: standing policies with a scope and a lifetime.

The records of the third round (``corpora3.build_training``) are kept and re-answered in the
fourth format (``scope=any; until=open``), and the same generator supplies sentences to which a
scope clause (one bit rate, requests from a node, requests to a node), a lifetime clause (a
number of hours, or until further notice) or both are attached, before or after the routing
sentence. The clause wording below is the author's, in four languages; the test phrases are
written by a separate AI instance (``data/instructions/v4_scope_source.json``).

    uv run python src/corpora4.py            # data/translate4/s1/{train,heldout_*}.jsonl
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path

from corpora import TRAIN_OUTSIDE
from corpora3 import (
    ATOMS,
    PREF,
    TRAIN_PAIRS,
    answer,
    build_training,
    compose,
    concrete,
    english_wording,
    values,
)
from generate import write_jsonl
from spec import RATES, UNKNOWN, Spec, Topology, format_spec, load_topology, parse_spec
from translate import messages

ROOT = Path(__file__).resolve().parents[1]
SCOPED = 1500  # records with a scope or a lifetime clause (or both)
UNKNOWN_SCOPE = 100  # a scope that names a place outside the network
HELDOUT = 150
CLAUSES: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "rate": (
            "for {g}G services",
            "only for {g}G requests",
            "this applies to {g} Gb/s demands only",
            "{g}G traffic only",
            "for all {g}G circuits",
            "applies to {g}G only",
        ),
        "from": (
            "for everything leaving {f}",
            "for all services from {f}",
            "for requests starting in {f}",
            "for traffic out of {f}",
            "{f}-originated demands only",
        ),
        "to": (
            "for traffic going to {t}",
            "for demands terminating in {t}",
            "for everything ending in {t}",
            "for all services towards {t}",
            "requests bound for {t} only",
        ),
        "hours": (
            "for the next {h} hours",
            "for {h} hours",
            "valid {h}h",
            "during the next {h} hours",
            "for the coming {h} hours",
            "{h}h from now",
        ),
        "open": (
            "until further notice",
            "until I say otherwise",
            "from now on",
            "until revoked",
            "standing order",
            "until told otherwise",
        ),
    },
    "de": {
        "rate": (
            "nur für {g}G-Dienste",
            "gilt für {g}G-Anfragen",
            "nur bei {g} Gbit/s",
            "für alle {g}G-Verbindungen",
        ),
        "from": ("für alles, was von {f} ausgeht", "für Anfragen ab {f}", "für Verkehr aus {f}"),
        "to": ("für Verbindungen nach {t}", "für alles, was in {t} endet", "für Verkehr Richtung {t}"),
        "hours": (
            "für die nächsten {h} Stunden",
            "{h} Stunden lang",
            "in den kommenden {h} Stunden",
            "gültig {h}h",
        ),
        "open": ("bis auf Weiteres", "ab sofort bis auf Widerruf", "bis ich etwas anderes sage", "ab jetzt"),
    },
    "fr": {
        "rate": (
            "uniquement pour les services {g}G",
            "pour les demandes {g}G",
            "seulement en {g} Gbit/s",
            "pour tous les circuits {g}G",
        ),
        "from": (
            "pour tout ce qui part de {f}",
            "pour les demandes au départ de {f}",
            "pour le trafic issu de {f}",
        ),
        "to": (
            "pour le trafic vers {t}",
            "pour tout ce qui aboutit à {t}",
            "pour les demandes à destination de {t}",
        ),
        "hours": (
            "pendant les {h} prochaines heures",
            "pour {h} heures",
            "durant {h}h",
            "pour les {h} heures à venir",
        ),
        "open": (
            "jusqu'à nouvel ordre",
            "à partir de maintenant",
            "jusqu'à révocation",
            "jusqu'à avis contraire",
        ),
    },
    "it": {
        "rate": (
            "solo per i servizi {g}G",
            "per le richieste {g}G",
            "solo a {g} Gbit/s",
            "per tutti i circuiti {g}G",
        ),
        "from": (
            "per tutto ciò che parte da {f}",
            "per le richieste in partenza da {f}",
            "per il traffico da {f}",
        ),
        "to": (
            "per il traffico verso {t}",
            "per tutto ciò che termina a {t}",
            "per le richieste dirette a {t}",
        ),
        "hours": ("per le prossime {h} ore", "per {h} ore", "nelle prossime {h} ore", "valido {h}h"),
        "open": ("fino a nuovo avviso", "da ora in poi", "fino a revoca", "fino a nuovo ordine"),
    },
}
JOINS = {
    "before": ("{clause}, {sentence}", "{clause}: {sentence}", "{clause} - {sentence}"),
    "after": ("{sentence} {clause}.", "{sentence} ({clause})", "{sentence}, {clause}"),
}


def _capitalise(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def attach(
    sentence: str, lang: str, fills: dict, rng: random.Random, kinds: tuple[str, ...]
) -> tuple[str, dict]:
    """The sentence with the given scope/lifetime clauses attached; the slot values they mean."""
    names = {"g": fills["g"], "f": fills["f"], "t": fills["t"], "h": fills["h"]}
    slots: dict = {}
    text = sentence
    for kind in kinds:
        clause = rng.choice(CLAUSES[lang][kind]).format(**names)
        where = rng.choice(("before", "after"))
        if where == "before":
            text = rng.choice(JOINS["before"]).format(
                clause=_capitalise(clause), sentence=text[0].lower() + text[1:]
            )
        else:
            text = rng.choice(JOINS["after"]).format(sentence=text.rstrip("."), clause=clause)
        if kind == "rate":
            slots["scope"] = f"rate:{fills['g']}"
        elif kind == "from":
            slots["scope"] = f"from:{fills['f_node']}"
        elif kind == "to":
            slots["scope"] = f"to:{fills['t_node']}"
        elif kind == "hours":
            slots["until"] = fills["h"]
    return text, slots


def scope_values(topology: Topology, rng: random.Random, lang: str, names: dict) -> dict:
    f, t = rng.sample(topology.nodes, 2)
    return {"g": rng.choice(RATES), "f": names.get(f, f), "t": names.get(t, t), "f_node": f, "t_node": t,
            "h": rng.randint(1, 72)}  # fmt: skip


def to_v4(line: str) -> str:
    spec = parse_spec(line)
    return line if not spec.applies else format_spec(spec, 4)


def build(topology: Topology, seed: int) -> dict[str, list[dict]]:
    from corpora import LANGUAGES

    rng = random.Random(f"translator-data-4-{seed}")
    english = english_wording()
    base = build_training(topology, seed)
    kinds_of_scope = (("rate",), ("from",), ("to",), ("hours",), ("open",), ("rate", "hours"), ("from", "hours"),
                      ("to", "open"), ("rate", "open"))  # fmt: skip
    combos = [(kind,) for kind in ATOMS if kind != "path_index"] + list(TRAIN_PAIRS) + [(PREF, PREF)]

    def scoped(count: int) -> list[tuple[str, str, str]]:
        out = []
        for _ in range(count):
            lang = rng.choice(("en", "en", "de", "fr", "it"))
            names = LANGUAGES[lang]["names"] if lang != "en" else {}
            fills, kinds = values(topology, rng), concrete(rng.choice(combos), rng)
            sentence = compose(kinds, lang, fills, rng, english)
            scope_kinds = rng.choice(kinds_of_scope)
            text, slots = attach(sentence, lang, scope_values(topology, rng, lang, names), rng, scope_kinds)
            spec = parse_spec(answer(kinds, fills))
            spec = Spec(**{**spec.__dict__, "scope": slots.get("scope"), "until": slots.get("until")})
            out.append((text, format_spec(spec, 4), f"{lang}: scoped {'+'.join(scope_kinds)}"))
        return out

    pairs = [
        (r["meta"]["text"], to_v4(r["completion"][0]["content"]), r["meta"]["kind"]) for r in base["train"]
    ]
    pairs += scoped(SCOPED)
    for _ in range(UNKNOWN_SCOPE):  # a scope naming a place that is not a node
        lang = rng.choice(("en", "de", "fr", "it"))
        names = LANGUAGES[lang]["names"] if lang != "en" else {}
        fills, kinds = values(topology, rng), concrete(rng.choice(combos), rng)
        sentence = compose(kinds, lang, fills, rng, english)
        sv = scope_values(topology, rng, lang, names)
        kind = rng.choice(("from", "to"))
        sv[kind] = rng.choice(TRAIN_OUTSIDE)
        sv[f"{kind}_node"] = UNKNOWN
        text, slots = attach(sentence, lang, sv, rng, (kind,))
        spec = parse_spec(answer(kinds, fills))
        spec = Spec(**{**spec.__dict__, "scope": slots["scope"]})
        pairs.append((text, format_spec(spec, 4), f"{lang}: scoped unknown place"))
    rng.shuffle(pairs)

    def record(index: int, text: str, line: str, kind: str) -> dict:
        return {"id": f"W{index:05d}", "prompt": messages(text, topology, version=4),
                "completion": [{"role": "assistant", "content": line}], "meta": {"text": text, "kind": kind}}  # fmt: skip

    data = {"train": [record(i, *pair) for i, pair in enumerate(pairs)]}
    # named as train.py expects its three held-out files; this one holds scoped sentences
    data["heldout_paraphrase"] = [record(i, *pair) for i, pair in enumerate(scoped(HELDOUT))]
    for name in ("heldout_indist", "heldout_pairs"):
        data[name] = [record(i, r["meta"]["text"], to_v4(r["completion"][0]["content"]), r["meta"]["kind"])
                      for i, r in enumerate(base[name])]  # fmt: skip
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "translate4")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    data = build(load_topology("nobel-eu"), args.seed)
    for name, records in data.items():
        write_jsonl(args.out / f"s{args.seed}" / f"{name}.jsonl", records)
    kinds = Counter(r["meta"]["kind"].split(": ")[-1].split(" ")[0] for r in data["train"])
    print(f"train: {len(data['train'])} records; {dict(kinds.most_common(6))}")
    for name in ("heldout_paraphrase", "heldout_indist", "heldout_pairs"):
        print(f"{name}: {len(data[name])}")
    for r in data["train"][:400]:
        if "scoped" in r["meta"]["kind"]:
            print(" ", r["meta"]["text"], "->", r["completion"][0]["content"])
            break


if __name__ == "__main__":
    main()
