"""
run_tests.py — full integration runner.

Starts all ammeter servers, collects samples via AmmeterTester,
computes stats, persists results, then prints a stability ranking.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
import uuid
from pathlib import Path

# ── project root on sys.path (so src.* imports work when run directly) ──────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.analytics import accuracy, reporter, visualizer
from src.analytics.statistics import compute_stats
from src.testing.AmmeterTester import AmmeterTester
from src.utils.ammeter_registry import AMMETER_REGISTRY
from src.utils.config_loader import load_config, get_ammeter_config
from src.utils.constants import (
    KEY_PORT,
    KEY_COMMAND,
    KEY_ANALYSIS,
    KEY_VISUALIZATION,
    KEY_ENABLED,
    SERVER_STARTUP_SEC,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CONFIG_PATH = _ROOT / "config" / "config.yaml"
results_dir = Path(__file__).parent.parent / "results"


def main() -> None:
    config = load_config(str(CONFIG_PATH))

    # ── one session_id for this entire run ───────────────────────────────────
    session_id = str(uuid.uuid4())
    logger.info("Session started — session_id=%s", session_id)

    # ── start all ammeter servers ────────────────────────────────────────────
    servers: dict[str, tuple] = {}
    threads: dict[str, threading.Thread] = {}

    for name, AmmeterClass in AMMETER_REGISTRY.items():
        cfg  = get_ammeter_config(config, name)
        inst = AmmeterClass(cfg[KEY_PORT], cfg[KEY_COMMAND])
        servers[name] = (inst, cfg)
        t = threading.Thread(
            target=inst.start_server,
            daemon=True,
            name=f"{name}-Thread",
        )
        t.start()
        threads[name] = t

    logger.info("Waiting %ss for servers to be ready …", SERVER_STARTUP_SEC)
    time.sleep(SERVER_STARTUP_SEC)

    # ── shared clock + parallel sampling ────────────────────────────────────
    # session_start is the single time reference for ALL ammeters.
    # Every timestamp_sec in every SampleResult is relative to this value,
    # so samples from different ammeters can be compared on the same axis.
    session_start = time.perf_counter()

    raw_results:  dict[str, list] = {}   # name -> list[SampleResult]
    raw_testers:  dict[str, AmmeterTester] = {}
    results_lock  = threading.Lock()

    def sample_ammeter(name: str) -> None:
        tester  = AmmeterTester()
        samples = tester.run_test(name, session_start)
        with results_lock:
            raw_results[name] = samples
            raw_testers[name] = tester

    sample_threads = [
        threading.Thread(target=sample_ammeter, args=(name,), name=f"Sample-{name}")
        for name in AMMETER_REGISTRY
    ]
    for t in sample_threads:
        t.start()
    for t in sample_threads:
        t.join()

    # ── compute stats and persist per-run artifacts (sequential is fine here)
    all_results:  dict[str, list] = {}   # name -> list[SampleResult]
    all_stats:    dict[str, dict] = {}   # name -> stats dict
    ammeter_runs: dict[str, dict] = {}   # name -> index entry {run_id, mean, std}

    for name in AMMETER_REGISTRY:
        samples = raw_results.get(name, [])
        tester  = raw_testers.get(name)
        if not samples or tester is None:
            logger.warning("No results for %s — skipping.", name)
            continue

        valid_values = [
            s.normalized_value
            for s in samples
            if s.normalized_value is not None
        ]

        if not valid_values:
            logger.warning("No valid samples for %s — skipping stats.", name)
            continue

        stats = compute_stats(valid_values)
        all_results[name] = samples
        all_stats[name]   = stats

        reporter.save_run(
            run_id=tester._run_id,
            session_id=session_id,
            samples=samples,
            stats=stats,
            ammeter_type=name,
            results_dir=results_dir,
            config=config,
        )

        ammeter_runs[name] = {
            "run_id": tester._run_id,
            "mean":   stats["mean"],
            "std":    stats["std"],
        }

    # ── write one session entry to index.json ────────────────────────────────
    if ammeter_runs:
        reporter.write_session_index(session_id, ammeter_runs, results_dir)

    # ── plot_comparison once — saved under results/sessions/{session_id}/ ────
    viz_enabled = (
        config.get(KEY_ANALYSIS, {})
              .get(KEY_VISUALIZATION, {})
              .get(KEY_ENABLED, False)
    )
    if viz_enabled and all_results:
        session_dir = results_dir / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        visualizer.plot_comparison(all_results, session_id, session_dir)

    # ── stability ranking ────────────────────────────────────────────────────
    if all_stats:
        ranking = accuracy.rank_ammeters(all_stats)
        accuracy.print_ranking(ranking)

    # ── stop all servers cleanly ─────────────────────────────────────────────
    for name, (inst, _) in servers.items():
        inst.stop()
    for name, t in threads.items():
        t.join(timeout=2)

    logger.info("All ammeters shut down cleanly.")


if __name__ == "__main__":
    main()

