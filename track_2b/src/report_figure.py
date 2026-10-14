"""The report's figure: violations in closed loop on the mixed stream and on the standing-policy
stream, one bar per policy, read from the results files.

    uv run python src/report_figure.py        # docs/figures/violations.png
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
MIXED = [  # results/eval/<name>_mix3.json at 390 Erlang
    ("first_fit", "first fit"),
    ("apertus_ft", "decider\nalone"),
    ("apertus3_ft", "matched\ndecider"),
    ("translate3_ft", "reader +\nrule engine"),
    ("hybrid3_ft", "hybrid,\nguard"),
    ("hybrid3_ft_ask-ft2", "hybrid,\nasks"),
    ("hybrid3_ft_laptop_ask-ft2_laptop", "same,\n4-bit"),
]
STANDING = [  # results/eval/<name>_standing4.json at 240 and 390 Erlang
    ("standing_oracle", "true\ntable"),
    ("first_fit", "first fit"),
    ("standing_noscope", "scope\nignored"),
    ("standing_nountil", "lifetime\nignored"),
    ("standing4_ft", "reader's\ntable"),
    ("standing4_ft_laptop", "same,\n4-bit"),
    ("standing3_ft_laptop", "old\nformat"),
]


def violations(path: Path, load: int) -> float | None:
    if not path.exists():
        return None
    episodes = [e for e in json.loads(path.read_text(encoding="utf-8"))["episodes"] if e["load"] == load]
    return 100 * statistics.mean(e["violation_rate"] for e in episodes) if episodes else None


def main() -> None:
    results = ROOT / "results" / "eval"
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.4, 2.6), gridspec_kw={"width_ratios": [7.4, 6.6]})
    plt.rcParams.update({"font.size": 7.5})
    names, values = [], []
    for name, label in MIXED:
        v = violations(results / f"{name}_mix3.json", 390)
        if v is not None:
            names.append(label)
            values.append(v)
    bars = left.bar(
        range(len(values)), values, color=["#9a9890"] + ["#4a6fa5"] * (len(values) - 1), width=0.7
    )
    for b, v in zip(bars, values, strict=True):
        left.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:.1f}", ha="center", va="bottom", fontsize=7)
    left.set_xticks(range(len(names)), names, fontsize=6.6)
    left.set_ylabel("violations, % of requests", fontsize=7.5)
    left.set_title("Mixed stream of instructions, 390 Erlang", fontsize=8)
    left.set_ylim(0, max(values) * 1.18 if values else 1)
    for load, colour, shift in ((240, "#7fa3d1", -0.19), (390, "#1f4f8a", 0.19)):
        labels, vals = [], []
        for name, label in STANDING:
            v = violations(results / f"{name}_standing4.json", load)
            if v is not None:
                labels.append(label)
                vals.append(v)
        xs = [i + shift for i in range(len(vals))]
        right.bar(xs, vals, width=0.36, color=colour, label=f"{load} Erlang")
        for x, v in zip(xs, vals, strict=True):
            right.text(x, v + 0.5, f"{v:.1f}", ha="center", va="bottom", fontsize=6)
        right.set_xticks(range(len(labels)), labels, fontsize=6.4)
    right.set_title("Standing policies, against the true table", fontsize=8)
    right.legend(fontsize=6.5, frameon=False)
    for ax in (left, right):
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout(pad=0.6)
    out = ROOT / "docs" / "figures" / "violations.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
