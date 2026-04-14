"""
Visualiser — matplotlib-based charts for ammeter sample runs.
No-ops when called with empty data.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import matplotlib
matplotlib.use("Agg")          # headless — no display required
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from src.testing.AmmeterTester import SampleResult


def plot_timeseries(
    samples: list["SampleResult"],
    run_id: str,
    output_path: Path,
) -> None:
    """
    Line chart: x = timestamp_sec, y = normalized_value.
    Saves to output_path/plot_timeseries.png.
    Skips silently if samples is empty or all normalized_values are None.
    """
    valid = [s for s in samples if s.normalized_value is not None]
    if not valid:
        return

    xs = [s.timestamp_sec    for s in valid]
    ys = [s.normalized_value for s in valid]
    ammeter_type = valid[0].ammeter_type

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(xs, ys, marker="o", linewidth=1.5, markersize=4)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Normalized current (A)")
    ax.set_title(f"Time-series — {ammeter_type}  [run {run_id[:8]}]")
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()

    output_path.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path / "plot_timeseries.png", dpi=120)
    plt.close(fig)


def plot_comparison(
    all_results: dict[str, list["SampleResult"]],
    run_id: str,
    output_path: Path,
) -> None:
    """
    Boxplot with one box per ammeter_type side by side.
    Each ammeter's values are normalised to its own mean (display only —
    raw_value / normalized_value in SampleResult are never modified).
    This keeps all boxes centred around 1.0 so ammeters on very different
    physical scales (e.g. ENTES ~70 A vs Circutor ~0.03 A) remain readable.
    Saves to output_path/plot_comparison.png.
    Skips silently if all_results is empty or contains no valid values.
    """
    labels:        list[str]         = []
    display_values: list[list[float]] = []

    for name, samples in all_results.items():
        vals = [s.normalized_value for s in samples if s.normalized_value is not None]
        if not vals:
            continue
        mean = float(np.mean(np.array(vals, dtype=np.float64)))
        if mean == 0:
            continue
        labels.append(name)
        display_values.append([v / mean for v in vals])

    if not display_values:
        return

    fig, ax = plt.subplots(figsize=(max(6, 3 * len(labels)), 5))
    ax.boxplot(display_values, labels=labels, patch_artist=True)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Ammeter type")
    ax.set_ylabel("Relative current (normalized to own mean)")
    ax.set_title(f"Ammeter comparison — relative dispersion  [run {run_id[:8]}]")
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()

    output_path.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path / "plot_comparison.png", dpi=120)
    plt.close(fig)


def plot_accuracy(
    ranking: list[dict],
    comparison: list[dict],
    run_id: str,
    output_path: Path,
) -> None:
    """
    Side-by-side bar chart showing CV% (stability) and relative_std (precision)
    for each ammeter.
    Left bars:  CV% from stability ranking.
    Right bars: relative_std from cross-ammeter comparison.
    Saves to output_path/plot_accuracy.png.
    Skips silently if both lists are empty.
    """
    if not ranking and not comparison:
        return

    # Build aligned data keyed on ammeter_type
    ammeter_names = [e["ammeter_type"] for e in ranking]
    cv_values     = [e["cv_percent"]   for e in ranking]

    comp_by_name  = {e["ammeter_type"]: e["relative_std"] for e in comparison}
    rel_std_values = [comp_by_name.get(n, 0.0) for n in ammeter_names]

    x      = np.arange(len(ammeter_names))
    width  = 0.35

    fig, ax = plt.subplots(figsize=(max(6, 2.5 * len(ammeter_names)), 5))
    bars_cv  = ax.bar(x - width / 2, cv_values,      width, label="CV (%)",        color="steelblue")
    bars_rel = ax.bar(x + width / 2, rel_std_values,  width, label="Relative Std",  color="coral")

    # Value labels on top of each bar
    for bar in bars_cv:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=8)
    for bar in bars_rel:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(ammeter_names)
    ax.set_xlabel("Ammeter type")
    ax.set_ylabel("Value")
    ax.set_title(f"Accuracy assessment  [session {run_id[:8]}]")
    ax.legend()
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    output_path.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path / "plot_accuracy.png", dpi=120)
    plt.close(fig)


