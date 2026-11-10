"""
Needle end-effector panel: two-axis open-loop jog control and readout.

The end-effector has no gyro or encoder, so the large readouts show the
commanded position the device is maintaining (firmware step counter).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from interface.styles import (
    COLOR_STATUS_CONNECTED,
    COLOR_STATUS_DISCONNECTED,
    create_status_indicator,
    update_status_indicator,
)

DEFAULT_BAUD_RATE = 115200

# Travel limits in native units: axis 1 = millimetres, axis 2 = degrees
AXIS_LIMITS = {
    1: (-180.0, 180.0),
    2: (-360.0, 360.0),
}

# Display unit per axis
AXIS_UNITS = {
    1: "mm",
    2: "°",
}

_TEXT   = "#e2e6ee"
_DIM    = "#7d8496"
_RED    = "#e05263"
_GREEN  = "#35c46f"


class EndEffectorPanel(QWidget):
    """
    Needle end-effector control panel.

    Signals
    -------
    connect_requested : (str, int)
    disconnect_requested : ()
    move_axis : (int, float, float)
    move_axis_relative : (int, float, float)
    stop_requested : ()
    home_requested : (int)
    enable_requested : ()
    disable_requested : ()
    refresh_ports_requested : ()
    """

    connect_requested       = Signal(str, int)
    disconnect_requested    = Signal()
    move_axis               = Signal(int, float, float)
    move_axis_relative      = Signal(int, float, float)
    stop_requested          = Signal()
    home_requested          = Signal(int)
    enable_requested        = Signal()
    disable_requested       = Signal()
    refresh_ports_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("endEffectorPanel")

        self._motor_enabled = False
        self._connected = False
        self._current_positions: dict[int, float] = {1: 0.0, 2: 0.0}

        # Per-axis widgets, indexed by axis - 1
        self._axis_position_labels:  list[QLabel]         = []
        self._axis_homed_indicators: list[QLabel]         = []
        self._axis_homed_labels:     list[QLabel]         = []
        self._axis_increments:       list[QDoubleSpinBox] = []
        self._axis_speed_sliders:    list[QSlider]        = []

        self._build_ui()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(20, 14, 20, 18)
        self._main_layout.setSpacing(4)

        self._build_connection_section()

        axis_layout = QVBoxLayout()
        axis_layout.setContentsMargins(0, 0, 0, 0)
        axis_layout.setSpacing(0)
        axis_layout.addWidget(
            self._build_axis(
                1, "AXIS 1  ·  NEEDLE INSERTION",
                default_step=1.0, default_speed=20, unit="mm",
            )
        )
        axis_layout.addWidget(
            self._build_axis(
                2, "AXIS 2  ·  NEEDLE ROTATION",
                default_step=15.0, default_speed=25, unit="°",
            )
        )
        self._main_layout.addLayout(axis_layout)

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    def _build_connection_section(self) -> None:
        group = QGroupBox("END-EFFECTOR")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 4, 0, 0)

        # Connection and motor controls share one operational surface.
        connection_column = QVBoxLayout()
        connection_column.setSpacing(6)

        connection_label = QLabel("SERIAL LINK")
        connection_label.setStyleSheet("color: #8d9aaa; font-size: 10px; font-weight: 700;")
        connection_column.addWidget(connection_label)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._conn_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 8)
        row.addWidget(self._conn_indicator)

        self._conn_label = QLabel("Offline")
        self._conn_label.setStyleSheet(f"color: {_RED}; font-weight: 600;")
        row.addWidget(self._conn_label)

        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(150)
        self._port_combo.setEditable(False)
        row.addWidget(self._port_combo)

        self._refresh_btn = QPushButton("Scan ports")
        self._refresh_btn.setToolTip("Scan serial ports")
        self._refresh_btn.clicked.connect(self.refresh_ports_requested.emit)
        row.addWidget(self._refresh_btn)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connectButton")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        row.addWidget(self._connect_btn)

        row.addStretch()
        connection_column.addLayout(row)

        # Motor row
        motor_column = QVBoxLayout()
        motor_column.setSpacing(6)

        motor_label = QLabel("DRIVER STATE")
        motor_label.setStyleSheet("color: #8d9aaa; font-size: 10px; font-weight: 700;")
        motor_column.addWidget(motor_label)

        motor_row = QHBoxLayout()
        motor_row.setSpacing(8)

        self._motor_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 8)
        motor_row.addWidget(self._motor_indicator)

        self._motor_status_label = QLabel("Motors off")
        self._motor_status_label.setStyleSheet(f"color: {_DIM}; font-weight: 600;")
        motor_row.addWidget(self._motor_status_label)

        self._enable_btn = QPushButton("Enable motors")
        self._enable_btn.setObjectName("connectButton")
        self._enable_btn.setToolTip("Enable or disable the stepper drivers  [M]")
        self._enable_btn.clicked.connect(self.toggle_motors)
        motor_row.addWidget(self._enable_btn)

        self._home_btn = QPushButton("Home")
        self._home_btn.setToolTip("Zero both needle axes  [H]")
        self._home_btn.clicked.connect(self.home_all)
        motor_row.addWidget(self._home_btn)
        motor_row.addStretch()
        motor_column.addLayout(motor_row)

        layout.addLayout(connection_column)
        layout.addLayout(motor_column)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    def _build_axis(
        self,
        axis: int,
        title: str,
        default_step: float,
        default_speed: int,
        unit: str = "°",
    ) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 4, 0, 0)

        # Readout row: large value, homed state, limits
        readout = QHBoxLayout()
        readout.setSpacing(8)

        value = QLabel(f"+0.00 {unit}")
        value.setStyleSheet(
            "font-family: 'Consolas','Courier New',monospace; font-size: 30px;"
            f" font-weight: 600; color: {_TEXT};"
        )
        self._axis_position_labels.append(value)
        readout.addWidget(value)

        homed_dot = create_status_indicator(COLOR_STATUS_DISCONNECTED, 7)
        self._axis_homed_indicators.append(homed_dot)
        readout.addWidget(homed_dot)

        homed_lbl = QLabel("Not homed")
        homed_lbl.setStyleSheet(f"color: {_DIM}; font-size: 11px;")
        self._axis_homed_labels.append(homed_lbl)
        readout.addWidget(homed_lbl)

        readout.addStretch()

        lo, hi = AXIS_LIMITS[axis]
        limits = QLabel(f"TRAVEL  {lo:g} {unit}  to  {hi:g} {unit}")
        limits.setStyleSheet(f"color: {_DIM}; font-size: 10px; letter-spacing: 0.3px;")
        readout.addWidget(limits)

        layout.addLayout(readout)

        # Controls row: step, speed, jog buttons
        controls = QHBoxLayout()
        controls.setSpacing(9)

        step_label = QLabel("STEP")
        step_label.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: 700;")
        controls.addWidget(step_label)

        step = QDoubleSpinBox()
        step.setRange(0.05 if axis == 1 else 0.1, 50.0 if axis == 1 else 180.0)
        step.setValue(default_step)
        step.setSingleStep(0.1 if axis == 1 else 1.0)
        step.setDecimals(2 if axis == 1 else 1)
        step.setSuffix(f" {unit}")
        step.setFixedWidth(86)
        self._axis_increments.append(step)
        controls.addWidget(step)

        controls.addSpacing(10)

        speed_label = QLabel("SPEED")
        speed_label.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: 700;")
        controls.addWidget(speed_label)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(1, 90)
        slider.setValue(default_speed)
        slider.setFixedWidth(130)
        self._axis_speed_sliders.append(slider)
        controls.addWidget(slider)

        speed_value = QLabel(f"{default_speed} {unit}/s")
        speed_value.setFixedWidth(58)
        speed_value.setStyleSheet(
            "font-family: 'Consolas','Courier New',monospace; font-size: 11px;"
            f" color: {_DIM};"
        )
        slider.valueChanged.connect(
            lambda v, lbl=speed_value, u=unit: lbl.setText(f"{v} {u}/s")
        )
        controls.addWidget(speed_value)

        controls.addStretch()

        minus = QPushButton("←")
        minus.setObjectName("jogButton")
        minus.setAccessibleName("Jog negative")
        minus.setToolTip("Jog negative  (keyboard: S for axis 1, A for axis 2)")
        minus.clicked.connect(lambda _=False, a=axis: self._jog(a, -1))
        controls.addWidget(minus)

        plus = QPushButton("→")
        plus.setObjectName("jogButton")
        plus.setAccessibleName("Jog positive")
        plus.setToolTip("Jog positive  (keyboard: W for axis 1, D for axis 2)")
        plus.clicked.connect(lambda _=False, a=axis: self._jog(a, 1))
        controls.addWidget(plus)

        layout.addLayout(controls)
        return group

    # ==================================================================
    # Keyboard teleoperation handlers
    # ==================================================================
    def advance_step(self) -> None:
        """Advance needle (axis 1, positive)."""
        self._execute_current_step(1, 1)

    def retract_step(self) -> None:
        """Retract needle (axis 1, negative)."""
        self._execute_current_step(1, -1)

    def angle_right_step(self) -> None:
        """Rotate needle clockwise (axis 2, positive)."""
        self._execute_current_step(2, 1)

    def angle_left_step(self) -> None:
        """Rotate needle counter-clockwise (axis 2, negative)."""
        self._execute_current_step(2, -1)

    def set_speed_preset(self, preset_idx: int) -> None:
        """Apply a speed preset to both axes (1=2, 2=10, 3=25, 4=60 °/s)."""
        presets = {1: 2, 2: 10, 3: 25, 4: 60}
        if preset_idx in presets:
            for slider in self._axis_speed_sliders:
                slider.setValue(presets[preset_idx])

    def adjust_speed(self, delta: float) -> None:
        """Nudge both axis speeds by *delta* °/s, clamped to 1–90."""
        for slider in self._axis_speed_sliders:
            slider.setValue(max(1, min(90, slider.value() + int(delta))))

    def toggle_motors(self) -> None:
        """Toggle the stepper drivers between enabled and disabled."""
        if self._motor_enabled:
            self.disable_requested.emit()
        else:
            self.enable_requested.emit()

    def home_all(self) -> None:
        """Zero both axes."""
        self._current_positions[1] = 0.0
        self._current_positions[2] = 0.0
        self.update_axis_position(1, 0.0)
        self.update_axis_position(2, 0.0)
        self.home_requested.emit(0)

    # ==================================================================
    # Motion helpers
    # ==================================================================
    def _jog(self, axis: int, direction: int) -> None:
        if axis == 1:
            self.advance_step() if direction > 0 else self.retract_step()
        else:
            self.angle_right_step() if direction > 0 else self.angle_left_step()

    def _get_axis_speed(self, axis: int) -> float:
        idx = axis - 1
        if 0 <= idx < len(self._axis_speed_sliders):
            return float(self._axis_speed_sliders[idx].value())
        return 20.0

    def _execute_step(self, axis: int, delta_position: float) -> None:
        speed = self._get_axis_speed(axis)

        # Optimistic open-loop update so the readout responds immediately.
        # Only while connected, so an offline panel never shows fake motion.
        if self._connected:
            lo, hi = AXIS_LIMITS.get(axis, (-180.0, 180.0))
            pos = self._current_positions.get(axis, 0.0) + delta_position
            self._current_positions[axis] = max(lo, min(hi, pos))
            self.update_axis_position(axis, self._current_positions[axis])

        self.move_axis_relative.emit(axis, delta_position, speed)

    def _execute_current_step(self, axis: int, direction: int) -> None:
        idx = axis - 1
        if 0 <= idx < len(self._axis_increments):
            delta = float(direction) * self._axis_increments[idx].value()
            self._execute_step(axis, delta)

    # ==================================================================
    # Slots
    # ==================================================================
    def _on_connect_clicked(self) -> None:
        if self._connected:
            self.disconnect_requested.emit()
            return
        port = self._port_combo.currentText().strip()
        if port:
            self.connect_requested.emit(port, DEFAULT_BAUD_RATE)

    # ==================================================================
    # Public API
    # ==================================================================
    def set_connection_status(self, connected: bool) -> None:
        self._connected = connected

        if connected:
            update_status_indicator(self._conn_indicator, COLOR_STATUS_CONNECTED, 8)
            self._conn_label.setText("Online")
            self._conn_label.setStyleSheet(f"color: {_GREEN}; font-weight: 600;")
            self._connect_btn.setText("Disconnect")
            self._connect_btn.setObjectName("disconnectButton")
            self._port_combo.setEnabled(False)
            self._refresh_btn.setEnabled(False)
        else:
            update_status_indicator(self._conn_indicator, COLOR_STATUS_DISCONNECTED, 8)
            self._conn_label.setText("Offline")
            self._conn_label.setStyleSheet(f"color: {_RED}; font-weight: 600;")
            self._connect_btn.setText("Connect")
            self._connect_btn.setObjectName("connectButton")
            self._port_combo.setEnabled(True)
            self._refresh_btn.setEnabled(True)

        # Re-apply the stylesheet so the changed object name takes effect.
        self._connect_btn.style().unpolish(self._connect_btn)
        self._connect_btn.style().polish(self._connect_btn)

    def set_ports(self, ports: list[str]) -> None:
        current = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)

    def update_axis_position(self, axis: int, position: float) -> None:
        """Update the displayed position for an axis (native units)."""
        self._current_positions[axis] = position
        idx = axis - 1
        if 0 <= idx < len(self._axis_position_labels):
            unit = AXIS_UNITS.get(axis, "")
            sign = "+" if position >= 0 else ""
            self._axis_position_labels[idx].setText(f"{sign}{position:.2f} {unit}")

    def set_axis_homed(self, axis: int, homed: bool) -> None:
        idx = axis - 1
        if not (0 <= idx < len(self._axis_homed_indicators)):
            return

        color = COLOR_STATUS_CONNECTED if homed else COLOR_STATUS_DISCONNECTED
        update_status_indicator(self._axis_homed_indicators[idx], color, 7)
        self._axis_homed_labels[idx].setText("Homed" if homed else "Not homed")
        self._axis_homed_labels[idx].setStyleSheet(
            f"color: {_GREEN if homed else _DIM}; font-size: 11px;"
        )

    def set_motor_status(self, enabled: bool) -> None:
        self._motor_enabled = enabled

        if enabled:
            update_status_indicator(self._motor_indicator, COLOR_STATUS_CONNECTED, 8)
            self._motor_status_label.setText("Motors on")
            self._motor_status_label.setStyleSheet(f"color: {_GREEN}; font-weight: 600;")
            self._enable_btn.setText("Disable motors")
            self._enable_btn.setObjectName("disconnectButton")
        else:
            update_status_indicator(self._motor_indicator, COLOR_STATUS_DISCONNECTED, 8)
            self._motor_status_label.setText("Motors off")
            self._motor_status_label.setStyleSheet(f"color: {_DIM}; font-weight: 600;")
            self._enable_btn.setText("Enable motors")
            self._enable_btn.setObjectName("connectButton")

        self._enable_btn.style().unpolish(self._enable_btn)
        self._enable_btn.style().polish(self._enable_btn)
