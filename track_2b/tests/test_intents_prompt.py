"""Intent rules, teacher and prompt/answer format on a hand-built request (no simulator)."""

import random
import re

from intents import (
    LINK_FORMS,
    N_TRAIN_PARAPHRASES,
    NO_INTENT,
    PARAPHRASES,
    Intent,
    admissible_paths,
    candidate_links,
    is_admissible,
    sample_intent,
    teacher_choice,
)
from prompt import ANSWER_REGEX, format_choice, parse_answer, render_prompt
from view import PathView, RequestView


def intent(*ids, link=None):
    return Intent(ids=ids, text="x", link=link)


def test_no_intent_teacher_is_lowest_start_slot(view):
    assert admissible_paths(view, NO_INTENT) == (0, 1, 2)
    assert teacher_choice(view, NO_INTENT) == (1, 12)


def test_single_intents(view):
    assert admissible_paths(view, intent("I1", link=("Vienna", "Hamburg"))) == (0, 2)  # either direction
    assert teacher_choice(view, intent("I1", link=("Vienna", "Hamburg"))) == (2, 40)
    assert teacher_choice(view, intent("I2")) == (0, 88)  # fewest hops
    assert teacher_choice(view, intent("I3")) == (1, 12)  # most free slots
    assert teacher_choice(view, intent("I4")) == (2, 40)  # fewest slots needed


def test_pairs_intersect_and_empty_means_reject(view):
    # fewest hops is path 0, which contains Berlin-Munich: nothing satisfies both
    both = intent("I1", "I2", link=("Berlin", "Munich"))
    assert admissible_paths(view, both) == ()
    assert teacher_choice(view, both) is None
    assert is_admissible(view, both, None)
    assert not is_admissible(view, both, (1, 12))
    # avoiding Berlin-Warsaw leaves path 0 as the fewest-hops path
    assert teacher_choice(view, intent("I1", "I2", link=("Berlin", "Warsaw"))) == (0, 88)


def test_admissibility_of_decisions(view):
    assert not is_admissible(view, NO_INTENT, None)  # rejecting with a feasible path is a violation
    assert is_admissible(view, intent("I2"), (0, 230))  # any start on an admissible path
    assert not is_admissible(view, intent("I2"), (1, 12))
    assert is_admissible(view, intent("I4"), (2, 43)) and not is_admissible(view, intent("I4"), (2, 60))


def test_ties_go_to_the_shorter_path(view):
    # paths 1 and 2 both have 3 hops once path 0 is excluded
    tied = intent("I1", "I2", link=("Munich", "Prague"))
    assert admissible_paths(view, tied) == ()  # intersection: path 0 is the only fewest-hops path
    equal_free = RequestView(**{**view.__dict__, "paths": tuple(
        PathView(**{**p.__dict__, "free_slots": 100}) for p in view.paths
    )})  # fmt: skip
    assert admissible_paths(equal_free, intent("I3")) == (0, 1, 2)
    assert teacher_choice(equal_free, intent("I3")) == (0, 88)  # shortest km among the tied paths


def test_sampled_intents_use_the_right_paraphrase_pool_and_real_links(view):
    rng = random.Random(3)
    links = candidate_links(view)
    for heldout in (False, True):
        for _ in range(200):
            sampled = sample_intent(view, ("I1", "I3"), rng, heldout=heldout)
            assert all((i >= N_TRAIN_PARAPHRASES) == heldout for i in sampled.paraphrases)
            assert tuple(sorted(sampled.link)) in links
            assert (
                "{" not in sampled.text
                and sampled.link[0] in sampled.text
                and sampled.link[1] in sampled.text
            )
    assert sample_intent(view, (), rng) is NO_INTENT


def test_paraphrases_are_ten_distinct_per_intent_and_fill_every_link_form():
    for intent_id, sentences in PARAPHRASES.items():
        assert len(sentences) == 10 and len(set(sentences)) == 10
        for sentence in sentences:
            assert ("{link}" in sentence or "{Link}" in sentence) == (intent_id == "I1")
    assert len({form.format(a="A", b="B") for form in LINK_FORMS}) == len(LINK_FORMS)


def test_prompt_lists_what_the_rules_need(view):
    text = render_prompt(
        view, Intent(("I1",), "Avoid the Berlin-Munich link for this request.", ("Berlin", "Munich"))
    )
    lines = text.splitlines()
    assert lines[0] == "Request: Berlin -> Prague, 100 Gb/s."
    assert lines[1] == "Intent: Avoid the Berlin-Munich link for this request."
    assert lines[2] == "Network: 320 slots per link, free ratio 0.61."
    assert lines[4] == "0: 2 hops, 900 km, QPSK, 9 slots, 60 free, blocks [88-41] [220-100]"
    assert lines[7] == "3: 4 hops, 2100 km, none"
    one = RequestView(**{**view.__dict__, "paths": (PathView(0, ("A", "B"), 80, 9, "64QAM", 1, ((5, 1),)),)})
    assert (
        render_prompt(one, NO_INTENT).splitlines()[4]
        == "0: 1 hop, 80 km, 64QAM, 1 slot, 9 free, blocks [5-1]"
    )
    assert lines[8].startswith(
        "Route per path: 0: Berlin-Munich-Prague ; 1: Berlin-Hamburg-Vienna-Prague ; 2:"
    )
    assert lines[-1] == "Answer format: path=<0-4> slot=<n>  or  reject"
    assert render_prompt(view, NO_INTENT).splitlines()[1] == "Intent: none"


def test_answers_round_trip_and_match_the_decode_regex():
    for choice in [(0, 0), (4, 319), None]:
        answer = format_choice(choice)
        assert re.fullmatch(ANSWER_REGEX, answer)
        assert parse_answer(f" {answer}\n") == (True, choice)
    for bad in ["path=5 slot=1", "path=1", "path=1 slot=1 because it is free", "Reject", ""]:
        assert parse_answer(bad) == (False, None)


def test_view_json_round_trip(view):
    assert RequestView.from_json(view.to_json()) == view
