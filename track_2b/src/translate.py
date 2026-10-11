"""The translator arm: instruction text -> spec -> rule engine.

The decider of the first two passes reads the instruction again with every request and answers
with a path and slot. Here the language model is asked once per instruction for one line in the
format of ``spec.py``; the line is checked against the topology, and the rule engine decides
every request. An instruction that is unsupported, unresolved or malformed is not applied (the
request is routed as if there were none) and is counted as *flagged*: the operator can be told.

Translators (``translate_<kind>``; add ``_ordered`` for the ordered rule of ``spec.py``):

    translate_keyword   no model: city names and keywords, written against the training wording
    translate_zero      Apertus as is, the task description only
    translate_few       Apertus as is, plus seven solved examples in the prompt
    translate_ft        Apertus fine-tuned on the training instructions (``corpora.py``)

Model answers are cached per translator (``results/cache/<name>.jsonl``), so the closed loop of
a translator runs on a laptop from the cache: ``texts`` lists every instruction the closed-loop
protocol will show, ``parse`` asks the model for them next to a GPU, and ``evaluate.py closed
--policy translate_few`` replays them.

    uv run python src/translate.py texts                                   # needs the simulator
    uv run python src/translate.py parse --policy translate_few --model <id> --sets data/instructions/*.jsonl
    uv run python src/translate.py score --policy translate_few --sets data/instructions/*.jsonl
    uv run python src/translate.py batch --model <id> --jobs translate_few:nobel-eu:regex:data/instructions/de.jsonl ...
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from policies import Decision, LocalLLMPolicy, Policy, Request
from spec import (
    EMPTY,
    UNKNOWN,
    Spec,
    Topology,
    answer_grammar,
    choose,
    format_spec,
    from_intent,
    load_topology,
    parse_spec,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
MAX_NEW_TOKENS = 48  # the longest answer line (two links, three preferences) is about 40 tokens

SYSTEM = """You translate an operator's instruction about one lightpath request into one line that a path computation engine can execute. The instruction can be in any language.

Answer with exactly one line, in one of these two forms:
avoid=<links>; prefer=<preferences>
unsupported

<links> is "none", or the links the route must not use. Write each link as NodeA-NodeB with the node names exactly as in the node list below, and separate several links with commas. If the instruction names a place that is not in the node list, write "unknown" for that place.
<preferences> is "none", or what the instruction asks to optimise, in the order it states them, separated by commas:
hops = the fewest hops (the fewest links crossed, the most direct route)
load = the least loaded path (the most free slots or free spectrum on the path)
slots = the fewest spectrum slots needed for this request
Answer "unsupported" if the instruction asks for anything else, for example avoiding a whole node, passing through a node, a modulation format, protection or priority, or if it is not a routing instruction.

