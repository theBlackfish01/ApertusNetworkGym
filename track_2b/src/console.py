"""The operator console: the hybrid on a map of the network, one instruction at a time.

A page (``src/console.html``) served by this script. The operator types an instruction in any
language; both readers translate it; the page shows each reading as a line of the policy
language, as a sentence read back, and as a TAPI constraint; a preview runs the next requests
on a copy of the simulator under each reading and without any, and reports blocking and how
many decisions change. When the two readings differ, the preview also lists the first requests
on which they would decide differently, and the operator chooses. Once a reading is applied,
every request flows through the hybrid: the rule engine for what the language carries, the
decider for the rest; the audit trail lists per lightpath the instruction, the line, who decided,
and whether the decision respects the confirmed line. The map shows link occupation, the links
and nodes an instruction avoids or requires, and the route of the last decision.

    uv run python src/console.py                      # readers and decider from recorded answers
    uv run python src/console.py --base-url http://127.0.0.1:8089/v1   # live, behind llama.cpp

Without a server only instructions answered before can be read (the page lists them); with one,
anything can be typed. The simulator always runs: the episode starts after a warm-up at the
given load and seed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import threading
import xml.dom.minidom
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from evaluate import Episode, answer_tags
from intents import Intent
from policies import Decision
from spec import EMPTY, Spec, choose, describe, format_spec, load_topology, parse_spec, respects, validate
from tapi import constraints
from translate import format_version, make_hybrid_policy, messages, read_rows

ROOT = Path(__file__).resolve().parents[1]
PAGE = Path(__file__).with_name("console.html")
RECORDED_SETS = ("owner", "mix3", "v3_en", "v3_de", "v3_fr", "v3_it", "v3_new", "v3_partial", "v3_not")
NOT_APPLIED = ("unsupported", "no_instruction", "unresolved", "malformed")


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


class Console:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.Lock()
        self.live = bool(args.base_url)
        suffix = "live" if self.live else "laptop"
        self.policy_name = args.policy or f"hybrid3_ft_{suffix}_ask-ft2_{suffix}"
        self.decider_name = args.decider or f"apertus_ft_{suffix}"
        if self.live and "LLM_LORA_IDS" not in os.environ:
            os.environ["LLM_LORA_IDS"] = json.dumps(
                {f"translate3_ft_{suffix}": 0, f"translate3_ft2_{suffix}": 1, f"apertus_ft_{suffix}": 2}
            )
        self.topology = load_topology(args.topology)
        self.coordinates = node_coordinates(args.topology)
        job = {"policy": self.policy_name, "condition": "I0", "load": args.load, "seed": args.seed,
               "warmup": args.warmup, "window": 10**6}  # fmt: skip
        self.episode = Episode(job)
        self.policy = make_hybrid_policy(
            self.policy_name, args.topology, decider=self.decider_name,
            base_url=args.base_url or None, concurrency=1,
        )  # fmt: skip
        self.text, self.spec = "none", EMPTY
        self.audit: list[dict] = []
        self.last_route: tuple[str, ...] | None = None
        self.recorded = [] if self.live else self._recorded()

    # ---- what the page shows -----------------------------------------------------------------
    def _recorded(self) -> list[dict]:
        """Instructions both readers answered before, so the console works without a server."""
        readers = (self.policy.translator, self.policy.second)
        caches = [getattr(getattr(t, "llm", None), "_cache", {}) for t in readers]
        few = [getattr(t, "few", False) for t in readers]
        version = format_version(self.policy_name)
        paths = [ROOT / "data" / "instructions" / f"{name}.jsonl" for name in RECORDED_SETS]
        out, seen = [], set()
        for row in read_rows([p for p in paths if p.exists()]):
            text = row["text"]
            if text in seen:
                continue
            keys = [
                hashlib.sha256(
                    json.dumps(messages(text, self.topology, f, version), sort_keys=True).encode()
                ).hexdigest()
                for f in few
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

    def state(self) -> dict:
        env = self.episode.env
        model, alloc = env.simulator.topology, env.simulator.state.slot_allocation
        links = []
        for link in model.links:
            used = float((alloc[link.id] >= 0).mean())
            links.append(
                {
                    "a": link.source_name,
                    "b": link.target_name,
                    "km": round(link.length_km),
                    "used": round(used, 3),
                }
            )
        snap = env.simulator.statistics.snapshot()
        view = self.episode.view
        return {
            "topology": self.args.topology,
            "nodes": [{"name": n, "lon": x, "lat": y} for n, (x, y) in self.coordinates.items()],
            "links": links,
            "instruction": {"text": self.text, "line": format_spec(self.spec, 3) if self.spec.applies else self.spec.status,
                            "readback": describe(self.spec), "spec": self.spec.to_json()},
            "pending": {"source": view.source, "destination": view.destination, "bit_rate": view.bit_rate,
                        "paths": [list(p.nodes) for p in view.paths]},
            "last_route": list(self.last_route) if self.last_route else None,
            "stats": {"served": len(self.audit), "processed": int(snap.episode_services_processed),
                      "blocking": round(float(snap.episode_service_blocking_rate), 4),
                      "load": self.args.load, "seed": self.args.seed},
            "mode": {"live": self.live, "policy": self.policy_name, "decider": self.decider_name,
                     "base_url": self.args.base_url or ""},
            "audit": self.audit[-80:],
        }  # fmt: skip

    # ---- reading an instruction --------------------------------------------------------------
    def read(self, text: str) -> dict:
        text = " ".join(text.split()) or "none"
        view = self.episode.view
        if text == "none":
            specs, lines = [EMPTY, EMPTY], ["none", "none"]
        else:
            lines = []
            for translator in (self.policy.translator, self.policy.second):
                try:
                    lines.append(translator.lines([text])[0][0])
                except (RuntimeError, ImportError) as error:  # no server; a cache miss would load the model
                    return {"error": f"no model server, and this instruction was not read before ({error})"}
            specs = [validate(parse_spec(line), self.topology) for line in lines]
        differ = specs[0].meaning() != specs[1].meaning()
        readings = [
            {"reader": name, "line": line, "spec": spec.to_json(), "readback": describe(spec),
             "tapi": constraints(spec, view), "applies": spec.applies, "status": spec.status}
            for name, line, spec in zip(("reader 1", "reader 2"), lines, specs, strict=True)
        ]  # fmt: skip
        candidates: list[Spec] = []
        for spec in specs:
            effective = spec if spec.applies else EMPTY
            if all(effective.meaning() != c.meaning() for c in candidates):
                candidates.append(effective)
        return {"text": text, "readings": readings, "differ": differ, "preview": self.preview(candidates)}

    def _rollout(self, spec: Spec, horizon: int) -> list[dict]:
        """The next requests on a copy of the simulator, decided by the rule engine under ``spec``."""
        from optical_networking_gym.heuristics import select_first_fit_action

        from sim import action_from_choice, view_from_analysis

        env = copy.deepcopy(self.episode.env)
        rows = []
        for _ in range(horizon):
            analysis = env.simulator.current_analysis
            view = view_from_analysis(analysis)
            choice = choose(view, spec)
            action = action_from_choice(analysis, choice)
            if action is None:
                action = select_first_fit_action(env.action_masks())
            route = list(view.paths[choice[0]].nodes) if choice is not None else None
            rows.append({"source": view.source, "destination": view.destination, "bit_rate": view.bit_rate,
                         "path": choice[0] if choice else None, "route": route, "blocked": choice is None})  # fmt: skip
            env.step(action)
        return rows

    def preview(self, candidates: list[Spec]) -> dict:
        horizon = self.args.horizon
        base = self._rollout(EMPTY, horizon)
        runs = [self._rollout(spec, horizon) for spec in candidates]

        def summary(rows: list[dict]) -> dict:
            blocked = sum(r["blocked"] for r in rows)
            return {
                "requests": len(rows),
                "blocked": blocked,
                "blocking": round(blocked / max(len(rows), 1), 3),
            }

        out: dict = {"horizon": horizon, "without": summary(base), "readings": []}
        for spec, run in zip(candidates, runs, strict=True):
            changed = sum(a["path"] != b["path"] for a, b in zip(run, base, strict=True))
            out["readings"].append(summary(run) | {"line": format_spec(spec, 3), "changed": changed})
        if len(runs) == 2:
            differences = []
            for i, (a, b) in enumerate(zip(runs[0], runs[1], strict=True)):
                if a["path"] != b["path"]:
                    differences.append({"at": i + 1, "source": a["source"], "destination": a["destination"],
                                        "bit_rate": a["bit_rate"], "route1": a["route"], "route2": b["route"]})  # fmt: skip
                if len(differences) == 5:
                    break
            out["differences"] = differences
            out["decide_differently"] = sum(
                a["path"] != b["path"] for a, b in zip(runs[0], runs[1], strict=True)
            )
        return out

    # ---- applying and stepping ---------------------------------------------------------------
    def apply(self, text: str, line: str, asked: bool) -> dict:
        text = " ".join(text.split()) or "none"
        spec = EMPTY if text == "none" else validate(parse_spec(line), self.topology)
        if spec.status == "malformed":
            return {"error": f"not a line of the policy language: {line!r}"}
        self.text, self.spec = text, spec
        self.policy._specs[text] = spec  # what the operator confirmed is what the hybrid applies
        if asked:
            self.policy._asked.add(text)
        return {"ok": True, "instruction": {"text": text, "line": line, "readback": describe(spec)}}

    def step(self, count: int) -> list[dict]:
        from sim import action_from_choice

        rows = []
        for _ in range(count):
            episode = self.episode
            episode.intent = Intent(text=self.text)
            request = episode.request()
            view = request.view
            try:
                (decision,) = self.policy.decide([request])
            except (RuntimeError, ImportError):  # the decider is needed and there is no server
                carried = self.spec if self.spec.applies else EMPTY
                decision = Decision(choose(view, carried), raw="offline:" + format_spec(self.spec, 3))
            analysis = episode.env.simulator.current_analysis
            invalid = decision.well_formed and action_from_choice(analysis, decision.choice) is None
            choice = decision.choice if decision.well_formed and not invalid else None
            row = {
                "n": len(self.audit) + 1,
                "source": view.source, "destination": view.destination, "bit_rate": view.bit_rate,
                "instruction": self.text,
                "line": format_spec(self.spec, 3) if self.spec.applies else self.spec.status,
                "who": who_decided(decision.raw),
                "asked": answer_tags(decision.raw)["asked"],
                "answer": (decision.raw or "").removeprefix("asked+").split(chr(9))[0],
                "path": choice[0] if choice else None,
                "slot": choice[1] if choice else None,
                "route": list(view.paths[choice[0]].nodes) if choice else None,
                "blocked": choice is None,
                "invalid": invalid or not decision.well_formed,
                "respects": respects(view, self.spec, choice) if self.text != "none" and self.spec.applies and not invalid else None,
                "tapi": constraints(self.spec, view),
            }  # fmt: skip
            episode.apply(decision)
            self.last_route = tuple(row["route"]) if row["route"] else None
            self.audit.append(row)
            rows.append(row)
        return rows


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

    def do_GET(self) -> None:
        console = self.console
        if self.path in ("/", "/index.html"):
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/state":
            with console.lock:
                self._json(console.state())
        elif self.path == "/api/recorded":
            self._json(console.recorded)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        console = self.console
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "bad JSON"}, 400)
            return
        with console.lock:
            if self.path == "/api/read":
                self._json(console.read(str(payload.get("text", ""))))
            elif self.path == "/api/apply":
                self._json(console.apply(str(payload.get("text", "")), str(payload.get("line", "")),
                                         bool(payload.get("asked", False))))  # fmt: skip
            elif self.path == "/api/step":
                count = max(1, min(int(payload.get("count", 1)), 200))
                self._json({"rows": console.step(count), "state": console.state()})
            else:
                self._json({"error": "not found"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--topology", default="nobel-eu")
    parser.add_argument("--load", type=int, default=390)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--warmup", type=int, default=300)
    parser.add_argument("--horizon", type=int, default=100, help="requests simulated for the preview")
    parser.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", ""))
    parser.add_argument("--policy", default=None, help="hybrid policy name (default by mode)")
    parser.add_argument("--decider", default=None, help="decider policy name (default by mode)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    print("building the simulator and the policies ...", flush=True)
    Handler.console = Console(args)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.verbose = args.verbose  # type: ignore[attr-defined]
    mode = (
        f"live at {args.base_url}"
        if args.base_url
        else f"recorded answers only ({len(Handler.console.recorded)} instructions)"
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
