"""The answer automaton accepts exactly the answer regex, also when lifted to tokens."""

import itertools
import random
import re

import pytest

from decoding import ACCEPTING, DONE, START, TokenAutomaton, walk
from prompt import ANSWER_REGEX, format_choice, parse_answer


def accepts(text: str) -> bool:
    return walk(START, text) in ACCEPTING


def test_automaton_agrees_with_the_regex():
    valid = ["reject", "path=0 slot=0", "path=4 slot=319", "path=2 slot=07", "path=3 slot=999"]
    invalid = ["", "path=5 slot=1", "path=1 slot=", "path=1 slot=1234", "path=1  slot=1", "reject ", "rejected",
               "path=1", "Path=1 slot=1", "path=1 slot=1\n", "path=1 slot=x"]  # fmt: skip
    for text in valid:
        assert accepts(text) and re.fullmatch(ANSWER_REGEX, text)
    for text in invalid:
        assert not accepts(text) and not re.fullmatch(ANSWER_REGEX, text)
    rng = random.Random(0)
    alphabet = "path=slot rejc0123456789"
    for _ in range(3000):  # random strings near the language
        base = format_choice(rng.choice([None, (rng.randrange(5), rng.randrange(1000))]))
        chars = list(base)
        for _ in range(rng.randrange(3)):
            chars[rng.randrange(len(chars))] = rng.choice(alphabet)
        text = "".join(chars)
        assert accepts(text) == bool(re.fullmatch(ANSWER_REGEX, text)), text


def test_token_automaton_only_ever_produces_valid_answers():
    # A toy vocabulary with multi-character tokens, tokens that straddle fields, and junk.
    vocab = ["<eos>", "path", "=", " slot", "re", "ject", "rej", "ect", "pa", "th=", "t=", " s", "lo", " ", "x",
             "path=1", "12", "007", "5", "th", *"0123456789", *"pathslotrejc"]  # fmt: skip
    automaton = TokenAutomaton(vocab, eos_ids=[0])
    assert 14 not in automaton.next[START]  # "x" can never start an answer
    assert vocab.index("5") not in automaton.next[walk(START, "path=")]  # path index is 0-4
    rng = random.Random(1)
    seen = set()
    for _ in range(2000):  # random walks through the allowed tokens always end in a valid answer
        state, text = START, ""
        for _ in range(40):
            token = rng.choice(automaton.allowed(state))
            state = automaton.next[state][token]
            if state == DONE:
                break
            text += vocab[token]
        assert state == DONE and re.fullmatch(ANSWER_REGEX, text), text
        assert parse_answer(text)[0]
        seen.add(text.split(" ")[0])
    assert {"reject", *(f"path={i}" for i in range(5))} <= seen


def test_end_token_only_after_a_complete_answer():
    vocab = ["<eos>", *"path= slot0123456789rejc"]
    automaton = TokenAutomaton(vocab, eos_ids=[0])
    for prefix, complete in [
        ("path=1 slot=", False),
        ("path=1 slot=3", True),
        ("rejec", False),
        ("reject", True),
    ]:
        state = START
        for char in prefix:
            state = automaton.next[state][vocab.index(char)]
        assert (0 in automaton.next[state]) == complete


def test_a_vocabulary_that_cannot_spell_answers_is_refused():
    with pytest.raises(ValueError, match="cannot spell"):
        TokenAutomaton(["<eos>", *"path=slot 0123456789"], eos_ids=[0])  # no way to finish "reject"


def test_every_valid_answer_is_reachable_with_single_characters():
    vocab = ["<eos>", *sorted(set("path= slot0123456789rejc"))]
    automaton = TokenAutomaton(vocab, eos_ids=[0])
    for path, slot in itertools.product(range(5), [0, 7, 42, 319]):
        state = START
        for char in f"path={path} slot={slot}":
            state = automaton.next[state][vocab.index(char)]
        assert automaton.next[state][0] == DONE
