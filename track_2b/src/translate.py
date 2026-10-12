"""The translator arm: instruction text -> spec -> rule engine.

The decider of the first two passes reads the instruction again with every request and answers
with a path and slot. Here the language model is asked once per instruction for one line in the
format of ``spec.py``; the line is checked against the topology, and the rule engine decides
every request. An instruction that is unsupported, unresolved or malformed is not applied (the
request is routed as if there were none) and is counted as *flagged*: the operator can be told.

Translators (``translate_<kind>``; add ``_ordered`` for the ordered rule of ``spec.py``):

    translate_keyword   no model: city names and keywords, written against the training wording
    translate_zero      Apertus as is, the task description only
    translate_few       Apertus as is, plus seven solved examples in the prompt
    translate_ft        Apertus fine-tuned on the training instructions (``corpora.py``)

Second version (``translate2_few``, ``translate2_ft``): the answer format has a second refusal,
``no_instruction``, the prompt says what separates it from ``unsupported``, the examples include
one instruction with two preferences, and the fine-tuned one is trained on two preferences and on
German, French and Italian as well. ``hybrid2_<kind>`` is that translator in front of the
fine-tuned decider: what the translator calls ``unsupported`` goes to the decider together with
the request, everything else is handled as before.

Model answers are cached per translator (``results/cache/<name>.jsonl``), so the closed loop of
a translator runs on a laptop from the cache: ``texts`` lists every instruction the closed-loop
protocol will show, ``parse`` asks the model for them next to a GPU, and ``evaluate.py closed
--policy translate_few`` replays them.

    uv run python src/translate.py texts                                   # needs the simulator
    uv run python src/translate.py parse --policy translate_few --model <id> --sets data/instructions/*.jsonl
    uv run python src/translate.py score --policy translate_few --sets data/instructions/*.jsonl
    uv run python src/translate.py batch --model <id> --jobs translate_few:nobel-eu:regex:data/instructions/de.jsonl ...
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from grammar import gbnf
from intents import Intent
from policies import Decision, GrammarEndpoint, LocalLLMPolicy, Policy, Request
from spec import (
    EMPTY,
    UNKNOWN,
    Spec,
    Topology,
    answer_expression,
    answer_grammar,
    choose,
    format_spec,
    from_intent,
    load_topology,
    meets,
    parse_spec,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
MAX_NEW_TOKENS = 48  # the longest answer line (two links, three preferences) is about 40 tokens
MAX_NEW_TOKENS3 = 96  # the line of slots of the third version
MAX_NEW_TOKENS4 = 120  # the fourth version's line is two slots longer

SYSTEM = """You translate an operator's instruction about one lightpath request into one line that a path computation engine can execute. The instruction can be in any language.

Answer with exactly one line, in one of these two forms:
avoid=<links>; prefer=<preferences>
unsupported

<links> is "none", or the links the route must not use. Write each link as NodeA-NodeB with the node names exactly as in the node list below, and separate several links with commas. The instruction may name a node in another language or misspell it; write the node of the list it refers to. Write "unknown" only for a place that is none of the nodes.
<preferences> is "none", or what the instruction asks to optimise, in the order it states them, separated by commas:
hops = the fewest hops (the fewest links crossed, the most direct route)
load = the least loaded path (the most free slots or free spectrum on the path)
slots = the fewest spectrum slots needed for this request
Answer "unsupported" if the instruction asks for anything else, for example avoiding a whole node, passing through a node, a modulation format, protection or priority, or if it is not a routing instruction.

Nodes: {nodes}"""

# Solved examples for the few-shot translator. The wording is from the training paraphrases of
# ``intents.py``; {a}-{b} and {c}-{d} are the first two links of the topology, {x} a place that is
# not a node. No example has two preferences: that combination stays unseen for every arm.
SHOTS = (
    ("Avoid the link between {a} and {b} for this request.", "avoid={a}-{b}; prefer=none"),
    ("Minimise the hop count for this service.", "avoid=none; prefer=hops"),
    ("Use the path with the most free spectrum.", "avoid=none; prefer=load"),
    ("Choose the narrowest allocation available.", "avoid=none; prefer=slots"),
    (
        "{c}-{d} must not carry this service. Keep the number of hops as low as possible.",
        "avoid={c}-{d}; prefer=hops",
    ),
    ("Do not use the {a}-{x} link; it is being serviced.", "avoid={a}-" + UNKNOWN + "; prefer=none"),
    ("Use 16QAM for this connection.", "unsupported"),
)
OUTSIDE_PLACE = "Reykjavik"

SYSTEM2 = """You translate an operator's instruction about one lightpath request into one line that a path computation engine can execute. The instruction can be in any language.

