# Testing Framework — Developer Guide

## Overview

This testing framework emulates three physical ammeter devices (Greenlee, ENTES,
CIRCUTOR) as in-process TCP servers and drives a configurable sampling loop
against them. Each run:

1. Starts all ammeter servers from the registry in daemon threads.
2. Collects `measurements_count` samples from every ammeter at
   `sampling_frequency_hz` using a precise busy-wait timing loop.
3. Computes descriptive statistics (mean, median, std, min, max) per ammeter.
4. Persists raw CSV data, per-run JSON summaries, and a session index.
5. Optionally produces time-series and comparison plots (PNG).
6. Prints a stability ranking sorted by coefficient of variation (CV).

---

## Runtime Dependencies

The following packages from `requirements.txt` are actively used:

| Package | Used for |
|---------|----------|
| `pyyaml` | Loading `config/config.yaml` via `yaml.safe_load()` |
| `numpy` | Descriptive statistics in `src/analytics/statistics.py` |
| `matplotlib` | Time-series and boxplot charts in `src/analytics/visualizer.py` |

---

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

> `pytest` is the only additional development dependency beyond `requirements.txt`.
> All test mocking uses the stdlib `unittest.mock` — no extra packages required.

---

## How to Run the Emulators and Tests

From the project root:

```bash
python examples/run_tests.py
```

This will:
- Start Greenlee (port 5000), ENTES (port 5001), and CIRCUTOR (port 5002) servers.
- Collect 10 samples per ammeter at 2 Hz (configurable in `config/config.yaml`).
- Save results under `results/`.
- Print the stability ranking to stdout.
- Stop all servers and exit cleanly.

To adjust sampling parameters, edit `config/config.yaml`:

```yaml
testing:
  sampling:
    measurements_count: 10
    total_duration_seconds: 5
    sampling_frequency_hz: 2
```

---

## How to Run pytest

```bash
pytest tests/ -v
```

---

## Test Suite

The test suite is organised into five files:

**`test_analytics.py`** — unit tests for pure functions.
These tests run with no servers, no files, no network.

- `compute_stats` with known inputs (`[1,2,3,4,5]` → mean=3.0, min=1.0, max=5.0)
  — verifies the statistical engine is numerically correct before any real data flows through it
- `compute_stats` with a single value (std == 0, no exception)
  — ensures the framework handles degenerate cases without crashing mid-session
- `compute_stats` with empty list (raises `ValueError`)
  — prevents silent NaN propagation into saved JSON files
- `coefficient_of_variation` correctness (std=1, mean=10 → CV=10.0)
  — the CV is the primary ranking metric; a bug here corrupts every accuracy report
- `rank_ammeters` sorts by CV ascending
  — the most stable device must appear first; wrong order misleads the engineer reading the report
- reporter creates `raw_samples.csv` and `summary.json` in the correct path
  — verifies the session directory structure is built correctly before integration tests run
- two sequential `save_run` calls produce two entries in `index.json`
  — historical retrieval depends on `index.json` growing correctly across sessions

**`test_infrastructure.py`** — configuration and wiring tests.
These tests verify that the config-driven architecture holds together correctly.

- `config.yaml` loads and returns correct port (`int`) and command (`str`) per ammeter
  — the entire system collapses if a port loads as a string or a command loads as `None`
- missing config file raises `FileNotFoundError`
  — fails fast with a clear error instead of a confusing `AttributeError` later
- missing ammeter key raises `KeyError`
  — catches config typos before a server starts on the wrong port
- each ammeter class encodes `get_current_command` from `self._command`, not a hardcoded literal
  — proves that removing hardcoded strings actually worked; the server must match the client
- `AMMETER_REGISTRY` contains exactly `KEY_GREENLEE`, `KEY_ENTES`, `KEY_CIRCUTOR`
  — the registry drives everything: missing a key means one ammeter is silently skipped

