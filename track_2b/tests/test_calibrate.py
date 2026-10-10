"""Tests for the calibration summary logic (no simulation)."""

import pytest

from calibrate import (
    TEACHER,
    environment_metadata,
    job_key,
    paired_teacher_wins,
    run_episode,
    scenario_metadata,
    summarise,
)


def _row(policy, load, seed, blocked, processed=1000, mode="window"):
    return {
        "mode": mode,
        "policy": policy,
        "load": load,
        "seed": seed,
        "processed": processed,
        "accepted": processed - blocked,
        "service_blocking_rate": blocked / processed,
        "bit_rate_blocking_rate": blocked / processed,
        "final_slot_utilisation": 0.5,
    }


def test_summarise_mean_and_sample_std():
    rows = [_row(TEACHER, 210.0, seed, blocked) for seed, blocked in [(1, 10), (2, 20), (3, 30)]]
    (entry,) = summarise(rows)
    assert entry["seeds"] == [1, 2, 3]
    assert entry["service_blocking_rate_mean"] == pytest.approx(0.02)
    assert entry["service_blocking_rate_std"] == pytest.approx(0.01)  # ddof = 1
    assert entry["blocked_total"] == 60
    assert entry["processed_total"] == 3000


def test_paired_teacher_wins_counts_strict_improvements_per_seed():
    rows = [
        _row(TEACHER, 210.0, 1, 5),
        _row("first_fit", 210.0, 1, 9),
        _row(TEACHER, 210.0, 2, 9),
        _row("first_fit", 210.0, 2, 9),
        _row(TEACHER, 210.0, 3, 1),
        _row("first_fit", 210.0, 3, 4),
    ]
    assert paired_teacher_wins(rows, "window", 210.0) == (2, 3)


def test_metadata_builds_without_running_episodes():
    assert scenario_metadata()["k_paths"] == 5
    assert environment_metadata()["ong_commit"]


def test_job_key_round_trips_through_an_episode_row():
    job = {"mode": "cold", "policy": "first_fit", "load": 150.0, "seed": 2, "warmup": 0, "requests": 5}
    row = run_episode(job)
    assert job_key(dict(row, warmup=row["warmup_requests"])) == job_key(job)


def test_window_episode_measures_exactly_the_window():
    row = run_episode(
        {"mode": "window", "policy": "first_fit", "load": 210.0, "seed": 1, "warmup": 20, "requests": 30}
    )
    assert row["processed"] == 30
    assert row["warmup_policy"] == TEACHER
    assert (
        row["processed"]
        == row["accepted"] + row["blocked_resources"] + row["blocked_qot"] + row["rejected_by_policy"]
    )
