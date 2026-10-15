"""The operator console from recorded answers (no server): policies, instructions, questions, the feed."""

import argparse
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from console import Console, Handler, who_decided
from spec import EMPTY, Spec, describe

OWNER_LINE = "pass through budapest but dont go through zagreb"  # the two readers answered it differently
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
    # the owner's Urdu lines are not offered (the owner's request)
    assert not any(r["lang"] == "ur" for r in console.recorded["instructions"])
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
    # a reading a question can offer: the instruction names a place outside the network
    assert console.confirm_instruction("y", "unresolved") == {"ok": True, "line": "unresolved"}


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


def test_inspector_explains_each_candidate_and_shows_the_spectrum():
    from console_extras import explain

    console = make()
    view = console.episode.view
    link = view.paths[0].links[0]
    spec = Spec(avoid=(link,), prefer=("hops",))
    detail = explain(view, spec, None)
    first = detail["paths"][0]
    assert any("avoided link" in why for why in first["excluded"])  # candidate 0 uses the avoided link
    assert all(p["index"] not in detail["admissible"] for p in detail["paths"] if p["excluded"])
    ranked = explain(view, Spec(prefer=("hops",)), None)
    if any(p["feasible"] for p in ranked["paths"]):
        assert (
            ranked["steps"][0]["by"] == "fewest hops" and ranked["admissible"] == ranked["steps"][0]["kept"]
        )
    console.add_policy(POLICY, console.read_policy(POLICY)["line"])
    rows = console.step(3)
    assert len(rows) == 3
    full = console.request_detail(1)["row"]
    inspect, strips = full["inspect"], full["spectrum"]
    assert len(inspect["paths"]) == 5
    assert len(full["used"]) == 41
    if full["route"]:
        assert inspect["chosen"] == full["path"] and len(strips) == len(full["route"]) - 1
        assert all(len(s["occupied"]) == 320 and s["block"][0] == full["slot"] for s in strips)
    else:
        assert strips == []
    state = console.state()
    assert all("inspect" not in r and "spectrum" not in r for r in state["audit"])  # kept out of every state
    assert len(state["series"]["violation"]) == 3
    assert console.request_detail(4)["decided"] is False and "error" in console.request_detail(9)
    policy = state["policies"][0]
    console.withdraw_policy(policy["id"])
    assert console.state()["policies"][0]["ended"] is not None


def test_race_lanes_replay_the_stored_runs():
    import time

    from console_extras import LANES, Race

    race = Race(390, 1, lanes=[lane for lane in LANES if lane[0] in ("first_fit", "reader")])
    for _ in range(600):
        if race.status != "preparing":
            break
        time.sleep(0.1)
    assert race.status == "ready", race.error
    assert race.step(20) == 20
    state = race.state(every=5)
    assert [lane["served"] for lane in state["lanes"]] == [20, 20]
    assert all(len(lane["series"]) == 4 and len(lane["links"]) == 41 for lane in state["lanes"])
    assert state["last"]["n"] == 20 and set(state["last"]["lanes"]) == {"first_fit", "reader"}
    assert all(lane["same_as_stored"] is None for lane in state["lanes"])  # checked only when complete
    with pytest.raises(ValueError):
        Race(300, 1)


def test_the_server_refuses_bad_bodies_and_paths(console):
    server = ThreadingHTTPServer(("127.0.0.1", 0), type("Bound", (Handler,), {"console": console}))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def status(path: str, body: bytes | None = None, headers: dict | None = None) -> int:
        request = urllib.request.Request(base + path, data=body, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    try:
        assert status("/") == 200 and status("/legacy") == 200
        assert status("/assets/../index.html") == 404 and status("/assets/../../console.py") == 404
        assert status("/api/step", b"[]") == 400  # not an object
        assert status("/api/step", json.dumps({"count": None}).encode()) == 400  # not a number
        assert status("/api/race/start", json.dumps({"load": "x"}).encode()) == 400
        assert status("/api/race/start", json.dumps({"load": 300}).encode()) == 400  # not a stored run
        assert status("/api/step", b"{}", {"Content-Length": str(2 << 20)}) == 413
    finally:
        server.shutdown()
