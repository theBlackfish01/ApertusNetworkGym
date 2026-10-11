"""The translator arm without a model: prompts, the keyword baseline, the policy, the corpora."""

import random

from corpora import LANGUAGES, TRAIN_OUTSIDE, TRAIN_UNSUPPORTED, fill, misspell, reword
from intents import NO_INTENT, SINGLES, TRAIN_PAIRS, Intent, is_admissible, sample_intent, teacher_choice
from policies import Request, make_policy
from spec import answer_grammar, from_intent, load_topology, mention_order, parse_spec
from translate import SHOTS, KeywordTranslator, messages


def test_prompt_lists_the_nodes_and_the_examples_are_valid_answers():
    for name in ("nobel-eu", "germany50"):
        topology = load_topology(name)
        zero, few = messages("Avoid X-Y.", topology), messages("Avoid X-Y.", topology, few=True)
        assert all(node in zero[0]["content"] for node in topology.nodes)
        assert [m["role"] for m in zero] == ["system", "user"] and zero[-1] == few[-1]
        assert len(few) == 2 + 2 * len(SHOTS)
        answers = [m["content"] for m in few if m["role"] == "assistant"]
        dfa = answer_grammar(topology)
        assert all(dfa.accepts(answer) for answer in answers)
        assert {parse_spec(answer).status for answer in answers} == {"ok", "unsupported"}


def test_keyword_baseline_reads_the_training_wording(view):
    translator = KeywordTranslator(load_topology("nobel-eu"))
    rng = random.Random(11)
    kinds = [(i,) for i in SINGLES] + list(TRAIN_PAIRS)
    for _ in range(300):
        intent = sample_intent(view, rng.choice(kinds), rng)
        # the hand-built request has links that are not in nobel-eu, so compare before validation
        ((line, _),) = translator.lines([intent.text])
        assert parse_spec(line).meaning() == from_intent(intent).meaning(), intent.text


def test_keyword_baseline_flags_what_it_cannot_resolve():
    translator = KeywordTranslator(load_topology("nobel-eu"))
    statuses = [s.status for s in translator.translate([
        "Avoid the Zurich-Geneva link for this request.",  # Geneva is not a node
        "Route around the link between Dublin and Athens.",  # not adjacent
        "Use 16QAM for this connection.",
    ])]  # fmt: skip
    assert statuses == ["unresolved", "unresolved", "unsupported"]


def test_translator_policy_applies_or_flags(view):
    policy = make_policy("translate_keyword")
    text = (
        "Avoid the link between Hamburg and Berlin for this request."  # a link of nobel-eu and of the request
    )
    avoid = Intent(ids=("I1",), text=text, link=("Hamburg", "Berlin"))
    unknown = Intent(text="Avoid the Berlin-Geneva link for this request.")  # cannot be applied
    requests = [Request(view, avoid), Request(view, unknown), Request(view, NO_INTENT)]
    applied, flagged, plain = policy.decide(requests)
    assert applied.raw == "avoid=Hamburg-Berlin; prefer=none"
    assert applied.choice == teacher_choice(view, avoid) == (2, 40) and is_admissible(
        view, avoid, applied.choice
    )
    assert flagged.raw == "unresolved" and flagged.choice == plain.choice == teacher_choice(view, NO_INTENT)
    ordered = make_policy("translate_keyword_ordered")
    both = Intent(text="Minimise the hop count for this service. Use the path with the most free spectrum.")
    assert policy.decide([Request(view, both)])[0].choice is None  # intersection: the two conflict here
    assert ordered.decide([Request(view, both)])[0].choice == (0, 88)  # fewest hops decides


def test_other_wordings_keep_the_order_and_the_link(view):
    rng = random.Random(2)
    for lang, wording in LANGUAGES.items():
        assert all("{a}" in s and "{b}" in s for s in wording["I1"]), lang
        assert not any("{" in s for key in ("I2", "I3", "I4") for s in wording[key]), lang
        for _ in range(50):
            intent = sample_intent(view, rng.choice(TRAIN_PAIRS), rng)
            text = reword(intent, wording, {}, wording["names"], rng)
            first, second = (rng_free_position(text, wording[i]) for i in mention_order(intent))
            assert 0 <= first < second, (lang, text)
            assert "{" not in text
    assert fill("skip {a}/{b}", "Rome", "Milan") == "skip Rome/Milan"
    assert not set(TRAIN_OUTSIDE) & set(load_topology("nobel-eu").nodes)
    assert all(t.format(a="Rome", n=3, mod="QPSK") for t in TRAIN_UNSUPPORTED)


def rng_free_position(text: str, templates: tuple[str, ...]) -> int:
    """Where a sentence of ``templates`` starts in ``text`` (its part before any placeholder)."""
    return max(text.find(t.split("{")[0][:12]) for t in templates if t.split("{")[0][:12])


def test_misspelling_changes_one_city_name():
    intent = Intent(ids=("I1",), text="x", link=("Hamburg", "Berlin"))
    noisy = misspell("Stay off the Hamburg-Berlin span.", intent, random.Random(4))
    assert noisy == noisy.lower() and not noisy.endswith(".")
    assert ("hamburg" in noisy) != ("berlin" in noisy)  # exactly one of the two is misspelt
