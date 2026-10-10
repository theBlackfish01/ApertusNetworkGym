"""Load calibration for the ``jocn_benchmark`` scenario (SPEC.md sections 7 and 9, day 1).

For every policy, load and seed this runs up to two episodes:

cold    The policy decides requests 1..N on an initially empty network (N = ``--requests``,
        default 1,000). This is the measurement ONG's JOCN load sweep reports.
window  The closed-loop evaluation protocol of SPEC section 7: the no-intent teacher decides a
        warm-up of ``--warmup`` requests, the counters are reset with ``only_episode_counters``,
        then the policy decides the next ``--window`` requests. The evaluation loads are picked
        from this mode, because it is the one the final table uses.

The same seed gives the same arrival sequence for every policy (ONG draws traffic from its own
RNG), so policies are compared on identical traffic.

All episode rows, a per (mode, policy, load) summary and the run metadata go to one JSON file;
a markdown table rendered from that JSON is written next to it. Each finished episode is also
appended to ``<out>.partial.jsonl`` at once, so an interrupted run resumes where it stopped.

    uv run python src/calibrate.py                                  # loads 150 210 270, seeds 1-3
    uv run python src/calibrate.py --loads 330 390 --out results/calibration/extra.json
    uv run python src/calibrate.py --render results/calibration/day1_sweep.json   # table only

Memory: about 150 MB per worker. WSL2 draws its RAM from the Windows host (shared with Docker
Desktop and everything else running), so the default is 4 workers; raise ``--workers`` only
when the host has memory to spare.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from optical_networking_gym import build_scenario
from optical_networking_gym.heuristics import select_heuristic_action

from sim import BASELINE, SCENARIO, TEACHER, build_env

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {
    BASELINE: "KSP-BM-FF (baseline)",
    TEACHER: "BM-LS-KSP (teacher)",
}


def job_key(job: dict) -> tuple:
    return (job["mode"], job["policy"], float(job["load"]), int(job["seed"]), job["warmup"], job["requests"])


def run_episode(job: dict) -> dict:
    policy, load, seed, mode = job["policy"], job["load"], job["seed"], job["mode"]
    warmup, requests = job["warmup"], job["requests"]

    env = build_env(load, seed, episode_length=warmup + requests)
    _, info = env.reset(seed=seed)
    simulator = env.simulator

    for _ in range(warmup):
        _, _, _, _, info = env.step(select_heuristic_action(TEACHER, env, info))
    if warmup:
        # Resets the episode counters and the step counter; the network state is kept.
        _, info = env.reset(options={"only_episode_counters": True})

    started = time.perf_counter()
    for index in range(requests):
        _, _, terminated, truncated, info = env.step(select_heuristic_action(policy, env, info))
        if (terminated or truncated) and index < requests - 1:
            raise RuntimeError(f"episode ended early at request {index + 1} of {requests}: {job}")
    wall_s = time.perf_counter() - started

    snap = simulator.statistics.snapshot()
    slot_allocation = simulator.state.slot_allocation
    return {
        "mode": mode,
        "policy": policy,
        "load": float(load),
        "seed": int(seed),
        "warmup_requests": warmup,
        "warmup_policy": TEACHER if warmup else None,
        "requests": requests,
        "processed": int(snap.episode_services_processed),
        "accepted": int(snap.episode_services_accepted),
        "blocked_resources": int(snap.episode_services_blocked_resources),
        "blocked_qot": int(snap.episode_services_blocked_qot),
        "rejected_by_policy": int(snap.episode_services_rejected_by_agent),
        "service_blocking_rate": float(snap.episode_service_blocking_rate),
        "bit_rate_blocking_rate": float(snap.episode_bit_rate_blocking_rate),
        "final_slot_utilisation": float(np.mean(slot_allocation != -1)),
        "active_services_at_end": len(simulator.state.active_services_by_id),
        "wall_s": round(wall_s, 3),
        "ms_per_request": round(1000.0 * wall_s / requests, 3),
    }


def summarise(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["mode"], row["policy"], row["load"])].append(row)

    summary = []
    for (mode, policy, load), group in sorted(groups.items()):
        group = sorted(group, key=lambda r: r["seed"])
        entry = {"mode": mode, "policy": policy, "load": load, "seeds": [r["seed"] for r in group]}
        for metric in ("service_blocking_rate", "bit_rate_blocking_rate", "final_slot_utilisation"):
            values = [r[metric] for r in group]
            entry[f"{metric}_mean"] = statistics.fmean(values)
            # Sample standard deviation across seeds (ddof = 1), as reported in the paper tables.
            entry[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
        entry["blocked_total"] = sum(r["processed"] - r["accepted"] for r in group)
        entry["processed_total"] = sum(r["processed"] for r in group)
        summary.append(entry)
    return summary


def paired_teacher_wins(rows: list[dict], mode: str, load: float) -> tuple[int, int]:
    """Seeds where the teacher blocks strictly less than first_fit on the same traffic."""
    by_seed: dict[int, dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row["mode"] == mode and row["load"] == load:
            by_seed[row["seed"]][row["policy"]] = row["service_blocking_rate"]
    pairs = [v for v in by_seed.values() if TEACHER in v and BASELINE in v]
    return sum(v[TEACHER] < v[BASELINE] for v in pairs), len(pairs)


def render_markdown(result: dict) -> str:
    meta, rows, summary = result["metadata"], result["episodes"], result["summary"]
    lines = [
        f"# Load calibration — `{meta['scenario']}`",
        "",
        (
            f"Generated from `{meta['output']}` (run {meta['run_id']}). Rendered by `src/calibrate.py`; "
            "do not edit by hand."
        ),
        "",
        (
            f"ONG commit `{meta['ong_commit']}`, seeds {meta['seeds']}, mean ± sample std across seeds. "
            "SBP = service blocking probability, BBP = bit-rate blocking probability."
        ),
    ]
    descriptions = {
        "cold": f"Policy decides requests 1–{meta['requests']} on an empty network (ONG JOCN sweep style).",
        "window": (
            f"Teacher warm-up of {meta['warmup']} requests, counters reset, policy decides the next "
            f"{meta['window']} (SPEC section 7 protocol)."
        ),
    }
    for mode in meta["modes"]:
        entries = {(e["policy"], e["load"]): e for e in summary if e["mode"] == mode}
        loads = sorted({load for (_, load) in entries})
        lines += ["", f"## Mode `{mode}`", "", descriptions[mode], ""]
        header = ["Load (E)"]
        for policy in meta["policies"]:
            header += [f"SBP % {POLICIES.get(policy, policy)}", f"BBP % {POLICIES.get(policy, policy)}"]
        header += ["Teacher better (seeds)", "Slots in use at last request % (teacher)"]
        lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        for load in loads:
            cells = [f"{load:g}"]
            for policy in meta["policies"]:
                e = entries.get((policy, load))
                if e is None:
                    cells += ["–", "–"]
                    continue
                cells.append(
                    f"{100 * e['service_blocking_rate_mean']:.2f} ± {100 * e['service_blocking_rate_std']:.2f}"
                )
                cells.append(
                    f"{100 * e['bit_rate_blocking_rate_mean']:.2f} ± {100 * e['bit_rate_blocking_rate_std']:.2f}"
                )
            wins, n = paired_teacher_wins(rows, mode, load)
            cells.append(f"{wins}/{n}" if n else "–")
            teacher = entries.get((TEACHER, load))
            cells.append(f"{100 * teacher['final_slot_utilisation_mean']:.1f}" if teacher else "–")
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def environment_metadata() -> dict:
    direct_url = json.loads(
        importlib.metadata.distribution("optical-networking-gym").read_text("direct_url.json") or "{}"
    )
    try:
        repo_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        repo_commit = None
    return {
        "ong_version": importlib.metadata.version("optical-networking-gym"),
        "ong_commit": direct_url.get("vcs_info", {}).get("commit_id"),
        "repo_commit": repo_commit,
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }


def scenario_metadata() -> dict:
    config = build_scenario(SCENARIO)  # load and seed vary per episode; everything else is fixed
    return {
        "topology_id": config.topology_id,
        "k_paths": config.k_paths,
        "num_spectrum_resources": config.num_spectrum_resources,
        "frequency_slot_bandwidth_hz": config.frequency_slot_bandwidth,
        "bit_rates": list(config.bit_rates),
        "mean_holding_time": config.mean_holding_time,
        "modulations": [m.name for m in config.modulations],
        "qot_constraint": config.qot_constraint,
        "mask_mode": str(config.mask_mode),
        "launch_power_dbm": config.launch_power_dbm,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--loads", type=float, nargs="+", default=[150.0, 210.0, 270.0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--policies", nargs="+", default=list(POLICIES))
    parser.add_argument("--modes", nargs="+", choices=["cold", "window"], default=["cold", "window"])
    parser.add_argument("--requests", type=int, default=1_000, help="requests in cold mode")
    parser.add_argument("--warmup", type=int, default=1_000, help="teacher warm-up in window mode")
    parser.add_argument("--window", type=int, default=2_000, help="measured requests in window mode")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "calibration" / "day1_sweep.json")
    parser.add_argument("--render", type=Path, help="only re-render the markdown table of an existing JSON")
    args = parser.parse_args()

    if args.render:
        result = json.loads(args.render.read_text())
        args.render.with_suffix(".md").write_text(render_markdown(result))
        print(render_markdown(result))
        return

    jobs = []
    for mode in args.modes:
        warmup, requests = (0, args.requests) if mode == "cold" else (args.warmup, args.window)
        for policy in args.policies:
            for load in args.loads:
                for seed in args.seeds:
                    jobs.append(
                        {
                            "mode": mode,
                            "policy": policy,
                            "load": load,
                            "seed": seed,
                            "warmup": warmup,
                            "requests": requests,
                        }
                    )

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".partial.jsonl")
    wanted = {job_key(job) for job in jobs}
    rows = []
    if partial.exists():
        rows = [json.loads(line) for line in partial.read_text().splitlines() if line.strip()]
        rows = [row for row in rows if job_key(dict(row, warmup=row["warmup_requests"])) in wanted]
        done = {job_key(dict(row, warmup=row["warmup_requests"])) for row in rows}
        jobs = [job for job in jobs if job_key(job) not in done]
        print(f"resuming: {len(rows)} episodes already in {partial.name}, {len(jobs)} to run", flush=True)

    started = datetime.now(UTC)
    total = len(rows) + len(jobs)
    if jobs:
        with Pool(min(args.workers, len(jobs))) as pool, partial.open("a") as checkpoint:
            for row in pool.imap_unordered(run_episode, jobs):
                rows.append(row)
                checkpoint.write(json.dumps(row) + "\n")
                checkpoint.flush()
                print(
                    f"[{len(rows):>3}/{total}] {row['mode']:<6} {row['policy']:<15} load={row['load']:g} "
                    f"seed={row['seed']} SBP={100 * row['service_blocking_rate']:.2f}% "
                    f"({row['ms_per_request']:.1f} ms/request)",
                    flush=True,
                )
    rows.sort(key=lambda r: (r["mode"], r["policy"], r["load"], r["seed"]))

    result = {
        "metadata": {
            "run_id": started.strftime("%Y%m%dT%H%M%SZ"),
            "started_utc": started.isoformat(),
            "finished_utc": datetime.now(UTC).isoformat(),
            "command": " ".join(sys.argv),
            "output": out.relative_to(ROOT).as_posix() if out.is_relative_to(ROOT) else str(out),
            "scenario": SCENARIO,
            "scenario_config": scenario_metadata(),
            "teacher": TEACHER,
            "policies": args.policies,
            "loads": args.loads,
            "seeds": args.seeds,
            "modes": args.modes,
            "requests": args.requests,
            "warmup": args.warmup,
            "window": args.window,
            **environment_metadata(),
        },
        "summary": summarise(rows),
        "episodes": rows,
    }
    out.write_text(json.dumps(result, indent=2) + "\n")
    out.with_suffix(".md").write_text(render_markdown(result))
    partial.unlink(missing_ok=True)
    print(render_markdown(result))
    print(f"wrote {out} and {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
