"""Does the pair rule of the training data leak into the single avoid-link intent?

In the training pairs I1+I2 and I1+I3 the admissible set is an intersection, so the correct answer
is ``reject`` whenever every fewest-hop path (I1+I2) or the most-free path (I1+I3) contains the
avoided link. With the avoid-link intent alone the same situation has an admissible path. This
script takes requests that carry *only* the avoid-link intent and still have an admissible path,
and compares how often the model rejects them when a training pair rule would have said reject
with how often it does otherwise, also within each number of admissible paths left (so that the
comparison is not just "harder requests").

Two sources: the held-out answers of the fine-tuned model (offline), and, once the closed loop
has been run, its avoid-link episodes of seed 1, replayed from the answer cache (no GPU). "Would
have said reject" always refers to the first-pass rule (intersection).

    PYTHONPATH=src uv run python results/design/pair_rule_leak.py apertus_ft \\
        results/train/apertus_ft_heldout_predictions.jsonl results/design/pair_rule_leak_apertus_ft.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOADS = (240, 390)
SEED = 1


def situation(view, intent) -> tuple[int, bool, bool] | None:
    """``(admissible paths left, I1+I2 would reject, I1+I3 would reject)``; None if reject is right."""
    from intents import Intent, admissible_paths

    allowed = admissible_paths(view, intent)
    if not allowed:
        return None
    # "Would say reject" refers to the first-pass rule (intersection), whatever the current rule is.
    pair = {"text": "", "link": intent.link}
    with_hops = admissible_paths(view, Intent(ids=("I1", "I2"), **pair), rule="intersection")
    with_load = admissible_paths(view, Intent(ids=("I1", "I3"), **pair), rule="intersection")
    return len(allowed), not with_hops, not with_load


def count(counter: Counter, left: int, hops: bool, load: bool, rejected: bool) -> None:
    group = "pair_rule_rejects" if (hops or load) else "no_pair_rule_rejects"
    for key in (
        group,
        f"{group}/left_{left}",
        *(["I1+I2_rejects"] if hops else []),
        *(["I1+I3_rejects"] if load else []),
    ):
        counter[f"{key}/requests"] += 1
        counter[f"{key}/rejected"] += rejected


def offline(predictions: Path) -> Counter:
    from intents import Intent
    from prompt import parse_answer
    from view import RequestView

    answers = {}
    for line in predictions.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            answers[row["id"]] = row["answer"]
    counter: Counter = Counter()
    for split in ("heldout_indist", "heldout_paraphrase"):
        for line in (ROOT / "data" / "full" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            meta = record["meta"]
            if meta["intent_key"] != "I1":
                continue
            found = situation(RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"]))
            if found is not None:
                well_formed, choice = parse_answer(answers[record["id"]])
                count(counter, *found, well_formed and choice is None)
    return counter


def replay(job: tuple[str, int]) -> Counter:
    from evaluate import Episode
    from policies import make_policy

    policy_name, load = job
    stored = json.loads((ROOT / "results" / "eval" / f"{policy_name}.json").read_text())["metadata"][
        "protocol"
    ]
    policy = make_policy(policy_name, backend="transformers")  # answers come from the cache only
    episode = Episode({"policy": policy_name, "condition": "I1", "load": load, "seed": SEED,
                       "warmup": stored["warmup"], "window": stored["window"]})  # fmt: skip
    counter: Counter = Counter()
    while episode.remaining:
        found = situation(episode.view, episode.intent)
        (decision,) = policy.decide([episode.request()])
        if found is not None:
            count(counter, *found, decision.well_formed and decision.choice is None)
        episode.apply(decision)
    return counter


def table(counter: Counter) -> dict:
    keys = sorted({key.rsplit("/", 1)[0] for key in counter})
    return {
        key: {"requests": counter[f"{key}/requests"], "rejected": counter[f"{key}/rejected"],
              "rate": counter[f"{key}/rejected"] / counter[f"{key}/requests"]}
        for key in keys
    }  # fmt: skip


def main() -> None:
    policy, predictions, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    result = {
        "policy": policy,
        "what": "requests with only the avoid-link intent that have an admissible path; 'rejected' is the model's answer",
        "offline_heldout": table(offline(predictions)),
    }
    shown = [("offline held-out", result["offline_heldout"])]
    if (ROOT / "results" / "eval" / f"{policy}.json").exists():  # closed loop: only once it has been run
        with Pool(2) as pool:
            per_load = pool.map(replay, [(policy, load) for load in LOADS])
        pooled = table(sum(per_load, Counter()))
        needless = pooled["pair_rule_rejects"]["rejected"] + pooled["no_pair_rule_rejects"]["rejected"]
        result["closed_loop"] = {
            "seed": SEED,
            "loads": list(LOADS),
            "pooled": pooled,
            **{f"load_{load}": table(c) for load, c in zip(LOADS, per_load, strict=True)},
            "share_of_needless_rejects_where_a_pair_rule_rejects": (
                pooled["pair_rule_rejects"]["rejected"] / needless if needless else None
            ),
        }
        shown.append(("closed loop, pooled", pooled))
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, rows in shown:
        print(name)
        for key, row in rows.items():
            print(
                f"  {key:34s} rejected {row['rejected']:4d} of {row['requests']:4d} = {100 * row['rate']:5.1f}%"
            )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