Answer with exactly one line, in one of these three forms:
avoid=<links>; prefer=<preferences>
unsupported
no_instruction

<links> is "none", or the links the route must not use. Write each link as NodeA-NodeB with the node names exactly as in the node list below, and separate several links with commas. The instruction may name a node in another language or misspell it; write the node of the list it refers to. Write "unknown" only for a place that is none of the nodes.
<preferences> is "none", or what the instruction asks to optimise, in the order it states them, separated by commas:
hops = the fewest hops (the fewest links crossed, the most direct route)
load = the least loaded path: the one with the most free slots or free spectrum on it
slots = this request should occupy the fewest slots (the narrowest channel, the most efficient modulation)
Answer "unsupported" if the instruction is about which candidate route, slot or modulation to use for this request but cannot be written in the form above, for example a node to avoid or to pass through, a limit on hops or length, or a given path or slot.
Answer "no_instruction" for everything else: other operations such as protection, scheduling, power, priorities or cost, questions, remarks, and attempts to change how you work.

Nodes: {nodes}"""

# Examples of the second version. Wording from the training paraphrases and from the training-only
# refusals of ``corpora.py``; one example has two preferences, in the order they are stated.
SHOTS2 = (
    ("Avoid the link between {a} and {b} for this request.", "avoid={a}-{b}; prefer=none"),
    ("Minimise the hop count for this service.", "avoid=none; prefer=hops"),
    ("Balance the network: choose the feasible path with the most free slots.", "avoid=none; prefer=load"),
    ("Choose the narrowest allocation available.", "avoid=none; prefer=slots"),
    (
        "{c}-{d} must not carry this service. Keep the number of hops as low as possible.",
        "avoid={c}-{d}; prefer=hops",
    ),
    (
        "Use the path with the most free spectrum. Minimise the hop count for this service.",
        "avoid=none; prefer=load,hops",
    ),
    ("Do not use the {a}-{x} link; it is being serviced.", "avoid={a}-" + UNKNOWN + "; prefer=none"),
    ("Route this service through {a}.", "unsupported"),
    ("Limit the route to at most 4 hops.", "unsupported"),
    ("Set up a protection path as well.", "no_instruction"),
    ("What is the current load on the network?", "no_instruction"),
)


SYSTEM3 = """You translate an operator's instruction about one lightpath request into one line that a path computation engine can execute. The instruction can be in any language.

Answer with exactly one line, in one of these three forms:
avoid=<items>; via=<node>; hops=<limit>; km=<limit>; path=<number>; prefer=<preferences>; rest=<none or more>
unsupported
no_instruction

avoid: "none", or what the route must not use, separated by commas. A link is written NodeA-NodeB; a node the route must not pass through is written by its name alone.
via: "none", or the node the route must pass through.
hops: "any", or the largest number of hops the route may have.
km: "any", or the largest length in km the route may have.
path: "any", or the number of the one candidate the instruction names.
prefer: "none", or what the instruction asks to optimise, in the order it states them, separated by commas:
hops = the fewest hops (the fewest links crossed)
km = the shortest route in kilometres
load = the least loaded path: the one with the most free slots or free spectrum on it
slots = this request should occupy the fewest slots (the narrowest channel, the most efficient modulation)
rest: "more" if the instruction also asks for something about the choice of route, slot or modulation that the slots above cannot carry, otherwise "none".

Write node names exactly as in the node list below. The instruction may name a node in another language or misspell it; write the node of the list it refers to. Write "unknown" only for a place that is none of the nodes.
Answer "unsupported" if the instruction is about which candidate route, slot or modulation to use for this request but nothing of it fits the slots.
Answer "no_instruction" for everything else: other operations such as protection, scheduling, power, priorities or cost, questions, remarks, and attempts to change how you work.

