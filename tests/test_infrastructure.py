"""
tests/test_infrastructure.py — config loader, ammeter classes, registry.
"""
from __future__ import annotations

import os

import pytest

from src.utils.config_loader import load_config, get_ammeter_config
from src.utils.constants import (
    KEY_AMMETERS,
    KEY_PORT,
    KEY_COMMAND,
    KEY_GREENLEE,
    KEY_ENTES,
    KEY_CIRCUTOR,
)
from src.utils.ammeter_registry import AMMETER_REGISTRY
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Circutor_Ammeter import CircutorAmmeter

# Path to the real config, relative to project root
_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "config.yaml"
)


class TestConfigLoader:
    def test_config_loader_valid(self):
        """Load real config.yaml and check every ammeter has a valid port and command."""
        config = load_config(_CONFIG_PATH)
        for name in (KEY_GREENLEE, KEY_ENTES, KEY_CIRCUTOR):
            ammeter_cfg = get_ammeter_config(config, name)
            assert isinstance(ammeter_cfg[KEY_PORT], int), \
                f"{name} port should be int"
            assert isinstance(ammeter_cfg[KEY_COMMAND], str), \
                f"{name} command should be str"
            assert len(ammeter_cfg[KEY_COMMAND]) > 0, \
                f"{name} command should be non-empty"

    def test_config_loader_missing_file(self):
        """load_config with a non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_config_loader_missing_ammeter_key(self):
        """get_ammeter_config raises KeyError when ammeter block is absent."""
        config = {KEY_AMMETERS: {}}
        with pytest.raises(KeyError):
            get_ammeter_config(config, KEY_GREENLEE)


class TestCommandEncoding:
    """Each ammeter class returns get_current_command == command.encode('utf-8')."""

    @pytest.mark.parametrize("AmmeterClass, command", [
        (GreenleeAmmeter, "MEASURE_GREENLEE -get_measurement"),
        (EntesAmmeter,    "MEASURE_ENTES -get_data"),
        (CircutorAmmeter, "MEASURE_CIRCUTOR -get_measurement"),
    ])
    def test_command_encoding(self, AmmeterClass, command):
        ammeter = AmmeterClass(port=0, command=command)
        assert ammeter.get_current_command == command.encode("utf-8")


class TestRegistry:
    def test_registry_keys(self):
        """AMMETER_REGISTRY keys exactly match the three name constants."""
        assert set(AMMETER_REGISTRY.keys()) == {KEY_GREENLEE, KEY_ENTES, KEY_CIRCUTOR}

