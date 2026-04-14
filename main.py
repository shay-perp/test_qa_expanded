import threading
import time
import os

from Ammeters.client import request_current_from_ammeter
from src.utils.ammeter_registry import AMMETER_REGISTRY
from src.utils.config_loader import load_config, get_ammeter_config
from src.utils.constants import KEY_PORT, KEY_COMMAND, SERVER_STARTUP_SEC

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.yaml")


if __name__ == "__main__":
    config = load_config(CONFIG_PATH)

    # Build instances and threads from the registry — no ammeter names hardcoded here
    instances = {}
    threads   = {}
    for name, AmmeterClass in AMMETER_REGISTRY.items():
        cfg = get_ammeter_config(config, name)
        instance = AmmeterClass(cfg[KEY_PORT], cfg[KEY_COMMAND])
        instances[name] = (instance, cfg)
        t = threading.Thread(target=instance.start_server, daemon=True, name=f"{name}-Thread")
        threads[name] = t
        t.start()

    # Wait for all servers to be ready
    time.sleep(SERVER_STARTUP_SEC)

    # Request one measurement from each registered ammeter
    for name, (instance, cfg) in instances.items():
        request_current_from_ammeter(cfg[KEY_PORT], cfg[KEY_COMMAND].encode('utf-8'))

    # Signal every server to stop, then join its thread
    for name, (instance, cfg) in instances.items():
        instance.stop()
    for name, t in threads.items():
        t.join(timeout=2)

    print("All ammeters shut down cleanly.")