Nodes: {nodes}"""

# Solved examples for the few-shot translator. The wording is from the training paraphrases of
# ``intents.py``; {a}-{b} and {c}-{d} are the first two links of the topology, {x} a place that is
# not a node. No example has two preferences: that combination stays unseen for every arm.
SHOTS = (
    ("Avoid the link between {a} and {b} for this request.", "avoid={a}-{b}; prefer=none"),
    ("Minimise the hop count for this service.", "avoid=none; prefer=hops"),
    ("Use the path with the most free spectrum.", "avoid=none; prefer=load"),
    ("Choose the narrowest allocation available.", "avoid=none; prefer=slots"),
    (
        "{c}-{d} must not carry this service. Keep the number of hops as low as possible.",
        "avoid={c}-{d}; prefer=hops",
    ),
    ("Do not use the {a}-{x} link; it is being serviced.", "avoid={a}-" + UNKNOWN + "; prefer=none"),
    ("Use 16QAM for this connection.", "unsupported"),
)
OUTSIDE_PLACE = "Reykjavik"


def messages(text: str, topology: Topology, few: bool = False) -> list[dict[str, str]]:
    """The chat messages that ask for the translation of one instruction."""
    chat = [{"role": "system", "content": SYSTEM.format(nodes=", ".join(topology.nodes))}]
    if few:
        (a, b), (c, d) = (sorted(link) for link in sorted(topology.links, key=sorted)[:2])
        names = {"a": a, "b": b, "c": c, "d": d, "x": OUTSIDE_PLACE}
        for instruction, answer in SHOTS:
            chat.append({"role": "user", "content": "Instruction: " + instruction.format(**names)})
            chat.append({"role": "assistant", "content": answer.format(**names)})
    chat.append({"role": "user", "content": "Instruction: " + text})
    return chat


class Translator:
    name = "translator"

    def __init__(self, topology: Topology) -> None:
        self.topology = topology

    def lines(self, texts: list[str]) -> list[tuple[str, float]]:
        """``(answer line, seconds)`` for each instruction."""
        raise NotImplementedError

    def translate(self, texts: list[str]) -> list[Spec]:
        """The validated spec of each instruction."""
        return [validate(parse_spec(line), self.topology) for line, _ in self.lines(texts)]

    def describe(self) -> dict:
        return {"name": self.name, "topology": self.topology.name}


class KeywordTranslator(Translator):
    """No model. Written against the training wording of ``intents.py`` only (English).

    A link is two capitalised names joined by a hyphen or dash, or "between A and B"; a name that
    is not a node becomes ``unknown``. A preference is a keyword; several are ordered by where
    they first appear. An instruction in which nothing is recognised is ``unsupported``.
    """

    name = "translate_keyword"
    _NAME = r"([A-Z][\w'’]*)"  # no full stop: a name at the end of a sentence must still match a node
    _LINKS = (re.compile(_NAME + r"\s?[-–—]\s?" + _NAME), re.compile(r"between " + _NAME + r" and " + _NAME))
    _KEYWORDS = (
        ("hops", r"\bhops?\b|fewest links"),
        ("load", r"least[- ]loaded|most free|emptiest|free-slot|spare slots|least congested|\bbalanc"),
        (
            "slots",
            r"fewest slots|number of slots|slot requirement|narrowest|spectrum-efficient|spectrum is scarce|save spectrum",
        ),
    )

    def one(self, text: str) -> str:
        links = []
        for pattern in self._LINKS:
            for a, b in pattern.findall(text):
                links.append(tuple(name if name in self.topology.nodes else UNKNOWN for name in (a, b)))
        found = {}
        for preference, pattern in self._KEYWORDS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                found[preference] = match.start()
        if not links and not found:
            return "unsupported"
        return format_spec(Spec(tuple(links[:2]), tuple(sorted(found, key=found.get))))

    def lines(self, texts: list[str]) -> list[tuple[str, float]]:
        answers = []
        for text in texts:
            started = time.perf_counter()
            answers.append((self.one(text), time.perf_counter() - started))
        return answers


class LLMTranslator(Translator):
    """Apertus, in this process (next to a GPU) or replayed from its answer cache."""

    def __init__(self, name: str, topology: Topology, *, few: bool = False, **llm) -> None:
        super().__init__(topology)
        self.name, self.few = name, few
        constrained = llm.get("structured") != "none"
        self.llm = LocalLLMPolicy(
            name,
            model=llm.get("model"),
            adapter=llm.get("adapter"),
            structured="regex" if constrained else "none",
            template_kwargs=llm.get("template_kwargs"),
            max_batch=llm.get("max_batch", 64),
            grammar=answer_grammar(topology) if constrained else None,
            max_new_tokens=MAX_NEW_TOKENS,
        )

    def lines(self, texts: list[str]) -> list[tuple[str, float]]:
        entries = self.llm.ask([messages(text, self.topology, self.few) for text in texts])
        return [(entry["answer"], entry["seconds"]) for entry in entries]

    def describe(self) -> dict:
        return super().describe() | {"few_shot": self.few, "llm": self.llm.describe()}


def make_translator(name: str, topology: str = "nobel-eu", **llm) -> Translator:
    """``translate_keyword``, or a model translator; a name containing ``_few`` gets the examples."""
    net = load_topology(topology)
    if name == "translate_keyword":
        return KeywordTranslator(net)
    return LLMTranslator(name, net, few="_few" in name, **llm)


class TranslatorPolicy(Policy):
    """A translator and the rule engine as a policy, so the evaluator treats it like any other."""

    parallel_safe = True  # in worker processes the model answers must already be in the cache

    def __init__(self, name: str, translator: Translator, rule: str) -> None:
        self.name, self.translator, self.rule = name, translator, rule
        self._specs: dict[str, Spec] = {"none": EMPTY}  # "none" is the prompt text of no instruction

    def decide(self, requests: list[Request]) -> list[Decision]:
        new = sorted({r.intent.text for r in requests} - self._specs.keys())
        if new:
            self._specs.update(zip(new, self.translator.translate(new), strict=True))
        decisions = []
        for request in requests:
            started = time.perf_counter()
            spec = self._specs[request.intent.text]
            choice = choose(request.view, spec if spec.applies else EMPTY, self.rule)
            raw = format_spec(spec) if spec.applies or spec.status == "unsupported" else spec.status
            decisions.append(Decision(choice, raw=raw, seconds=time.perf_counter() - started))
        return decisions

    def describe(self) -> dict:
        return {"name": self.name, "rule": self.rule, "translator": self.translator.describe()}


def make_translator_policy(name: str, topology: str = "nobel-eu", **llm) -> TranslatorPolicy:
    ordered = name.endswith("_ordered")
    translator = make_translator(name.removesuffix("_ordered"), topology, **llm)
    return TranslatorPolicy(name, translator, "ordered" if ordered else "intersection")


def read_rows(paths: list[Path]) -> list[dict]:
    """Instruction rows (``text``, ``expect``, ``set``, ...) of the given files, each text once per set."""
    rows, seen = [], set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("set", path.stem), row["text"])
            if key not in seen:
                seen.add(key)
                rows.append(row | {"set": key[0]})
    return rows


def collect_texts(args: argparse.Namespace) -> None:
    """Every instruction of the closed-loop protocol, with the spec it means.

    The instruction of request i depends on the condition, load, seed and the request's candidate
    paths only, not on the policy, so one pass with the oracle lists them all.
    """
    from multiprocessing import Pool

    from evaluate import CONDITIONS, EVAL_LOADS, EVAL_SEEDS, WARMUP, WINDOW

    jobs = [
        {"policy": "oracle", "condition": c, "load": load, "seed": seed, "warmup": WARMUP, "window": WINDOW}
        for c in CONDITIONS if c != "I0" for load in EVAL_LOADS for seed in EVAL_SEEDS
    ]  # fmt: skip
    rows: dict[str, dict] = {}
    with Pool(args.workers) as pool:
        for done, found in enumerate(pool.imap_unordered(_episode_texts, jobs), start=1):
            for row in found:
                rows.setdefault(row["text"], row)
            print(f"[{done:>2}/{len(jobs)}] {len(rows)} distinct instructions", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        for text in sorted(rows):
            handle.write(json.dumps(rows[text], ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} instructions to {args.out}")


def _episode_texts(job: dict) -> list[dict]:
    from evaluate import Episode
    from policies import Oracle

    episode, policy, rows = Episode(job), Oracle(), {}
    while episode.remaining:
        intent = episode.intent
        if intent.text not in rows:
            rows[intent.text] = {"text": intent.text, "expect": from_intent(intent).to_json(),
                                 "set": "closed_loop", "lang": "en", "kind": intent.key}  # fmt: skip
        (decision,) = policy.decide([episode.request()])
        episode.apply(decision)
    return list(rows.values())


def parse(args: argparse.Namespace) -> None:
    """Ask the translator for every instruction of the given sets (fills its answer cache)."""
    from evaluate import upload_results

    translator = make_translator(args.policy, args.topology, **_llm(args))
    texts = sorted({row["text"] for row in read_rows(args.sets)})
    started = synced = time.perf_counter()
    for start in range(0, len(texts), args.chunk):
        translator.lines(texts[start : start + args.chunk])
        done = min(start + args.chunk, len(texts))
        print(
            f"{args.policy}: {done}/{len(texts)} instructions, {time.perf_counter() - started:.0f} s",
            flush=True,
        )
        cache = getattr(getattr(translator, "llm", None), "cache_path", None)
        due = done == len(texts) or time.perf_counter() - synced > 120  # the cache is the only thing to lose
        if args.sync_repo and cache is not None and cache.exists() and due:
            upload_results(args.sync_repo, [cache])
            synced = time.perf_counter()


def score(args: argparse.Namespace) -> None:
    """Translation accuracy on labelled instructions.

    For an instruction that should be applied: ``correct`` (same meaning), ``flagged`` (not
    applied: visible to the operator) or ``wrong`` (applied with another meaning: silent).
    For one that should not be applied: ``flagged`` or ``applied`` (silent).
    """
    translator = make_translator(args.policy, args.topology, **_llm(args))
    rows = read_rows(args.sets)
    lines = translator.lines([row["text"] for row in rows])
    groups: dict[tuple, Counter] = defaultdict(Counter)
    examples: dict[tuple, list] = defaultdict(list)
    for row, (line, seconds) in zip(rows, lines, strict=True):
        expect = Spec.from_json(row["expect"])
        raw = parse_spec(line)
        got = validate(raw, translator.topology)
        if expect.applies:
            outcome = (
                "correct" if got.meaning() == expect.meaning() else "wrong" if got.applies else "flagged"
            )
        else:
            outcome = "applied" if got.applies else "flagged"
        for key in ((row["set"], "all", "all"), (row["set"], row.get("lang", "en"), row.get("kind", "all"))):
            counter = groups[key]
            counter["n"] += 1
            counter[outcome] += 1
            counter["malformed"] += raw.status == "malformed"
            counter["same_status"] += got.status == expect.status
            counter["ms"] += 1000 * seconds
        bad = outcome in ("wrong", "applied") or (outcome == "flagged" and expect.applies)
        if bad and len(examples[(row["set"], outcome)]) < args.examples:
            examples[(row["set"], outcome)].append(
                {
                    "text": row["text"],
                    "expected": format_spec(expect) if expect.applies else expect.status,
                    "answer": line,
                    "status": got.status,
                }
            )
    result = {
        "metadata": {"policy": translator.describe(), "command": " ".join(sys.argv),
                     "finished_utc": datetime.now(UTC).isoformat(), "sets": [p.name for p in args.sets]},
        "groups": [
            {"set": s, "lang": lang, "kind": kind, "n": c["n"],
             **{k: c[k] for k in ("correct", "flagged", "wrong", "applied", "malformed", "same_status")},
             "ms_per_instruction": c["ms"] / c["n"]}
            for (s, lang, kind), c in sorted(groups.items())
        ],
        "examples": [{"set": s, "outcome": o, "cases": cases} for (s, o), cases in sorted(examples.items())],
    }  # fmt: skip
    out = args.out or ROOT / "results" / "translate" / f"{args.policy}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for group in result["groups"]:
        if group["lang"] == "all":
            n = group["n"]
            print(f"{group['set']:22s} n={n:6d}  correct {100 * group['correct'] / n:5.1f}%  flagged "
                  f"{100 * group['flagged'] / n:5.1f}%  wrong {100 * group['wrong'] / n:5.1f}%  applied "
                  f"{100 * group['applied'] / n:5.1f}%")  # fmt: skip
    print(f"wrote {out}")
    if args.sync_repo:
        from evaluate import upload_results

        upload_results(args.sync_repo, [out])


def batch(args: argparse.Namespace) -> None:
    """Several ``parse`` and ``score`` runs in one process, so the model is loaded once.

    A job is ``policy:topology:regex|none:file,file,...``; its scores go to
    ``results/translate/<policy>.json`` (``<policy>_<topology>.json`` off nobel-eu).
    """
    for job in args.jobs:
        policy, topology, structured, files = job.split(":")
        name = policy if topology == "nobel-eu" else f"{policy}_{topology}"
        one = argparse.Namespace(**{**vars(args), "policy": policy, "topology": topology, "structured": structured,
                                    "sets": [Path(f) for f in files.split(",")],
                                    "out": ROOT / "results" / "translate" / f"{name}.json"})  # fmt: skip
        print(f"=== {job}", flush=True)
        parse(one)
        score(one)


def _llm(args: argparse.Namespace) -> dict:
    return {"model": args.model, "adapter": args.adapter, "structured": args.structured,
            "template_kwargs": json.loads(args.template_kwargs), "max_batch": args.batch}  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["texts", "parse", "score", "batch"])
    parser.add_argument(
        "--jobs", nargs="+", default=[], help="batch: policy:topology:regex|none:file,file,..."
    )
    parser.add_argument("--policy", default="translate_keyword")
    parser.add_argument("--sets", type=Path, nargs="+", default=[], help="instruction files (JSON lines)")
    parser.add_argument("--topology", default="nobel-eu")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=2, help="texts: simulator processes")
    parser.add_argument("--examples", type=int, default=8, help="score: failures kept per set and kind")
    parser.add_argument("--chunk", type=int, default=512, help="parse: instructions between two syncs")
    parser.add_argument("--model", default=None)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--structured", choices=["regex", "none"], default="regex")
    parser.add_argument("--template-kwargs", default="{}")
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--sync-repo", default=None, help="Hub dataset repo to copy cache and results to")
    args = parser.parse_args()
    if args.mode == "texts":
        args.out = args.out or ROOT / "data" / "instructions" / "closed_loop.jsonl"
        collect_texts(args)
    else:
        {"parse": parse, "score": score, "batch": batch}[args.mode](args)


if __name__ == "__main__":
    main()
