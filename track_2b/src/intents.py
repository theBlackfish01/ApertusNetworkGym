"""Operator intents: wording, admissible sets and the teacher inside each set (SPEC section 3).

Every intent is a rule about *paths*, so the admissible set of a request is a set of candidate
path indices (any valid start on such a path is admissible) and a violation is a decision
outside it. The teacher ranks the admissible paths with the rule that matches the intent and
takes the first valid start on the best one.

| Id | Meaning                         | Admissible paths (among feasible ones)   | Teacher inside the set   |
| -- | ------------------------------- | ---------------------------------------- | ------------------------ |
| I0 | none                            | all                                      | BM-LS-KSP                |
| I1 | avoid a named link              | those not containing the link            | BM-LS-KSP                |
| I2 | fewest hops                     | those with the minimum hop count         | shortest km, first fit   |
| I3 | least loaded                    | those with the most free slots           | shortest km, first fit   |
| I4 | fewest slots                    | those with the minimum slots needed      | shortest km, first fit   |

Pairs combine as set intersection; an empty set means the only admissible decision is reject.
A path is feasible when it has at least one valid (resource and QoT) start.

BM-LS-KSP here means: the admissible path whose first listed block starts lowest, ties by path
order. It reproduces ONG's ``select_jocn_ls_bm_ksp_action`` in 99.95 % of decisions (the rest
are starts that are only valid with a wider format, which the prompt does not list). "Free
slots" of a path are the slots free on every one of its links. Both are deviations from the
letter of the spec; ``docs/decisions.md`` has the measurements behind them.

Wording: ten paraphrases per intent; the first seven are used in training, the last three are
held out. The paraphrases below are drafts for the owner to review (SPEC section 10).
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from view import Choice, PathView, RequestView

SINGLES = ("I1", "I2", "I3", "I4")
TRAIN_PAIRS = (("I1", "I2"), ("I1", "I3"))
HELDOUT_PAIRS = (("I1", "I4"), ("I2", "I3"))
N_TRAIN_PARAPHRASES = 7
RANKED = frozenset({"I2", "I3", "I4"})  # intents whose teacher ranks paths by km, then first fit

# {link} is a noun phrase from LINK_FORMS; {Link} is the same phrase with a capital first letter.
PARAPHRASES: dict[str, tuple[str, ...]] = {
    "I1": (
        "{Link} is under maintenance; do not route through it.",
        "Avoid {link} for this request.",
        "Do not use {link}; it is being serviced.",
        "Maintenance window on {link}: keep this lightpath off it.",
        "{Link} must not carry this service.",
        "Route around {link}.",
        "This connection may not traverse {link}.",
        # held out
        "Field crews are working on {link}, so pick a route that skips it.",
        "Exclude {link} from the route.",
        "{Link} is out of bounds for now; stay clear of it.",
    ),
    "I2": (
        "Latency-sensitive: use the path with the fewest hops that fits.",
        "Use the feasible path with the fewest hops.",
        "Minimise the hop count for this service.",
        "This service is delay-critical; take the route with the fewest hops that can carry it.",
        "Pick the path that crosses the fewest links among those with room.",
        "Keep the number of hops as low as possible.",
        "Low latency required: fewest hops among the paths that fit.",
        # held out
        "The customer wants the most direct route, counted in hops, that can still be provisioned.",
        "Go through as few intermediate nodes as possible.",
        "Shortest hop count wins for this one, as long as the path has a valid slot.",
    ),
    "I3": (
        "Spread the load: use the least-loaded feasible path.",
        "Balance the network: choose the feasible path with the most free slots.",
        "Use the path with the most free spectrum.",
        "Prefer the emptiest path that can carry this request.",
        "Load balancing: route over the path with the highest free-slot count.",
        "Keep busy routes clear; take the path with the most spare slots.",
        "Pick the least congested candidate that fits.",
        # held out
        "Send this one where there is the most room left.",
        "Even out utilisation by selecting the candidate with the largest number of free slots.",
        "Avoid crowded routes: the roomiest feasible path is the right choice.",
    ),
    "I4": (
        "Be spectrum-efficient: use the option needing the fewest slots.",
        "Minimise the number of slots this service occupies.",
        "Use the path whose modulation needs the fewest slots.",
        "Save spectrum: choose the candidate with the smallest slot requirement.",
        "Spectrum is scarce; pick the option that consumes the fewest slots.",
        "Choose the narrowest allocation available.",
        "Fewest slots needed wins.",
        # held out
        "Conserve bandwidth by taking the candidate with the lowest slot demand.",
        "Occupy as little spectrum as you can for this request.",
        "Go with whichever feasible path gives the most compact channel.",
    ),
}

# Ways of naming a link (SPEC section 3). The prompt lists links as "A-B" in path direction; an
# intent may name the same link in either direction.
LINK_FORMS = (
    "the {a}-{b} link",
    "the link between {a} and {b}",
    "the {a}–{b} span",
    "{a}-{b}",
)


@dataclass(frozen=True)
class Intent:
    ids: tuple[str, ...] = ()  # () = no intent (I0)
    text: str = "none"  # what follows "Intent:" in the prompt
    link: tuple[str, str] | None = None  # the link named by I1, in the order it is named
    paraphrases: tuple[int, ...] = ()  # paraphrase index for each id
    link_form: int | None = None

    @property
    def key(self) -> str:
        return "+".join(self.ids) if self.ids else "I0"

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> Intent:
        return cls(
            ids=tuple(data["ids"]),
            text=data["text"],
            link=tuple(data["link"]) if data["link"] else None,
            paraphrases=tuple(data["paraphrases"]),
            link_form=data["link_form"],
        )


NO_INTENT = Intent()


def ids_from_key(key: str) -> tuple[str, ...]:
    return () if key == "I0" else tuple(key.split("+"))


def candidate_links(view: RequestView) -> list[tuple[str, str]]:
    """Every link on at least one candidate path, each once, endpoints in alphabetical order."""
    return sorted({tuple(sorted(link)) for path in view.paths for link in path.links})


def sample_intent(
    view: RequestView, ids: tuple[str, ...], rng: random.Random, *, heldout: bool = False
) -> Intent:
    """An intent of the given kind for this request, with random wording.

    ``heldout`` selects the held-out paraphrases. For I1 the link is drawn uniformly from the
    links on the candidate paths, named in a random direction and form.
    """
    if not ids:
        return NO_INTENT
    pool = range(N_TRAIN_PARAPHRASES, 10) if heldout else range(N_TRAIN_PARAPHRASES)
    link = link_form = None
    sentences, chosen = [], []
    for intent_id in ids:
        index = rng.choice(pool)
        chosen.append(index)
        sentence = PARAPHRASES[intent_id][index]
        if intent_id == "I1":
            a, b = rng.choice(candidate_links(view))
            link = (a, b) if rng.random() < 0.5 else (b, a)
            link_form = rng.randrange(len(LINK_FORMS))
            phrase = LINK_FORMS[link_form].format(a=link[0], b=link[1])
            sentence = sentence.format(link=phrase, Link=phrase[0].upper() + phrase[1:])
        sentences.append(sentence)
    if len(sentences) > 1 and rng.random() < 0.5:
        sentences.reverse()
    return Intent(tuple(ids), " ".join(sentences), link, tuple(chosen), link_form)


def _allowed_by(intent_id: str, intent: Intent, feasible: list[PathView]) -> set[int]:
    if intent_id == "I1":
        return {p.index for p in feasible if not p.has_link(*intent.link)}
    if intent_id == "I2":
        best = min(p.hops for p in feasible)
        return {p.index for p in feasible if p.hops == best}
    if intent_id == "I3":
        best = max(p.free_slots for p in feasible)
        return {p.index for p in feasible if p.free_slots == best}
    if intent_id == "I4":
        best = min(p.slots_needed for p in feasible)
        return {p.index for p in feasible if p.slots_needed == best}
    raise ValueError(f"unknown intent id {intent_id!r}")


def admissible_paths(view: RequestView, intent: Intent) -> tuple[int, ...]:
    """Indices of the paths the intent allows; empty means the request must be rejected."""
    feasible = [p for p in view.paths if p.feasible]
    allowed = {p.index for p in feasible}
    if feasible:
        for intent_id in intent.ids:
            allowed &= _allowed_by(intent_id, intent, feasible)
    return tuple(sorted(allowed))


def teacher_choice(view: RequestView, intent: Intent) -> Choice:
    """The teacher's decision inside the admissible set (reject when it is empty)."""
    paths = [view.paths[i] for i in admissible_paths(view, intent)]
    if not paths:
        return None
    if RANKED & set(intent.ids):
        best = min(paths, key=lambda p: (p.km, p.index))
    else:
        # BM-LS-KSP on the listed blocks: lowest start slot, ties by path order.
        best = min(paths, key=lambda p: (p.first_slot, p.index))
    return (best.index, best.first_slot)


def is_admissible(view: RequestView, intent: Intent, choice: Choice) -> bool:
    """Whether a *valid* decision respects the intent.

    Reject is admissible only when no path is. For I4 the start must also lie in a listed
    block, otherwise the service would occupy more than the minimum number of slots.
    """
    allowed = admissible_paths(view, intent)
    if choice is None:
        return not allowed
    path, slot = choice
    if path not in allowed:
        return False
    return "I4" not in intent.ids or view.paths[path].in_block(slot)
