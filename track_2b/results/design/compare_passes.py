"""First pass against second pass on the same held-out records (offline, no simulator).

Both passes answer the same 2,200 prompts; only the labels of some avoid-link pair records differ
(intersection in the first pass, filter-then-rank in the second). Each answer is judged under
the rule its model was trained with. For records whose admissible set is the same under both
rules the two models are also compared record by record: both right, only one right, neither.

    PYTHONPATH=src python results/design/compare_passes.py \\
        results/pass1/train/apertus_ft_heldout_predictions.jsonl runs/pass2-epoch1/heldout_predictions.jsonl \\
        results/design/compare_passes_epoch1.json
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
RULES = {"first": "intersection", "second": "filter"}


def judge(view: RequestView, intent: Intent, answer: str, rule: str) -> str:
    well_formed, choice = parse_answer(answer)
    allowed = admissible_paths(view, intent, rule)
    if not well_formed:
        return "invalid"
    if choice is None:
        return "admissible" if not allowed else "needless reject"
    path = view.paths[choice[0]] if choice[0] < len(view.paths) else None
    if path is None or not path.in_block(choice[1]):
        return "invalid"
    if not allowed:
        return "accepts although it must reject"
    return "admissible" if choice[0] in allowed else "wrong path"


def answers(path: Path) -> dict[str, str]:
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {row["id"]: row["answer"] for row in rows}


def main() -> None:
    first, second, out = answers(Path(sys.argv[1])), answers(Path(sys.argv[2])), Path(sys.argv[3])
    kinds: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    paired: dict[str, Counter] = defaultdict(Counter)
    for split in SPLITS:
        for line in (ROOT / "data" / "full" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            meta = record["meta"]
            view, intent = RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"])
            verdict = {
                name: judge(view, intent, source[record["id"]], RULES[name])
                for name, source in (("first", first), ("second", second))
            }
            group = f"{split}/{meta['intent_key']}"
            for name, kind in verdict.items():
                kinds[group][name][kind] += 1
            same_rule = admissible_paths(view, intent, "intersection") == admissible_paths(
                view, intent, "filter"
            )
            if same_rule:
                ok = (verdict["first"] == "admissible", verdict["second"] == "admissible")
                label = {(True, True): "both right", (True, False): "only first pass right",
                         (False, True): "only second pass right", (False, False): "neither right"}[ok]  # fmt: skip
                paired[group][label] += 1
    result = {
        "first_pass": sys.argv[1],
        "second_pass": sys.argv[2],
        "by_split_and_intent": {
            group: {name: dict(counter.most_common()) for name, counter in sorted(passes.items())}
            for group, passes in sorted(kinds.items())
        },
        "paired_on_records_with_the_same_admissible_set": {
            group: dict(counter.most_common()) for group, counter in sorted(paired.items())
        },
    }
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"{'split / intent':30s} {'n':>4s}  {'admissible 1st':>14s} {'2nd':>6s}   {'needless rejects 1st':>20s} {'2nd':>5s}   only 1st right / only 2nd right"
    )
    for group, passes in sorted(kinds.items()):
        n = sum(passes["first"].values())
        shares = {
            (name, kind): f"{100 * passes[name][kind] / n:5.1f}%"
            for name in ("first", "second")
            for kind in ("admissible", "needless reject")
        }
        pair = paired.get(group, Counter())
        print(f"{group:30s} {n:4d}  {shares['first', 'admissible']:>14s} {shares['second', 'admissible']:>6s}   "
              f"{shares['first', 'needless reject']:>20s} {shares['second', 'needless reject']:>5s}   "
              f"{pair['only first pass right']:3d} / {pair['only second pass right']:3d}")  # fmt: skip
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
