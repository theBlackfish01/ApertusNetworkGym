"""The instruction format: answer lines, validation, grammar, and the engine against ``intents.py``."""

import json
import random
from pathlib import Path

import pytest

from grammar import DONE, START, Dfa, TokenAutomaton, alt, lit, opt, seq
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
from spec import (
    EMPTY,
    Spec,
    admissible,
    answer_grammar,
    choose,
    format_spec,
    from_intent,
    load_topology,
    mention_order,
    parse_spec,
    respects,
    validate,
)
from view import RequestView

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


def test_answer_lines_round_trip():
    for spec in (
        EMPTY,
        Spec(avoid=(("Hamburg", "Berlin"),)),
        Spec(prefer=("load", "hops")),
        Spec(avoid=(("Paris", "Lyon"), ("Zurich", "Milan")), prefer=("slots",)),
        Spec(status="unsupported"),
    ):
        assert parse_spec(format_spec(spec)) == spec
    assert format_spec(EMPTY) == "avoid=none; prefer=none"
    assert format_spec(Spec(avoid=(("Hamburg", "Berlin"),), prefer=("hops", "load"))) == (
        "avoid=Hamburg-Berlin; prefer=hops,load"
    )
    for text in ("", "reject", "avoid=Hamburg; prefer=none", "avoid=none; prefer=speed", "avoid=none"):
        assert parse_spec(text).status == "malformed"


def test_meaning_ignores_link_direction_but_not_preference_order():
    a = Spec(avoid=(("Hamburg", "Berlin"),), prefer=("hops", "load"))
    assert a.meaning() == Spec(avoid=(("Berlin", "Hamburg"),), prefer=("hops", "load")).meaning()
    assert a.meaning() != Spec(avoid=(("Berlin", "Hamburg"),), prefer=("load", "hops")).meaning()
    assert Spec(status="unsupported").meaning() != Spec(status="unresolved").meaning()


def test_validate_flags_what_cannot_be_applied():
    topology = load_topology("nobel-eu")
    assert len(topology.nodes) == 28 and len(topology.links) == 41
    ok = Spec(avoid=(("Hamburg", "Berlin"), ("Berlin", "Hamburg")), prefer=("hops", "hops", "load"))
    assert validate(ok, topology) == Spec(avoid=(("Hamburg", "Berlin"),), prefer=("hops", "load"))
    assert validate(Spec(avoid=(("Zurich", "unknown"),)), topology).status == "unresolved"
    assert validate(Spec(avoid=(("Dublin", "Athens"),)), topology).status == "unresolved"  # not adjacent
    assert validate(Spec(status="unsupported"), topology).status == "unsupported"


def test_grammar_accepts_exactly_the_answer_lines():
    topology = load_topology("nobel-eu")
    dfa = answer_grammar(topology)
    good = [
        "unsupported",
        "avoid=none; prefer=none",
        "avoid=Hamburg-Berlin; prefer=none",
        "avoid=Zurich-unknown; prefer=hops",
        "avoid=Paris-Lyon,Zurich-Milan; prefer=load,hops,slots",
    ]
    bad = [
        "avoid=none; prefer=",
        "avoid=Hamburg; prefer=none",
        "avoid=Geneva-Zurich; prefer=none",  # not a node: must be written as unknown
        "avoid=Paris-Lyon,Zurich-Milan,Rome-Milan; prefer=none",  # more links than the format carries
        "avoid=none; prefer=hops,load,slots,hops",
        "avoid=none;prefer=none",
        "unsupported ",
    ]
    assert all(dfa.accepts(text) for text in good)
    assert not any(dfa.accepts(text) for text in bad)
    assert all(parse_spec(text).status != "malformed" for text in good)


def test_combinators():
    dfa = Dfa(seq(lit("a"), opt(lit("b")), alt(lit("c"), lit("cd"))))
    assert [dfa.accepts(t) for t in ("ac", "abc", "acd", "abcd", "a", "abd", "")] == [True] * 4 + [False] * 3


