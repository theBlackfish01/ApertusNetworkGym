"""Instructions beyond the dataset's own wording: probes for both arms, and the translator's data.

The dataset of ``generate.py`` words every intent with ten English templates. That is too easy
to tell a translator from a keyword parser, and it says nothing about other languages or about
instructions that cannot be applied. This module builds, from the held-out records (unseen
traffic, seeds 107 and 108) and without the simulator:

probe sets, ``data/probes/<set>.jsonl`` (dataset record format, so ``evaluate.py offline --data
data/probes --splits <set>`` scores any policy on them):

    independent    every held-out instruction re-worded with ``data/instructions/independent_source.json``,
                   written by a separate model instance that never saw this repository's wording
    de fr it       the same instructions in German, French and Italian, with the city names of
                   that language (Mailand, Vienne, Monaco di Baviera)
    gsw            Swiss German, a sample (no standard spelling: treat as a stress test)
    noisy          the independent wording in lower case, one city name misspelt, a sample
    faulty         an avoid-link instruction that cannot be resolved: two nodes of a candidate path
                   that are not adjacent, or a place that is not in the network
    out_of_scope   an instruction the system does not support (independent source)

``data/instructions/<set>.jsonl``: the distinct instruction texts of each set with the spec they
mean (``text``, ``expect``, ``set``, ``lang``, ``kind``), for ``translate.py score``;
``templates.jsonl`` holds those of the three held-out dataset splits.

``data/translate/``: prompt/completion records for fine-tuning the translator with ``train.py``:
the training instructions of the dataset, plus instructions it must refuse and places it must
mark unknown. Their wording (``TRAIN_UNSUPPORTED``, ``TRAIN_OUTSIDE``) was written before the
independent source existed and shares no text with the test sets.

``data/fewshot/decider.jsonl``: seven solved training records for the few-shot decider.

    uv run python src/corpora.py

The German, French, Italian and Swiss German wording was drafted and reviewed by AI models
(disclosed in the technical report); it is test data only and is never trained on.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from generate import read_jsonl, write_jsonl
from intents import LINK_FORMS, NO_INTENT, PARAPHRASES, Intent, admissible_paths, teacher_choice
from prompt import chat_messages, format_choice
from spec import UNKNOWN, Spec, Topology, format_spec, from_intent, load_topology, mention_order
from translate import messages
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]
HELDOUT = ("heldout_indist", "heldout_paraphrase", "heldout_pairs")
KIND = {"avoid_link": "I1", "fewest_hops": "I2", "least_loaded": "I3", "fewest_slots": "I4"}
SAMPLE = 600  # records in the sampled probe sets

# Sentences per intent; {a} and {b} are the two ends of the link, in the names of the language.
LANGUAGES: dict[str, dict] = {
    "de": {
        "names": {"Athens": "Athen", "Belgrade": "Belgrad", "Brussels": "Brüssel", "Copenhagen": "Kopenhagen",
                  "Milan": "Mailand", "Munich": "München", "Prague": "Prag", "Rome": "Rom",
                  "Strasbourg": "Straßburg", "Vienna": "Wien", "Warsaw": "Warschau", "Zurich": "Zürich"},
        "I1": (
            "Die Strecke {a}–{b} wird gewartet; bitte nicht darüber routen.",
            "Meide für diese Anfrage die direkte Verbindung zwischen {a} und {b}.",
            "Der Abschnitt {a}-{b} darf für diesen Dienst nicht benutzt werden.",
            "Bitte den Link {a}-{b} umgehen.",
            "Wartungsfenster auf {a}–{b}: diesen Lichtpfad nicht darüber führen.",
        ),
        "I2": (
            "Latenzkritisch: nimm den Pfad mit den wenigsten Hops, der passt.",
            "Verwende den realisierbaren Pfad mit der geringsten Anzahl an Hops.",
            "Die Zahl der Hops soll so klein wie möglich sein.",
            "Möglichst wenige Teilstrecken für diesen Dienst.",
        ),
        "I3": (
            "Last verteilen: nimm den am wenigsten ausgelasteten Pfad, der passt.",
            "Wähle den Pfad mit den meisten freien Slots.",
            "Nimm die Route mit dem meisten freien Spektrum.",
            "Stark belegte Routen schonen; den leersten möglichen Pfad verwenden.",
        ),
        "I4": (
            "Spektrum sparen: nimm die Variante, die am wenigsten Slots benötigt.",
            "Dieser Dienst soll so wenige Slots wie möglich belegen.",
            "Wähle den Pfad, dessen Modulation die wenigsten Slots braucht.",
            "Spektrum ist knapp; die schmalste mögliche Zuweisung wählen.",
        ),
    },
    "fr": {
        "names": {"Athens": "Athènes", "Barcelona": "Barcelone", "Brussels": "Bruxelles",
                  "Copenhagen": "Copenhague", "Frankfurt": "Francfort", "Hamburg": "Hambourg",
                  "London": "Londres", "Vienna": "Vienne", "Warsaw": "Varsovie"},
        "I1": (
            "La liaison {a}–{b} est en maintenance ; ne pas l'emprunter.",
            "Évitez le lien entre {a} et {b} pour cette demande.",
            "Ce service ne doit pas passer par le tronçon {a}-{b}.",
            "Contournez la liaison {a}-{b}.",
            "Fenêtre de maintenance sur {a}–{b} : ce chemin optique ne doit pas y passer.",
        ),
        "I2": (
            "Sensible à la latence : prendre le chemin réalisable avec le moins de sauts.",
            "Utilisez le chemin comportant le plus petit nombre de sauts.",
            "Réduisez au minimum le nombre de sauts pour ce service.",
            "Le moins de liens traversés possible pour cette connexion.",
        ),
        "I3": (
            "Répartir la charge : choisir le chemin réalisable le moins chargé.",
            "Prenez le chemin qui a le plus de slots libres.",
            "Utilisez la route où il reste le plus de spectre libre.",
            "Épargnez les routes encombrées ; prenez le chemin le plus vide possible.",
        ),
        "I4": (
            "Économiser le spectre : choisir l'option qui demande le moins de slots.",
            "Ce service doit occuper le moins de slots possible.",
            "Prenez le chemin dont la modulation nécessite le moins de slots.",
            "Le spectre est rare ; choisissez l'allocation la plus étroite possible.",
        ),
    },
    "it": {
        "names": {"Athens": "Atene", "Barcelona": "Barcellona", "Belgrade": "Belgrado", "Berlin": "Berlino",
                  "Brussels": "Bruxelles", "Copenhagen": "Copenaghen", "Dublin": "Dublino",
                  "Frankfurt": "Francoforte", "Hamburg": "Amburgo", "London": "Londra", "Lyon": "Lione",
                  "Milan": "Milano", "Munich": "Monaco di Baviera", "Paris": "Parigi", "Prague": "Praga",
                  "Rome": "Roma", "Stockholm": "Stoccolma", "Strasbourg": "Strasburgo", "Warsaw": "Varsavia",
                  "Zagreb": "Zagabria", "Zurich": "Zurigo"},
        "I1": (
            "Il collegamento {a}–{b} è in manutenzione; non instradare su di esso.",
            "Evita il link tra {a} e {b} per questa richiesta.",
            "Questo servizio non deve passare per la tratta {a}-{b}.",
            "Aggira il collegamento {a}-{b}.",
            "Finestra di manutenzione sul collegamento {a}–{b}: questo lightpath non deve attraversarlo.",
        ),
        "I2": (
            "Sensibile alla latenza: usa il percorso fattibile con il minor numero di salti.",
            "Usa il percorso con meno salti tra quelli disponibili.",
            "Riduci al minimo il numero di salti per questo servizio.",
            "Attraversa il minor numero possibile di collegamenti.",
        ),
        "I3": (
            "Distribuisci il carico: scegli il percorso fattibile meno carico.",
            "Scegli il percorso con più slot liberi.",
            "Usa la rotta con più spettro libero.",
            "Risparmia le rotte congestionate; prendi il percorso più vuoto possibile.",
        ),
        "I4": (
            "Risparmia spettro: scegli l'opzione che richiede meno slot.",
            "Questo servizio deve occupare il minor numero possibile di slot.",
            "Prendi il percorso la cui modulazione richiede meno slot.",
            "Lo spettro è scarso; scegli l'allocazione più stretta possibile.",
        ),
    },
    "gsw": {
        "names": {"Athens": "Athen", "Belgrade": "Belgrad", "Brussels": "Brüssel", "Copenhagen": "Kopehage",
                  "Milan": "Mailand", "Munich": "Münche", "Prague": "Prag", "Rome": "Rom",
                  "Strasbourg": "Strassburg", "Vienna": "Wien", "Warsaw": "Warschau", "Zurich": "Züri"},
        "I1": (
            "D Strecki {a}–{b} wird gwartet; bitte nöd drüber leite.",
            "Für die Aafrag di diräkt Verbindig zwüsche {a} und {b} vermiide.",
            "De Link {a}-{b} dörf für de Dienscht nöd bruucht werde.",
            "Bitte um d Strecki {a}-{b} ume leite.",
        ),
        "I2": (
            "Latenzkritisch: nimm de Pfad mit de wenigschte Hops, wo passt.",
            "D Aazahl Hops söll so chlii wie möglich sii.",
            "Möglichscht wenig Teilstrecke für de Dienscht.",
        ),
        "I3": (
            "Lascht verteile: nimm de Pfad, wo am wenigschte uusglaschtet isch.",
            "Wähl de Pfad mit de meischte freie Slots.",
            "Nimm d Route mit em meischte freie Spektrum.",
        ),
        "I4": (
            "Spektrum spare: nimm d Variante, wo am wenigschte Slots bruucht.",
            "De Dienscht söll so wenig Slots wie möglich belegge.",
            "Wähl de Pfad, wo d Modulation am wenigschte Slots bruucht.",
        ),
    },
}  # fmt: skip

# Training only: what the fine-tuned translator must refuse. {a} is a node, {n} a number.
TRAIN_UNSUPPORTED = (
    "Use {mod} for this connection.",
    "Route this service through {a}.",
    "Do not pass through {a}.",
    "Keep this lightpath away from {a} altogether.",
    "Set up a protection path as well.",
    "This customer has priority over the others.",
    "Encrypt this connection.",
    "Use the shortest path in kilometres.",
    "Start at slot {n}.",
    "Use path {n}.",
    "Reject this request.",
    "Delay the setup until tomorrow.",
    "What is the current load on the network?",
    "The launch power should be {n} dBm.",
    "Limit the route to at most {n} hops.",
    "Keep the latency below {n} ms.",
    "Reserve {n} extra slots as a guard band.",
    "Thanks, that is all.",
    "Tear down the old connection first.",
    "Use the same route as the previous request.",
    "Pick the cheapest route.",
    "Make sure the path is disjoint from the one to {a}.",
    "Prefer routes through {a}.",
    "Send half of the traffic over each of two paths.",
    "Schedule this for the maintenance window on Sunday.",
)
MODULATIONS = ("BPSK", "QPSK", "8QAM", "16QAM", "32QAM", "64QAM")
TRAIN_OUTSIDE = ("Helsinki", "Lisbon", "Porto", "Marseille", "Naples", "Sofia", "Bucharest", "Riga", "Tallinn",
                 "Valencia")  # fmt: skip
TEST_OUTSIDE = (
    "Geneva",
    "Bern",
    "Basel",
    "Lausanne",
    "Lugano",
    "Edinburgh",
    "Seville",
    "Kyiv",
    "Turin",
    "Vilnius",
)
TRANSLATOR_TRAIN = {"I1": 600, "I2": 200, "I3": 200, "I4": 200, "I1+I2": 600, "I1+I3": 600}
TRAIN_REFUSALS, TRAIN_UNKNOWN = 300, 200
# Few-shot decider: one solved training record per line of this list (intent key, what the teacher did).
DECIDER_SHOTS = (("I0", "route"), ("I1", "binding"), ("I1", "reject"), ("I2", "binding"), ("I3", "binding"),
                 ("I4", "binding"), ("I1+I2", "binding"))  # fmt: skip


def load_independent() -> dict:
    """The independent wording: sentences per intent id, combined sentences per order, refusals."""
    source = json.loads(
        (ROOT / "data" / "instructions" / "independent_source.json").read_text(encoding="utf-8")
    )
    combined: dict[tuple[str, ...], list[str]] = {}
    for item in source["combined"]:
        combined.setdefault(tuple(KIND[k] for k in item["order"]), []).append(item["text"])
    return {
        "single": {KIND[kind]: tuple(source[kind]) for kind in KIND},
        "combined": combined,
        "out_of_scope": tuple(source["out_of_scope"]),
    }


def fill(template: str, a: str | None = None, b: str | None = None) -> str:
    return template.replace("{a}", a or "").replace("{b}", b or "")


def reword(intent: Intent, single: dict, combined: dict, names: dict, rng: random.Random) -> str:
    """The instruction of a dataset intent in another wording, sentences in the original order."""
    order = mention_order(intent)
    a, b = (names.get(end, end) for end in intent.link) if intent.link else (None, None)
    if len(order) == 2 and order in combined and rng.random() < 0.5:
        return fill(rng.choice(combined[order]), a, b)
    sentences = [fill(rng.choice(single[intent_id]), a, b) for intent_id in order]
    # a terse note without a full stop ("min hops") is closed with a semicolon before the next one
    return (
        " ".join(s if s[-1] in ".!?;:" else s + ";" for s in sentences[:-1])
        + (" " if order[1:] else "")
        + sentences[-1]
    )


def misspell(text: str, intent: Intent, rng: random.Random) -> str:
    """Lower case, no final full stop, and two neighbouring letters swapped in one city name."""
    for name in rng.sample(list(intent.link or ()), k=len(intent.link or ())):
        swaps = [i for i in range(1, len(name) - 2) if name[i] != name[i + 1]]
        if name in text and swaps:
            i = rng.choice(swaps)
            text = text.replace(name, name[:i] + name[i + 1] + name[i] + name[i + 2 :])
            break
    return text.lower().rstrip(".")


def probe(
    record: dict, text: str, name: str, lang: str, *, expect: Spec | None = None, kind: str = ""
) -> dict:
    """A dataset record with another instruction text.

    Without ``expect`` the instruction means what the record's intent means, so labels and
    admissible set are unchanged. With ``expect`` (a spec that does not apply) nothing valid is
    asked for: the reference decision is the teacher's without an intent.
    """
    meta = record["meta"]
    view, original = RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"])
    if expect is None:
        intent = Intent(ids=original.ids, text=text, link=original.link)
        meant, key = from_intent(original), meta["intent_key"]
    else:
        intent, meant, key = Intent(text=text), expect, kind
    choice = teacher_choice(view, intent)
    return {
        "id": f"{record['id']}-{name}" + (f"-{kind}" if expect is not None else ""),
        "prompt": chat_messages(view, intent),
        "completion": [{"role": "assistant", "content": format_choice(choice)}],
        "meta": {
            **{k: meta[k] for k in ("load", "seed", "request_index", "no_intent_choice", "view")},
            "group": name,
            "intent_key": key,
            "intent": intent.to_json(),
            "admissible_paths": list(admissible_paths(view, intent)),
            "teacher_choice": list(choice) if choice else None,
            "spec": meant.to_json(),
            "probe": {"set": name, "lang": lang, "apply": expect is None, "source": record["id"],
                      "source_group": meta["group"]},
        },
    }  # fmt: skip


def row(record: dict) -> dict:
    """The instruction row of a probe record."""
    meta = record["meta"]
    return {"text": meta["intent"]["text"], "expect": meta["spec"], "set": meta["probe"]["set"],
            "lang": meta["probe"]["lang"], "kind": meta["intent_key"]}  # fmt: skip


def build_probes(heldout: list[dict], topology: Topology) -> dict[str, list[dict]]:
    independent = load_independent()
    with_intent = [r for r in heldout if r["meta"]["intent_key"] != "I0"]
    without = [r for r in heldout if r["meta"]["intent_key"] == "I0"]
    sample = sorted(random.Random("probe-sample").sample(with_intent, SAMPLE), key=lambda r: r["id"])
    probes: dict[str, list[dict]] = {name: [] for name in ("independent", "de", "fr", "it", "gsw", "noisy")}

    def other(record: dict, name: str, single: dict, combined: dict, names: dict) -> tuple[str, Intent]:
        intent = Intent.from_json(record["meta"]["intent"])
        return reword(intent, single, combined, names, random.Random(f"{name}-{record['id']}")), intent

    for record in with_intent:
        text, _ = other(record, "independent", independent["single"], independent["combined"], {})
        probes["independent"].append(probe(record, text, "independent", "en"))
        for lang in ("de", "fr", "it"):
            text, _ = other(record, lang, LANGUAGES[lang], {}, LANGUAGES[lang]["names"])
            probes[lang].append(probe(record, text, lang, lang))
    for record in sample:
        text, _ = other(record, "gsw", LANGUAGES["gsw"], {}, LANGUAGES["gsw"]["names"])
        probes["gsw"].append(probe(record, text, "gsw", "gsw"))
        text, intent = other(record, "noisy", independent["single"], independent["combined"], {})
        text = misspell(text, intent, random.Random(f"typo-{record['id']}"))
        probes["noisy"].append(probe(record, text, "noisy", "en"))

    faulty, out_of_scope = [], []
    avoid = independent["single"]["I1"]
    for record in without:
        rng = random.Random(f"faulty-{record['id']}")
        view = RequestView.from_json(record["meta"]["view"])
        on_paths = sorted({node for path in view.paths for node in path.nodes})
        apart = sorted({
            (path.nodes[i], path.nodes[j])
            for path in view.paths for i in range(len(path.nodes)) for j in range(i + 2, len(path.nodes))
            if not topology.has_link(path.nodes[i], path.nodes[j])
        })  # fmt: skip
        pairs = {"unknown_place": (rng.choice(on_paths), rng.choice(TEST_OUTSIDE))}
        if apart:
            pairs["not_a_link"] = rng.choice(apart)
        for kind, pair in pairs.items():
            a, b = pair if rng.random() < 0.5 else pair[::-1]
            text = fill(rng.choice(avoid), a, b)
            faulty.append(probe(record, text, "faulty", "en", expect=Spec(status="unresolved"), kind=kind))
        text = fill(rng.choice(independent["out_of_scope"]), rng.choice(on_paths))
        out_of_scope.append(probe(record, text, "out_of_scope", "en", expect=Spec(status="unsupported"),
                                  kind="out_of_scope"))  # fmt: skip
    return probes | {"faulty": faulty, "out_of_scope": out_of_scope}


def translation_record(index: int, text: str, line: str, kind: str, topology: Topology) -> dict:
    return {"id": f"T{index:05d}", "prompt": messages(text, topology),
            "completion": [{"role": "assistant", "content": line}], "meta": {"text": text, "kind": kind}}  # fmt: skip


def build_translator_data(splits: dict[str, list[dict]], topology: Topology) -> dict[str, list[dict]]:
    """Training and held-out records for the translator; ``line`` is the answer it must give."""
    rng = random.Random("translator-data")
    pairs: list[tuple[str, str, str]] = []  # text, answer line, kind
    by_key: dict[str, list[dict]] = {}
    for record in splits["train"]:
        by_key.setdefault(record["meta"]["intent_key"], []).append(record)
    for key, count in TRANSLATOR_TRAIN.items():
        for record in rng.sample(by_key[key], count):
            intent = Intent.from_json(record["meta"]["intent"])
            pairs.append((intent.text, format_spec(from_intent(intent)), key))
    for _ in range(TRAIN_REFUSALS):
        text = rng.choice(TRAIN_UNSUPPORTED).format(
            a=rng.choice(topology.nodes), n=rng.randint(1, 40), mod=rng.choice(MODULATIONS)
        )
        pairs.append((text, "unsupported", "unsupported"))
    for _ in range(TRAIN_UNKNOWN):
        ends = [rng.choice(topology.nodes), rng.choice(TRAIN_OUTSIDE)]
        rng.shuffle(ends)
        phrase = rng.choice(LINK_FORMS).format(a=ends[0], b=ends[1])
        text = rng.choice(PARAPHRASES["I1"][:7]).format(link=phrase, Link=phrase[0].upper() + phrase[1:])
        line = format_spec(Spec(avoid=(tuple(e if e in topology.nodes else UNKNOWN for e in ends),)))
        pairs.append((text, line, "unknown_place"))
    rng.shuffle(pairs)
    data = {"train": [translation_record(i, *pair, topology) for i, pair in enumerate(pairs)]}
    for name in HELDOUT:
        seen: dict[str, tuple[str, str]] = {}
        for record in splits[name]:
            intent = Intent.from_json(record["meta"]["intent"])
            if intent.ids:
                seen.setdefault(intent.text, (format_spec(from_intent(intent)), intent.key))
        data[name] = [
            translation_record(i, text, line, key, topology)
            for i, (text, (line, key)) in enumerate(sorted(seen.items()))
        ]
    return data


def decider_shots(train: list[dict]) -> list[dict]:
    """One solved training record per entry of ``DECIDER_SHOTS`` (the first that fits, by id)."""
    chosen = []
    for key, what in DECIDER_SHOTS:
        for record in train:
            meta = record["meta"]
            teacher, plain = meta["teacher_choice"], meta["no_intent_choice"]
            fits = {"route": teacher is not None, "reject": teacher is None and plain is not None,
                    "binding": teacher is not None and plain is not None and teacher[0] != plain[0]}[what]  # fmt: skip
            if meta["intent_key"] == key and fits and record not in chosen:
                chosen.append(record)
                break
        else:
            raise RuntimeError(f"no training record for the example {key} / {what}")
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    topology = load_topology("nobel-eu")
    splits = {name: read_jsonl(args.data / "full" / f"{name}.jsonl") for name in ("train", *HELDOUT)}
    heldout = [record for name in HELDOUT for record in splits[name]]

    probes = build_probes(heldout, topology)
    for name, records in probes.items():
        write_jsonl(args.data / "probes" / f"{name}.jsonl", records)
        rows = {r["text"]: r for r in map(row, records)}
        write_jsonl(args.data / "instructions" / f"{name}.jsonl", [rows[t] for t in sorted(rows)])
        kinds = Counter(r["meta"]["intent_key"] for r in records)
        print(
            f"{name:13s} {len(records):5d} probes, {len(rows):5d} distinct instructions  {dict(sorted(kinds.items()))}"
        )
    templates = {}
    for name in HELDOUT:
        for record in splits[name]:
            intent = Intent.from_json(record["meta"]["intent"])
            if intent.ids:
                templates.setdefault((name, intent.text), {"text": intent.text, "expect": from_intent(intent).to_json(),
                                                           "set": name, "lang": "en", "kind": intent.key})  # fmt: skip
    write_jsonl(args.data / "instructions" / "templates.jsonl", [templates[k] for k in sorted(templates)])
    print(f"{'templates':13s} {len(templates):5d} distinct instructions of the held-out splits")

    for name, records in build_translator_data(splits, topology).items():
        write_jsonl(args.data / "translate" / f"{name}.jsonl", records)
        print(
            f"translate/{name}: {len(records)} records  {dict(Counter(r['meta']['kind'] for r in records))}"
        )
    shots = decider_shots(splits["train"])
    write_jsonl(args.data / "fewshot" / "decider.jsonl", shots)
    print(
        "decider examples:",
        [(r["id"], r["meta"]["intent_key"], r["completion"][0]["content"]) for r in shots],
    )
    assert NO_INTENT.text == "none"


if __name__ == "__main__":
    main()
