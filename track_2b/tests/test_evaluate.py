"""Closed-loop runner: environments stepped in worker processes give the same rows as in-process."""

from evaluate import run_group, run_pool
from policies import Oracle

TIMING = ("decision_ms", "group_decisions_per_s")


def test_pool_matches_single_process():
    jobs = [
        {"policy": "oracle", "condition": condition, "load": 390, "seed": seed, "warmup": 60, "window": 25}
        for condition, seed in [
            ("I1", 1),
            ("heldout_pairs", 1),
            ("I3", 2),
            ("mixed_heldout_paraphrases", 2),
            ("I0", 3),
        ]
    ]

    def strip(rows):
        return sorted(
            ({k: v for k, v in row.items() if k not in TIMING} for row in rows),
            key=lambda r: (r["condition"], r["seed"]),
        )

    done = []
    pooled = run_pool(Oracle(), jobs, workers=3, on_done=done.append)
    assert len(pooled) == len(done) == len(jobs)
    assert strip(pooled) == strip(run_group(Oracle(), jobs))
    assert all(row["processed"] == 25 and row["violations"] == 0 for row in pooled)
