"""
End-Effector Control Panel for ESP32-based needle insertion mechanism.

Primary Role: Teleoperation Telemetry Display & Keyboard Teleop HUD.
Displays high-visibility real-time values for:
  - Axis 1: Needle Linear Travel (Forward / Backward, To & Fro)
  - Axis 2: Needle Guide Angle (Angle Left / Angle Right)

Designed specifically for keyboard-driven teleoperation:
  - Huge 32px digital value displays (high readability at a glance)
  - Live motion direction feedback (Idle, Forward, Backward, Angle Left, Angle Right)
  - Direct responsive position updates (no lag or stuck at 0)
  - Keyboard shortcut cheat-sheet HUD
  - Preserves all signals, public APIs, and manual tuning controls
"""

from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSlider,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from interface.styles import (
    create_status_indicator, update_status_indicator,
    COLOR_STATUS_CONNECTED, COLOR_STATUS_DISCONNECTED, COLOR_STATUS_WARNING,
    COLOR_BG_INPUT, COLOR_BORDER, COLOR_TEXT_DIM,
)

# Default serial settings
DEFAULT_BAUD_RATE = 115200

# Travel limits
AXIS_LIMITS = {
    1: (-180.0, 180.0),
    2: (-360.0, 360.0),
}

_CYAN    = "#4a90d9"
_RED     = "#e63946"
_AMBER   = "#f0a500"
_GREEN   = "#2ecc71"
_TEXT    = "#dde1e9"
_DIM     = "#7a8194"
_CARD_BG = "#090a0d"


