"""What the console's richer views need, apart from the stream itself (``console.py``).

* ``explain``: for one request, why each candidate path was kept or dropped by the line that was
  applied, the preferences that ranked the rest, and the tie-break; the request inspector shows it.
* ``spectrum``: the slot occupancy of every link of a route at the moment of the decision, and the
  block the decision took; the inspector's spectrum strip.
* ``Race``: four methods on the evaluation's own stream (the mixed condition, ``operations_mix3``),
  side by side: first fit, the decider alone, the reader with the rule engine, the hybrid. Every
  decision is replayed from the answers stored when the closed loop was run (``results/cache``), so
  no model is needed, and each lane can be checked against the stored run when it is complete.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from spec import Spec, _best, meets
from view import Choice, RequestView

ROOT = Path(__file__).resolve().parents[1]
CLASSES = {  # the paper's classes of the mixed stream, by the stream's instruction keys
    "inside the language": ("atom", "pair", "heldout_pair", "triple", "two_preferences"),
    "carried in part": ("partial",),
    "types never shown": ("not_first", "min_mod", "min_free", "largest_block"),
    "nothing to apply": ("I0", "not_instruction", "faulty"),
}
CLASS_OF = {key: name for name, keys in CLASSES.items() for key in keys}
PREFERENCE_WORDS = {"hops": "fewest hops", "km": "shortest in km", "load": "least loaded (most free slots)",
                    "slots": "fewest spectrum slots"}  # fmt: skip


# ---- the request inspector -------------------------------------------------------------------------
def explain(view: RequestView, spec: Spec | None, choice: Choice, engine: Choice = None) -> dict:
    """Why each candidate was kept or dropped under ``spec`` (``None``: no line applied)."""
    spec = spec if spec is not None and spec.applies else Spec()
    paths = []
    for p in view.paths:
        inner = p.nodes[1:-1]
        why = [] if p.feasible else ["no free block of slots for this request on this path"]
        why += [f"uses the avoided link {a}–{b}" for a, b in spec.avoid if p.has_link(a, b)]
        why += [f"passes through {n}, which is avoided" for n in spec.nodes if n in inner]
        why += [f"does not pass through {n}" for n in spec.via if n not in inner]
        if spec.max_hops is not None and p.hops > spec.max_hops:
            why.append(f"{p.hops} hops, more than {spec.max_hops}")
        if spec.max_km is not None and p.km > spec.max_km:
            why.append(f"{p.km:,} km, more than {spec.max_km:,}")
        if spec.path is not None and p.index != spec.path:
            why.append(f"not candidate {spec.path}")
        paths.append({"index": p.index, "nodes": list(p.nodes), "hops": p.hops, "km": p.km, "free_slots": p.free_slots,
                      "modulation": p.modulation, "slots_needed": p.slots_needed, "first_slot": p.first_slot,
                      "blocks": [list(b) for b in p.blocks[:6]], "feasible": p.feasible, "excluded": why})  # fmt: skip
    kept = [p for p in view.paths if p.feasible and meets(p, spec)]
    steps = []
    for preference in spec.prefer:
        if not kept:
            break
        before = [p.index for p in kept]
        kept = _best(preference, kept)
        steps.append(
            {
                "by": PREFERENCE_WORDS.get(preference, preference),
                "from": before,
                "kept": [p.index for p in kept],
            }
        )
    tie = (
        "shortest in km, then the lower candidate number"
        if spec.prefer
        else "lowest free start slot, then the lower candidate number"
    )
    return {"paths": paths, "steps": steps, "tie_break": tie, "admissible": [p.index for p in kept],
            "chosen": None if choice is None else choice[0], "slot": None if choice is None else choice[1],
            "engine": None if engine is None else engine[0]}  # fmt: skip


def spectrum(env, view: RequestView, choice: Choice) -> list[dict]:
    """Slot occupancy (``"0"`` free, ``"1"`` in use) of each link of the chosen route, before the
    decision is applied, and the block it takes."""
    if choice is None:
        return []
    path = view.paths[choice[0]]
    model, alloc = env.simulator.topology, env.simulator.state.slot_allocation
    ids = {frozenset((link.source_name, link.target_name)): link.id for link in model.links}
    width = path.slots_needed or 0
    out = []
    for a, b in path.links:
        row = alloc[ids[frozenset((a, b))]]
        out.append({"a": a, "b": b, "occupied": "".join("1" if x >= 0 else "0" for x in row),
                    "block": [int(choice[1]), int(width)]})  # fmt: skip
    return out


# ---- the race --------------------------------------------------------------------------------------
LANES = (  # key, label, what it is, the stored closed-loop run it replays
    ("first_fit", "First fit", "the first candidate path that fits; ignores the instruction", "first_fit_mix3"),
    ("decider", "Decider alone", "Apertus 8B fine-tuned to decide every request, instruction in the prompt", "apertus_ft_mix3"),
    ("reader", "Reader + rule engine", "Apertus 8B reads the instruction into a line; the rule engine decides", "translate3_ft_mix3"),
    ("hybrid", "Hybrid", "the reader, and the decider (with the guard) for what the language cannot express", "hybrid3_ft_mix3"),
)  # fmt: skip
RACE_LOADS, RACE_SEEDS = (240, 390), (1, 2, 3)
WARMUP, WINDOW = 1000, 2000  # the evaluation's protocol: what the stored answers were made under


def _policy(key: str, topology: str):
    from policies import make_policy

    if key == "first_fit":
        return make_policy("first_fit")
    if key == "decider":
        return make_policy("apertus_ft_mix3", backend="transformers")
    if key == "reader":
        return make_policy("translate3_ft", topology=topology)
    return make_policy("hybrid3_ft", topology=topology, decider="apertus_ft_hybrid3")


class Race:
    """Four lanes over one stream, built in the background (each lane warms up for 1,000 requests)."""

    def __init__(self, load: int = 390, seed: int = 1, topology: str = "nobel-eu", lanes=LANES) -> None:
        if load not in RACE_LOADS or seed not in RACE_SEEDS:
            raise ValueError(f"the race replays stored runs: load {RACE_LOADS}, seed {RACE_SEEDS}")
        self.load, self.seed, self.topology, self.spec = load, seed, topology, lanes
        self.lock = threading.Lock()
        self.status, self.progress, self.error = "preparing", 0.0, None
        self.lanes: list[dict] = []
        self.requests: list[
            dict
        ] = []  # one row per request: the request, its instruction, each lane's outcome
        self.started = time.monotonic()
        threading.Thread(target=self._build, daemon=True).start()

    def _build(self) -> None:
        from evaluate import Episode

        try:
            for i, (key, label, what, stored) in enumerate(self.spec):
                job = {"policy": key, "condition": "operations_mix3", "load": self.load, "seed": self.seed,
                       "warmup": WARMUP, "window": WINDOW, "topology": self.topology}  # fmt: skip
                episode = Episode(job)
                path = ROOT / "results" / "eval" / f"{stored}.json"
                check = None
                if path.exists():
                    rows = json.loads(path.read_text(encoding="utf-8"))["episodes"]
                    check = next((r for r in rows if r["load"] == self.load and r["seed"] == self.seed), None)
                self.lanes.append({"key": key, "label": label, "what": what, "stored": stored, "episode": episode,
                                   "policy": _policy(key, self.topology), "check": check, "series": [],
                                   "classes": {name: [0, 0] for name in CLASSES}, "last": None})  # fmt: skip
                self.progress = (i + 1) / len(self.spec)
            self.status = "ready"
        except Exception as error:  # noqa: BLE001  (a background thread: any failure is shown on the page)
            self.status, self.error = "error", f"{type(error).__name__}: {error}"

    def step(self, count: int) -> int:
        """Advance every lane by up to ``count`` requests; the number decided."""
        from optical_networking_gym.heuristics import select_first_fit_action

        from evaluate import answer_tags
        from sim import action_from_choice, choice_from_action

        if self.status != "ready":
            return 0
        done = 0
        with self.lock:
            for _ in range(count):
                if any(not lane["episode"].remaining for lane in self.lanes):
                    break
                # Every lane decides before any applies: a failure (say, an answer missing from the
                # cache) then leaves the four on the same request, and the race stops with the error.
                try:
                    decisions = [lane["policy"].decide([lane["episode"].request()])[0] for lane in self.lanes]
                except Exception as error:  # noqa: BLE001  (shown on the page)
                    self.status, self.error = "error", f"{type(error).__name__}: {error}"
                    break
                first = self.lanes[0]["episode"]
                view, intent = first.view, first.intent
                kind = getattr(intent, "key", "I0")
                row = {"n": len(self.requests) + 1, "source": view.source, "destination": view.destination,
                       "bit_rate": view.bit_rate, "text": getattr(intent, "text", "none") or "none",
                       "class": CLASS_OF.get(kind, "nothing to apply"), "kind": kind, "lanes": {}}  # fmt: skip
                for lane, decision in zip(self.lanes, decisions, strict=True):
                    episode = lane["episode"]
                    before = dict(episode.counts)
                    lane_view, analysis = episode.view, episode.env.simulator.current_analysis
                    executed = decision.choice
                    if not decision.well_formed or action_from_choice(analysis, decision.choice) is None:
                        # what Episode.apply runs in place of an answer that is not a valid action
                        masks = episode.env.action_masks()
                        executed = choice_from_action(analysis, select_first_fit_action(masks))
                    episode.apply(decision)
                    after = episode.counts
                    violated = after["violations"] > before.get("violations", 0)
                    invalid = after["invalid"] > before.get("invalid", 0)
                    tags = answer_tags(decision.raw)
                    route = list(lane_view.paths[executed[0]].nodes) if executed is not None else None
                    who = "guard" if tags["guarded"] else "decider" if (tags["forwarded"] or lane["key"] == "decider") else (
                        "heuristic" if lane["key"] == "first_fit" else "rule engine")  # fmt: skip
                    outcome = {"route": route, "rejected": route is None, "violation": violated, "invalid": invalid,
                               "who": who}  # fmt: skip
                    lane["last"] = outcome
                    stats = lane["classes"][row["class"]]
                    stats[0] += 1
                    stats[1] += violated
                    lane["series"].append(int(after["violations"]))
                    row["lanes"][lane["key"]] = outcome
                self.requests.append(row)
                done += 1
        return done

    def state(self, every: int = 10) -> dict:
        with self.lock:  # a snapshot between two steps: every lane on the same request
            return self._state(every)

    def _state(self, every: int) -> dict:
        lanes = []
        for lane in list(self.lanes):
            episode = lane["episode"]
            served = int(episode.counts["requests"])
            check = lane["check"]
            complete = served >= WINDOW
            same = None
            if complete and check is not None:  # the replay must be the run that was scored
                result = episode.result()
                same = all(
                    result[f] == check[f]
                    for f in ("violations", "processed", "accepted", "rejected_by_policy")
                )
            model, alloc = episode.env.simulator.topology, episode.env.simulator.state.slot_allocation
            lanes.append({
                "key": lane["key"], "label": lane["label"], "what": lane["what"], "stored": lane["stored"],
                "served": served, "violations": int(episode.counts["violations"]), "rejected": int(episode.counts["rejects"]),
                "classes": {name: {"n": n, "violations": v} for name, (n, v) in lane["classes"].items()},
                "series": lane["series"][every - 1 :: every], "last": lane["last"],
                "links": [{"a": link.source_name, "b": link.target_name, "used": round(float((alloc[link.id] >= 0).mean()), 3)}
                          for link in model.links],
                "stored_violations": None if check is None else check["violations"], "same_as_stored": same,
            })  # fmt: skip
        return {"status": self.status, "progress": round(self.progress, 2), "error": self.error, "load": self.load,
                "seed": self.seed, "window": WINDOW, "every": every, "lanes": lanes,
                "requests": len(self.requests), "last": self.requests[-1] if self.requests else None,
                "recent": self.requests[-12:]}  # fmt: skip
