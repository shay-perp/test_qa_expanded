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
from pathlib import Path

# ── project root on sys.path (so src.* imports work when run directly) ──────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.analytics import accuracy, reporter
from src.analytics import visualizer
from src.analytics.statistics import compute_stats
from src.testing.AmmeterTester import AmmeterTester
from src.utils.ammeter_registry import AMMETER_REGISTRY
from src.utils.config_loader import load_config, get_ammeter_config
from src.utils.constants import (
    KEY_PORT,
    KEY_COMMAND,
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

    # ── collect samples and persist results ──────────────────────────────────
    all_results:   dict[str, list] = {}   # name -> list[SampleResult]
    all_stats:     dict[str, dict] = {}   # name -> stats dict
    run_dirs:      dict[str, Path] = {}   # name -> run directory
    shared_run_id: str = ""

    for name in AMMETER_REGISTRY:
        tester  = AmmeterTester()
        samples = tester.run_test(name)

        if not shared_run_id:
            shared_run_id = tester._run_id

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

        run_dirs[name] = reporter.save_run(
            run_id=tester._run_id,
            samples=samples,
            stats=stats,
            ammeter_type=name,
            results_dir=results_dir,
            config=config,
        )

    # ── plot_comparison once — uses complete all_results ─────────────────────
    from src.utils.constants import KEY_ANALYSIS, KEY_VISUALIZATION, KEY_ENABLED
    viz_enabled = (
        config.get(KEY_ANALYSIS, {})
              .get(KEY_VISUALIZATION, {})
              .get(KEY_ENABLED, False)
    )
    if viz_enabled and all_results and shared_run_id:
        comparison_dir = results_dir / "runs" / shared_run_id
        comparison_dir.mkdir(parents=True, exist_ok=True)
        visualizer.plot_comparison(all_results, shared_run_id, comparison_dir)

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

