"""Standing policies: scope, lifetime, combination, conflicts and the report."""

from spec import Spec, load_topology, parse_spec
from standing import PolicyTable, combine, covers, overlap
from view import PathView, RequestView

TOPOLOGY = load_topology("nobel-eu")


def line(**slots: str) -> Spec:
    empty = {"avoid": "none", "via": "none", "hops": "any", "km": "any", "path": "any", "prefer": "none",
             "scope": "any", "until": "open", "rest": "none"}  # fmt: skip
    return parse_spec("; ".join(f"{k}={v}" for k, v in (empty | slots).items()))


def view(source: str, destination: str, rate: int) -> RequestView:
    path = PathView(0, (source, "Frankfurt", destination), 900, 100, "QPSK", 4, ((0, 10),))
    return RequestView(source, destination, rate, 320, 0.5, (path,))


def test_scope_and_overlap():
    assert covers(None, view("Zurich", "Milan", 100)) and covers("rate:100", view("Zurich", "Milan", 100))
    assert not covers("rate:400", view("Zurich", "Milan", 100))
    assert covers("from:Zurich", view("Zurich", "Milan", 100)) and not covers(
        "to:Zurich", view("Zurich", "Milan", 100)
    )
    assert (
        overlap(None, "rate:400")
        and overlap("rate:400", "from:Zurich")
        and not overlap("rate:400", "rate:100")
    )
    assert overlap("from:Zurich", "to:Milan") and not overlap("from:Zurich", "to:Zurich")


def test_lifetime_combination_and_report():
    table = PolicyTable(TOPOLOGY)
    first, conflicts = table.add(
        "avoid Berlin-Prague for 6 hours", line(avoid="Berlin-Prague", until="6h"), now=0.0
    )
    assert not conflicts and first.expires == 6.0
    second, conflicts = table.add("400G least loaded", line(prefer="load", scope="rate:400"), now=1.0)
    assert not conflicts
    v = view("Zurich", "Milan", 400)
    effective = table.effective(v, now=2.0)
    assert (
        effective.avoid == (("Berlin", "Prague"),)
        and effective.prefer == ("load",)
        and effective.scope is None
    )
    assert table.effective(view("Zurich", "Milan", 100), now=2.0).prefer == ()
    assert table.expire(now=7.0) == [first] and table.active(now=7.0) == [second]
    table.record(v, now=7.0, choice=(0, 5), without=None, respects=True)
    row = next(r for r in table.report(now=7.0) if r["id"] == second.id)
    assert (row["in_scope"], row["changed"], row["rejected"], row["violations"], row["active"]) == (
        1,
        1,
        0,
        0,
        True,
    )
    assert next(r for r in table.report(now=7.0) if r["id"] == first.id)["active"] is False


def test_conflicts_are_named_not_resolved():
    table = PolicyTable(TOPOLOGY)
    table.add("via Frankfurt", line(via="Frankfurt"), now=0.0)
    _, found = table.add("avoid Frankfurt", line(avoid="Frankfurt"), now=0.0)
    assert any(c["kind"] == "contradiction" and "Frankfurt" in c["why"] for c in found)
    _, found = table.add("shortest", line(prefer="km", scope="rate:400"), now=0.0)
    assert not found
    _, found = table.add("least loaded for 400G", line(prefer="load", scope="rate:400"), now=0.0)
    assert any(c["kind"] == "override" for c in found)
    _, found = table.add("fewest hops for 100G", line(prefer="hops", scope="rate:100"), now=0.0)
    assert not any(c["kind"] == "override" for c in found)  # a different bit rate: no overlap
    # a scope that pins a node which the avoided links cut off
    cut = PolicyTable(TOPOLOGY)
    cut.add("no links of Dublin", line(avoid="Dublin-Glasgow,Dublin-London"), now=0.0)
    _, found = cut.add("from Dublin", line(prefer="hops", scope="from:Dublin"), now=0.0)
    assert any("cut off" in c["why"] for c in found)


def test_combine_keeps_the_newest_first():
    newest, older = line(prefer="km", hops="3"), line(prefer="load,hops", hops="5", km="1500")
    combined = combine([newest, older])
    assert combined.prefer == ("km", "load", "hops") and combined.max_hops == 3 and combined.max_km == 1500
