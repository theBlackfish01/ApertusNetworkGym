"""The operator console: reading, preview, applying and stepping, from recorded answers (no server)."""

import argparse

import pytest

from console import Console, who_decided
from spec import EMPTY, Spec, describe

OWNER_LINE = "paris se mat guzarna, baqi jo kam busy hai woh le lo"  # both readers answered it on the laptop


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
def console():
    args = argparse.Namespace(topology="nobel-eu", load=390, seed=11, warmup=0, horizon=6, base_url="", standing=False, reader=None,
                              policy=None, decider=None)  # fmt: skip
    return Console(args)


def test_read_preview_apply_step(console):
    state = console.state()
    assert len(state["nodes"]) == 28 and len(state["links"]) == 41
    assert any(r["text"] == OWNER_LINE for r in console.recorded)
    read = console.read(OWNER_LINE)
    assert "error" not in read and read["differ"] is True
    lines = [r["line"] for r in read["readings"]]
    assert lines[0] != lines[1] and all(r["tapi"] for r in read["readings"])
    preview = read["preview"]
    assert preview["without"]["requests"] == 6 and len(preview["readings"]) == 2
    assert "decide_differently" in preview and isinstance(preview["differences"], list)
    assert "error" in console.read("an instruction nobody ever read")  # no server: must say so, not guess
    assert console.apply(OWNER_LINE, lines[1], asked=True)["ok"]
    rows = console.step(3)
    assert [r["n"] for r in rows] == [1, 2, 3]
    assert all(r["who"] == "rule engine" and r["asked"] and r["respects"] is not None for r in rows)
    assert console.state()["stats"]["served"] == 3 and console.state()["instruction"]["line"] == lines[1]
    assert console.apply("none", "none", asked=False)["ok"] and console.step(1)[0]["respects"] is None
    assert "error" in console.apply("something", "not a line", asked=False)
