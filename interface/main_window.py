"""
Main window for the needle teleoperation workstation.

Layout
------
header    — subsystem status and master stop
workspace — connection and two-axis needle controls
log       — activity and safety audit console

The UR7e arm is commanded from its own interface, and the ultrasound image is
shown in a separate application, so this workstation covers the needle
end-effector only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot
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
from interface.end_effector_panel import AXIS_UNITS, EndEffectorPanel
from interface.styles import (
    COLOR_STATUS_CONNECTED,
    COLOR_STATUS_DISCONNECTED,
    COLOR_TEXT_DIM,
    create_status_indicator,
    update_status_indicator,
)
from workers.esp32_worker import ESP32Worker

logger = logging.getLogger(__name__)

_AMBER = "#e0a33a"


class MainWindow(QMainWindow):
    """
    Needle teleoperation dashboard.

    Layout (top → bottom):
        header_bar  — 64 px fixed
        workspace   — end-effector panel
        log_panel   — activity audit console
    """

    def __init__(
        self,
        esp32_controller: ESP32Controller,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._cfg = Config.instance()
        self._esp32_controller = esp32_controller

        self.setWindowTitle("Needle Motion Control — Robotic Teleoperation Workstation")
        self.resize(640, 860)
        self.setMinimumSize(520, 640)

        self._build_ui()

        # Background worker
        self._esp32_worker = ESP32Worker(self._esp32_controller)

        self._connect_signals()

        self._esp32_worker.start()

        self._refresh_esp32_ports()

        # In dry-run mode, auto-connect the simulated end-effector and enable
        # its drivers so keyboard teleoperation works out of the box.
        if self._esp32_controller.simulation_mode:
            self.log_message("ESP32", "Auto-connecting simulated end-effector...")
            self._esp32_worker.connect_device("SIMULATED_PORT", self._cfg.esp32.baud_rate)
            self._esp32_worker.enable()

        sim_state = "ENABLED (dry run)" if self._cfg.application.simulation_mode else "DISABLED (hardware active)"
        self.log_message("SYSTEM", f"Workstation ready. Simulation mode: {sim_state}")
        self.log_message("TELEOP", "Keyboard: [W]/[S] insert/retract, [A]/[D] rotate, [1-4] speed, [M] motors, [H] home, [Space] stop")
        self.log_message("SAFETY", "Software stop does not replace the physical E-Stop button.")

        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_header())

        root_splitter = QSplitter(Qt.Vertical)
        root_splitter.setChildrenCollapsible(False)

        self.end_effector_panel = EndEffectorPanel()
        root_splitter.addWidget(self.end_effector_panel)

        log_widget = self._build_log_panel()
        root_splitter.addWidget(log_widget)
        root_splitter.setStretchFactor(0, 1)
        root_splitter.setStretchFactor(1, 0)
        root_splitter.setSizes([560, 210])

        main_layout.addWidget(root_splitter, stretch=1)

    # ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("headerBar")
        header.setFixedHeight(64)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 0, 12, 0)
        layout.setSpacing(7)

        mark = QLabel("N")
        mark.setFixedSize(30, 30)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            "background: #183142; color: #8ed3f0; border: 1px solid #3c728f;"
            " border-radius: 5px; font-size: 16px; font-weight: 700;"
        )
        layout.addWidget(mark)

        identity = QVBoxLayout()
        identity.setSpacing(1)

        title = QLabel("NEEDLE MOTION CONTROL")
        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #f3f7fa; letter-spacing: 1px;")
        identity.addWidget(title)

        subtitle = QLabel("2-DOF END-EFFECTOR  /  TELEOP")
        subtitle.setStyleSheet("color: #8293a4; font-size: 8px; letter-spacing: 0.6px;")
        identity.addWidget(subtitle)
        layout.addLayout(identity)

        is_sim = self._cfg.application.simulation_mode
        badge = QLabel("SIM" if is_sim else "HW")
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumWidth(38)
        badge.setStyleSheet(
            f"color: {_AMBER if is_sim else COLOR_STATUS_CONNECTED};"
            "background: #17212b; border: 1px solid #344353; border-radius: 4px;"
            "padding: 3px 7px; font-size: 10px; font-weight: 700;"
        )
        layout.addWidget(badge)

        layout.addSpacing(10)

        self._hdr_esp_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 8)
        layout.addWidget(self._hdr_esp_indicator)
        self._hdr_esp_text = QLabel("End-effector offline")
        self._hdr_esp_text.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        layout.addWidget(self._hdr_esp_text)

        layout.addSpacing(10)

        self._hdr_motor_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 8)
        layout.addWidget(self._hdr_motor_indicator)
        self._hdr_motor_text = QLabel("Motors off")
        self._hdr_motor_text.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        layout.addWidget(self._hdr_motor_text)

        layout.addStretch(1)

        self._master_stop_btn = QPushButton("ALL STOP")
        self._master_stop_btn.setObjectName("stopButton")
        self._master_stop_btn.setFixedSize(126, 36)
        self._master_stop_btn.setToolTip("Stop all needle motion  [Space]")
        self._master_stop_btn.clicked.connect(self._handle_master_stop)
        layout.addWidget(self._master_stop_btn)

        return header

    def _build_log_panel(self) -> QWidget:
        box = QGroupBox("EVENT LOG  /  SAFETY AUDIT")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(1000)
        self._log_text.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #0a1016;"
            "  color: #aebdca;"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 11px;"
            "  border: 1px solid #25313d;"
            "  border-radius: 5px;"
            "  padding: 8px;"
            "}"
        )
        layout.addWidget(self._log_text)
        return box

    # ==================================================================
    # Signal wiring
    # ==================================================================
    def _connect_signals(self) -> None:
        panel = self.end_effector_panel

        panel.connect_requested.connect(self._on_esp32_connect_requested)
        panel.disconnect_requested.connect(self._on_esp32_disconnect_requested)
        panel.move_axis.connect(self._on_esp32_move_axis)
        panel.move_axis_relative.connect(self._on_esp32_move_axis_relative)
        panel.stop_requested.connect(self._on_esp32_stop_requested)
        panel.home_requested.connect(self._on_esp32_home_requested)
        panel.enable_requested.connect(self._esp32_worker.enable)
        panel.disable_requested.connect(self._esp32_worker.disable)
        panel.refresh_ports_requested.connect(self._refresh_esp32_ports)

        self._esp32_worker.connection_changed.connect(self._on_esp32_connection_changed)
        self._esp32_worker.status_updated.connect(self._on_esp32_status_updated)
        self._esp32_worker.telemetry_received.connect(self._on_esp32_telemetry_received)
        self._esp32_worker.command_response.connect(self._on_esp32_cmd_response)
        self._esp32_worker.error_occurred.connect(self._on_esp32_error)

    # ==================================================================
    # ESP32 slots
    # ==================================================================
    def _refresh_esp32_ports(self) -> None:
        ports = self._esp32_controller.list_serial_ports()
        if not ports:
            ports = ["SIMULATED_PORT" if self._cfg.application.simulation_mode else "NO_PORTS_FOUND"]
        self.end_effector_panel.set_ports(ports)
        self.log_message("ESP32", f"Serial ports: {', '.join(ports)}")

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
            self.log_message("ESP32_WARN", f"Cannot move Axis {axis}: end-effector is not connected.")
            return
        unit = AXIS_UNITS.get(axis, "")
        self.log_message(
            "ESP32",
            f"Move ABS: axis {axis} to {target_position:+.2f} {unit} (speed={speed:.1f} {unit}/s)",
        )
        self._esp32_worker.move_axis(axis=axis, position=target_position, speed=speed)

    @Slot(int, float, float)
    def _on_esp32_move_axis_relative(self, axis: int, delta_position: float, speed: float) -> None:
        if not self._esp32_controller.is_connected:
            self.log_message("ESP32_WARN", f"Cannot move Axis {axis}: end-effector is not connected.")
            return
        unit = AXIS_UNITS.get(axis, "")
        self.log_message(
            "ESP32",
            f"Move REL: axis {axis} delta={delta_position:+.2f} {unit} (speed={speed:.1f} {unit}/s)",
        )
        self._esp32_worker.move_axis_relative(axis=axis, delta=delta_position, speed=speed)

    @Slot()
    def _on_esp32_stop_requested(self) -> None:
        self.log_message("ESP32", "Stop requested from end-effector panel.")
        self._esp32_worker.stop_device()

    @Slot(int)
    def _on_esp32_home_requested(self, axis: int) -> None:
        target = f"Axis {axis}" if axis > 0 else "all axes"
        self.log_message("ESP32", f"Homing {target}...")
        self._esp32_worker.home(axis=axis if axis > 0 else None)

    @Slot(bool)
    def _on_esp32_connection_changed(self, connected: bool) -> None:
        self.end_effector_panel.set_connection_status(connected)

        if connected:
            update_status_indicator(self._hdr_esp_indicator, COLOR_STATUS_CONNECTED, 8)
            self._hdr_esp_text.setText("End-effector online")
            self._hdr_esp_text.setStyleSheet("color: #e2e6ee;")
            self.log_message("ESP32", "Connected to end-effector controller.")
        else:
            update_status_indicator(self._hdr_esp_indicator, COLOR_STATUS_DISCONNECTED, 8)
            self._hdr_esp_text.setText("End-effector offline")
            self._hdr_esp_text.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
            self.log_message("ESP32", "Disconnected from end-effector controller.")

    @Slot(dict)
    def _on_esp32_status_updated(self, status: dict) -> None:
        enabled = status.get("enabled", False)
        self.end_effector_panel.set_motor_status(enabled)

        update_status_indicator(
            self._hdr_motor_indicator,
            COLOR_STATUS_CONNECTED if enabled else COLOR_STATUS_DISCONNECTED,
            8,
        )
        self._hdr_motor_text.setText("Motors on" if enabled else "Motors off")
        self._hdr_motor_text.setStyleSheet("color: #e2e6ee;" if enabled else f"color: {COLOR_TEXT_DIM};")

        self._apply_axes(status.get("axes", []))

    @Slot(dict)
    def _on_esp32_telemetry_received(self, telemetry: dict) -> None:
        self._apply_axes(telemetry.get("axes", []))

    def _apply_axes(self, axes: list) -> None:
        for ax in axes:
            axis_id = ax.get("axis", 0)
            if axis_id not in (1, 2):
                continue
            position = ax.get("position_deg", ax.get("position", 0.0))
            self.end_effector_panel.update_axis_position(axis_id, position)
            self.end_effector_panel.set_axis_homed(axis_id, ax.get("homed", False))

    @Slot(dict)
    def _on_esp32_cmd_response(self, resp: dict) -> None:
        if resp.get("ok", False):
            return
        err = resp.get("error") or resp.get("status") or "Unknown error"
        hint = ""
        if "enable" in err.lower() or "disabled" in err.lower():
            hint = "  Press [M] to enable the motor drivers."
        self.log_message("ESP32_REJ", f"Command #{resp.get('id', '?')} rejected: {err}{hint}")

    @Slot(str)
    def _on_esp32_error(self, err: str) -> None:
        self.log_message("ESP32_ERR", err)

    # ==================================================================
    # Master stop
    # ==================================================================
    @Slot()
    def _handle_master_stop(self) -> None:
        """Operator-requested software stop of needle motion."""
        self.log_message("OPERATIONAL_STOP", ">>> MASTER ALL-STOP ENGAGED <<<")
        self._esp32_worker.stop_device()

    # ==================================================================
    # Logging
    # ==================================================================
    def log_message(self, category: str, msg: str) -> None:
        """Append a timestamped message to the audit log."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log_text.appendPlainText(f"[{timestamp}] [{category:<12s}] {msg}")
        logger.info("%s - %s", category, msg)

    # ==================================================================
    # Keyboard teleoperation
    # ==================================================================
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Global keyboard teleoperation handler."""
        if isinstance(QApplication.focusWidget(), QPlainTextEdit):
            super().keyPressEvent(event)
            return

        key = event.key()

        if key == Qt.Key_Space:
            self._handle_master_stop()
            event.accept()
            return

        if key in (Qt.Key_W, Qt.Key_Up):
            self.end_effector_panel.advance_step()
        elif key in (Qt.Key_S, Qt.Key_Down):
            self.end_effector_panel.retract_step()

        elif key in (Qt.Key_A, Qt.Key_Left):
            self.end_effector_panel.angle_left_step()
        elif key in (Qt.Key_D, Qt.Key_Right):
            self.end_effector_panel.angle_right_step()

        elif key in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4):
            preset = key - Qt.Key_1 + 1
            self.end_effector_panel.set_speed_preset(preset)
            self.log_message("TELEOP", f"Speed preset {preset} selected.")

        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.end_effector_panel.adjust_speed(+5.0)
        elif key in (Qt.Key_Minus, Qt.Key_Underscore):
            self.end_effector_panel.adjust_speed(-5.0)

        elif key == Qt.Key_M:
            self.end_effector_panel.toggle_motors()

        elif key == Qt.Key_H:
            self.end_effector_panel.home_all()

        else:
            super().keyPressEvent(event)
            return

        event.accept()

    # ==================================================================
    # Shutdown
    # ==================================================================
    def closeEvent(self, event: QCloseEvent) -> None:
        """Gracefully release hardware connections and terminate threads."""
        self.log_message("SYSTEM", "Initiating shutdown sequence...")

        try:
            self._esp32_worker.stop_device()
        except Exception:
            pass

        self._esp32_worker.request_stop()
        self._esp32_worker.wait(1000)

        self._esp32_controller.disconnect()

        self.log_message("SYSTEM", "All workers and controllers closed.")
        event.accept()
