"""
Main Window for the Needle Motion Control Teleoperation System.

Integrates:
- System Status Header (subsystem health, env badge, clock, ALL STOP)
- UR7e Robot Control Panel (left)
- ESP32 End-Effector Control Panel (center)
- Live Vision & ML Detection Panel (right)
- System Activity / Safety Audit Log (bottom)

Coordinates background worker threads and manages application lifecycle.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QCloseEvent, QFont, QKeyEvent
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
    COLOR_BG_HEADER,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_STATUS_CONNECTED,
    COLOR_STATUS_DISCONNECTED,
    COLOR_STATUS_STOPPED,
    COLOR_STATUS_WARNING,
    COLOR_TEXT_DIM,
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

# Header chip background / border
_CHIP_BG     = "#1a1c20"
_CHIP_BORDER = "#2a2d35"
_AMBER       = "#f0a500"
_AMBER_DIM   = "#5a3c00"
_GREEN_DIM   = "#1a7a44"


class MainWindow(QMainWindow):
    """
    Primary teleoperation dashboard for the needle insertion system.

    Layout (top → bottom):
        header_bar  — 52 px fixed
        workstation_splitter  — 3-panel horizontal (robot | end-effector | vision)
        log_panel   — 150 px fixed
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

        self.setWindowTitle(
            "NEEDLE MOTION CONTROL — Robotic Teleoperation Workstation"
        )
        self.resize(1700, 960)
        self.setMinimumSize(1400, 860)

        # Build UI layout
        self._build_ui()

        # Instantiate background workers
        self._ur_worker    = URWorker(self._ur_controller)
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

        # In dry-run mode, auto-connect the simulated end-effector and enable
        # its drivers so keyboard teleoperation works out of the box.
        if self._esp32_controller.simulation_mode:
            self.log_message("ESP32", "Auto-connecting simulated end-effector...")
            self._esp32_worker.connect_device("SIMULATED_PORT", self._cfg.esp32.baud_rate)
            self._esp32_worker.enable()

        # Clock timer
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

        # Initial log entries
        sim_str = "ENABLED (Dry-run)" if self._cfg.application.simulation_mode else "DISABLED (Hardware active)"
        self.log_message("SYSTEM", f"Application initialized. Simulation mode: {sim_str}")
        self.log_message("SAFETY", "NOTICE: Software stop controls do NOT replace physical E-Stop buttons.")
        self.log_message("TELEOP", "Keyboard teleoperation armed: [W]/[S] Insert/Retract, [A]/[D] Rotate, [Space] Stop")

        # Enable keyboard focus for teleoperation
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        # Start in Needle Focus mode by default to eliminate visual overwhelm
        self._on_toggle_needle_focus(True)
        self._btn_focus_needle.setChecked(True)

    # ==================================================================
    # UI Layout Construction
    # ==================================================================
    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # 1. Header bar
        header_widget = self._build_header_bar()
        main_layout.addWidget(header_widget)

        # 2. Three-panel horizontal workstation splitter
        workstation_splitter = QSplitter(Qt.Horizontal)
        workstation_splitter.setChildrenCollapsible(False)

        self.robot_panel = RobotPanel()
        self.end_effector_panel = EndEffectorPanel()
        self.vision_panel = VisionPanel()

        workstation_splitter.addWidget(self.robot_panel)
        workstation_splitter.addWidget(self.end_effector_panel)
        workstation_splitter.addWidget(self.vision_panel)
        workstation_splitter.setStretchFactor(0, 35)
        workstation_splitter.setStretchFactor(1, 35)
        workstation_splitter.setStretchFactor(2, 30)

        # 3. Root vertical splitter: workstation (top) + log (bottom)
        root_splitter = QSplitter(Qt.Vertical)
        root_splitter.setChildrenCollapsible(False)
        root_splitter.addWidget(workstation_splitter)

        log_widget = self._build_log_panel()
        self._log_box = log_widget
        root_splitter.addWidget(log_widget)
        root_splitter.setSizes([800, 150])

        main_layout.addWidget(root_splitter, stretch=1)

    # ------------------------------------------------------------------
    # Header Bar
    # ------------------------------------------------------------------
    def _build_header_bar(self) -> QWidget:
        """Construct the top status and operational control header."""
        header = QFrame()
        header.setObjectName("headerBar")
        header.setFixedHeight(56)
        header.setStyleSheet(
            f"QFrame#headerBar {{"
            f"  background-color: {COLOR_BG_HEADER};"
            f"  border-bottom: 1px solid {COLOR_BORDER_LIGHT};"
            f"}}"
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # --- Product identity block ---
        identity_widget = QWidget()
        identity_widget.setStyleSheet("background: transparent;")
        id_layout = QVBoxLayout(identity_widget)
        id_layout.setContentsMargins(0, 4, 0, 4)
        id_layout.setSpacing(1)

        name_label = QLabel("NEEDLE MOTION CONTROL")
        name_font = QFont("Segoe UI", 10)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #ecf0f8; background: transparent;")
        id_layout.addWidget(name_label)

        sub_label = QLabel("Manual precision control — UR7e arm & 2-axis needle end-effector")
        sub_label.setStyleSheet("color: #7a8194; font-size: 9px; background: transparent;")
        id_layout.addWidget(sub_label)

        layout.addWidget(identity_widget)

        # --- Env badge ---
        self._env_badge = QLabel()
        is_sim = self._cfg.application.simulation_mode
        badge_text = "SIM" if is_sim else " HW "
        badge_bg   = _AMBER_DIM if is_sim else _GREEN_DIM
        badge_fg   = _AMBER if is_sim else COLOR_STATUS_CONNECTED
        self._env_badge.setText(badge_text)
        self._env_badge.setStyleSheet(
            f"background-color: {badge_bg}; color: {badge_fg};"
            f"font-family: 'Consolas','Courier New',monospace; font-size: 10px; font-weight: bold;"
            f"border-radius: 3px; padding: 2px 6px;"
        )
        self._env_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._env_badge)

        layout.addWidget(self._create_vdivider())

        # --- UR7e chip ---
        layout.addWidget(self._make_chip_label("UR7e"))
        self._hdr_ur_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=11)
        layout.addWidget(self._hdr_ur_indicator)
        self._hdr_ur_text = QLabel("Offline")
        self._hdr_ur_text.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px; background: transparent;")
        layout.addWidget(self._hdr_ur_text)

        layout.addWidget(self._create_vdivider())

        # --- ESP32 chip ---
        layout.addWidget(self._make_chip_label("ESP32"))
        self._hdr_esp_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=11)
        layout.addWidget(self._hdr_esp_indicator)
        self._hdr_esp_text = QLabel("Offline")
        self._hdr_esp_text.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px; background: transparent;")
        layout.addWidget(self._hdr_esp_text)

        layout.addWidget(self._create_vdivider())

        # --- MOTORS chip ---
        layout.addWidget(self._make_chip_label("MOTORS"))
        self._hdr_motor_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=11)
        layout.addWidget(self._hdr_motor_indicator)
        self._hdr_motor_text = QLabel("Disabled")
        self._hdr_motor_text.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px; background: transparent;")
        layout.addWidget(self._hdr_motor_text)

        layout.addWidget(self._create_vdivider())

        # --- SAFETY chip ---
        layout.addWidget(self._make_chip_label("SAFETY"))
        self._hdr_safety_text = QLabel("NORMAL")
        self._hdr_safety_text.setStyleSheet(
            f"color: {COLOR_STATUS_CONNECTED}; font-size: 11px; background: transparent; font-weight: bold;"
        )
        layout.addWidget(self._hdr_safety_text)

        layout.addWidget(self._create_vdivider())

        # --- Camera chip (vision is optional — no indicator dot here) ---
        layout.addWidget(self._make_chip_label("CAMERA"))
        self._hdr_cam_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=11)
        layout.addWidget(self._hdr_cam_indicator)
        self._hdr_cam_text = QLabel("Offline")
        self._hdr_cam_text.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px; background: transparent;")
        layout.addWidget(self._hdr_cam_text)

        layout.addWidget(self._create_vdivider())

        # --- View Mode Toggles (reduces overwhelm) ---
        layout.addWidget(self._make_chip_label("PANELS"))

        self._btn_focus_needle = QPushButton("🎯 Needle Focus")
        self._btn_focus_needle.setObjectName("focusBtn")
        self._btn_focus_needle.setCheckable(True)
        self._btn_focus_needle.setChecked(False)
        self._btn_focus_needle.setToolTip("Focus exclusively on needle controls (hides UR7e & Vision panels)")
        self._btn_focus_needle.clicked.connect(self._on_toggle_needle_focus)
        layout.addWidget(self._btn_focus_needle)

        self._btn_toggle_ur = QPushButton("🦾 UR7e")
        self._btn_toggle_ur.setObjectName("viewBtn")
        self._btn_toggle_ur.setCheckable(True)
        self._btn_toggle_ur.setChecked(True)
        self._btn_toggle_ur.setToolTip("Show/Hide UR7e 6-Axis Robot Panel")
        self._btn_toggle_ur.clicked.connect(self._on_toggle_ur_panel)
        layout.addWidget(self._btn_toggle_ur)

        self._btn_toggle_vision = QPushButton("📷 Vision")
        self._btn_toggle_vision.setObjectName("viewBtn")
        self._btn_toggle_vision.setCheckable(True)
        self._btn_toggle_vision.setChecked(True)
        self._btn_toggle_vision.setToolTip("Show/Hide Camera & Vision Panel")
        self._btn_toggle_vision.clicked.connect(self._on_toggle_vision_panel)
        layout.addWidget(self._btn_toggle_vision)

        self._btn_toggle_log = QPushButton("📋 Log")
        self._btn_toggle_log.setObjectName("viewBtn")
        self._btn_toggle_log.setCheckable(True)
        self._btn_toggle_log.setChecked(True)
        self._btn_toggle_log.setToolTip("Show/Hide Bottom Audit Log")
        self._btn_toggle_log.clicked.connect(self._on_toggle_log_panel)
        layout.addWidget(self._btn_toggle_log)

        layout.addStretch(1)

        # --- Clock ---
        self._hdr_clock_label = QLabel(datetime.now().strftime("%H:%M:%S"))
        self._hdr_clock_label.setStyleSheet(
            f"font-family: 'Consolas','Courier New',monospace; font-size: 12px;"
            f"color: {COLOR_TEXT_DIM}; background: transparent; padding: 0 4px;"
        )
        layout.addWidget(self._hdr_clock_label)

        layout.addWidget(self._create_vdivider())

        # --- ALL STOP button ---
        self._master_stop_btn = QPushButton("ALL STOP")
        self._master_stop_btn.setMinimumSize(110, 36)
        self._master_stop_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #e63946;"
            "  color: white;"
            "  font-weight: bold;"
            "  font-size: 13px;"
            "  border: 2px solid #ff5060;"
            "  border-radius: 3px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #f04050;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #c02030;"
            "}"
        )
        self._master_stop_btn.clicked.connect(self._handle_master_stop)
        layout.addWidget(self._master_stop_btn)

        return header

    @staticmethod
    def _make_chip_label(text: str) -> QLabel:
        """Create a small dimmed subsystem label for the header chips."""
        lbl = QLabel(f"{text}:")
        lbl.setStyleSheet(
            "color: #7a8194; font-size: 10px; font-weight: bold; background: transparent;"
        )
        return lbl

    def _build_log_panel(self) -> QWidget:
        """Construct the activity and safety log console."""
        box = QGroupBox("SYSTEM LOG  —  Event & Safety Audit")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)

        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(800)
        self._log_text.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #090a0c;"
            "  color: #9ba3b4;"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 11px;"
            "  border: 1px solid #2a2d35;"
            "  border-radius: 2px;"
            "}"
        )
        layout.addWidget(self._log_text)
        return box

    @staticmethod
    def _create_vdivider() -> QFrame:
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setFrameShadow(QFrame.Sunken)
        div.setStyleSheet(f"color: {COLOR_BORDER_LIGHT};")
        div.setFixedWidth(1)
        return div

    # ==================================================================
    # Clock & View Mode Slots
    # ==================================================================
    def _update_clock(self) -> None:
        self._hdr_clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    @Slot(bool)
    def _on_toggle_needle_focus(self, checked: bool) -> None:
        """Toggle Needle Focus mode to eliminate visual overwhelm."""
        if checked:
            self.robot_panel.setVisible(False)
            self.vision_panel.setVisible(False)
            self._btn_toggle_ur.blockSignals(True)
            self._btn_toggle_vision.blockSignals(True)
            self._btn_toggle_ur.setChecked(False)
            self._btn_toggle_vision.setChecked(False)
            self._btn_toggle_ur.blockSignals(False)
            self._btn_toggle_vision.blockSignals(False)
            self.log_message("VIEW", "🎯 Needle Focus Mode activated (UR7e & Vision panels hidden).")
        else:
            self.robot_panel.setVisible(True)
            self.vision_panel.setVisible(True)
            self._btn_toggle_ur.blockSignals(True)
            self._btn_toggle_vision.blockSignals(True)
            self._btn_toggle_ur.setChecked(True)
            self._btn_toggle_vision.setChecked(True)
            self._btn_toggle_ur.blockSignals(False)
            self._btn_toggle_vision.blockSignals(False)
            self.log_message("VIEW", "🌐 Full Workstation View restored.")

    @Slot(bool)
    def _on_toggle_ur_panel(self, checked: bool) -> None:
        self.robot_panel.setVisible(checked)
        self._sync_focus_btn()

    @Slot(bool)
    def _on_toggle_vision_panel(self, checked: bool) -> None:
        self.vision_panel.setVisible(checked)
        self._sync_focus_btn()

    @Slot(bool)
    def _on_toggle_log_panel(self, checked: bool) -> None:
        self._log_box.setVisible(checked)

    def _sync_focus_btn(self) -> None:
        is_focused = (not self.robot_panel.isVisible()) and (not self.vision_panel.isVisible())
        self._btn_focus_needle.blockSignals(True)
        self._btn_focus_needle.setChecked(is_focused)
        self._btn_focus_needle.blockSignals(False)

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
        inc_rad = math.radians(increment)
        speed_rad_s = speed * 0.5
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
            spd = speed * 0.1
        else:
            spd = speed * 0.2
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
            update_status_indicator(self._hdr_ur_indicator, COLOR_STATUS_CONNECTED, size=11)
            self._hdr_ur_text.setText("Online")
            self.log_message("UR7e", "Connected successfully.")
        else:
            update_status_indicator(self._hdr_ur_indicator, COLOR_STATUS_DISCONNECTED, size=11)
            self._hdr_ur_text.setText("Offline")
            self.log_message("UR7e", "Disconnected.")

    @Slot(list)
    def _on_ur_joints_updated(self, joints_rad: list[float]) -> None:
        joints_deg = [math.degrees(j) for j in joints_rad]
        self.robot_panel.update_joint_positions(joints_deg)

    @Slot(list)
    def _on_ur_tcp_updated(self, pose: list[float]) -> None:
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
        # Update header safety chip
        is_safe = not ("STOP" in safety_mode.upper() or "PROTECTIVE" in safety_mode.upper())
        if is_safe:
            self._hdr_safety_text.setText(safety_mode if safety_mode else "NORMAL")
            self._hdr_safety_text.setStyleSheet(
                f"color: {COLOR_STATUS_CONNECTED}; font-size: 11px; background: transparent; font-weight: bold;"
            )
        else:
            self._hdr_safety_text.setText(safety_mode)
            self._hdr_safety_text.setStyleSheet(
                f"color: {_AMBER}; font-size: 11px; background: transparent; font-weight: bold;"
            )
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
    def _on_esp32_move_axis(self, axis: int, target_position: float, speed: float) -> None:
        if not self._esp32_controller.is_connected:
            self.log_message("ESP32_WARN", f"Cannot move Axis {axis}: End-effector is not connected.")
            return
        unit = "mm" if axis == 1 else "°"
        speed_unit = "mm/s" if axis == 1 else "°/s"
        self.log_message(
            "ESP32",
            f"Move ABS: {'Insertion' if axis == 1 else 'Guide angle'} "
            f"to {target_position:.2f} {unit} (speed={speed:.1f} {speed_unit})",
        )
        self._esp32_worker.move_axis(axis=axis, position=target_position, speed=speed)

    @Slot(int, float, float)
    def _on_esp32_move_axis_relative(self, axis: int, delta_position: float, speed: float) -> None:
        if not self._esp32_controller.is_connected:
            self.log_message("ESP32_WARN", f"Cannot move Axis {axis}: End-effector is not connected.")
            return
        unit = "mm" if axis == 1 else "°"
        speed_unit = "mm/s" if axis == 1 else "°/s"
        self.log_message(
            "ESP32",
            f"Move REL: {'Insertion' if axis == 1 else 'Guide angle'} "
            f"delta={delta_position:+.2f} {unit} (speed={speed:.1f} {speed_unit})",
        )
        # Jogging is open-loop: let the device add the step to its own step
        # counter (no encoder/gyro is fitted, so no absolute feedback read).
        self._esp32_worker.move_axis_relative(axis=axis, delta=delta_position, speed=speed)

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
            update_status_indicator(self._hdr_esp_indicator, COLOR_STATUS_CONNECTED, size=11)
            self._hdr_esp_text.setText("Online")
            self.log_message("ESP32", "Connected to end-effector controller.")
        else:
            update_status_indicator(self._hdr_esp_indicator, COLOR_STATUS_DISCONNECTED, size=11)
            self._hdr_esp_text.setText("Offline")
            self.log_message("ESP32", "Disconnected from end-effector controller.")

    @Slot(dict)
    def _on_esp32_status_updated(self, status: dict) -> None:
        # Update motor status in panel
        enabled = status.get("enabled", False)
        self.end_effector_panel.set_motor_status(enabled)

        # Update motor status in header
        motor_color = COLOR_STATUS_CONNECTED if enabled else COLOR_STATUS_STOPPED
        update_status_indicator(self._hdr_motor_indicator, motor_color, size=11)
        self._hdr_motor_text.setText("Enabled" if enabled else "Disabled")

        # Communication / watchdog
        connected = status.get("connected", False)
        self.end_effector_panel.set_communication_status(
            "Active" if connected else "Inactive", healthy=connected
        )
        self.end_effector_panel.set_watchdog_status("Armed", healthy=True)

        # Axes updates
        for ax in status.get("axes", []):
            axis_id = ax.get("axis", 0)
            pos     = ax.get("position_mm" if axis_id == 1 else "position_deg", ax.get("position", 0.0))
            homed   = ax.get("homed", False)
            self.end_effector_panel.update_axis_position(axis_id, pos)
            self.end_effector_panel.set_axis_homed(axis_id, homed)

    @Slot(dict)
    def _on_esp32_telemetry_received(self, telemetry: dict) -> None:
        for ax in telemetry.get("axes", []):
            axis_id = ax.get("axis", 0)
            pos     = ax.get("position_mm" if axis_id == 1 else "position_deg", ax.get("position", 0.0))
            homed   = ax.get("homed", False)
            self.end_effector_panel.update_axis_position(axis_id, pos)
            self.end_effector_panel.set_axis_homed(axis_id, homed)

    @Slot(dict)
    def _on_esp32_cmd_response(self, resp: dict) -> None:
        cmd_id = resp.get("id", "?")
        ok     = resp.get("ok", False)
        if not ok:
            # Older firmware reports the reason in "status", newer in "error".
            err = resp.get("error") or resp.get("status") or "Unknown error"
            hint = ""
            if "enable" in err.lower() or "disabled" in err.lower():
                hint = "  Press [M] to enable the motor drivers."
            self.log_message("ESP32_REJ", f"Command #{cmd_id} rejected: {err}{hint}")

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
            update_status_indicator(self._hdr_cam_indicator, COLOR_STATUS_CONNECTED, size=11)
            self._hdr_cam_text.setText("Capturing")
            w, h = self._camera_manager.resolution
            self.vision_panel.set_resolution(w, h)
            self.log_message("VISION", f"Camera active: {w}x{h}")
        else:
            update_status_indicator(self._hdr_cam_indicator, COLOR_STATUS_DISCONNECTED, size=11)
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
        formatted = f"[{timestamp}] [{category:<12s}] {msg}"
        self._log_text.appendPlainText(formatted)
        logger.info("%s - %s", category, msg)

    # ==================================================================
    # Keyboard Teleoperation
    # ==================================================================
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Global keyboard teleoperation handler.
        Directly drives needle insertion and guide-angle adjustment from the keyboard.
        """
        # If user is actively typing in a multiline log or text box, don't capture teleop keys
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QPlainTextEdit,)):
            super().keyPressEvent(event)
            return

        key = event.key()

        # 1. Emergency ALL STOP: Spacebar
        if key == Qt.Key_Space:
            self._handle_master_stop()
            event.accept()
            return

        # 2. Needle Insertion (To & Fro): W/S or Up/Down
        if key in (Qt.Key_W, Qt.Key_Up):
            self.end_effector_panel.advance_step()
            event.accept()
            return
        elif key in (Qt.Key_S, Qt.Key_Down):
            self.end_effector_panel.retract_step()
            event.accept()
            return

        # 3. Needle-guide angle adjustment: A/D or Left/Right
        elif key in (Qt.Key_A, Qt.Key_Left):
            self.end_effector_panel.angle_left_step()
            event.accept()
            return
        elif key in (Qt.Key_D, Qt.Key_Right):
            self.end_effector_panel.angle_right_step()
            event.accept()
            return

        # 4. Speed Presets: 1, 2, 3, 4
        elif key == Qt.Key_1:
            self.end_effector_panel.set_speed_preset(1)
            self.log_message("TELEOP", "Speed Preset 1 selected: Micro")
            event.accept()
            return
        elif key == Qt.Key_2:
            self.end_effector_panel.set_speed_preset(2)
            self.log_message("TELEOP", "Speed Preset 2 selected: Slow")
            event.accept()
            return
        elif key == Qt.Key_3:
            self.end_effector_panel.set_speed_preset(3)
            self.log_message("TELEOP", "Speed Preset 3 selected: Normal")
            event.accept()
            return
        elif key == Qt.Key_4:
            self.end_effector_panel.set_speed_preset(4)
            self.log_message("TELEOP", "Speed Preset 4 selected: Rapid")
            event.accept()
            return

        # 5. Speed Fine Tuning: + / -
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.end_effector_panel.adjust_speed(+5.0)
            event.accept()
            return
        elif key in (Qt.Key_Minus, Qt.Key_Underscore):
            self.end_effector_panel.adjust_speed(-5.0)
            event.accept()
            return

        # 6. Motor Drivers Toggle: M
        elif key == Qt.Key_M:
            self.end_effector_panel.toggle_motors()
            event.accept()
            return

        # 7. Home Needle Axes: H
        elif key == Qt.Key_H:
            self.end_effector_panel.home_all()
            event.accept()
            return

        super().keyPressEvent(event)

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
