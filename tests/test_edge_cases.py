"""
tests/test_edge_cases.py — boundary and error conditions.
"""
from __future__ import annotations

import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.analytics.statistics import compute_stats
from src.utils.config_loader import load_config
from src.testing.AmmeterTester import AmmeterTester
from src.utils.constants import HOST, KEY_PORT, KEY_COMMAND, KEY_SCALE_FACTOR
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter

# Ports reserved for edge-case tests — never overlap with production (5000-5002)
_PORT_DOUBLE_BIND = 5011
_PORT_STOP_RELEASE = 5012


class TestPortBinding:
    def test_port_already_bound(self):
        """Binding two sockets on the same port raises OSError."""
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s1.bind((HOST, _PORT_DOUBLE_BIND))
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Explicitly do NOT set SO_REUSEADDR on s2
            try:
                with pytest.raises(OSError):
                    s2.bind((HOST, _PORT_DOUBLE_BIND))
            finally:
                s2.close()
        finally:
            s1.close()


class TestEmptyResponse:
    def test_empty_response_raises_value_error(self):
        """_request_raw receiving empty bytes must raise ValueError via float('')."""
        mock_sock = MagicMock()
        mock_sock.__enter__ = lambda s: s
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_sock.recv.return_value = b""  # simulate empty response

        with patch("src.testing.AmmeterTester.socket.socket", return_value=mock_sock):
            with pytest.raises(ValueError):
                AmmeterTester._request_raw(5010, b"MEASURE_GREENLEE -get_measurement")


class TestMissingYaml:
    def test_missing_yaml_raises_file_not_found(self):
        """load_config with a non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config("/no/such/file.yaml")


class TestStatsEdgeCases:
    def test_stats_empty_list(self):
        """compute_stats([]) raises ValueError with a non-empty message."""
        with pytest.raises(ValueError, match=r".+"):
            compute_stats([])


class TestServerStopReleasesPort:
    def test_server_stop_releases_port(self):
        """
        After stop() + join(), a new socket can bind to the same port without OSError.
        """
        command = "MEASURE_GREENLEE -get_measurement"
        ammeter = GreenleeAmmeter(_PORT_STOP_RELEASE, command)

        t = threading.Thread(target=ammeter.start_server, daemon=True)
        t.start()
        time.sleep(0.3)   # let the server bind

        ammeter.stop()
        t.join(timeout=2)

        # The port should now be free (SO_REUSEADDR allows immediate rebind)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, _PORT_STOP_RELEASE))  # must not raise
        finally:
            s.close()

