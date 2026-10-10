"""Regex-constrained decoding for the answer format, without a serving framework.

The answer language is ``path=[0-4] slot=\\d{1,3}`` or ``reject`` (``prompt.ANSWER_REGEX``).
:func:`step` is its character automaton; :class:`TokenAutomaton` lifts it to a tokenizer's
vocabulary, so that at every decoding step only tokens that keep the output a prefix of a valid
answer can be chosen, and the end token only once the answer is complete. This is what a
server's structured-output option does; having it here lets the same constraint run inside
plain ``transformers`` generation (``policies.LocalLLMPolicy``).

States are integers: 0 is the start, 1-15 count the characters consumed of the ``path=`` form,
16-21 those of ``reject``; ``DONE`` is reached by the end token from an accepting state.
"""

from __future__ import annotations

START, DONE = 0, -1
_PATH = "path=# slot=###"  # '#': a digit; the first one must be 0-4
_REJECT = "reject"
_REJECT_BASE = len(_PATH)  # state 16 = one character of "reject" consumed
ACCEPTING = frozenset({13, 14, 15, _REJECT_BASE + len(_REJECT)})
ALPHABET = frozenset(_PATH.replace("#", "") + _REJECT + "0123456789")
STATES = range(_REJECT_BASE + len(_REJECT) + 1)


def step(state: int, char: str) -> int | None:
    """Next state after ``char``, or ``None`` if it cannot follow."""
    if state == START:
        return 1 if char == "p" else _REJECT_BASE + 1 if char == "r" else None
    if state < len(_PATH):
        expected = _PATH[state]
        if expected == "#":
            return state + 1 if char in ("01234" if state == 5 else "0123456789") else None
        return state + 1 if char == expected else None
    if _REJECT_BASE < state < _REJECT_BASE + len(_REJECT):
        return state + 1 if char == _REJECT[state - _REJECT_BASE] else None
    return None


def walk(state: int, text: str) -> int | None:
    """State after consuming ``text`` from ``state``, or ``None`` if it leaves the language."""
    for char in text:
        state = step(state, char)
        if state is None:
            return None
    return state


class TokenAutomaton:
    """Allowed next tokens per state for one vocabulary.

    ``token_strings[i]`` is the text token ``i`` decodes to. ``eos_ids`` end the answer and are
    allowed exactly in accepting states.
    """

    def __init__(self, token_strings: list[str], eos_ids: list[int]) -> None:
        candidates = [
            (index, text)
            for index, text in enumerate(token_strings)
            if text and index not in eos_ids and ALPHABET.issuperset(text)
        ]
        self.next: dict[int, dict[int, int]] = {}
        for state in STATES:
            moves = {}
            for index, text in candidates:
                target = walk(state, text)
                if target is not None:
                    moves[index] = target
            if state in ACCEPTING:
                moves.update(dict.fromkeys(eos_ids, DONE))
            self.next[state] = moves
        stuck = [state for state in STATES if not self.next[state] and state not in ACCEPTING]
        if not self.next[START] or stuck:
            raise ValueError(f"the vocabulary cannot spell the answer format (dead states: {stuck})")

    def allowed(self, state: int) -> list[int]:
        return list(self.next[state])
