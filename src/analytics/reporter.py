"""
Reporter — persists raw samples, summary stats, session index, and accuracy report.
Optionally triggers visualisations when config.analysis.visualization.enabled.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.analytics import visualizer
from src.utils.constants import (
    KEY_ANALYSIS,
    KEY_VISUALIZATION,
    KEY_ENABLED,
    KEY_CV_PERCENT,
    KEY_MOST_STABLE,
    KEY_NOTE,
)

if TYPE_CHECKING:
    from src.testing.AmmeterTester import SampleResult

logger = logging.getLogger(__name__)

# ── column names (local — not config keys) ──────────────────────────────────
_CSV_HEADERS = ["timestamp_sec", "raw_value", "normalized_value", "ammeter_type"]
_INDEX_FILE  = "index.json"

_ACCURACY_NOTE = (
    "CV measures precision (repeatability). Lower CV = more stable. "
    "Absolute accuracy requires a calibrated reference device."
)


def save_run(
    run_id: str,
    session_id: str,
    samples: list["SampleResult"],
    stats: dict,
    ammeter_type: str,
    results_dir: Path,
    config: dict | None = None,
) -> Path:
    """
    Persist one ammeter run to disk.

    Creates:
      results/sessions/{session_id}/runs/{ammeter_type}/raw_samples.csv
      results/sessions/{session_id}/runs/{ammeter_type}/summary.json
    Optionally writes plot_timeseries.png if config.analysis.visualization.enabled.

    Does NOT write index.json — call write_session_index() once after all runs.

    Returns the run directory Path.
    """
    run_dir = results_dir / "sessions" / session_id / "runs" / ammeter_type
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(samples, run_dir)
    _write_summary(run_id, session_id, ammeter_type, samples, stats, run_dir)

    if _viz_enabled(config):
        visualizer.plot_timeseries(samples, run_id, run_dir)

    logger.info("Run saved — ammeter=%s  dir=%s", ammeter_type, run_dir)
    return run_dir


def write_session_index(
    session_id: str,
    ammeter_runs: dict[str, dict],
    results_dir: Path,
) -> None:
    """
    Append one session entry to results/index.json.

    Each ammeter entry now includes cv_percent for at-a-glance
    historical comparison across sessions.

    Entry shape:
    {
      "session_id": "...",
      "iso_timestamp": "...",
      "most_stable": "circutor",
      "ammeters": {
        "greenlee": {"run_id": "...", "mean": ..., "std": ..., "cv_percent": ...},
        ...
      }
    }
    Creates the file if it does not exist.
    """
    index_path = results_dir / _INDEX_FILE
    results_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except json.JSONDecodeError:
                entries = []

    # Determine most stable: ammeter with lowest cv_percent
    most_stable = min(
        ammeter_runs,
        key=lambda n: ammeter_runs[n].get(KEY_CV_PERCENT, float("inf")),
        default=None,
    )

    entries.append({
        "session_id":    session_id,
        "iso_timestamp": datetime.now(timezone.utc).isoformat(),
        KEY_MOST_STABLE: most_stable,
        "ammeters":      ammeter_runs,
    })

    with index_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

    logger.info("Session index updated — session_id=%s", session_id)


def write_accuracy_report(
    session_id: str,
    ranking: list[dict],
    comparison: list[dict],
    results_dir: Path,
    per_ammeter_stats: dict | None = None,
) -> None:
    """
    Write results/sessions/{session_id}/accuracy_report.json.

    Structure:
    {
      "session_id": "...",
      "iso_timestamp": "...",
      "stability_ranking": [...],
      "relative_precision": [...],
      "per_ammeter_stats": {
        "greenlee": {"mean": ..., "median": ..., "std": ..., "min": ..., "max": ...},
        ...
      },
      "most_stable": "...",
      "note": "..."
    }
    """
    session_dir = results_dir / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    stability_ranking = [
        {
            "rank":         i + 1,
            "ammeter_type": e["ammeter_type"],
            KEY_CV_PERCENT: e["cv_percent"],
            "mean_A":       e["mean"],
            "std_A":        e["std"],
        }
        for i, e in enumerate(ranking)
    ]

    relative_precision = [
        {
            "rank":         i + 1,
            "ammeter_type": e["ammeter_type"],
            "relative_std": e["relative_std"],
            "mean_A":       e["mean_A"],
            "sample_count": e["sample_count"],
        }
        for i, e in enumerate(comparison)
    ]

    most_stable = ranking[0]["ammeter_type"] if ranking else None

    report = {
        "session_id":         session_id,
        "iso_timestamp":      datetime.now(timezone.utc).isoformat(),
        "stability_ranking":  stability_ranking,
        "relative_precision": relative_precision,
        "per_ammeter_stats":  per_ammeter_stats or {},
        KEY_MOST_STABLE:      most_stable,
        KEY_NOTE:             _ACCURACY_NOTE,
    }

    report_path = session_dir / "accuracy_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Accuracy report written — session_id=%s  path=%s", session_id, report_path)


# ── private helpers ──────────────────────────────────────────────────────────

def _write_csv(samples: list["SampleResult"], run_dir: Path) -> None:
    csv_path = run_dir / "raw_samples.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_HEADERS)
        writer.writeheader()
        for s in samples:
            writer.writerow({
                "timestamp_sec":    s.timestamp_sec,
                "raw_value":        s.raw_value,
                "normalized_value": s.normalized_value,
                "ammeter_type":     s.ammeter_type,
            })


def _write_summary(
    run_id: str,
    session_id: str,
    ammeter_type: str,
    samples: list["SampleResult"],
    stats: dict,
    run_dir: Path,
) -> None:
    summary = {
        "run_id":             run_id,
        "session_id":         session_id,
        "ammeter_type":       ammeter_type,
        "iso_timestamp":      datetime.now(timezone.utc).isoformat(),
        "measurements_count": len(samples),
        "stats":              stats,
    }
    summary_path = run_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def _viz_enabled(config: dict | None) -> bool:
    """Return True only if config.analysis.visualization.enabled is True."""
    if config is None:
        return False
    try:
        return bool(
            config[KEY_ANALYSIS][KEY_VISUALIZATION][KEY_ENABLED]
        )
    except (KeyError, TypeError):
        return False
