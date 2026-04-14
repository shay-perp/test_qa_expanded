"""
Visualiser — matplotlib-based charts for ammeter sample runs.
No-ops when called with empty data.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

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
    Saves to output_path/plot_comparison.png.
    Skips silently if all_results is empty or contains no valid values.
    """
    labels: list[str]        = []
    data:   list[list[float]] = []

    for name, samples in all_results.items():
        vals = [s.normalized_value for s in samples if s.normalized_value is not None]
        if vals:
            labels.append(name)
            data.append(vals)

    if not data:
        return

    fig, ax = plt.subplots(figsize=(max(6, 3 * len(labels)), 5))
    ax.boxplot(data, labels=labels, patch_artist=True)
    ax.set_xlabel("Ammeter type")
    ax.set_ylabel("Normalized current (A)")
    ax.set_title(f"Ammeter comparison  [run {run_id[:8]}]")
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()

    output_path.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path / "plot_comparison.png", dpi=120)
    plt.close(fig)

