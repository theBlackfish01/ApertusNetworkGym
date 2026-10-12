"""The closed loop with standing policies (condition ``standing4``).

Policies arrive during an episode: sentences of the fourth round's test sets (a routing sentence
with a scope or a lifetime, in four languages, independently written), three at the start and
then one every ``ARRIVAL_EVERY`` simulated hours. A policy holds for the hours it states or until
the operator withdraws it, and covers the requests its scope names. When a fifth policy would be
active the operator withdraws the oldest open one. The truth is a table of the policies' true
specs; a policy under test keeps its own table from what its reader understood. A request's
intent carries the texts that arrived with it, the texts withdrawn, the simulated hour and the
true effective spec, so every policy sees the same stream and the evaluator judges every
decision against the truth.

Policies of this condition (``make_policy``):

    standing_oracle        the truth table: no violation by construction
    standing_noscope       the true specs, but every active policy covers every request
    standing_nountil       the true specs, but no policy ever expires
    standing<v>_<reader>   each policy read once by ``translate<v>_<reader>`` (``standing4_ft``, or
                           ``standing3_ft``, whose format has no scope and no lifetime)

Time: the simulator's clock runs in units of which a request's holding time spans a few
thousand; ``HOUR`` of them are taken as one hour, so that a window of 2,000 requests spans about
15 hours at 390 Erlang and 25 at 240, and a lifetime of a few hours ends inside it.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, replace
from pathlib import Path

from intents import Intent
from policies import Decision, Policy, Request
from spec import EMPTY, Spec, choose, format_spec, parse_spec, validate
from standing import PolicyTable
from translate import make_translator, read_rows
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]
CONDITION = "standing4"
SOURCES = ("v4_en", "v4_de", "v4_fr", "v4_it")
HOUR = 3600.0  # simulator time units per hour
FIRST = 3  # policies in force when the window opens
ARRIVAL_EVERY = 2.0  # hours between later arrivals
MAX_ACTIVE = 4
SHORT_SHARE = 0.5  # share of arrivals that state a short lifetime, so that expiry happens in the window
SHORT_HOURS = 12


@dataclass(frozen=True)
class StandingIntent(Intent):
    episode: str = ""
    arrivals: tuple[tuple[str, str], ...] = ()  # (text, true spec as a line of the fourth format)
    withdrawn: tuple[str, ...] = ()  # texts the operator withdrew with this request
    active: tuple[str, ...] = ()
    now: float = 0.0
    truth: str = ""  # the true effective spec for this request, as a line of the third format

    @property
    def key(self) -> str:
        return "standing"

    def truth_spec(self) -> Spec:
        return parse_spec(self.truth) if self.truth else EMPTY


def standing_material(spec: Spec) -> bool:
    """Whether a sentence makes sense as a policy that stands for many requests.

    A candidate by number is a per-request choice; a node to pass through only makes sense for
    requests from or to somewhere; a limit of one or two hops, or of a few hundred km, stands for
    nothing but rejection. The test sets carry such sentences; the stream leaves them out.
    """
    kind = (spec.scope or "any").partition(":")[0]
    return (
        spec.path is None
        and (not spec.via or kind in ("from", "to"))
        and (spec.max_hops is None or spec.max_hops >= 3)
        and (spec.max_km is None or spec.max_km >= 1000)
    )


class Stream:
    """The schedule of one episode: what arrives and is withdrawn, and the truth table."""

    def __init__(self, job: dict) -> None:
        self.job = job
        self.rng = random.Random(f"standing-{job['load']}-{job['seed']}")
        rows = read_rows([ROOT / "data" / "instructions" / f"{name}.jsonl" for name in SOURCES])
        self.pool = [(r["text"], s) for r in rows if standing_material(s := Spec.from_json(r["expect"]))]
        self.short = [(t, s) for t, s in self.pool if s.until is not None and s.until <= SHORT_HOURS]
        self.used: set[str] = set()
        self.table = PolicyTable()
        self.next_arrival: float | None = None

    def draw(self) -> tuple[str, Spec]:
        """A policy not used yet in this episode; a text comes again only when all have been used."""
        pool = self.short if self.rng.random() < SHORT_SHARE else self.pool
        unused = [item for item in pool if item[0] not in self.used] or [
            item for item in self.pool if item[0] not in self.used
        ]
        if not unused:
            self.used.clear()
            unused = list(pool)
        text, spec = self.rng.choice(unused)
        self.used.add(text)
        return text, spec

    def intent(self, view: RequestView, now: float) -> StandingIntent:
        arrivals, withdrawn = [], []
        if self.next_arrival is None:
            count, self.next_arrival = FIRST, now + ARRIVAL_EVERY
        elif now >= self.next_arrival:
            count, self.next_arrival = 1, self.next_arrival + ARRIVAL_EVERY
        else:
            count = 0
        self.table.expire(now)
        for _ in range(count):
            if len(self.table.active(now)) >= MAX_ACTIVE:
                oldest = min(self.table.active(now), key=lambda p: (p.spec.until is not None, p.created))
                self.table.withdraw(oldest.id)
                withdrawn.append(oldest.text)
            text, spec = self.draw()
            self.table.add(text, spec, now)
            arrivals.append((text, format_spec(spec, 4)))
        active = tuple(p.text for p in self.table.active(now))
        return StandingIntent(
            text="; ".join(t for t, _ in arrivals) or "none",
            episode=f"{self.job['load']}-{self.job['seed']}",
            arrivals=tuple(arrivals),
            withdrawn=tuple(withdrawn),
            active=active,
            now=now,
            truth=format_spec(self.table.effective(view, now), 3),
        )


class TableKeeper(Policy):
    """A policy that keeps one table per episode and decides with the rule engine."""

    parallel_safe = True

    def __init__(self, name: str) -> None:
        self.name = name
        self.tables: dict[str, PolicyTable] = {}
        self.dropped = 0  # policies the reader could not apply (refused or unresolved)

    def understand(self, text: str, true_line: str) -> Spec:
        raise NotImplementedError

    def decide(self, requests: list[Request]) -> list[Decision]:
        decisions = []
        for request in requests:
            started = time.perf_counter()
            intent: StandingIntent = request.intent  # type: ignore[assignment]
            table = self.tables.setdefault(intent.episode, PolicyTable())
            for text in intent.withdrawn:
                for policy in list(table.policies):
                    if policy.text == text:
                        table.withdraw(policy.id)
            for text, true_line in intent.arrivals:
                spec = self.understand(text, true_line)
                if spec.applies:
                    table.add(text, spec, intent.now)
                else:
                    self.dropped += 1
            table.expire(intent.now)
            effective = table.effective(request.view, intent.now)
            choice = choose(request.view, effective)
            decisions.append(
                Decision(choice, raw=format_spec(effective, 3), seconds=time.perf_counter() - started)
            )
        return decisions

    def describe(self) -> dict:
        return {"name": self.name, "dropped_policies": self.dropped}


class Truthful(TableKeeper):
    """The true specs, possibly stripped of their scope or lifetime (the ablations)."""

    def __init__(self, name: str, scope: bool = True, until: bool = True) -> None:
        super().__init__(name)
        self.keep_scope, self.keep_until = scope, until

    def understand(self, text: str, true_line: str) -> Spec:
        spec = parse_spec(true_line)
        if not self.keep_scope:
            spec = replace(spec, scope=None)
        if not self.keep_until:
            spec = replace(spec, until=None)
        return spec


class Read(TableKeeper):
    """Each policy read once by a translator; what it understood is what the table holds."""

    def __init__(self, name: str, translator) -> None:
        super().__init__(name)
        self.translator = translator
        self.topology = translator.topology

    def understand(self, text: str, true_line: str) -> Spec:
        return validate(self.translator.translate([text])[0], self.topology)

    def describe(self) -> dict:
        return super().describe() | {"translator": self.translator.describe()}


def make_standing_policy(name: str, topology: str = "nobel-eu", **llm) -> Policy:
    if name == "standing_oracle":
        return Truthful(name)
    if name == "standing_noscope":
        return Truthful(name, scope=False)
    if name == "standing_nountil":
        return Truthful(name, until=False)
    if name.startswith("standing") and "_" in name:
        version, _, kind = name.removeprefix("standing").partition("_")
        return Read(name, make_translator(f"translate{version}_{kind}", topology, **llm))
    raise ValueError(f"unknown standing policy {name!r}")
