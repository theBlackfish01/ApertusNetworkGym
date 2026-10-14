"""The operator console: one stream of requests under standing policies and per-request instructions,
with a feed of what the AI does.

A page (``src/console.html``) served by this script. The simulator runs a stream of requests at the
given load and seed. Two kinds of operator text govern it:

* **standing policies** (the fourth format: scope and lifetime), typed in the command bar or, in
  demo mode, arriving on the schedule of the standing-policy stream. One reader translates each
  policy; the console reads it back, names the conflicts with the policies in force, previews it
  on a copy of the network, and adds it to the policy table, where it covers the requests its
  scope names until it expires or is withdrawn;
* **per-request instructions** (the third format), drawn with each request from the mixed stream
  of the third round (in the language, never-shown types, carried in part, no instruction, places
  outside) or typed for the next request. Two readers translate each one; when they differ the
  operator is asked, by consequence: the first reading stands until a request would be decided
  differently under the two readings (a reading that does not apply, or one carried in part, is
  asked about at once).

Every request is decided by the rule engine under the one line the policies and the instruction
combine to, except an instruction outside the language or carried in part, which goes to the
decider with the guard (live only; without a model server the rule engine stands in and the feed
says so). The feed narrates each step; the audit trail keeps one row per lightpath; every policy
reports what it did. Questions pause the stream until the operator answers, unless the simulated
operator is on, which answers with the recorded meaning, as the closed-loop evaluation does.

    uv run python src/console.py                      # readers and decider from recorded answers
    uv run python src/console.py --base-url http://127.0.0.1:8089/v1   # live, behind llama.cpp

Without a server only texts answered before can be read (the page lists them); with one, anything
can be typed. One simulator hour is ``standing_stream.HOUR`` time units.

The page is the frontend in ``src/console_ui`` (Svelte), built to ``src/console_ui/dist``; without
a build the server falls back to ``console.html``. Besides the stream, the server keeps for every
decided request why each candidate path was kept or dropped and the spectrum of its route
(``/api/request?n=``), and runs the race of four methods on the evaluation's stream from stored
answers (``/api/race``; ``console_extras.Race``).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import mimetypes
import os
import threading
import xml.dom.minidom
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import mixed3
import standing_stream
from console_extras import RACE_LOADS, RACE_SEEDS, Race, explain, spectrum
from evaluate import Episode, answer_tags
from intents import Intent
from mixed import respected
from policies import Decision, Request
from spec import (
    EMPTY,
    Spec,
    choose,
    describe,
    format_spec,
    load_topology,
    meets,
    parse_spec,
    respects,
    validate,
)
from standing import PolicyTable, combine
from standing_stream import HOUR
from tapi import constraints
from translate import make_hybrid_policy, make_translator, meant, messages, read_rows

ROOT = Path(__file__).resolve().parents[1]
PAGE = Path(__file__).with_name("console.html")  # the page without a build step (served at /legacy)
DIST = Path(__file__).with_name("console_ui") / "dist"  # the built frontend (src/console_ui: npm run build)
HEAVY = ("inspect", "spectrum", "used")  # per-request detail served by /api/request, not in every state
DETAIL = 2000  # requests that keep that detail (about 10 kB each); older rows keep the audit fields only
MAX_BODY = 1 << 20  # bytes of a request body
TYPES = {".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".svg": "image/svg+xml",
         ".json": "application/json"}  # fixed, so the Windows registry cannot change them  # fmt: skip
RECORDED_SETS = ("owner", "mix3_390", "v3_en", "v3_de", "v3_fr", "v3_it", "v3_new", "v3_partial", "v3_not")
RECORDED_SETS4 = ("v4_en", "v4_de", "v4_fr", "v4_it", "owner")
NOT_APPLIED = ("unsupported", "no_instruction", "unresolved", "malformed")
FEED_KEEP = 400
KINDS = {  # what the mixed stream's kinds mean to an operator
    "supported": "in the language", "new": "a type never shown", "partial": "carried in part",
    "not_instruction": "no routing instruction", "faulty": "a place outside the network", "none": "no instruction",
}  # fmt: skip


def node_coordinates(topology_id: str) -> dict[str, tuple[float, float]]:
    """Longitude and latitude of every node, from the SNDlib file ONG loads."""
    from optical_networking_gym.defaults import resolve_topology, set_topology_dir

    from sim import SCENARIO, TOPOLOGIES, build_scenario

    own = {"topology_dir": TOPOLOGIES} if (TOPOLOGIES / f"{topology_id}.xml").exists() else {}
    config = build_scenario(SCENARIO, topology_id=topology_id, **own)
    if config.topology_dir is not None:
        set_topology_dir(config.topology_dir)
    document = xml.dom.minidom.parse(str(resolve_topology(config.topology_id))).documentElement
    out = {}
    for node in document.getElementsByTagName("node"):
        x = float(node.getElementsByTagName("x")[0].firstChild.data)
        y = float(node.getElementsByTagName("y")[0].firstChild.data)
        out[node.getAttribute("id")] = (x, y)
    return out


def who_decided(raw: str | None) -> str:
    tags = answer_tags(raw)
    body = (raw or "").removeprefix("asked+")
    if body.startswith("offline:"):
        return "rule engine (decider offline)"
    if tags["guarded"]:
        return "decider, choice replaced by the guard"
    if tags["forwarded"]:
        return "decider"
    if body in NOT_APPLIED:
        return "not applied"
    return "rule engine"


def route_of(view, choice) -> list[str] | None:
    return list(view.paths[choice[0]].nodes) if choice is not None else None


class Console:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.Lock()
        self.live = bool(args.base_url)
        suffix = "live" if self.live else "laptop"
        self.hybrid_name = args.policy or f"hybrid3_ft_{suffix}_askif-ft2_{suffix}"
        self.decider_name = args.decider or f"apertus_ft_{suffix}"
        self.reader_name = args.reader or f"translate4_ft_{suffix}"
        if self.live and "LLM_LORA_IDS" not in os.environ:
            os.environ["LLM_LORA_IDS"] = json.dumps(
                {f"translate3_ft_{suffix}": 0, f"translate3_ft2_{suffix}": 1, f"apertus_ft_{suffix}": 2,
                 f"translate4_ft_{suffix}": 3}
            )  # fmt: skip
        self.topology = load_topology(args.topology)
        self.coordinates = node_coordinates(args.topology)
        job = {"policy": self.hybrid_name, "condition": mixed3.CONDITION, "load": args.load, "seed": args.seed,
               "warmup": args.warmup, "window": 10**6, "topology": args.topology}  # fmt: skip
        self.episode = Episode(job)
        llm = {"base_url": args.base_url or None, "concurrency": 1}
        self.hybrid = make_hybrid_policy(self.hybrid_name, args.topology, decider=self.decider_name, **llm)
        if self.hybrid.second is None:
            raise SystemExit("the console needs a hybrid with two readers (a name with _ask- or _askif-)")
        self.readers = (self.hybrid.translator, self.hybrid.second)
        self.reader = make_translator(self.reader_name, args.topology, **llm)
        self.table = PolicyTable(self.topology)  # what the operator confirmed
        self.stream = standing_stream.Stream(job)  # the schedule of arrivals, and the true table
        self.truth = self.stream.table
        self.arrivals = bool(getattr(args, "arrivals", True))
        self.mix = bool(getattr(args, "mix", True))
        self.auto_answer = bool(getattr(args, "auto_answer", False))
        self.override: str | None = None  # an instruction the operator typed for the next request
        self._specs: dict[str, Spec] = {"none": EMPTY}  # confirmed readings per instruction text
        self._asked: set[str] = set()
        self._pending: dict[str, tuple[Spec, Spec]] = {}  # two readings not yet told apart by a request
        self._announced: int = 0  # the request number whose instruction the feed announced
        self.question: dict | None = None
        self._questions = 0
        self.feed: list[dict] = []
        self.audit: list[dict] = []
        self.last_route: list[str] | None = None
        self.counts: Counter = Counter()
        self.series: list[tuple[int, ...]] = []  # per request: violation, rejected, asked, decider, guard
        self._ended: dict[int, float] = {}  # policy id -> the hour it was withdrawn
        self.race: Race | None = None
        self.race_lock = threading.Lock()  # guards replacing the race; the race has its own lock
        self.recorded = {"instructions": [], "policies": []} if self.live else self._recorded()
        self._event("start", "operator", "console ready",
                    f"{args.topology}, {args.load} Erlang, seed {args.seed}; "
                    + ("models live" if self.live else "recorded answers, no model server"))  # fmt: skip

    @property
    def now(self) -> float:
        """The simulator's clock in hours."""
        return float(self.episode.env.simulator.state.current_time) / HOUR

    # ---- the feed ----------------------------------------------------------------------------
    def _event(
        self, kind: str, level: str, title: str, detail: str | None = None, data: dict | None = None
    ) -> dict:
        event = {"n": len(self.feed) + 1, "hour": round(self.now, 2), "request": len(self.audit) + 1,
                 "kind": kind, "level": level, "title": title, "detail": detail, "data": data}  # fmt: skip
        self.feed.append(event)
        if len(self.feed) > 4 * FEED_KEEP:
            del self.feed[: len(self.feed) - FEED_KEEP]
        return event

    # ---- what the page shows -----------------------------------------------------------------
    def _recorded(self) -> dict[str, list[dict]]:
        """Texts answered before by the readers, so the console works without a server."""

        def listing(readers, sets) -> list[dict]:
            caches = [getattr(getattr(t, "llm", None), "_cache", {}) for t in readers]
            few = [getattr(t, "few", False) for t in readers]
            versions = [getattr(t, "version", 3) for t in readers]
            paths = [ROOT / "data" / "instructions" / f"{name}.jsonl" for name in sets]
            out, seen = [], set()
            for row in read_rows([p for p in paths if p.exists()]):
                text = row["text"]
                if text in seen:
                    continue
                keys = [
                    hashlib.sha256(
                        json.dumps(messages(text, self.topology, f, v), sort_keys=True).encode()
                    ).hexdigest()
                    for f, v in zip(few, versions, strict=True)
                ]
                if all(key in cache for key, cache in zip(keys, caches, strict=True)):
                    seen.add(text)
                    out.append(
                        {
                            "text": text,
                            "set": row["set"],
                            "lang": row.get("lang", "en"),
                            "kind": row.get("kind", ""),
                        }
                    )
            return out

        return {
            "instructions": listing(self.readers, RECORDED_SETS),
            "policies": listing((self.reader,), RECORDED_SETS4),
        }

    def _policy_rows(self) -> list[dict]:
        specs = {p.id: p.spec for p in self.table.policies + self.table.withdrawn}
        rows = self.table.report(self.now)
        for row in rows:
            spec = specs[row["id"]]
            row["line"] = format_spec(spec, 4)
            row["readback"] = describe(spec)
            row["spec"] = spec.to_json()
            ended = self._ended.get(row["id"])
            if ended is None and not row["active"] and row["expires"] is not None:
                ended = row["expires"]
            row["ended"] = ended
        return rows

    def state(self) -> dict:
        env = self.episode.env
        model, alloc = env.simulator.topology, env.simulator.state.slot_allocation
        links = [{"a": link.source_name, "b": link.target_name, "km": round(link.length_km),
                  "used": round(float((alloc[link.id] >= 0).mean()), 3)} for link in model.links]  # fmt: skip
        snap = env.simulator.statistics.snapshot()
        view, now = self.episode.view, self.now
        active = self.table.active(now)
        in_force = combine([p.spec.routing() for p in reversed(active)])
        covering = [p.id for p in self.table.applicable(view, now)]
        text = (
            self.override if self.override is not None else (self.episode.intent.text if self.mix else "none")
        )
        intent = self.episode.intent if self.override is None and self.mix else None
        served = len(self.audit)
        return {
            "topology": self.args.topology,
            "now": round(now, 2),
            "mode": {"live": self.live, "hybrid": self.hybrid_name, "reader": self.reader_name,
                     "decider": self.decider_name if self.live else "offline (the rule engine stands in)",
                     "base_url": self.args.base_url or ""},
            "settings": {"arrivals": self.arrivals, "mix": self.mix, "auto_answer": self.auto_answer},
            "nodes": [{"name": n, "lon": x, "lat": y} for n, (x, y) in self.coordinates.items()],
            "links": links,
            "policies": self._policy_rows(),
            "in_force": {"line": format_spec(in_force, 3), "spec": in_force.to_json(), "count": len(active), "covering": covering},
            "pending": {"n": served + 1, "source": view.source, "destination": view.destination, "bit_rate": view.bit_rate,
                        "paths": [list(p.nodes) for p in view.paths],
                        "instruction": {"text": text, "kind": getattr(intent, "kind", "typed" if text != "none" else "none"),
                                        "lang": getattr(intent, "lang", ""), "typed": self.override is not None}},
            "question": self.question,
            "last_route": self.last_route,
            "stats": {"served": served, "processed": int(snap.episode_services_processed),
                      "blocking": round(float(snap.episode_service_blocking_rate), 4),
                      "rejected": self.counts["rejected"], "violations": self.counts["violations"],
                      "policy_violations": self.counts["policy_violations"], "questions": self._questions,
                      "decider": self.counts["decider"], "guarded": self.counts["guarded"],
                      "flagged": self.counts["flagged"], "unread": self.counts["unread"],
                      "policies_active": len(active), "load": self.args.load, "seed": self.args.seed},
            "feed": self.feed[-FEED_KEEP:],
            "audit": [{k: v for k, v in row.items() if k not in HEAVY} for row in self.audit[-100:]],
            "series": {name: "".join(str(s[i]) for s in self.series) for i, name in
                       enumerate(("violation", "rejected", "asked", "decider", "guard"))},
            "race_default": {"load": self.args.load if self.args.load in RACE_LOADS else 390,
                             "seed": self.args.seed if self.args.seed in RACE_SEEDS else 1},
        }  # fmt: skip

    # ---- reading -----------------------------------------------------------------------------
    def _read_instruction(self, text: str) -> tuple[list[str], list[Spec], list[float]] | None:
        """Both readers' lines for an instruction; ``None`` when there is no server and no record."""
        lines, seconds = [], []
        for translator in self.readers:
            try:
                line, took = translator.lines([text])[0]
            except (RuntimeError, ImportError, OSError):  # no server and no record, or no answer
                return None
            lines.append(line)
            seconds.append(took)
        return lines, [validate(parse_spec(line), self.topology) for line in lines], seconds

    def _readings(
        self, text: str, lines: list[str], specs: list[Spec], seconds: list[float], view, standing: Spec
    ) -> list[dict]:
        out = []
        for name, line, spec, took in zip(("reader 1", "reader 2"), lines, specs, seconds, strict=True):
            effective = combine([spec.routing(), standing]) if spec.applies else standing
            choice = choose(view, effective) if not self._forwarded(spec) else None
            out.append({"reader": name, "line": line, "spec": spec.to_json(), "readback": describe(spec),
                        "status": spec.status, "applies": spec.applies, "tapi": constraints(spec, view),
                        "seconds": round(took, 2),
                        "decision": {"route": route_of(view, choice), "reject": choice is None,
                                     "to_decider": self._forwarded(spec)}})  # fmt: skip
        return out

    def _unread(self, what: str) -> str:
        if self.live:
            return f"the model server at {self.args.base_url} did not answer, and {what} was not read before"
        return f"no model server, and {what} was not read before"

    @staticmethod
    def _forwarded(spec: Spec) -> bool:
        return spec.status == "unsupported" or (spec.applies and spec.rest)

    def read_instruction(self, text: str) -> dict:
        """The operator types an instruction for the next request: both readings and what each would do."""
        text = " ".join(text.split())
        if not text or text == "none":
            self.override = None if not text else "none"
            return {"ok": True, "text": self.override or "", "readings": []}
        read = self._read_instruction(text)
        if read is None:
            return {"error": self._unread("this instruction")}
        lines, specs, seconds = read
        self.override = text
        view, now = self.episode.view, self.now
        standing = self.table.effective(view, now)
        readings = self._readings(text, lines, specs, seconds, view, standing)
        differ = specs[0].meaning() != specs[1].meaning()
        decide_differently = differ and readings[0]["decision"] != readings[1]["decision"]
        return {"ok": True, "text": text, "readings": readings, "differ": differ,
                "decide_differently": decide_differently, "request": self.state()["pending"]}  # fmt: skip

    def confirm_instruction(self, text: str, line: str) -> dict:
        """The operator settles the reading of an instruction (typed, or asked about)."""
        text = " ".join(text.split())
        # "unresolved" (a place outside the network) is a reading a question can offer, not a line to parse
        unresolved = line.strip() == "unresolved"
        spec = Spec(status="unresolved") if unresolved else validate(parse_spec(line), self.topology)
        if spec.status == "malformed":
            return {"error": f"not a line of the policy language: {line!r}"}
        self._specs[text] = spec
        self._asked.add(text)
        self._pending.pop(text, None)
        if self.question and self.question["text"] == text:
            self.question = None
        self._event(
            "answer", "operator", "you settled the reading", f"{describe(spec)}", {"text": text, "line": line}
        )
        return {"ok": True, "line": format_spec(spec, 3) if spec.applies else spec.status}

    def answer(self, question_id: int, choice: str | int, line: str = "") -> dict:
        if not self.question or self.question["id"] != int(question_id):
            return {"error": "no such question is open"}
        if str(choice) in ("1", "2"):
            picked = self.question["readings"][int(choice) - 1]["line"]
        else:
            picked = line
        return self.confirm_instruction(self.question["text"], picked)

    # ---- standing policies -------------------------------------------------------------------
    def read_policy(self, text: str, preview: bool = True) -> dict:
        text = " ".join(text.split())
        if not text:
            return {"error": "type a policy first"}
        try:
            line, took = self.reader.lines([text])[0]
        except (RuntimeError, ImportError, OSError):
            return {"error": self._unread("this policy")}
        spec = validate(parse_spec(line), self.topology)
        now, view = self.now, self.episode.view
        conflicts = self.table.conflicts(spec, now) if spec.applies else []
        out = {"text": text, "line": line, "status": spec.status, "applies": spec.applies, "readback": describe(spec),
               "scope": spec.scope or "any", "until": spec.until, "tapi": constraints(spec, view),
               "conflicts": conflicts, "seconds": round(took, 2), "preview": None}  # fmt: skip
        if spec.applies and preview:
            trial = copy.deepcopy(self.table)
            trial.add(text, spec, now)
            horizon = self.args.horizon
            without = self._rollout(self.table.effective, horizon)
            with_it = self._rollout(trial.effective, horizon)
            changed = sum(a["path"] != b["path"] for a, b in zip(with_it, without, strict=True))
            out["preview"] = {"horizon": horizon,
                              "without": {"blocked": sum(r["blocked"] for r in without)},
                              "with": {"blocked": sum(r["blocked"] for r in with_it), "changed": changed},
                              "covers": sum(spec.scope is None or self._covers(spec.scope, r) for r in with_it)}  # fmt: skip
        return out

    @staticmethod
    def _covers(scope: str, row: dict) -> bool:
        kind, _, value = scope.partition(":")
        return {"rate": str(row["bit_rate"]) == value, "from": row["source"] == value,
                "to": row["destination"] == value}.get(kind, True)  # fmt: skip

    def _rollout(self, spec, horizon: int) -> list[dict]:
        """The next requests on a copy of the simulator, decided by the rule engine under ``spec``
        (a spec, or a function of the request's view and the hour that gives one); policies only."""
        from optical_networking_gym.heuristics import select_first_fit_action

        from sim import action_from_choice, view_from_analysis

        env = copy.deepcopy(self.episode.env)
        rows = []
        for _ in range(horizon):
            analysis = env.simulator.current_analysis
            view = view_from_analysis(analysis)
            applied = spec(view, float(env.simulator.state.current_time) / HOUR) if callable(spec) else spec
            choice = choose(view, applied)
            action = action_from_choice(analysis, choice)
            if action is None:
                action = select_first_fit_action(env.action_masks())
            rows.append({"source": view.source, "destination": view.destination, "bit_rate": view.bit_rate,
                         "path": choice[0] if choice else None, "route": route_of(view, choice), "blocked": choice is None})  # fmt: skip
            env.step(action)
        return rows

    def add_policy(self, text: str, line: str, truth: Spec | None = None, source: str = "operator") -> dict:
        text = " ".join(text.split())
        spec = validate(parse_spec(line), self.topology)
        if not spec.applies:
            return {"error": f"not a policy the table can hold: {spec.status}"}
        now = self.now
        policy, conflicts = self.table.add(text, spec, now)
        if source == "operator":  # what the operator confirmed is the truth of a typed policy
            self.truth.add(text, spec, now)
        for c in conflicts:
            self._event("conflict", "operator", f"{c['kind']} with policy {c['with']}" if c["with"] else c["kind"], c["why"],
                        {"policy": policy.id, "with": c["with"]})  # fmt: skip
        holds = "until withdrawn" if spec.until is None else f"for {spec.until} h"
        self._event("policy_added", "operator", f"policy {policy.id} in force, {holds}",
                    f"{describe(spec)}", {"policy": policy.id, "line": format_spec(spec, 4), "text": text, "source": source,
                                          "truth": format_spec(truth, 4) if truth is not None else None,
                                          "right": None if truth is None else truth.meaning() == spec.meaning()})  # fmt: skip
        return {"ok": True, "id": policy.id, "conflicts": conflicts}

    def withdraw_policy(self, policy_id: int) -> dict:
        gone = self.table.withdraw(int(policy_id))
        if gone is None:
            return {"error": "no such policy in force"}
        self._ended[gone.id] = round(self.now, 2)
        for p in list(self.truth.policies):
            if p.text == gone.text:
                self.truth.withdraw(p.id)
        self._event(
            "policy_withdrawn", "operator", f"policy {gone.id} withdrawn", gone.text, {"policy": gone.id}
        )
        return {"ok": True}

    def _arrivals(self, view, now: float) -> None:
        """Policies arriving and leaving on the stream's schedule (demo mode)."""
        intent = self.stream.intent(view, now)
        for text in intent.withdrawn:
            mine = next((p for p in self.table.policies if p.text == text), None)
            if mine is not None:
                self.table.withdraw(mine.id)
                self._ended[mine.id] = round(now, 2)
                self._event("policy_withdrawn", "operator", f"policy {mine.id} withdrawn by the stream (four at most)", text,
                            {"policy": mine.id})  # fmt: skip
        for text, true_line in intent.arrivals:
            self._event("policy_in", "operator", "policy arrives", text, {"text": text})
            reading = self.read_policy(text, preview=False)
            if "error" in reading:
                self._event(
                    "unread", "operator", "the policy could not be read", reading["error"], {"text": text}
                )
                self.counts["unread"] += 1
                continue
            truth = validate(parse_spec(true_line), self.topology)
            right = validate(parse_spec(reading["line"]), self.topology).meaning() == truth.meaning()
            self._event("policy_read", "operator", f"reader: {reading['readback']}",
                        f"scope {reading['scope']}, " + ("until withdrawn" if reading["until"] is None else f"{reading['until']} h")
                        + ("" if right else " (differs from the recorded meaning)"),
                        {"line": reading["line"], "truth": true_line, "right": right, "tapi": reading["tapi"],
                         "seconds": reading["seconds"], "text": text})  # fmt: skip
            if not reading["applies"]:
                self._event(
                    "not_applied", "operator", f"not a policy the table can hold ({reading['status']})", text
                )
                self.counts["flagged"] += 1
                continue
            self.add_policy(text, reading["line"], truth=truth, source="stream")

    # ---- settings ----------------------------------------------------------------------------
    def settings(self, **changes) -> dict:
        for key in ("arrivals", "mix", "auto_answer"):
            if key in changes and changes[key] is not None:
                setattr(self, key, bool(changes[key]))
        self._event("settings", "inspect", "settings changed",
                    f"policies arrive on the stream: {self.arrivals}; instructions with requests: {self.mix}; "
                    f"simulated operator: {self.auto_answer}")  # fmt: skip
        return {
            "ok": True,
            "settings": {"arrivals": self.arrivals, "mix": self.mix, "auto_answer": self.auto_answer},
        }

    def request_detail(self, n: int) -> dict:
        """One request for the inspector: a decided one from the audit trail, or the pending one."""
        if 1 <= n <= len(self.audit):
            row = self.audit[n - 1]
            return {"ok": True, "decided": True, "row": row, "pruned": "inspect" not in row}
        if n == len(self.audit) + 1:
            view, now = self.episode.view, self.now
            standing = self.table.effective(view, now)
            return {"ok": True, "decided": False,
                    "row": {"n": n, "source": view.source, "destination": view.destination, "bit_rate": view.bit_rate,
                            "inspect": explain(view, standing if standing.applies else None, None,
                                               choose(view, standing if standing.applies else EMPTY)),
                            "effective": format_spec(standing, 3)}}  # fmt: skip
        return {"error": f"no request {n}"}

    # ---- the stream --------------------------------------------------------------------------
    def step(self, count: int) -> list[dict]:
        rows = []
        for _ in range(count):
            if self.question is not None:
                break
            row = self._process()
            if row is None:
                break
            rows.append(row)
        return rows

    def _understand(
        self, text: str, intent, view, standing: Spec, truth: Spec | None
    ) -> tuple[Spec | None, bool]:
        """The instruction's reading for this request, asking when it matters. ``(None, _)`` when a question is open."""
        if text in self._specs:
            return self._specs[text], text in self._asked
        if text in self._pending:
            first, other = self._pending[text]
            if choose(view, combine([first, standing])) == choose(view, combine([other, standing])):
                self._event(
                    "provisional",
                    "inspect",
                    "first reading kept",
                    "this request does not tell the two readings apart",
                )
                return first, False
            return self._ask(
                text,
                view,
                standing,
                [first, other],
                truth,
                "the two readings decide this request differently",
            )
        read = self._read_instruction(text)
        if read is None:
            why = "the model server did not answer" if self.live else "no model server and no record"
            self._event("unread", "operator", f"instruction not read: {why}", text)
            self.counts["unread"] += 1
            self._specs[text] = Spec(status="unread")
            return self._specs[text], False
        lines, specs, seconds = read
        differ = specs[0].meaning() != specs[1].meaning()
        self._event("reading", "operator", "readers agree: " + describe(specs[0]) if not differ else "readers differ",
                    None if not differ else f"reader 1: {describe(specs[0])}  |  reader 2: {describe(specs[1])}",
                    {"lines": lines, "seconds": [round(s, 2) for s in seconds], "statuses": [s.status for s in specs],
                     "tapi": constraints(specs[0], view)})  # fmt: skip
        if not differ:
            self._specs[text] = specs[0]
            return specs[0], False
        foreseeable = all(s.applies and not s.rest for s in specs)
        if foreseeable:
            self._pending[text] = (specs[0], specs[1])
            if choose(view, combine([specs[0], standing])) == choose(view, combine([specs[1], standing])):
                self._event("provisional", "operator", "first reading applied for now",
                            "the readings differ, but decide this request alike; you are asked when one tells them apart")  # fmt: skip
                return specs[0], False
            return self._ask(
                text, view, standing, specs, truth, "the two readings decide this request differently"
            )
        return self._ask(
            text,
            view,
            standing,
            specs,
            truth,
            "a reading that does not apply, or is carried in part, is asked about at once",
        )

    def _ask(
        self, text: str, view, standing: Spec, specs: list[Spec], truth: Spec | None, why: str
    ) -> tuple[Spec | None, bool]:
        self._questions += 1
        self._pending.pop(text, None)
        lines = [format_spec(s, 3) if s.applies or s.status == "unsupported" else s.status for s in specs]
        readings = self._readings(text, lines, specs, [0.0, 0.0], view, standing)
        true_line = None if truth is None else (format_spec(truth, 3) if truth.applies else truth.status)
        if self.auto_answer:
            spec = truth if truth is not None else specs[0]
            self._specs[text] = spec
            self._asked.add(text)
            self._event("question", "operator", "readers differ: the simulated operator answered",
                        "with the recorded meaning" if truth is not None else "no recorded meaning: the first reading stands",
                        {"text": text, "readings": readings, "why": why, "truth": true_line,
                         "answer": format_spec(spec, 3) if spec.applies else spec.status})  # fmt: skip
            return spec, True
        self.question = {"id": self._questions, "text": text, "why": why, "readings": readings, "truth": true_line,
                         "request": {"n": len(self.audit) + 1, "source": view.source, "destination": view.destination,
                                     "bit_rate": view.bit_rate}}  # fmt: skip
        self._event(
            "question", "operator", "readers differ: you are asked", why, {"text": text, "readings": readings}
        )
        return None, True

    def _decide(self, view, intent, spec: Spec, effective: Spec, covering, asked: bool) -> tuple:
        """``(choice, who, raw)`` for one request: the rule engine, or the decider with the guard."""
        engine = choose(view, effective if effective.applies else EMPTY)
        prefix = "asked+" if asked else ""
        policies = f" (policies {', '.join(str(p.id) for p in covering)})" if covering else ""
        if not self._forwarded(spec):
            body = format_spec(spec, 3) if spec.applies else spec.status
            return engine, "rule engine" + policies, prefix + body
        episode = self.episode
        carried = "\t" + format_spec(spec, 3) if spec.applies else ""
        try:
            (d,) = self.hybrid.decider.decide([Request(view, intent, episode.env, episode.info)])
        except (RuntimeError, ImportError, OSError):
            self._event("decider", "operator", "outside the language: the decider would decide, but there is no model server",
                        "the rule engine stands in under what the line carries")  # fmt: skip
            return (
                engine,
                "rule engine (decider offline)" + policies,
                prefix + "offline:" + (spec.status if not spec.applies else format_spec(spec, 3)),
            )
        self.counts["decider"] += 1
        choice, tag, who = d.choice if d.well_formed else None, "decider:", "decider"
        checkable = effective.applies and effective.constrains and d.well_formed and choice is not None
        if checkable and (choice[0] >= len(view.paths) or not meets(view.paths[choice[0]], effective)):
            self.counts["guarded"] += 1
            self._event("guard", "operator", "the decider's route broke a constraint the line carries; replaced by the rule engine's",
                        f"decider: {' - '.join(route_of(view, choice) or ['reject'])}  ->  {' - '.join(route_of(view, engine) or ['reject'])}")  # fmt: skip
            choice, tag, who = engine, "guard:", "decider, choice replaced by the guard"
        else:
            self._event("decider", "operator", "outside the language: the decider decided",
                        f"{' - '.join(route_of(view, choice) or ['reject'])} ({d.seconds:.1f} s)")  # fmt: skip
        return choice, who + policies, prefix + tag + (d.raw or "") + carried

    def _process(self) -> dict | None:
        """One request through the console; ``None`` when a question stopped it."""
        from sim import action_from_choice

        episode = self.episode
        view, now, n = episode.view, self.now, len(self.audit) + 1
        for policy in self.table.expire(now):
            self._event(
                "policy_expired",
                "operator",
                f"policy {policy.id} expired",
                policy.text,
                {"policy": policy.id},
            )
        self.truth.expire(now)
        if self.arrivals:
            self._arrivals(view, now)
        covering = self.table.applicable(view, now)
        standing = self.table.effective(view, now)
        if self.override is not None:
            text, intent = self.override, Intent(text=self.override)
            truth = None
        elif self.mix:
            text, intent = episode.intent.text, episode.intent
            truth = meant(intent) if isinstance(intent, mixed3.Instruction) else EMPTY
        else:
            text, intent, truth = "none", Intent(text="none"), EMPTY
        if text != "none" and self._announced != n:
            self._announced = n
            kind = KINDS.get(getattr(intent, "kind", ""), "typed by you" if self.override is not None else "")
            self._event("instruction", "operator", f"request {n} carries an instruction" + (f" ({kind})" if kind else ""), text,
                        {"text": text, "kind": getattr(intent, "kind", "typed"), "lang": getattr(intent, "lang", "")})  # fmt: skip
        spec, asked = (
            self._understand(text, intent, view, standing, truth) if text != "none" else (EMPTY, False)
        )
        if spec is None:
            return None
        applies = spec.applies and spec.status != "unread"
        effective = combine([spec.routing(), standing]) if applies else standing
        choice, who, raw = self._decide(view, intent, spec, effective, covering, asked)
        analysis = episode.env.simulator.current_analysis
        invalid = choice is not None and action_from_choice(analysis, choice) is None
        if invalid:
            choice = None
        # The verdict: against what was meant, instruction and policies together. A typed instruction
        # means what the operator confirmed; a recorded one its recorded meaning; a type outside the
        # language is judged by its own rule, without the policies, as the mixed evaluation does.
        meant_spec = spec if truth is None and applies else truth
        policy_truth = self.truth.effective(view, now)
        parts = (
            [meant_spec.routing()] if meant_spec is not None and meant_spec.applies and text != "none" else []
        ) + [policy_truth]
        truth_line = combine(parts)
        if text != "none" and truth is not None and truth.status == "unsupported":
            ok = respected(view, intent, choice)
            judged = "the instruction's own rule, policies aside"
        elif parts[:-1] or covering:
            ok = respects(view, truth_line, choice)
            judged = (
                "the instruction and the policies together"
                if parts[:-1] and covering
                else ("the instruction" if parts[:-1] else "the policies")
            )
        else:
            ok, judged = None, None
        # Per policy: did the chosen route break a constraint the policy truly states? (A newer
        # preference may outrank a policy's; that is the table's rule, not a breach.)
        true_by_text = {p.text: p.spec for p in self.truth.policies}
        broken = [p.id for p in covering if choice is not None and p.text in true_by_text
                  and not meets(view.paths[choice[0]], true_by_text[p.text].routing())]  # fmt: skip
        ok_policies = None if not covering or choice is None else not broken
        self.table.record(view, now, choice, choose(view, EMPTY), ok_policies)
        flagged = spec.status in NOT_APPLIED or spec.status == "unread" or (applies and spec.rest)
        self.counts.update({"served": 1, "rejected": choice is None, "violations": ok is False,
                            "policy_violations": ok_policies is False, "flagged": flagged and text != "none"})  # fmt: skip
        route = route_of(view, choice)
        row = {"n": n, "hour": round(now, 2), "source": view.source, "destination": view.destination, "bit_rate": view.bit_rate,
               "instruction": text, "kind": getattr(intent, "kind", "typed" if text != "none" else "none"),
               "line": (format_spec(spec, 3) if applies else spec.status) if text != "none" else "none",
               "policies": [p.id for p in covering], "effective": format_spec(effective, 3) if covering or applies else "none",
               "who": who, "asked": asked, "answer": raw, "path": choice[0] if choice else None,
               "slot": choice[1] if choice else None, "route": route, "blocked": choice is None, "invalid": invalid,
               "respects": ok, "judged": judged, "respects_policies": ok_policies, "broken": broken,
               "truth": None if truth is None or text == "none" else (format_spec(truth, 3) if truth.applies else truth.status),
               "meant": format_spec(truth_line, 3) if parts[:-1] or covering else None,
               "tapi": constraints(effective, view) if (covering or applies) else None}  # fmt: skip
        model, alloc = episode.env.simulator.topology, episode.env.simulator.state.slot_allocation
        row["used"] = [
            round(float((alloc[link.id] >= 0).mean()), 3) for link in model.links
        ]  # before the decision
        engine_choice = choose(view, effective if effective.applies else EMPTY)
        row["inspect"] = explain(view, effective if (covering or applies) else None, choice, engine_choice)
        row["spectrum"] = spectrum(episode.env, view, choice)
        self.series.append(
            (
                int(ok is False),
                int(choice is None),
                int(asked),
                int(who.startswith("decider")),
                int("guard" in who),
            )
        )
        episode.intent = intent
        episode.apply(Decision(choice, True, raw))
        self.override = None
        self.last_route = route
        self.audit.append(row)
        # a long session keeps the candidates and the spectrum of the last requests only
        if len(self.audit) > DETAIL:
            for key in HEAVY:
                self.audit[-DETAIL - 1].pop(key, None)
        verdict = "" if ok is None else (f"; respects {judged}" if ok else f"; BREAKS {judged}")
        if broken:
            verdict += f"; breaks a constraint of {'policy' if len(broken) == 1 else 'policies'} {', '.join(str(i) for i in broken)}"
        self._event("decision", "operator",
                    f"request {n}: {view.source} to {view.destination}, {view.bit_rate}G: " + (" - ".join(route) if route else "rejected"),
                    f"{who}" + (f", slot {choice[1]}" if choice else "") + verdict,
                    {"n": n, "route": route, "who": who, "policies": row["policies"], "line": row["effective"], "meant": row["meant"],
                     "respects": ok, "respects_policies": ok_policies, "tapi": row["tapi"]})  # fmt: skip
        return row


