"""A closed-loop condition that mixes what an operator might type: ``operations_mix``.

The conditions of SPEC section 7 give every request an instruction of one kind, in the dataset's
wording. This one draws, per request:

    15 %  nothing
    45 %  a supported instruction (the four intents and their four pairs) in the independent wording
    25 %  an instruction of a type nobody wrote a rule for (pass through a node, avoid a node, a hop
          limit, a length limit, the shortest route in km, a given candidate)
    10 %  text that is no instruction
     5 %  an avoid-link instruction that cannot be resolved (no such link)

Like every condition, the instruction of request i depends on the condition, load, seed and the
request's candidate paths only, never on the state of the network, so all policies see the same
stream and a translator's answers can be computed beforehand.

What counts as respecting it: a supported instruction as in ``intents.py``; an unseen type by its
rule (a constraint that no feasible path meets asks for a reject, the preference never does); for
the three other kinds the request is to be served as if nothing had been typed.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import mixed3
from corpora import TEST_OUTSIDE, fill, load_independent, reword
from intents import (
    HELDOUT_PAIRS,
    SINGLES,
    TRAIN_PAIRS,
    Intent,
    admissible_paths,
    is_admissible,
    sample_intent,
)
from intents import teacher_choice as intent_teacher
from spec import EMPTY, Spec, from_intent, load_topology, mention_order, respects
from view import Choice, PathView, RequestView

ROOT = Path(__file__).resolve().parents[1]
CONDITION = "operations_mix"
MIX = (("none", 15), ("supported", 45), ("unseen", 25), ("not_instruction", 10), ("faulty", 5))
TYPES = ("via_node", "avoid_node", "max_hops", "max_km", "shortest_km", "path_index")
PREFERENCES = ("shortest_km",)  # unseen types that never ask for a reject


@dataclass(frozen=True)
class Instruction(Intent):
    """An intent with what the mixed condition adds: its kind, the rule of an unseen type, the order of mention."""

    kind: str = "none"  # none | supported | unseen | not_instruction | faulty
    rule: tuple = ()  # unseen: (type, value)
    order: tuple[str, ...] = ()  # supported: the ids in the order the text states them

    @property
    def key(self) -> str:
        if self.kind == "unseen":
            return self.rule[0]
        if self.kind in ("not_instruction", "faulty"):
            return self.kind
        return "+".join(self.ids) if self.ids else "I0"


@cache
def _sources() -> tuple[dict, dict]:
    unseen = json.loads((ROOT / "data" / "instructions" / "unseen_source.json").read_text(encoding="utf-8"))
    return load_independent(), unseen


def sample(view: RequestView, rng: random.Random) -> Instruction:
    """The instruction of one request; depends on the candidate paths (not on their state) and ``rng``."""
    independent, unseen = _sources()
    kind = rng.choices([k for k, _ in MIX], weights=[w for _, w in MIX])[0]
    inner = sorted({n for p in view.paths for n in p.nodes[1:-1]})
    on_paths = sorted({n for p in view.paths for n in p.nodes})
    if kind == "unseen":
        kinds = [t for t in TYPES if inner or t not in ("via_node", "avoid_node")]
        name = rng.choice(kinds)
        if name in ("via_node", "avoid_node"):
            value, key = rng.choice(inner), "a"
        elif name == "max_hops":
            value, key = rng.randint(min(p.hops for p in view.paths), max(p.hops for p in view.paths)), "n"
        elif name == "max_km":
            low, high = min(p.km for p in view.paths), max(p.km for p in view.paths)
            value, key = 50 * rng.randint(-(-low // 50), max(high // 50, -(-low // 50))), "km"
        elif name == "path_index":
            value, key = rng.randrange(len(view.paths)), "n"
        else:
            value, key = None, ""
        text = rng.choice(unseen[name]).replace("{" + key + "}", str(value))
        return Instruction(text=text, kind="unseen", rule=(name, value))
    if kind == "supported":
        ids = rng.choice([(i,) for i in SINGLES] + list(TRAIN_PAIRS + HELDOUT_PAIRS))
        base = sample_intent(view, ids, rng)
        text = reword(base, independent["single"], independent["combined"], {}, rng)
        return Instruction(
            ids=base.ids, text=text, link=base.link, kind="supported", order=mention_order(base)
        )
    if kind == "not_instruction":
        return Instruction(text=fill(rng.choice(unseen["not_instruction"]), rng.choice(on_paths)), kind=kind)
    if kind == "faulty":
        topology = load_topology("nobel-eu")
        apart = sorted({(p.nodes[i], p.nodes[j]) for p in view.paths for i in range(len(p.nodes))
                        for j in range(i + 2, len(p.nodes)) if not topology.has_link(p.nodes[i], p.nodes[j])})  # fmt: skip
        pair = (
            rng.choice(apart)
            if apart and rng.random() < 0.5
            else (rng.choice(on_paths), rng.choice(TEST_OUTSIDE))
        )
        a, b = pair if rng.random() < 0.5 else pair[::-1]
        return Instruction(text=fill(rng.choice(independent["single"]["I1"]), a, b), kind=kind)
    return Instruction()


def expected(instruction: Instruction) -> Spec:
    """What a translator of the second format should answer."""
    if instruction.kind == "supported":
        return from_intent(instruction, order=instruction.order)
    status = {"unseen": "unsupported", "not_instruction": "no_instruction", "faulty": "unresolved"}
    return Spec(status=status[instruction.kind]) if instruction.kind in status else EMPTY


def _complies(path: PathView, rule: tuple, shortest: int) -> bool:
    name, value = rule
    if name == "via_node":
        return value in path.nodes[1:-1]
    if name == "avoid_node":
        return value not in path.nodes[1:-1]
    if name == "max_hops":
        return path.hops <= value
    if name == "max_km":
        return path.km <= value
    if name == "path_index":
        return path.index == value
    return path.km == shortest


def allowed(view: RequestView, instruction: Intent) -> tuple[int, ...]:
    """Indices of the paths that respect the instruction; empty means the request must be rejected."""
    if isinstance(instruction, mixed3.Instruction):  # the third round has its own rules
        return mixed3.allowed(view, instruction)
    if getattr(instruction, "kind", "") != "unseen":
        return admissible_paths(view, instruction)
    feasible = [p for p in view.paths if p.feasible]
    shortest = min((p.km for p in feasible), default=0)
    return tuple(p.index for p in feasible if _complies(p, instruction.rule, shortest))


def respected(view: RequestView, instruction: Intent, choice: Choice, rule: str = "intersection") -> bool:
    """Whether a valid decision respects the instruction (``intents.is_admissible`` for every kind)."""
    if isinstance(instruction, mixed3.Instruction):
        return mixed3.respected(view, instruction, choice)
    kind = getattr(instruction, "kind", "")
    if kind == "unseen":
        ok = allowed(view, instruction)
        return (not ok) if choice is None else choice[0] in ok
    if rule == "ordered":
        spec = (
            from_intent(instruction, order=instruction.order)
            if kind == "supported"
            else from_intent(instruction)
        )
        return respects(view, spec, choice, "ordered")
    return is_admissible(view, instruction, choice)


def oracle(view: RequestView, instruction: Intent) -> Choice:
    """The reference decision: the teacher inside the paths that respect the instruction."""
    if isinstance(instruction, mixed3.Instruction):
        return mixed3.oracle(view, instruction)
    if getattr(instruction, "kind", "") != "unseen":
        return intent_teacher(view, instruction)
    paths = [view.paths[i] for i in allowed(view, instruction)]
    if not paths:
        return None
    best = min(paths, key=lambda p: (p.first_slot, p.index))
    return (best.index, best.first_slot)
