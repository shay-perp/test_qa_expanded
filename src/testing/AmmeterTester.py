"""
AmmeterTester — sampler engine for ammeter emulators.

Assumes the ammeter servers (Phase 1) are already running before
run_test() is called.
"""
from __future__ import annotations

import logging
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Optional
import os

from src.utils.config_loader import load_config, get_ammeter_config
from src.utils.constants import (
    HOST,
    KEY_PORT,
    KEY_COMMAND,
    KEY_SCALE_FACTOR,
    KEY_TESTING,
    KEY_SAMPLING,
    KEY_MEASUREMENTS_COUNT,
    KEY_TOTAL_DURATION,
    KEY_SAMPLING_FREQ,
    SOCKET_TIMEOUT_SEC,
    MAX_RETRIES,
)

# ── config path ─────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "config.yaml"
)

logger = logging.getLogger(__name__)


# ── result dataclass ────────────────────────────────────────────────────────

@dataclass
class SampleResult:
    run_id:           str
    ammeter_type:     str
    timestamp_sec:    float
    raw_value:        Optional[float]
    normalized_value: Optional[float]


# ── tester class ────────────────────────────────────────────────────────────

class AmmeterTester:
    def __init__(self) -> None:
        self._config = load_config(CONFIG_PATH)
        self._run_id = str(uuid.uuid4())
        logger.info("AmmeterTester initialised — run_id=%s", self._run_id)

    # ── public ──────────────────────────────────────────────────────────────

    def run_test(self, ammeter_name: str) -> list[SampleResult]:
        """
        Collect measurements_count samples from the named ammeter at
        sampling_frequency_hz, then return the list of SampleResult objects.
        """
        sampling_cfg = self._config[KEY_TESTING][KEY_SAMPLING]
        measurements_count: int   = sampling_cfg[KEY_MEASUREMENTS_COUNT]
        freq: float               = sampling_cfg[KEY_SAMPLING_FREQ]

        ammeter_cfg = get_ammeter_config(self._config, ammeter_name)
        logger.info(
            "Starting test — ammeter=%s  samples=%d  freq=%.2f Hz  run_id=%s",
            ammeter_name, measurements_count, freq, self._run_id,
        )

        results: list[SampleResult] = []
        start = time.perf_counter()

        for i in range(measurements_count):
            target = self._compute_next_target(start, i, freq)
            self._wait_until(target)
            sample = self._take_sample(ammeter_cfg, ammeter_name)
            sample.timestamp_sec = time.perf_counter() - start
            results.append(sample)

        return results

    # ── private helpers ─────────────────────────────────────────────────────

    def _take_sample(self, ammeter_cfg: dict, ammeter_name: str) -> SampleResult:
        """
        Connect to the ammeter server, send the command, and return a
        SampleResult.  Retries up to MAX_RETRIES on socket.timeout.
        Raises immediately on ConnectionRefusedError (server not running).
        """
        port:    int   = ammeter_cfg[KEY_PORT]
        command: bytes = ammeter_cfg[KEY_COMMAND].encode("utf-8")

        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = self._request_raw(port, command)
                logger.info(
                    "Measurement received — ammeter=%s  raw=%.6f  attempt=%d",
                    ammeter_name, raw, attempt,
                )
                normalized = self._normalize(raw, ammeter_cfg)
                return SampleResult(
                    run_id=self._run_id,
                    ammeter_type=ammeter_name,
                    timestamp_sec=0.0,        # overwritten by caller
                    raw_value=raw,
                    normalized_value=normalized,
                )
            except socket.timeout as exc:
                last_exc = exc
                logger.warning(
                    "Socket timeout on attempt %d/%d — ammeter=%s",
                    attempt, MAX_RETRIES, ammeter_name,
                )
            except ConnectionRefusedError as exc:
                logger.error(
                    "Connection refused — ammeter=%s is not running", ammeter_name
                )
                raise

        # All retries exhausted
        logger.warning(
            "All %d retries failed for ammeter=%s — recording None result",
            MAX_RETRIES, ammeter_name,
        )
        return SampleResult(
            run_id=self._run_id,
            ammeter_type=ammeter_name,
            timestamp_sec=0.0,
            raw_value=None,
            normalized_value=None,
        )

    @staticmethod
    def _request_raw(port: int, command: bytes) -> float:
        """
        Performs the same socket exchange as client.request_current_from_ammeter
        but returns the float value instead of printing it.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(SOCKET_TIMEOUT_SEC)
            s.connect((HOST, port))
            s.sendall(command)
            data = s.recv(1024)
        if not data:
            raise ValueError(f"No data received from port {port}")
        return float(data.decode("utf-8"))

    @staticmethod
    def _normalize(raw: float, ammeter_cfg: dict) -> float:
        """Apply scale_factor — the only place normalisation happens."""
        return raw * ammeter_cfg[KEY_SCALE_FACTOR]

    @staticmethod
    def _wait_until(target_time: float) -> None:
        """Busy-wait until perf_counter reaches target_time."""
        while time.perf_counter() < target_time:
            pass

    @staticmethod
    def _compute_next_target(start: float, index: int, freq: float) -> float:
        """Return the absolute perf_counter time for sample #index."""
        return start + (index / freq)


