"""
Tests for configuration management (config.py).
"""

import json
from pathlib import Path

import pytest
from config import Config, ConfigData, RobotConfig, ESP32Config


@pytest.fixture(autouse=True)
def reset_config_singleton(tmp_path: Path):
    """Ensure each test runs with a fresh Config instance using a temporary file."""
    Config.reset()
    yield
    Config.reset()


def test_default_config_creation(tmp_path: Path):
    test_cfg_path = tmp_path / "test_config.json"
    cfg = Config(test_cfg_path)

    # Defaults check
    assert cfg.application.simulation_mode is True
    assert cfg.robot.enabled is False
    assert cfg.robot.ip is None
    assert cfg.esp32.baud_rate == 115200
    assert cfg.camera.fps == 30
    assert test_cfg_path.exists()


def test_config_save_and_reload(tmp_path: Path):
    test_cfg_path = tmp_path / "test_config.json"
    cfg = Config(test_cfg_path)

    cfg.robot.ip = "192.168.1.100"
    cfg.esp32.serial_port = "COM4"
    cfg.vision.confidence_threshold = 0.65
    cfg.save()

    # Reset and reload
    Config.reset()
    cfg_reloaded = Config(test_cfg_path)

    assert cfg_reloaded.robot.ip == "192.168.1.100"
    assert cfg_reloaded.esp32.serial_port == "COM4"
    assert pytest.approx(cfg_reloaded.vision.confidence_threshold, 0.01) == 0.65


def test_config_validation_clamping(tmp_path: Path):
    test_cfg_path = tmp_path / "invalid_config.json"
    # Write invalid data
    bad_data = {
        "esp32": {"baud_rate": -9600},
        "vision": {"confidence_threshold": 1.5},
        "application": {"log_level": "INVALID_LEVEL"},
        "robot": {"max_velocity": -1.0},
    }
    test_cfg_path.write_text(json.dumps(bad_data), encoding="utf-8")

    cfg = Config(test_cfg_path)

    # Should clamp / reset to defaults
    assert cfg.esp32.baud_rate == 115200
    assert cfg.vision.confidence_threshold == 0.5
    assert cfg.application.log_level == "INFO"
    assert cfg.robot.max_velocity is None
