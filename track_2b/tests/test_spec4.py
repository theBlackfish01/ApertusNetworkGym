"""The fourth version of the format: scope and lifetime of a standing policy."""

from grammar import gbnf
from spec import (
    EMPTY,
    Spec,
    answer_expression,
    answer_grammar,
    describe,
    format_spec,
    load_topology,
    parse_spec,
    validate,
)

TOPOLOGY = load_topology("nobel-eu")
LINE4 = "avoid=Berlin-Prague; via=Lyon; hops=4; km=any; path=any; prefer=km,load; scope=rate:400; until=12h; rest=none"
LINE3 = "avoid=Berlin-Prague; via=Lyon; hops=4; km=any; path=any; prefer=km,load; rest=none"


def test_scope_and_until_round_trip_and_project_to_the_third_version():
    spec = parse_spec(LINE4)
    assert (spec.scope, spec.until) == ("rate:400", 12) and spec.applies
    assert format_spec(spec, 4) == LINE4 and format_spec(spec, 3) == LINE3
    assert spec.routing() == parse_spec(LINE3) and spec.meaning() != parse_spec(LINE3).meaning()
    assert Spec.from_json(spec.to_json()) == spec
    assert parse_spec(LINE3).scope is None and format_spec(parse_spec(LINE3), 4).endswith(
        "scope=any; until=open; rest=none"
    )
    assert (
        format_spec(EMPTY, 4)
        == "avoid=none; via=none; hops=any; km=any; path=any; prefer=none; scope=any; until=open; rest=none"
    )


def test_scope_values_are_checked():
    assert parse_spec(LINE4.replace("rate:400", "rate:50")).status == "malformed"
    assert parse_spec(LINE4.replace("12h", "0h")).status == "malformed"
    assert validate(parse_spec(LINE4.replace("rate:400", "from:Zurich")), TOPOLOGY).applies
    assert validate(parse_spec(LINE4.replace("rate:400", "to:Lisbon")), TOPOLOGY).status == "unresolved"
    assert "only for 400 Gb/s requests" in describe(parse_spec(LINE4)) and "next 12 hours" in describe(
        parse_spec(LINE4)
    )


def test_grammar_accepts_the_fourth_version_only_when_asked():
    accepts4 = answer_grammar(TOPOLOGY, 4).accepts
    assert (
        accepts4(LINE4)
        and accepts4(LINE3.replace("; rest=", "; scope=from:Zurich; until=open; rest="))
        and not accepts4(LINE3)
    )
    assert not accepts4(LINE4.replace("rate:400", "rate:50")) and not accepts4(LINE4.replace("12h", "120h"))
    assert answer_grammar(TOPOLOGY, 3).accepts(LINE3) and not answer_grammar(TOPOLOGY, 3).accepts(LINE4)
    assert "scope=" in gbnf(answer_expression(TOPOLOGY, 4)) and "scope=" not in gbnf(
        answer_expression(TOPOLOGY, 3)
    )
