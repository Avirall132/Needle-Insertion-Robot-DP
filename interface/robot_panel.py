"""
Robot Control Panel for UR7e teleoperation.

Provides joint-level and Cartesian-level jog controls, TCP pose display,
connection management, and an emergency stop button.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QDoubleSpinBox, QSlider,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal

from interface.styles import (
    create_status_indicator, update_status_indicator,
    COLOR_STATUS_CONNECTED, COLOR_STATUS_DISCONNECTED, COLOR_STATUS_WARNING,
    COLOR_STATUS_IDLE, COLOR_STATUS_MOVING, COLOR_STATUS_STOPPED,
)

# Joint names for UR7e (6-axis)
JOINT_NAMES = ["Joint 1", "Joint 2", "Joint 3", "Joint 4", "Joint 5", "Joint 6"]

# Cartesian axis labels
CARTESIAN_AXES = ["X", "Y", "Z", "RX", "RY", "RZ"]


class RobotPanel(QWidget):
    """
    Main control panel for the UR7e robot arm.

    Provides:
    - System status / connection controls
    - Individual joint jog controls
    - Cartesian jog controls
    - TCP pose readout
    - Motion status and emergency stop
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    connect_requested = Signal(str)                     # IP address
    disconnect_requested = Signal()
    jog_joint_start = Signal(int, int, float, float)    # joint_idx, direction(+1/-1), speed, increment
    jog_joint_stop = Signal()
    jog_cartesian_start = Signal(int, int, float, float)  # axis, direction, speed, increment
    jog_cartesian_stop = Signal()
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("robotPanel")

        # Stored references to dynamic UI elements
        self._joint_value_labels: list[QLabel] = []
        self._cartesian_value_labels: list[QLabel] = []
        self._tcp_value_labels: list[QLabel] = []

        self._build_ui()

    # ==================================================================
    # UI Construction
    # ==================================================================
    def _build_ui(self) -> None:
        """Assemble the full panel inside a scroll area."""
        # Outer layout holds the scroll area
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

        self._build_status_section()
        self._build_joint_control_section()
        self._build_cartesian_control_section()
        self._build_tcp_section()
        self._build_motion_section()

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # System Status Section
    # ------------------------------------------------------------------
    def _build_status_section(self) -> None:
        group = QGroupBox("System Status")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        # Row 0 – connection status
        self._conn_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED)
        self._conn_label = QLabel("Disconnected")
        layout.addWidget(self._conn_indicator, 0, 0)
        layout.addWidget(self._conn_label, 0, 1, 1, 2)

        # Row 1 – Robot mode
        layout.addWidget(QLabel("Robot Mode:"), 1, 0, 1, 2)
        self._robot_mode_label = QLabel("N/A")
        self._robot_mode_label.setObjectName("valueLabel")
        layout.addWidget(self._robot_mode_label, 1, 2)

        # Row 2 – Safety mode
        layout.addWidget(QLabel("Safety Mode:"), 2, 0, 1, 2)
        self._safety_mode_label = QLabel("N/A")
        self._safety_mode_label.setObjectName("valueLabel")
        layout.addWidget(self._safety_mode_label, 2, 2)

        # Row 3 – IP address input
        layout.addWidget(QLabel("IP Address:"), 3, 0, 1, 2)
        self._ip_input = QLineEdit("192.168.1.100")
        self._ip_input.setPlaceholderText("e.g. 192.168.1.100")
        layout.addWidget(self._ip_input, 3, 2)

        # Row 4 – Connect / Disconnect buttons
        btn_layout = QHBoxLayout()
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connectButton")
        self._connect_btn.clicked.connect(self._on_connect_clicked)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("disconnectButton")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)

        btn_layout.addWidget(self._connect_btn)
        btn_layout.addWidget(self._disconnect_btn)
        layout.addLayout(btn_layout, 4, 0, 1, 3)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Joint Control Section
    # ------------------------------------------------------------------
    def _build_joint_control_section(self) -> None:
        group = QGroupBox("Joint Control")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.addWidget(QLabel("Joint"), 2)
        header.addWidget(QLabel("Position (°)"), 3)
        header.addWidget(QLabel("Jog"), 2)
        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1e3a5f;")
        layout.addWidget(sep)

        # Per-joint rows
        self._joint_value_labels = []
        for idx, name in enumerate(JOINT_NAMES):
            row = QHBoxLayout()
            row.setSpacing(4)

            lbl_name = QLabel(name)
            lbl_name.setMinimumWidth(55)
            row.addWidget(lbl_name, 2)

            lbl_val = QLabel("0.00")
            lbl_val.setObjectName("valueLabel")
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
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

        # Movement parameters
        params = QHBoxLayout()

        params.addWidget(QLabel("Increment (°):"))
        self._joint_increment = QDoubleSpinBox()
        self._joint_increment.setRange(0.1, 10.0)
        self._joint_increment.setValue(1.0)
        self._joint_increment.setSingleStep(0.1)
        self._joint_increment.setDecimals(1)
        self._joint_increment.setSuffix("°")
        params.addWidget(self._joint_increment)

        params.addSpacing(12)
        params.addWidget(QLabel("Speed (%):"))

        self._joint_speed_slider = QSlider(Qt.Horizontal)
        self._joint_speed_slider.setRange(1, 100)
        self._joint_speed_slider.setValue(25)
        self._joint_speed_slider.setTickInterval(10)
        params.addWidget(self._joint_speed_slider)

        self._joint_speed_label = QLabel("25%")
        self._joint_speed_label.setMinimumWidth(35)
        self._joint_speed_slider.valueChanged.connect(
            lambda v: self._joint_speed_label.setText(f"{v}%")
        )
        params.addWidget(self._joint_speed_label)

        layout.addLayout(params)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Cartesian Control Section
    # ------------------------------------------------------------------
    def _build_cartesian_control_section(self) -> None:
        group = QGroupBox("Cartesian Control")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.addWidget(QLabel("Axis"), 2)
        header.addWidget(QLabel("Value"), 3)
        header.addWidget(QLabel("Jog"), 2)
        layout.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1e3a5f;")
        layout.addWidget(sep)

        # Per-axis rows
        self._cartesian_value_labels = []
        for idx, name in enumerate(CARTESIAN_AXES):
            row = QHBoxLayout()
            row.setSpacing(4)

            unit = "mm" if idx < 3 else "°"
            lbl_name = QLabel(f"{name}")
            lbl_name.setMinimumWidth(30)
            row.addWidget(lbl_name, 2)

            lbl_val = QLabel(f"0.00 {unit}")
            lbl_val.setObjectName("valueLabel")
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
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

        # Increment controls
        params = QHBoxLayout()

        params.addWidget(QLabel("Trans. (mm):"))
        self._cart_trans_increment = QDoubleSpinBox()
        self._cart_trans_increment.setRange(0.1, 10.0)
        self._cart_trans_increment.setValue(1.0)
        self._cart_trans_increment.setSingleStep(0.1)
        self._cart_trans_increment.setDecimals(1)
        self._cart_trans_increment.setSuffix(" mm")
        params.addWidget(self._cart_trans_increment)

        params.addSpacing(8)
        params.addWidget(QLabel("Rot. (°):"))
        self._cart_rot_increment = QDoubleSpinBox()
        self._cart_rot_increment.setRange(0.1, 5.0)
        self._cart_rot_increment.setValue(1.0)
        self._cart_rot_increment.setSingleStep(0.1)
        self._cart_rot_increment.setDecimals(1)
        self._cart_rot_increment.setSuffix("°")
        params.addWidget(self._cart_rot_increment)

        layout.addLayout(params)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # TCP Pose Display Section
    # ------------------------------------------------------------------
    def _build_tcp_section(self) -> None:
        group = QGroupBox("TCP Pose")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        tcp_labels = [
            ("X (mm):", 0, 0), ("Y (mm):", 1, 0), ("Z (mm):", 2, 0),
            ("RX (°):", 0, 2), ("RY (°):", 1, 2), ("RZ (°):", 2, 2),
        ]
        self._tcp_value_labels = []
        for text, row, col in tcp_labels:
            layout.addWidget(QLabel(text), row, col)
            val_lbl = QLabel("0.00")
            val_lbl.setObjectName("valueLabel")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tcp_value_labels.append(val_lbl)
            layout.addWidget(val_lbl, row, col + 1)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Motion Status Section
    # ------------------------------------------------------------------
    def _build_motion_section(self) -> None:
        group = QGroupBox("Motion Status")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Current state row
        state_row = QHBoxLayout()
        state_row.addWidget(QLabel("State:"))
        self._motion_state_indicator = create_status_indicator(COLOR_STATUS_IDLE)
        state_row.addWidget(self._motion_state_indicator)
        self._motion_state_label = QLabel("Idle")
        self._motion_state_label.setObjectName("valueLabel")
        state_row.addWidget(self._motion_state_label)
        state_row.addStretch()
        layout.addLayout(state_row)

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
            update_status_indicator(self._conn_indicator, COLOR_STATUS_CONNECTED)
            self._conn_label.setText("Connected")
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
            self._ip_input.setEnabled(False)
        else:
            update_status_indicator(self._conn_indicator, COLOR_STATUS_DISCONNECTED)
            self._conn_label.setText("Disconnected")
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._ip_input.setEnabled(True)

    def set_robot_mode(self, mode: str) -> None:
        """Display the current UR robot mode string."""
        self._robot_mode_label.setText(mode)

    def set_safety_mode(self, mode: str) -> None:
        """Display the current UR safety mode string."""
        self._safety_mode_label.setText(mode)

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
            "Idle": COLOR_STATUS_IDLE,
            "Moving": COLOR_STATUS_MOVING,
            "Stopped": COLOR_STATUS_STOPPED,
        }
        color = color_map.get(state, COLOR_STATUS_WARNING)
        update_status_indicator(self._motion_state_indicator, color)
        self._motion_state_label.setText(state)
