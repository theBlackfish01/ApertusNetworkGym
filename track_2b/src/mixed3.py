"""Instructions of the third round, tied to a request: the policy language and what lies outside it.

The wording comes from ``data/instructions/v3_source_<lang>.json``, written by separate AI
instances that never saw this repository. An instruction is a list of clause kinds in the order
the text states them, with the values that fill its placeholders. Three groups of kinds:

    in the format    avoid_link, avoid_node, via_node, max_hops, max_km, path_index and the four
                     preferences: the slots of ``spec.py`` carry them, alone or combined
    new types        min_mod, not_first, min_free, largest_block: no part of the system was
                     shown them, not even as an example of a refusal. Their rules below exist
                     for scoring only
    partial          one clause of each group in one instruction

The closed-loop condition ``operations_mix3`` draws, per request::

    15 %  nothing
    45 %  an instruction in the format: one clause, a pair seen in training, a pair or a triple
          never seen together (COMBINATIONS), in English, German, French or Italian
    15 %  a new type
    10 %  a partial instruction
    10 %  text that is no instruction
     5 %  an instruction that names a place outside the network

As in every condition the instruction depends on the request's candidate paths and the random
stream only, never on the state of the network.

What counts as respecting an instruction: its constraints filter the feasible paths (none left:
the request must be rejected), then its preferences apply in the order stated. For the last two
kinds the request is to be served as if nothing had been typed.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from corpora import LANGUAGES, MODULATIONS, TEST_OUTSIDE
from corpora3 import HELDOUT, NEW_TYPES, PREF, PREFERENCE, signature
from intents import NO_INTENT, Intent, teacher_choice
from spec import EMPTY, Spec, meets
from view import MAX_BLOCKS, Choice, PathView, RequestView

ROOT = Path(__file__).resolve().parents[1]
CONDITION = "operations_mix3"
MIX = (("none", 15), ("supported", 45), ("new", 15), ("partial", 10), ("not_instruction", 10), ("faulty", 5))
# Supported instructions: share of each group of combinations, and of each language.
COMBINATIONS = (("atom", 40), ("pair", 20), ("heldout_pair", 20), ("triple", 12), ("two_preferences", 8))
LANGUAGE_MIX = (("en", 55), ("de", 15), ("fr", 15), ("it", 15))
NEW_PREFERENCES = ("largest_block",)  # new types that never ask for a reject
NAMED = ("avoid_link", "avoid_node", "via_node")  # clause kinds that name a place
TOPOLOGY = "nobel-eu"
# node id -> its name in the sentence's language (English sentences use the id on nobel-eu)
NAMES: dict[str, dict[str, str]] = {lang: LANGUAGES[lang]["names"] for lang in ("de", "fr", "it")}
OUTSIDE: tuple[str, ...] = TEST_OUTSIDE  # places that are not nodes, for the faulty kind
EXTRA_OUTSIDE = ("Milan", "Munich", "Lyon", "Strasbourg", "Paris", "Vienna", "Innsbruck", "Stuttgart")


def set_topology(name: str) -> None:
    """Make the stream speak of the nodes of another topology.

    ``data/topologies/<name>_names.json`` gives each node's name in German, French, Italian and
    English (an operator writes "Genf", "Genève" or "Geneva" for the node ``Genève``); a sentence
    then carries the first form of its language. Places outside the network are those of the
    test list that are not nodes here, plus a few cities of the European topology.
    """
    global TOPOLOGY, NAMES, OUTSIDE
    TOPOLOGY = name
    path = ROOT / "data" / "topologies" / f"{name}_names.json"
    if path.exists():
        table = json.loads(path.read_text(encoding="utf-8"))["nodes"]
        NAMES = {lang: {node: forms[lang][0] for node, forms in table.items() if forms.get(lang)}
                 for lang in ("de", "fr", "it", "en")}  # fmt: skip
        OUTSIDE = tuple(place for place in TEST_OUTSIDE + EXTRA_OUTSIDE if place not in table)
    else:
        NAMES = {lang: LANGUAGES[lang]["names"] for lang in ("de", "fr", "it")}
        OUTSIDE = TEST_OUTSIDE


@dataclass(frozen=True)
class Instruction(Intent):
    """An instruction of the third round (``ids`` stays empty: these are not the dataset's intents)."""

    kind: str = "none"  # none | supported | new | partial | not_instruction | faulty
    clauses: tuple[str, ...] = ()  # clause kinds in the order the text states them
    fills: tuple[tuple[str, object], ...] = ()  # placeholder -> value, as sorted items
    lang: str = "en"
    group: str = ""  # supported: atom | pair | heldout_pair | triple | two_preferences

    @property
    def key(self) -> str:
        if self.kind == "supported":
            return self.group
        if self.kind == "new":
            return self.clauses[0]
        return "I0" if self.kind == "none" else self.kind

    @property
    def values(self) -> dict:
        return dict(self.fills)


@cache
def sources() -> dict[str, dict]:
    """The independent wording per language; combined sentences are grouped as COMBINATIONS names them."""
    out = {}
    for lang in ("en", "de", "fr", "it"):
        path = ROOT / "data" / "instructions" / f"v3_source_{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        grouped: dict[str, list] = {"atom": [], "pair": [], "heldout_pair": [], "triple": [],
                                    "two_preferences": []}  # fmt: skip
        for kind, sentences in data["atoms"].items():
            grouped["atom"] += [((kind,), text) for text in sentences]
        for item in data["pairs"]:
            name = "heldout_pair" if signature(item["clauses"]) in HELDOUT else "pair"
            grouped[name].append((tuple(item["clauses"]), item["text"]))
        grouped["triple"] = [(tuple(item["clauses"]), item["text"]) for item in data["triples"]]
        grouped["two_preferences"] = [(tuple(i["clauses"]), i["text"]) for i in data["two_preferences"]]
        assert all(signature(c) in HELDOUT for c, _ in grouped["triple"]), lang
        out[lang] = data | {"grouped": grouped}
    return out


