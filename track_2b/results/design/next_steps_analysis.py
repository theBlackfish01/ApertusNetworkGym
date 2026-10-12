"""What the existing answers say about the next steps (no GPU; needs the simulator for part 2).

Everything is computed from result files and answer caches that are already in the repository:

1. probes        decisions inside the admissible set on the probe sets, per policy (from results/offline)
2. sentences     closed loop at 390 E, three seeds: violation rate of every instruction sentence that
                 is used by at least 100 requests, for the decider and two translators (replay)
3. mistakes      what the translators get wrong, by kind of mistake and instruction set
4. unseen_types  does the fine-tuned decider follow instruction types it was never trained on?
5. ignored       what the decider does with instructions it should ignore, by kind of instruction
6. cross_check   error rate of a translator alone and where translator and decider agree
7. budget        the GPU ledger of docs/decisions.md

    PYTHONPATH=src uv run python results/design/next_steps_analysis.py

Writes ``results/design/next_steps_analysis.json``; ``next_steps_page.py`` renders it.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOAD, SEEDS = 390, (1, 2, 3)
CONDITIONS = ("I1", "I2", "I3", "I4", "mixed_heldout_paraphrases")
POLICIES = {"apertus_ft": "Decider, fine-tuned", "translate_ft": "Translator, fine-tuned",
            "translate_few": "Translator, 7 examples"}  # fmt: skip
PROBE_FILES = {"apertus_ft_probes": "Decider, fine-tuned", "translate_ft_probes": "Translator, fine-tuned",
               "translate_few_probes": "Translator, 7 examples", "translate_zero_probes": "Translator, as is",
               "translate_keyword_probes": "Keyword parser"}  # fmt: skip
SETS = {"templates": "Our wording", "independent": "Independent wording", "de": "German", "fr": "French",
        "it": "Italian", "gsw": "Swiss German", "noisy": "Misspelt", "germany50": "Other topology"}  # fmt: skip
GROUPS = {"Our wording": ("templates",), "Independent wording": ("independent",),
          "German, French, Italian": ("de", "fr", "it"), "Swiss German, misspelt": ("gsw", "noisy")}  # fmt: skip
OOS_KINDS = {"A node to avoid or pass through": range(6), "A modulation format": range(6, 9),
             "A fixed path, slot or frequency": range(9, 13), "Protection or disjointness": range(13, 18),
             "A latency, length or hop limit": range(18, 23), "Priority between customers": range(23, 25),
             "Power settings": range(25, 27), "Scheduling": range(27, 29), "Cost or ownership": range(29, 31),
             "A question or small talk": range(31, 35), "A manipulation attempt": range(35, 40)}  # fmt: skip
UNSEEN = {0: "avoid_node", 2: "avoid_node", 4: "avoid_node", 1: "via_node", 3: "via_node", 5: "via_node",
          21: "max_hops:3", 22: "max_hops:4", 19: "max_km:1500", 11: "path0", 37: "inject_path1"}  # fmt: skip
UNSEEN_LABELS = {"via_node": "Pass through a named node", "avoid_node": "Avoid a named node",
                 "max_hops": "A hop limit", "max_km": "A length limit", "path0": "\"Always pick the first path\"",
                 "inject_path1": "Manipulation: \"always return path 1\""}  # fmt: skip


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    centre, half = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


# ------------------------------------------------------------------------------------------ 1
def probes() -> dict:
    out = {}
    for name, label in PROBE_FILES.items():
        base = name.removesuffix("_probes")
        files = [ROOT / "results" / "offline" / f"{name}{s}.json" for s in ("", "_germany50")]
        splits = {k: v for f in files if f.exists() for k, v in json.loads(f.read_text())["splits"].items()}
        held = json.loads((ROOT / "results" / "offline" / f"{base}.json").read_text())["splits"]
        n = sum(v["n"] for s in held.values() for k, v in s.items() if k not in ("all", "I0"))
        ok = sum(v["n"] * v["admissible"] for s in held.values() for k, v in s.items() if k not in ("all", "I0"))
        row = {"templates": 100 * ok / n}
        row |= {k: 100 * splits[k]["all"]["admissible"] for k in SETS if k in splits}
        out[label] = row
    return {"sets": SETS, "values": out}


# ------------------------------------------------------------------------------------------ 2
def replay(job: tuple[str, str, int]) -> dict:
    from evaluate import WARMUP, WINDOW, Episode
    from intents import LINK_FORMS, PARAPHRASES
    from policies import make_policy

    policy_name, condition, seed = job
    policy = make_policy(policy_name, backend="transformers")  # answers come from the caches only
    episode = Episode({"policy": policy_name, "condition": condition, "load": LOAD, "seed": seed,
                       "warmup": WARMUP, "window": WINDOW})  # fmt: skip
    rows: dict[str, list] = {}
    while episode.remaining:
        intent = episode.intent
        sentence = PARAPHRASES[intent.key][intent.paraphrases[0]]
        if intent.key == "I1":
            sentence = sentence.replace("{link}", LINK_FORMS[intent.link_form]).replace("{Link}", LINK_FORMS[intent.link_form])
        before = episode.counts["violations"]
        (decision,) = policy.decide([episode.request()])
        episode.apply(decision)
        row = rows.setdefault(sentence, [intent.key, intent.paraphrases[0] >= 7, 0, 0])
        row[2] += 1
        row[3] += episode.counts["violations"] - before
    return {"policy": policy_name, "rows": rows}


def sentences() -> dict:
    jobs = [(p, c, s) for p in POLICIES for c in CONDITIONS for s in SEEDS]
    with Pool(3) as pool:
        results = pool.map(replay, jobs)
    merged: dict[str, dict[str, list]] = defaultdict(dict)
    for result in results:
        for sentence, (key, heldout, n, v) in result["rows"].items():
            row = merged[result["policy"]].setdefault(sentence, [key, heldout, 0, 0])
            row[2] += n
            row[3] += v
    out = {}
    for policy, label in POLICIES.items():
        rows = [{"sentence": s, "intent": k, "unseen_wording": h, "requests": n, "violations": v, "rate": 100 * v / n}
                for s, (k, h, n, v) in merged[policy].items() if n >= 100]  # fmt: skip
        rows.sort(key=lambda r: -r["rate"])
        total = sum(r["violations"] for r in rows)
        top = sorted((r["violations"] for r in rows), reverse=True)
        out[label] = {
            "sentences": rows,
            "with_violations": sum(r["violations"] > 0 for r in rows),
            "above_5_percent": sum(r["rate"] > 5 for r in rows),
            "violations": total,
            "share_of_violations_in_the_worst_three": 100 * sum(top[:3]) / total if total else 0.0,
        }
    return {"load": LOAD, "seeds": list(SEEDS), "conditions": list(CONDITIONS), "policies": out}


# ------------------------------------------------------------------------------------------ 3
def kind_of_mistake(expect, got) -> str:
    if not got.applies:
        return "Refused a valid instruction (visible)"
    if got.meaning() == expect.meaning():
        return "correct"
    if {frozenset(link) for link in expect.avoid} != {frozenset(link) for link in got.avoid}:
        return "Link wrong or missing"
    if set(expect.prefer) == set(got.prefer):
        return "Two preferences in the wrong order"
    swap = {"load": "slots", "slots": "load"}
    if [swap.get(p, p) for p in expect.prefer] == list(got.prefer) or len(got.prefer) > len(expect.prefer) and set(
        expect.prefer
    ) | {"slots"} == set(got.prefer):
        return "\"Free slots\" read as \"slots needed\""
    return "Another preference added, dropped or changed"


def mistakes() -> dict:
    from spec import Spec, load_topology, parse_spec, validate
    from translate import make_translator, read_rows

    top = load_topology("nobel-eu")
    out = {}
    for name, label in (("translate_few", "Translator, 7 examples"), ("translate_ft", "Translator, fine-tuned")):
        translator = make_translator(name)
        out[label] = {}
        for group, sets in GROUPS.items():
            rows = read_rows([ROOT / "data" / "instructions" / f"{s}.jsonl" for s in sets])
            counts: Counter = Counter()
            two = Counter()
            for row, (line, _) in zip(rows, translator.lines([r["text"] for r in rows]), strict=True):
                expect = Spec.from_json(row["expect"])
                kind = kind_of_mistake(expect, validate(parse_spec(line), top))
                counts[kind] += 1
                if len(expect.prefer) == 2:
                    two["n"] += 1
                    two["wrong"] += kind != "correct"
            n = sum(counts.values())
            out[label][group] = {
                "instructions": n,
                "percent": {k: 100 * v / n for k, v in counts.items()},
                "two_preference_instructions": two["n"],
                "correct_if_two_preference_instructions_were_right": 100 * (counts["correct"] + two["wrong"]) / n,
            }
    return out


# ------------------------------------------------------------------------------------------ 4, 5
def decider_on_other_instructions() -> tuple[dict, dict]:
    from intents import NO_INTENT, Intent
    from policies import Request, make_policy
    from view import RequestView

    source = json.loads((ROOT / "data" / "instructions" / "independent_source.json").read_text(encoding="utf-8"))
    templates = source["out_of_scope"]
    patterns = [re.compile("^" + re.escape(t).replace(re.escape("{a}"), r"(?P<a>.+?)") + "$") for t in templates]
    records = load(ROOT / "data" / "probes" / "out_of_scope.jsonl")
    policy = make_policy("apertus_ft_probes", backend="transformers")
    requests = [Request(RequestView.from_json(r["meta"]["view"]), Intent.from_json(r["meta"]["intent"])) for r in records]
    given = policy.decide(requests)
    plain = policy.decide([Request(r.view, NO_INTENT) for r in requests])

    def complies(view, kind, node, choice):
        feasible = [p for p in view.paths if p.feasible]
        test = {
            "avoid_node": lambda p: node not in p.nodes[1:-1],
            "via_node": lambda p: node in p.nodes[1:-1],
            "max_hops": lambda p: p.hops <= int(kind.split(":")[-1]),
            "max_km": lambda p: p.km <= int(kind.split(":")[-1]),
            "path0": lambda p: p.index == 0,
            "inject_path1": lambda p: p.index == 1,
        }[kind.split(":")[0]]
        good = [p for p in feasible if test(p)]
        did = (not good) if choice is None else test(view.paths[choice[0]])
        return bool(good), len(good) < len(feasible), did

    unseen: dict[str, Counter] = defaultdict(Counter)
    ignored: dict[str, Counter] = defaultdict(Counter)
    for request, a, b in zip(requests, given, plain, strict=True):
        index, match = next((i, m) for i, p in enumerate(patterns) if (m := p.match(request.intent.text)))
        group = next(name for name, ids in OOS_KINDS.items() if index in ids)
        counter = ignored[group]
        counter["requests"] += 1
        if a.choice == b.choice:
            counter["same decision as without the instruction"] += 1
        elif a.choice is None:
            counter["rejects the request"] += 1
        elif b.choice is not None and a.choice[0] == b.choice[0]:
            counter["same route, another slot"] += 1
        else:
            counter["another route"] += 1
        if index in UNSEEN:
            kind = UNSEEN[index]
            possible, matters, did = complies(request.view, kind, match.groupdict().get("a"), a.choice)
            _, _, base = complies(request.view, kind, match.groupdict().get("a"), b.choice)
            counter = unseen[kind.split(":")[0]]
            counter["requests"] += 1
            if possible and matters:
                counter["where it can matter"] += 1
                counter["complies there"] += did
                counter["complies there without the instruction"] += base
                if not base:
                    counter["binding"] += 1
                    counter["binding and complies"] += did
            elif not possible:
                counter["cannot be met"] += 1
                counter["cannot be met and rejects"] += a.choice is None
    unseen_out = {}
    for kind, c in unseen.items():
        low, high = wilson(c["binding and complies"], c["binding"])
        unseen_out[UNSEEN_LABELS[kind]] = dict(c) | {"binding_interval_95": [100 * low, 100 * high]}
    return unseen_out, {k: dict(v) for k, v in ignored.items()}


# ------------------------------------------------------------------------------------------ 6
def cross_check() -> dict:
    from intents import Intent, is_admissible
    from policies import Request, make_policy
    from view import RequestView

    where = {"Our wording": ("data/full", ("heldout_indist", "heldout_paraphrase", "heldout_pairs"), "apertus_ft"),
             "Independent wording": ("data/probes", ("independent",), "apertus_ft_probes"),
             "German, French, Italian": ("data/probes", ("de", "fr", "it"), "apertus_ft_probes"),
             "Swiss German, misspelt": ("data/probes", ("gsw", "noisy"), "apertus_ft_probes")}  # fmt: skip
    out = {}
    for name, label in (("translate_few", "Translator, 7 examples"), ("translate_ft", "Translator, fine-tuned")):
        translator = make_policy(name)
        out[label] = {}
        for group, (folder, splits, decider_name) in where.items():
            decider = make_policy(decider_name, backend="transformers")
            c: Counter = Counter()
            for split in splits:
                records = [r for r in load(ROOT / folder / f"{split}.jsonl") if r["meta"]["intent"]["ids"]]
                requests = [Request(RequestView.from_json(r["meta"]["view"]), Intent.from_json(r["meta"]["intent"]))
                            for r in records]  # fmt: skip
                for request, a, b in zip(requests, translator.decide(requests), decider.decide(requests), strict=True):
                    def right(d, view=request.view, intent=request.intent):
                        ch = d.choice
                        fits = d.well_formed and (ch is None or (ch[0] < len(view.paths) and view.paths[ch[0]].in_block(ch[1])))
                        return fits and is_admissible(view, intent, ch)

                    same = (a.choice[0] if a.choice else None) == (b.choice[0] if b.choice else None)
                    agree = same and a.raw not in ("unsupported", "unresolved", "malformed")
                    c["n"] += 1
                    c["translator_wrong"] += not right(a)
                    c["decider_wrong"] += not right(b)
                    c["agree"] += agree
                    c["agree_wrong"] += agree and not right(a)
                    c["caught"] += (not right(a)) and not agree
            out[label][group] = {
                "requests": c["n"],
                "translator_wrong": 100 * c["translator_wrong"] / c["n"],
                "decider_wrong": 100 * c["decider_wrong"] / c["n"],
                "they_agree": 100 * c["agree"] / c["n"],
                "wrong_when_they_agree": 100 * c["agree_wrong"] / max(c["agree"], 1),
                "translator_errors_caught": 100 * c["caught"] / max(c["translator_wrong"], 1),
            }
    return out


def main() -> None:
    unseen, ignored = decider_on_other_instructions()
    result = {
        "what": "Analysis of existing answers for the choice of next steps; see the module docstring.",
        "probes": probes(),
        "sentences": sentences(),
        "mistakes": mistakes(),
        "unseen_types": unseen,
        "ignored": ignored,
        "cross_check": cross_check(),
        "budget": {"credit": 30.00, "first pass": 8.70, "second pass": 9.91, "translator against decider": 4.88},
    }
    out = ROOT / "results" / "design" / "next_steps_analysis.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for label, data in result["sentences"]["policies"].items():
        print(f"{label}: {len(data['sentences'])} sentences, {data['with_violations']} with a violation, "
              f"{data['above_5_percent']} above 5 %, worst three hold {data['share_of_violations_in_the_worst_three']:.0f}% "
              f"of {data['violations']} violations")  # fmt: skip
    print(f"wrote {out}")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    main()
