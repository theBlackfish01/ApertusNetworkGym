"""The policy language as a TAPI 2.1.3 constraint."""

from spec import Spec, parse_spec
from tapi import OBJECTIVE, constraints, link_uuid, node_uuid
from view import PathView, RequestView

LINE = "avoid=Berlin-Prague,Paris; via=Lyon; hops=4; km=1500; path=any; prefer=km,load; rest=none"


def test_every_slot_lands_in_the_standard_field():
    out = constraints(parse_spec(LINE))
    topology, routing = out["topology-constraint"], out["routing-constraint"]
    assert topology["exclude-link"] == [link_uuid("Prague", "Berlin")]  # direction does not matter
    assert topology["exclude-node"] == [node_uuid("Paris")]
    assert topology["include-node"] == [node_uuid("Lyon")]
    assert routing["max-allowed-hops"] == {"value": 4}
    assert routing["max-allowed-cost"] == {"value": 1500}
    assert routing["route-objective-function"] == OBJECTIVE["km"]
    by_name = {(n["value-name"], n["value"]) for n in out["name"]}
    assert ("exclude-link", "Berlin-Prague") in by_name
    assert ("apertus-lightpath:preference-order", "km,load") in by_name
    assert link_uuid("Berlin", "Prague") != link_uuid("Berlin", "Munich")


def test_candidate_by_number_becomes_its_links():
    path = PathView(2, ("Zurich", "Milan", "Rome"), 900, 100, "QPSK", 4, ((0, 10),))
    view = RequestView("Zurich", "Rome", 100, 320, 0.5, (path, path, path))
    out = constraints(Spec(path=2), view)
    assert out["topology-constraint"]["include-link"] == [
        link_uuid("Zurich", "Milan"),
        link_uuid("Milan", "Rome"),
    ]
    assert "routing-constraint" not in out
    assert constraints(Spec(path=2))["name"] == [{"value-name": "apertus-lightpath:candidate", "value": "2"}]


def test_slots_and_refusals():
    out = constraints(Spec(prefer=("slots", "hops")))
    assert "route-objective-function" not in out.get("routing-constraint", {})  # no TAPI objective for slots
    assert out["name"] == [{"value-name": "apertus-lightpath:preference-order", "value": "slots,hops"}]
    for status in ("unsupported", "no_instruction", "unresolved", "malformed"):
        assert constraints(Spec(status=status)) is None
