"""
Reporter — persists raw samples, summary stats, and index for each run.
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
)

if TYPE_CHECKING:
    from src.testing.AmmeterTester import SampleResult

logger = logging.getLogger(__name__)

# ── column names (local — not config keys) ──────────────────────────────────
_CSV_HEADERS = ["timestamp_sec", "raw_value", "normalized_value", "ammeter_type"]
_INDEX_FILE  = "index.json"


def save_run(
    run_id: str,
    samples: list["SampleResult"],
    stats: dict,
    ammeter_type: str,
    results_dir: Path,
    config: dict | None = None,
) -> Path:
    """
    Persist one test run to disk.

    Creates:
      results/runs/{run_id}/raw_samples.csv
      results/runs/{run_id}/summary.json
    Updates:
      results/index.json
    Optionally writes plot_timeseries.png if config.analysis.visualization.enabled.
    plot_comparison is NOT called here — the caller is responsible for that
    once all ammeter runs have completed.

    Returns the run directory Path.
    """
    run_dir = results_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(samples, run_dir)
    _write_summary(run_id, ammeter_type, samples, stats, run_dir)
    _update_index(run_id, ammeter_type, stats, results_dir)

    if _viz_enabled(config):
        visualizer.plot_timeseries(samples, run_id, run_dir)

    logger.info("Run saved — run_id=%s  dir=%s", run_id, run_dir)
    return run_dir


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
    ammeter_type: str,
    samples: list["SampleResult"],
    stats: dict,
    run_dir: Path,
) -> None:
    summary = {
        "run_id":             run_id,
        "ammeter_type":       ammeter_type,
        "iso_timestamp":      datetime.now(timezone.utc).isoformat(),
        "measurements_count": len(samples),
        "stats":              stats,
    }
    summary_path = run_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def _update_index(
    run_id: str,
    ammeter_type: str,
    stats: dict,
    results_dir: Path,
) -> None:
    index_path = results_dir / _INDEX_FILE
    results_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except json.JSONDecodeError:
                entries = []

    entries.append({
        "run_id":       run_id,
        "ammeter_type": ammeter_type,
        "iso_timestamp": datetime.now(timezone.utc).isoformat(),
        "mean":         stats.get("mean"),
        "std":          stats.get("std"),
    })

    with index_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


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

