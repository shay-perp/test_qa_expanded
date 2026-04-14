"""
Accuracy — coefficient of variation, ammeter ranking, cross-ammeter comparison,
and result printing.
"""
from __future__ import annotations

import numpy as np


def coefficient_of_variation(stats: dict) -> float:
    """
    Return (std / mean) * 100.
    Raises ZeroDivisionError if mean is zero.
    """
    mean = stats["mean"]
    if mean == 0.0:
        raise ZeroDivisionError(
            "Cannot compute CV: mean is zero — division by zero."
        )
    return (stats["std"] / mean) * 100.0


def rank_ammeters(results_per_ammeter: dict[str, dict]) -> list[dict]:
    """
    Rank ammeters by coefficient of variation (ascending — lower = more stable).

    Args:
        results_per_ammeter: {ammeter_name: stats_dict}

    Returns:
        List of dicts sorted by cv_percent ascending, each entry:
        {ammeter_type, cv_percent, mean, std}
    """
    ranking: list[dict] = []
    for name, stats in results_per_ammeter.items():
        try:
            cv = coefficient_of_variation(stats)
        except ZeroDivisionError:
            cv = float("inf")
        ranking.append({
            "ammeter_type": name,
            "cv_percent":   cv,
            "mean":         stats["mean"],
            "std":          stats["std"],
        })

    ranking.sort(key=lambda e: e["cv_percent"])
    return ranking


def print_ranking(ranking: list[dict]) -> None:
    """Print a clean table of ammeter stability rankings to stdout."""
    if not ranking:
        print("No ranking data available.")
        return

    col_w = {"rank": 6, "ammeter": 12, "cv": 12, "mean": 14, "std": 14}
    header = (
        f"{'Rank':<{col_w['rank']}}"
        f"{'Ammeter':<{col_w['ammeter']}}"
        f"{'CV (%)':<{col_w['cv']}}"
        f"{'Mean (A)':<{col_w['mean']}}"
        f"{'Std (A)':<{col_w['std']}}"
    )
    sep = "-" * len(header)

    print("\n" + sep)
    print("  Ammeter Stability Ranking  (lower CV = more stable)")
    print(sep)
    print(header)
    print(sep)

    for i, entry in enumerate(ranking, start=1):
        cv_str   = f"{entry['cv_percent']:.2f}" if entry["cv_percent"] != float("inf") else "N/A"
        mean_str = f"{entry['mean']:.6f}"
        std_str  = f"{entry['std']:.6f}"
        print(
            f"{i:<{col_w['rank']}}"
            f"{entry['ammeter_type']:<{col_w['ammeter']}}"
            f"{cv_str:<{col_w['cv']}}"
            f"{mean_str:<{col_w['mean']}}"
            f"{std_str:<{col_w['std']}}"
        )

    print(sep + "\n")


def compare_ammeters(results_per_ammeter: dict) -> list[dict]:
    """
    Normalize each ammeter's readings to its own mean so that ammeters
    with different physical scales can be compared on a dimensionless basis.

    Args:
        results_per_ammeter: {ammeter_name: list[SampleResult]}

    Returns:
        List of dicts sorted by relative_std ascending (lower = more precise
        relative to own mean), each entry:
        {ammeter_type, relative_std, mean_A, sample_count}
    """
    comparison: list[dict] = []
    for name, samples in results_per_ammeter.items():
        values = [
            s.normalized_value
            for s in samples
            if s.normalized_value is not None
        ]
        if not values:
            continue

        arr  = np.array(values, dtype=np.float64)
        mean = float(np.mean(arr))
        if mean == 0.0:
            relative_std = float("inf")
        else:
            normalized   = arr / mean          # dimensionless — centered at 1.0
            relative_std = float(np.std(normalized))

        comparison.append({
            "ammeter_type": name,
            "relative_std": relative_std,
            "mean_A":       mean,
            "sample_count": len(values),
        })

    comparison.sort(key=lambda e: e["relative_std"])
    return comparison


def print_comparison(comparison: list[dict]) -> None:
    """Print a clean cross-ammeter comparison table to stdout."""
    if not comparison:
        print("No comparison data available.")
        return

    col_w = {"rank": 6, "ammeter": 12, "rel_std": 14, "mean": 14, "samples": 10}
    header = (
        f"{'Rank':<{col_w['rank']}}"
        f"{'Ammeter':<{col_w['ammeter']}}"
        f"{'Relative Std':<{col_w['rel_std']}}"
        f"{'Mean (A)':<{col_w['mean']}}"
        f"{'Samples':<{col_w['samples']}}"
    )
    sep = "-" * len(header)

    print("\n" + sep)
    print("  Cross-Ammeter Comparison  (lower relative std = more precise)")
    print(sep)
    print(header)
    print(sep)

    for i, entry in enumerate(comparison, start=1):
        rel_str  = (
            f"{entry['relative_std']:.6f}"
            if entry["relative_std"] != float("inf")
            else "N/A"
        )
        mean_str = f"{entry['mean_A']:.6f}"
        print(
            f"{i:<{col_w['rank']}}"
            f"{entry['ammeter_type']:<{col_w['ammeter']}}"
            f"{rel_str:<{col_w['rel_std']}}"
            f"{mean_str:<{col_w['mean']}}"
            f"{entry['sample_count']:<{col_w['samples']}}"
        )

    print(sep + "\n")


