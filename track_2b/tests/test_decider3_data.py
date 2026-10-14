"""The matched decider's data (decider3_data.py): where a sentence is placed and what it is labelled."""

import json
from pathlib import Path

from decider3_data import placement, record
from prompt import format_choice
from spec import EMPTY, admissible, choose, load_topology, parse_spec, validate
from translate import _parts
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]


def states(key: str | None = None, count: int = 40) -> list[dict]:
    rows = []
    with (ROOT / "data" / "full" / "heldout_indist.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if key is None or row["meta"]["intent_key"] == key:
                rows.append(row)
            if len(rows) == count:
                break
    return rows


def test_a_link_on_the_first_candidate_is_labelled_by_the_rule_engine():
    topology = load_topology("nobel-eu")
    for state in states():
        view = RequestView.from_json(state["meta"]["view"])
        feasible = [p for p in view.paths if p.feasible]
        if len(feasible) < 2:
            continue
        a, b = feasible[0].nodes[:2]
        line = f"avoid={a}-{b}; via=none; hops=any; km=any; path=any; prefer=none; rest=none"
        spec = validate(parse_spec(line), topology)
        made = record(state, view, {"text": f"keep off {a}-{b}", "kind": "en: avoid_link", "line": line, "spec": spec},
                      "check", 0)  # fmt: skip
        assert made["completion"][0]["content"] == format_choice(choose(view, spec))
        assert made["meta"]["admissible_paths"] == list(admissible(view, spec))
        assert feasible[0].index not in made["meta"]["admissible_paths"]
        assert placement(view, spec) in ("restrictive", "impossible")
        return
    raise AssertionError("no state with two feasible candidates among the first ones")


def test_without_an_instruction_the_label_is_the_first_deciders():
    for state in states("I0", 20):
        view = RequestView.from_json(state["meta"]["view"])
        made = record(state, view, None, "check", 0)
        assert made["meta"]["teacher_choice"] == state["meta"]["teacher_choice"]
        assert made["meta"]["spec"] == EMPTY.to_json()
        assert made["prompt"][-1]["content"].splitlines()[1] == "Intent: none"


def test_the_fourth_format_ranks_preferences_in_order():
    assert _parts("hybrid4_ft")[3] and _parts("translate4_ft")[3]
    assert _parts("hybrid3_ft")[3] and not _parts("hybrid2_ft")[3]
