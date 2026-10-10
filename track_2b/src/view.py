"""What a policy sees for one lightpath request: plain data, no simulator dependency.

``sim.view_from_analysis`` builds a :class:`RequestView` from ONG's request analysis. The
prompt (``prompt.py``), the intent rules (``intents.py``) and the MLP features (``mlp.py``) are
all computed from this view, so the language model and the numeric control are given the same
information. Views are JSON-serialisable and stored with every dataset record.

A decision is a :data:`Choice`: ``(path_index, start_slot)`` or ``None`` for reject. The
modulation is not part of it; the simulator adapter uses the most efficient format valid at
that path and slot (SPEC section 2).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

Choice = tuple[int, int] | None  # (path index, start slot); None = reject
MAX_BLOCKS = 3  # blocks listed per path in the prompt


@dataclass(frozen=True)
class PathView:
    index: int
    nodes: tuple[str, ...]
    km: int  # rounded, as shown in the prompt, so ties "by km" are decidable from the prompt
    free_slots: int  # slots free on every link of the path
    # Most efficient modulation with at least one valid (resource and QoT) start; None if the
    # path has no valid start at any modulation.
    modulation: str | None
    slots_needed: int | None  # at that modulation
    # Runs of start slots, as (start, length) in ascending order, at which the request is valid
    # in ``slots_needed`` slots: it can start anywhere from ``start`` to
    # ``start + length - slots_needed``. "Valid in slots_needed slots" means valid with the best
    # modulation or with another format that needs the same number of slots; several formats
    # often do (100 Gb/s takes 2 slots with 16QAM, 32QAM and 64QAM), and the simulator adapter
    # picks the most efficient one that passes QoT at the chosen slot.
    blocks: tuple[tuple[int, int], ...]

    @property
    def feasible(self) -> bool:
        return self.modulation is not None

    @property
    def hops(self) -> int:
        return len(self.nodes) - 1

    @property
    def links(self) -> tuple[tuple[str, str], ...]:
        return tuple(zip(self.nodes, self.nodes[1:], strict=False))

    @property
    def first_slot(self) -> int | None:
        return self.blocks[0][0] if self.blocks else None

    @property
    def largest_block(self) -> int:
        return max((length for _, length in self.blocks), default=0)

    def has_link(self, a: str, b: str) -> bool:
        return (a, b) in self.links or (b, a) in self.links

    def in_block(self, slot: int) -> bool:
        """Whether ``slot`` is a valid start in ``slots_needed`` slots (inside one of the blocks)."""
        if self.slots_needed is None:
            return False
        return any(start <= slot <= start + length - self.slots_needed for start, length in self.blocks)


@dataclass(frozen=True)
class RequestView:
    source: str
    destination: str
    bit_rate: int  # Gb/s
    num_slots: int  # slots per link
    free_ratio: float  # free slots over all links, two decimals
    paths: tuple[PathView, ...]

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> RequestView:
        paths = tuple(
            PathView(
                **{
                    **path,
                    "nodes": tuple(path["nodes"]),
                    "blocks": tuple((int(start), int(length)) for start, length in path["blocks"]),
                }
            )
            for path in data["paths"]
        )
        return cls(**{**data, "paths": paths})