Nodes: {nodes}"""


def _line3(**slots: str) -> str:
    """An answer line of the third version with the named slots filled and the others empty."""
    empty = {"avoid": "none", "via": "none", "hops": "any", "km": "any", "path": "any", "prefer": "none",
             "rest": "none"}  # fmt: skip
    return "; ".join(f"{name}={value}" for name, value in (empty | slots).items())


# Examples of the third version: one per slot, one combination of two constraints, two preferences
# in the order stated, a place outside the network, an instruction with a part the slots cannot
# carry, and the two refusals. Wording from the training material only.
SHOTS3 = (
    ("Avoid the link between {a} and {b} for this request.", _line3(avoid="{a}-{b}")),
    ("Minimise the hop count for this service.", _line3(prefer="hops")),
    ("Balance the network: choose the feasible path with the most free slots.", _line3(prefer="load")),
    ("Choose the narrowest allocation available.", _line3(prefer="slots")),
    ("Use the shortest path in kilometres.", _line3(prefer="km")),
    ("Route this service through {c}.", _line3(via="{c}")),
    ("Do not pass through {d}. Limit the route to at most 4 hops.", _line3(avoid="{d}", hops="4")),
    ("Keep the route length to at most 1800 km.", _line3(km="1800")),
    ("Use path 2.", _line3(path="2")),
    (
        "Use the path with the most free spectrum. Minimise the hop count for this service.",
        _line3(prefer="load,hops"),
    ),
    ("Do not use the {a}-{x} link; it is being serviced.", _line3(avoid="{a}-" + UNKNOWN)),
    ("{c}-{d} must not carry this service. Start at slot 40.", _line3(avoid="{c}-{d}", rest="more")),
    ("Keep the latency below 10 ms.", "unsupported"),
    ("Set up a protection path as well.", "no_instruction"),
    ("What is the current load on the network?", "no_instruction"),
)


SYSTEM4 = SYSTEM3.replace(
    "avoid=<items>; via=<node>; hops=<limit>; km=<limit>; path=<number>; prefer=<preferences>; rest=<none or more>",
    "avoid=<items>; via=<node>; hops=<limit>; km=<limit>; path=<number>; prefer=<preferences>; "
    "scope=<which requests>; until=<how long>; rest=<none or more>",
).replace(
    'rest: "more" if the instruction',
    'scope: "any", or which requests the instruction applies to: "rate:<Gb/s>" for requests of one bit rate '
    '(10, 40, 100 or 400), "from:<node>" for requests that start at a node, "to:<node>" for requests that '
    "end at a node.\n"
    'until: "open" if no end is stated or the instruction holds until further notice, or "<hours>h" when it '
    "holds for a number of hours.\n"
    'rest: "more" if the instruction',
)


def _line4(**slots: str) -> str:
    """An answer line of the fourth version with the named slots filled and the others empty."""
    empty = {"avoid": "none", "via": "none", "hops": "any", "km": "any", "path": "any", "prefer": "none",
             "scope": "any", "until": "open", "rest": "none"}  # fmt: skip
    return "; ".join(f"{name}={value}" for name, value in (empty | slots).items())


# The examples of the third version in the fourth format, and three with a scope or a lifetime.
SHOTS4 = tuple(
    (
        text,
        line
        if line in ("unsupported", "no_instruction")
        else line.replace("; rest=", "; scope=any; until=open; rest="),
    )
    for text, line in SHOTS3
) + (
    ("For the next 6 hours, avoid the link between {a} and {b}.", _line4(avoid="{a}-{b}", until="6h")),
    ("Only for 400G services: route through {c}.", _line4(via="{c}", scope="rate:400")),
    (
        "Everything leaving {d} takes the least loaded path until further notice.",
        _line4(prefer="load", scope="from:{d}"),
    ),
)


def messages(text: str, topology: Topology, few: bool = False, version: int = 1) -> list[dict[str, str]]:
    """The chat messages that ask for the translation of one instruction."""
    system, shots = {2: (SYSTEM2, SHOTS2), 3: (SYSTEM3, SHOTS3), 4: (SYSTEM4, SHOTS4)}.get(
        version, (SYSTEM, SHOTS)
    )
    chat = [{"role": "system", "content": system.format(nodes=", ".join(topology.nodes))}]
    if few:
        (a, b), (c, d) = (sorted(link) for link in sorted(topology.links, key=sorted)[:2])
        names = {"a": a, "b": b, "c": c, "d": d, "x": OUTSIDE_PLACE}
        for instruction, answer in shots:
            chat.append({"role": "user", "content": "Instruction: " + instruction.format(**names)})
            chat.append({"role": "assistant", "content": answer.format(**names)})
    chat.append({"role": "user", "content": "Instruction: " + text})
    return chat


class Translator:
    name = "translator"

    def __init__(self, topology: Topology) -> None:
        self.topology = topology

    def lines(self, texts: list[str]) -> list[tuple[str, float]]:
        """``(answer line, seconds)`` for each instruction."""
        raise NotImplementedError

    def translate(self, texts: list[str]) -> list[Spec]:
        """The validated spec of each instruction."""
        return [validate(parse_spec(line), self.topology) for line, _ in self.lines(texts)]

    def describe(self) -> dict:
        return {"name": self.name, "topology": self.topology.name}


class KeywordTranslator(Translator):
    """No model. Written against the training wording of ``intents.py`` only (English).

    A link is two capitalised names joined by a hyphen or dash, or "between A and B"; a name that
    is not a node becomes ``unknown``. A preference is a keyword; several are ordered by where
    they first appear. An instruction in which nothing is recognised is ``unsupported``.
    """

    name = "translate_keyword"
    _NAME = r"([A-Z][\w'’]*)"  # no full stop: a name at the end of a sentence must still match a node
    _LINKS = (re.compile(_NAME + r"\s?[-–—]\s?" + _NAME), re.compile(r"between " + _NAME + r" and " + _NAME))
    _KEYWORDS = (
        ("hops", r"\bhops?\b|fewest links"),
        ("load", r"least[- ]loaded|most free|emptiest|free-slot|spare slots|least congested|\bbalanc"),
        (
            "slots",
            r"fewest slots|number of slots|slot requirement|narrowest|spectrum-efficient|spectrum is scarce|save spectrum",
        ),
    )

    def one(self, text: str) -> str:
        links = []
        for pattern in self._LINKS:
            for a, b in pattern.findall(text):
                links.append(tuple(name if name in self.topology.nodes else UNKNOWN for name in (a, b)))
        found = {}
        for preference, pattern in self._KEYWORDS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                found[preference] = match.start()
        if not links and not found:
            return "unsupported"
        return format_spec(Spec(tuple(links[:2]), tuple(sorted(found, key=found.get))))

    def lines(self, texts: list[str]) -> list[tuple[str, float]]:
        answers = []
        for text in texts:
            started = time.perf_counter()
            answers.append((self.one(text), time.perf_counter() - started))
        return answers


class LLMTranslator(Translator):
    """Apertus: in this process (next to a GPU), behind a server (``base_url``), or replayed from
    its answer cache."""

    def __init__(self, name: str, topology: Topology, *, few: bool = False, version: int = 1, **llm) -> None:
        super().__init__(topology)
        self.name, self.few, self.version = name, few, version
        constrained = llm.get("structured") != "none"
        limit = MAX_NEW_TOKENS4 if version >= 4 else MAX_NEW_TOKENS3 if version == 3 else MAX_NEW_TOKENS
        if llm.get("base_url"):
            self.llm = GrammarEndpoint(
                name,
                grammar=gbnf(answer_expression(topology, version)),
                max_tokens=limit,
                base_url=llm["base_url"],
                model=llm.get("model"),
                extra_body=llm.get("extra_body"),
                concurrency=llm.get("concurrency", 4),
            )
            return
        self.llm = LocalLLMPolicy(
            name,
            model=llm.get("model"),
            adapter=llm.get("adapter"),
            structured="regex" if constrained else "none",
            template_kwargs=llm.get("template_kwargs"),
            max_batch=llm.get("max_batch", 64),
            grammar=answer_grammar(topology, version) if constrained else None,
            max_new_tokens=limit,
        )

    def lines(self, texts: list[str]) -> list[tuple[str, float]]:
        entries = self.llm.ask([messages(text, self.topology, self.few, self.version) for text in texts])
        return [(entry["answer"], entry["seconds"]) for entry in entries]

    def describe(self) -> dict:
        described = {"few_shot": self.few, "format_version": self.version, "llm": self.llm.describe()}
        return super().describe() | described


def format_version(name: str) -> int:
    """The answer format of a translator or hybrid, from its name (``translate3_ft``, ``hybrid2_few``)."""
    return next((v for v in (4, 3, 2) if name.startswith((f"translate{v}_", f"hybrid{v}_"))), 1)


def make_translator(name: str, topology: str = "nobel-eu", **llm) -> Translator:
    """``translate_keyword``, or a model translator; a name containing ``_few`` gets the examples."""
    net = load_topology(topology)
    if name == "translate_keyword":
        return KeywordTranslator(net)
    return LLMTranslator(name, net, few="_few" in name, version=format_version(name), **llm)


def meant(intent) -> Spec:
    """What the author of an instruction means by it: the answer of an operator who is asked."""
    import mixed
    import mixed3

    if isinstance(intent, mixed3.Instruction):
        return mixed3.expected(intent)
    return mixed.expected(intent) if isinstance(intent, mixed.Instruction) else from_intent(intent)


class TranslatorPolicy(Policy):
    """A translator and the rule engine as a policy, so the evaluator treats it like any other.

    With a ``second`` reader every instruction is translated twice. Where the two readings differ
    the operator is asked, which in the simulation means the instruction's true meaning is used;
    such decisions carry ``asked+`` in front of what they report. With ``ask="if"`` the question
    is put only when it matters: the first reading is applied for the time being, and the operator
    is asked on the first request on which the two readings would decide differently (a reading
    that does not apply, or one carried in part, is asked about at once, because what the decider
    would do with it cannot be foreseen).
    """

    parallel_safe = True  # in worker processes the model answers must already be in the cache

    def __init__(
        self, name: str, translator: Translator, rule: str, second: Translator | None = None, ask: str = "always"
    ) -> None:  # fmt: skip
        self.name, self.translator, self.rule, self.second, self.ask = name, translator, rule, second, ask
        self.version = getattr(translator, "version", 1)
        self._specs: dict[str, Spec] = {"none": EMPTY}  # "none" is the prompt text of no instruction
        self._asked: set[str] = set()
        self._pending: dict[str, tuple[Spec, Spec, Intent]] = {}  # text -> two readings not yet asked about

    def read(self, requests: list[Request]) -> None:
        """Translate the instructions not seen before; ask where two readers disagree."""
        new = {r.intent.text: r.intent for r in requests if r.intent.text not in self._specs}
        if not new:
            return
        texts = sorted(new)
        specs = self.translator.translate(texts)
        if self.second is not None:
            for i, (text, other) in enumerate(zip(texts, self.second.translate(texts), strict=True)):
                if specs[i].meaning() == other.meaning():
                    continue
                foreseeable = specs[i].applies and other.applies and not (specs[i].rest or other.rest)
                if self.ask == "if" and foreseeable:
                    self._pending[text] = (
                        specs[i],
                        other,
                        new[text],
                    )  # asked when a request tells them apart
                else:
                    self._asked.add(text)
                    specs[i] = meant(new[text])
        self._specs.update(zip(texts, specs, strict=True))

    def resolve(self, requests: list[Request]) -> None:
        """Ask about a pending pair of readings on the first request they would decide differently."""
        for request in requests:
            text = request.intent.text
            if text in self._pending:
                first, other, intent = self._pending[text]
                if choose(request.view, first, self.rule) != choose(request.view, other, self.rule):
                    del self._pending[text]
                    self._asked.add(text)
                    self._specs[text] = meant(intent)

    def report(self, text: str, body: str) -> str:
        return ("asked+" if text in self._asked else "") + body

    def decide(self, requests: list[Request]) -> list[Decision]:
        self.read(requests)
        self.resolve(requests)
        decisions = []
        for request in requests:
            started = time.perf_counter()
            spec = self._specs[request.intent.text]
            choice = choose(request.view, spec if spec.applies else EMPTY, self.rule)
            body = (
                format_spec(spec, self.version)
                if spec.applies or spec.status == "unsupported"
                else spec.status
            )
            raw = self.report(request.intent.text, body)
            decisions.append(Decision(choice, raw=raw, seconds=time.perf_counter() - started))
        return decisions

    def describe(self) -> dict:
        second = (
            {"second_reader": self.second.describe(), "ask": self.ask,
             # after a run in one process: distinct instructions asked about, and pairs of readings
             # that no request ever told apart (so the first reading stood unasked)
             "questions": len(self._asked), "never_told_apart": len(self._pending)}
            if self.second is not None
            else {}
        )  # fmt: skip
        return {"name": self.name, "rule": self.rule, "translator": self.translator.describe()} | second


class HybridPolicy(TranslatorPolicy):
    """The translator in front of the decider.

    An instruction the translator can write in its format is executed by the rule engine. One it
    calls ``unsupported`` (about the choice of route, but outside the format) is handed to the
    decider together with the request. Everything else is not applied.

    In the third format an instruction can be carried in part (``rest=more``). It goes to the
    decider too, and with ``guard`` the decider's choice is checked against the constraints the
    slots do carry: a path that breaks them is replaced by the rule engine's choice under those
    constraints (``guard:`` in the report). A reject by the decider is kept, because the part the
    slots cannot carry may be impossible to meet.
    """

    def __init__(
        self, name: str, translator: Translator, decider: Policy, rule: str, second: Translator | None = None,
        guard: bool = True, ask: str = "always",
    ) -> None:  # fmt: skip
        super().__init__(name, translator, rule, second, ask)
        self.decider, self.guard = decider, guard

    def decide(self, requests: list[Request]) -> list[Decision]:
        decisions = super().decide(requests)
        specs = [self._specs[r.intent.text] for r in requests]
        forward = [
            i for i, spec in enumerate(specs) if spec.status == "unsupported" or (spec.applies and spec.rest)
        ]
        if forward:
            for i, d in zip(forward, self.decider.decide([requests[i] for i in forward]), strict=True):
                spec, paths, tag = specs[i], requests[i].view.paths, "decider:"
                choice, well_formed = d.choice, d.well_formed
                checkable = (
                    self.guard and spec.applies and spec.constrains and well_formed and choice is not None
                )
                if checkable and (choice[0] >= len(paths) or not meets(paths[choice[0]], spec)):
                    choice, tag = decisions[i].choice, "guard:"  # the engine's choice under the carried part
                # after a tab: what the slots carry of an instruction that was handed on in part
                carried = "\t" + format_spec(spec, self.version) if spec.applies else ""
                raw = self.report(requests[i].intent.text, tag + (d.raw or "") + carried)
                decisions[i] = Decision(choice, well_formed, raw, d.seconds)
        return decisions

    def describe(self) -> dict:
        return super().describe() | {"decider": self.decider.describe(), "guard": self.guard}


def _parts(name: str) -> tuple[str, str | None, bool, bool, str]:
    """``(first reader, second reader or None, guard, ordered, ask)`` from a policy name such as
    ``hybrid3_ft_ask-ft2``, ``translate3_ft_askif-ft2`` (asked only when a request tells the
    readings apart), ``translate3_ft_ask-few`` or ``hybrid3_ft_noguard``."""
    ordered = name.endswith("_ordered")
    base = name.removesuffix("_ordered")
    ask = "if" if "_askif-" in base else "always"
    base, _, second = base.partition("_askif-" if ask == "if" else "_ask-")
    guard = "_noguard" not in base
    first = base.replace("_noguard", "").replace("hybrid", "translate", 1)
    version = format_version(first)
    return first, (f"translate{version}_{second}" if second else None), guard, ordered or version == 3, ask


def make_hybrid_policy(
    name: str,
    topology: str = "nobel-eu",
    decider: str = "apertus_ft_probes",
    decider_adapter: str | None = None,
    **llm,
) -> HybridPolicy:
    """``hybrid<v>_<kind>``: ``translate<v>_<kind>`` in front of the decider.

    ``_ask-<kind>`` adds ``translate<v>_<kind>`` as a second reader; ``_noguard`` switches the
    guard of the third format off. Without ``decider_adapter`` all answer from their caches (a
    replay). With it the decider is loaded with that adapter and asked live, and the translators
    still answer from their caches only: their instructions are translated beforehand, and a
    missing one must stop the run instead of being answered by a model without the translator's
    adapter. The third format is defined with ordered preferences.
    """
    from policies import make_policy

    first, second, guard, ordered, ask = _parts(name)
    options, backend = {}, "transformers"
    if decider_adapter:
        options = {
            "model": llm.get("model"),
            "adapter": decider_adapter,
            "max_batch": llm.get("max_batch", 64),
        }
        llm = {}
    elif llm.get("base_url"):  # everything behind one server that takes a grammar (a laptop)
        backend = "endpoint"
        options = {"structured": "gbnf", "base_url": llm["base_url"], "model": llm.get("model"),
                   "concurrency": llm.get("concurrency", 1)}  # fmt: skip
    policy = HybridPolicy(
        name,
        make_translator(first, topology, **llm),
        make_policy(decider, backend=backend, **options),
        "ordered" if ordered else "intersection",
        make_translator(second, topology, **llm) if second else None,
        guard,
        ask,
    )
    policy.parallel_safe = not decider_adapter and backend != "endpoint"  # a live decider is one model
    policy.cache_path = getattr(
        policy.decider, "cache_path", None
    )  # what a closed-loop run copies to the Hub
    return policy


def make_translator_policy(name: str, topology: str = "nobel-eu", **llm) -> TranslatorPolicy:
    first, second, _, ordered, ask = _parts(name)
    # The third format is defined with ordered preferences: constraints, then objectives in order.
    return TranslatorPolicy(
        name,
        make_translator(first, topology, **llm),
        "ordered" if ordered else "intersection",
        make_translator(second, topology, **llm) if second else None,
        ask,
    )


def read_rows(paths: list[Path]) -> list[dict]:
    """Instruction rows (``text``, ``expect``, ``set``, ...) of the given files, each text once per set."""
    rows, seen = [], set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("set", path.stem), row["text"])
            if key not in seen:
                seen.add(key)
                rows.append(row | {"set": key[0]})
    return rows


def collect_texts(args: argparse.Namespace) -> None:
    """Every instruction of the closed-loop protocol, with the spec it means.

    The instruction of request i depends on the condition, load, seed and the request's candidate
    paths only, not on the policy, so one pass with the oracle lists them all.
    """
    from multiprocessing import Pool

    from evaluate import CONDITIONS, EVAL_LOADS, EVAL_SEEDS, WARMUP, WINDOW

    conditions = args.conditions or [c for c in CONDITIONS if c != "I0"]
    warmup = WARMUP if args.warmup is None else args.warmup
    window = WINDOW if args.window is None else args.window
    jobs = [
        {"policy": "oracle", "condition": c, "load": load, "seed": seed, "warmup": warmup, "window": window,
         "topology": args.topology}
        for c in conditions for load in (args.loads or EVAL_LOADS) for seed in (args.seeds or EVAL_SEEDS)
    ]  # fmt: skip
    rows: dict[str, dict] = {}
    with Pool(args.workers) as pool:
        for done, found in enumerate(pool.imap_unordered(_episode_texts, jobs), start=1):
            for row in found:
                rows.setdefault(row["text"], row)
            print(f"[{done:>2}/{len(jobs)}] {len(rows)} distinct instructions", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        for text in sorted(rows):
            handle.write(json.dumps(rows[text], ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} instructions to {args.out}")


def _episode_texts(job: dict) -> list[dict]:
    from evaluate import Episode
    from policies import Oracle

    episode, policy, rows = Episode(job), Oracle(), {}
    while episode.remaining:
        intent = episode.intent
        if getattr(intent, "arrivals", ()):  # standing policies: each text that arrives, with its true line
            for text, line in intent.arrivals:
                rows.setdefault(text, {"text": text, "expect": parse_spec(line).to_json(), "set": job["condition"],
                                       "lang": "any", "kind": "standing"})  # fmt: skip
        elif intent.text not in rows and intent.text != "none":
            rows[intent.text] = {"text": intent.text, "expect": meant(intent).to_json(), "set": job["condition"],
                                 "lang": getattr(intent, "lang", "en"), "kind": intent.key}  # fmt: skip
        (decision,) = policy.decide([episode.request()])
        episode.apply(decision)
    return list(rows.values())


def parse(args: argparse.Namespace) -> None:
    """Ask the translator for every instruction of the given sets (fills its answer cache)."""
    from evaluate import upload_results

    translator = make_translator(args.policy, args.topology, **_llm(args))
    texts = sorted({row["text"] for row in read_rows(args.sets)})
    started = synced = time.perf_counter()
    for start in range(0, len(texts), args.chunk):
        translator.lines(texts[start : start + args.chunk])
        done = min(start + args.chunk, len(texts))
        print(
            f"{args.policy}: {done}/{len(texts)} instructions, {time.perf_counter() - started:.0f} s",
            flush=True,
        )
        cache = getattr(getattr(translator, "llm", None), "cache_path", None)
        due = done == len(texts) or time.perf_counter() - synced > 120  # the cache is the only thing to lose
        if args.sync_repo and cache is not None and cache.exists() and due:
            upload_results(args.sync_repo, [cache])
            synced = time.perf_counter()


def score(args: argparse.Namespace) -> None:
    """Translation accuracy on labelled instructions.

    For an instruction that should be applied: ``correct`` (same meaning), ``flagged`` (not
    applied: visible to the operator) or ``wrong`` (applied with another meaning: silent).
    For one that should not be applied: ``flagged`` or ``applied`` (silent).
    """
    translator = make_translator(args.policy, args.topology, **_llm(args))
    rows = read_rows(args.sets)
    lines = translator.lines([row["text"] for row in rows])
    groups: dict[tuple, Counter] = defaultdict(Counter)
    examples: dict[tuple, list] = defaultdict(list)
    for row, (line, seconds) in zip(rows, lines, strict=True):
        expect = Spec.from_json(row["expect"])
        raw = parse_spec(line)
        got = validate(raw, translator.topology)
        if expect.applies:
            outcome = (
                "correct" if got.meaning() == expect.meaning() else "wrong" if got.applies else "flagged"
            )
        else:
            outcome = "applied" if got.applies else "flagged"
        for key in ((row["set"], "all", "all"), (row["set"], row.get("lang", "en"), row.get("kind", "all"))):
            counter = groups[key]
            counter["n"] += 1
            counter[outcome] += 1
            counter["malformed"] += raw.status == "malformed"
            counter["same_status"] += got.status == expect.status
            counter["ms"] += 1000 * seconds
        bad = outcome in ("wrong", "applied") or (outcome == "flagged" and expect.applies)
        if bad and len(examples[(row["set"], outcome)]) < args.examples:
            examples[(row["set"], outcome)].append(
                {
                    "text": row["text"],
                    "expected": format_spec(expect, getattr(translator, "version", 1))
                    if expect.applies
                    else expect.status,
                    "answer": line,
                    "status": got.status,
                }
            )
    result = {
        "metadata": {"policy": translator.describe(), "command": " ".join(sys.argv),
                     "finished_utc": datetime.now(UTC).isoformat(), "sets": [p.name for p in args.sets]},
        "groups": [
            {"set": s, "lang": lang, "kind": kind, "n": c["n"],
             **{k: c[k] for k in ("correct", "flagged", "wrong", "applied", "malformed", "same_status")},
             "ms_per_instruction": c["ms"] / c["n"]}
            for (s, lang, kind), c in sorted(groups.items())
        ],
        "examples": [{"set": s, "outcome": o, "cases": cases} for (s, o), cases in sorted(examples.items())],
    }  # fmt: skip
    out = args.out or ROOT / "results" / "translate" / f"{args.policy}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for group in result["groups"]:
        if group["lang"] == "all":
            n = group["n"]
            print(f"{group['set']:22s} n={n:6d}  correct {100 * group['correct'] / n:5.1f}%  flagged "
                  f"{100 * group['flagged'] / n:5.1f}%  wrong {100 * group['wrong'] / n:5.1f}%  applied "
                  f"{100 * group['applied'] / n:5.1f}%")  # fmt: skip
    print(f"wrote {out}")
    if args.sync_repo:
        from evaluate import upload_results

        upload_results(args.sync_repo, [out])


def batch(args: argparse.Namespace) -> None:
    """Several ``parse`` and ``score`` runs in one process, so the model is loaded once.

    A job is ``policy:topology:regex|none:file,file,...``; its scores go to
    ``results/translate/<policy>.json`` (``<policy>_<topology>.json`` off nobel-eu).
    """
    for job in args.jobs:
        policy, topology, structured, files = job.split(":")
        name = policy if topology == "nobel-eu" else f"{policy}_{topology}"
        one = argparse.Namespace(**{**vars(args), "policy": policy, "topology": topology, "structured": structured,
                                    "sets": [Path(f) for f in files.split(",")],
                                    "out": ROOT / "results" / "translate" / f"{name}.json"})  # fmt: skip
        print(f"=== {job}", flush=True)
        parse(one)
        score(one)


def _llm(args: argparse.Namespace) -> dict:
    return {"model": args.model, "adapter": args.adapter, "structured": args.structured,
            "template_kwargs": json.loads(args.template_kwargs), "max_batch": args.batch,
            "base_url": args.base_url, "extra_body": json.loads(args.extra_body),
            "concurrency": args.concurrency}  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["texts", "parse", "score", "batch"])
    parser.add_argument(
        "--jobs", nargs="+", default=[], help="batch: policy:topology:regex|none:file,file,..."
    )
    parser.add_argument("--policy", default="translate_keyword")
    parser.add_argument("--sets", type=Path, nargs="+", default=[], help="instruction files (JSON lines)")
    parser.add_argument("--topology", default="nobel-eu")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=2, help="texts: simulator processes")
    parser.add_argument("--conditions", nargs="+", default=None, help="texts: closed-loop conditions to list")
    parser.add_argument(
        "--loads", type=int, nargs="+", default=None, help="texts: loads (default: the protocol's)"
    )
    parser.add_argument(
        "--seeds", type=int, nargs="+", default=None, help="texts: seeds (default: the protocol's)"
    )
    parser.add_argument(
        "--warmup", type=int, default=None, help="texts: warm-up requests (default: the protocol's)"
    )
    parser.add_argument(
        "--window", type=int, default=None, help="texts: measured requests (default: the protocol's)"
    )
    parser.add_argument("--examples", type=int, default=8, help="score: failures kept per set and kind")
    parser.add_argument("--chunk", type=int, default=512, help="parse: instructions between two syncs")
    parser.add_argument("--model", default=None)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--structured", choices=["regex", "none"], default="regex")
    parser.add_argument("--template-kwargs", default="{}")
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument(
        "--base-url",
        default=None,
        help="a server that takes a GBNF grammar (llama-server), e.g. http://127.0.0.1:8080/v1",
    )
    parser.add_argument(
        "--extra-body", default="{}", help="JSON merged into each request, e.g. the LoRA adapters to apply"
    )
    parser.add_argument("--concurrency", type=int, default=4, help="parallel requests to the server")
    parser.add_argument("--sync-repo", default=None, help="Hub dataset repo to copy cache and results to")
    args = parser.parse_args()
    if args.mode == "texts":
        args.out = args.out or ROOT / "data" / "instructions" / "closed_loop.jsonl"
        collect_texts(args)
    else:
        {"parse": parse, "score": score, "batch": batch}[args.mode](args)


if __name__ == "__main__":
    main()