def test_token_automaton_follows_the_grammar():
    dfa = answer_grammar(load_topology("nobel-eu"))
    # single characters, a few multi-character tokens (one crossing a field boundary), and noise
    vocabulary = sorted(dfa.alphabet) + ["avoid=", "; prefer=", "Ham", "burg-", "none", "hops", "xx", "="]
    eos = len(vocabulary)
    automaton = TokenAutomaton(dfa, [*vocabulary, "<eos>"], [eos])
    token = {text: index for index, text in enumerate(vocabulary)}
    state = START
    for piece in ("avoid=", "Ham", "burg-", "B", "e", "r", "l", "i", "n", "; prefer=", "hops"):
        assert eos not in automaton.next[state]
        assert token["xx"] not in automaton.next[state]
        state = automaton.next[state][token[piece]]
    assert automaton.next[state][eos] == DONE
    assert token["none"] not in automaton.next[state]  # "hopsnone" is not an answer
    assert token["avoid="] in automaton.allowed(START) and token["none"] not in automaton.allowed(START)


def test_two_preferences_under_both_rules(view):
    # path 0 has the fewest hops, path 1 the most free slots: the two preferences conflict
    assert admissible(view, Spec(prefer=("hops", "load")), "intersection") == ()
    assert admissible(view, Spec(prefer=("hops", "load")), "ordered") == (0,)
    assert admissible(view, Spec(prefer=("load", "hops")), "ordered") == (1,)
    assert choose(view, Spec(prefer=("hops", "load")), "intersection") is None
    assert choose(view, Spec(prefer=("hops", "load")), "ordered") == (0, 88)
    assert respects(view, Spec(prefer=("hops", "load")), (0, 88), "ordered")
    assert not respects(view, Spec(prefer=("hops", "load")), None, "ordered")
    # a constraint still rejects: every feasible path uses one of the two links
    blocked = Spec(avoid=(("Berlin", "Munich"), ("Vienna", "Prague")))
    assert admissible(view, blocked, "ordered") == () and choose(view, blocked, "ordered") is None
    # ties on the first preference are broken by the second: paths 1 and 2 have three hops
    assert admissible(view, Spec(avoid=(("Berlin", "Munich"),), prefer=("hops", "load")), "ordered") == (1,)
    assert admissible(view, Spec(avoid=(("Berlin", "Munich"),), prefer=("hops", "slots")), "ordered") == (2,)


def test_mention_order_follows_the_text(view):
    rng = random.Random(3)
    orders = set()
    for _ in range(200):
        intent = sample_intent(view, rng.choice(TRAIN_PAIRS + HELDOUT_PAIRS), rng)
        order = mention_order(intent)
        assert sorted(order) == sorted(intent.ids)
        first, second = (intent.text.index(s) for s in _sentences(intent, order))
        assert first < second
        orders.add(order == intent.ids)
    assert orders == {True, False}  # both orders occur
    spec = from_intent(Intent(ids=("I2", "I3"), text="x"), order=("I3", "I2"))
    assert spec.prefer == ("load", "hops")


def _sentences(intent, order):
    from intents import LINK_FORMS, PARAPHRASES

    for intent_id in order:
        sentence = PARAPHRASES[intent_id][intent.paraphrases[intent.ids.index(intent_id)]]
        if intent_id == "I1":
            phrase = LINK_FORMS[intent.link_form].format(a=intent.link[0], b=intent.link[1])
            sentence = sentence.format(link=phrase, Link=phrase[0].upper() + phrase[1:])
        yield sentence


def test_engine_equals_the_intent_rules(view):
    """With the intersection rule the spec engine is the oracle of ``intents.py``."""
    rng = random.Random(5)
    kinds = [(i,) for i in SINGLES] + list(TRAIN_PAIRS + HELDOUT_PAIRS) + [()]
    for _ in range(300):
        intent = sample_intent(view, rng.choice(kinds), rng)
        spec = from_intent(intent)
        assert admissible(view, spec, "intersection") == admissible_paths(view, intent)
        assert choose(view, spec, "intersection") == intent_teacher(view, intent)


@pytest.mark.skipif(not SAMPLE.exists(), reason="dataset sample not present")
def test_engine_equals_the_intent_rules_on_dataset_records():
    checked = 0
    for path in sorted(SAMPLE.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            meta = json.loads(line)["meta"]
            view, intent = RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"])
            spec = from_intent(intent)
            assert admissible(view, spec, "intersection") == admissible_paths(view, intent)
            teacher = intent_teacher(view, intent)
            assert choose(view, spec, "intersection") == teacher
            assert respects(view, spec, teacher, "intersection") == is_admissible(view, intent, teacher)
            checked += 1
    assert checked >= 100
