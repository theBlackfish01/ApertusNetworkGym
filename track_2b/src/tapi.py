"""The policy language as a TAPI constraint (ONF Transport API 2.1.3, ``tapi-path-computation``).

A TAPI connectivity-service request carries a ``topology-constraint`` (links, nodes and paths
to include or exclude) and a ``routing-constraint`` (the largest allowed number of hops or cost,
and one route objective function). The slots of the third format map onto them:

    avoid=<links>   -> topology-constraint.exclude-link
    avoid=<nodes>   -> topology-constraint.exclude-node
    via=<node>      -> topology-constraint.include-node
    hops=<n>        -> routing-constraint.max-allowed-hops.value
    km=<n>          -> routing-constraint.max-allowed-cost.value (the cost characteristic is km)
    path=<k>        -> topology-constraint.include-link: the links of candidate k (a loose list)
    prefer=hops     -> routing-constraint.route-objective-function MIN_WORK_ROUTE_HOP
    prefer=km       -> MIN_WORK_ROUTE_COST
    prefer=load     -> LOAD_BALANCE_MAX_UNUSED_CAPACITY
    prefer=slots    -> no TAPI objective: carried as a ``name`` entry

TAPI identifies links and nodes by uuid. Here each uuid is derived from the name (uuid5 in a
fixed namespace) and the name is listed next to it in ``name``, so a controller can map either.
TAPI has one objective function per request; the whole ordered list of preferences, and
anything the standard cannot carry, goes into ``name`` entries prefixed ``apertus-lightpath:``.
An instruction that is not applied (``unsupported``, ``no_instruction``, ``unresolved``) has no
TAPI form: :func:`constraints` returns ``None``.

    uv run python src/tapi.py "avoid=Berlin-Prague; via=Lyon; hops=4; km=any; path=any; prefer=km,load; rest=none"
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from spec import Spec, parse_spec
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/apertus-lightpath/tapi")
OBJECTIVE = {
    "hops": "MIN_WORK_ROUTE_HOP",
    "km": "MIN_WORK_ROUTE_COST",
    "load": "LOAD_BALANCE_MAX_UNUSED_CAPACITY",
}
PREFIX = "apertus-lightpath:"


def node_uuid(node: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"node/{node}"))


def link_uuid(a: str, b: str) -> str:
    """The same uuid for a link whichever way round its ends are written."""
    first, second = sorted((a, b))
    return str(uuid.uuid5(NAMESPACE, f"link/{first}-{second}"))


def constraints(spec: Spec, view: RequestView | None = None) -> dict | None:
    """The ``topology-constraint`` and ``routing-constraint`` objects of a spec, or ``None``."""
    if not spec.applies:
        return None
    names: list[dict] = []
    topology: dict = {}
    routing: dict = {}
    if spec.avoid:
        topology["exclude-link"] = [link_uuid(a, b) for a, b in spec.avoid]
        names += [{"value-name": "exclude-link", "value": f"{a}-{b}"} for a, b in spec.avoid]
    if spec.nodes:
        topology["exclude-node"] = [node_uuid(n) for n in spec.nodes]
        names += [{"value-name": "exclude-node", "value": n} for n in spec.nodes]
    if spec.via:
        topology["include-node"] = [node_uuid(n) for n in spec.via]
        names += [{"value-name": "include-node", "value": n} for n in spec.via]
    if spec.path is not None:
        if view is not None and spec.path < len(view.paths):
            links = view.paths[spec.path].links
            topology["include-link"] = [link_uuid(a, b) for a, b in links]
            names += [{"value-name": "include-link", "value": f"{a}-{b}"} for a, b in links]
        names.append({"value-name": PREFIX + "candidate", "value": str(spec.path)})
    if spec.max_hops is not None:
        routing["max-allowed-hops"] = {"value": spec.max_hops}
    if spec.max_km is not None:
        routing["max-allowed-cost"] = {"value": spec.max_km}
        routing["cost-characteristic"] = [
            {"cost-name": "km", "cost-value": "length", "cost-algorithm": "sum"}
        ]
    if spec.prefer:
        first = spec.prefer[0]
        if first in OBJECTIVE:
            routing["route-objective-function"] = OBJECTIVE[first]
        names.append({"value-name": PREFIX + "preference-order", "value": ",".join(spec.prefer)})
    if spec.rest:
        names.append({"value-name": PREFIX + "carried-in-part", "value": "true"})
    out: dict = {}
    if topology:
        out["topology-constraint"] = topology
    if routing:
        out["routing-constraint"] = routing
    if names:
        out["name"] = names
    return out


def to_json(spec: Spec, view: RequestView | None = None) -> str:
    return json.dumps(constraints(spec, view), indent=1)


if __name__ == "__main__":
    print(to_json(parse_spec(" ".join(sys.argv[1:]))))
