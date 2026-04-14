"""
tests/test_sampler.py — AmmeterTester sampling logic.
"""
from __future__ import annotations

import socket
import time
from unittest.mock import MagicMock, patch

import pytest

from src.testing.AmmeterTester import AmmeterTester
from src.utils.constants import KEY_SCALE_FACTOR, KEY_PORT, KEY_COMMAND


class TestRunTest:
    def test_sample_count(self, running_greenlee_server):
        """run_test returns exactly measurements_count SampleResults."""
        port, command = running_greenlee_server
        tester = AmmeterTester()
        # Override config so measurements_count=3 and points at the test port
        from src.utils.constants import (
            KEY_AMMETERS, KEY_GREENLEE, KEY_SCALE_FACTOR,
            KEY_TESTING, KEY_SAMPLING, KEY_MEASUREMENTS_COUNT, KEY_SAMPLING_FREQ,
            KEY_TOTAL_DURATION,
        )
        tester._config = {
            KEY_AMMETERS: {
                KEY_GREENLEE: {
                    KEY_PORT:         port,
                    KEY_COMMAND:      command,
                    KEY_SCALE_FACTOR: 1.0,
                }
            },
            KEY_TESTING: {
                KEY_SAMPLING: {
                    KEY_MEASUREMENTS_COUNT: 3,
                    KEY_SAMPLING_FREQ:      2.0,
                    KEY_TOTAL_DURATION:     2,
                }
            },
        }
        session_start = time.perf_counter()
        results = tester.run_test(KEY_GREENLEE, session_start)
        assert len(results) == 3

    def test_timestamps_monotonic(self, running_greenlee_server):
        """Each sample's timestamp_sec must be >= the previous sample's."""
        port, command = running_greenlee_server
        tester = AmmeterTester()
        from src.utils.constants import (
            KEY_AMMETERS, KEY_GREENLEE, KEY_SCALE_FACTOR,
            KEY_TESTING, KEY_SAMPLING, KEY_MEASUREMENTS_COUNT, KEY_SAMPLING_FREQ,
            KEY_TOTAL_DURATION,
        )
        tester._config = {
            KEY_AMMETERS: {
                KEY_GREENLEE: {
                    KEY_PORT:         port,
                    KEY_COMMAND:      command,
                    KEY_SCALE_FACTOR: 1.0,
                }
            },
            KEY_TESTING: {
                KEY_SAMPLING: {
                    KEY_MEASUREMENTS_COUNT: 3,
                    KEY_SAMPLING_FREQ:      2.0,
                    KEY_TOTAL_DURATION:     2,
                }
            },
        }
        session_start = time.perf_counter()
        results = tester.run_test(KEY_GREENLEE, session_start)
        timestamps = [r.timestamp_sec for r in results]
        for a, b in zip(timestamps, timestamps[1:]):
            assert b >= a, f"Timestamp went backwards: {a} → {b}"


class TestNormalize:
    def test_normalize_scale_factor(self):
        """_normalize(10.0, {KEY_SCALE_FACTOR: 0.5}) == 5.0"""
        result = AmmeterTester._normalize(10.0, {KEY_SCALE_FACTOR: 0.5})
        assert result == pytest.approx(5.0)


class TestTakeSample:
    def _make_tester_with_cfg(self, port, command):
        """Helper: build an AmmeterTester with a minimal patched config."""
        tester = AmmeterTester()
        from src.utils.constants import (
            KEY_AMMETERS, KEY_GREENLEE, KEY_SCALE_FACTOR,
            KEY_TESTING, KEY_SAMPLING, KEY_MEASUREMENTS_COUNT,
            KEY_SAMPLING_FREQ, KEY_TOTAL_DURATION,
        )
        tester._config = {
            KEY_AMMETERS: {
                KEY_GREENLEE: {
                    KEY_PORT:         port,
                    KEY_COMMAND:      command,
                    KEY_SCALE_FACTOR: 1.0,
                }
            },
            KEY_TESTING: {
                KEY_SAMPLING: {
                    KEY_MEASUREMENTS_COUNT: 1,
                    KEY_SAMPLING_FREQ:      1.0,
                    KEY_TOTAL_DURATION:     1,
                }
            },
        }
        return tester

    def test_timeout_returns_none(self):
        """When all socket.connect calls raise socket.timeout, raw_value is None."""
        tester = self._make_tester_with_cfg(5010, "MEASURE_GREENLEE -get_measurement")
        ammeter_cfg = {
            KEY_PORT:         5010,
            KEY_COMMAND:      "MEASURE_GREENLEE -get_measurement",
            KEY_SCALE_FACTOR: 1.0,
        }

        mock_sock = MagicMock()
        mock_sock.__enter__ = lambda s: s
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_sock.connect.side_effect = socket.timeout("timed out")

        with patch("src.testing.AmmeterTester.socket.socket", return_value=mock_sock):
            result = tester._take_sample(ammeter_cfg, "greenlee")

        assert result.raw_value is None
        assert result.normalized_value is None

    def test_connection_refused_raises(self):
        """When socket.connect raises ConnectionRefusedError it propagates."""
        tester = self._make_tester_with_cfg(5010, "MEASURE_GREENLEE -get_measurement")
        ammeter_cfg = {
            KEY_PORT:         5010,
            KEY_COMMAND:      "MEASURE_GREENLEE -get_measurement",
            KEY_SCALE_FACTOR: 1.0,
        }

        mock_sock = MagicMock()
        mock_sock.__enter__ = lambda s: s
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_sock.connect.side_effect = ConnectionRefusedError("refused")

        with patch("src.testing.AmmeterTester.socket.socket", return_value=mock_sock):
            with pytest.raises(ConnectionRefusedError):
                tester._take_sample(ammeter_cfg, "greenlee")

