"""Generate publication figures from the saved corpus audit and main results."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INK = "#263342"
BLUE = "#315f83"
RUST = "#b65e3c"
GRAY = "#78838b"


def tidy(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#b9bfc4")
    ax.tick_params(colors=INK, length=3)
    ax.set_axisbelow(True)


def save(fig, path, preview):
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight", metadata={"Date": None})
    if preview:
        fig.savefig(path.with_suffix(".png"), bbox_inches="tight", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Also write PNGs for visual inspection")
    args = parser.parse_args()
    audit = json.loads((ROOT / "data/processed/audit.json").read_text())
    results = json.loads((ROOT / "results/main_v3/metrics.json").read_text())
    out = ROOT / "docs/figures"
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                         "axes.labelcolor": INK, "axes.titleweight": "semibold", "svg.fonttype": "none",
                         "svg.hashsalt": "flacky-test-figures", "axes.unicode_minus": False})
    labels = results["labels"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.5, 1]})
    for ax, key, title, color, limit in zip(axes, ["categories", "category_project_groups"],
                                           ["A. Eligible tests", "B. Repository coverage"], [BLUE, GRAY], [900, 135]):
        values = [audit[key][label] for label in labels]
        ax.barh(labels, values, color=color, height=.55)
        for i, value in enumerate(values):
            ax.text(value + limit * .018, i, f"{value:,}", va="center", fontsize=11)
        ax.invert_yaxis()
        ax.set_xlim(0, limit)
        ax.set_title(title, loc="left", pad=16)
        ax.set_xlabel("Count")
        ax.grid(axis="x", color="#e5e8eb", lw=.7)
        tidy(ax)
    fig.subplots_adjust(wspace=.4, bottom=.23)
    fig.text(.125, .01, "1,051 canonical tests across 127 repository groups. Category group counts overlap.", fontsize=9, color=GRAY)
    save(fig, out / "dataset", args.preview)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    keys = ["source_format", "original", "masked", "majority"]
    names = ["Source-format baseline", "Original logs", "Masked logs", "Majority baseline"]
    values = [results["metrics"][key]["pooled_macro_f1"] for key in keys]
    colors = [GRAY, BLUE, RUST, GRAY]
    for i, (value, color) in enumerate(zip(values, colors)):
        ax.hlines(i, 0, value, color="#d7dde2", lw=2)
        ax.scatter(value, i, c=color, s=75, zorder=3)
        ax.text(value + .024, i, f"{value:.4f}", va="center", fontsize=10)
    ax.set_yticks(range(4), names)
    ax.invert_yaxis()
    ax.set_xlim(0, .9)
    ax.set_title("A. Pooled macro-F1", loc="left", pad=18)
    ax.set_xlabel("Macro-F1")
    ax.grid(axis="x", color="#e5e8eb", lw=.7)
    tidy(ax)
    ax = axes[1]
    for i, label in enumerate(labels):
        a = results["metrics"]["original"]["classification_report"][label]["recall"]
        b = results["metrics"]["masked"]["classification_report"][label]["recall"]
        ax.plot([a, b], [i, i], color="#adb7c0", lw=2)
        ax.scatter(a, i, color=BLUE, s=65, zorder=3, label="Original" if i == 0 else None)
        ax.scatter(b, i, color=RUST, marker="x", s=65, zorder=4, label="Masked" if i == 0 else None)
    ax.set_yticks(range(4), labels)
    ax.invert_yaxis()
    ax.set_xlim(-.04, 1.06)
    ax.set_xlabel("Recall")
    ax.set_title("B. Recall by category", loc="left", pad=18)
    ax.grid(axis="x", color="#e5e8eb", lw=.7)
    ax.legend(loc="lower center", bbox_to_anchor=(.5, 1.01), ncol=2, frameon=False, fontsize=8)
    tidy(ax)
    fig.subplots_adjust(wspace=.42, bottom=.24, top=.8)
    fig.text(.125, .01, "127 held-out project groups; identical partitions in both conditions. No confidence interval is shown here.", fontsize=9, color=GRAY)
    save(fig, out / "performance", args.preview)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    for ax, key, title in zip(axes, ["original", "masked"], ["A. Original logs", "B. Masked logs"]):
        matrix = np.array(results["metrics"][key]["confusion_matrix"])
        normalised = matrix / matrix.sum(axis=1, keepdims=True)
        ax.imshow(normalised, vmin=0, vmax=1, cmap="Blues")
        for i in range(4):
            for j in range(4):
                ax.text(j, i, str(matrix[i, j]), ha="center", va="center", fontsize=12,
                        color="white" if normalised[i, j] > .57 else INK)
        ax.set_xticks(range(4), labels)
        ax.set_yticks(range(4), labels)
        ax.set_xlabel("Predicted category")
        ax.set_ylabel("True category")
        ax.set_title(title, loc="left", pad=13)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks(np.arange(-.5, 4, 1), minor=True)
        ax.set_yticks(np.arange(-.5, 4, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.8)
        ax.tick_params(which="minor", bottom=False, left=False)
    fig.subplots_adjust(wspace=.35, bottom=.2)
    fig.text(.125, .015, "Cells show counts; shading uses row proportions on the same 0 to 1 scale in both panels.", fontsize=9, color=GRAY)
    save(fig, out / "confusion", args.preview)


if __name__ == "__main__":
    main()
