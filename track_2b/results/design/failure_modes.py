"""What kind of mistakes does a model make on the held-out splits? (offline, no simulator)

Every held-out answer is put in one class: exact match with the teacher; an admissible answer
other than the teacher's; a reject although an admissible path exists; an accept although the
admissible set is empty; a violation, with the rule it breaks; not a valid start; malformed.
For requests with an avoid-link intent it also counts rejects by the number of admissible paths
left, which shows when the model gives up.

    PYTHONPATH=src python results/design/failure_modes.py runs/apertus-ft/heldout_predictions.jsonl \\
        results/design/failure_modes_apertus_ft_unconstrained.json

The predictions file holds one ``{"id", "answer"}`` object per line (what ``train.py`` writes).
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from intents import Intent, admissible_paths
from prompt import parse_answer
from view import RequestView

ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("heldout_indist", "heldout_paraphrase", "heldout_pairs")


def classify(view: RequestView, intent: Intent, teacher, answer: str) -> str:
    well_formed, choice = parse_answer(answer)
    allowed = admissible_paths(view, intent)
    if not well_formed:
        return "malformed"
    if choice == teacher:
        return "exact"
    if choice is None:
        return "rejects although an admissible path exists"
    path = view.paths[choice[0]] if choice[0] < len(view.paths) else None
    if path is None or not path.in_block(choice[1]):
        return "not a valid start"
    if not allowed:
        return "accepts although it must reject"
    if choice[0] in allowed:
        return "admissible, but not the teacher's choice"
    broken = []
    for intent_id in intent.ids:
        if choice[0] not in admissible_paths(view, Intent(ids=(intent_id,), text="", link=intent.link)):
            broken.append("uses the avoided link" if intent_id == "I1" else f"breaks {intent_id}")
    return "violation: " + " and ".join(broken)


def main() -> None:
    predictions, out = Path(sys.argv[1]), Path(sys.argv[2])
    answers = {}
    for line in predictions.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            answers[row["id"]] = row["answer"]
    classes: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    rejects: dict[int, Counter] = defaultdict(Counter)
    for split in SPLITS:
        path = ROOT / "data" / "full" / f"{split}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            meta = json.loads(line)["meta"]
            record_id = json.loads(line)["id"]
            view, intent = RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"])
            teacher = tuple(meta["teacher_choice"]) if meta["teacher_choice"] else None
            kind = classify(view, intent, teacher, answers[record_id])
            classes[split][meta["intent_key"]][kind] += 1
            allowed = admissible_paths(view, intent)
            if "I1" in intent.ids and allowed:
                rejects[len(allowed)]["requests"] += 1
                rejects[len(allowed)]["rejected"] += kind.startswith("rejects")
    result = {
        "predictions": predictions.name,
        "classes": {
            split: {
                key: {"n": sum(counter.values()), **dict(counter.most_common())}
                for key, counter in sorted(by_intent.items())
            }
            for split, by_intent in classes.items()
        },
        "avoid_link_rejects_by_admissible_paths_left": {
            str(size): dict(counter) for size, counter in sorted(rejects.items())
        },
    }
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for split, by_intent in result["classes"].items():
        for key, counts in by_intent.items():
            n = counts["n"]
            parts = ", ".join(f"{k} {100 * v / n:.1f}%" for k, v in counts.items() if k != "n")
            print(f"{split:20s} {key:6s} n={n:4d}  {parts}")
    for size, counts in result["avoid_link_rejects_by_admissible_paths_left"].items():
        print(
            f"avoid-link requests with {size} admissible path(s): rejected {counts['rejected']} of {counts['requests']}"
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
