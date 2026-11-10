"""
Robotic Needle Insertion Teleoperation System.

Primary application entry point.
Initializes configuration, controllers, background workers, and PySide6 GUI.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from config import Config
from controllers.esp32_controller import ESP32Controller
from controllers.ur_controller import URController
from interface.main_window import MainWindow
from interface.styles import DARK_STYLESHEET
from vision.camera import CameraManager
from vision.needle_detector import create_detector


def setup_logging(log_level: str = "INFO") -> None:
    """Configure console and rotating file logging."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "teleop.log"

    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)-7s] [%(name)s]: %(message)s",
        datefmt="%H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def main() -> int:
    """Application entry point."""
    # 1. Initialize configuration singleton
    cfg = Config.instance()

    # 2. Setup logging
    setup_logging(cfg.application.log_level)
    logger = logging.getLogger("main")
    logger.info("Starting Robotic Needle Insertion Teleoperation System...")
    logger.info("Simulation mode: %s", cfg.application.simulation_mode)

    # 3. Setup PySide6 Application with High-DPI support
    # (High DPI is handled by default in Qt6, but setting attribute ensures compliance)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName("Robotic Needle Insertion System")
    app.setOrganizationName("Healthcare Robotics Research")
    app.setStyleSheet(DARK_STYLESHEET)

    # 4. Instantiate Subsystem Controllers
    logger.info("Initializing UR7e controller (sim=%s)...", cfg.application.simulation_mode)
    ur_controller = URController(
        simulation_mode=cfg.application.simulation_mode,
        max_velocity=cfg.robot.max_velocity,
        max_acceleration=cfg.robot.max_acceleration,
    )

    logger.info("Initializing ESP32 controller (sim=%s)...", cfg.application.simulation_mode)
    esp32_controller = ESP32Controller(
        simulation_mode=cfg.application.simulation_mode,
        baud_rate=cfg.esp32.baud_rate,
    )

    # For development/demonstration, allow movement in simulation mode
    if cfg.application.simulation_mode:
        esp32_controller.set_motor_parameters(
            axis1_steps_per_mm=8.889,
            axis2_steps_per_deg=8.889,
            axis1_limits=(-180.0, 180.0),
            axis2_limits=(-360.0, 360.0),
        )

    logger.info("Initializing Camera Manager...")
    camera_manager = CameraManager()
    camera_manager.set_resolution(cfg.camera.width, cfg.camera.height)
    camera_manager.set_fps(cfg.camera.fps)

    logger.info("Initializing Needle Detector...")
    model_path = cfg.vision.model_path if cfg.vision.enabled else None
    detector = create_detector(model_path)

    # 5. Build and show main window
    window = MainWindow(
        ur_controller=ur_controller,
        esp32_controller=esp32_controller,
        camera_manager=camera_manager,
        needle_detector=detector,
    )
    window.show()

    logger.info("Application workstation active. Entering event loop.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
