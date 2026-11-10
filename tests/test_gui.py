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
