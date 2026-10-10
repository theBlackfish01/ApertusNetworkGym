"""Policies without the simulator: the LLM client against a mock endpoint, and the MLP control."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from intents import NO_INTENT, Intent
from mlp import MLP, N_FEATURES, REJECT, features, label, train
from policies import LLMPolicy, Oracle, Request
from prompt import ANSWER_REGEX


@pytest.fixture
def endpoint():
    """A chat-completions server that answers with ``state["answer"]`` and records the bodies."""
    state = {"answer": "path=1 slot=12", "bodies": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["bodies"].append(body)
            payload = json.dumps({"choices": [{"message": {"content": state["answer"]}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{server.server_port}/v1"
    yield state
    server.shutdown()


def test_llm_policy_asks_with_the_answer_regex_caches_and_replays(endpoint, view, tmp_path):
    cache = tmp_path / "answers.jsonl"
    policy = LLMPolicy("mock", base_url=endpoint["url"], model="apertus", cache=cache)
    requests = [Request(view, NO_INTENT), Request(view, Intent(("I2",), "Use the fewest hops."))]
    decisions = policy.decide(requests)
    assert [d.choice for d in decisions] == [(1, 12), (1, 12)] and all(d.well_formed for d in decisions)
    body = endpoint["bodies"][0]
    assert body["model"] == "apertus" and body["temperature"] == 0
    assert body["structured_outputs"] == {"regex": ANSWER_REGEX}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]

    # Same prompts again: served from the cache, also with no endpoint configured at all.
    asked = len(endpoint["bodies"])
    policy.decide(requests)
    replay = LLMPolicy("mock", base_url="", model="", cache=cache)
    assert [d.choice for d in replay.decide(requests)] == [(1, 12), (1, 12)]
    assert len(endpoint["bodies"]) == asked
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        replay.decide([Request(view, Intent(("I3",), "Something never asked before."))])


def test_llm_policy_flags_malformed_answers_and_older_vllm_field(endpoint, view, tmp_path):
    endpoint["answer"] = "I would pick path 1."
    policy = LLMPolicy(
        "mock", base_url=endpoint["url"], cache=tmp_path / "c.jsonl", structured="guided_regex"
    )
    (decision,) = policy.decide([Request(view, NO_INTENT)])
    assert not decision.well_formed and decision.choice is None and decision.raw == "I would pick path 1."
    assert endpoint["bodies"][0]["guided_regex"] == ANSWER_REGEX


def test_oracle_policy_is_the_intent_aware_teacher(view):
    (decision,) = Oracle().decide([Request(view, Intent(("I4",), "Fewest slots."))])
    assert decision.choice == (2, 40) and decision.well_formed


def test_mlp_features_and_labels(view):
    x = features(view, Intent(("I1", "I3"), "x", link=("Vienna", "Hamburg")))
    assert x.shape == (N_FEATURES,) and x.dtype == np.float32 and 0.0 <= x.min() and x.max() <= 1.0
    per_path = x[: 5 * 9].reshape(5, 9)
    assert per_path[:, 0].tolist() == [1, 1, 1, 0, 0]  # feasible flags; the fifth path is padding
    assert per_path[:, 8].tolist() == [0, 1, 0, 0, 0]  # only path 1 contains Hamburg-Vienna
    assert x[-4:].tolist() == [1, 0, 1, 0]  # I1 and I3 set
    assert label(None) == REJECT and label((3, 7)) == 3


def test_mlp_learns_a_simple_rule_and_round_trips(view, tmp_path):
    rng = np.random.default_rng(1)
    x = rng.random((600, N_FEATURES), dtype=np.float32)
    y = (x[:, 0] > 0.5).astype(np.int64) + 2 * (x[:, 1] > 0.5)  # four classes from two inputs
    model, info = train(x, y, epochs=60, seed=1)
    assert info["val_accuracy"] > 0.85
    model.save(tmp_path / "mlp.npz")
    loaded = MLP.load(tmp_path / "mlp.npz")
    assert np.allclose(loaded.logits(x[:5]), model.logits(x[:5]))
    choice = loaded.predict(view, NO_INTENT)
    assert choice is None or 0 <= choice[0] < 5
