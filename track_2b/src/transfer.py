"""A probe on a topology no model of this project has seen (needs the simulator).

Everything trained here saw nobel-eu only: 28 nodes, 41 links, the same city names in every
prompt. This script builds held-out-style records on another topology shipped with ONG (default
germany50: 50 nodes, 88 links), with the ``jocn_benchmark`` preset otherwise unchanged, the
intent-aware teacher of ``intents.py`` driving the episodes, and the dataset's English wording.
A decider that learnt a procedure should carry over; one that memorised nobel-eu should not.

    uv run python src/transfer.py --calibrate          # teacher blocking at a few loads
    uv run python src/transfer.py                      # writes the files below

    data/topologies/<id>.json      nodes and links (for the translator's node list and validation)
    data/probes/<id>.jsonl         records in the dataset format, groups as in the held-out splits
    data/instructions/<id>.jsonl   their distinct instructions with the spec they mean

Score with ``evaluate.py offline --data data/probes --splits <id>`` (``--topology <id>`` for a
translator). These records are test data only.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from generate import HELDOUT_COUNTS, sample_kind, write_jsonl
from intents import NO_INTENT, admissible_paths, sample_intent, teacher_choice
from prompt import chat_messages, format_choice
from spec import from_intent

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (201, 202)  # not a training, held-out or evaluation seed of the nobel-eu data
REQUESTS, WARMUP = 1_500, 700
PER_GROUP = 400  # records per group (in-distribution wording, held-out wording, held-out pairs)


def export_topology(topology: str) -> dict:
    from optical_networking_gym.defaults import resolve_topology, set_topology_dir
    from optical_networking_gym.network.topology import TopologyModel

    from sim import SCENARIO, build_scenario

    config = build_scenario(SCENARIO, topology_id=topology)
    if config.topology_dir is not None:
        set_topology_dir(config.topology_dir)
    model = TopologyModel.from_file(
        resolve_topology(topology), topology_id=topology, k_paths=config.k_paths,
        max_span_length_km=config.max_span_length_km,
        default_attenuation_db_per_km=config.default_attenuation_db_per_km,
        default_noise_figure_db=config.default_noise_figure_db,
    )  # fmt: skip
    links = sorted(
        {
            tuple(sorted(pair))
            for path in model.paths
            for pair in zip(path.node_names, path.node_names[1:], strict=False)
        }
    )
    nodes = sorted({name for link in links for name in link})
    return {"id": topology, "nodes": nodes, "links": [list(link) for link in links]}


def episode(job: tuple[str, int, int, bool]) -> tuple[float, list[dict]]:
    """One teacher-driven episode; returns the service blocking rate and the records after warm-up."""
    from sim import action_from_choice, build_env, view_from_analysis

    topology, load, seed, with_intents = job
    rng = random.Random(f"transfer-{topology}-{load}-{seed}")
    env = build_env(load, seed, episode_length=REQUESTS, topology=topology)
    env.reset(seed=seed)
    records = []
    for index in range(REQUESTS):
        analysis = env.simulator.current_analysis
        view = view_from_analysis(analysis)
        group, ids, heldout = sample_kind(rng, True) if with_intents else ("calibration", (), False)
        intent = sample_intent(view, ids, rng, heldout=heldout)
        choice = teacher_choice(view, intent)
        action = action_from_choice(analysis, choice)
        if action is None:
            raise RuntimeError(
                f"teacher produced an invalid action at load {load} seed {seed} request {index}"
            )
        if index >= WARMUP and with_intents:
            plain = teacher_choice(view, NO_INTENT)
            records.append({
                "id": f"{topology}-L{load}-S{seed}-R{index:04d}",
                "prompt": chat_messages(view, intent),
                "completion": [{"role": "assistant", "content": format_choice(choice)}],
                "meta": {
                    "group": group, "load": load, "seed": seed, "request_index": index,
                    "intent_key": intent.key, "intent": intent.to_json(),
                    "admissible_paths": list(admissible_paths(view, intent)),
                    "teacher_choice": list(choice) if choice else None,
                    "no_intent_choice": list(plain) if plain else None,
                    "view": view.to_json(), "spec": from_intent(intent).to_json(),
                    "probe": {"set": topology, "lang": "en", "apply": True, "source_group": group},
                },
            })  # fmt: skip
        env.step(action)
    snapshot = env.simulator.statistics.snapshot()
    return float(snapshot.episode_service_blocking_rate), records


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--topology", default="germany50")
    parser.add_argument("--loads", type=int, nargs="+", default=None)
    parser.add_argument("--calibrate", action="store_true", help="only print the teacher's blocking per load")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    data = ROOT / "data"
    exported = export_topology(args.topology)
    (data / "topologies").mkdir(parents=True, exist_ok=True)
    (data / "topologies" / f"{args.topology}.json").write_text(
        json.dumps(exported, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{args.topology}: {len(exported['nodes'])} nodes, {len(exported['links'])} links")
    if args.calibrate:
        loads = args.loads or [200, 400, 600, 800]
        with Pool(args.workers) as pool:
            rates = pool.map(episode, [(args.topology, load, SEEDS[0], False) for load in loads])
        for load, (rate, _) in zip(loads, rates, strict=True):
            print(f"  load {load}: no-intent teacher blocks {100 * rate:.2f}% of {REQUESTS} requests")
        return
    if not args.loads:
        raise SystemExit("give --loads (see --calibrate)")
    jobs = [(args.topology, load, seed, True) for load in args.loads for seed in SEEDS]
    with Pool(args.workers) as pool:
        results = pool.map(episode, jobs)
    for job, (rate, records) in zip(jobs, results, strict=True):
        print(f"  load {job[1]} seed {job[2]}: blocking {100 * rate:.2f}%, {len(records)} records")
    pools: dict[str, list[dict]] = {group: [] for group in HELDOUT_COUNTS}
    seen: set[str] = set()
    for _, records in results:
        for record in records:
            text = record["prompt"][-1]["content"]
            if text not in seen:
                seen.add(text)
                pools[record["meta"]["group"]].append(record)
    rng = random.Random(f"transfer-sample-{args.topology}")
    chosen = sorted(
        (r for pool in pools.values() for r in rng.sample(pool, PER_GROUP)), key=lambda r: r["id"]
    )
    write_jsonl(data / "probes" / f"{args.topology}.jsonl", chosen)
    rows = {}
    for record in chosen:
        meta = record["meta"]
        if meta["intent"]["ids"]:
            rows.setdefault(meta["intent"]["text"], {"text": meta["intent"]["text"], "expect": meta["spec"],
                                                     "set": args.topology, "lang": "en", "kind": meta["intent_key"]})  # fmt: skip
    write_jsonl(data / "instructions" / f"{args.topology}.jsonl", [rows[t] for t in sorted(rows)])
    kinds = Counter(f"{r['meta']['group']}/{r['meta']['intent_key']}" for r in chosen)
    print(f"wrote {len(chosen)} records, {len(rows)} distinct instructions: {dict(sorted(kinds.items()))}")


if __name__ == "__main__":
    main()
