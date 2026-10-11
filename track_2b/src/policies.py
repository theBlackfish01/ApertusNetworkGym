"""Policies under test (SPEC section 7).

Every policy maps pending requests to decisions through the same interface, so the evaluator
treats heuristics, the MLP and the language model identically:

    first_fit        ONG masked first fit (KSP-BM-FF baseline); ignores the intent
    teacher          ONG BM-LS-KSP (no-intent teacher); ignores the intent
    oracle           the intent-aware teacher of ``intents.py`` (upper bound for each condition)
    mlp              the numeric control of ``mlp.py``
    llm              Apertus, zero-shot or fine-tuned: behind an OpenAI-compatible endpoint (vLLM)
                     or loaded in this process with transformers; with ``shots`` a few solved
                     requests are put in front of every prompt (the few-shot decider)
    translate_*      the translator arm of ``translate.py``: the model (or a keyword parser) turns
                     the instruction into a spec once, and the rule engine of ``spec.py`` decides

``decide`` takes a list so the language model can be queried for many environments at once.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intents import Intent, teacher_choice
from mlp import MLP
from prompt import ANSWER_REGEX, chat_messages, parse_answer
from view import Choice, RequestView

ROOT = Path(__file__).resolve().parents[1]
HEURISTICS = {"first_fit": "first_fit", "teacher": "jocn_ls_bm_ksp"}  # policy name -> ONG heuristic
_LOADED: dict[tuple, Any] = {}  # (model, adapter) -> the LocalLLMPolicy that loaded it, to share the weights


@dataclass
class Request:
    """One pending request. ``env``/``info`` are only set (and needed) for ONG heuristics."""

    view: RequestView
    intent: Intent
    env: Any = None
    info: Any = None


@dataclass
class Decision:
    choice: Choice
    well_formed: bool = True  # False when a model answer did not match the answer format
    raw: str | None = None  # the model's text, for language-model policies
    seconds: float = 0.0  # time to produce this decision


class Policy:
    name: str = "policy"
    parallel_safe = True  # can run in worker processes (False for a policy that talks to one server)

    def decide(self, requests: list[Request]) -> list[Decision]:
        raise NotImplementedError

    def describe(self) -> dict:
        """What goes into the results metadata."""
        return {"name": self.name}


class Timed(Policy):
    """Base for policies that decide one request at a time on the CPU."""

    def choose(self, request: Request) -> Choice:
        raise NotImplementedError

    def decide(self, requests: list[Request]) -> list[Decision]:
        decisions = []
        for request in requests:
            started = time.perf_counter()
            choice = self.choose(request)
            decisions.append(Decision(choice, seconds=time.perf_counter() - started))
        return decisions


class OngHeuristic(Timed):
    def __init__(self, name: str) -> None:
        self.name, self.heuristic = name, HEURISTICS[name]

    def choose(self, request: Request) -> Choice:
        from optical_networking_gym.heuristics import select_heuristic_action

        from sim import choice_from_action

        action = select_heuristic_action(self.heuristic, request.env, request.info)
        return choice_from_action(request.env.simulator.current_analysis, action)

    def describe(self) -> dict:
        return {"name": self.name, "ong_heuristic": self.heuristic}


class Oracle(Timed):
    name = "oracle"

    def choose(self, request: Request) -> Choice:
        return teacher_choice(request.view, request.intent)


class MLPPolicy(Timed):
    name = "mlp"

    def __init__(self, weights: Path = ROOT / "results" / "mlp" / "mlp.npz") -> None:
        self.weights = weights
        self.model = MLP.load(weights)

    def choose(self, request: Request) -> Choice:
        return self.model.predict(request.view, request.intent)

    def describe(self) -> dict:
        return {"name": self.name, "weights": self.weights.name}


class CachedLLM(Policy):
    """Base of the language-model policies: prompt rendering, answer cache, answer parsing.

    Answers are cached per policy name (``results/cache/<name>.jsonl``), keyed by the chat
    messages only, so a finished run can be replayed, and its tables rebuilt, with no model,
    server or environment variable. Use a new policy name (or delete the file) for a different
    model or decoding setup.
    """

    parallel_safe = False

    def __init__(self, name: str, cache: Path | None = None, shots: list[dict] | None = None) -> None:
        self.name = name
        self.shots = list(shots or [])  # solved examples (user and assistant turns) after the system turn
        self.cache_path = cache or ROOT / "results" / "cache" / f"{name}.jsonl"
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        if self.cache_path.exists():
            with self.cache_path.open(encoding="utf-8") as handle:
                for line in handle:
                    entry = json.loads(line)
                    self._cache[entry["key"]] = entry

    def complete(self, prompts: list[list[dict]]) -> list[tuple[str, float]]:
        """``(answer text, seconds)`` for each prompt; only called for prompts not in the cache."""
        raise NotImplementedError

    def ask(self, prompts: list[list[dict]]) -> list[dict]:
        """The cache entry (``answer``, ``seconds``) of each prompt; the model is asked for new ones."""
        keys = [hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest() for p in prompts]
        missing = {key: prompt for key, prompt in zip(keys, prompts, strict=True) if key not in self._cache}
        if missing:
            answers = self.complete(list(missing.values()))
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, self.cache_path.open("a", encoding="utf-8") as handle:
                for key, (answer, seconds) in zip(missing, answers, strict=True):
                    entry = {"key": key, "answer": answer, "seconds": round(seconds, 4)}
                    self._cache[key] = entry
                    handle.write(json.dumps(entry) + "\n")
        return [self._cache[key] for key in keys]

    def decide(self, requests: list[Request]) -> list[Decision]:
        prompts = []
        for request in requests:
            system, user = chat_messages(request.view, request.intent)
            prompts.append([system, *self.shots, user])
        decisions = []
        for entry in self.ask(prompts):
            well_formed, choice = parse_answer(entry["answer"])
            decisions.append(Decision(choice, well_formed, entry["answer"], entry["seconds"]))
        return decisions


class LLMPolicy(CachedLLM):
    """Chat-completions client for an OpenAI-compatible endpoint (vLLM and similar).

    ``structured`` selects how the answer regex is sent: ``structured_outputs`` (current vLLM),
    ``guided_regex`` (older vLLM) or ``none`` (unconstrained). ``extra_body`` is merged into the
    request, e.g. chat-template arguments.
    """

    def __init__(
        self,
        name: str,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        structured: str = "structured_outputs",
        extra_body: dict | None = None,
        cache: Path | None = None,
        concurrency: int = 32,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(name, cache)
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/")
        self.model = model or os.environ.get("LLM_NAME", "")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.structured, self.extra_body = structured, dict(extra_body or {})
        self.concurrency, self.timeout = concurrency, timeout

    def describe(self) -> dict:
        return {"name": self.name, "backend": "endpoint", "model": self.model, "structured": self.structured,
                "extra_body": self.extra_body, "cache": self.cache_path.name}  # fmt: skip

    def _body(self, messages: list[dict]) -> dict:
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 16}
        if self.structured == "structured_outputs":
            body["structured_outputs"] = {"regex": ANSWER_REGEX}
        elif self.structured == "guided_regex":
            body["guided_regex"] = ANSWER_REGEX
        return body | self.extra_body

    def _ask(self, messages: list[dict]) -> tuple[str, float]:
        key = self.api_key or "none"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(self._body(messages)).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        started = time.perf_counter()
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                break
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt == 3 or (isinstance(error, urllib.error.HTTPError) and error.code < 500):
                    raise
                time.sleep(2.0**attempt)
        return payload["choices"][0]["message"]["content"] or "", time.perf_counter() - started

    def complete(self, prompts: list[list[dict]]) -> list[tuple[str, float]]:
        if not self.base_url:
            raise RuntimeError(
                f"{self.name}: answer not in {self.cache_path.name} and LLM_BASE_URL is not set"
            )
        with ThreadPoolExecutor(max_workers=max(1, min(self.concurrency, len(prompts)))) as pool:
            return list(pool.map(self._ask, prompts))


class LocalLLMPolicy(CachedLLM):
    """The model loaded in this process with ``transformers`` (used next to the GPU in a job).

    Greedy decoding in batches. With ``structured="regex"`` every step is restricted by
    ``decoding.TokenAutomaton`` to tokens that keep the output a valid answer, which is the same
    constraint a server applies with structured outputs; ``"none"`` decodes freely for at most
    16 new tokens. ``adapter`` is a LoRA adapter merged into the base model at load time.
    The model is loaded on first use, so replaying a cached run never needs it.

    ``grammar`` (a ``grammar.Dfa``) replaces the decision format as the constraint and
    ``max_new_tokens`` the length limit; the translator uses both for its answer lines.
    """

    MAX_NEW_TOKENS = 18  # the longest answer is 15 characters plus the end token

    def __init__(
        self,
        name: str,
        *,
        model: str | None = None,
        adapter: str | None = None,
        structured: str = "regex",
        template_kwargs: dict | None = None,
        cache: Path | None = None,
        max_batch: int = 64,
        shots: list[dict] | None = None,
        grammar: Any = None,
        max_new_tokens: int | None = None,
    ) -> None:
        super().__init__(name, cache, shots)
        self.model_id = model or os.environ.get("LLM_NAME", "")
        self.grammar, self.max_new_tokens = grammar, max_new_tokens
        self.adapter, self.structured = adapter, structured
        self.template_kwargs, self.max_batch = dict(template_kwargs or {}), max_batch
        self._model = None

    def describe(self) -> dict:
        return {"name": self.name, "backend": "transformers", "model": self.model_id, "adapter": self.adapter,
                "structured": self.structured, "template_kwargs": self.template_kwargs,
                "shots": len(self.shots) // 2, "cache": self.cache_path.name}  # fmt: skip

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not self.model_id:
            raise RuntimeError(f"{self.name}: answer not in {self.cache_path.name} and no model was given")
        self._torch = torch
        first = _LOADED.get((self.model_id, self.adapter))
        if first is not None:  # several policies of one process (translator variants) share the weights
            for field in ("_tokenizer", "_model", "_eos", "_head", "_last_only"):
                setattr(self, field, getattr(first, field))
            self._constrain(self._tokenizer, self._model)
            return
        cuda = torch.cuda.is_available()
        tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        tokenizer.padding_side = "left"
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            dtype=torch.bfloat16 if cuda else torch.float32,
            device_map="auto" if cuda else None,
        )
        if self.adapter:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, self.adapter).merge_and_unload()
        model.eval()
        eos = model.generation_config.eos_token_id
        self._eos = sorted({tokenizer.eos_token_id, *(eos if isinstance(eos, list) else [eos])} - {None})
        self._tokenizer, self._model = tokenizer, model
        # Only the last position's logits are needed. Projecting just that position through the
        # output head avoids a [batch, tokens, vocabulary] tensor (gigabytes for a full batch).
        # Checked once against the model's own forward; if the two disagree, use the full forward.
        self._head, self._last_only = model.get_output_embeddings(), False
        try:
            probe = tokenizer(["path=1 slot=", "reject"], return_tensors="pt", padding=True).to(model.device)
            with torch.no_grad():
                full = model(**probe).logits[:, -1, :].float()
                self._last_only = True
                last, _ = self._forward(**probe)
            same = bool((full.argmax(-1) == last.argmax(-1)).all()) and float((full - last).abs().max()) < 0.1
            self._last_only = same
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self._last_only = False
        _LOADED[(self.model_id, self.adapter)] = self
        self._constrain(tokenizer, model)

    def _constrain(self, tokenizer, model) -> None:
        """Build the token automaton of this policy's answer format."""
        from decoding import TokenAutomaton

        torch = self._torch
        if self.structured == "regex":
            strings = tokenizer.batch_decode([[i] for i in range(len(tokenizer))], skip_special_tokens=False)
            if self.grammar is None:
                self._automaton = TokenAutomaton(strings, self._eos)
            else:
                from grammar import TokenAutomaton as GrammarAutomaton

                self._automaton = GrammarAutomaton(self.grammar, strings, self._eos)
            self._allowed = {
                state: torch.tensor(self._automaton.allowed(state), device=model.device)
                for state in self._automaton.next
            }

    def _forward(self, **inputs):
        """``(logits of the last position as float32, key-value cache)``."""
        if self._last_only:
            hidden = self._model.base_model(**inputs, use_cache=True)
            return self._head(hidden.last_hidden_state[:, -1, :]).float(), hidden.past_key_values
        output = self._model(**inputs, use_cache=True)
        return output.logits[:, -1, :].float(), output.past_key_values

    def _generate(self, prompts: list[list[dict]]) -> list[str]:
        from decoding import DONE, START

        torch, tokenizer, model = self._torch, self._tokenizer, self._model
        texts = [
            tokenizer.apply_chat_template(
                p, tokenize=False, add_generation_prompt=True, **self.template_kwargs
            )
            for p in prompts
        ]
        batch = tokenizer(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
        mask = batch["attention_mask"]
        rows = len(prompts)
        states, done, generated = [START] * rows, [False] * rows, [[] for _ in range(rows)]
        constrained = self.structured == "regex"
        with torch.no_grad():
            logits, past = self._forward(input_ids=batch["input_ids"], attention_mask=mask)
            for _ in range(self.max_new_tokens or (self.MAX_NEW_TOKENS if constrained else 16)):
                if constrained:
                    bias = torch.full_like(logits, float("-inf"))
                    for row in range(rows):
                        bias[row, self._eos[0] if done[row] else self._allowed[states[row]]] = 0.0
                    logits = logits + bias
                chosen = logits.argmax(dim=-1)
                for row, token in enumerate(chosen.tolist()):
                    if done[row]:
                        continue
                    if token in self._eos:
                        done[row] = True
                    else:
                        generated[row].append(token)
                        if constrained:
                            states[row] = self._automaton.next[states[row]][token]
                            done[row] = states[row] == DONE
                if all(done):
                    break
                mask = torch.cat([mask, mask.new_ones((rows, 1))], dim=1)
                logits, past = self._forward(
                    input_ids=chosen[:, None], attention_mask=mask, past_key_values=past
                )
        return [tokenizer.decode(tokens, skip_special_tokens=True).strip() for tokens in generated]

    def complete(self, prompts: list[list[dict]]) -> list[tuple[str, float]]:
        if self._model is None:
            self._load()
        answers: list[tuple[str, float]] = []
        for start in range(0, len(prompts), self.max_batch):
            chunk = prompts[start : start + self.max_batch]
            started = time.perf_counter()
            texts = self._generate(chunk)
            elapsed = time.perf_counter() - started  # every request in the batch waited this long
            answers += [(text, elapsed) for text in texts]
        return answers


def make_policy(name: str, *, backend: str = "endpoint", **llm_options) -> Policy:
    """``first_fit``, ``teacher``, ``oracle``, ``mlp``, ``translate_*``, or any other name for a language-model run.

    For a language model, ``backend`` is ``endpoint`` (an OpenAI-compatible server) or
    ``transformers`` (the model loaded in this process).
    """
    if name in HEURISTICS:
        return OngHeuristic(name)
    if name == "oracle":
        return Oracle()
    if name == "mlp":
        return MLPPolicy()
    if name.startswith("translate_"):
        from translate import make_translator_policy

        return make_translator_policy(name, **llm_options)
    if backend == "transformers":
        return LocalLLMPolicy(name, **llm_options)
    return LLMPolicy(name, **llm_options)
