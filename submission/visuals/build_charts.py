"""Charts for the story. Every number is read from engine/eval/results."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

HERE = Path(__file__).parent
R = HERE.parent.parent / "engine/eval/results"
SURFACE, TEXT, MUTED, GRID = "#0e1530", "#eef2fb", "#a4b1cc", "#27335c"
SERIES = {"keyword": "#3987e5", "vector": "#d95926", "hybrid": "#199e70"}
LABEL = {"keyword": "Keyword only", "vector": "Vector only", "hybrid": "Keyword + vector"}
for name in fm.findSystemFonts():
    if "Avenir Next" in name:
        fm.fontManager.addfont(name)
plt.rcParams.update({"font.family": ["Avenir Next", "Helvetica", "Arial"], "text.color": TEXT, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def clean(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)


def recall_chart():
    d = json.loads((R / "eval_holdout.json").read_text())
    n = d["summary"]["all"]["n"]
    cats = [("name", "File name"), ("content", "Inside\ndocuments"), ("ocr", "Text in\nimages"), ("spoken", "Spoken"),
            ("visual", "Looks like"), ("graph", "Connected"), ("all", f"All {n}")]
    fig, ax = plt.subplots(figsize=(15, 10), dpi=100)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.75, bottom=0.12)
    w = 0.26
    for i, (key, _) in enumerate(cats):
        for j, mode in enumerate(SERIES):
            val = d["summary"][key][mode]["recall@10"]
            x = i + (j - 1) * (w + 0.012)
            ax.bar(x, val, w, color=SERIES[mode], edgecolor=SURFACE, linewidth=1.5)
            if key in ("all", "visual"):
                ax.text(x, val + 0.018, f"{val:.2f}", ha="center", fontsize=14, fontweight="bold", color=TEXT)
    ax.axvline(5.5, color=GRID, lw=1.5, ls=(0, (4, 4)))
    ax.set_xlim(-0.55, len(cats) - 0.45)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([c[1] for c in cats], fontsize=16, color=TEXT)
    ax.tick_params(axis="y", labelsize=14)
    ax.grid(axis="y", color=GRID, lw=1)
    ax.set_axisbelow(True)
    clean(ax)
    ax.set_ylabel("Share of right files in the top 10", fontsize=15)
    fig.text(0.07, 0.925, "Keyword and vectors cover each other's gaps", fontsize=36, fontweight="bold", color=TEXT)
    fig.text(0.07, 0.875, f"Recall@10 on {n} held-out queries, locked before the run. No LLM. Synthetic test NAS.", fontsize=19, color=MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, fc=SERIES[m]) for m in SERIES]
    fig.legend(handles, [LABEL[m] for m in SERIES], loc="upper left", bbox_to_anchor=(0.065, 0.855), ncol=3, frameon=False, fontsize=16, handlelength=1, handleheight=1, columnspacing=2)
    fig.savefig(HERE / "04-results.png", facecolor=SURFACE)


def graph_gain():
    d = json.loads((R / "eval_holdout.json").read_text())
    rows = [r for r in d["rows"] if r["cat"] == "graph"]
    rows.sort(key=lambda r: r["budget20"]["direct_plus_connected"] - r["budget20"]["direct_only"])
    fig, ax = plt.subplots(figsize=(15, 10), dpi=100)
    fig.subplots_adjust(left=0.40, right=0.95, top=0.76, bottom=0.08)
    a, b = "#3987e5", "#199e70"
    for i, r in enumerate(rows):
        x0, x1 = r["budget20"]["direct_only"], r["budget20"]["direct_plus_connected"]
        ax.plot([x0, x1], [i, i], color=GRID, lw=6, solid_capstyle="round", zorder=1)
        ax.scatter(x0, i, s=210, color=a, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.scatter(x1, i, s=210, color=b, edgecolor=SURFACE, linewidth=2, zorder=3)
        if x1 - x0 > 0.001:
            ax.text(x1 + 0.03, i, f"+{x1 - x0:.2f}", va="center", fontsize=15, fontweight="bold", color=TEXT)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["query"] for r in rows], fontsize=16, color=TEXT)
    ax.set_xlim(-0.04, 1.14)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.tick_params(axis="x", labelsize=14)
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    clean(ax)
    ax.set_xlabel("Share of right files found, with 20 files shown", fontsize=15)
    s = d["summary"]["graph"]["budget20"]
    fig.text(0.04, 0.925, "The graph finds what search cannot see", fontsize=36, fontweight="bold", color=TEXT)
    fig.text(0.04, 0.875, f"Held-out connected queries: {s['direct_only']:.2f} with direct results, {s['direct_plus_connected']:.2f} with connected files. These queries were written to need the graph.", fontsize=17, color=MUTED)
    fig.legend([plt.Line2D([], [], marker="o", ls="", ms=13, color=a), plt.Line2D([], [], marker="o", ls="", ms=13, color=b)],
               ["20 direct results", "10 direct + 10 connected"], loc="upper left", bbox_to_anchor=(0.035, 0.855), ncol=2, frameon=False, fontsize=16, columnspacing=2)
    fig.savefig(HERE / "10-graph-gain.png", facecolor=SURFACE)


def model_chart():
    d = json.loads((R / "model_bench.json").read_text())
    rows = d["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(15, 10), dpi=100, gridspec_kw={"wspace": 0.08, "width_ratios": [1.15, 1]})
    fig.subplots_adjust(left=0.17, right=0.96, top=0.74, bottom=0.17)
    names = [r["label"] for r in rows][::-1]
    speed = [r["images_per_s"] for r in rows][::-1]
    mem = [r["ram_gb"] for r in rows][::-1]
    for ax, vals, fmt, title, cap in (
        (axes[0], speed, "{:.2f}", "Images per second", max(speed) * 1.22),
        (axes[1], mem, "{:.1f} GB", "RAM for the model process", max(mem) * 1.3),
    ):
        ax.barh(names, vals, color="#3987e5", height=0.56, edgecolor=SURFACE, linewidth=2)
        for i, v in enumerate(vals):
            ax.text(v + cap * 0.015, i, fmt.format(v), va="center", fontsize=16, fontweight="bold", color=TEXT)
        ax.set_xlim(0, cap)
        ax.set_title(title, loc="left", fontsize=20, fontweight="bold", color=TEXT, pad=14)
        ax.xaxis.set_visible(False)
        clean(ax)
    axes[0].tick_params(axis="y", labelsize=16, labelcolor=TEXT)
    axes[1].set_yticklabels([])
    fig.text(0.04, 0.925, "\"Lightweight\" does not survive measurement", fontsize=36, fontweight="bold", color=TEXT)
    fig.text(0.04, 0.875, "Qwen3-VL-Embedding-2B at up to 512 px on an Apple M2 Max, on real photos.", fontsize=19, color=MUTED)
    fig.text(0.04, 0.05, "The card's default, bfloat16, is emulated on this CPU. Dynamic int8 was slower, larger, and damaged the vectors (cosine 0.62).\nGPU RAM counts the CPU process only. The Docker row is the full pipeline, including OCR, on Linux with 6 cores.", fontsize=15, color=MUTED)
    fig.savefig(HERE / "06-model-reality.png", facecolor=SURFACE)


if __name__ == "__main__":
    recall_chart()
    graph_gain()
    model_chart()