def group_of(clauses: tuple[str, ...] | list[str]) -> str:
    """The COMBINATIONS group of an instruction in the format."""
    if len(clauses) == 1:
        return "atom"
    if signature(clauses) == (PREF, PREF):
        return "two_preferences"
    if len(clauses) == 3:
        return "triple"
    return "heldout_pair" if signature(clauses) in HELDOUT else "pair"


def _displayed_block(path: PathView) -> int:
    return max((length for _, length in path.blocks[:MAX_BLOCKS]), default=0)


def draw(clauses: tuple[str, ...], view: RequestView, rng: random.Random) -> dict | None:
    """Values for the placeholders of the clauses, taken from the request's candidate paths.

    Only what does not change with the state of the network is used (nodes, hops, lengths), so
    the instruction of a request is the same whatever policy filled the network before it.
    """
    inner = sorted({n for p in view.paths for n in p.nodes[1:-1]})
    links = sorted({tuple(sorted(link)) for p in view.paths for link in p.links})
    fills: dict = {}
    for kind in clauses:
        if kind == "avoid_link":
            a, b = rng.choice(links)
            fills["a"], fills["b"] = (a, b) if rng.random() < 0.5 else (b, a)
        elif kind in ("avoid_node", "via_node"):
            free = [n for n in inner if n not in (fills.get("c"), fills.get("v"))]
            if not free:
                return None
            fills["c" if kind == "avoid_node" else "v"] = rng.choice(free)
        elif kind == "max_hops":
            fills["n"] = rng.randint(min(p.hops for p in view.paths), max(p.hops for p in view.paths))
        elif kind == "max_km":
            low, high = min(p.km for p in view.paths), max(p.km for p in view.paths)
            fills["km"] = 50 * rng.randint(-(-low // 50), max(high // 50, -(-low // 50)))
        elif kind == "path_index":
            fills["k"] = rng.randrange(len(view.paths))
        elif kind == "min_mod":
            fills["mod"] = rng.choice(MODULATIONS[1:5])  # QPSK ... 32QAM
        elif kind == "min_free":
            fills["f"] = 10 * rng.randint(3, 12)  # 30 to 120 of 320 slots free on the path
    return fills


def render(text: str, fills: dict, lang: str) -> str:
    """The sentence with its placeholders filled; cities carry the name of the sentence's language."""
    names = NAMES.get(lang, {})
    for key, value in fills.items():
        text = text.replace(
            "{" + key + "}", names.get(value, str(value)) if isinstance(value, str) else str(value)
        )
    return text


def expressed(instruction: Instruction) -> Spec:
    """The part of the instruction the slots carry, as a spec."""
    kinds, fills = instruction.clauses, instruction.values
    return Spec(
        avoid=((fills["a"], fills["b"]),) if "avoid_link" in kinds else (),
        prefer=tuple(PREFERENCE[kind] for kind in kinds if kind in PREFERENCE),
        nodes=(fills["c"],) if "avoid_node" in kinds else (),
        via=(fills["v"],) if "via_node" in kinds else (),
        max_hops=fills["n"] if "max_hops" in kinds else None,
        max_km=fills["km"] if "max_km" in kinds else None,
        path=fills["k"] if "path_index" in kinds else None,
        rest=any(kind in NEW_TYPES for kind in kinds),
    )


def expected(instruction: Intent) -> Spec:
    """What a translator of the third format should answer."""
    kind = getattr(instruction, "kind", "none")
    if kind in ("supported", "partial"):
        return expressed(instruction)
    status = {"new": "unsupported", "not_instruction": "no_instruction", "faulty": "unresolved"}
    return Spec(status=status[kind]) if kind in status else EMPTY


def _new_rule(path: PathView, kind: str, fills: dict) -> bool:
    if kind == "min_mod":
        return MODULATIONS.index(path.modulation) >= MODULATIONS.index(fills["mod"])
    if kind == "not_first":
        return path.index != 0
    if kind == "min_free":
        return path.free_slots >= fills["f"]
    raise ValueError(kind)


def allowed(view: RequestView, instruction: Intent) -> tuple[int, ...]:
    """Indices of the paths that respect the instruction; empty means the request must be rejected."""
    kind = getattr(instruction, "kind", "none")
    feasible = [p for p in view.paths if p.feasible]
    if kind not in ("supported", "new", "partial"):
        return tuple(p.index for p in feasible)
    spec, fills = expressed(instruction), instruction.values
    constraints = [k for k in instruction.clauses if k in NEW_TYPES and k not in NEW_PREFERENCES]
    paths = [p for p in feasible if meets(p, spec) and all(_new_rule(p, k, fills) for k in constraints)]
    for clause in instruction.clauses:  # preferences in the order stated
        if not paths:
            break
        if clause in PREFERENCE:
            score = {"hops": lambda p: p.hops, "km": lambda p: p.km, "load": lambda p: -p.free_slots,
                     "slots": lambda p: p.slots_needed}[PREFERENCE[clause]]  # fmt: skip
        elif clause in NEW_PREFERENCES:
            score = lambda p: -_displayed_block(p)
        else:
            continue
        best = min(score(p) for p in paths)
        paths = [p for p in paths if score(p) == best]
    return tuple(p.index for p in paths)


def respected(view: RequestView, instruction: Intent, choice: Choice, rule: str = "ordered") -> bool:
    """Whether a valid decision respects the instruction. A needless reject never does."""
    ok = allowed(view, instruction)
    if choice is None:
        return not ok
    if choice[0] not in ok:
        return False
    return "fewest_slots" not in getattr(instruction, "clauses", ()) or view.paths[choice[0]].in_block(
        choice[1]
    )


def oracle(view: RequestView, instruction: Intent) -> Choice:
    """The reference decision: inside the allowed paths, the shortest if a preference was stated,
    otherwise the lowest start slot (the no-intent teacher's rule)."""
    kind = getattr(instruction, "kind", "none")
    if kind not in ("supported", "new", "partial"):
        return teacher_choice(view, NO_INTENT)
    paths = [view.paths[i] for i in allowed(view, instruction)]
    if not paths:
        return None
    stated = any(c in PREFERENCE or c in NEW_PREFERENCES for c in instruction.clauses)
    best = min(paths, key=(lambda p: (p.km, p.index)) if stated else (lambda p: (p.first_slot, p.index)))
    return (best.index, best.first_slot)


def instance(
    clauses: tuple[str, ...], text: str, lang: str, view: RequestView, rng: random.Random, *, kind: str,
    meetable: bool | None = None, tries: int = 8,
) -> Instruction | None:  # fmt: skip
    """The sentence as an instruction of this request.

    ``meetable`` True/False asks for values with/without a path that complies; ``None`` takes what
    the first draw gives, which is how the closed-loop stream samples.
    """
    for _ in range(tries):
        fills = draw(clauses, view, rng)
        if fills is None:
            return None
        item = Instruction(
            text=render(text, fills, lang), kind=kind, clauses=tuple(clauses), fills=tuple(sorted(fills.items())),
            lang=lang, group=group_of(clauses) if kind == "supported" else "",
        )  # fmt: skip
        if meetable is None or bool(allowed(view, item)) == meetable:
            return item
    return None


def sample(view: RequestView, rng: random.Random) -> Instruction:
    """The instruction of one request in the closed-loop stream."""
    kind = rng.choices([k for k, _ in MIX], weights=[w for _, w in MIX])[0]
    english = sources()["en"]
    on_paths = sorted({n for p in view.paths for n in p.nodes})
    item = None
    if kind == "supported":
        lang = rng.choices([name for name, _ in LANGUAGE_MIX], weights=[w for _, w in LANGUAGE_MIX])[0]
        group = rng.choices([g for g, _ in COMBINATIONS], weights=[w for _, w in COMBINATIONS])[0]
        clauses, text = rng.choice(sources()[lang]["grouped"][group])
        item = instance(clauses, text, lang, view, rng, kind=kind)
    elif kind == "new":
        name = rng.choice(NEW_TYPES)
        item = instance((name,), rng.choice(english["new_types"][name]), "en", view, rng, kind=kind)
    elif kind == "partial":
        entry = rng.choice(english["partial"])
        item = instance(tuple(entry["clauses"]), entry["text"], "en", view, rng, kind=kind)
    elif kind == "not_instruction":
        return Instruction(text=rng.choice(english["not_instruction"]), kind=kind)
    elif kind == "faulty":  # a place that is not in the network, in a sentence that names one
        clauses, text = rng.choice([s for s in english["grouped"]["atom"] if s[0][0] in NAMED])
        outside = rng.choice(OUTSIDE)
        if clauses[0] == "avoid_link":
            ends = [rng.choice(on_paths), outside]
            rng.shuffle(ends)
            fills = {"a": ends[0], "b": ends[1]}
        else:
            fills = {"c" if clauses[0] == "avoid_node" else "v": outside}
        return Instruction(text=render(text, fills, "en"), kind=kind, clauses=clauses)
    return item or Instruction()