**`test_sampler.py`** — sampler engine tests.
These tests use a real `GreenleeAmmeter` server on port 5010 for integration paths,
and mock socket for failure paths.

- `run_test` returns exactly `measurements_count` `SampleResult` objects
  — the analytics layer expects a fixed-length list; a short list produces wrong statistics
- timestamps are monotonically non-decreasing across all samples
  — a non-monotonic timestamp means the shared session clock is broken,
    which invalidates cross-ammeter time comparisons
- `_normalize` applies `scale_factor` correctly (`10.0 × 0.5 == 5.0`)
  — normalization happens only here; a bug silently scales all saved values
- socket timeout produces `SampleResult` with `raw_value=None`, no crash
  — in a real embedded environment a device can be temporarily unresponsive;
    the sampler must record the gap and continue, not abort the session
- `ConnectionRefusedError` propagates out of `_take_sample`
  — if a server is not running the error must surface immediately,
    not be swallowed and silently produce a session of `None` values

**`test_edge_cases.py`** — boundary and failure tests.
These tests verify the system behaves correctly at its limits.

- binding two sockets on the same port raises `OSError`
  — confirms `SO_REUSEADDR` fix works and two servers cannot accidentally share a port
- empty socket response raises `ValueError` in `_request_raw`
  — an ammeter that connects but sends nothing must not be treated as a valid 0 A reading
- `config_loader` called with nonexistent path raises `FileNotFoundError`
  — clear error on startup rather than a crash inside a running session
- `compute_stats([])` raises `ValueError` with a clear message
  — an empty session (all timeouts) must not produce NaN in the accuracy report
- starting and stopping a server releases the port for immediate reuse
  — the `stop()` + `join()` mechanism must actually free the port;
    if it does not, re-running the test suite within seconds will fail with `AddressInUse`

**`test_integration.py`** — full session flow tests.
These tests start all three real ammeter servers internally on ports 5020–5022.
The production servers on 5000–5002 do not need to be running.

- full session creates correct directory structure under `sessions/{session_id}/runs/{ammeter_type}/`
  — end-to-end proof that the `session_id` scoping, parallel sampling,
    and reporter work together correctly as a complete pipeline
- `raw_samples.csv` contains correct column headers
  — any column rename or reorder breaks downstream tools that parse the CSV by name
- `accuracy_report.json` contains all required fields including `per_ammeter_stats`
  — the report is the primary deliverable; a missing field means the engineer
    looking at `results/sessions/` gets an incomplete picture
- `index.json` session entry contains `cv_percent` per ammeter
  — historical comparison across sessions depends on `cv_percent` being present
    in the index; without it you can only compare means, not stability

---

## Results Structure

```
results/
├── index.json
└── sessions/
    └── {session_id}/
        ├── accuracy_report.json
        ├── plot_comparison.png
        ├── plot_accuracy.png
        └── runs/
            ├── greenlee/
            │   ├── raw_samples.csv
            │   ├── summary.json
            │   └── plot_timeseries.png
            ├── entes/
            │   └── (same files)
            └── circutor/
                └── (same files)
```

### `index.json` entry format

Each invocation of `run_tests.py` appends one entry:

```json
{
  "session_id": "uuid",
  "iso_timestamp": "...",
  "ammeters": {
    "greenlee":  {"run_id": "uuid", "mean": 0.18, "std": 0.21, "cv_percent": 55.9},
    "entes":     {"run_id": "uuid", "mean": 61.6, "std": 27.7, "cv_percent": 44.9},
    "circutor":  {"run_id": "uuid", "mean": 0.03, "std": 0.01, "cv_percent": 49.1}
  },
  "most_stable": "entes"
}
```

---

### `accuracy_report.json` fields

Written once per session to `results/sessions/{session_id}/accuracy_report.json`.

