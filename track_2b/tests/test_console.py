"""The operator console from recorded answers (no server): policies, instructions, questions, the feed."""

import argparse

import pytest

from console import Console, who_decided
from spec import EMPTY, Spec, describe

OWNER_LINE = "paris se mat guzarna, baqi jo kam busy hai woh le lo"  # the two readers answered it differently
POLICY = "For 10G services. The route has to pass through Warsaw."  # a recorded policy sentence (v4_en)


def make(**over) -> Console:
    args = {"topology": "nobel-eu", "load": 390, "seed": 1, "warmup": 0, "horizon": 4, "base_url": "", "policy": None,
            "decider": None, "reader": None, "arrivals": False, "mix": False, "auto_answer": False}  # fmt: skip
    args.update(over)
    return Console(argparse.Namespace(**args))


def test_who_decided_and_readback():
    assert (
        who_decided("avoid=Zurich-Milan; via=none; hops=any; km=any; path=any; prefer=none; rest=none")
        == "rule engine"
    )
    assert (
        who_decided(
            "asked+decider:path=1 slot=3\tavoid=none; via=none; hops=any; km=any; path=any; prefer=none; rest=more"
        )
        == "decider"
    )
    assert who_decided("guard:path=1 slot=3") == "decider, choice replaced by the guard"
    assert who_decided("unsupported") == "not applied"
    assert who_decided("offline:unsupported") == "rule engine (decider offline)"
    assert describe(EMPTY) == "No constraint and no preference."
    assert describe(Spec(status="no_instruction")).startswith("Not a routing instruction")


@pytest.fixture(scope="module")
def console() -> Console:
    return make()


def test_state_and_recorded(console):
    state = console.state()
    assert len(state["nodes"]) == 28 and len(state["links"]) == 41
    assert state["question"] is None and state["policies"] == [] and state["stats"]["served"] == 0
    assert state["pending"]["instruction"]["text"] == "none"
    assert any(r["text"] == OWNER_LINE for r in console.recorded["instructions"])
    assert any(r["text"] == POLICY for r in console.recorded["policies"])
    assert console.feed[0]["kind"] == "start"


def test_policy_read_conflict_add_report_withdraw(console):
    first = console.read_policy(POLICY)
    assert (
        "error" not in first and first["applies"] and first["scope"] == "rate:10" and first["until"] is None
    )
    assert first["conflicts"] == [] and first["preview"]["horizon"] == 4 and first["tapi"]
    assert console.add_policy(first["text"], first["line"])["ok"]
    state = console.state()
    assert state["in_force"]["count"] == 1 and state["policies"][0]["line"].endswith(
        "scope=rate:10; until=open; rest=none"
    )
    rows = console.step(5)
    assert len(rows) == 5 and all(r["who"].startswith("rule engine") for r in rows)
    covered = [r for r in rows if r["policies"]]
    assert all(r["bit_rate"] == 10 and r["respects"] is True for r in covered)
    assert all(r["policies"] == [] and r["respects"] is None for r in rows if r["bit_rate"] != 10)
    report = console.state()["policies"][0]
    assert report["in_scope"] == len(covered) and report["violations"] == 0 and report["active"]
    assert any(e["kind"] == "decision" for e in console.feed) and all(
        e["kind"] != "question" for e in console.feed
    )
    # a second policy that overrides the first's preference is named as a conflict, and can still be added
    second = console.read_policy("least busy route pls, if its a tie just take fewer hops")
    assert "error" not in second
    assert console.add_policy(second["text"], second["line"])["ok"]
    third = console.read_policy("shortest in km pls, load doesnt matter for this one")
    assert any(c["kind"] == "override" for c in third["conflicts"])
    assert console.withdraw_policy(console.state()["policies"][-1]["id"])["ok"]
    assert "error" in console.withdraw_policy(999)
    assert "error" in console.read_policy("a policy nobody ever read")  # no server: say so, never guess


def test_typed_instruction_asks_by_consequence_and_the_answer_settles_it(console):
    read = console.read_instruction(OWNER_LINE)
    assert read["ok"] and read["differ"] and len(read["readings"]) == 2
    assert read["readings"][0]["line"] != read["readings"][1]["line"]
    assert console.state()["pending"]["instruction"]["typed"]
    if read["decide_differently"]:
        assert console.step(3) == [] and console.question is not None  # the stream waits for the answer
        assert console.question["text"] == OWNER_LINE and "error" in console.answer(999, 1)
        assert console.answer(console.question["id"], 2)["ok"] and console.question is None
        row = console.step(1)[0]
        assert (
            row["instruction"] == OWNER_LINE and row["asked"] and row["line"] == read["readings"][1]["line"]
        )
    else:  # the pending request does not tell them apart: the first reading stands
        row = console.step(1)[0]
        assert row["instruction"] == OWNER_LINE and row["asked"] is False
    rows = console.step(2)
    assert rows and rows[0]["instruction"] == "none"  # a typed instruction holds for one request only
    assert console.state()["stats"]["questions"] <= 1
    assert "error" in console.read_instruction("an instruction nobody ever read")
    assert "error" in console.confirm_instruction("x", "not a line")


def test_mixed_stream_with_arrivals_and_the_simulated_operator():
    console = make(warmup=1000, arrivals=True, mix=True, auto_answer=True)
    rows = console.step(40)
    assert len(rows) == 40 and console.question is None
    stats = console.state()["stats"]
    assert stats["served"] == 40 and stats["unread"] == 0, (
        "every drawn text must be recorded at this load and seed"
    )
    assert stats["policies_active"] >= 1 and any(r["policies"] for r in rows)
    kinds = {e["kind"] for e in console.feed}
    assert {"policy_in", "policy_read", "policy_added", "instruction", "reading", "decision"} <= kinds
    assert any(r["instruction"] != "none" for r in rows)
    assert all(r["who"] != "decider" for r in rows)  # no server: the rule engine stands in, and says so
    offline = [r for r in rows if r["who"].startswith("rule engine (decider offline)")]
    assert all(r["kind"] in ("new", "partial") for r in offline)
    questions = [e for e in console.feed if e["kind"] == "question"]
    assert all("simulated operator" in e["title"] for e in questions)
    judged = {r["judged"] for r in rows if r["respects"] is not None}
    assert judged and judged <= {"the instruction and the policies together", "the instruction", "the policies",
                                 "the instruction's own rule, policies aside"}  # fmt: skip
    assert console.settings(auto_answer=False)["settings"]["auto_answer"] is False
    assert console.state()["settings"]["mix"] is True
