"""An instruction as data: hard constraints plus ordered preferences.

``intents.py`` defines the five intents of the first two passes as rules about paths. This
module is the form a *translator* writes an instruction in, and the engine that executes it:

    avoid=Hamburg-Berlin; prefer=hops,load      constraints, then preferences in order of mention
    avoid=none; prefer=none                     nothing to apply
    unsupported                                 the instruction asks for something else
    no_instruction                              (second version of the format only, see below)

``avoid`` lists links the route must not use; it can make a request impossible (reject).
``prefer`` lists what to optimise among the remaining paths: ``hops`` (fewest hops, I2),
``load`` (most free slots, I3), ``slots`` (fewest slots needed, I4). A city the instruction
names that is not a node is written ``unknown``; :func:`validate` then marks the instruction
``unresolved``, as it does for two nodes that are not joined by a link. An instruction that is
unsupported, unresolved or malformed is not applied, and the operator can be told why.

The second version of the format (``answer_grammar(topology, 2)``, translators named
``translate2_*``) splits the refusal in two, because a hybrid hands some instructions on to the
decider: ``unsupported`` is an instruction about which candidate route, slot or modulation to use
that the format cannot express (a node to avoid, a hop limit); ``no_instruction`` is everything
else (other operations, questions, remarks, attempts to change how the system works). Only the
first may go to the decider.

The third version (``answer_grammar(topology, 3)``, translators named ``translate3_*``) is a line
of slots, so that clauses combine freely:

    avoid=Berlin-Prague,Paris; via=Lyon; hops=4; km=any; path=any; prefer=km,load; rest=none

``avoid`` takes links and nodes (the route must not pass through the node), ``via`` a node it must
pass through, ``hops`` and ``km`` upper limits, ``path`` one candidate by its number, ``prefer``
also ``km`` (the shortest route). ``rest=more`` says the instruction asks for something else as
well that the slots cannot carry: the expressed part can still be enforced, and a hybrid hands
the whole instruction to the decider with that part as a guard. A line with nothing in the slots
and ``rest=more`` is the same as ``unsupported``.

Two readings of several preferences (``rule``):

    intersection   every preference must be met at once; if no path is best on all of them the
                   request is rejected. This is the rule of ``intents.py`` (SPEC section 3), and
                   with it :func:`admissible` equals ``intents.admissible_paths`` on every intent
                   of the dataset (``tests/test_spec.py``).
    ordered        the first preference decides, later ones break ties; a preference never causes
                   a rejection. This is how path computation is normally specified: constraints
                   plus an objective.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from grammar import Dfa, alt, lit, opt, seq
from intents import LINK_FORMS, PARAPHRASES, Intent
from view import Choice, PathView, RequestView

ROOT = Path(__file__).resolve().parents[1]
PREFERENCES = ("hops", "load", "slots")
PREFERENCES3 = ("hops", "km", "load", "slots")  # third version of the format
PREFERENCE_OF = {"I2": "hops", "I3": "load", "I4": "slots"}
UNKNOWN = "unknown"  # a named place that is not a node of the network
MAX_LINKS = 2  # links one instruction can exclude in the answer grammar
MAX_AVOID = 3  # links and nodes together, third version
RULES = ("intersection", "ordered")
_LINE = re.compile(r"avoid=(none|[^;,=]+(?:,[^;,=]+)*); prefer=(none|[a-z]+(?:,[a-z]+)*)")
_LINE3 = re.compile(
    r"avoid=(none|[^;,=]+(?:,[^;,=]+)*); via=(none|[^;,=-]+); hops=(any|[1-9]); km=(any|[1-9][0-9]{2,3}); "
    r"path=(any|[0-4]); prefer=(none|[a-z]+(?:,[a-z]+)*); rest=(none|more)"
)


@dataclass(frozen=True)
class Spec:
    avoid: tuple[tuple[str, str], ...] = ()  # links, endpoints in the order they were written
    prefer: tuple[str, ...] = ()  # in order of mention
    status: str = "ok"  # ok | unsupported | no_instruction | unresolved | malformed
    # The slots of the third version of the format.
    nodes: tuple[str, ...] = ()  # nodes the route must not pass through
    via: tuple[str, ...] = ()  # nodes it must pass through
    max_hops: int | None = None
    max_km: int | None = None
    path: int | None = None  # one candidate, by its number in the list
    rest: bool = False  # the instruction also asks for something the slots cannot carry

    @property
    def applies(self) -> bool:
        return self.status == "ok"

    @property
    def constrains(self) -> bool:
        """Whether a hard constraint is expressed (something a decision can be checked against)."""
        return bool(self.avoid or self.nodes or self.via) or (self.max_hops, self.max_km, self.path) != (
            None,
            None,
            None,
        )

    def meaning(self) -> tuple:
        """What two specs must share to mean the same thing (link direction does not matter)."""
        if not self.applies:
            return (self.status,)
        links = frozenset(frozenset(link) for link in self.avoid)
        return ("ok", links, self.prefer, frozenset(self.nodes), frozenset(self.via),
                self.max_hops, self.max_km, self.path, self.rest)  # fmt: skip

    def to_json(self) -> dict:
        data = {
            "status": self.status,
            "avoid": [list(link) for link in self.avoid],
            "prefer": list(self.prefer),
        }
        extra = {"nodes": list(self.nodes), "via": list(self.via), "max_hops": self.max_hops,
                 "max_km": self.max_km, "path": self.path, "rest": self.rest}  # fmt: skip
        return data | {key: value for key, value in extra.items() if value not in ([], None, False)}

    @classmethod
    def from_json(cls, data: dict) -> Spec:
        return cls(
            tuple(tuple(link) for link in data["avoid"]),
            tuple(data["prefer"]),
            data["status"],
            tuple(data.get("nodes", ())),
            tuple(data.get("via", ())),
            data.get("max_hops"),
            data.get("max_km"),
            data.get("path"),
            data.get("rest", False),
        )


EMPTY = Spec()


@dataclass(frozen=True)
class Topology:
    name: str
    nodes: tuple[str, ...]
    links: frozenset[frozenset[str]]

    def has_link(self, a: str, b: str) -> bool:
        return frozenset((a, b)) in self.links


@cache
def load_topology(name: str = "nobel-eu") -> Topology:
    """Nodes and links of a topology, from ``data/topologies/<name>.json``."""
    data = json.loads((ROOT / "data" / "topologies" / f"{name}.json").read_text(encoding="utf-8"))
    return Topology(name, tuple(data["nodes"]), frozenset(frozenset(link) for link in data["links"]))


def format_spec(spec: Spec, version: int = 1) -> str:
    """The answer line of a spec, in the first two versions of the format or in the third."""
    if spec.status in ("unsupported", "no_instruction"):
        return spec.status
    avoid = ",".join([f"{a}-{b}" for a, b in spec.avoid] + list(spec.nodes)) or "none"
    if version < 3:
        return f"avoid={avoid}; prefer={','.join(spec.prefer) or 'none'}"

    def slot(value: int | None) -> str:
        return "any" if value is None else str(value)

    return (
        f"avoid={avoid}; via={','.join(spec.via) or 'none'}; hops={slot(spec.max_hops)}; km={slot(spec.max_km)}; "
        f"path={slot(spec.path)}; prefer={','.join(spec.prefer) or 'none'}; rest={'more' if spec.rest else 'none'}"
    )


def _parse3(match: re.Match) -> Spec:
    items, via, hops, km, path, preferences, rest = match.groups()
    parts = [] if items == "none" else [tuple(item.split("-")) for item in items.split(",")]
    prefer = () if preferences == "none" else tuple(preferences.split(","))
    if any(len(part) > 2 for part in parts) or any(p not in PREFERENCES3 for p in prefer):
        return Spec(status="malformed")
    spec = Spec(
        tuple(part for part in parts if len(part) == 2),
        prefer,
        "ok",
        tuple(part[0] for part in parts if len(part) == 1),
        () if via == "none" else (via,),
        None if hops == "any" else int(hops),
        None if km == "any" else int(km),
        None if path == "any" else int(path),
        rest == "more",
    )
    # Nothing in the slots and something left over: the instruction is outside the format.
    return Spec(status="unsupported") if spec.rest and not (spec.constrains or spec.prefer) else spec


def parse_spec(text: str) -> Spec:
    """The spec of an answer line; ``status`` is ``malformed`` when it is not in the format."""
    text = text.strip()
    if text in ("unsupported", "no_instruction"):
        return Spec(status=text)
    if (third := _LINE3.fullmatch(text)) is not None:
        return _parse3(third)
    match = _LINE.fullmatch(text)
    if match is None:
        return Spec(status="malformed")
    links, preferences = match.groups()
    avoid = () if links == "none" else tuple(tuple(link.split("-")) for link in links.split(","))
    prefer = () if preferences == "none" else tuple(preferences.split(","))
    if any(len(link) != 2 for link in avoid) or any(p not in PREFERENCES for p in prefer):
        return Spec(status="malformed")
    return Spec(avoid, prefer)


def validate(spec: Spec, topology: Topology) -> Spec:
    """Check an applicable spec against the topology; repeated entries are dropped.

    A link with a place that is not a node, or between two nodes that are not adjacent, makes
    the whole instruction ``unresolved``: applying the rest would silently ignore part of it.
    The same holds for a node to avoid or to pass through that is not in the network.
    """
    if not spec.applies:
        return spec
    avoid, seen = [], set()
    for a, b in spec.avoid:
        if a not in topology.nodes or b not in topology.nodes or not topology.has_link(a, b):
            return replace(spec, status="unresolved")
        if frozenset((a, b)) not in seen:
            seen.add(frozenset((a, b)))
            avoid.append((a, b))
    if any(node not in topology.nodes for node in spec.nodes + spec.via):
        return replace(spec, status="unresolved")
    return replace(
        spec,
        avoid=tuple(avoid),
        prefer=tuple(dict.fromkeys(spec.prefer)),
        nodes=tuple(dict.fromkeys(spec.nodes)),
        via=tuple(dict.fromkeys(spec.via)),
    )


@cache
def answer_grammar(topology: Topology, version: int = 1) -> Dfa:
    """The automaton of the answer lines for this topology (for constrained decoding).

    Version 2 adds the answer ``no_instruction``; version 3 is the line of slots.
    """
    return Dfa(answer_expression(topology, version))


def _repeat(item: tuple, most: int) -> tuple:
    """One to ``most`` items separated by commas."""
    items = item
    for _ in range(most - 1):
        items = seq(item, opt(seq(lit(","), items)))
    return items


def _expression3(topology: Topology) -> tuple:
    city = alt(*(lit(node) for node in topology.nodes), lit(UNKNOWN))
    digit, nonzero = alt(*(lit(d) for d in "0123456789")), alt(*(lit(d) for d in "123456789"))
    preference = alt(*(lit(p) for p in PREFERENCES3))
    line = seq(
        lit("avoid="), alt(lit("none"), _repeat(seq(city, opt(seq(lit("-"), city))), MAX_AVOID)),
        lit("; via="), alt(lit("none"), city),
        lit("; hops="), alt(lit("any"), nonzero),
        lit("; km="), alt(lit("any"), seq(nonzero, digit, digit, opt(digit))),
        lit("; path="), alt(lit("any"), *(lit(d) for d in "01234")),
        lit("; prefer="), alt(lit("none"), _repeat(preference, 3)),
        lit("; rest="), alt(lit("none"), lit("more")),
    )  # fmt: skip
    return alt(lit("unsupported"), lit("no_instruction"), line)


def answer_expression(topology: Topology, version: int = 1) -> tuple:
    """The answer lines of this topology as an expression of ``grammar.py``."""
    clash = {"none", "any", UNKNOWN} & set(topology.nodes)
    if clash or any("-" in node or "," in node or ";" in node for node in topology.nodes):
        raise ValueError(f"node names the answer format cannot carry: {sorted(clash) or topology.nodes}")
    if version == 3:
        return _expression3(topology)
    city = alt(*(lit(node) for node in topology.nodes), lit(UNKNOWN))
    link = seq(city, lit("-"), city)
    links = link
    for _ in range(MAX_LINKS - 1):
        links = seq(link, opt(seq(lit(","), links)))
    preference = alt(*(lit(p) for p in PREFERENCES))
    preferences = seq(preference, opt(seq(lit(","), preference, opt(seq(lit(","), preference)))))
    line = seq(lit("avoid="), alt(lit("none"), links), lit("; prefer="), alt(lit("none"), preferences))
    refusals = [lit("unsupported")] + ([lit("no_instruction")] if version == 2 else [])
    return alt(*refusals, line)


def mention_order(intent: Intent) -> tuple[str, ...]:
    """The ids of a dataset intent in the order its text states them."""
    if len(intent.ids) < 2:
        return intent.ids
    positions = []
    for intent_id, index in zip(intent.ids, intent.paraphrases, strict=True):
        sentence = PARAPHRASES[intent_id][index]
        if intent_id == "I1":
            phrase = LINK_FORMS[intent.link_form].format(a=intent.link[0], b=intent.link[1])
            sentence = sentence.format(link=phrase, Link=phrase[0].upper() + phrase[1:])
        positions.append(intent.text.find(sentence))
    if min(positions) < 0:
        raise ValueError(f"cannot locate the sentences of {intent.key} in {intent.text!r}")
    return tuple(intent_id for _, intent_id in sorted(zip(positions, intent.ids, strict=True)))


def from_intent(intent: Intent, order: tuple[str, ...] | None = None) -> Spec:
    """The spec a dataset intent means; ``order`` (ids as mentioned) is derived from its text if not given."""
    order = order if order is not None else mention_order(intent)
    avoid = (tuple(intent.link),) if "I1" in intent.ids else ()
    return Spec(avoid, tuple(PREFERENCE_OF[i] for i in order if i in PREFERENCE_OF))


def _best(preference: str, paths: list[PathView]) -> list[PathView]:
    if preference == "hops":
        value = min(p.hops for p in paths)
        return [p for p in paths if p.hops == value]
    if preference == "load":
        value = max(p.free_slots for p in paths)
        return [p for p in paths if p.free_slots == value]
    if preference == "slots":
        value = min(p.slots_needed for p in paths)
        return [p for p in paths if p.slots_needed == value]
    if preference == "km":
        value = min(p.km for p in paths)
        return [p for p in paths if p.km == value]
    raise ValueError(f"unknown preference {preference!r}")


def meets(path: PathView, spec: Spec) -> bool:
    """Whether a path satisfies the hard constraints of a spec (preferences aside)."""
    inner = path.nodes[1:-1]
    return (
        not any(path.has_link(*link) for link in spec.avoid)
        and not any(node in inner for node in spec.nodes)
        and all(node in inner for node in spec.via)
        and (spec.max_hops is None or path.hops <= spec.max_hops)
        and (spec.max_km is None or path.km <= spec.max_km)
        and (spec.path is None or path.index == spec.path)
    )


def admissible(view: RequestView, spec: Spec, rule: str = "ordered") -> tuple[int, ...]:
    """Indices of the paths the spec allows; empty means the request must be rejected."""
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}")
    paths = [p for p in view.paths if p.feasible and meets(p, spec)]
    if not paths:
        return ()
    if rule == "ordered":
        for preference in spec.prefer:
            paths = _best(preference, paths)
        return tuple(sorted(p.index for p in paths))
    allowed = {p.index for p in paths}
    for preference in spec.prefer:
        allowed &= {p.index for p in _best(preference, paths)}
    return tuple(sorted(allowed))


def choose(view: RequestView, spec: Spec, rule: str = "ordered") -> Choice:
    """The engine's decision: the teacher of ``intents.py`` inside the admissible set."""
    paths = [view.paths[i] for i in admissible(view, spec, rule)]
    if not paths:
        return None
    if spec.prefer:
        best = min(paths, key=lambda p: (p.km, p.index))
    else:  # BM-LS-KSP on the listed blocks: lowest start slot, ties by path order
        best = min(paths, key=lambda p: (p.first_slot, p.index))
    return (best.index, best.first_slot)


def respects(view: RequestView, spec: Spec, choice: Choice, rule: str = "ordered") -> bool:
    """Whether a valid decision respects the spec (``intents.is_admissible`` for specs)."""
    allowed = admissible(view, spec, rule)
    if choice is None:
        return not allowed
    path, slot = choice
    if path not in allowed:
        return False
    return "slots" not in spec.prefer or view.paths[path].in_block(slot)
