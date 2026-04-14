"""
tests/test_analytics.py — statistics, accuracy, and reporter.
"""
from __future__ import annotations

import csv
import json
import uuid

import pytest

from src.analytics.statistics import compute_stats
from src.analytics.accuracy import coefficient_of_variation, rank_ammeters
from src.analytics import reporter
from src.testing.AmmeterTester import SampleResult
from src.utils.constants import KEY_GREENLEE, KEY_ENTES


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_samples(ammeter_type: str = KEY_GREENLEE, count: int = 3) -> list[SampleResult]:
    run_id = str(uuid.uuid4())
    return [
        SampleResult(
            run_id=run_id,
            ammeter_type=ammeter_type,
            timestamp_sec=float(i) * 0.5,
            raw_value=float(i + 1),
            normalized_value=float(i + 1),
        )
        for i in range(count)
    ]


# ── statistics ────────────────────────────────────────────────────────────────

class TestComputeStats:
    def test_known_input(self):
        stats = compute_stats([1.0, 2.0, 3.0, 4.0, 5.0])
        assert stats["mean"] == pytest.approx(3.0)
        assert stats["min"]  == pytest.approx(1.0)
        assert stats["max"]  == pytest.approx(5.0)

    def test_single_value(self):
        """Single-element list must not raise; std should be 0.0 (or NaN for ddof=1)."""
        stats = compute_stats([5.0])
        assert stats["mean"] == pytest.approx(5.0)
        # ddof=1 on a single element gives nan — we just confirm no exception
        assert "std" in stats

    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            compute_stats([])


# ── accuracy ──────────────────────────────────────────────────────────────────

class TestAccuracy:
    def test_cv_calculation(self):
        cv = coefficient_of_variation({"std": 1.0, "mean": 10.0})
        assert cv == pytest.approx(10.0)

    def test_rank_ammeters_order(self):
        """Ammeter with lower CV must appear first in ranking."""
        stats_input = {
            KEY_GREENLEE: {"mean": 10.0, "std": 5.0},   # CV = 50 %
            KEY_ENTES:    {"mean": 10.0, "std": 1.0},   # CV = 10 %
        }
        ranking = rank_ammeters(stats_input)
        assert ranking[0]["ammeter_type"] == KEY_ENTES
        assert ranking[1]["ammeter_type"] == KEY_GREENLEE
        assert ranking[0]["cv_percent"] < ranking[1]["cv_percent"]


# ── reporter ──────────────────────────────────────────────────────────────────

class TestReporter:
    def test_reporter_creates_files(self, tmp_results_dir, sample_stats):
        """save_run must create raw_samples.csv and summary.json."""
        run_id    = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        samples   = _make_samples()

        run_dir = reporter.save_run(
            run_id=run_id,
            session_id=session_id,
            samples=samples,
            stats=sample_stats,
            ammeter_type=KEY_GREENLEE,
            results_dir=tmp_results_dir,
            config=None,
        )

        assert (run_dir / "raw_samples.csv").exists()
        assert (run_dir / "summary.json").exists()

    def test_csv_row_count(self, tmp_results_dir, sample_stats):
        """raw_samples.csv must contain one row per sample (plus header)."""
        run_id     = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        samples    = _make_samples(count=3)

        run_dir = reporter.save_run(
            run_id=run_id,
            session_id=session_id,
            samples=samples,
            stats=sample_stats,
            ammeter_type=KEY_GREENLEE,
            results_dir=tmp_results_dir,
            config=None,
        )

        with (run_dir / "raw_samples.csv").open() as f:
            rows = list(csv.reader(f))
        assert len(rows) == 4  # 1 header + 3 data rows

    def test_index_json_appends(self, tmp_results_dir, sample_stats):
        """Calling write_session_index twice produces exactly two entries."""
        for _ in range(2):
            session_id = str(uuid.uuid4())
            ammeter_runs = {
                KEY_GREENLEE: {
                    "run_id": str(uuid.uuid4()),
                    "mean":   sample_stats["mean"],
                    "std":    sample_stats["std"],
                }
            }
            reporter.write_session_index(session_id, ammeter_runs, tmp_results_dir)

        index_path = tmp_results_dir / "index.json"
        assert index_path.exists()
        with index_path.open() as f:
            entries = json.load(f)
        assert len(entries) == 2

