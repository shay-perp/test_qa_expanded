import yaml
from src.utils.constants import (
    KEY_AMMETERS, KEY_PORT, KEY_COMMAND, KEY_SCALE_FACTOR,
)
def load_config(path: str) -> dict:
    """Load and return the YAML config file as a dict."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)
def get_ammeter_config(config: dict, name: str) -> dict:
    """
    Return a dict with port, command and scale_factor for the named ammeter.
    Raises KeyError if the ammeter block is missing from config.
    """
    ammeter_cfg = config[KEY_AMMETERS][name]
    return {
        KEY_PORT: ammeter_cfg[KEY_PORT],
        KEY_COMMAND: ammeter_cfg[KEY_COMMAND],
        KEY_SCALE_FACTOR: ammeter_cfg.get(KEY_SCALE_FACTOR, 1.0),
    }
