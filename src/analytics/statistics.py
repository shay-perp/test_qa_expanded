"""
Pure-function descriptive statistics using numpy only.
"""
from __future__ import annotations

import numpy as np


def compute_stats(samples: list[float]) -> dict:
    """
    Compute descriptive statistics for a list of float samples.

    Returns a dict with keys: mean, median, std, min, max.
    Raises ValueError if samples is empty.
    """
    if not samples:
        raise ValueError("Cannot compute stats on an empty sample list.")

    arr = np.array(samples, dtype=np.float64)
    return {
        "mean":   float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std":    float(np.std(arr, ddof=1)),   # sample std (ddof=1)
        "min":    float(np.min(arr)),
        "max":    float(np.max(arr)),
    }

