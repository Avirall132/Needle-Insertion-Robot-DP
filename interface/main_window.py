"""
Main Window for the Robotic Needle Insertion Teleoperation System.

Integrates the four primary sections:
- System Status Header (subsystem health, simulation mode indicator, safety disclaimer)
- UR7e Robot Control Panel
- ESP32 End-Effector Panel
- Live Vision & ML Detection Panel
- System Activity Log Panel (bottom dock/section)

Coordinates background worker threads and manages application lifecycle.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QCloseEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config import Config
from controllers.esp32_controller import ESP32Controller
from controllers.ur_controller import URController
from interface.end_effector_panel import EndEffectorPanel
from interface.robot_panel import RobotPanel
from interface.styles import (
    COLOR_ACCENT,
    COLOR_BG_DARK,
    COLOR_BG_PANEL,
    COLOR_BORDER,
    COLOR_STATUS_CONNECTED,
    COLOR_STATUS_DISCONNECTED,
    COLOR_STATUS_STOPPED,
    COLOR_STATUS_WARNING,
    create_status_indicator,
    update_status_indicator,
)
from interface.vision_panel import VisionPanel
from vision.camera import CameraManager
from vision.needle_detector import Detection, NeedleDetector
from workers.esp32_worker import ESP32Worker
from workers.ur_worker import URWorker
from workers.vision_worker import VisionWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Primary teleoperation dashboard for the needle insertion system.
    """

    def __init__(
        self,
        ur_controller: URController,
        esp32_controller: ESP32Controller,
        camera_manager: CameraManager,
        needle_detector: NeedleDetector,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._cfg = Config.instance()
        self._ur_controller = ur_controller
        self._esp32_controller = esp32_controller
        self._camera_manager = camera_manager
        self._needle_detector = needle_detector

        self.setWindowTitle("Robotic Needle Insertion System - Teleoperation Workstation")
        self.resize(1600, 960)
        self.setMinimumSize(1280, 800)

        # Build UI layout
        self._build_ui()

        # Instantiate background workers
        self._ur_worker = URWorker(self._ur_controller)
        self._esp32_worker = ESP32Worker(self._esp32_controller)
        self._vision_worker = VisionWorker(self._camera_manager, self._needle_detector)

        # Wire all signals
        self._connect_signals()

        # Start workers
        self._ur_worker.start()
        self._esp32_worker.start()
        self._vision_worker.start()

        # Initial port scan for ESP32
        self._refresh_esp32_ports()

        # Initial log entry
        sim_str = "ENABLED (Dry-run)" if self._cfg.application.simulation_mode else "DISABLED (Hardware active)"
        self.log_message("SYSTEM", f"Application initialized. Simulation mode: {sim_str}")
        self.log_message("SAFETY", "NOTICE: Software stop controls do NOT replace physical E-Stop buttons.")

    # ==================================================================
    # UI Layout Construction
    # ==================================================================
    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. System Status Header Bar
        header_widget = self._build_header_bar()
        main_layout.addWidget(header_widget)

        # 2. Main Workstation Area (Splitter between Controls and Vision)
        workstation_splitter = QSplitter(Qt.Horizontal)
        workstation_splitter.setChildrenCollapsible(False)

        # Left / Middle side: Robot Panel and End-Effector Panel stacked
        control_splitter = QSplitter(Qt.Vertical)
        control_splitter.setChildrenCollapsible(False)

        self.robot_panel = RobotPanel()
        self.end_effector_panel = EndEffectorPanel()

        control_splitter.addWidget(self.robot_panel)
        control_splitter.addWidget(self.end_effector_panel)
        control_splitter.setStretchFactor(0, 55)
        control_splitter.setStretchFactor(1, 45)

        # Right side: Vision Panel
        self.vision_panel = VisionPanel()

        workstation_splitter.addWidget(control_splitter)
        workstation_splitter.addWidget(self.vision_panel)
        workstation_splitter.setStretchFactor(0, 48)
        workstation_splitter.setStretchFactor(1, 52)

        # 3. Main vertical splitter: Workstation on top, System Log at bottom
        root_splitter = QSplitter(Qt.Vertical)
        root_splitter.setChildrenCollapsible(False)
        root_splitter.addWidget(workstation_splitter)

        log_widget = self._build_log_panel()
        root_splitter.addWidget(log_widget)
        root_splitter.setStretchFactor(0, 85)
        root_splitter.setStretchFactor(1, 15)

        main_layout.addWidget(root_splitter)

    def _build_header_bar(self) -> QWidget:
        """Construct the top status and operational control header."""
        header = QFrame()
        header.setObjectName("headerBar")
        header.setStyleSheet(
            f"QFrame#headerBar {{"
            f"  background-color: {COLOR_BG_PANEL};"
            f"  border: 1px solid {COLOR_BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 4px;"
            f"}}"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(16)

        # Title / Workstation Brand
        title_label = QLabel("NEEDLE INSERTION TELEOPERATOR")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #4cc9f0;")
        layout.addWidget(title_label)

        # Divider
        layout.addWidget(self._create_vdivider())

        # Subsystem Status Indicators
        # UR7e Status
        layout.addWidget(QLabel("UR7e:"))
        self._hdr_ur_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=12)
        layout.addWidget(self._hdr_ur_indicator)
        self._hdr_ur_text = QLabel("Offline")
        layout.addWidget(self._hdr_ur_text)

        layout.addWidget(self._create_vdivider())

        # ESP32 Status
        layout.addWidget(QLabel("ESP32:"))
        self._hdr_esp_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=12)
        layout.addWidget(self._hdr_esp_indicator)
        self._hdr_esp_text = QLabel("Offline")
        layout.addWidget(self._hdr_esp_text)

        layout.addWidget(self._create_vdivider())

        # Camera Status
        layout.addWidget(QLabel("Vision:"))
        self._hdr_cam_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=12)
        layout.addWidget(self._hdr_cam_indicator)
        self._hdr_cam_text = QLabel("Offline")
        layout.addWidget(self._hdr_cam_text)

        layout.addStretch(1)

        # Simulation Mode Banner
        self._sim_banner = QLabel()
        if self._cfg.application.simulation_mode:
            self._sim_banner.setText(" [ SIMULATION / DRY-RUN ACTIVE ] ")
            self._sim_banner.setStyleSheet("color: #ffaa00; font-weight: bold; font-size: 11px;")
        else:
            self._sim_banner.setText(" [ LIVE HARDWARE CONTROL ] ")
            self._sim_banner.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 11px;")
        layout.addWidget(self._sim_banner)

        # Master Software STOP Button
        self._master_stop_btn = QPushButton("ALL STOP")
        self._master_stop_btn.setObjectName("dangerButton")
        self._master_stop_btn.setMinimumSize(120, 34)
        self._master_stop_btn.setStyleSheet(
            f"QPushButton#dangerButton {{"
            f"  background-color: #d90429;"
            f"  color: white;"
            f"  font-weight: bold;"
            f"  font-size: 13px;"
            f"  border: 1px solid #ff4d6d;"
            f"  border-radius: 4px;"
            f"}}"
            f"QPushButton#dangerButton:hover {{"
            f"  background-color: #ef233c;"
            f"}}"
        )
        self._master_stop_btn.clicked.connect(self._handle_master_stop)
        layout.addWidget(self._master_stop_btn)

        return header

    def _build_log_panel(self) -> QWidget:
        """Construct the activity and safety log console."""
        box = QGroupBox("System Activity & Safety Audit Log")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)

        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(500)
        self._log_text.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #0b132b;"
            "  color: #c5c6c7;"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 11px;"
            "  border: 1px solid #1c2541;"
            "}"
        )
        layout.addWidget(self._log_text)
        return box

    @staticmethod
    def _create_vdivider() -> QFrame:
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setFrameShadow(QFrame.Sunken)
        div.setStyleSheet("color: #2b3a55;")
        return div

    # ==================================================================
    # Signal Wiring
    # ==================================================================
    def _connect_signals(self) -> None:
        # --- Robot Panel -> UR Worker ---
        self.robot_panel.connect_requested.connect(self._on_robot_connect_requested)
        self.robot_panel.disconnect_requested.connect(self._on_robot_disconnect_requested)
        self.robot_panel.jog_joint_start.connect(self._on_robot_jog_joint_start)
        self.robot_panel.jog_joint_stop.connect(self._ur_worker.stop_robot)
        self.robot_panel.jog_cartesian_start.connect(self._on_robot_jog_cartesian_start)
        self.robot_panel.jog_cartesian_stop.connect(self._ur_worker.stop_robot)
        self.robot_panel.stop_requested.connect(self._on_robot_stop_requested)

        # --- UR Worker -> Robot Panel & Header ---
        self._ur_worker.connection_changed.connect(self._on_ur_connection_changed)
        self._ur_worker.joint_positions_updated.connect(self._on_ur_joints_updated)
        self._ur_worker.tcp_pose_updated.connect(self._on_ur_tcp_updated)
        self._ur_worker.robot_mode_changed.connect(self.robot_panel.set_robot_mode)
        self._ur_worker.safety_mode_changed.connect(self._on_ur_safety_mode_changed)
        self._ur_worker.motion_status_changed.connect(self.robot_panel.set_motion_state)
        self._ur_worker.error_occurred.connect(self._on_ur_error)

        # --- End Effector Panel -> ESP32 Worker ---
        self.end_effector_panel.connect_requested.connect(self._on_esp32_connect_requested)
        self.end_effector_panel.disconnect_requested.connect(self._on_esp32_disconnect_requested)
        self.end_effector_panel.move_axis.connect(self._on_esp32_move_axis)
        self.end_effector_panel.move_axis_relative.connect(self._on_esp32_move_axis_relative)
        self.end_effector_panel.stop_requested.connect(self._on_esp32_stop_requested)
        self.end_effector_panel.home_requested.connect(self._on_esp32_home_requested)
        self.end_effector_panel.enable_requested.connect(self._esp32_worker.enable)
        self.end_effector_panel.disable_requested.connect(self._esp32_worker.disable)
        self.end_effector_panel.refresh_ports_requested.connect(self._refresh_esp32_ports)

        # --- ESP32 Worker -> End Effector Panel & Header ---
        self._esp32_worker.connection_changed.connect(self._on_esp32_connection_changed)
        self._esp32_worker.status_updated.connect(self._on_esp32_status_updated)
        self._esp32_worker.telemetry_received.connect(self._on_esp32_telemetry_received)
        self._esp32_worker.error_occurred.connect(self._on_esp32_error)
        self._esp32_worker.command_response.connect(self._on_esp32_cmd_response)

        # --- Vision Panel -> Camera / Vision Worker ---
        self.vision_panel.camera_connect_requested.connect(self._on_camera_connect_requested)
        self.vision_panel.camera_disconnect_requested.connect(self._on_camera_disconnect_requested)
        self.vision_panel.detection_enabled_changed.connect(self._vision_worker.set_detection_enabled)
        self.vision_panel.confidence_threshold_changed.connect(self._on_conf_threshold_changed)

        # --- Vision Worker -> Vision Panel & Header ---
        self._vision_worker.frame_ready.connect(self.vision_panel.update_frame)
        self._vision_worker.detection_updated.connect(self._on_vision_detections_updated)
        self._vision_worker.fps_updated.connect(self.vision_panel.set_fps)
        self._vision_worker.camera_status_changed.connect(self._on_vision_camera_status_changed)
        self._vision_worker.model_status_changed.connect(self._on_vision_model_status_changed)
        self._vision_worker.error_occurred.connect(self._on_vision_error)

    # ==================================================================
    # UR7e Robot Slots
    # ==================================================================
    @Slot(str)
    def _on_robot_connect_requested(self, ip: str) -> None:
        self.log_message("UR7e", f"Initiating connection to {ip}...")
        self._ur_worker.connect_robot(ip)

    @Slot()
    def _on_robot_disconnect_requested(self) -> None:
        self.log_message("UR7e", "Disconnect requested...")
        self._ur_worker.disconnect_robot()

    @Slot(int, int, float, float)
    def _on_robot_jog_joint_start(
        self, joint_idx: int, direction: int, speed: float, increment: float
    ) -> None:
        # Increment is passed in degrees from UI; worker expects radians
        inc_rad = math.radians(increment)
        # speed is 0..1 ratio; convert to rad/s or scale
        speed_rad_s = speed * 0.5  # conservative max ~0.5 rad/s
        self.log_message(
            "UR7e",
            f"Joint jog: J{joint_idx + 1} dir={direction:+d} inc={increment:.2f}° ({inc_rad:.4f} rad) spd={speed:.2f}",
        )
        self._ur_worker.jog_joint(joint_idx, float(direction), speed_rad_s)

    @Slot(int, int, float, float)
    def _on_robot_jog_cartesian_start(
        self, axis_idx: int, direction: int, speed: float, increment: float
    ) -> None:
        if axis_idx < 3:
            spd = speed * 0.1  # max 0.1 m/s
        else:
            spd = speed * 0.2  # max 0.2 rad/s
        axis_names = ["X", "Y", "Z", "RX", "RY", "RZ"]
        self.log_message(
            "UR7e",
            f"Cartesian jog: {axis_names[axis_idx]} dir={direction:+d} inc={increment:.2f} spd={speed:.2f}",
        )
        self._ur_worker.jog_cartesian(axis_idx, float(direction), spd)

    @Slot()
    def _on_robot_stop_requested(self) -> None:
        self.log_message("UR7e", "Stop requested from robot panel.")
        self._ur_worker.stop_robot()

    @Slot(bool)
    def _on_ur_connection_changed(self, connected: bool) -> None:
        self.robot_panel.set_connection_status(connected)
        if connected:
            update_status_indicator(self._hdr_ur_indicator, COLOR_STATUS_CONNECTED, size=12)
            self._hdr_ur_text.setText("Online")
            self.log_message("UR7e", "Connected successfully.")
        else:
            update_status_indicator(self._hdr_ur_indicator, COLOR_STATUS_DISCONNECTED, size=12)
            self._hdr_ur_text.setText("Offline")
            self.log_message("UR7e", "Disconnected.")

    @Slot(list)
    def _on_ur_joints_updated(self, joints_rad: list[float]) -> None:
        # Convert radians to degrees for operator display
        joints_deg = [math.degrees(j) for j in joints_rad]
        self.robot_panel.update_joint_positions(joints_deg)

    @Slot(list)
    def _on_ur_tcp_updated(self, pose: list[float]) -> None:
        # pose is [X, Y, Z, RX, RY, RZ]
        # X, Y, Z in m -> mm; RX, RY, RZ in rad -> deg
        if len(pose) >= 6:
            pose_disp = [
                pose[0] * 1000.0,
                pose[1] * 1000.0,
                pose[2] * 1000.0,
                math.degrees(pose[3]),
                math.degrees(pose[4]),
                math.degrees(pose[5]),
            ]
            self.robot_panel.update_cartesian_values(pose_disp)
            self.robot_panel.update_tcp_pose(pose_disp)

    @Slot(str)
    def _on_ur_safety_mode_changed(self, safety_mode: str) -> None:
        self.robot_panel.set_safety_mode(safety_mode)
        if "STOP" in safety_mode.upper() or "PROTECTIVE" in safety_mode.upper():
            self.log_message("SAFETY", f"UR7e Safety Alert: {safety_mode}")

    @Slot(str)
    def _on_ur_error(self, err: str) -> None:
        self.log_message("UR7e_ERR", err)

    # ==================================================================
    # ESP32 Slots
    # ==================================================================
    def _refresh_esp32_ports(self) -> None:
        ports = self._esp32_controller.list_serial_ports()
        if not ports:
            ports = ["SIMULATED_PORT" if self._cfg.application.simulation_mode else "NO_PORTS_FOUND"]
        self.end_effector_panel.set_ports(ports)
        self.log_message("ESP32", f"Scanned serial ports: {', '.join(ports)}")

    @Slot(str, int)
    def _on_esp32_connect_requested(self, port: str, baud: int) -> None:
        self.log_message("ESP32", f"Connecting to {port} @ {baud}...")
        self._esp32_worker.connect_device(port, baud)

    @Slot()
    def _on_esp32_disconnect_requested(self) -> None:
        self.log_message("ESP32", "Disconnecting...")
        self._esp32_worker.disconnect_device()

    @Slot(int, float, float)
    def _on_esp32_move_axis(self, axis: int, target_deg: float, speed: float) -> None:
        self.log_message("ESP32", f"Move ABS: Axis {axis} to {target_deg:.2f}° (speed={speed:.1f})")
        self._esp32_worker.move_axis(axis=axis, position=target_deg, speed=speed)

    @Slot(int, float, float)
    def _on_esp32_move_axis_relative(self, axis: int, delta_deg: float, speed: float) -> None:
        self.log_message("ESP32", f"Move REL: Axis {axis} delta={delta_deg:+.2f}° (speed={speed:.1f})")
        curr_status = self._esp32_controller.get_status()
        axes = curr_status.get("axes", [])
        curr_pos = 0.0
        for ax in axes:
            if ax.get("axis") == axis:
                curr_pos = ax.get("position_deg", 0.0)
                break
        target = curr_pos + delta_deg
        self._esp32_worker.move_axis(axis=axis, position=target, speed=speed)

    @Slot()
    def _on_esp32_stop_requested(self) -> None:
        self.log_message("ESP32", "Stop requested from end-effector panel.")
        self._esp32_worker.stop_device()

    @Slot(int)
    def _on_esp32_home_requested(self, axis: int) -> None:
        ax_str = f"Axis {axis}" if axis > 0 else "All Axes"
        self.log_message("ESP32", f"Homing requested for {ax_str}...")
        self._esp32_worker.home(axis=axis if axis > 0 else None)

    @Slot(bool)
    def _on_esp32_connection_changed(self, connected: bool) -> None:
        self.end_effector_panel.set_connection_status(connected)
        if connected:
            update_status_indicator(self._hdr_esp_indicator, COLOR_STATUS_CONNECTED, size=12)
            self._hdr_esp_text.setText("Online")
            self.log_message("ESP32", "Connected to end-effector controller.")
        else:
            update_status_indicator(self._hdr_esp_indicator, COLOR_STATUS_DISCONNECTED, size=12)
            self._hdr_esp_text.setText("Offline")
            self.log_message("ESP32", "Disconnected from end-effector controller.")

    @Slot(dict)
    def _on_esp32_status_updated(self, status: dict) -> None:
        # Update motor status
        enabled = status.get("enabled", False)
        self.end_effector_panel.set_motor_status(enabled)

        # Update communication / watchdog
        connected = status.get("connected", False)
        self.end_effector_panel.set_communication_status(
            "Active" if connected else "Inactive", healthy=connected
        )
        self.end_effector_panel.set_watchdog_status("Armed", healthy=True)

        # Axes updates
        for ax in status.get("axes", []):
            axis_id = ax.get("axis", 0)
            pos = ax.get("position_deg", 0.0)
            homed = ax.get("homed", False)
            self.end_effector_panel.update_axis_position(axis_id, pos)
            self.end_effector_panel.set_axis_homed(axis_id, homed)

    @Slot(dict)
    def _on_esp32_telemetry_received(self, telemetry: dict) -> None:
        for ax in telemetry.get("axes", []):
            axis_id = ax.get("axis", 0)
            pos = ax.get("position_deg", 0.0)
            homed = ax.get("homed", False)
            self.end_effector_panel.update_axis_position(axis_id, pos)
            self.end_effector_panel.set_axis_homed(axis_id, homed)

    @Slot(dict)
    def _on_esp32_cmd_response(self, resp: dict) -> None:
        cmd_id = resp.get("id", "?")
        ok = resp.get("ok", False)
        status_msg = resp.get("status", "")
        if not ok:
            err = resp.get("error", "Unknown error")
            self.log_message("ESP32_REJ", f"Command #{cmd_id} rejected: {err}")

    @Slot(str)
    def _on_esp32_error(self, err: str) -> None:
        self.log_message("ESP32_ERR", err)

    # ==================================================================
    # Vision Slots
    # ==================================================================
    @Slot(int)
    def _on_camera_connect_requested(self, camera_idx: int) -> None:
        self.log_message("VISION", f"Connecting camera index {camera_idx}...")
        success = self._camera_manager.connect(camera_idx)
        if not success:
            self.log_message("VISION_ERR", f"Failed to open camera index {camera_idx}")

    @Slot()
    def _on_camera_disconnect_requested(self) -> None:
        self.log_message("VISION", "Disconnecting camera...")
        self._camera_manager.disconnect()

    @Slot(bool)
    def _on_vision_camera_status_changed(self, connected: bool) -> None:
        self.vision_panel.set_camera_status(connected)
        if connected:
            update_status_indicator(self._hdr_cam_indicator, COLOR_STATUS_CONNECTED, size=12)
            self._hdr_cam_text.setText("Capturing")
            w, h = self._camera_manager.resolution
            self.vision_panel.set_resolution(w, h)
            self.log_message("VISION", f"Camera active: {w}x{h}")
        else:
            update_status_indicator(self._hdr_cam_indicator, COLOR_STATUS_DISCONNECTED, size=12)
            self._hdr_cam_text.setText("Offline")
            self.log_message("VISION", "Camera closed / disconnected.")

    @Slot(str)
    def _on_vision_model_status_changed(self, msg: str) -> None:
        loaded = self._needle_detector.is_loaded
        self.vision_panel.set_model_status(msg, loaded=loaded)
        self.vision_panel.set_model_path(self._needle_detector.model_path or "")
        self.log_message("ML_MODEL", f"Status: {msg}")

    @Slot(list)
    def _on_vision_detections_updated(self, detections: list[Detection]) -> None:
        count = len(detections)
        self.vision_panel.set_detection_count(count)
        if count > 0:
            best_conf = max(d.confidence for d in detections)
            self.vision_panel.set_last_confidence(best_conf)
            self.vision_panel.set_confidence_bar(best_conf)
            self.vision_panel.set_detection_status(f"Needle detected ({best_conf*100:.1f}%)")
        else:
            self.vision_panel.set_last_confidence(0.0)
            self.vision_panel.set_confidence_bar(0.0)
            self.vision_panel.set_detection_status("No needle in view")

    @Slot(float)
    def _on_conf_threshold_changed(self, thresh: float) -> None:
        self._needle_detector.confidence_threshold = thresh
        self.log_message("VISION", f"Detection confidence threshold updated to {thresh:.2f}")

    @Slot(str)
    def _on_vision_error(self, err: str) -> None:
        self.log_message("VISION_ERR", err)

    # ==================================================================
    # Master Operational Stop
    # ==================================================================
    @Slot()
    def _handle_master_stop(self) -> None:
        """
        Operator-requested software stop across all subsystems.
        Halts UR7e motion and ESP32 motor drive.
        """
        self.log_message("OPERATIONAL_STOP", ">>> MASTER ALL-STOP ENGAGED <<<")
        self._ur_worker.stop_robot()
        self._esp32_worker.stop_device()

    # ==================================================================
    # Logging Helper
    # ==================================================================
    def log_message(self, category: str, msg: str) -> None:
        """Append a timestamped message to the GUI audit log."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{timestamp}] [{category:10s}] {msg}"
        self._log_text.appendPlainText(formatted)
        logger.info("%s - %s", category, msg)

    # ==================================================================
    # Clean Shutdown
    # ==================================================================
    def closeEvent(self, event: QCloseEvent) -> None:
        """Gracefully release hardware connections and terminate threads."""
        self.log_message("SYSTEM", "Initiating shutdown sequence...")

        # 1. Stop all physical/simulated motion
        try:
            self._ur_worker.stop_robot()
            self._esp32_worker.stop_device()
        except Exception:
            pass

        # 2. Stop worker threads safely
        self._vision_worker.request_stop()
        self._ur_worker.request_stop()
        self._esp32_worker.request_stop()

        # 3. Wait with timeout
        self._vision_worker.wait(1000)
        self._ur_worker.wait(1000)
        self._esp32_worker.wait(1000)

        # 4. Disconnect controllers
        self._camera_manager.disconnect()
        self._ur_controller.disconnect()
        self._esp32_controller.disconnect()

        self.log_message("SYSTEM", "All workers and controllers cleanly closed.")
        event.accept()