| Field | Description |
|-------|-------------|
| `stability_ranking` | Ammeters sorted by CV ascending — lower CV = more repeatable readings in this session |
| `relative_precision` | Same ammeters normalised to their own mean before comparing — allows fair cross-scale comparison (e.g. ENTES at ~60 A vs Greenlee at ~0.1 A) |
| `per_ammeter_stats` | Full descriptive statistics for each ammeter: `mean`, `median`, `std`, `min`, `max` of all `normalized_value` samples |
| `most_stable` | Ammeter with the lowest CV in this session |
| `note` | Reminder that CV measures precision (repeatability), not absolute accuracy |

---

## Design Decisions

### Why `session_id`?

A single invocation of `run_tests.py` tests all three ammeters together.
Grouping their runs under one `session_id` in `index.json` makes it trivial
to retrieve and compare all ammeters from a single test session without
joining on timestamps. Each ammeter still gets its own `run_id` and its own
`runs/{run_id}/` directory so individual run artefacts remain self-contained.

### Why `time.perf_counter()` for timing?

`time.perf_counter()` is the highest-resolution monotonic clock available in
Python. Unlike `time.time()`, it is not affected by NTP adjustments or system
clock changes, which makes it reliable for sub-second scheduling and for
computing accurate inter-sample intervals.

### Parallel Sampling and Normalized Timestamps

All three ammeters are sampled concurrently in separate threads.
A single `session_start = time.perf_counter()` is created once before
any sampling thread starts. Every sample's `timestamp_sec` field is
computed as:

```
sample.timestamp_sec = time.perf_counter() - session_start
```

This means timestamps are relative to a single shared reference point,
so a greenlee sample at `t=2.5s` and an entes sample at `t=2.5s` represent
the same moment in real time. This is essential for embedded systems
testing where comparing device behaviour at the same instant is required.
Total sampling time is ~5 seconds regardless of the number of ammeters
because all three run in parallel — not ~15 seconds sequentially.

### Why Coefficient of Variation (CV)?

CV = (std / mean) × 100 normalises the spread relative to the magnitude of
the signal. This allows fair stability comparisons across ammeters whose
measurement scales differ by orders of magnitude (e.g. ENTES measures in
tens of amps while CIRCUTOR measures in milliamps). A lower CV means the
ammeter produces more consistent readings regardless of its absolute range.

---

## Accuracy vs Precision

### Precision

Precision is the **repeatability** of measurements — how tightly grouped
successive readings are. It is quantified in this framework by the
**Coefficient of Variation (CV)**:

```
CV = (std / mean) × 100
```

A lower CV means the ammeter produces more consistent readings. `rank_ammeters()`
sorts by CV ascending so the most precise device appears first.

### Accuracy

Accuracy is the **closeness to the true value** — how well a measurement
reflects the physical quantity being measured. Determining accuracy requires
a **known calibrated reference**. Without such a reference, absolute accuracy
cannot be assessed from emulated readings alone. This framework does not
attempt to measure accuracy in the absolute sense.

### What `compare_ammeters()` does

`compare_ammeters()` addresses the challenge of comparing devices that operate
on entirely different physical scales (e.g. ENTES producing ~70 A readings
vs Greenlee producing ~0.1 A readings). A raw standard-deviation comparison
would be meaningless.

The function normalises each ammeter's sample list to its **own mean**,
producing dimensionless values centred at 1.0:

```
normalised_i = reading_i / mean
```

The **relative standard deviation** of this dimensionless series is then a
scale-independent measure of how repeatable the device is. The output is
sorted ascending — the device with the lowest relative std is the most
precise **relative to its own operating range**.

### Conclusion

| Metric | What it measures | Function |
|--------|-----------------|----------|
| CV (%) | Precision relative to the device's mean | `rank_ammeters()` |
| Relative Std | Precision normalised across scales | `compare_ammeters()` |
| Absolute accuracy | Closeness to true value | ⚠ Requires calibrated reference — not available here |

This framework fully quantifies **precision** and **relative stability**.
For absolute accuracy assessment, a traceable reference measurement device
would be required alongside the emulators.

