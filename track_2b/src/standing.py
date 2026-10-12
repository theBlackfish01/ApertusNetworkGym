"""Standing policies: instructions with a scope and a lifetime, kept in a table.

An operator does not type an instruction per request; a policy is stated once ("for 400G
services, avoid the Zurich-Milan link for the next six hours") and the system applies it to the
requests it covers while it holds. This module is the table behind the console and the closed
loop: which policies are active at a time, which cover a request, the one spec they combine to,
the conflicts a new policy raises against the ones in force, and the report per policy (how many
requests it covered, how many decisions it changed, how many it rejected). Time is the
simulator's: one unit is one hour.

Combining the routing parts of several policies: constraints add up (every avoided link and
node, every node to pass through, the tighter limit on hops and km); a candidate by number comes
from the newest policy that names one; preferences are the newest policy's first, older ones
break ties. Conflicts are reported, not resolved: the operator decides.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from spec import EMPTY, Spec, Topology
from view import Choice, RequestView


@dataclass
class Standing:
    id: int
    text: str
    spec: Spec  # the fourth format: routing part, scope, until
    created: float  # simulated hour
    asked: bool = False
    counts: dict = field(
        default_factory=lambda: {"in_scope": 0, "changed": 0, "rejected": 0, "violations": 0}
    )

    @property
    def expires(self) -> float | None:
        return None if self.spec.until is None else self.created + self.spec.until

    def active(self, now: float) -> bool:
        return self.expires is None or now < self.expires

    def covers(self, view: RequestView) -> bool:
        return covers(self.spec.scope, view)


def covers(scope: str | None, view: RequestView) -> bool:
    if not scope:
        return True
    kind, _, value = scope.partition(":")
    if kind == "rate":
        return view.bit_rate == int(value)
    if kind == "from":
        return view.source == value
    if kind == "to":
        return view.destination == value
    return False


def overlap(a: str | None, b: str | None) -> bool:
    """Whether two scopes can cover the same request."""
    if not a or not b:
        return True
    ka, _, va = a.partition(":")
    kb, _, vb = b.partition(":")
    if ka == kb:
        return va == vb
    if {ka, kb} == {"from", "to"}:
        return va != vb  # a request from A to A does not exist
    return True  # a bit rate with a node


def combine(specs: list[Spec]) -> Spec:
    """One routing spec from several, newest first."""
    applying = [s for s in specs if s.applies]
    if not applying:
        return EMPTY
    avoid: list[tuple[str, str]] = []
    seen: set[frozenset] = set()
    for s in applying:
        for link in s.avoid:
            if frozenset(link) not in seen:
                seen.add(frozenset(link))
                avoid.append(link)
    hops = [s.max_hops for s in applying if s.max_hops is not None]
    km = [s.max_km for s in applying if s.max_km is not None]
    return Spec(
        avoid=tuple(avoid),
        prefer=tuple(dict.fromkeys(p for s in applying for p in s.prefer)),
        nodes=tuple(dict.fromkeys(n for s in applying for n in s.nodes)),
        via=tuple(dict.fromkeys(n for s in applying for n in s.via)),
        max_hops=min(hops) if hops else None,
        max_km=min(km) if km else None,
        path=next((s.path for s in applying if s.path is not None), None),
        rest=any(s.rest for s in applying),
    )


def _connected(topology: Topology, node: str, avoid_links: set[frozenset], avoid_nodes: set[str]) -> bool:
    """Whether ``node`` still reaches another node once the avoided links and nodes are removed."""
    if node not in topology.nodes:
        return True
    queue, seen = deque([node]), {node}
    while queue:
        here = queue.popleft()
        for link in topology.links:
            if here in link and link not in avoid_links:
                (other,) = set(link) - {here} or {here}
                if other != here and other not in seen and other not in avoid_nodes:
                    return True
    return False


class PolicyTable:
    def __init__(self, topology: Topology | None = None) -> None:
        self.topology = topology
        self.policies: list[Standing] = []
        self.withdrawn: list[Standing] = []
        self._next = 1

    # ---- lifecycle ---------------------------------------------------------------------------
    def add(self, text: str, spec: Spec, now: float, asked: bool = False) -> tuple[Standing, list[dict]]:
        found = self.conflicts(spec, now)
        policy = Standing(self._next, text, spec, now, asked)
        self._next += 1
        self.policies.append(policy)
        return policy, found

    def withdraw(self, policy_id: int) -> Standing | None:
        for policy in self.policies:
            if policy.id == policy_id:
                self.policies.remove(policy)
                self.withdrawn.append(policy)
                return policy
        return None

    def expire(self, now: float) -> list[Standing]:
        gone = [p for p in self.policies if not p.active(now)]
        for policy in gone:
            self.policies.remove(policy)
            self.withdrawn.append(policy)
        return gone

    def active(self, now: float) -> list[Standing]:
        return [p for p in self.policies if p.active(now)]

    def applicable(self, view: RequestView, now: float) -> list[Standing]:
        return [p for p in self.active(now) if p.covers(view)]

    def effective(self, view: RequestView, now: float) -> Spec:
        """The spec the rule engine applies to this request: the newest covering policy first."""
        return combine([p.spec.routing() for p in reversed(self.applicable(view, now))])

    # ---- conflicts ---------------------------------------------------------------------------
    def conflicts(self, spec: Spec, now: float) -> list[dict]:
        """What a new policy would clash with among the active ones (contradictions and overrides)."""
        found = []
        if not spec.applies:
            return found
        for other in self.active(now):
            o = other.spec
            if not overlap(spec.scope, o.scope):
                continue
            for node in spec.via:
                if node in o.nodes:
                    found.append(
                        self._conflict(
                            "contradiction",
                            other,
                            f"must pass through {node}, which policy {other.id} avoids",
                        )
                    )
            for node in spec.nodes:
                if node in o.via:
                    found.append(
                        self._conflict(
                            "contradiction", other, f"avoids {node}, which policy {other.id} requires"
                        )
                    )
            if spec.path is not None and o.path is not None and spec.path != o.path:
                found.append(
                    self._conflict(
                        "contradiction",
                        other,
                        f"candidate {spec.path} against candidate {o.path} of policy {other.id}",
                    )
                )
            if spec.prefer and o.prefer and spec.prefer[0] != o.prefer[0]:
                found.append(
                    self._conflict(
                        "override",
                        other,
                        f"prefers {spec.prefer[0]} where policy {other.id} prefers {o.prefer[0]}; the newer policy decides, the older breaks ties",
                    )
                )
        if self.topology is not None:
            combined = combine(
                [spec.routing()]
                + [p.spec.routing() for p in self.active(now) if overlap(spec.scope, p.spec.scope)]
            )
            links, nodes = {frozenset(link) for link in combined.avoid}, set(combined.nodes)
            pinned = (
                [spec.scope.partition(":")[2]]
                if spec.scope and spec.scope.partition(":")[0] in ("from", "to")
                else []
            )
            for node in pinned + list(spec.via):
                if not _connected(self.topology, node, links, nodes):
                    found.append(
                        {
                            "kind": "contradiction",
                            "with": None,
                            "why": f"{node} is cut off by the avoided links and nodes",
                        }
                    )
        return found

    @staticmethod
    def _conflict(kind: str, other: Standing, why: str) -> dict:
        return {"kind": kind, "with": other.id, "with_text": other.text, "why": why}

    # ---- the report --------------------------------------------------------------------------
    def record(
        self, view: RequestView, now: float, choice: Choice, without: Choice, respects: bool | None
    ) -> None:
        """Count a decision for every policy that covered its request."""
        for policy in self.applicable(view, now):
            c = policy.counts
            c["in_scope"] += 1
            c["changed"] += (choice is None) != (without is None) or (
                choice is not None and without is not None and choice[0] != without[0]
            )
            c["rejected"] += choice is None
            c["violations"] += respects is False

    def report(self, now: float) -> list[dict]:
        rows = []
        for policy in self.policies + self.withdrawn:
            rows.append({"id": policy.id, "text": policy.text, "scope": policy.spec.scope or "any",
                         "until": policy.spec.until, "created": round(policy.created, 2),
                         "expires": None if policy.expires is None else round(policy.expires, 2),
                         "active": policy in self.policies and policy.active(now), "asked": policy.asked,
                         **policy.counts})  # fmt: skip
        return rows
