"""Results JSON -> tables and the figure (SPEC section 7 deliverable).

Reads every ``results/eval/<policy>.json`` and ``results/offline/<policy>.json`` and writes

    results/tables/results.md      closed-loop tables per load + the offline agreement table
    results/tables/results.tex     the same closed-loop tables as LaTeX tabulars
    docs/figures/blocking.png/.pdf blocking per condition for the oracle, MLP and Apertus runs

Nothing here computes a metric: every number is the mean and sample standard deviation over
seeds stored in the results files. Policies without a results file are simply absent, so the
table grows as runs finish. ``make run`` prints ``results.md``.

    uv run python src/report_tables.py            # write the files and print the markdown
    uv run python src/report_tables.py --no-figure
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {  # display order and names; other result files are appended under their own name
    "first_fit": "KSP-BM-FF first fit",
    "teacher": "BM-LS-KSP (no-intent teacher)",
    "oracle": "Intent-aware teacher (oracle)",
    "mlp": "MLP control",
    "apertus_zero_shot": "Apertus 8B zero-shot",
    "apertus_ft": "Apertus 8B fine-tuned",
}
CONDITIONS = {
    "I0": "No intent",
    "I1": "Avoid link",
    "I2": "Fewest hops",
    "I3": "Least loaded",
    "I4": "Fewest slots",
    "mixed_heldout_paraphrases": "Unseen wording",
    "heldout_pairs": "Unseen pairs",
}
TABLES = {  # metric -> (title, decimals); values are rates shown in percent
    "service_blocking_rate": ("Service blocking probability, %", 2),
    "violation_rate": ("Intent violations, % of decisions", 1),
    "invalid_rate": ("Invalid answers, % of decisions", 2),
}
SPLITS = {
    "heldout_indist": "In distribution",
    "heldout_paraphrase": "Unseen wording",
    "heldout_pairs": "Unseen pairs",
}
# Figure series: colour follows the policy (fixed order of the validated categorical palette).
FIGURE_SERIES = {
    "oracle": "#2a78d6",
    "mlp": "#eb6834",
    "apertus_ft": "#1baf7a",
    "apertus_zero_shot": "#eda100",
}
INK, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def load(directory: Path) -> dict[str, dict]:
    found = {path.stem: json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))}
    ordered = [name for name in POLICIES if name in found] + [name for name in found if name not in POLICIES]
    return {name: found[name] for name in ordered}


def cell(entry: dict | None, metric: str, decimals: int) -> str:
    if entry is None:
        return "–"
    return f"{100 * entry[f'{metric}_mean']:.{decimals}f} ± {100 * entry[f'{metric}_std']:.{decimals}f}"


def closed_tables(results: dict[str, dict]) -> list[tuple[str, list[str], list[list[str]]]]:
    """``(title, header, rows)`` for every load and metric, plus decision latency."""
    tables = []
    loads = sorted({e["load"] for r in results.values() for e in r["summary"]})
    conditions = [
        c for c in CONDITIONS if any(e["condition"] == c for r in results.values() for e in r["summary"])
    ]
    for load in loads:
        index = {
            (name, e["condition"]): e
            for name, r in results.items()
            for e in r["summary"]
            if e["load"] == load
        }
        for metric, (title, decimals) in TABLES.items():
            rows = [
                [POLICIES.get(name, name)]
                + [cell(index.get((name, c)), metric, decimals) for c in conditions]
                for name in results
            ]
            tables.append(
                (f"{title} — load {load} E", ["Policy"] + [CONDITIONS[c] for c in conditions], rows)
            )
    rows = []
    for name, result in results.items():
        times = [e["decision_ms_mean"] for e in result["summary"]]
        bound = [e["binding_violation_rate"] for e in result["summary"] if e["condition"] != "I0"]
        rows.append([
            POLICIES.get(name, name),
            f"{sum(times) / len(times):.2f}",
            f"{100 * sum(bound) / len(bound):.1f}" if bound else "–",
            ", ".join(str(s) for s in result["metadata"]["seeds"]),
        ])  # fmt: skip
    header = ["Policy", "ms per decision", "Violations where the intent binds, %", "Seeds"]
    tables.append(
        ("Decision latency and violations on binding requests (all loads and conditions)", header, rows)
    )
    return tables


def offline_table(results: dict[str, dict]) -> tuple[str, list[str], list[list[str]]] | None:
    if not results:
        return None
    header = ["Policy"] + [
        f"{label}: {kind}" for label in SPLITS.values() for kind in ("exact %", "admissible %")
    ]
    rows = []
    for name, result in results.items():
        row = [POLICIES.get(name, name)]
        for split in SPLITS:
            entry = result["splits"].get(split, {}).get("all")
            row += (
                ["–", "–"]
                if entry is None
                else [f"{100 * entry['exact_match']:.1f}", f"{100 * entry['admissible']:.1f}"]
            )
        rows.append(row)
    return ("Offline agreement with the teacher on the held-out splits", header, rows)


def markdown(tables: list, notes: list[str]) -> str:
    lines = ["# Results", "", *notes]
    for title, header, rows in tables:
        lines += ["", f"## {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def latex(tables: list) -> str:
    def esc(text: str) -> str:
        return text.replace("%", r"\%").replace("±", r"$\pm$").replace("–", "--").replace("_", r"\_")

    blocks = []
    for title, header, rows in tables:
        body = [" & ".join(esc(c) for c in header) + r" \\", r"\midrule"]
        body += [" & ".join(esc(c) for c in row) + r" \\" for row in rows]
        blocks.append(
            f"% {title}\n\\begin{{tabular}}{{l{'r' * (len(header) - 1)}}}\n\\toprule\n"
            + "\n".join(body)
            + "\n\\bottomrule\n\\end{tabular}\n"
        )
    return "\n".join(blocks)


def figure(results: dict[str, dict], out: Path) -> bool:
    """Grouped bars: blocking per condition, one panel per load. Returns False without matplotlib."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    series = [name for name in FIGURE_SERIES if name in results]
    loads = sorted({e["load"] for name in series for e in results[name]["summary"]})
    if not series or not loads:
        return False
    conditions = list(CONDITIONS)
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 9, "axes.edgecolor": AXIS,
                         "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED})  # fmt: skip
    fig, axes = plt.subplots(1, len(loads), figsize=(4.6 * len(loads), 3.2), sharey=False, facecolor=SURFACE)
    axes = [axes] if len(loads) == 1 else list(axes)
    width = 0.8 / len(series)
    for ax, load in zip(axes, loads, strict=True):
        ax.set_facecolor(SURFACE)
        for k, name in enumerate(series):
            index = {e["condition"]: e for e in results[name]["summary"] if e["load"] == load}
            xs = [i + (k - (len(series) - 1) / 2) * width for i, c in enumerate(conditions) if c in index]
            means = [100 * index[c]["service_blocking_rate_mean"] for c in conditions if c in index]
            stds = [100 * index[c]["service_blocking_rate_std"] for c in conditions if c in index]
            ax.bar(xs, means, width=width, color=FIGURE_SERIES[name], edgecolor=SURFACE, linewidth=1.2,
                   label=POLICIES[name], zorder=2)  # fmt: skip
            ax.errorbar(xs, means, yerr=stds, fmt="none", ecolor=MUTED, elinewidth=0.8, capsize=1.5, zorder=3)
        ax.set_xticks(range(len(conditions)), [CONDITIONS[c].replace(" ", "\n") for c in conditions])
        ax.set_title(f"Load {load} E", loc="left", color=INK, fontsize=10)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
        ax.tick_params(length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
    axes[0].set_ylabel("Service blocking, %  (mean ± std, 3 seeds)")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=len(series), frameon=False,
               bbox_to_anchor=(0.5, -0.02))  # fmt: skip
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".pdf"):
        fig.savefig(out.with_suffix(suffix), dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--no-figure", action="store_true")
    args = parser.parse_args()

    closed = load(args.results / "eval")
    offline = load(args.results / "offline")
    if not closed and not offline:
        raise SystemExit(f"no results under {args.results}")
    protocol = next(iter(closed.values()))["metadata"]["protocol"] if closed else None
    notes = [
        "Rendered by `src/report_tables.py` from `results/eval/` and `results/offline/`; do not edit by hand."
    ]
    if protocol:
        protocol_note = (
            f"Closed loop: {protocol['warmup']}-request warm-up by the no-intent teacher, then "
            f"{protocol['window']} measured requests per condition, load and seed. Cells are mean ± sample "
            "standard deviation over seeds. An invalid answer is replaced by first fit; a violation is an "
            "executed decision outside the intent's admissible set. Policies that ignore the intent (first "
            "fit, no-intent teacher) show how often an intent changes the right answer."
        )
        notes += ["", protocol_note]
    tables = closed_tables(closed) if closed else []
    offline_tab = offline_table(offline)
    text = markdown(tables + ([offline_tab] if offline_tab else []), notes)
    out = args.results / "tables"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.md").write_text(text, encoding="utf-8")
    (out / "results.tex").write_text(latex(tables), encoding="utf-8")
    print(text)
    if not args.no_figure and closed:
        made = figure(closed, ROOT / "docs" / "figures" / "blocking")
        print(
            "figure written to docs/figures/blocking.png"
            if made
            else "figure skipped (matplotlib not installed)"
        )


if __name__ == "__main__":
    main()
