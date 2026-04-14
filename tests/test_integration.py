"""
tests/test_integration.py — full session flow integration tests.

All tests use the running_all_servers fixture (ports 5020-5022).
"""
from __future__ import annotations

import csv
import json
import time
import uuid

import pytest

from src.analytics import reporter
from src.analytics.accuracy import (
    coefficient_of_variation,
    rank_ammeters,
    compare_ammeters,
)
from src.analytics.statistics import compute_stats
from src.testing.AmmeterTester import AmmeterTester
from src.utils.constants import (
    KEY_GREENLEE,
    KEY_ENTES,
    KEY_CIRCUTOR,
    KEY_CV_PERCENT,
    KEY_PORT,
    KEY_COMMAND,
    KEY_SCALE_FACTOR,
    KEY_TESTING,
    KEY_SAMPLING,
    KEY_MEASUREMENTS_COUNT,
    KEY_SAMPLING_FREQ,
    KEY_TOTAL_DURATION,
    KEY_AMMETERS,
)

# ── helpers ───────────────────────────────────────────────────────────────────

_STAT_KEYS = {"mean", "median", "std", "min", "max"}


def _make_tester_config(server_map: dict) -> dict:
    """
    Build a minimal AmmeterTester config pointing at the integration ports
    with 3 samples at 2 Hz so tests run in ~1.5 s.
    """
    return {
        KEY_AMMETERS: {
            name: {
                KEY_PORT:         port,
                KEY_COMMAND:      command,
                KEY_SCALE_FACTOR: 1.0,
            }
            for name, (port, command) in server_map.items()
        },
        KEY_TESTING: {
            KEY_SAMPLING: {
                KEY_MEASUREMENTS_COUNT: 3,
                KEY_TOTAL_DURATION:     2,
                KEY_SAMPLING_FREQ:      2.0,
            }
        },
    }


def _run_all_ammeters(server_map: dict) -> tuple[dict, dict, dict, str]:
    """
    Run AmmeterTester for all three ammeters with a shared session_start.
    Returns (all_results, all_stats, ammeter_runs, session_id).
    """
    session_id    = str(uuid.uuid4())
    session_start = time.perf_counter()
    all_results:  dict = {}
    all_stats:    dict = {}
    ammeter_runs: dict = {}

    for name, (port, command) in server_map.items():
        tester = AmmeterTester()
        tester._config = _make_tester_config(server_map)

        samples = tester.run_test(name, session_start)
        valid   = [s.normalized_value for s in samples if s.normalized_value is not None]
        if not valid:
            continue

        stats = compute_stats(valid)
        cv    = coefficient_of_variation(stats)
        all_results[name] = samples
        all_stats[name]   = stats
        ammeter_runs[name] = {
            "run_id":       tester._run_id,
            "mean":         stats["mean"],
            "std":          stats["std"],
            KEY_CV_PERCENT: cv,
        }

    return all_results, all_stats, ammeter_runs, session_id


# ── tests ─────────────────────────────────────────────────────────────────────

class TestFullSessionDirectories:
    def test_full_session_creates_directories(
        self, running_all_servers, tmp_results_dir
    ):
        """save_run() must create runs/{ammeter_type}/ under the session dir."""
        all_results, all_stats, ammeter_runs, session_id = _run_all_ammeters(
            running_all_servers
        )

        for name, samples in all_results.items():
            reporter.save_run(
                run_id=ammeter_runs[name]["run_id"],
                session_id=session_id,
                samples=samples,
                stats=all_stats[name],
                ammeter_type=name,
                results_dir=tmp_results_dir,
                config=None,
            )

        session_runs = tmp_results_dir / "sessions" / session_id / "runs"
        assert (session_runs / KEY_GREENLEE).is_dir(),  "greenlee run dir missing"
        assert (session_runs / KEY_ENTES).is_dir(),     "entes run dir missing"
        assert (session_runs / KEY_CIRCUTOR).is_dir(),  "circutor run dir missing"


