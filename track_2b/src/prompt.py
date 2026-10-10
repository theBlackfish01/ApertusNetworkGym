"""Prompt and answer format (SPEC section 4): request view -> prompt text, answer text -> choice.

The user message lists, for each candidate path, what the intent rules need: hops and km (I2),
free slots on the path (I3), slots needed at the best modulation (I4), the first blocks of valid
start slots, and the route node by node, from which the links follow (I1). Example:

    Request: Berlin -> Prague, 100 Gb/s.
    Intent: Avoid the Berlin-Munich link for this request.
    Network: 320 slots per link, free ratio 0.61.
    Candidates (path: hops, km, best modulation, slots needed, free slots on path, free blocks [start-length]):
    0: 3 hops, 1240 km, QPSK, 9 slots, 156 free, blocks [12-15] [88-41] [220-100]
    1: 4 hops, 1410 km, QPSK, 9 slots, 100 free, blocks [120-30] [250-70]
    2: 5 hops, 2100 km, none
    Route per path: 0: Berlin-Munich-Vienna-Prague ; 1: Berlin-Hamburg-Warsaw-Vienna-Prague ; 2: ...
    Answer format: path=<0-4> slot=<n>  or  reject

A block ``[start-length]`` is a run of free spectrum in which the request is valid (resources
and QoT) at the path's best modulation wherever it is placed, so every teacher answer is the
start of a listed block. At most ``MAX_BLOCKS`` blocks per path are listed, lowest first.

Routes list each node once instead of every link pair: with the Apertus tokenizer that brings
the user message from 468 to 428 tokens on average (83 % of prompts under 450 instead of 29 %).
"""

from __future__ import annotations

import re

from intents import Intent
from view import MAX_BLOCKS, Choice, RequestView

SYSTEM = (
    "You are a lightpath provisioning controller. Choose a path and start slot for the request, "
    "or reject. Answer with exactly one line."
)
ANSWER_REGEX = r"^(path=[0-4] slot=\d{1,3}|reject)$"  # also the structured-output constraint at decode time
_ANSWER = re.compile(r"path=([0-4]) slot=(\d{1,3})|reject")
HEADER = "Candidates (path: hops, km, best modulation, slots needed, free slots on path, free blocks [start-length]):"
ANSWER_FORMAT = "Answer format: path=<0-4> slot=<n>  or  reject"


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else noun + "s"


def render_prompt(view: RequestView, intent: Intent) -> str:
    """The user message for one request."""
    lines = [
        f"Request: {view.source} -> {view.destination}, {view.bit_rate} Gb/s.",
        f"Intent: {intent.text}",
        f"Network: {view.num_slots} slots per link, free ratio {view.free_ratio:.2f}.",
        HEADER,
    ]
    for path in view.paths:
        head = f"{path.index}: {path.hops} {_plural(path.hops, 'hop')}, {path.km} km"
        if path.feasible:
            blocks = " ".join(f"[{start}-{length}]" for start, length in path.blocks[:MAX_BLOCKS])
            needed = f"{path.slots_needed} {_plural(path.slots_needed, 'slot')}"
            lines.append(f"{head}, {path.modulation}, {needed}, {path.free_slots} free, blocks {blocks}")
        else:
            lines.append(f"{head}, none")
    routes = " ; ".join(f"{path.index}: " + "-".join(path.nodes) for path in view.paths)
    lines += [f"Route per path: {routes}", ANSWER_FORMAT]
    return "\n".join(lines)


def chat_messages(view: RequestView, intent: Intent) -> list[dict[str, str]]:
    """System and user messages, as sent to the chat endpoint and stored in the dataset."""
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": render_prompt(view, intent)},
    ]


def format_choice(choice: Choice) -> str:
    """The assistant answer for a choice: ``path=1 slot=120`` or ``reject``."""
    return "reject" if choice is None else f"path={choice[0]} slot={choice[1]}"


def parse_answer(text: str) -> tuple[bool, Choice]:
    """``(well_formed, choice)`` for a model answer; surrounding whitespace is ignored.

    A malformed answer returns ``(False, None)``. Whether a well-formed choice is a valid action
    is decided by the simulator adapter (``sim.action_from_choice``), not here.
    """
    match = _ANSWER.fullmatch(text.strip())
    if match is None:
        return False, None
    if match.group(1) is None:
        return True, None
    return True, (int(match.group(1)), int(match.group(2)))
