#!/usr/bin/env python3
"""Generate the reproducible figures used in the final Bench-bench report."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "reports" / "figures"
PUBLIC_SEEDS = list(range(100, 110))
T_CRIT_95_DF9 = 2.2621571627409915

LIVE_ORDER = ["claude-opus-5", "grok-4.5", "muse-spark-1.2", "gpt-5.6-sol", "kimi-k3"]
LIVE_SHORT = {
    "claude-opus-5": "Opus",
    "grok-4.5": "Grok",
    "muse-spark-1.2": "Muse",
    "gpt-5.6-sol": "GPT",
    "kimi-k3": "Kimi",
}
LIVE_COLORS = {
    "claude-opus-5": "#2E74B5",
    "grok-4.5": "#4F91C8",
    "muse-spark-1.2": "#78A9D2",
    "gpt-5.6-sol": "#9DB9D3",
    "kimi-k3": "#A66A00",
}
BASELINE_ORDER = [
    "scripted-expert",
    "recovery-aware",
    "skip-when-busy",
    "rigid-linear",
    "random",
    "reckless-maximalist",
]
BASELINE_LABELS = {
    "scripted-expert": "scripted-expert",
    "recovery-aware": "recovery-aware",
    "skip-when-busy": "skip-when-busy",
    "rigid-linear": "rigid-linear",
    "random": "random",
    "reckless-maximalist": "reckless-maximalist*",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#B8CBE1",
            "axes.linewidth": 0.8,
            "axes.titleweight": "bold",
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
        }
    )


def _finish(ax: Any) -> None:
    ax.grid(axis="x", color="#E8EEF5", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _save(fig: Any, filename: str) -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURE_DIR / filename
    fig.savefig(path, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _live_ci(item: dict[str, Any]) -> float:
    return T_CRIT_95_DF9 * float(item["seed_sd_kg"]) / math.sqrt(10)


def make_performance_overview(data: dict[str, Any]) -> Path:
    models = data["models"]
    baselines = data["baselines"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.0), gridspec_kw={"width_ratios": [1.0, 1.12]})
    fig.suptitle("Performance hierarchy and uncertainty", x=0.05, ha="left", y=0.995, color="#0B2545", fontsize=13, fontweight="bold")

    ax = axes[0]
    ys = np.arange(len(LIVE_ORDER))
    means = [models[name]["mean_kg"] for name in LIVE_ORDER]
    cis = [_live_ci(models[name]) for name in LIVE_ORDER]
    for y, name, mean, ci in zip(ys, LIVE_ORDER, means, cis):
        color = LIVE_COLORS[name]
        ax.errorbar(mean, y, xerr=ci, fmt="o", color=color, ecolor=color, elinewidth=2, capsize=3, markersize=6, markeredgecolor="white", markeredgewidth=0.7)
        ax.text(mean + ci + 0.18, y, f"{mean:.2f}", va="center", ha="left", color="#222222", fontsize=8)
    ax.axvline(baselines["scripted-expert"]["mean_kg"], color="#0B2545", linestyle=(0, (4, 2)), linewidth=1.2)
    ax.text(baselines["scripted-expert"]["mean_kg"] - 0.12, -0.55, "expert 102.89", ha="right", va="bottom", color="#0B2545", fontsize=7.5)
    ax.set_yticks(ys, [models[name]["display_name"] for name in LIVE_ORDER])
    ax.invert_yaxis()
    ax.set_xlim(88, 104.5)
    ax.set_xlabel("Final 1RM (kg)")
    ax.set_title("Live models", loc="left", pad=8)
    _finish(ax)

    ax = axes[1]
    ys = np.arange(len(BASELINE_ORDER))
    for y, name in zip(ys, BASELINE_ORDER):
        item = baselines[name]
        color = "#A66A00" if name == "reckless-maximalist" else "#2E74B5"
        ax.errorbar(item["mean_kg"], y, xerr=item["seed_sd_kg"], fmt="o", color=color, ecolor=color, elinewidth=2, capsize=3, markersize=6, markeredgecolor="white", markeredgewidth=0.7)
        label_x = item["mean_kg"] + item["seed_sd_kg"] + 0.18
        ax.text(label_x, y, f"{item['mean_kg']:.2f}", va="center", ha="left", color="#222222", fontsize=8)
    ax.axvline(baselines["scripted-expert"]["mean_kg"], color="#0B2545", linestyle=(0, (4, 2)), linewidth=1.2)
    ax.set_yticks(ys, [BASELINE_LABELS[name] for name in BASELINE_ORDER])
    ax.invert_yaxis()
    ax.set_xlim(84, 105.5)
    ax.set_xlabel("Final 1RM (kg)")
    ax.set_title("Scripted references", loc="left", pad=8)
    ax.text(0.01, -0.17, "Reckless-maximalist: 20/20 seeds exceeded the pain limit", transform=ax.transAxes, fontsize=7.5, color="#A66A00", va="top")
    _finish(ax)
    fig.subplots_adjust(left=0.16, right=0.98, bottom=0.16, top=0.88, wspace=0.38)
    return _save(fig, "performance-overview.png")


def make_seed_and_pairwise(data: dict[str, Any]) -> Path:
    models = data["models"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.3), gridspec_kw={"width_ratios": [1.05, 1.0]})
    fig.suptitle("Matched-seed variation and pairwise uncertainty", x=0.05, ha="left", y=0.995, color="#0B2545", fontsize=13, fontweight="bold")

    matrix = np.array([[models[name]["scores"][str(seed)] for seed in PUBLIC_SEEDS] for name in LIVE_ORDER])
    ax = axes[0]
    image = ax.imshow(matrix, aspect="auto", cmap="Blues", vmin=84, vmax=103)
    ax.set_xticks(np.arange(len(PUBLIC_SEEDS)), [str(seed) for seed in PUBLIC_SEEDS])
    ax.set_yticks(np.arange(len(LIVE_ORDER)), [LIVE_SHORT[name] for name in LIVE_ORDER])
    ax.set_xlabel("Public seed")
    ax.set_title("A. Same seed, different model", loc="left", pad=8)
    ax.tick_params(length=0)
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix[row, col]
            ax.text(col, row, f"{value:.1f}", ha="center", va="center", fontsize=7.4, color="white" if value < 94 else "#0B2545")
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("Final 1RM (kg)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax = axes[1]
    pairs = sorted(data["pairwise_model_differences"], key=lambda pair: pair["mean_difference_kg"], reverse=True)
    ys = np.arange(len(pairs))
    labels = [f"{LIVE_SHORT[pair['a']]} − {LIVE_SHORT[pair['b']]}" for pair in pairs]
    for y, pair in zip(ys, pairs):
        delta = pair["mean_difference_kg"]
        low = pair["ci95_low_kg"]
        high = pair["ci95_high_kg"]
        color = "#2E74B5" if low > 0 else "#A66A00" if high < 0 else "#6B7280"
        ax.errorbar(delta, y, xerr=[[delta - low], [high - delta]], fmt="o", color=color, ecolor=color, elinewidth=2, capsize=3, markersize=5.5, markeredgecolor="white", markeredgewidth=0.7)
        ax.text(high + 0.18, y, f"{delta:.2f}", va="center", ha="left", fontsize=7.3, color="#222222")
    ax.axvline(0, color="#0B2545", linewidth=1.0)
    ax.set_yticks(ys, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Mean A − B (kg)")
    ax.set_title("B. Paired 95% intervals", loc="left", pad=8)
    _finish(ax)
    fig.subplots_adjust(left=0.11, right=0.98, bottom=0.15, top=0.87, wspace=0.43)
    return _save(fig, "seed-variation-and-pairwise.png")


def make_operations(data: dict[str, Any]) -> Path:
    models = data["models"]
    names = LIVE_ORDER
    labels = [LIVE_SHORT[name] for name in names]
    colors = [LIVE_COLORS[name] for name in names]
    fig, axes = plt.subplots(1, 3, figsize=(10, 4.3), gridspec_kw={"width_ratios": [1, 1.08, 1]})
    fig.suptitle("Operational behavior is part of the result", x=0.05, ha="left", y=0.995, color="#0B2545", fontsize=13, fontweight="bold")
    ys = np.arange(len(names))

    ax = axes[0]
    repair_values = [models[name]["repair_rate"] * 100 for name in names]
    ax.barh(ys, repair_values, color=colors, height=0.58)
    for y, value in zip(ys, repair_values):
        ax.text(value + 0.35, y, f"{value:.1f}%", va="center", fontsize=7.5)
    ax.set_xlim(0, 22)
    ax.set_yticks(ys, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Rejected outputs (%)")
    ax.set_title("Repairs", loc="left", pad=8)
    _finish(ax)

    ax = axes[1]
    transport_values = [models[name]["transport_failures"] for name in names]
    ax.barh(ys, transport_values, color=colors, height=0.58)
    for y, value in zip(ys, transport_values):
        ax.text(max(value + 12, 8), y, f"{value}", va="center", fontsize=7.5)
    ax.set_xlim(0, 770)
    ax.set_yticks(ys, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Transport failures")
    ax.set_title("Provider reliability", loc="left", pad=8)
    _finish(ax)

    ax = axes[2]
    cost_values = [models[name]["cost_per_episode_usd"] for name in names]
    ax.barh(ys, cost_values, color=colors, height=0.58)
    for y, value in zip(ys, cost_values):
        ax.text(value + 0.08, y, f"${value:.2f}", va="center", fontsize=7.5)
    ax.set_xlim(0, 6.7)
    ax.set_yticks(ys, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Dollars per episode")
    ax.set_title("Cost", loc="left", pad=8)
    _finish(ax)
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.18, top=0.87, wspace=0.52)
    return _save(fig, "operational-behavior.png")


def make_process_timeline() -> Path:
    labels = [
        "Start\nbrief",
        "12-week\nslice",
        "Calibration",
        "Ablations",
        "Repair\naudit",
        "Mechanics",
        "Ledger",
        "Adversarial\nsearch",
        "Safety +\nstats",
        "Prompt +\nartifacts",
        "Independent\nreviews",
        "Live\npreparation",
        "Public\nrun",
    ]
    groups = [
        "concept",
        "concept",
        "calibration",
        "calibration",
        "mechanics",
        "mechanics",
        "mechanics",
        "evidence",
        "evidence",
        "evidence",
        "evidence",
        "live",
        "live",
    ]
    group_colors = {
        "concept": "#7A5A00",
        "calibration": "#2E74B5",
        "mechanics": "#4F8A5B",
        "evidence": "#7C5AA6",
        "live": "#0B2545",
    }
    fig, ax = plt.subplots(figsize=(10, 3.2))
    fig.suptitle("From benchmark idea to frozen public result", x=0.05, ha="left", y=0.99, color="#0B2545", fontsize=13, fontweight="bold")
    x = np.arange(len(labels))
    ax.plot(x, np.full_like(x, 0.5, dtype=float), color="#D9E2F3", linewidth=2, zorder=1)
    for index, (label, group) in enumerate(zip(labels, groups)):
        color = group_colors[group]
        ax.scatter(index, 0.5, s=85, color=color, edgecolor="white", linewidth=1.2, zorder=3)
        y = 0.77 if index % 2 == 0 else 0.23
        va = "bottom" if index % 2 == 0 else "top"
        ax.plot([index, index], [0.55 if index % 2 == 0 else 0.45, 0.70 if index % 2 == 0 else 0.30], color=color, linewidth=0.8)
        ax.text(index, y, label, ha="center", va=va, fontsize=7.4, color="#222222", linespacing=1.0)
    ax.text(0.0, -0.02, "Each review turned a failure class into an invariant, audit, or counted diagnostic.", transform=ax.transAxes, fontsize=8, color="#4B5563", va="top")
    handles = [Patch(facecolor=color, edgecolor="none", label=label.title()) for label, color in group_colors.items()]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=5, frameon=False, handlelength=0.9, columnspacing=1.1)
    ax.set_xlim(-0.6, len(labels) - 0.4)
    ax.set_ylim(-0.16, 1.02)
    ax.axis("off")
    fig.subplots_adjust(left=0.03, right=0.98, top=0.82, bottom=0.20)
    return _save(fig, "development-timeline.png")


def build_figures(data: dict[str, Any]) -> dict[str, Path]:
    _style()
    return {
        "performance_overview": make_performance_overview(data),
        "seed_variation_and_pairwise": make_seed_and_pairwise(data),
        "operational_behavior": make_operations(data),
        "development_timeline": make_process_timeline(),
    }


if __name__ == "__main__":
    import json

    source = ROOT / "reports" / "final_public_leaderboard.json"
    result = build_figures(json.loads(source.read_text(encoding="utf-8")))
    for path in result.values():
        print(path)
