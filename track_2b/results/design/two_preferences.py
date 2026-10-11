"""What does a decider do when an instruction states two preferences (fewest hops, least loaded)?

SPEC section 3 defines the pair as an intersection: if no path is best on both, the request
must be rejected. No training pair has two preferences, so the model was never shown this. The
other natural reading is the ordered one of ``spec.py``: the first-stated preference decides,
the second breaks ties, and a preference never rejects a request that can be served.

For every I2+I3 decision this script records whether the two preferences can be met at once,
what the model did, and whether the decision is right under either reading. Two sources: the
held-out answers of a model (offline), and its closed-loop episodes of the unseen-pairs
condition, replayed from the answer cache (no model, no GPU).

    PYTHONPATH=src uv run python results/design/two_preferences.py apertus_ft \\
        results/train/apertus_ft_epoch2_heldout_predictions.jsonl results/design/two_preferences_apertus_ft.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOADS = (240, 390)
SEEDS = (1, 2, 3)


def classify(view, intent, choice) -> list[str]:
    """Counter keys for one valid I2+I3 decision."""
    from spec import Spec, admissible, from_intent, respects

    spec = from_intent(intent)
    first, second = (set(admissible(view, Spec(prefer=(p,)), "ordered")) for p in spec.prefer)
    if not first:
        return ["nothing feasible"]
    path = choice[0] if choice else None
    conflict = not first & second
    keys = ["decisions", "preferences conflict" if conflict else "preferences agree"]
    if path is None:
        what = "rejects"
    elif path in first & second:
        what = "meets both"
    elif path in first:
        what = "meets the first-stated only"
    elif path in second:
        what = "meets the second-stated only"
    else:
        what = "meets neither"
    keys.append(("conflict: " if conflict else "agree: ") + what)
    if path is not None and (path in first) != (path in second):
        followed = spec.prefer[0] if path in first else spec.prefer[1]
        keys.append(("conflict: " if conflict else "agree: ") + f"follows {followed} over the other")
    keys += [
        f"right under {rule}" for rule in ("intersection", "ordered") if respects(view, spec, choice, rule)
    ]
    return keys


def offline(predictions: Path) -> Counter:
    from intents import Intent
    from prompt import parse_answer
    from view import RequestView

    rows = (json.loads(line) for line in predictions.read_text(encoding="utf-8").splitlines() if line.strip())
    answers = {row["id"]: row["answer"] for row in rows}
    counter: Counter = Counter()
    for line in (ROOT / "data" / "full" / "heldout_pairs.jsonl").read_text(encoding="utf-8").splitlines():
        meta = json.loads(line)["meta"]
        if meta["intent_key"] != "I2+I3":
            continue
        view, intent = RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"])
        well_formed, choice = parse_answer(answers[json.loads(line)["id"]])
        valid = well_formed and (choice is None or view.paths[choice[0]].in_block(choice[1]))
        counter.update(classify(view, intent, choice) if valid else ["invalid answer"])
    return counter


def replay(job: tuple[str, int, int]) -> Counter:
    from evaluate import Episode
    from policies import make_policy
    from sim import action_from_choice

    policy_name, load, seed = job
    stored = json.loads((ROOT / "results" / "eval" / f"{policy_name}.json").read_text())["metadata"][
        "protocol"
    ]
    policy = make_policy(policy_name, backend="transformers")  # answers come from the cache only
    episode = Episode({"policy": policy_name, "condition": "heldout_pairs", "load": load, "seed": seed,
                       "warmup": stored["warmup"], "window": stored["window"]})  # fmt: skip
    counter: Counter = Counter()
    while episode.remaining:
        view, intent = episode.view, episode.intent
        (decision,) = policy.decide([episode.request()])
        if intent.key == "I2+I3":
            analysis = episode.env.simulator.current_analysis
            valid = decision.well_formed and action_from_choice(analysis, decision.choice) is not None
            counter.update(classify(view, intent, decision.choice) if valid else ["invalid answer"])
        episode.apply(decision)
    return counter


def table(counter: Counter) -> dict:
    n = counter["decisions"]
    return {
        key: {"count": count, "share": count / n if n else None} for key, count in sorted(counter.items())
    }


def main() -> None:
    policy, predictions, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    result = {
        "policy": policy,
        "what": "decisions on instructions with two preferences (I2+I3); shares are of the valid decisions "
        "on requests with a feasible path",
        "offline_heldout": table(offline(predictions)),
    }
    shown = [("offline held-out", result["offline_heldout"])]
    if (ROOT / "results" / "eval" / f"{policy}.json").exists():  # closed loop: only once it has been run
        jobs = [(policy, load, seed) for load in LOADS for seed in SEEDS]
        with Pool(3) as pool:
            counters = pool.map(replay, jobs)
        result["closed_loop"] = {"seeds": list(SEEDS)}
        for load in LOADS:
            pooled = sum((c for job, c in zip(jobs, counters, strict=True) if job[1] == load), Counter())
            result["closed_loop"][f"load_{load}"] = table(pooled)
            shown.append((f"closed loop, load {load}", result["closed_loop"][f"load_{load}"]))
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, rows in shown:
        print(name)
        for key, row in rows.items():
            share = "" if row["share"] is None else f" = {100 * row['share']:5.1f}%"
            print(f"  {key:52s} {row['count']:5d}{share}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
