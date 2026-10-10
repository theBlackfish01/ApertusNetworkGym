"""Dataset generation (SPEC section 5): intent-aware teacher episodes -> prompt/completion records.

Stage 1, episodes. For every load and seed one 1,000-request episode is driven by the
intent-aware teacher: each request gets a random intent, the teacher decides inside its
admissible set, and requests after the first 300 (warm-up) are recorded. Each episode is written
to ``data/full/episodes/`` as soon as it finishes, so an interrupted run resumes.

Stage 2, splits. Records are sampled into the four splits with the sizes of the spec:

    train               12,000  I0 4,000; I1-I4 1,500 each; I1+I2 and I1+I3 1,000 each
    heldout_indist       1,000  same intents and wording as train, unseen episodes
    heldout_paraphrase     600  I1-I4 with the three held-out paraphrases
    heldout_pairs          600  I1+I4 and I2+I3, never seen in training

Training and held-out records come from different seeds, and none of the generation seeds
(101-108) is an evaluation seed (1-3), so no evaluated traffic is ever trained on.

Stage 3, checks. No prompt appears in two splits; every teacher answer is a valid action and
inside its admissible set; per-intent path distribution, reject rate and prompt length are
written to ``data/stats.json``. A small sample of every split is copied to ``data/sample/``.

    uv run python src/generate.py                 # all stages, 2 workers
    uv run python src/generate.py --stage splits  # rebuild splits and checks from the episodes

Record format (JSON lines), a prompt/completion chat dataset:

    {"id": "L270-S103-R0457",
     "prompt": [{"role": "system", ...}, {"role": "user", ...}],
     "completion": [{"role": "assistant", "content": "path=1 slot=120"}],
     "meta": {"group", "load", "seed", "request_index", "intent_key", "intent", "admissible_paths",
              "teacher_choice", "no_intent_choice", "valid_actions", "view"}}
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from intents import (
    HELDOUT_PAIRS,
    NO_INTENT,
    SINGLES,
    Intent,
    admissible_paths,
    ids_from_key,
    is_admissible,
    sample_intent,
    teacher_choice,
)
from prompt import chat_messages, format_choice
from view import RequestView

ROOT = Path(__file__).resolve().parents[1]
LOADS = (150, 210, 270, 330, 390)
TRAIN_SEEDS = (101, 102, 103, 104, 105, 106)
HELDOUT_SEEDS = (107, 108)
REQUESTS = 1_000
WARMUP = 300
TRAIN_COUNTS = {
    "I0": 4_000,
    "I1": 1_500,
    "I2": 1_500,
    "I3": 1_500,
    "I4": 1_500,
    "I1+I2": 1_000,
    "I1+I3": 1_000,
}
HELDOUT_COUNTS = {"heldout_indist": 1_000, "heldout_paraphrase": 600, "heldout_pairs": 600}
SAMPLE_SIZE = 50  # records per split copied to data/sample/


def sample_kind(rng: random.Random, heldout_seed: bool) -> tuple[str, tuple[str, ...], bool]:
    """``(group, intent ids, use held-out paraphrases)`` for one request."""
    group = "train"
    if heldout_seed:
        group = rng.choices(list(HELDOUT_COUNTS), weights=list(HELDOUT_COUNTS.values()))[0]
    if group == "heldout_paraphrase":
        return group, (rng.choice(SINGLES),), True
    if group == "heldout_pairs":
        return group, rng.choice(HELDOUT_PAIRS), False
    key = rng.choices(list(TRAIN_COUNTS), weights=list(TRAIN_COUNTS.values()))[0]
    return group, ids_from_key(key), False


def run_episode(job: tuple[int, int, str]) -> str:
    """Generate one episode file (skipped when it already exists); returns its path."""
    from sim import action_from_choice, build_env, view_from_analysis  # ONG is only needed here

    load, seed, out_dir = job
    path = Path(out_dir) / f"L{load}-S{seed}.jsonl"
    if path.exists():
        return str(path)

    rng = random.Random(f"generate-{load}-{seed}")
    env = build_env(load, seed, episode_length=REQUESTS)
    env.reset(seed=seed)
    lines = []
    for index in range(REQUESTS):
        analysis = env.simulator.current_analysis
        view = view_from_analysis(analysis)
        group, ids, heldout = sample_kind(rng, seed in HELDOUT_SEEDS)
        intent = sample_intent(view, ids, rng, heldout=heldout)
        choice = teacher_choice(view, intent)
        action = action_from_choice(analysis, choice)
        mask = env.action_masks()
        if action is None or (choice is not None and not mask[action]):
            raise RuntimeError(
                f"teacher produced an invalid action at load {load} seed {seed} request {index}"
            )
        if index >= WARMUP:
            none_choice = teacher_choice(view, NO_INTENT)
            record = {
                "id": f"L{load}-S{seed}-R{index:04d}",
                "prompt": chat_messages(view, intent),
                "completion": [{"role": "assistant", "content": format_choice(choice)}],
                "meta": {
                    "group": group,
                    "load": load,
                    "seed": seed,
                    "request_index": index,
                    "intent_key": intent.key,
                    "intent": intent.to_json(),
                    "admissible_paths": list(admissible_paths(view, intent)),
                    "teacher_choice": list(choice) if choice else None,
                    "no_intent_choice": list(none_choice) if none_choice else None,
                    "valid_actions": int(mask[:-1].sum()),
                    "view": view.to_json(),
                },
            }
            lines.append(json.dumps(record, ensure_ascii=False))
        env.step(action)

    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.rename(path)
    return str(path)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def user_text(record: dict) -> str:
    return record["prompt"][-1]["content"]


def build_splits(episodes_dir: Path) -> dict[str, list[dict]]:
    """Sample the episode records into the four splits (deterministic).

    A prompt can repeat when a blocked request is followed by an identical one (the network
    state has not changed). Only its first occurrence is kept, training episodes first, so no
    prompt appears twice anywhere.

    Prompts are rendered again from the stored view and intent, so the splits always match the
    current ``prompt.py`` without re-running the simulator.
    """
    records = [r for path in sorted(episodes_dir.glob("L*-S*.jsonl")) for r in read_jsonl(path)]
    records.sort(key=lambda r: (r["meta"]["group"] != "train", r["id"]))
    by_bucket: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for record in records:
        meta = record["meta"]
        record["prompt"] = chat_messages(
            RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"])
        )
        text = user_text(record)
        if text in seen:
            continue
        seen.add(text)
        meta = record["meta"]
        bucket = meta["intent_key"] if meta["group"] == "train" else "*"
        by_bucket[(meta["group"], bucket)].append(record)

    rng = random.Random("splits")
    splits: dict[str, list[dict]] = {"train": []}
    for key, count in TRAIN_COUNTS.items():
        pool = by_bucket[("train", key)]
        if len(pool) < count:
            raise RuntimeError(f"only {len(pool)} train records for {key}, need {count}")
        splits["train"] += rng.sample(pool, count)
    for group, count in HELDOUT_COUNTS.items():
        pool = by_bucket[(group, "*")]
        if len(pool) < count:
            raise RuntimeError(f"only {len(pool)} records for {group}, need {count}")
        splits[group] = rng.sample(pool, count)
    for records in splits.values():
        records.sort(key=lambda r: r["id"])
    return splits


def check_splits(splits: dict[str, list[dict]]) -> dict:
    """Sanity checks of SPEC section 5; raises on a violation, returns the statistics."""
    seen: dict[str, str] = {}
    for name, records in splits.items():
        for record in records:
            text = user_text(record)
            if text in seen:
                raise AssertionError(f"prompt of {record['id']} ({name}) also appears in {seen[text]}")
            seen[text] = name

    stats: dict = {"splits": {}}
    for name, records in splits.items():
        per_intent: dict[str, Counter] = defaultdict(Counter)
        lengths = []
        for record in records:
            meta = record["meta"]
            view = RequestView.from_json(meta["view"])
            intent = Intent.from_json(meta["intent"])
            choice = tuple(meta["teacher_choice"]) if meta["teacher_choice"] else None
            if not is_admissible(view, intent, choice):
                raise AssertionError(f"{record['id']}: teacher answer outside its admissible set")
            if record["completion"][0]["content"] != format_choice(choice):
                raise AssertionError(f"{record['id']}: completion does not match the teacher choice")
            if choice is not None and choice[1] != view.paths[choice[0]].first_slot:
                raise AssertionError(f"{record['id']}: teacher slot is not the first listed block")
            none_choice = meta["no_intent_choice"]
            counter = per_intent[meta["intent_key"]]
            counter["n"] += 1
            counter["reject" if choice is None else f"path{choice[0]}"] += 1
            counter["differs_from_no_intent"] += (choice[0] if choice else None) != (
                none_choice[0] if none_choice else None
            )
            counter["no_admissible_path"] += not meta["admissible_paths"]
            lengths.append(len(user_text(record)))
        stats["splits"][name] = {
            "records": len(records),
            "loads": dict(sorted(Counter(r["meta"]["load"] for r in records).items())),
            "seeds": sorted({r["meta"]["seed"] for r in records}),
            "prompt_chars": {
                "mean": round(statistics.fmean(lengths), 1),
                "max": max(lengths),
            },
            "by_intent": {key: dict(sorted(counter.items())) for key, counter in sorted(per_intent.items())},
        }
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--stage", choices=["all", "episodes", "splits"], default="all")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    args = parser.parse_args()

    episodes_dir = args.data / "full" / "episodes"
    if args.stage in ("all", "episodes"):
        episodes_dir.mkdir(parents=True, exist_ok=True)
        jobs = [(load, seed, str(episodes_dir)) for load in LOADS for seed in TRAIN_SEEDS + HELDOUT_SEEDS]
        with Pool(min(args.workers, len(jobs))) as pool:
            for done, path in enumerate(pool.imap_unordered(run_episode, jobs), start=1):
                print(f"[{done:>2}/{len(jobs)}] {Path(path).name}", flush=True)

    if args.stage in ("all", "splits"):
        splits = build_splits(episodes_dir)
        stats = check_splits(splits)
        for name, records in splits.items():
            write_jsonl(args.data / "full" / f"{name}.jsonl", records)
            write_jsonl(args.data / "sample" / f"{name}.jsonl", records[:SAMPLE_SIZE])
        (args.data / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
        for name, split in stats["splits"].items():
            print(f"\n{name}: {split['records']} records, prompt chars mean {split['prompt_chars']['mean']} "
                  f"max {split['prompt_chars']['max']}, loads {split['loads']}")  # fmt: skip
            for key, counter in split["by_intent"].items():
                n = counter["n"]
                paths = " ".join(f"p{i}={counter.get(f'path{i}', 0)}" for i in range(5))
                print(f"  {key:6s} n={n:5d}  {paths}  reject={counter.get('reject', 0)}  "
                      f"differs from no-intent={100 * counter['differs_from_no_intent'] / n:.0f}%")  # fmt: skip
        print(
            f"\nchecks passed; wrote splits to {args.data / 'full'} and stats to {args.data / 'stats.json'}"
        )


if __name__ == "__main__":
    main()
