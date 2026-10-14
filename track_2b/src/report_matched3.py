"""The matched decider and the full-format reader in one summary (``results/design/matched3.json``).

Reads the result files of the two experiments of 14 October 2026 and of the runs they are compared
with, and writes per policy: decisions that comply on the stored probes by number of clauses and by
language, and closed-loop violations and rejections on the mixed condition by class of instruction.

    uv run python src/report_matched3.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CLASSES = {
    "inside the language": ("atom", "pair", "heldout_pair", "triple", "two_preferences"),
    "carried in part": ("partial",),
    "types never shown": ("not_first", "min_mod", "min_free", "largest_block"),
    "nothing to apply": ("I0", "not_instruction", "faulty"),
}
PROBE_FILES = {
    "routing-field reader + engine": ["offline/translate3_ft_probes3.json"],
    "full-format reader + engine": ["offline/translate4_ft_probes3.json"],
    "first decider (four types)": ["offline/apertus_ft_probes3.json", "offline/apertus_ft_probes3_langs.json"],
    "matched decider": ["offline/apertus3_ft_probes3.json"],
}
CLOSED = {
    "first fit": "eval/first_fit_mix3.json",
    "first decider (four types)": "eval/apertus_ft_mix3.json",
    "matched decider": "eval/apertus3_ft_mix3.json",
    "routing-field reader + engine": "eval/translate3_ft_mix3.json",
    "full-format reader + engine": "eval/translate4_ft_mix3.json",
    "hybrid: routing-field reader, first decider": "eval/hybrid3_ft_mix3.json",
    "hybrid: full-format reader, first decider": "eval/hybrid4_ft_mix3.json",
    "hybrid: full-format reader, matched decider": "eval/hybrid4_ft_d3_mix3.json",
}


def load(path: str) -> dict | None:
    file = RESULTS / path
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else None


def probes() -> dict:
    out = {}
    for policy, files in PROBE_FILES.items():
        splits = {}
        for file in files:
            data = load(file)
            if data:
                splits |= data["splits"]
        if not splits:
            continue
        row = {}
        for lang in ("en", "de", "fr", "it"):
            split = splits.get(f"v3_{lang}")
            if split:
                row[lang] = {key: {"n": v["n"], "comply_pct": round(100 * v["admissible_ordered"], 1)}
                             for key, v in split.items() if key in ("all", "atom", "pair", "heldout_pair", "triple", "two_preferences")}  # fmt: skip
        for name in ("v3_new", "v3_new_hard", "v3_new_impossible", "v3_partial"):
            if name in splits:
                # outside the language the probe's own list of complying paths decides ("admissible")
                row[name] = {"n": splits[name]["all"]["n"], "comply_pct": round(100 * splits[name]["all"]["admissible"], 1)}
        out[policy] = row
    return out


def closed() -> dict:
    out = {}
    for policy, file in CLOSED.items():
        data = load(file)
        if not data:
            continue
        row = {}
        for load_ in (240, 390):
            episodes = sorted((e for e in data["episodes"] if e["load"] == load_), key=lambda e: e["seed"])
            if not episodes:
                continue
            entry = {"violations_pct": round(100 * statistics.mean(e["violation_rate"] for e in episodes), 2),
                     "rejected_pct": round(100 * statistics.mean(e["service_blocking_rate"] for e in episodes), 2),
                     "seeds": [e["seed"] for e in episodes]}  # fmt: skip
            for name, keys in CLASSES.items():
                n = sum(e["by_intent"].get(k, {}).get("requests", 0) for e in episodes for k in keys)
                v = sum(e["by_intent"].get(k, {}).get("violations", 0) for e in episodes for k in keys)
                entry[name] = round(100 * v / n, 2) if n else None
            forwarded = sum(c.get("forwarded", 0) for e in episodes for c in e["by_intent"].values())
            entry["forwarded_to_decider_pct"] = round(100 * forwarded / sum(e["processed"] for e in episodes), 2)
            row[str(load_)] = entry
        out[policy] = row | {"file": file}
    return out


def main() -> None:
    held = {name: load(f"offline/{file}.json") for name, file in (
        ("matched decider, epoch 1", "decider3_e1_heldout"), ("matched decider, epoch 2", "decider3_e2_heldout"),
        ("routing-field reader + engine", "translate3_ft_heldout_full3"))}  # fmt: skip
    summary = {
        "heldout_decisions": {name: {s: round(100 * v["all"]["admissible_ordered"], 1) for s, v in d["splits"].items()}
                              for name, d in held.items() if d},  # fmt: skip
        "probes": probes(),
        "mixed_condition": closed(),
        "note": "probes: decisions that comply, ordered preferences; outside the language the probe's own "
                "list of complying paths. Mixed condition: three seeds per load; classes as in the paper.",
    }
    out = RESULTS / "design" / "matched3.json"
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary["heldout_decisions"], indent=1))
    for policy, row in summary["mixed_condition"].items():
        r = row.get("390", {})
        print(f"{policy:46s} 390 E: all {r.get('violations_pct')}  in {r.get('inside the language')}  part {r.get('carried in part')}  "
              f"never {r.get('types never shown')}  rejected {r.get('rejected_pct')}  to decider {r.get('forwarded_to_decider_pct')}")
    print("wrote", out)


if __name__ == "__main__":
    main()
