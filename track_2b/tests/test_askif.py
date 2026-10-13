"""Asking by consequence: two readers that disagree are asked about only on a request that tells them apart."""

import translate
from intents import Intent
from policies import Request
from spec import Spec, Topology
from translate import Translator, TranslatorPolicy, _parts
from view import PathView, RequestView


class Fixed(Translator):
    def __init__(self, answers: dict[str, Spec]) -> None:
        super().__init__(Topology("t", ("A", "B", "C", "D"), frozenset()))
        self.answers = answers

    def translate(self, texts: list[str]) -> list[Spec]:
        return [self.answers[t] for t in texts]


def path(index: int, nodes: tuple[str, ...], km: int, free: int) -> PathView:
    return PathView(index, nodes, km, free, "QPSK", 4, ((0, 10),))


def view(*paths: PathView) -> RequestView:
    return RequestView(paths[0].nodes[0], paths[0].nodes[-1], 100, 320, 0.5, tuple(paths))


def test_parts_reads_the_ask_mode():
    assert _parts("translate3_ft_ask-ft2") == ("translate3_ft", "translate3_ft2", True, True, "always")
    assert _parts("hybrid3_ft_askif-few70b") == ("translate3_ft", "translate3_few70b", True, True, "if")
    assert _parts("translate3_ft_askfair-ft2") == ("translate3_ft", "translate3_ft2", True, True, "fair")
    assert _parts("hybrid3_ft_noguard")[2] is False


def test_asked_only_when_a_request_tells_the_readings_apart(monkeypatch):
    text = "keep it short"
    first, other = Spec(prefer=("hops",)), Spec(prefer=("km",))
    truth = Spec(prefer=("km",))
    monkeypatch.setattr(translate, "meant", lambda intent: truth)
    policy = TranslatorPolicy("t", Fixed({text: first}), "ordered", Fixed({text: other}), ask="if")
    intent = Intent(text=text)
    # one request on which fewest hops and shortest km pick the same path: no question yet
    same = view(path(0, ("A", "B"), 100, 50), path(1, ("A", "C", "B"), 300, 80))
    (decision,) = policy.decide([Request(same, intent)])
    assert decision.choice[0] == 0 and not decision.raw.startswith("asked+")
    assert text in policy._pending and text not in policy._asked
    # one on which they differ: the operator is asked and the true meaning is applied from then on
    differs = view(path(0, ("A", "B"), 500, 50), path(1, ("A", "C", "B"), 300, 80))
    (decision,) = policy.decide([Request(differs, intent)])
    assert decision.choice[0] == 1 and decision.raw.startswith("asked+")
    assert text in policy._asked and text not in policy._pending
    # the always-asking policy asks on the first request
    always = TranslatorPolicy("t", Fixed({text: first}), "ordered", Fixed({text: other}))
    (decision,) = always.decide([Request(same, intent)])
    assert decision.raw.startswith("asked+")


def test_a_reading_outside_the_language_is_asked_about_at_once(monkeypatch):
    text = "slot 12 please"
    monkeypatch.setattr(translate, "meant", lambda intent: Spec(status="unsupported"))
    policy = TranslatorPolicy("t", Fixed({text: Spec(prefer=("hops",))}), "ordered",
                              Fixed({text: Spec(status="unsupported")}), ask="if")  # fmt: skip
    (decision,) = policy.decide([Request(view(path(0, ("A", "B"), 100, 50)), Intent(text=text))])
    assert decision.raw == "asked+unsupported" and text not in policy._pending
