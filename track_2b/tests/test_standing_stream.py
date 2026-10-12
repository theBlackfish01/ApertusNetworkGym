"""The stream of standing policies: arrivals, withdrawals, the truth, and the table-keeping policies."""

from policies import Request
from spec import parse_spec
from standing_stream import HOUR, MAX_ACTIVE, Stream, Truthful, make_standing_policy, standing_material
from view import PathView, RequestView


def view(source: str = "Zurich", destination: str = "Milan", rate: int = 100) -> RequestView:
    paths = (
        PathView(0, (source, destination), 300, 100, "QPSK", 4, ((0, 10),)),
        PathView(1, (source, "Frankfurt", destination), 900, 200, "QPSK", 4, ((0, 10),)),
    )
    return RequestView(source, destination, rate, 320, 0.5, paths)


def test_standing_material_filters_per_request_sentences():
    assert standing_material(
        parse_spec("avoid=Berlin-Prague; via=none; hops=any; km=any; path=any; prefer=none; rest=none")
    )
    assert not standing_material(
        parse_spec("avoid=none; via=none; hops=any; km=any; path=2; prefer=none; rest=none")
    )
    assert not standing_material(
        parse_spec("avoid=none; via=Lyon; hops=any; km=any; path=any; prefer=none; rest=none")
    )
    assert standing_material(
        parse_spec(
            "avoid=none; via=Lyon; hops=any; km=any; path=any; prefer=none; scope=from:Paris; until=open; rest=none"
        )
    )
    assert not standing_material(
        parse_spec("avoid=none; via=none; hops=1; km=any; path=any; prefer=none; rest=none")
    )


def test_stream_schedules_arrivals_withdrawals_and_the_truth():
    stream = Stream({"load": 390, "seed": 1})
    assert stream.pool and stream.short
    first = stream.intent(view(), 0.0)
    assert (
        len(first.arrivals) == 3
        and first.active == tuple(t for t, _ in first.arrivals)
        and not first.withdrawn
    )
    assert first.truth and first.episode == "390-1"
    quiet = stream.intent(view(), 0.5)
    assert not quiet.arrivals and quiet.active == first.active
    seen_withdrawal = False
    for hour in range(2, 40, 2):
        intent = stream.intent(view(), float(hour))
        assert len(intent.active) <= MAX_ACTIVE
        seen_withdrawal |= bool(intent.withdrawn)
    assert seen_withdrawal
    assert HOUR == 3600.0


def test_truthful_keepers_follow_the_truth_and_the_ablations_differ():
    stream = Stream({"load": 390, "seed": 2})
    oracle, noscope = Truthful("standing_oracle"), make_standing_policy("standing_noscope")
    differed = False
    for step in range(60):
        hour, v = step * 0.5, view(rate=(100, 400, 10)[step % 3])
        intent = stream.intent(v, hour)
        (decision,) = oracle.decide([Request(v, intent)])
        assert decision.raw == intent.truth  # the oracle applies exactly the true effective spec
        (ignoring,) = noscope.decide([Request(v, intent)])
        out_of_scope = any(p.spec.scope and not p.covers(v) for p in stream.table.active(hour))
        if out_of_scope and ignoring.raw != intent.truth:
            differed = True
    assert differed and noscope.describe()["dropped_policies"] == 0
