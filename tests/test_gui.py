"""
Tests for PySide6 GUI integration (interface/main_window.py).
"""

import sys
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from config import Config
from controllers.esp32_controller import ESP32Controller
from interface.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_window():
    cfg = Config.instance()
    cfg.application.simulation_mode = True

    esp_ctrl = ESP32Controller(simulation_mode=True)
    esp_ctrl.set_motor_parameters(8.889, 8.889, (-180.0, 180.0), (-360.0, 360.0))

    return MainWindow(esp32_controller=esp_ctrl)


def test_main_window_startup_and_shutdown(qapp):
    win = _make_window()

    assert win is not None
    assert "Teleoperation Workstation" in win.windowTitle()

    # Audit log is present and receives entries
    assert win._log_text.toPlainText()

    # The arm and camera panels are intentionally not part of this workstation
    assert not hasattr(win, "robot_panel")
    assert not hasattr(win, "vision_panel")

    win._handle_master_stop()
    win.close()


def test_keyboard_teleoperation(qapp):
    from PySide6.QtGui import QKeyEvent

    win = _make_window()

    # Connect the simulated end-effector and enable the drivers
    win._esp32_controller.connect("SIMULATED_PORT", 115200)
    win._esp32_controller.enable()
    win.end_effector_panel.set_motor_status(True)

    for key, text in (
        (Qt.Key_W, "w"),
        (Qt.Key_S, "s"),
        (Qt.Key_A, "a"),
        (Qt.Key_D, "d"),
        (Qt.Key_3, "3"),
        (Qt.Key_Space, " "),
    ):
        win.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, key, Qt.NoModifier, text))

    win.close()
