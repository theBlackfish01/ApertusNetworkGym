"""Regular languages for constrained decoding of answer formats other than the decision line.

``decoding.py`` hard-codes the automaton of ``path=<p> slot=<s> | reject``. The translator's
answer (``spec.py``) contains city names, so its language depends on the topology and is built
here from three combinators:

    lit("avoid=")            exactly this text
    seq(a, b, ...)           a, then b, ...
    alt(a, b, ...)           one of them
    opt(a)                   a or nothing

:class:`Dfa` compiles such an expression into a deterministic character automaton (Thompson
construction, then the subset construction). :class:`TokenAutomaton` lifts it to a tokenizer's
vocabulary with the same interface as ``decoding.TokenAutomaton``: state 0 is the start, and
``DONE`` is reached by an end token from an accepting state.
"""

from __future__ import annotations

START, DONE = 0, -1
Expression = tuple  # ("lit", text) | ("seq", parts) | ("alt", parts)


def lit(text: str) -> Expression:
    return ("lit", text)


def seq(*parts: Expression) -> Expression:
    return ("seq", parts)


def alt(*parts: Expression) -> Expression:
    return ("alt", parts)


def opt(part: Expression) -> Expression:
    return ("alt", (part, ("lit", "")))


def gbnf(expression: Expression) -> str:
    """The expression as a GBNF grammar (llama.cpp), so the same language constrains a GGUF model.

    An alternation that occurs more than once becomes a rule of its own; the rest is written inline.
    """
    counts: dict[Expression, int] = {}

    def count(expr: Expression) -> None:
        counts[expr] = counts.get(expr, 0) + 1
        if expr[0] != "lit" and counts[expr] == 1:
            for part in expr[1]:
                count(part)

    count(expression)
    names: dict[Expression, str] = {}
    rules: list[str] = []

    def text(expr: Expression, top: bool = False) -> str:
        kind, body = expr
        if kind == "lit":
            return '"' + body.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if kind == "seq":
            return " ".join(text(part) for part in body)
        if not top and counts[expr] > 1 and len(body) > 2:
            if expr not in names:
                names[expr] = f"r{len(names)}"
                rules.append(f"{names[expr]} ::= {text(expr, top=True)}")
            return names[expr]
        if ("lit", "") in body:  # opt(...)
            rest = [part for part in body if part != ("lit", "")]
            inner = rest[0] if len(rest) == 1 else ("alt", tuple(rest))
            return f"({text(inner, top=True)})?"
        choice = " | ".join(text(part) for part in body)
        return choice if top else f"({choice})"

    root = f"root ::= {text(expression, top=True)}"
    return "\n".join([root, *rules]) + "\n"


class Dfa:
    """Deterministic automaton of an expression; ``moves[state][char]`` is the next state."""

    def __init__(self, expression: Expression) -> None:
        edges: list[dict[str, set[int]]] = []
        empty: list[set[int]] = []  # moves that consume nothing

        def new() -> int:
            edges.append({})
            empty.append(set())
            return len(edges) - 1

        def build(expr: Expression) -> tuple[int, int]:
            kind, body = expr
            if kind == "lit":
                start = state = new()
                for char in body:
                    target = new()
                    edges[state].setdefault(char, set()).add(target)
                    state = target
                return start, state
            if kind == "seq":
                start = state = new()
                for part in body:
                    first, last = build(part)
                    empty[state].add(first)
                    state = last
                return start, state
            if kind == "alt":
                start, end = new(), new()
                for part in body:
                    first, last = build(part)
                    empty[start].add(first)
                    empty[last].add(end)
                return start, end
            raise ValueError(f"unknown expression {kind!r}")

        def closure(states: set[int]) -> frozenset[int]:
            seen, stack = set(states), list(states)
            while stack:
                for target in empty[stack.pop()]:
                    if target not in seen:
                        seen.add(target)
                        stack.append(target)
            return frozenset(seen)

        first, final = build(expression)
        start = closure({first})
        index = {start: START}
        self.moves: list[dict[str, int]] = [{}]
        accepting = set()
        queue = [start]
        while queue:
            subset = queue.pop()
            state = index[subset]
            if final in subset:
                accepting.add(state)
            by_char: dict[str, set[int]] = {}
            for member in subset:
                for char, targets in edges[member].items():
                    by_char.setdefault(char, set()).update(targets)
            for char, targets in sorted(by_char.items()):
                target = closure(targets)
                if target not in index:
                    index[target] = len(self.moves)
                    self.moves.append({})
                    queue.append(target)
                self.moves[state][char] = index[target]
        self.accepting = frozenset(accepting)
        self.alphabet = frozenset(char for moves in self.moves for char in moves)

    def walk(self, state: int, text: str) -> int | None:
        """State after consuming ``text`` from ``state``, or ``None`` if it leaves the language."""
        for char in text:
            state = self.moves[state].get(char)
            if state is None:
                return None
        return state

    def accepts(self, text: str) -> bool:
        return self.walk(START, text) in self.accepting


class TokenAutomaton:
    """Allowed next tokens per state of ``dfa`` for one vocabulary.

    ``token_strings[i]`` is the text token ``i`` decodes to. The tokens are put in a character
    trie that is walked together with the automaton, so the work per state is proportional to the
    token prefixes the state allows, not to the size of the vocabulary.
    """

    def __init__(self, dfa: Dfa, token_strings: list[str], eos_ids: list[int]) -> None:
        trie: dict = {}
        for index, text in enumerate(token_strings):
            if not text or index in eos_ids or not dfa.alphabet.issuperset(text):
                continue
            node = trie
            for char in text:
                node = node.setdefault(char, {})
            node.setdefault("", []).append(index)  # "" holds the tokens that end at this node
        self.next: dict[int, dict[int, int]] = {}
        for state in range(len(dfa.moves)):
            moves: dict[int, int] = {}
            stack = [(trie, state)]
            while stack:
                node, at = stack.pop()
                for char, child in node.items():
                    target = dfa.moves[at].get(char) if char else None
                    if target is None:
                        continue
                    for token in child.get("", ()):
                        moves[token] = target
                    stack.append((child, target))
            if state in dfa.accepting:
                moves.update(dict.fromkeys(eos_ids, DONE))
            self.next[state] = moves
        stuck = [state for state, moves in self.next.items() if not moves]
        if stuck:
            raise ValueError(f"the vocabulary cannot spell the answer format (dead states: {stuck[:5]})")

    def allowed(self, state: int) -> list[int]:
        return list(self.next[state])
