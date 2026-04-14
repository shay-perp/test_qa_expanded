"""
Shared pytest fixtures for the ammeter testing framework test suite.
"""
from __future__ import annotations

import threading
import time

import pytest

from src.utils.constants import (
    KEY_AMMETERS,
    KEY_PORT,
    KEY_COMMAND,
    KEY_SCALE_FACTOR,
    KEY_GREENLEE,
    KEY_ENTES,
    KEY_CIRCUTOR,
    KEY_TESTING,
    KEY_SAMPLING,
    KEY_MEASUREMENTS_COUNT,
    KEY_TOTAL_DURATION,
    KEY_SAMPLING_FREQ,
)
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Circutor_Ammeter import CircutorAmmeter

# ── port constants for test servers (never overlap with production 5000-5002) ─
_TEST_GREENLEE_PORT = 5010

# ── port constants for integration tests ─────────────────────────────────────
_INTEGRATION_GREENLEE_PORT  = 5020
_INTEGRATION_ENTES_PORT     = 5021
_INTEGRATION_CIRCUTOR_PORT  = 5022

_INTEGRATION_COMMANDS = {
    KEY_GREENLEE: "MEASURE_GREENLEE -get_measurement",
    KEY_ENTES:    "MEASURE_ENTES -get_data",
    KEY_CIRCUTOR: "MEASURE_CIRCUTOR -get_measurement",
}


@pytest.fixture()
def tmp_results_dir(tmp_path):
    """Return a temporary results directory inside pytest's tmp_path."""
    return tmp_path / "results"


@pytest.fixture()
def sample_config():
    """Return a minimal valid config dict with all required keys."""
    return {
        KEY_AMMETERS: {
            KEY_GREENLEE: {
                KEY_PORT:         5010,
                KEY_COMMAND:      "MEASURE_GREENLEE -get_measurement",
                KEY_SCALE_FACTOR: 1.0,
            },
            KEY_ENTES: {
                KEY_PORT:         5011,
                KEY_COMMAND:      "MEASURE_ENTES -get_data",
                KEY_SCALE_FACTOR: 1.0,
            },
            KEY_CIRCUTOR: {
                KEY_PORT:         5012,
                KEY_COMMAND:      "MEASURE_CIRCUTOR -get_measurement",
                KEY_SCALE_FACTOR: 1.0,
            },
        },
        KEY_TESTING: {
            KEY_SAMPLING: {
                KEY_MEASUREMENTS_COUNT: 3,
                KEY_TOTAL_DURATION:     2,
                KEY_SAMPLING_FREQ:      2.0,
            }
        },
    }


@pytest.fixture()
def sample_stats():
    """Return a representative stats dict."""
    return {
        "mean":   5.0,
        "median": 5.0,
        "std":    2.0,
        "min":    1.0,
        "max":    9.0,
    }


@pytest.fixture()
def running_greenlee_server():
    """
    Start a real GreenleeAmmeter server on port 5010 in a daemon thread.
    Yields (port, command).
    Calls stop() and join(timeout=2) after the test completes.
    """
    command = "MEASURE_GREENLEE -get_measurement"
    ammeter = GreenleeAmmeter(_TEST_GREENLEE_PORT, command)

    t = threading.Thread(target=ammeter.start_server, daemon=True)
    t.start()
    time.sleep(0.3)   # give the server a moment to bind and listen

    yield (_TEST_GREENLEE_PORT, command)

    ammeter.stop()
    t.join(timeout=2)


@pytest.fixture()
def running_all_servers():
    """
    Start GreenleeAmmeter (5020), EntesAmmeter (5021), CircutorAmmeter (5022)
    each in a daemon thread with their correct commands.
    Waits 0.5 s for all three to bind.
    Yields {KEY_GREENLEE: (port, command), KEY_ENTES: ..., KEY_CIRCUTOR: ...}.
    Calls stop() and join(timeout=2) for all three after the test.
    """
    specs = {
        KEY_GREENLEE: (GreenleeAmmeter,  _INTEGRATION_GREENLEE_PORT),
        KEY_ENTES:    (EntesAmmeter,     _INTEGRATION_ENTES_PORT),
        KEY_CIRCUTOR: (CircutorAmmeter,  _INTEGRATION_CIRCUTOR_PORT),
    }

    instances: dict[str, object]          = {}
    threads:   dict[str, threading.Thread] = {}

    for key, (Cls, port) in specs.items():
        command  = _INTEGRATION_COMMANDS[key]
        inst     = Cls(port, command)
        instances[key] = inst
        t = threading.Thread(target=inst.start_server, daemon=True)
        t.start()
        threads[key] = t

    time.sleep(0.5)   # let all three servers bind and listen

    yield {
        key: (_INTEGRATION_GREENLEE_PORT if key == KEY_GREENLEE
              else _INTEGRATION_ENTES_PORT if key == KEY_ENTES
              else _INTEGRATION_CIRCUTOR_PORT,
              _INTEGRATION_COMMANDS[key])
        for key in specs
    }

    for key, inst in instances.items():
        inst.stop()
    for key, t in threads.items():
        t.join(timeout=2)