class EndEffectorPanel(QWidget):
    """
    Telemetry & Value Display for the ESP32 needle end-effector.

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

        # Dynamic element storage for external API compatibility
        self._axis_position_labels:  list[QLabel]         = []
        self._axis_homed_indicators: list[QLabel]         = []
        self._axis_homed_labels:     list[QLabel]         = []
        self._axis_increments:       list[QDoubleSpinBox] = []
        self._axis_speed_sliders:    list[QSlider]        = []
        self._axis_speed_labels:     list[QLabel]         = []
        self._axis_speed_spins:      list[QDoubleSpinBox] = []
        self._axis_target_spins:     list[QDoubleSpinBox] = []

        # Motion status badges
        self._axis_motion_badges:    list[QLabel]         = []

        # Reset timers to clear motion states back to IDLE
        self._idle_timer_axis1 = QTimer(self)
        self._idle_timer_axis1.setSingleShot(True)
        self._idle_timer_axis1.timeout.connect(lambda: self._set_motion_badge(1, "IDLE", _DIM))

        self._idle_timer_axis2 = QTimer(self)
        self._idle_timer_axis2.setSingleShot(True)
        self._idle_timer_axis2.timeout.connect(lambda: self._set_motion_badge(2, "IDLE", _DIM))

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
        self._main_layout.setSpacing(10)
        self._main_layout.setContentsMargins(8, 8, 8, 8)

        # 1. Header & Status Strip
        self._build_header_and_status_strip()

        # 2. Axis 1: Needle Linear Travel (Forward / Backward)
        self._build_axis1_display()

        # 3. Axis 2: Needle guide angle adjustment
        self._build_axis2_display()

        # 4. Keyboard Shortcuts HUD / Legend
        self._build_keyboard_hud()

        # 5. Master Stop Button
        self._build_stop_section()

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Header & Status Strip
    # ------------------------------------------------------------------
    def _build_header_and_status_strip(self) -> None:
        group = QGroupBox("HARDWARE STATUS & TELEOP STATE")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(10)

        # Hardware connection
        self._esp_conn_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=11)
        row.addWidget(self._esp_conn_indicator)

        self._esp_conn_label = QLabel("OFFLINE")
        self._esp_conn_label.setStyleSheet(f"color: {_RED}; font-weight: bold; background: transparent; font-size: 11px;")
        row.addWidget(self._esp_conn_label)

        row.addSpacing(6)
        row.addWidget(self._dim_lbl("Port:"))

        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(110)
        self._port_combo.setEditable(False)
        row.addWidget(self._port_combo)

        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setToolTip("Scan COM ports")
        self._refresh_btn.setFixedWidth(26)
        self._refresh_btn.clicked.connect(self.refresh_ports_requested.emit)
        row.addWidget(self._refresh_btn)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connectButton")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        row.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("disconnectButton")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        row.addWidget(self._disconnect_btn)

        row.addSpacing(12)

        # Motor Drivers
        row.addWidget(self._dim_lbl("Motors:"))
        self._motor_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        row.addWidget(self._motor_indicator)
        self._motor_status_label = QLabel("Disabled")
        self._motor_status_label.setStyleSheet(f"color: {_RED}; font-weight: bold; background: transparent; font-size: 11px;")
        row.addWidget(self._motor_status_label)

        self._enable_btn = QPushButton("ENABLE [M]")
        self._enable_btn.setObjectName("connectButton")
        self._enable_btn.setMinimumHeight(24)
        self._enable_btn.clicked.connect(self.enable_requested.emit)
        row.addWidget(self._enable_btn)

        self._disable_btn = QPushButton("DISABLE [M]")
        self._disable_btn.setObjectName("disconnectButton")
        self._disable_btn.setMinimumHeight(24)
        self._disable_btn.clicked.connect(self.disable_requested.emit)
        row.addWidget(self._disable_btn)

        row.addStretch()

        # Keyboard active badge
        kb_badge = QLabel("⌨ KEYBOARD TELEOP ACTIVE")
        kb_badge.setStyleSheet(
            f"background-color: #0e2a3a; color: #4cc9f0; font-family: 'Consolas', monospace;"
            f"font-size: 10px; font-weight: bold; border: 1px solid #207a90; border-radius: 3px; padding: 3px 8px;"
        )
        row.addWidget(kb_badge)

        layout.addLayout(row)
        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Axis 1: Needle Linear Travel (Forward / Backward)
    # ------------------------------------------------------------------
    def _build_axis1_display(self) -> None:
        group = QGroupBox("AXIS 1 · NEEDLE LINEAR MOTION  [ FORWARD / BACKWARD ]")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Big Telemetry Value Card
        card = QFrame()
        card.setStyleSheet(
            f"background-color: {_CARD_BG}; border: 1px solid #20242e; border-radius: 4px; padding: 8px 12px;"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 6, 10, 6)
        card_layout.setSpacing(16)

        # Left: Huge Position Readout
        pos_box = QVBoxLayout()
        pos_box.setSpacing(2)

        pos_title = QLabel("CURRENT LINEAR POSITION")
        pos_title.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        pos_box.addWidget(pos_title)

        lbl_pos1 = QLabel("+0.00 mm")
        lbl_pos1.setObjectName("valueLabel")
        lbl_pos1.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_pos1.setStyleSheet(
            f"font-family: 'Consolas','Courier New',monospace; font-size: 32px; font-weight: bold;"
            f"color: {_CYAN}; background: transparent; border: none; padding: 0px;"
        )
        self._axis_position_labels.append(lbl_pos1)
        pos_box.addWidget(lbl_pos1)

        card_layout.addLayout(pos_box, stretch=2)

        # Middle: Motion State Badge
        state_box = QVBoxLayout()
        state_box.setSpacing(4)
        state_title = QLabel("DIRECTION")
        state_title.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        state_box.addWidget(state_title)

        badge1 = QLabel("IDLE")
        badge1.setAlignment(Qt.AlignCenter)
        badge1.setStyleSheet(
            f"font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold;"
            f"color: {_DIM}; background-color: #14171d; border: 1px solid #2a2e38; border-radius: 3px;"
            f"padding: 6px 14px; min-width: 120px;"
        )
        self._axis_motion_badges.append(badge1)
        state_box.addWidget(badge1)

        card_layout.addLayout(state_box)

        card_layout.addSpacing(16)

        # Right: Limits & Homed state
        status_box = QVBoxLayout()
        status_box.setSpacing(4)

        limits_lbl1 = QLabel("Linear Limits: [ -180.0 mm , +180.0 mm ]")
        limits_lbl1.setStyleSheet(f"color: {_DIM}; font-size: 11px; font-family: 'Consolas', monospace;")
        status_box.addWidget(limits_lbl1)

        homed_row = QHBoxLayout()
        homed_row.setSpacing(6)
        homed_row.addWidget(self._dim_lbl("Zeroed / Homed:"))
        home_ind1 = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        self._axis_homed_indicators.append(home_ind1)
        homed_row.addWidget(home_ind1)

        home_lbl1 = QLabel("Not Homed")
        home_lbl1.setStyleSheet(f"color: {_AMBER}; font-size: 11px; font-weight: bold; background: transparent;")
        self._axis_homed_labels.append(home_lbl1)
        homed_row.addWidget(home_lbl1)
        homed_row.addStretch()

        status_box.addLayout(homed_row)
        card_layout.addLayout(status_box)

        layout.addWidget(card)

        # Speed & Step Hyperparameter Tuning Row
        param_row = QHBoxLayout()
        param_row.setSpacing(10)

        param_row.addWidget(self._dim_lbl("Feed Speed:"))
        speed_spin1 = QDoubleSpinBox()
        speed_spin1.setRange(1.0, 90.0)
        speed_spin1.setValue(20.0)
        speed_spin1.setSingleStep(1.0)
        speed_spin1.setDecimals(1)
        speed_spin1.setSuffix(" mm/s")
        speed_spin1.setFixedWidth(78)
        self._axis_speed_spins.append(speed_spin1)
        param_row.addWidget(speed_spin1)

        speed_slider1 = QSlider(Qt.Horizontal)
        speed_slider1.setRange(1, 90)
        speed_slider1.setValue(20)
        self._axis_speed_sliders.append(speed_slider1)
        param_row.addWidget(speed_slider1, 1)

        speed_lbl1 = QLabel("20 mm/s")
        self._axis_speed_labels.append(speed_lbl1)
        speed_slider1.valueChanged.connect(lambda v: speed_spin1.setValue(float(v)))
        speed_spin1.valueChanged.connect(lambda v: speed_slider1.setValue(int(v)))
        speed_spin1.valueChanged.connect(lambda v: speed_lbl1.setText(f"{v:.0f} mm/s"))

        param_row.addSpacing(10)
        param_row.addWidget(self._dim_lbl("Step Increment:"))
        inc_spin1 = QDoubleSpinBox()
        inc_spin1.setRange(0.05, 50.0)
        inc_spin1.setValue(1.0)
        inc_spin1.setSingleStep(0.1)
        inc_spin1.setDecimals(2)
        inc_spin1.setSuffix(" mm")
        inc_spin1.setFixedWidth(78)
        self._axis_increments.append(inc_spin1)
        param_row.addWidget(inc_spin1)

        layout.addLayout(param_row)

        # Step Presets & Motion Controls
        ctl_row = QHBoxLayout()
        ctl_row.setSpacing(6)
        ctl_row.addWidget(self._dim_lbl("Step Presets:"))

        for label, val in [("0.1 mm", 0.1), ("0.5 mm", 0.5), ("1.0 mm", 1.0), ("5.0 mm", 5.0), ("10.0 mm", 10.0)]:
            btn = QPushButton(label)
            btn.setObjectName("presetBtn")
            btn.clicked.connect(lambda checked=False, st=val: inc_spin1.setValue(st))
            ctl_row.addWidget(btn)

        ctl_row.addSpacing(16)

        # Primary Forward / Backward Buttons
        btn_retract = QPushButton("◀◀  BACKWARD / RETRACT [S]")
        btn_retract.setObjectName("primaryJogBtn")
        btn_retract.setToolTip("Retract needle backward by current step (Keyboard: S or Down Arrow)")
        btn_retract.clicked.connect(self.retract_step)
        ctl_row.addWidget(btn_retract, 1)

        btn_advance = QPushButton("FORWARD / ADVANCE [W]  ▶▶")
        btn_advance.setObjectName("primaryJogBtn")
        btn_advance.setToolTip("Advance needle forward by current step (Keyboard: W or Up Arrow)")
        btn_advance.clicked.connect(self.advance_step)
        ctl_row.addWidget(btn_advance, 1)

        layout.addLayout(ctl_row)

        # Hidden spinbox for API compatibility
        dummy_target1 = QDoubleSpinBox()
        dummy_target1.setVisible(False)
        self._axis_target_spins.append(dummy_target1)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Axis 2: Needle Guide Angle Display (Angular Motion)
    # ------------------------------------------------------------------
    def _build_axis2_display(self) -> None:
        group = QGroupBox("AXIS 2 · NEEDLE GUIDE ANGLE  [ ADJUST LEFT / RIGHT ]")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Big Telemetry Value Card
        card = QFrame()
        card.setStyleSheet(
            f"background-color: {_CARD_BG}; border: 1px solid #20242e; border-radius: 4px; padding: 8px 12px;"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 6, 10, 6)
        card_layout.setSpacing(16)

        # Left: Huge Angle Readout
        ang_box = QVBoxLayout()
        ang_box.setSpacing(2)

        ang_title = QLabel("CURRENT GUIDE ANGLE")
        ang_title.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        ang_box.addWidget(ang_title)

        lbl_pos2 = QLabel("+0.00 °")
        lbl_pos2.setObjectName("valueLabel")
        lbl_pos2.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_pos2.setStyleSheet(
            f"font-family: 'Consolas','Courier New',monospace; font-size: 32px; font-weight: bold;"
            f"color: {_CYAN}; background: transparent; border: none; padding: 0px;"
        )
        self._axis_position_labels.append(lbl_pos2)
        ang_box.addWidget(lbl_pos2)

        card_layout.addLayout(ang_box, stretch=2)

        # Middle: Motion State Badge
        state_box = QVBoxLayout()
        state_box.setSpacing(4)
        state_title = QLabel("DIRECTION")
        state_title.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        state_box.addWidget(state_title)

        badge2 = QLabel("IDLE")
        badge2.setAlignment(Qt.AlignCenter)
        badge2.setStyleSheet(
            f"font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold;"
            f"color: {_DIM}; background-color: #14171d; border: 1px solid #2a2e38; border-radius: 3px;"
            f"padding: 6px 14px; min-width: 120px;"
        )
        self._axis_motion_badges.append(badge2)
        state_box.addWidget(badge2)

        card_layout.addLayout(state_box)

        card_layout.addSpacing(16)

        # Right: Limits & Homed
        status_box = QVBoxLayout()
        status_box.setSpacing(4)

        limits_lbl2 = QLabel("Angle Limits: [ -360.0° , +360.0° ]")
        limits_lbl2.setStyleSheet(f"color: {_DIM}; font-size: 11px; font-family: 'Consolas', monospace;")
        status_box.addWidget(limits_lbl2)

        homed_row2 = QHBoxLayout()
        homed_row2.setSpacing(6)
        homed_row2.addWidget(self._dim_lbl("Zeroed / Homed:"))
        home_ind2 = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        self._axis_homed_indicators.append(home_ind2)
        homed_row2.addWidget(home_ind2)

        home_lbl2 = QLabel("Not Homed")
        home_lbl2.setStyleSheet(f"color: {_AMBER}; font-size: 11px; font-weight: bold; background: transparent;")
        self._axis_homed_labels.append(home_lbl2)
        homed_row2.addWidget(home_lbl2)
        homed_row2.addStretch()

        status_box.addLayout(homed_row2)
        card_layout.addLayout(status_box)

        layout.addWidget(card)

        # Angular Speed & Angle Step Tuning Row
        param_row = QHBoxLayout()
        param_row.setSpacing(10)

        param_row.addWidget(self._dim_lbl("Angle Speed:"))
        speed_spin2 = QDoubleSpinBox()
        speed_spin2.setRange(1.0, 90.0)
        speed_spin2.setValue(25.0)
        speed_spin2.setSingleStep(1.0)
        speed_spin2.setDecimals(1)
        speed_spin2.setSuffix(" °/s")
        speed_spin2.setFixedWidth(78)
        self._axis_speed_spins.append(speed_spin2)
        param_row.addWidget(speed_spin2)

        speed_slider2 = QSlider(Qt.Horizontal)
        speed_slider2.setRange(1, 90)
        speed_slider2.setValue(25)
        self._axis_speed_sliders.append(speed_slider2)
        param_row.addWidget(speed_slider2, 1)

        speed_lbl2 = QLabel("25 °/s")
        self._axis_speed_labels.append(speed_lbl2)
        speed_slider2.valueChanged.connect(lambda v: speed_spin2.setValue(float(v)))
        speed_spin2.valueChanged.connect(lambda v: speed_slider2.setValue(int(v)))
        speed_spin2.valueChanged.connect(lambda v: speed_lbl2.setText(f"{v:.0f} °/s"))

        param_row.addSpacing(10)
        param_row.addWidget(self._dim_lbl("Angle Step:"))
        inc_spin2 = QDoubleSpinBox()
        inc_spin2.setRange(0.1, 180.0)
        inc_spin2.setValue(15.0)
        inc_spin2.setSingleStep(1.0)
        inc_spin2.setDecimals(1)
        inc_spin2.setSuffix(" °")
        inc_spin2.setFixedWidth(78)
        self._axis_increments.append(inc_spin2)
        param_row.addWidget(inc_spin2)

        layout.addLayout(param_row)

        # Angle Presets & Primary Buttons
        ctl_row = QHBoxLayout()
        ctl_row.setSpacing(6)
        ctl_row.addWidget(self._dim_lbl("Angle Presets:"))

        for label, val in [("1°", 1.0), ("5°", 5.0), ("15°", 15.0), ("45°", 45.0), ("90°", 90.0), ("180°", 180.0)]:
            btn = QPushButton(label)
            btn.setObjectName("presetBtn")
            btn.clicked.connect(lambda checked=False, st=val: inc_spin2.setValue(st))
            ctl_row.addWidget(btn)

        ctl_row.addSpacing(16)

        # Primary guide-angle buttons (Clickable or via A/D keys)
        btn_ccw = QPushButton("◀  ANGLE LEFT [A]")
        btn_ccw.setObjectName("primaryJogBtn")
        btn_ccw.setToolTip("Decrease guide angle by the selected step (Keyboard: A or Left Arrow)")
        btn_ccw.clicked.connect(self.angle_left_step)
        ctl_row.addWidget(btn_ccw, 1)

        btn_cw = QPushButton("ANGLE RIGHT [D]  ▶")
        btn_cw.setObjectName("primaryJogBtn")
        btn_cw.setToolTip("Increase guide angle by the selected step (Keyboard: D or Right Arrow)")
        btn_cw.clicked.connect(self.angle_right_step)
        ctl_row.addWidget(btn_cw, 1)

        layout.addLayout(ctl_row)

        dummy_target2 = QDoubleSpinBox()
        dummy_target2.setVisible(False)
        self._axis_target_spins.append(dummy_target2)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Keyboard Shortcuts HUD (Cheat Sheet)
    # ------------------------------------------------------------------
    def _build_keyboard_hud(self) -> None:
        frame = QFrame()
        frame.setStyleSheet(
            "background-color: #0b0d10; border: 1px solid #1f232b; border-radius: 4px; padding: 6px 10px;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("KEYBOARD TELEOPERATION CONTROLS")
        header.setStyleSheet("color: #7a8194; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(6)

        keys_info = [
            ("[ W ] / [ ↑ ]", "Forward / Advance Needle"),
            ("[ S ] / [ ↓ ]", "Backward / Retract Needle"),
            ("[ A ] / [ ← ]", "Decrease guide angle"),
            ("[ D ] / [ → ]", "Increase guide angle"),
            ("[ 1..4 ]", "Speed presets: 1=2, 2=10, 3=25, 4=60 units/s"),
            ("[ + ] / [ - ]", "Increase / Decrease Speed"),
            ("[ M ]", "Toggle Motor Drivers (Enable/Disable)"),
            ("[ H ]", "Home Needle Axes (Zero)"),
            ("[ SPACE ]", "EMERGENCY ALL STOP"),
        ]

        for i, (key, desc) in enumerate(keys_info):
            r = i // 3
            c = (i % 3) * 2

            lbl_k = QLabel(key)
            lbl_k.setStyleSheet(
                "color: #ecf0f8; font-family: 'Consolas', monospace; font-weight: bold; font-size: 11px;"
                "background-color: #171b22; border: 1px solid #2e3542; border-radius: 2px; padding: 1px 4px;"
            )
            grid.addWidget(lbl_k, r, c)

            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("color: #9ba3b4; font-size: 11px; background: transparent;")
            grid.addWidget(lbl_d, r, c + 1)

        layout.addLayout(grid)
        self._main_layout.addWidget(frame)

    # ------------------------------------------------------------------
    # Emergency Stop Section
    # ------------------------------------------------------------------
    def _build_stop_section(self) -> None:
        self._stop_btn = QPushButton("⬛   STOP END-EFFECTOR MOTION   [ SPACE ]   ⬛")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._stop_btn.setMinimumHeight(44)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._main_layout.addWidget(self._stop_btn)

    # ==================================================================
    # Keyboard Teleoperation Handlers
    # ==================================================================
    def advance_step(self) -> None:
        """Advance needle (Axis 1 forward)."""
        self._set_motion_badge(1, "FORWARD ▲", _GREEN)
        self._execute_current_step(1, 1)
        self._idle_timer_axis1.start(450)

    def retract_step(self) -> None:
        """Retract needle (Axis 1 backward)."""
        self._set_motion_badge(1, "BACKWARD ▼", _AMBER)
        self._execute_current_step(1, -1)
        self._idle_timer_axis1.start(450)

    def angle_right_step(self) -> None:
        """Increase the needle-guide angle (Axis 2)."""
        self._set_motion_badge(2, "ANGLE RIGHT ▶", _CYAN)
        self._execute_current_step(2, 1)
        self._idle_timer_axis2.start(450)

    def angle_left_step(self) -> None:
        """Decrease the needle-guide angle (Axis 2)."""
        self._set_motion_badge(2, "ANGLE LEFT ◀", _CYAN)
        self._execute_current_step(2, -1)
        self._idle_timer_axis2.start(450)

    def set_speed_preset(self, preset_idx: int) -> None:
        """Set insertion/angle speed preset."""
        presets = {1: 2.0, 2: 10.0, 3: 25.0, 4: 60.0}
        if preset_idx in presets:
            spd = presets[preset_idx]
            for spin in self._axis_speed_spins:
                spin.setValue(spd)

    def adjust_speed(self, delta: float) -> None:
        """Increase or decrease the selected motion speeds."""
        for spin in self._axis_speed_spins:
            spin.setValue(max(1.0, min(90.0, spin.value() + delta)))

    def toggle_motors(self) -> None:
        """Toggle motor drivers between enabled and disabled."""
        if self._motor_enabled:
            self.disable_requested.emit()
        else:
            self.enable_requested.emit()

    def home_all(self) -> None:
        """Home all axes and re-zero position displays."""
        self._current_positions[1] = 0.0
        self._current_positions[2] = 0.0
        self.update_axis_position(1, 0.0)
        self.update_axis_position(2, 0.0)
        self.home_requested.emit(0)

    def _set_motion_badge(self, axis: int, text: str, color: str) -> None:
        idx = axis - 1
        if 0 <= idx < len(self._axis_motion_badges):
            b = self._axis_motion_badges[idx]
            b.setText(text)
            b.setStyleSheet(
                f"font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold;"
                f"color: {color}; background-color: #14171d; border: 1px solid {color}; border-radius: 3px;"
                f"padding: 6px 14px; min-width: 120px;"
            )

    # ==================================================================
    # Motion Execution Helpers
    # ==================================================================
    def _get_axis_speed(self, axis: int) -> float:
        idx = axis - 1
        if 0 <= idx < len(self._axis_speed_spins):
            return self._axis_speed_spins[idx].value()
        return 20.0

    def _execute_step(self, axis: int, delta_position: float) -> None:
        speed = self._get_axis_speed(axis)
        # Optimistically update the local open-loop position so the display
        # reacts immediately.  This is the commanded position estimate - there
        # is no gyro/encoder to read back from.  Only do it while connected, so
        # an offline panel never shows fake motion.
        if self._connected:
            lo, hi = AXIS_LIMITS.get(axis, (-180.0, 180.0))
            pos = self._current_positions.get(axis, 0.0) + delta_position
            self._current_positions[axis] = max(lo, min(hi, pos))
            self.update_axis_position(axis, self._current_positions[axis])
        self.move_axis_relative.emit(axis, delta_position, speed)

    def _execute_current_step(self, axis: int, direction: int) -> None:
        idx = axis - 1
        if 0 <= idx < len(self._axis_increments):
            step = self._axis_increments[idx].value()
            delta = float(direction) * step
            self._execute_step(axis, delta)

    def _execute_abs_move(self, axis: int, target_position: float) -> None:
        speed = self._get_axis_speed(axis)
        self._current_positions[axis] = target_position
        self.update_axis_position(axis, target_position)
        self.move_axis.emit(axis, target_position, speed)

    # ==================================================================
    # Visual Helpers
    # ==================================================================
    @staticmethod
    def _dim_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: bold; background: transparent;")
        return lbl

    # ==================================================================
    # Slots
    # ==================================================================
    def _on_connect_clicked(self) -> None:
        port = self._port_combo.currentText().strip()
        if port:
            self.connect_requested.emit(port, DEFAULT_BAUD_RATE)

    def _on_disconnect_clicked(self) -> None:
        self.disconnect_requested.emit()

    def _on_axis_jog_pressed(self, axis: int, direction: int) -> None:
        self._execute_current_step(axis, direction)

    def _on_axis_jog_released(self) -> None:
        pass

    # ==================================================================
    # Public API
    # ==================================================================
    def set_connection_status(self, connected: bool) -> None:
        self._connected = connected
        if connected:
            update_status_indicator(self._esp_conn_indicator, COLOR_STATUS_CONNECTED, size=11)
            self._esp_conn_label.setText("CONNECTED")
            self._esp_conn_label.setStyleSheet(f"color: {_GREEN}; font-weight: bold; background: transparent;")
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
            self._port_combo.setEnabled(False)
            self._refresh_btn.setEnabled(False)
        else:
            update_status_indicator(self._esp_conn_indicator, COLOR_STATUS_DISCONNECTED, size=11)
            self._esp_conn_label.setText("OFFLINE")
            self._esp_conn_label.setStyleSheet(f"color: {_RED}; font-weight: bold; background: transparent;")
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._port_combo.setEnabled(True)
            self._refresh_btn.setEnabled(True)

    def set_ports(self, ports: list[str]) -> None:
        current = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)

    def update_axis_position(self, axis: int, position: float) -> None:
        """Update the insertion position or guide angle for an axis."""
        self._current_positions[axis] = position
        list_idx = axis - 1
        if 0 <= list_idx < len(self._axis_position_labels):
            sign_str = "+" if position >= 0 else ""
            unit = "mm" if axis == 1 else "°"
            self._axis_position_labels[list_idx].setText(f"{sign_str}{position:.2f} {unit}")

    def set_axis_homed(self, axis: int, homed: bool) -> None:
        list_idx = axis - 1
        if 0 <= list_idx < len(self._axis_homed_indicators):
            color = COLOR_STATUS_CONNECTED if homed else COLOR_STATUS_DISCONNECTED
            update_status_indicator(self._axis_homed_indicators[list_idx], color, 10)
            text = "Homed" if homed else "Not Homed"
            tc = _GREEN if homed else _AMBER
            self._axis_homed_labels[list_idx].setText(text)
            self._axis_homed_labels[list_idx].setStyleSheet(
                f"color: {tc}; font-size: 11px; font-weight: bold; background: transparent;"
            )

    def set_motor_status(self, enabled: bool) -> None:
        self._motor_enabled = enabled
        if enabled:
            update_status_indicator(self._motor_indicator, COLOR_STATUS_CONNECTED, 10)
            self._motor_status_label.setText("Enabled")
            self._motor_status_label.setStyleSheet(
                f"color: {_GREEN}; font-weight: bold; background: transparent; font-size: 11px;"
            )
            self._enable_btn.setEnabled(False)
            self._disable_btn.setEnabled(True)
        else:
            update_status_indicator(self._motor_indicator, COLOR_STATUS_DISCONNECTED, 10)
            self._motor_status_label.setText("Disabled")
            self._motor_status_label.setStyleSheet(
                f"color: {_RED}; font-weight: bold; background: transparent; font-size: 11px;"
            )
            self._enable_btn.setEnabled(True)
            self._disable_btn.setEnabled(False)

    def set_communication_status(self, status: str, healthy: bool) -> None:
        pass

    def set_watchdog_status(self, status: str, healthy: bool) -> None:
        pass
