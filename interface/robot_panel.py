"""
Robot Control Panel for UR7e teleoperation.

Provides joint-level and Cartesian-level jog controls, TCP pose display,
connection management, and an emergency stop button.

Design: compact dark-panel layout, Consolas telemetry values, cyan jog buttons.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QDoubleSpinBox, QSlider,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from interface.styles import (
    create_status_indicator, update_status_indicator,
    COLOR_STATUS_CONNECTED, COLOR_STATUS_DISCONNECTED, COLOR_STATUS_WARNING,
    COLOR_STATUS_IDLE, COLOR_STATUS_MOVING, COLOR_STATUS_STOPPED,
    COLOR_BG_INPUT, COLOR_BORDER, COLOR_TEXT_DIM,
)

# Joint names for UR7e (6-axis)
JOINT_NAMES = ["J1", "J2", "J3", "J4", "J5", "J6"]

# Cartesian axis labels
CARTESIAN_AXES = ["X", "Y", "Z", "RX", "RY", "RZ"]

_CYAN  = "#4a90d9"
_RED   = "#e63946"
_AMBER = "#f0a500"
_GREEN = "#2ecc71"


class RobotPanel(QWidget):
    """
    Main control panel for the UR7e robot arm.

    Provides:
    - System status / connection controls
    - Individual joint jog controls (J1–J6)
    - Cartesian jog controls (X/Y/Z/RX/RY/RZ)
    - TCP pose readout
    - Motion status and emergency stop
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    connect_requested    = Signal(str)                      # IP address
    disconnect_requested = Signal()
    jog_joint_start      = Signal(int, int, float, float)   # joint_idx, direction(+1/-1), speed, increment
    jog_joint_stop       = Signal()
    jog_cartesian_start  = Signal(int, int, float, float)   # axis, direction, speed, increment
    jog_cartesian_stop   = Signal()
    stop_requested       = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("robotPanel")

        # Stored references to dynamic UI elements
        self._joint_value_labels:     list[QLabel] = []
        self._cartesian_value_labels: list[QLabel] = []
        self._tcp_value_labels:       list[QLabel] = []

        self._build_ui()

    # ==================================================================
    # UI Construction
    # ==================================================================
    def _build_ui(self) -> None:
        """Assemble the full panel inside a scroll area."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setSpacing(6)
        self._main_layout.setContentsMargins(6, 6, 6, 6)

        self._build_panel_header()
        self._build_status_section()
        self._build_joint_control_section()
        self._build_cartesian_control_section()
        self._build_tcp_section()
        self._build_motion_section()

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Panel Identity Header (no groupbox – just labels)
    # ------------------------------------------------------------------
    def _build_panel_header(self) -> None:
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(hdr)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)

        title = QLabel("UR7e ARM CONTROL")
        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {_CYAN}; background: transparent;")
        layout.addWidget(title)

        sub = QLabel("Universal Robots UR7e · 6-Axis Collaborative Arm")
        sub.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px; background: transparent;")
        layout.addWidget(sub)

        self._main_layout.addWidget(hdr)

    # ------------------------------------------------------------------
    # Status / Connection Section
    # ------------------------------------------------------------------
    def _build_status_section(self) -> None:
        group = QGroupBox("UR7e STATUS & CONNECTION")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Row 0 – connection status + mode chips
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        self._conn_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=14)
        status_row.addWidget(self._conn_indicator)

        self._conn_label = QLabel("OFFLINE")
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        self._conn_label.setFont(font)
        self._conn_label.setStyleSheet(f"color: {_RED}; background: transparent;")
        status_row.addWidget(self._conn_label)

        status_row.addSpacing(10)

        # Robot mode chip
        mode_lbl = QLabel("Mode:")
        mode_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px; background: transparent;")
        status_row.addWidget(mode_lbl)
        self._robot_mode_label = QLabel("N/A")
        self._robot_mode_label.setObjectName("valueLabel")
        self._robot_mode_label.setStyleSheet(
            f"font-family: 'Consolas','Courier New',monospace; font-size: 11px;"
            f"color: #b8c6e0; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
            f"border-radius: 2px; padding: 2px 6px;"
        )
        status_row.addWidget(self._robot_mode_label)

        status_row.addSpacing(6)

        # Safety chip
        safety_lbl = QLabel("Safety:")
        safety_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px; background: transparent;")
        status_row.addWidget(safety_lbl)
        self._safety_mode_label = QLabel("N/A")
        self._safety_mode_label.setObjectName("valueLabel")
        self._safety_mode_label.setStyleSheet(
            f"font-family: 'Consolas','Courier New',monospace; font-size: 11px;"
            f"color: #b8c6e0; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
            f"border-radius: 2px; padding: 2px 6px;"
        )
        status_row.addWidget(self._safety_mode_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Row 1 – IP + buttons
        conn_row = QHBoxLayout()
        conn_row.setSpacing(6)

        ip_lbl = QLabel("IP:")
        ip_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px; background: transparent;")
        ip_lbl.setFixedWidth(20)
        conn_row.addWidget(ip_lbl)

        self._ip_input = QLineEdit("192.168.1.100")
        self._ip_input.setPlaceholderText("192.168.1.xxx")
        conn_row.addWidget(self._ip_input, 1)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connectButton")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        conn_row.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("disconnectButton")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        conn_row.addWidget(self._disconnect_btn)

        layout.addLayout(conn_row)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Joint Space Jog Section
    # ------------------------------------------------------------------
    def _build_joint_control_section(self) -> None:
        group = QGroupBox("JOINT SPACE JOG")
        layout = QVBoxLayout(group)
        layout.setSpacing(3)

        # Column header
        hdr_row = QHBoxLayout()
        hdr_row.addWidget(self._dim_label("Joint"), 2)
        hdr_row.addWidget(self._dim_label("Position °", align=Qt.AlignRight), 3)
        hdr_row.addWidget(self._dim_label("−", align=Qt.AlignCenter), 1)
        hdr_row.addWidget(self._dim_label("+", align=Qt.AlignCenter), 1)
        layout.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {COLOR_BORDER};")
        layout.addWidget(sep)

        self._joint_value_labels = []
        for idx, name in enumerate(JOINT_NAMES):
            row = QHBoxLayout()
            row.setSpacing(4)

            lbl_name = QLabel(name)
            lbl_name.setFixedWidth(28)
            lbl_name.setStyleSheet("font-weight: bold; font-size: 11px; background: transparent;")
            row.addWidget(lbl_name, 2)

            lbl_val = QLabel("0.00")
            lbl_val.setObjectName("valueLabel")
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl_val.setMinimumWidth(70)
            lbl_val.setStyleSheet(
                f"font-family: 'Consolas','Courier New',monospace; font-size: 12px;"
                f"color: #b8c6e0; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
                f"border-radius: 2px; padding: 2px 6px;"
            )
            self._joint_value_labels.append(lbl_val)
            row.addWidget(lbl_val, 3)

            btn_neg = QPushButton("−")
            btn_neg.setObjectName("jogButton")
            btn_neg.setAutoRepeat(False)
            btn_neg.pressed.connect(lambda i=idx: self._on_joint_jog_pressed(i, -1))
            btn_neg.released.connect(self._on_joint_jog_released)
            row.addWidget(btn_neg, 1)

            btn_pos = QPushButton("+")
            btn_pos.setObjectName("jogButton")
            btn_pos.setAutoRepeat(False)
            btn_pos.pressed.connect(lambda i=idx: self._on_joint_jog_pressed(i, 1))
            btn_pos.released.connect(self._on_joint_jog_released)
            row.addWidget(btn_pos, 1)

            layout.addLayout(row)

        # Speed + increment row
        params = QHBoxLayout()
        params.setSpacing(6)

        params.addWidget(self._dim_label("STEP"))
        self._joint_increment = QDoubleSpinBox()
        self._joint_increment.setRange(0.1, 10.0)
        self._joint_increment.setValue(1.0)
        self._joint_increment.setSingleStep(0.1)
        self._joint_increment.setDecimals(1)
        self._joint_increment.setSuffix("°")
        self._joint_increment.setFixedWidth(76)
        params.addWidget(self._joint_increment)

        params.addSpacing(8)
        params.addWidget(self._dim_label("SPEED"))

        self._joint_speed_slider = QSlider(Qt.Horizontal)
        self._joint_speed_slider.setRange(1, 100)
        self._joint_speed_slider.setValue(25)
        self._joint_speed_slider.setTickInterval(10)
        params.addWidget(self._joint_speed_slider, 1)

        self._joint_speed_label = QLabel("25%")
        self._joint_speed_label.setFixedWidth(36)
        self._joint_speed_label.setStyleSheet(f"color: {_CYAN}; font-weight: bold; background: transparent;")
        self._joint_speed_slider.valueChanged.connect(
            lambda v: self._joint_speed_label.setText(f"{v}%")
        )
        params.addWidget(self._joint_speed_label)

        layout.addLayout(params)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Cartesian Jog Section
    # ------------------------------------------------------------------
    def _build_cartesian_control_section(self) -> None:
        group = QGroupBox("CARTESIAN JOG  (TCP Frame)")
        layout = QVBoxLayout(group)
        layout.setSpacing(3)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(self._dim_label("Axis"), 2)
        hdr_row.addWidget(self._dim_label("Value", align=Qt.AlignRight), 3)
        hdr_row.addWidget(self._dim_label("−", align=Qt.AlignCenter), 1)
        hdr_row.addWidget(self._dim_label("+", align=Qt.AlignCenter), 1)
        layout.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {COLOR_BORDER};")
        layout.addWidget(sep)

        self._cartesian_value_labels = []
        for idx, name in enumerate(CARTESIAN_AXES):
            unit = "mm" if idx < 3 else "°"
            row = QHBoxLayout()
            row.setSpacing(4)

            lbl_name = QLabel(name)
            lbl_name.setFixedWidth(28)
            lbl_name.setStyleSheet("font-weight: bold; font-size: 11px; background: transparent;")
            row.addWidget(lbl_name, 2)

            lbl_val = QLabel(f"0.00 {unit}")
            lbl_val.setObjectName("valueLabel")
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl_val.setMinimumWidth(70)
            lbl_val.setStyleSheet(
                f"font-family: 'Consolas','Courier New',monospace; font-size: 12px;"
                f"color: #b8c6e0; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
                f"border-radius: 2px; padding: 2px 6px;"
            )
            self._cartesian_value_labels.append(lbl_val)
            row.addWidget(lbl_val, 3)

            btn_neg = QPushButton("−")
            btn_neg.setObjectName("jogButton")
            btn_neg.pressed.connect(lambda i=idx: self._on_cartesian_jog_pressed(i, -1))
            btn_neg.released.connect(self._on_cartesian_jog_released)
            row.addWidget(btn_neg, 1)

            btn_pos = QPushButton("+")
            btn_pos.setObjectName("jogButton")
            btn_pos.pressed.connect(lambda i=idx: self._on_cartesian_jog_pressed(i, 1))
            btn_pos.released.connect(self._on_cartesian_jog_released)
            row.addWidget(btn_pos, 1)

            layout.addLayout(row)

        # Increments
        params = QHBoxLayout()
        params.setSpacing(6)
        params.addWidget(self._dim_label("TRANS"))
        self._cart_trans_increment = QDoubleSpinBox()
        self._cart_trans_increment.setRange(0.1, 10.0)
        self._cart_trans_increment.setValue(1.0)
        self._cart_trans_increment.setSingleStep(0.1)
        self._cart_trans_increment.setDecimals(1)
        self._cart_trans_increment.setSuffix(" mm")
        self._cart_trans_increment.setFixedWidth(82)
        params.addWidget(self._cart_trans_increment)

        params.addSpacing(8)
        params.addWidget(self._dim_label("ROT"))
        self._cart_rot_increment = QDoubleSpinBox()
        self._cart_rot_increment.setRange(0.1, 5.0)
        self._cart_rot_increment.setValue(1.0)
        self._cart_rot_increment.setSingleStep(0.1)
        self._cart_rot_increment.setDecimals(1)
        self._cart_rot_increment.setSuffix("°")
        self._cart_rot_increment.setFixedWidth(68)
        params.addWidget(self._cart_rot_increment)
        params.addStretch()

        layout.addLayout(params)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # TCP Pose Display Section
    # ------------------------------------------------------------------
    def _build_tcp_section(self) -> None:
        group = QGroupBox("TCP POSE")
        layout = QGridLayout(group)
        layout.setSpacing(5)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        # Left column: X/Y/Z | Right column: RX/RY/RZ
        tcp_entries = [
            ("X (mm)", 0, 0), ("Y (mm)", 1, 0), ("Z (mm)", 2, 0),
            ("RX (°)", 0, 2), ("RY (°)", 1, 2), ("RZ (°)", 2, 2),
        ]
        self._tcp_value_labels = []
        for text, row, col in tcp_entries:
            lbl_name = QLabel(text)
            lbl_name.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px; background: transparent;")
            lbl_name.setFixedWidth(46)
            layout.addWidget(lbl_name, row, col)

            val_lbl = QLabel("0.00")
            val_lbl.setObjectName("valueLabel")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setStyleSheet(
                f"font-family: 'Consolas','Courier New',monospace; font-size: 12px;"
                f"color: #b8c6e0; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
                f"border-radius: 2px; padding: 2px 6px;"
            )
            self._tcp_value_labels.append(val_lbl)
            layout.addWidget(val_lbl, row, col + 1)

        # Spacer column between left and right groups
        spacer = QWidget()
        spacer.setFixedWidth(8)
        layout.addWidget(spacer, 0, 2)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Motion Status + STOP Section
    # ------------------------------------------------------------------
    def _build_motion_section(self) -> None:
        group = QGroupBox("MOTION STATE")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        layout.addWidget(self._dim_label("State:"))
        self._motion_state_indicator = create_status_indicator(COLOR_STATUS_IDLE)
        layout.addWidget(self._motion_state_indicator)
        self._motion_state_label = QLabel("Idle")
        self._motion_state_label.setObjectName("valueLabel")
        self._motion_state_label.setStyleSheet(
            f"font-family: 'Consolas','Courier New',monospace; font-size: 12px;"
            f"color: #b8c6e0; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
            f"border-radius: 2px; padding: 2px 8px;"
        )
        layout.addWidget(self._motion_state_label)
        layout.addSpacing(10)

        self._stop_btn = QPushButton("STOP ROBOT")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        layout.addWidget(self._stop_btn, 1)

        self._main_layout.addWidget(group)

    # ==================================================================
    # Helpers
    # ==================================================================
    @staticmethod
    def _dim_label(text: str, align: Qt.AlignmentFlag = Qt.AlignLeft) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(align)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px; background: transparent;")
        return lbl

    # ==================================================================
    # Internal Slot Helpers
    # ==================================================================
    def _on_connect_clicked(self) -> None:
        ip = self._ip_input.text().strip()
        if ip:
            self.connect_requested.emit(ip)

    def _on_disconnect_clicked(self) -> None:
        self.disconnect_requested.emit()

    def _on_joint_jog_pressed(self, joint_idx: int, direction: int) -> None:
        speed = self._joint_speed_slider.value() / 100.0
        increment = self._joint_increment.value()
        self.jog_joint_start.emit(joint_idx, direction, speed, increment)

    def _on_joint_jog_released(self) -> None:
        self.jog_joint_stop.emit()

    def _on_cartesian_jog_pressed(self, axis: int, direction: int) -> None:
        speed = self._joint_speed_slider.value() / 100.0
        if axis < 3:
            increment = self._cart_trans_increment.value()
        else:
            increment = self._cart_rot_increment.value()
        self.jog_cartesian_start.emit(axis, direction, speed, increment)

    def _on_cartesian_jog_released(self) -> None:
        self.jog_cartesian_stop.emit()

    # ==================================================================
    # Public API – called from the controller / worker layer
    # ==================================================================
    def set_connection_status(self, connected: bool) -> None:
        """Update UI to reflect robot connection state."""
        if connected:
            update_status_indicator(self._conn_indicator, COLOR_STATUS_CONNECTED, size=14)
            self._conn_label.setText("CONNECTED")
            self._conn_label.setStyleSheet(f"color: {_GREEN}; font-weight: bold; background: transparent;")
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
            self._ip_input.setEnabled(False)
        else:
            update_status_indicator(self._conn_indicator, COLOR_STATUS_DISCONNECTED, size=14)
            self._conn_label.setText("OFFLINE")
            self._conn_label.setStyleSheet(f"color: {_RED}; font-weight: bold; background: transparent;")
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._ip_input.setEnabled(True)

    def set_robot_mode(self, mode: str) -> None:
        """Display the current UR robot mode string."""
        self._robot_mode_label.setText(mode)

    def set_safety_mode(self, mode: str) -> None:
        """Display the current UR safety mode string."""
        self._safety_mode_label.setText(mode)
        # Colour amber if not safe
        if "STOP" in mode.upper() or "PROTECTIVE" in mode.upper():
            self._safety_mode_label.setStyleSheet(
                f"font-family: 'Consolas','Courier New',monospace; font-size: 11px;"
                f"color: {_AMBER}; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
                f"border-radius: 2px; padding: 2px 6px;"
            )
        else:
            self._safety_mode_label.setStyleSheet(
                f"font-family: 'Consolas','Courier New',monospace; font-size: 11px;"
                f"color: #b8c6e0; background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
                f"border-radius: 2px; padding: 2px 6px;"
            )

    def update_joint_positions(self, positions: list[float]) -> None:
        """
        Update displayed joint positions.

        Args:
            positions: List of 6 joint angles in degrees.
        """
        for idx, val in enumerate(positions[:6]):
            self._joint_value_labels[idx].setText(f"{val:.2f}")

    def update_cartesian_values(self, values: list[float]) -> None:
        """
        Update Cartesian axis displays.

        Args:
            values: [X, Y, Z, RX, RY, RZ] – positions in mm and degrees.
        """
        for idx, val in enumerate(values[:6]):
            unit = "mm" if idx < 3 else "°"
            self._cartesian_value_labels[idx].setText(f"{val:.2f} {unit}")

    def update_tcp_pose(self, pose: list[float]) -> None:
        """
        Update TCP pose readout.

        Args:
            pose: [X, Y, Z, RX, RY, RZ] – mm and degrees.
        """
        for idx, val in enumerate(pose[:6]):
            self._tcp_value_labels[idx].setText(f"{val:.2f}")

    def set_motion_state(self, state: str) -> None:
        """
        Update the motion state indicator.

        Args:
            state: One of 'Idle', 'Moving', 'Stopped'.
        """
        color_map = {
            "Idle":    COLOR_STATUS_IDLE,
            "Moving":  COLOR_STATUS_MOVING,
            "Stopped": COLOR_STATUS_STOPPED,
        }
        color = color_map.get(state, COLOR_STATUS_WARNING)
        update_status_indicator(self._motion_state_indicator, color)
        self._motion_state_label.setText(state)
