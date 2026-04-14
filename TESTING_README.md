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

## Results Structure

```
results/
├── index.json                        # one entry per session (all ammeters grouped)
├── runs/
│   ├── {run_id}/                     # one directory per ammeter per session
│   │   ├── raw_samples.csv           # timestamp_sec, raw_value, normalized_value, ammeter_type
│   │   ├── summary.json              # run_id, session_id, stats, measurements_count
│   │   └── plot_timeseries.png       # line chart (only if visualization.enabled = true)
└── sessions/
    └── {session_id}/
        └── plot_comparison.png       # boxplot of all ammeters (only if visualization.enabled = true)
```

### `index.json` entry format

Each invocation of `run_tests.py` appends one entry:

```json
{
  "session_id": "uuid",
  "iso_timestamp": "2026-04-14T11:00:00+00:00",
  "ammeters": {
    "greenlee":  {"run_id": "uuid", "mean": 0.18, "std": 0.21},
    "entes":     {"run_id": "uuid", "mean": 68.4, "std": 31.0},
    "circutor":  {"run_id": "uuid", "mean": 0.03, "std": 0.01}
  }
}
```

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

