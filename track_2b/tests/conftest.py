"""Shared hand-built request for tests that need no simulator."""

import pytest

from view import PathView, RequestView


def make_path(index, nodes, km, free, modulation="QPSK", slots=9, blocks=((10, 20),)):
    if modulation is None:
        slots, blocks = None, ()
    return PathView(index, tuple(nodes), km, free, modulation, slots, tuple(blocks))


@pytest.fixture
def view():
    return RequestView(
        source="Berlin",
        destination="Prague",
        bit_rate=100,
        num_slots=320,
        free_ratio=0.61,
        paths=(
            # 0: fewest hops, but its first block starts late and it is the fullest
            make_path(0, ["Berlin", "Munich", "Prague"], 900, 60, "QPSK", 9, [(88, 41), (220, 100)]),
            # 1: lowest start slot (BM-LS-KSP choice), most free slots
            make_path(
                1, ["Berlin", "Hamburg", "Vienna", "Prague"], 1410, 150, "QPSK", 9, [(12, 15), (120, 30)]
            ),
            # 2: fewest slots needed, same hop count as path 1
            make_path(2, ["Berlin", "Warsaw", "Vienna", "Prague"], 1500, 100, "16QAM", 5, [(40, 8)]),
            # 3: infeasible
            make_path(3, ["Berlin", "Munich", "Vienna", "Zagreb", "Prague"], 2100, 0, None),
        ),
    )