class TestCSVColumns:
    def test_full_session_csv_has_correct_columns(
        self, running_all_servers, tmp_results_dir
    ):
        """raw_samples.csv must have exactly the expected column headers."""
        all_results, all_stats, ammeter_runs, session_id = _run_all_ammeters(
            running_all_servers
        )

        # Save only greenlee for this test
        name = KEY_GREENLEE
        run_dir = reporter.save_run(
            run_id=ammeter_runs[name]["run_id"],
            session_id=session_id,
            samples=all_results[name],
            stats=all_stats[name],
            ammeter_type=name,
            results_dir=tmp_results_dir,
            config=None,
        )

        csv_path = run_dir / "raw_samples.csv"
        assert csv_path.exists(), "raw_samples.csv not created"

        with csv_path.open(newline="", encoding="utf-8") as f:
            reader  = csv.DictReader(f)
            headers = set(reader.fieldnames or [])

        expected = {"timestamp_sec", "raw_value", "normalized_value", "ammeter_type"}
        assert headers == expected, f"Unexpected CSV headers: {headers}"


class TestAccuracyReport:
    def test_accuracy_report_has_required_fields(
        self, running_all_servers, tmp_results_dir
    ):
        """accuracy_report.json must contain all required top-level fields and
        per_ammeter_stats must have mean/median/std/min/max for each ammeter."""
        all_results, all_stats, ammeter_runs, session_id = _run_all_ammeters(
            running_all_servers
        )

        ranking    = rank_ammeters(all_stats)
        comparison = compare_ammeters(all_results)

        reporter.write_accuracy_report(
            session_id=session_id,
            ranking=ranking,
            comparison=comparison,
            results_dir=tmp_results_dir,
            per_ammeter_stats=all_stats,
        )

        report_path = (
            tmp_results_dir / "sessions" / session_id / "accuracy_report.json"
        )
        assert report_path.exists(), "accuracy_report.json not created"

        with report_path.open(encoding="utf-8") as f:
            report = json.load(f)

        required_top = {
            "session_id", "stability_ranking", "relative_precision",
            "per_ammeter_stats", "most_stable", "note",
        }
        assert required_top.issubset(report.keys()), \
            f"Missing top-level keys: {required_top - report.keys()}"

        per_stats = report["per_ammeter_stats"]
        for ammeter in (KEY_GREENLEE, KEY_ENTES, KEY_CIRCUTOR):
            assert ammeter in per_stats, f"{ammeter} missing from per_ammeter_stats"
            assert _STAT_KEYS.issubset(per_stats[ammeter].keys()), \
                f"{ammeter} missing stat keys: {_STAT_KEYS - per_stats[ammeter].keys()}"


class TestIndexJsonCV:
    def test_index_json_contains_cv(
        self, running_all_servers, tmp_results_dir
    ):
        """Every ammeter entry in index.json must have a cv_percent field."""
        all_results, all_stats, ammeter_runs, session_id = _run_all_ammeters(
            running_all_servers
        )

        reporter.write_session_index(
            session_id=session_id,
            ammeter_runs=ammeter_runs,
            results_dir=tmp_results_dir,
        )

        index_path = tmp_results_dir / "index.json"
        assert index_path.exists(), "index.json not created"

        with index_path.open(encoding="utf-8") as f:
            entries = json.load(f)

        assert len(entries) == 1
        ammeters = entries[0]["ammeters"]
        for name in (KEY_GREENLEE, KEY_ENTES, KEY_CIRCUTOR):
            assert name in ammeters, f"{name} missing from index ammeters"
            assert KEY_CV_PERCENT in ammeters[name], \
                f"{name} missing cv_percent in index.json"
            assert isinstance(ammeters[name][KEY_CV_PERCENT], float), \
                f"{name} cv_percent is not a float"

