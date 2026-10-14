"""Why a decider complies far less in closed loop than on the stored probes (``results/design/decider_gap.json``).

The matched decider complies with 96.4 % of the English probes but breaks 14.1 % of the mixed
condition's in-language requests at 390 Erlang; the reader with the rule engine is at 99.6 % and
0.9 %. This replays the mixed condition from the answer caches (no model is loaded; a missing
answer stops the run), checks that every episode reproduces its stored result, and classifies each
request carrying an instruction in the policy language by what the instruction allows on it:

* ``restrictive``: some feasible path complies and some does not, the only case the probes
  contain (``corpora3_tests`` places every probe so);
* ``every feasible path complies``: the instruction changes nothing on this request;
* ``only a reject complies``: there are feasible paths but none complies, either because no
  candidate meets the constraints (``by the candidates``) or because those that meet them have no
  room (``by the spectrum``); the stream draws its instructions without regard to this
  (``mixed3.instance`` with ``meetable=None``);
* ``nothing feasible``: the request is blocked whatever is decided.

    uv run python src/analyse_decider_gap.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import mixed3
from corpora3 import NEW_TYPES
from evaluate import Episode, make_policy, run_group
from intents import NO_INTENT, teacher_choice
from spec import meets

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "design" / "decider_gap.json"
POLICIES = {  # results/eval/<file>.json -> (how to rebuild the policy, label)
    "apertus3_ft_mix3": (lambda: make_policy("apertus3_ft_mix3", backend="transformers"), "matched decider"),
    "apertus_ft_mix3": (lambda: make_policy("apertus_ft_mix3", backend="transformers"), "first decider"),
    "translate3_ft_mix3": (lambda: make_policy("translate3_ft", topology="nobel-eu"), "routing-field reader + rule engine"),
    "first_fit_mix3": (lambda: make_policy("first_fit"), "first fit"),
}  # fmt: skip
CASES = ("restrictive", "every feasible path complies", "only a reject complies", "nothing feasible")


def case_of(view, instruction) -> tuple[str, str]:
    feasible = [p.index for p in view.paths if p.feasible]
    allowed = mixed3.allowed(view, instruction)
    if not feasible:
        return "nothing feasible", ""
    if not allowed:
        spec, fills = mixed3.expressed(instruction), instruction.values
        rules = [k for k in instruction.clauses if k in NEW_TYPES and k not in mixed3.NEW_PREFERENCES]
        meeting = [p for p in view.paths if meets(p, spec) and all(mixed3._new_rule(p, k, fills) for k in rules)]
        return "only a reject complies", "by the spectrum" if meeting else "by the candidates"
    return ("every feasible path complies" if len(allowed) == len(feasible) else "restrictive"), ""


def replay(file: str) -> tuple[list[dict], list[dict]]:
    build, _ = POLICIES[file]
    stored = json.loads((RESULTS / "eval" / f"{file}.json").read_text(encoding="utf-8"))
    jobs = [{"policy": file, "condition": e["condition"], "load": e["load"], "seed": e["seed"], "warmup": e["warmup"],
             "window": e["window"], "topology": "nobel-eu"} for e in stored["episodes"]]  # fmt: skip
    records: list[dict] = []
    original = Episode.apply

    def apply(self, decision, *, keep_trace=False):
        view, instruction = self.view, self.intent
        if getattr(instruction, "kind", "") == "supported":
            case, why = case_of(view, instruction)
            before = Counter(self.counts)
            original(self, decision, keep_trace=keep_trace)
            delta = Counter(self.counts)
            delta.subtract(before)
            executed = decision.choice if not delta["invalid"] else None
            records.append({
                "load": self.job["load"], "seed": self.job["seed"], "case": case, "why": why,
                "lang": instruction.lang, "group": instruction.group, "violation": bool(delta["violations"]),
                "rejected": bool(delta["rejects"]), "invalid": bool(delta["invalid"]),
                "as_without_instruction": executed is not None and executed == teacher_choice(view, NO_INTENT),
            })  # fmt: skip
        else:
            original(self, decision, keep_trace=keep_trace)

    Episode.apply = apply
    try:
        rows = run_group(build(), jobs)
    finally:
        Episode.apply = original
    by_key = {(e["load"], e["seed"]): e for e in stored["episodes"]}
    for row in rows:  # the replay must be the run that was scored
        old = by_key[(row["load"], row["seed"])]
        for field in ("violations", "processed", "accepted", "rejected_by_policy"):
            assert row[field] == old[field], (file, row["load"], row["seed"], field, row[field], old[field])
    return records, rows


def rate(items: list[dict], field: str = "violation") -> dict:
    n = len(items)
    return {"n": n, f"{field}_pct": round(100 * sum(r[field] for r in items) / n, 2) if n else None}


def summary(records: list[dict]) -> dict:
    out = {}
    for load in (240, 390):
        here = [r for r in records if r["load"] == load]
        total = len(here)
        entry = {"in_language_requests": total, "violations_pct": round(100 * sum(r["violation"] for r in here) / total, 2)}
        for case in CASES:
            items = [r for r in here if r["case"] == case]
            entry[case] = rate(items) | {
                "share_of_in_language_pct": round(100 * len(items) / total, 2),
                "violations_pct_of_in_language": round(100 * sum(r["violation"] for r in items) / total, 2),
                "rejected_pct": round(100 * sum(r["rejected"] for r in items) / len(items), 2) if items else None,
            }
        only = [r for r in here if r["case"] == "only a reject complies"]
        entry["only a reject complies"] |= {
            "why": dict(Counter(r["why"] for r in only)),
            "accepted_the_choice_without_instruction_pct": round(
                100 * sum(r["as_without_instruction"] for r in only) / len(only), 2) if only else None,
        }  # fmt: skip
        restrictive = [r for r in here if r["case"] == "restrictive"]
        entry["restrictive"] |= {
            "by_language": {lang: rate([r for r in restrictive if r["lang"] == lang]) for lang in ("en", "de", "fr", "it")},
            "by_group": {g: rate([r for r in restrictive if r["group"] == g])
                         for g in ("atom", "pair", "heldout_pair", "triple", "two_preferences")},
        }  # fmt: skip
        out[str(load)] = entry
    return out


def training_rejects() -> dict:
    """How often each decider was taught to reject, and on how many states only a reject complied."""
    out = {}
    for name, path in (("first decider", ROOT / "data" / "full" / "train.jsonl"),
                       ("matched decider", ROOT / "data" / "full3" / "train.jsonl")):  # fmt: skip
        if not path.exists():
            continue
        n = rejects = 0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                n += 1
                rejects += record["completion"][0]["content"] == "reject"
        out[name] = {"records": n, "reject_labels_pct": round(100 * rejects / n, 2)}
    stats = ROOT / "data" / "full3" / "stats.json"
    if stats.exists():
        out["matched decider"]["placements"] = json.loads(stats.read_text(encoding="utf-8"))["train"]["placement"]
    return out


def main() -> None:
    result = {"note": __doc__.split("\n\n")[1].replace("\n", " "), "policies": {}}
    for file, (_, label) in POLICIES.items():
        records, _ = replay(file)
        result["policies"][label] = {"file": f"eval/{file}.json"} | summary(records)
        print(label, json.dumps(result["policies"][label]["390"]["only a reject complies"]), flush=True)
    result["training"] = training_rejects()
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
