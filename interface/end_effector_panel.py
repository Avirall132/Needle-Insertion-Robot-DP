"""
End-Effector Control Panel for ESP32-based needle insertion mechanism.

Provides serial connection management, two-axis motor jog controls,
homing, enable/disable, and an emergency stop button.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSlider,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal

from interface.styles import (
    create_status_indicator, update_status_indicator,
    COLOR_STATUS_CONNECTED, COLOR_STATUS_DISCONNECTED, COLOR_STATUS_WARNING,
    COLOR_STATUS_IDLE, COLOR_STATUS_MOVING, COLOR_STATUS_STOPPED,
)

# Default serial settings
DEFAULT_BAUD_RATE = 115200

# Axis descriptors
AXIS_INFO = [
    {"index": 1, "name": "Axis 1 (Insertion)"},
    {"index": 2, "name": "Axis 2 (Rotation)"},
]


class EndEffectorPanel(QWidget):
    """
    Control panel for the ESP32-driven two-axis end-effector.

    Features:
    - Serial port connection management
    - Per-axis jog, homing, position display
    - Motor enable / disable
    - Emergency stop
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    connect_requested = Signal(str, int)          # port, baud
    disconnect_requested = Signal()
    move_axis = Signal(int, float, float)          # axis, target, speed
    move_axis_relative = Signal(int, float, float) # axis, delta, speed
    stop_requested = Signal()
    home_requested = Signal(int)                   # axis (0 = both)
    enable_requested = Signal()
    disable_requested = Signal()
    refresh_ports_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("endEffectorPanel")

        # Dynamic element storage
        self._axis_position_labels: list[QLabel] = []
        self._axis_homed_indicators: list[QLabel] = []
        self._axis_homed_labels: list[QLabel] = []
        self._axis_increments: list[QDoubleSpinBox] = []
        self._axis_speed_sliders: list[QSlider] = []
        self._axis_speed_labels: list[QLabel] = []

        self._build_ui()

    # ==================================================================
    # UI Construction
    # ==================================================================
    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setSpacing(8)
        self._main_layout.setContentsMargins(6, 6, 6, 6)

        self._build_connection_section()
        for axis in AXIS_INFO:
            self._build_axis_section(axis)
        self._build_motor_section()
        self._build_status_section()

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Connection Section
    # ------------------------------------------------------------------
    def _build_connection_section(self) -> None:
        group = QGroupBox("ESP32 Connection")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        # Row 0 – status
        self._esp_conn_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED)
        self._esp_conn_label = QLabel("Disconnected")
        layout.addWidget(self._esp_conn_indicator, 0, 0)
        layout.addWidget(self._esp_conn_label, 0, 1, 1, 2)

        # Row 1 – serial port
        layout.addWidget(QLabel("Port:"), 1, 0)
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(120)
        self._port_combo.setEditable(False)
        layout.addWidget(self._port_combo, 1, 1)

        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setToolTip("Refresh serial ports")
        self._refresh_btn.setFixedWidth(36)
        self._refresh_btn.clicked.connect(self.refresh_ports_requested.emit)
        layout.addWidget(self._refresh_btn, 1, 2)

        # Row 2 – baud rate (display only)
        layout.addWidget(QLabel("Baud Rate:"), 2, 0)
        self._baud_label = QLabel(str(DEFAULT_BAUD_RATE))
        self._baud_label.setObjectName("valueLabel")
        layout.addWidget(self._baud_label, 2, 1, 1, 2)

        # Row 3 – connect / disconnect
        btn_row = QHBoxLayout()
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connectButton")
        self._connect_btn.clicked.connect(self._on_connect_clicked)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("disconnectButton")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)

        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(self._disconnect_btn)
        layout.addLayout(btn_row, 3, 0, 1, 3)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Per-Axis Control Section
    # ------------------------------------------------------------------
    def _build_axis_section(self, axis_info: dict) -> None:
        axis_idx = axis_info["index"]
        group = QGroupBox(axis_info["name"])
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Position display row
        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("Position (°):"))
        lbl_pos = QLabel("0.00")
        lbl_pos.setObjectName("valueLabel")
        lbl_pos.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._axis_position_labels.append(lbl_pos)
        pos_row.addWidget(lbl_pos)
        layout.addLayout(pos_row)

        # Jog buttons row
        jog_row = QHBoxLayout()

        btn_neg = QPushButton("−")
        btn_neg.setObjectName("jogButton")
        btn_neg.pressed.connect(lambda a=axis_idx: self._on_axis_jog_pressed(a, -1))
        btn_neg.released.connect(self._on_axis_jog_released)
        jog_row.addWidget(btn_neg)

        btn_pos = QPushButton("+")
        btn_pos.setObjectName("jogButton")
        btn_pos.pressed.connect(lambda a=axis_idx: self._on_axis_jog_pressed(a, 1))
        btn_pos.released.connect(self._on_axis_jog_released)
        jog_row.addWidget(btn_pos)

        jog_row.addSpacing(12)

        # Increment
        jog_row.addWidget(QLabel("Inc:"))
        inc_spin = QDoubleSpinBox()
        inc_spin.setRange(0.1, 10.0)
        inc_spin.setValue(1.0)
        inc_spin.setSingleStep(0.1)
        inc_spin.setDecimals(1)
        inc_spin.setSuffix("°")
        self._axis_increments.append(inc_spin)
        jog_row.addWidget(inc_spin)

        layout.addLayout(jog_row)

        # Speed slider row
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed (%):"))
        slider = QSlider(Qt.Horizontal)
        slider.setRange(1, 100)
        slider.setValue(25)
        self._axis_speed_sliders.append(slider)
        speed_row.addWidget(slider)

        speed_lbl = QLabel("25%")
        speed_lbl.setMinimumWidth(35)
        slider.valueChanged.connect(lambda v, lbl=speed_lbl: lbl.setText(f"{v}%"))
        self._axis_speed_labels.append(speed_lbl)
        speed_row.addWidget(speed_lbl)
        layout.addLayout(speed_row)

        # Home button + homed status row
        home_row = QHBoxLayout()
        home_btn = QPushButton(f"Home Axis {axis_idx}")
        home_btn.clicked.connect(lambda checked=False, a=axis_idx: self.home_requested.emit(a))
        home_row.addWidget(home_btn)

        home_row.addSpacing(12)
        home_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        self._axis_homed_indicators.append(home_indicator)
        home_row.addWidget(home_indicator)

        home_lbl = QLabel("Not Homed")
        self._axis_homed_labels.append(home_lbl)
        home_row.addWidget(home_lbl)
        home_row.addStretch()

        layout.addLayout(home_row)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Motor Control Section
    # ------------------------------------------------------------------
    def _build_motor_section(self) -> None:
        group = QGroupBox("Motor Control")
        layout = QHBoxLayout(group)
        layout.setSpacing(8)

        self._enable_btn = QPushButton("Enable Motors")
        self._enable_btn.setObjectName("connectButton")
        self._enable_btn.clicked.connect(self.enable_requested.emit)
        layout.addWidget(self._enable_btn)

        self._disable_btn = QPushButton("Disable Motors")
        self._disable_btn.setObjectName("disconnectButton")
        self._disable_btn.clicked.connect(self.disable_requested.emit)
        layout.addWidget(self._disable_btn)

        self._motor_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        layout.addWidget(self._motor_indicator)

        self._motor_status_label = QLabel("Disabled")
        layout.addWidget(self._motor_status_label)
        layout.addStretch()

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Status / Stop Section
    # ------------------------------------------------------------------
    def _build_status_section(self) -> None:
        group = QGroupBox("Status")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Communication status
        comm_row = QHBoxLayout()
        comm_row.addWidget(QLabel("Communication:"))
        self._comm_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        comm_row.addWidget(self._comm_indicator)
        self._comm_label = QLabel("N/A")
        self._comm_label.setObjectName("valueLabel")
        comm_row.addWidget(self._comm_label)
        comm_row.addStretch()
        layout.addLayout(comm_row)

        # Watchdog status
        wd_row = QHBoxLayout()
        wd_row.addWidget(QLabel("Watchdog:"))
        self._watchdog_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        wd_row.addWidget(self._watchdog_indicator)
        self._watchdog_label = QLabel("N/A")
        self._watchdog_label.setObjectName("valueLabel")
        wd_row.addWidget(self._watchdog_label)
        wd_row.addStretch()
        layout.addLayout(wd_row)

        # STOP button
        self._stop_btn = QPushButton("⬛  STOP")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        layout.addWidget(self._stop_btn)

        self._main_layout.addWidget(group)

    # ==================================================================
    # Internal Slot Helpers
    # ==================================================================
    def _on_connect_clicked(self) -> None:
        port = self._port_combo.currentText().strip()
        if port:
            self.connect_requested.emit(port, DEFAULT_BAUD_RATE)

    def _on_disconnect_clicked(self) -> None:
        self.disconnect_requested.emit()

    def _on_axis_jog_pressed(self, axis: int, direction: int) -> None:
        # Map axis_idx (1-based) to list index (0-based)
        list_idx = axis - 1
        if list_idx < 0 or list_idx >= len(self._axis_increments):
            return
        inc = self._axis_increments[list_idx].value()
        speed = self._axis_speed_sliders[list_idx].value() / 100.0
        delta = direction * inc
        self.move_axis_relative.emit(axis, delta, speed)

    def _on_axis_jog_released(self) -> None:
        self.stop_requested.emit()

    # ==================================================================
    # Public API
    # ==================================================================
    def set_connection_status(self, connected: bool) -> None:
        """Update ESP32 connection indicator."""
        if connected:
            update_status_indicator(self._esp_conn_indicator, COLOR_STATUS_CONNECTED)
            self._esp_conn_label.setText("Connected")
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
            self._port_combo.setEnabled(False)
            self._refresh_btn.setEnabled(False)
        else:
            update_status_indicator(self._esp_conn_indicator, COLOR_STATUS_DISCONNECTED)
            self._esp_conn_label.setText("Disconnected")
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._port_combo.setEnabled(True)
            self._refresh_btn.setEnabled(True)

    def set_ports(self, ports: list[str]) -> None:
        """Populate the serial port combo box."""
        current = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)

    def update_axis_position(self, axis: int, degrees: float) -> None:
        """
        Update the displayed position for a given axis.

        Args:
            axis: 1 or 2 (1-based).
            degrees: Current position in degrees.
        """
        list_idx = axis - 1
        if 0 <= list_idx < len(self._axis_position_labels):
            self._axis_position_labels[list_idx].setText(f"{degrees:.2f}")

    def set_axis_homed(self, axis: int, homed: bool) -> None:
        """
        Update the homed status indicator for an axis.

        Args:
            axis: 1 or 2 (1-based).
            homed: True if homed.
        """
        list_idx = axis - 1
        if 0 <= list_idx < len(self._axis_homed_indicators):
            color = COLOR_STATUS_CONNECTED if homed else COLOR_STATUS_DISCONNECTED
            update_status_indicator(self._axis_homed_indicators[list_idx], color, 10)
            self._axis_homed_labels[list_idx].setText("Homed" if homed else "Not Homed")

    def set_motor_status(self, enabled: bool) -> None:
        """Update motor enable/disable indicator."""
        if enabled:
            update_status_indicator(self._motor_indicator, COLOR_STATUS_CONNECTED, 10)
            self._motor_status_label.setText("Enabled")
        else:
            update_status_indicator(self._motor_indicator, COLOR_STATUS_DISCONNECTED, 10)
            self._motor_status_label.setText("Disabled")

    def set_communication_status(self, status: str, healthy: bool) -> None:
        """Update communication status display."""
        color = COLOR_STATUS_CONNECTED if healthy else COLOR_STATUS_DISCONNECTED
        update_status_indicator(self._comm_indicator, color, 10)
        self._comm_label.setText(status)

    def set_watchdog_status(self, status: str, healthy: bool) -> None:
        """Update watchdog status display."""
        color = COLOR_STATUS_CONNECTED if healthy else COLOR_STATUS_WARNING
        update_status_indicator(self._watchdog_indicator, color, 10)
        self._watchdog_label.setText(status)
