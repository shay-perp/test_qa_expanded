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

