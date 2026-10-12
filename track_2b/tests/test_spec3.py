"""The third version of the instruction format: the line of slots, its grammar and the engine."""

import random

from corpora3 import (
    ATOMS,
    HELDOUT,
    HELDOUT_PAIRS,
    HELDOUT_TRIPLES,
    TRAIN_PAIRS,
    TRAINED,
    build_training,
    signature,
)
from grammar import gbnf
from spec import (
    Spec,
    admissible,
    answer_expression,
    answer_grammar,
    choose,
    format_spec,
    load_topology,
    meets,
    parse_spec,
    respects,
    validate,
)

TOPOLOGY = load_topology("nobel-eu")
FULL = "avoid=Berlin-Prague,Paris; via=Lyon; hops=4; km=1500; path=any; prefer=km,load; rest=none"


def test_line_of_slots_round_trips():
    spec = parse_spec(FULL)
    assert spec == Spec((("Berlin", "Prague"),), ("km", "load"), "ok", ("Paris",), ("Lyon",), 4, 1500)
    assert format_spec(spec, 3) == FULL
    assert Spec.from_json(spec.to_json()) == spec
    assert validate(spec, TOPOLOGY) == spec
    assert parse_spec(FULL.replace("path=any", "path=5")).status == "malformed"
    assert parse_spec(FULL.replace("prefer=km,load", "prefer=cost")).status == "malformed"


def test_first_format_is_unchanged():
    old = Spec((("Berlin", "Prague"),), ("hops",))
    assert format_spec(old) == "avoid=Berlin-Prague; prefer=hops"
    assert old.to_json() == {"status": "ok", "avoid": [["Berlin", "Prague"]], "prefer": ["hops"]}
    assert parse_spec("avoid=Berlin-Prague; prefer=hops") == old


def test_rest_and_refusals():
    empty = "avoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest="
    assert parse_spec(empty + "none") == Spec()
    assert parse_spec(empty + "more").status == "unsupported"  # nothing the slots carry
    partial = parse_spec(FULL.replace("rest=none", "rest=more"))
    assert partial.applies and partial.rest and partial.constrains
    assert partial.meaning() != parse_spec(FULL).meaning()
    assert not parse_spec(empty.replace("prefer=none", "prefer=hops") + "more").constrains


def test_places_outside_the_network_are_unresolved():
    for line in (
        FULL.replace("Paris", "unknown"),
        FULL.replace("Lyon", "unknown"),
        FULL.replace("Berlin-Prague", "Berlin-Madrid"),  # two nodes, no link between them
    ):
        assert validate(parse_spec(line), TOPOLOGY).status == "unresolved"


def test_grammar_and_gbnf_cover_the_training_lines():
    dfa = answer_grammar(TOPOLOGY, 3)
    data = build_training(TOPOLOGY, 1)
    lines = {record["completion"][0]["content"] for records in data.values() for record in records}
    assert len(lines) > 1000 and all(dfa.accepts(line) for line in lines)
    assert not dfa.accepts("avoid=none; prefer=hops")
    assert not dfa.accepts(FULL.replace("hops=4", "hops=0"))
    text = gbnf(answer_expression(TOPOLOGY, 3))
    assert text.startswith('root ::= "unsupported" | "no_instruction" | "avoid="') and '"Zurich"' in text


def test_training_combinations_exclude_the_held_out_ones():
    assert len(HELDOUT) == len(HELDOUT_PAIRS) + len(HELDOUT_TRIPLES) == 12
    assert not TRAINED & HELDOUT
    kinds = {r["meta"]["kind"].split(": ")[-1] for r in build_training(TOPOLOGY, 2)["train"]}
    assert not {tuple(kind.split("+")) for kind in kinds} & HELDOUT
    assert {signature(pair) for pair in TRAIN_PAIRS} <= {tuple(kind.split("+")) for kind in kinds}
    assert set(ATOMS) - {"fewest_hops", "shortest_km", "least_loaded", "fewest_slots"} <= kinds


def test_engine_applies_every_constraint(view):
    feasible = [p for p in view.paths if p.feasible]
    assert len(feasible) >= 3
    rng = random.Random(3)
    for _ in range(200):
        path = rng.choice(feasible)
        inner = path.nodes[1:-1]
        spec = Spec(
            nodes=(rng.choice(inner),) if inner and rng.random() < 0.3 else (),
            via=(rng.choice(inner),) if inner and rng.random() < 0.3 else (),
            max_hops=rng.choice((None, path.hops, path.hops - 1)),
            max_km=rng.choice((None, path.km, path.km - 1)),
            path=rng.choice((None, None, path.index)),
            prefer=tuple(rng.sample(("hops", "km", "load", "slots"), rng.randrange(3))),
        )
        allowed = admissible(view, spec)
        assert all(meets(view.paths[i], spec) for i in allowed)
        constrained = [p for p in feasible if meets(p, spec)]
        assert bool(allowed) == bool(constrained)
        choice = choose(view, spec)
        assert respects(view, spec, choice)
        if spec.prefer and constrained:
            first = spec.prefer[0]
            key = {"hops": lambda p: p.hops, "km": lambda p: p.km, "load": lambda p: -p.free_slots,
                   "slots": lambda p: p.slots_needed}[first]  # fmt: skip
            assert key(view.paths[choice[0]]) == min(key(p) for p in constrained)
    assert choose(view, Spec(nodes=(view.paths[0].nodes[1],), via=(view.paths[0].nodes[1],))) is None
