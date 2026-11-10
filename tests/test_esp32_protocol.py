"""
Tests for ESP32 controller and JSON protocol (controllers/esp32_controller.py).
"""

import pytest
from controllers.esp32_controller import (
    ESP32Controller,
    CMD_CONNECT,
    CMD_DISCONNECT,
    CMD_MOVE_ABS,
    CMD_STOP,
    CMD_HOME,
    CMD_ENABLE,
    CMD_DISABLE,
)


def test_esp32_simulation_connect_and_disconnect():
    ctrl = ESP32Controller(simulation_mode=True)
    assert not ctrl.is_connected

    success = ctrl.connect("COM3", 115200)
    assert success is True
    assert ctrl.is_connected is True

    ctrl.disconnect()
    assert ctrl.is_connected is False


def test_esp32_sequence_ids():
    ctrl = ESP32Controller(simulation_mode=True)
    ctrl.connect("COM3")

    resp1 = ctrl.send_command(CMD_ENABLE)
    assert resp1.get("ok") is True
    id1 = resp1.get("id")

    resp2 = ctrl.send_command(CMD_DISABLE)
    assert resp2.get("ok") is True
    id2 = resp2.get("id")

    # Sequence ID must auto-increment
    assert id2 > id1
    ctrl.disconnect()


def test_esp32_movement_safety_unconfigured_rejection():
    # Per safety requirements: real movement must NOT be allowed
    # until calibration / motor parameters are entered
    ctrl = ESP32Controller(simulation_mode=False)  # Non-simulated needs configured params
    assert not ctrl.motor_params_configured

    resp = ctrl.move_axis(axis=1, target_deg=30.0, speed=10.0)
    assert resp.get("ok") is False
    assert "not configured" in resp.get("error", "").lower()


def test_esp32_configured_movement_and_limits():
    ctrl = ESP32Controller(simulation_mode=True)
    ctrl.connect("COM3")

    ctrl.set_motor_parameters(
        axis1_steps_per_deg=8.889,
        axis2_steps_per_deg=8.889,
        axis1_limits=(-90.0, 90.0),
        axis2_limits=(-180.0, 180.0),
    )
    assert ctrl.motor_params_configured is True

    # Valid move
    resp = ctrl.move_axis(axis=1, target_deg=45.0, speed=10.0)
    assert resp.get("ok") is True

    # Invalid move exceeding software travel limits (-90 to +90)
    resp_bad = ctrl.move_axis(axis=1, target_deg=120.0, speed=10.0)
    assert resp_bad.get("ok") is False
    assert "limit" in resp_bad.get("error", "").lower()

    ctrl.disconnect()


def test_esp32_homing_and_status():
    ctrl = ESP32Controller(simulation_mode=True)
    ctrl.connect("COM3")

    # Homing
    resp = ctrl.home(axis=1)
    assert resp.get("ok") is True

    status = ctrl.get_status()
    assert status.get("connected") is True
    axes = status.get("axes", [])
    assert len(axes) == 2
    assert axes[0]["homed"] is True

    ctrl.disconnect()
