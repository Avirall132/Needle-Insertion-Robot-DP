"""
Tests for PySide6 GUI integration (interface/main_window.py).
"""

import sys
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from config import Config
from controllers.ur_controller import URController
from controllers.esp32_controller import ESP32Controller
from vision.camera import CameraManager
from vision.needle_detector import MockDetector
from interface.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_main_window_startup_and_shutdown(qapp):
    cfg = Config.instance()
    cfg.application.simulation_mode = True

    ur_ctrl = URController(simulation_mode=True)
    esp_ctrl = ESP32Controller(simulation_mode=True)
    esp_ctrl.set_motor_parameters(8.889, 8.889, (-180.0, 180.0), (-360.0, 360.0))
    cam = CameraManager()
    det = MockDetector()

    win = MainWindow(
        ur_controller=ur_ctrl,
        esp32_controller=esp_ctrl,
        camera_manager=cam,
        needle_detector=det,
    )

    # Window should be created and responsive
    assert win is not None
    assert "Teleoperation Workstation" in win.windowTitle()

    # Test master stop
    win._handle_master_stop()

    # Simulate close event
    win.close()


def test_keyboard_teleoperation(qapp):
    from PySide6.QtGui import QKeyEvent

    cfg = Config.instance()
    cfg.application.simulation_mode = True

    ur_ctrl = URController(simulation_mode=True)
    esp_ctrl = ESP32Controller(simulation_mode=True)
    esp_ctrl.set_motor_parameters(8.889, 8.889, (-180.0, 180.0), (-360.0, 360.0))
    cam = CameraManager()
    det = MockDetector()

    win = MainWindow(
        ur_controller=ur_ctrl,
        esp32_controller=esp_ctrl,
        camera_manager=cam,
        needle_detector=det,
    )

    # Connect ESP32 in simulation
    esp_ctrl.connect("SIMULATED_PORT", 115200)
    esp_ctrl.enable()
    win.end_effector_panel.set_motor_status(True)

    # Press W (Advance)
    ev_w = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_W, Qt.NoModifier, "w")
    win.keyPressEvent(ev_w)

    # Press S (Retract)
    ev_s = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_S, Qt.NoModifier, "s")
    win.keyPressEvent(ev_s)

    # Press A (Rotate CCW)
    ev_a = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.NoModifier, "a")
    win.keyPressEvent(ev_a)

    # Press D (Rotate CW)
    ev_d = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_D, Qt.NoModifier, "d")
    win.keyPressEvent(ev_d)

    # Press 3 (Speed Preset Normal)
    ev_3 = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_3, Qt.NoModifier, "3")
    win.keyPressEvent(ev_3)

    # Press Space (ALL STOP)
    ev_sp = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Space, Qt.NoModifier, " ")
    win.keyPressEvent(ev_sp)

    win.close()
