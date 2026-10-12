"""Closed-loop and offline evaluation (SPEC sections 6 and 7).

closed   The protocol applied identically to every policy. For each condition, load and seed:
         1. build the ``jocn_benchmark`` environment;
         2. warm-up: the no-intent teacher (ONG BM-LS-KSP) decides the first 1,000 requests;
         3. reset the episode counters;
         4. window: the policy decides the next 2,000 requests, each carrying an intent drawn
            from the condition. A decision that is not a valid action counts as invalid and is
            replaced by ONG's first fit; a violation is an executed decision outside the
            intent's admissible set. Counted next to it: violations under the ordered reading
            of several preferences (``spec.py``), and decisions for which a translator flagged
            the instruction instead of applying it.
         The intent of request i is the same for every policy (it depends on the condition, load,
         seed and the request's candidate paths only), so policies are compared like for like.

offline  Agreement with the teacher on the held-out dataset splits, without the simulator:
         exact match and admissible-set agreement (the number that matters for intents).
         ``--data data/probes`` scores the probe sets of ``corpora.py`` the same way; for
         instructions that should not be applied it also reports how often the decision is
         the policy's own decision without an instruction.

demo     A short live run that prints a few prompt/answer exchanges (used by ``make run``).

    uv run python src/evaluate.py closed --policy oracle
    uv run python src/evaluate.py closed --policy apertus_ft --base-url http://localhost:8000/v1 --model apertus-ft
    uv run python src/evaluate.py offline --policy mlp
    uv run python src/evaluate.py demo --policy oracle

Results go to ``results/eval/<policy>.json`` and ``results/offline/<policy>.json``. Finished
episodes are checkpointed, so an interrupted closed-loop run resumes.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from multiprocessing import Pool
from pathlib import Path

from intents import (
    HELDOUT_PAIRS,
    NO_INTENT,
    SINGLES,
    Intent,
    admissible_paths,
    is_admissible,
    sample_intent,
    teacher_choice,
)
from policies import Decision, Policy, Request, make_policy
from prompt import format_choice, parse_answer, render_prompt
from spec import EMPTY, Spec, from_intent, respects
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]
EVAL_LOADS = (240, 390)  # teacher blocking ~1.2 % and ~6.0 % (results/calibration, docs/decisions.md)
EVAL_SEEDS = (1, 2, 3)
WARMUP, WINDOW = 1_000, 2_000
CONDITIONS = ("I0", "I1", "I2", "I3", "I4", "mixed_heldout_paraphrases", "heldout_pairs")
HELDOUT_SPLITS = ("heldout_indist", "heldout_paraphrase", "heldout_pairs")
METRICS = ("service_blocking_rate", "bit_rate_blocking_rate", "violation_rate", "invalid_rate", "decision_ms",
           "ordered_violation_rate")  # fmt: skip
# a translator's answer when it does not apply an instruction
FLAGS = ("unsupported", "no_instruction", "unresolved", "malformed")


def condition_intent(condition: str, view: RequestView, rng: random.Random) -> Intent:
    """The intent carried by one request under a condition."""
    if condition == "I0":
        return NO_INTENT
    if condition in SINGLES:
        return sample_intent(view, (condition,), rng)
    if condition == "mixed_heldout_paraphrases":
        return sample_intent(view, (rng.choice(SINGLES),), rng, heldout=True)
    if condition == "heldout_pairs":
        return sample_intent(view, rng.choice(HELDOUT_PAIRS), rng)
    raise ValueError(f"unknown condition {condition!r}")


class Episode:
    """One (condition, load, seed) run, advanced one decision at a time."""

    def __init__(self, job: dict) -> None:
        from optical_networking_gym.heuristics import select_heuristic_action

        from sim import TEACHER, build_env

        self.job = job
        self.env = build_env(job["load"], job["seed"], episode_length=job["warmup"] + job["window"])
        _, self.info = self.env.reset(seed=job["seed"])
        for _ in range(job["warmup"]):
            _, _, _, _, self.info = self.env.step(select_heuristic_action(TEACHER, self.env, self.info))
        if job["warmup"]:
            _, self.info = self.env.reset(options={"only_episode_counters": True})
        self.rng = random.Random(f"eval-{job['condition']}-{job['load']}-{job['seed']}")
        self.counts: Counter = Counter()
        self.by_intent: dict[str, Counter] = defaultdict(Counter)  # the same counts per intent key
        self.seconds = 0.0
        self.remaining = job["window"]
        self.trace: list[dict] = []
        self._prepare()

    def _prepare(self) -> None:
        from sim import view_from_analysis

        self.view = view_from_analysis(self.env.simulator.current_analysis)
        self.intent = condition_intent(self.job["condition"], self.view, self.rng)

    def request(self) -> Request:
        return Request(self.view, self.intent, self.env, self.info)

    def apply(self, decision: Decision, *, keep_trace: bool = False) -> None:
        from optical_networking_gym.heuristics import select_first_fit_action

        from sim import action_from_choice, choice_from_action

        analysis = self.env.simulator.current_analysis
        view, intent, counts = self.view, self.intent, self.counts
        action = action_from_choice(analysis, decision.choice) if decision.well_formed else None
        executed = decision.choice
        invalid = action is None
        if invalid:  # malformed answer or not a valid action: fall back to first fit
            action = select_first_fit_action(self.env.action_masks())
            executed = choice_from_action(analysis, action)
        violation = not is_admissible(view, intent, executed)
        flagged = decision.raw in FLAGS
        binding = not is_admissible(view, intent, teacher_choice(view, NO_INTENT))
        oracle = teacher_choice(view, intent)
        tally = {
            "requests": 1,
            "invalid": invalid,
            "malformed": not decision.well_formed,
            "violations": violation,
            "binding": binding,
            "binding_violations": binding and violation,
            "rejects": executed is None,
            # the two kinds of violation that are about the reject decision itself
            "needless_rejects": violation and executed is None,
            "wrong_accepts": violation and executed is not None and not admissible_paths(view, intent),
            # first-stated preference decides, later ones break ties, preferences never reject
            "ordered_violations": not respects(view, from_intent(intent), executed, "ordered"),
            "flagged": flagged,  # the translator did not apply the instruction and says so
            "silent_violations": violation and not flagged,
            "oracle_exact": decision.well_formed and decision.choice == oracle,
            "oracle_path": (executed[0] if executed else None) == (oracle[0] if oracle else None),
        }
        for counter in (counts, self.by_intent[intent.key]):
            counter.update({key: int(value) for key, value in tally.items()})
        self.seconds += decision.seconds
        if keep_trace:
            self.trace.append({"prompt": render_prompt(view, intent), "answer": decision.raw,
                               "decision": format_choice(decision.choice), "oracle": format_choice(oracle),
                               "valid": action is not None and executed == decision.choice,
                               "violation": violation})  # fmt: skip
        _, _, _, _, self.info = self.env.step(action)
        self.remaining -= 1
        if self.remaining:
            self._prepare()

    def result(self) -> dict:
        snap = self.env.simulator.statistics.snapshot()
        counts, n = self.counts, max(self.counts["requests"], 1)
        return {
            **{k: self.job[k] for k in ("policy", "condition", "load", "seed", "warmup", "window")},
            "processed": int(snap.episode_services_processed),
            "accepted": int(snap.episode_services_accepted),
            "blocked_resources": int(snap.episode_services_blocked_resources),
            "blocked_qot": int(snap.episode_services_blocked_qot),
            "rejected_by_policy": int(snap.episode_services_rejected_by_agent),
            "service_blocking_rate": float(snap.episode_service_blocking_rate),
            "bit_rate_blocking_rate": float(snap.episode_bit_rate_blocking_rate),
            "violations": counts["violations"],
            "violation_rate": counts["violations"] / n,
            "invalid": counts["invalid"],
            "invalid_rate": counts["invalid"] / n,
            "malformed": counts["malformed"],
            "binding": counts["binding"],
            "binding_violations": counts["binding_violations"],
            "needless_rejects": counts["needless_rejects"],
            "wrong_accepts": counts["wrong_accepts"],
            "ordered_violations": counts["ordered_violations"],
            "ordered_violation_rate": counts["ordered_violations"] / n,
            "flagged": counts["flagged"],
            "silent_violations": counts["silent_violations"],
            "by_intent": {
                key: dict(sorted(counter.items())) for key, counter in sorted(self.by_intent.items())
            },
            "oracle_exact_rate": counts["oracle_exact"] / n,
            "oracle_path_rate": counts["oracle_path"] / n,
            "decision_ms": 1000.0 * self.seconds / n,
        }


def run_group(policy: Policy, jobs: list[dict], on_done=None) -> list[dict]:
    """Run the jobs in lockstep so the policy sees one request per environment at a time."""
    episodes = [Episode(job) for job in jobs]
    started = time.perf_counter()
    active = list(episodes)
    decisions = 0
    while active:
        for episode, decision in zip(active, policy.decide([e.request() for e in active]), strict=True):
            episode.apply(decision)
        decisions += len(active)
        active = [e for e in active if e.remaining]
    wall = time.perf_counter() - started
    rows = []
    for episode in episodes:
        row = episode.result() | {"group_decisions_per_s": round(decisions / wall, 2)}
        rows.append(row)
        if on_done:
            on_done(row)
    return rows


def _run_single(job: dict) -> dict:
    return run_group(make_policy(job["policy"]), [job])[0]


def _pool_worker(conn, jobs: list[dict]) -> None:
    """Own some episodes in a separate process: warm them up, then apply decisions as they arrive."""
    episodes = [Episode(job) for job in jobs]
    active = list(range(len(episodes)))
    while True:
        conn.send([(episodes[i].view, episodes[i].intent) for i in active])
        if not active:
            break
        for i, decision in zip(active, conn.recv(), strict=True):
            episodes[i].apply(decision)
        active = [i for i in active if episodes[i].remaining]
    conn.send([episode.result() for episode in episodes])
    conn.close()


def run_pool(policy: Policy, jobs: list[dict], workers: int, on_done=None, on_tick=None) -> list[dict]:
    """Like :func:`run_group`, with the environments stepped in ``workers`` processes.

    For policies that decide from the view and intent alone (the language model). The model is
    still asked once per tick for every active environment, but the simulator work between two
    model calls, and the warm-ups, run in parallel instead of on one core, so a GPU is not kept
    waiting. Results are identical to :func:`run_group`.
    """
    import multiprocessing
    import os

    context = multiprocessing.get_context("spawn")  # the parent may hold a CUDA context
    pipes, processes = [], []
    # Each worker is one simulator on one core: keep its numerical libraries single-threaded.
    thread_vars = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    saved = {name: os.environ.get(name) for name in thread_vars}
    os.environ.update(dict.fromkeys(thread_vars, "1"))
    try:
        for chunk in (jobs[i::workers] for i in range(min(workers, len(jobs)))):
            parent, child = context.Pipe()
            process = context.Process(target=_pool_worker, args=(child, chunk), daemon=True)
            process.start()
            child.close()
            pipes.append(parent)
            processes.append(process)
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    pending = [pipe.recv() for pipe in pipes]  # arrives when the worker's warm-ups are done
    started = time.perf_counter()
    decisions = 0
    while any(pending):
        requests = [Request(view, intent) for batch in pending for view, intent in batch]
        answers = iter(policy.decide(requests))
        for pipe, batch in zip(pipes, pending, strict=True):
            if batch:
                pipe.send([next(answers) for _ in batch])
        decisions += len(requests)
        pending = [pipe.recv() if batch else [] for pipe, batch in zip(pipes, pending, strict=True)]
        if on_tick:
            on_tick()
    wall = time.perf_counter() - started
    rows = []
    for pipe, process in zip(pipes, processes, strict=True):
        for row in pipe.recv():
            row |= {"group_decisions_per_s": round(decisions / wall, 2)}
            rows.append(row)
            if on_done:
                on_done(row)
        process.join()
    return rows


def job_key(row: dict) -> tuple:
    return tuple(row[k] for k in ("policy", "condition", "load", "seed", "warmup", "window"))


def summarise(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["condition"], row["load"])].append(row)
    summary = []
    for (condition, load), group in sorted(groups.items()):
        entry = {"condition": condition, "load": load, "seeds": sorted(r["seed"] for r in group)}
        for metric in METRICS:
            values = [r[metric] for r in group]
            entry[f"{metric}_mean"] = statistics.fmean(values)
            entry[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
        binding = sum(r["binding"] for r in group)
        entry["binding_violation_rate"] = (
            sum(r["binding_violations"] for r in group) / binding if binding else 0.0
        )
        entry["binding_share"] = binding / sum(r["window"] for r in group)
        entry["oracle_path_rate_mean"] = statistics.fmean(r["oracle_path_rate"] for r in group)
        # Counts pooled over the seeds, overall and per intent key (a condition can mix intents).
        pooled: dict[str, Counter] = defaultdict(Counter)
        for row in group:
            for key, counts in row.get("by_intent", {}).items():
                pooled[key].update(counts)
                pooled["all"].update(counts)
        entry["by_intent"] = {key: dict(sorted(counter.items())) for key, counter in sorted(pooled.items())}
        summary.append(entry)
    return summary


def upload_results(repo: str, paths: list[Path]) -> None:
    """Copy result files to a Hub dataset repo, keeping their path below the project root."""
    from huggingface_hub import HfApi

    for path in paths:
        resolved = path.resolve()
        name = (
            resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else f"results/{path.name}"
        )
        HfApi().upload_file(path_or_fileobj=str(path), path_in_repo=name, repo_id=repo, repo_type="dataset")


def closed(args: argparse.Namespace) -> None:
    from calibrate import environment_metadata

    out = (args.out or ROOT / "results" / "eval" / f"{args.policy}.json").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".partial.jsonl")
    jobs = [
        {"policy": args.policy, "condition": c, "load": load, "seed": s, "warmup": args.warmup, "window": args.window}
        for c in args.conditions for load in args.loads for s in args.seeds
    ]  # fmt: skip
    rows = []
    if partial.exists():
        wanted = {job_key(job) for job in jobs}
        rows = [r for r in map(json.loads, partial.read_text().splitlines()) if job_key(r) in wanted]
        rows = [r for r in rows if all(m in r for m in METRICS)]  # a checkpoint of an older version is redone
        done = {job_key(r) for r in rows}
        jobs = [job for job in jobs if job_key(job) not in done]
        print(f"resuming: {len(rows)} episodes in {partial.name}, {len(jobs)} to run", flush=True)
    total = len(rows) + len(jobs)
    policy = make_policy(args.policy, **llm_options(args))
    started = datetime.now(UTC)
    last_sync = time.monotonic()

    def sync(force: bool = False) -> None:
        """Copy the answer cache and the checkpoint to the Hub so a dead job loses nothing."""
        nonlocal last_sync
        if not args.sync_repo or (not force and time.monotonic() - last_sync < args.sync_every):
            return
        last_sync = time.monotonic()
        files = [partial, out, getattr(policy, "cache_path", None)]
        upload_results(args.sync_repo, [p for p in files if p is not None and p.exists()])

    with partial.open("a") as checkpoint:

        def record(row: dict) -> None:
            rows.append(row)
            checkpoint.write(json.dumps(row) + "\n")
            checkpoint.flush()
            print(f"[{len(rows):>3}/{total}] {row['condition']:<26} load={row['load']} seed={row['seed']} "
                  f"SBP={100 * row['service_blocking_rate']:.2f}% viol={100 * row['violation_rate']:.1f}% "
                  f"invalid={100 * row['invalid_rate']:.1f}% {row['decision_ms']:.2f} ms/decision", flush=True)  # fmt: skip

        if policy.parallel_safe and args.workers > 1 and jobs:
            with Pool(min(args.workers, len(jobs))) as pool:
                for row in pool.imap_unordered(_run_single, jobs):
                    record(row)
        else:
            for start in range(0, len(jobs), args.batch_envs):
                group = jobs[start : start + args.batch_envs]
                if args.sim_workers > 1 and not policy.parallel_safe:
                    run_pool(policy, group, args.sim_workers, on_done=record, on_tick=sync)
                else:
                    run_group(policy, group, on_done=record)
                sync(force=True)

    rows.sort(key=job_key)
    result = {
        "metadata": {
            "run_id": started.strftime("%Y%m%dT%H%M%SZ"),
            "finished_utc": datetime.now(UTC).isoformat(),
            "command": " ".join(sys.argv),
            "policy": policy.describe(),
            "protocol": {"warmup": args.warmup, "window": args.window, "warmup_policy": "jocn_ls_bm_ksp",
                         "invalid_fallback": "first_fit"},
            "conditions": args.conditions, "loads": args.loads, "seeds": args.seeds,
            **environment_metadata(),
        },
        "summary": summarise(rows),
        "episodes": rows,
    }  # fmt: skip
    out.write_text(json.dumps(result, indent=2) + "\n")
    sync(force=True)
    partial.unlink(missing_ok=True)
    print(f"wrote {out}")


def offline(args: argparse.Namespace) -> None:
    """Agreement with the teacher on the held-out splits (no simulator).

    With ``--predictions`` the answers are read from a file of ``{"id", "answer"}`` lines (what
    ``train.py`` writes for the fine-tuned model) instead of asking a policy.
    """
    answers, policy = None, None
    if args.predictions:
        lines = args.predictions.read_text(encoding="utf-8").splitlines()
        answers = {row["id"]: row["answer"] for row in map(json.loads, filter(None, lines))}
        described = {"name": args.policy, "predictions": args.predictions.name}
    else:
        policy = make_policy(args.policy, **llm_options(args))
        described = policy.describe()
    result = {"metadata": {"policy": described, "command": " ".join(sys.argv),
                           "finished_utc": datetime.now(UTC).isoformat()}, "splits": {}}  # fmt: skip
    for split in args.splits:
        path = args.data / f"{split}.jsonl"
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.limit:
            records = records[: args.limit]
        requests = [
            Request(RequestView.from_json(r["meta"]["view"]), Intent.from_json(r["meta"]["intent"]))
            for r in records
        ]
        decisions = []
        if answers is not None:
            for record in records:
                well_formed, choice = parse_answer(answers[record["id"]])
                decisions.append(Decision(choice, well_formed, answers[record["id"]]))
        for start in range(0, len(requests) if policy else 0, args.batch_envs):
            decisions += policy.decide(requests[start : start + args.batch_envs])
        # Probe instructions that should not be applied: what does the policy decide without one?
        plain: dict[str, Decision] = {}
        inapplicable = [r for r in records if not r["meta"].get("probe", {}).get("apply", True)]
        for start in range(0, len(inapplicable) if policy else 0, args.batch_envs):
            chunk = inapplicable[start : start + args.batch_envs]
            bare = [Request(RequestView.from_json(r["meta"]["view"]), NO_INTENT) for r in chunk]
            plain.update(zip((r["id"] for r in chunk), policy.decide(bare), strict=True))
        per_intent: dict[str, Counter] = defaultdict(Counter)
        for record, request, decision in zip(records, requests, decisions, strict=True):
            teacher = tuple(record["meta"]["teacher_choice"]) if record["meta"]["teacher_choice"] else None
            choice = decision.choice
            # Offline a start is valid when it lies in a listed block of a feasible path.
            valid = decision.well_formed and (
                choice is None
                or (choice[0] < len(request.view.paths) and request.view.paths[choice[0]].in_block(choice[1]))
            )
            for key in (record["meta"]["intent_key"], "all"):
                counter = per_intent[key]
                counter["n"] += 1
                counter["malformed"] += not decision.well_formed
                counter["invalid"] += not valid
                counter["exact"] += decision.well_formed and choice == teacher
                # A probe of an instruction type outside intents.py lists the paths that comply itself
                # (an empty list: the request must be rejected).
                allowed = record["meta"].get("probe", {}).get("allowed")
                if allowed is None:
                    respected = is_admissible(request.view, request.intent, choice)
                else:
                    respected = (choice[0] in allowed) if choice else not allowed
                counter["admissible"] += valid and respected
                counter["forwarded"] += decision.raw is not None and decision.raw.startswith("decider:")
                meant = (
                    Spec.from_json(record["meta"]["spec"])
                    if "spec" in record["meta"]
                    else from_intent(request.intent)
                )
                counter["ordered"] += valid and respects(
                    request.view, meant if meant.applies else EMPTY, choice, "ordered"
                )
                counter["flagged"] += decision.raw in FLAGS
                if record["id"] in plain:
                    counter["inapplicable"] += 1
                    counter["unchanged"] += decision.well_formed and choice == plain[record["id"]].choice
                    counter["rejects"] += decision.well_formed and choice is None
        result["splits"][split] = {
            key: {"n": c["n"], "exact_match": c["exact"] / c["n"], "admissible": c["admissible"] / c["n"],
                  "admissible_ordered": c["ordered"] / c["n"], "flagged": c["flagged"] / c["n"],
                  "forwarded_to_decider": c["forwarded"] / c["n"],
                  "invalid": c["invalid"] / c["n"], "malformed": c["malformed"] / c["n"]}
            | ({"unchanged_without_instruction": c["unchanged"] / c["inapplicable"],
                "rejects": c["rejects"] / c["inapplicable"]} if c["inapplicable"] else {})
            for key, c in sorted(per_intent.items())
        }  # fmt: skip
        overall = result["splits"][split]["all"]
        print(f"{split:20s} n={overall['n']:5d} exact={100 * overall['exact_match']:.1f}% "
              f"admissible={100 * overall['admissible']:.1f}% invalid={100 * overall['invalid']:.1f}%")  # fmt: skip
    out = (args.out or ROOT / "results" / "offline" / f"{args.policy}.json").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {out}")
    if args.sync_repo:
        cache = getattr(policy, "cache_path", None)
        upload_results(args.sync_repo, [out] + ([cache] if cache is not None and cache.exists() else []))


def demo(args: argparse.Namespace) -> None:
    """A short live episode that shows requests flowing prompt -> answer -> simulator."""
    policy = make_policy(args.policy, **llm_options(args))
    job = {"policy": args.policy, "condition": args.conditions[0], "load": args.loads[0], "seed": args.seeds[0],
           "warmup": args.warmup, "window": args.window}  # fmt: skip
    episode = Episode(job)
    while episode.remaining:
        (decision,) = policy.decide([episode.request()])
        episode.apply(decision, keep_trace=True)
    for step in episode.trace[: args.show]:
        print(step["prompt"])
        print(f"--> {args.policy}: {step['answer'] or step['decision']}   (teacher: {step['oracle']}; "
              f"{'valid' if step['valid'] else 'INVALID'}; {'VIOLATES intent' if step['violation'] else 'intent respected'})\n")  # fmt: skip
    row = episode.result()
    print(f"{args.policy} on {row['window']} requests ({job['condition']}, load {job['load']}): "
          f"blocking {100 * row['service_blocking_rate']:.1f}%, intent violations {100 * row['violation_rate']:.1f}%, "
          f"invalid answers {100 * row['invalid_rate']:.1f}%, {row['decision_ms']:.1f} ms per decision")  # fmt: skip


def llm_options(args: argparse.Namespace) -> dict:
    if args.policy in ("first_fit", "teacher", "oracle", "mlp"):
        return {}
    local = {"model": args.model, "adapter": args.adapter,
             "structured": "none" if args.structured == "none" else "regex",
             "template_kwargs": json.loads(args.template_kwargs), "max_batch": args.batch_envs}  # fmt: skip
    if args.policy.startswith(("translate", "hybrid")):
        return local | {"topology": args.topology}
    if args.backend == "transformers":
        shots = []
        for line in args.shots.read_text(encoding="utf-8").splitlines() if args.shots else []:
            record = json.loads(line)
            shots += [record["prompt"][-1], record["completion"][0]]
        return local | {"backend": "transformers", "shots": shots}
    return {"backend": "endpoint", "base_url": args.base_url, "model": args.model, "structured": args.structured,
            "extra_body": json.loads(args.extra_body), "concurrency": args.concurrency}  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["closed", "offline", "demo"])
    parser.add_argument(
        "--policy", required=True, help="first_fit, teacher, oracle, mlp, or a name for an LLM run"
    )
    parser.add_argument("--conditions", nargs="+", default=None, choices=CONDITIONS)
    parser.add_argument("--loads", type=int, nargs="+", default=list(EVAL_LOADS))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(EVAL_SEEDS))
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--window", type=int, default=None)
    parser.add_argument("--workers", type=int, default=2, help="processes for CPU policies")
    parser.add_argument("--batch-envs", type=int, default=42, help="environments queried together (LLM)")
    parser.add_argument("--out", type=Path, default=None)
    # offline
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "full")
    parser.add_argument("--splits", nargs="+", default=list(HELDOUT_SPLITS))
    parser.add_argument("--limit", type=int, default=0, help="offline: only the first N records per split")
    parser.add_argument("--predictions", type=Path, help="offline: score answers from this JSONL file")
    # demo
    parser.add_argument("--show", type=int, default=3, help="demo: exchanges to print")
    # language model: an endpoint (defaults from LLM_BASE_URL, LLM_NAME, LLM_API_KEY) or in this process
    parser.add_argument("--backend", choices=["endpoint", "transformers"], default="endpoint")
    parser.add_argument("--adapter", default=None, help="transformers backend: LoRA adapter to merge")
    parser.add_argument("--template-kwargs", default="{}", help="transformers backend: chat-template JSON")
    parser.add_argument(
        "--shots", type=Path, help="transformers backend: solved records put before every prompt"
    )
    parser.add_argument(
        "--topology", default="nobel-eu", help="translate_* policies: topology of the node list"
    )
    parser.add_argument(
        "--sim-workers", type=int, default=1, help="processes stepping the environments (LLM)"
    )
    parser.add_argument("--sync-repo", default=None, help="Hub dataset repo to copy cache and results to")
    parser.add_argument("--sync-every", type=float, default=300.0, help="seconds between copies")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--structured", choices=["structured_outputs", "guided_regex", "none"],
                        default="structured_outputs")  # fmt: skip
    parser.add_argument("--extra-body", default="{}", help="JSON merged into each chat request")
    parser.add_argument("--concurrency", type=int, default=32)
    args = parser.parse_args()

    demo_mode = args.mode == "demo"
    args.conditions = args.conditions or (["mixed_heldout_paraphrases"] if demo_mode else list(CONDITIONS))
    args.warmup = args.warmup if args.warmup is not None else (300 if demo_mode else WARMUP)
    args.window = args.window if args.window is not None else (50 if demo_mode else WINDOW)
    {"closed": closed, "offline": offline, "demo": demo}[args.mode](args)


if __name__ == "__main__":
    main()