class Handler(BaseHTTPRequestHandler):
    console: Console

    def log_message(self, format: str, *args) -> None:
        if getattr(self.server, "verbose", False):
            super().log_message(format, *args)

    def _json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, cache: bool = False) -> None:
        body = path.read_bytes()
        kind = TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header(
            "Content-Type",
            kind + ("; charset=utf-8" if kind.startswith("text/") or kind.endswith("javascript") else ""),
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=31536000, immutable" if cache else "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        console = self.console
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        if path in ("/", "/index.html"):
            self._file(DIST / "index.html" if (DIST / "index.html").exists() else PAGE)
        elif path == "/legacy":
            self._file(PAGE)
        elif path.startswith("/assets/") and DIST.exists():
            target = (DIST / path.lstrip("/")).resolve()
            if target.is_file() and target.is_relative_to((DIST / "assets").resolve()):
                self._file(target, cache=True)  # hashed names: a new build is a new file
            else:
                self._json({"error": "not found"}, 404)
        elif path == "/api/state":
            with console.lock:
                self._json(console.state())
        elif path == "/api/recorded":
            self._json(console.recorded)
        elif path == "/api/request":
            try:
                n = int(query.get("n", ["0"])[0])
            except ValueError:
                n = 0
            with console.lock:
                self._json(console.request_detail(n))
        elif path == "/api/race":
            race = console.race
            self._json(race.state() if race else {"status": "off"})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        try:
            self._post()
        except (TypeError, ValueError, OverflowError) as error:  # a number that is not one, say
            self._json({"error": f"bad request: {error}"}, 400)

    def _post(self) -> None:
        console = self.console
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 <= length <= MAX_BODY:
            self._json({"error": "body too large"}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "bad JSON"}, 400)
            return
        if not isinstance(payload, dict):
            self._json({"error": "the body must be a JSON object"}, 400)
            return
        text = str(payload.get("text", ""))
        if self.path == "/api/race/start":  # the race has its own simulators and lock
            load, seed = int(payload.get("load", 390)), int(payload.get("seed", 1))
            with console.race_lock:  # a second click while the same race is being prepared starts nothing new
                race = console.race
                if race is None or race.status != "preparing" or (race.load, race.seed) != (load, seed):
                    try:
                        race = console.race = Race(load, seed, console.args.topology)
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                        return
            self._json(race.state())
            return
        if self.path == "/api/race/step":
            race = console.race
            if race is None:
                self._json({"error": "no race: start one first"}, 400)
                return
            done = race.step(max(1, min(int(payload.get("count", 1)), 100)))
            self._json(race.state() | {"done": done})
            return
        with console.lock:
            if self.path == "/api/step":
                count = max(1, min(int(payload.get("count", 1)), 200))
                rows = [{k: v for k, v in row.items() if k not in HEAVY} for row in console.step(count)]
                self._json({"rows": rows, "state": console.state()})
            elif self.path == "/api/instruction":
                self._json(console.read_instruction(text))
            elif self.path == "/api/instruction/confirm":
                self._json(console.confirm_instruction(text, str(payload.get("line", ""))))
            elif self.path == "/api/answer":
                self._json(
                    console.answer(
                        int(payload.get("id", 0)), payload.get("choice", "1"), str(payload.get("line", ""))
                    )
                )
            elif self.path == "/api/policy/read":
                self._json(console.read_policy(text))
            elif self.path == "/api/policy/add":
                self._json(console.add_policy(text, str(payload.get("line", ""))))
            elif self.path == "/api/policy/withdraw":
                self._json(console.withdraw_policy(int(payload.get("id", 0))))
            elif self.path == "/api/settings":
                self._json(
                    console.settings(**{k: payload.get(k) for k in ("arrivals", "mix", "auto_answer")})
                )
            else:
                self._json({"error": "not found"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--topology", default="nobel-eu")
    parser.add_argument("--load", type=int, default=390)
    parser.add_argument("--seed", type=int, default=1, help="1 to 3 at load 240 or 390 are fully recorded")
    parser.add_argument(
        "--warmup", type=int, default=1000, help="as in the evaluation, so recorded answers match"
    )
    parser.add_argument("--horizon", type=int, default=100, help="requests simulated for a policy's preview")
    parser.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", ""))
    parser.add_argument("--policy", default=None, help="hybrid with two readers (default by mode)")
    parser.add_argument("--decider", default=None, help="decider policy name (default by mode)")
    parser.add_argument("--reader", default=None, help="the reader of standing policies (default by mode)")
    parser.add_argument(
        "--no-arrivals", dest="arrivals", action="store_false", help="no policies from the stream"
    )
    parser.add_argument(
        "--no-mix", dest="mix", action="store_false", help="requests carry no instruction unless typed"
    )
    parser.add_argument("--auto-answer", action="store_true", help="the simulated operator answers questions")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    print("building the simulator and the policies ...", flush=True)
    if not (DIST / "index.html").exists():
        print(
            "note: no built frontend in src/console_ui/dist (npm ci && npm run build there); serving console.html",
            flush=True,
        )
    Handler.console = Console(args)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.verbose = args.verbose  # type: ignore[attr-defined]
    recorded = Handler.console.recorded
    mode = (
        f"live at {args.base_url}"
        if args.base_url
        else f"recorded answers only ({len(recorded['instructions'])} instructions, {len(recorded['policies'])} policies)"
    )
    print(
        f"console: http://{args.host}:{args.port}/  ({mode}; {args.topology}, load {args.load}, seed {args.seed})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
