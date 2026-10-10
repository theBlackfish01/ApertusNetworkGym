"""What kind of violations does a language-model policy commit in the closed loop?

Replays finished closed-loop episodes from the policy's answer cache (no model, no GPU: a prompt
that is not in the cache raises), classifies every decision, and checks that the replay
reproduces the violation count of the stored results file.

    PYTHONPATH=src uv run python results/design/closed_loop_failures.py apertus_ft \\
        results/design/closed_loop_failures_apertus_ft.json

Classes: admissible; rejects although an admissible path exists; accepts although it must
reject; violation, with the rule it breaks; invalid answer (first fit was executed instead).
For conditions with an avoid-link intent, rejects are also counted by the number of admissible
paths the request had.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONDITIONS = ("I1", "mixed_heldout_paraphrases", "heldout_pairs")
LOADS = (240, 390)
SEED = 1


def classify(view, intent, decision, valid: bool) -> str:
    from intents import Intent, admissible_paths, is_admissible

    if not decision.well_formed or not valid:
        return "invalid answer"
    allowed = admissible_paths(view, intent)
    choice = decision.choice
    if is_admissible(view, intent, choice):
        return "admissible"
    if choice is None:
        return "rejects although an admissible path exists"
    if not allowed:
        return "accepts although it must reject"
    broken = []
    for intent_id in intent.ids:
        single = Intent(ids=(intent_id,), text="", link=intent.link)
        if not is_admissible(view, single, choice):
            broken.append("uses the avoided link" if intent_id == "I1" else f"breaks {intent_id}")
    return "violation: " + " and ".join(broken)


def replay(job: dict) -> dict:
    from evaluate import Episode
    from intents import admissible_paths
    from policies import make_policy
    from sim import action_from_choice

    policy = make_policy(job["policy"], backend="transformers")  # answers come from the cache only
    episode = Episode(job)
    classes: Counter = Counter()
    by_intent: dict[str, Counter] = defaultdict(Counter)
    rejects: dict[int, Counter] = defaultdict(Counter)
    while episode.remaining:
        view, intent = episode.view, episode.intent
        (decision,) = policy.decide([episode.request()])
        valid = decision.well_formed and (
            action_from_choice(episode.env.simulator.current_analysis, decision.choice) is not None
        )
        kind = classify(view, intent, decision, valid)
        classes[kind] += 1
        by_intent[intent.key][kind] += 1
        allowed = admissible_paths(view, intent)
        if "I1" in intent.ids and allowed:
            rejects[len(allowed)]["requests"] += 1
            rejects[len(allowed)]["rejected"] += kind.startswith("rejects")
        episode.apply(decision)
    row = episode.result()
    return {
        **{k: job[k] for k in ("condition", "load", "seed")},
        "violations": row["violations"],
        "invalid": row["invalid"],
        "service_blocking_rate": row["service_blocking_rate"],
        "classes": dict(classes.most_common()),
        "by_intent": {key: dict(counter.most_common()) for key, counter in sorted(by_intent.items())},
        "avoid_link_rejects_by_admissible_paths_left": {
            str(size): dict(counter) for size, counter in sorted(rejects.items())
        },
    }


def main() -> None:
    policy, out = sys.argv[1], Path(sys.argv[2])
    stored = json.loads((ROOT / "results" / "eval" / f"{policy}.json").read_text())
    protocol = stored["metadata"]["protocol"]
    jobs = [
        {"policy": policy, "condition": c, "load": load, "seed": SEED,
         "warmup": protocol["warmup"], "window": protocol["window"]}
        for c in CONDITIONS for load in LOADS
    ]  # fmt: skip
    with Pool(3) as pool:
        rows = pool.map(replay, jobs)
    reference = {(e["condition"], e["load"], e["seed"]): e for e in stored["episodes"]}
    for row in rows:
        ref = reference[(row["condition"], row["load"], row["seed"])]
        row["matches_stored_run"] = (
            row["violations"] == ref["violations"]
            and row["invalid"] == ref["invalid"]
            and abs(row["service_blocking_rate"] - ref["service_blocking_rate"]) < 1e-12
        )
        n = sum(row["classes"].values())
        parts = ", ".join(f"{k} {100 * v / n:.1f}%" for k, v in row["classes"].items())
        print(f"{row['condition']:26s} load {row['load']} replay ok: {row['matches_stored_run']} | {parts}")
        for size, counts in row["avoid_link_rejects_by_admissible_paths_left"].items():
            print(f"    {size} admissible path(s): rejected {counts['rejected']} of {counts['requests']}")
    out.write_text(json.dumps({"policy": policy, "seed": SEED, "episodes": rows}, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
