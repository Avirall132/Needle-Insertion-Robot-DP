"""
Stylesheet module for the Needle Robot Teleoperation System.

Defines comprehensive QSS dark theme, color constants, and helper functions
for creating a professional industrial robotics workstation appearance.

Design system: near-black, cool-grey, restrained accent palette.
"""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush

# ---------------------------------------------------------------------------
# Canonical Design-System Color Tokens
# ---------------------------------------------------------------------------
_BG_BASE      = "#0e0f11"
_BG_PANEL     = "#141518"
_BG_SECTION   = "#1a1c20"
_BG_INPUT     = "#0c0d0f"
_BG_HEADER    = "#101214"

_BORDER       = "#2a2d35"
_BORDER_MID   = "#363b46"
_BORDER_FOCUS = "#4a90d9"

_TEXT_PRIMARY = "#dde1e9"
_TEXT_DIM     = "#7a8194"
_TEXT_MONO    = "#b8c6e0"
_TEXT_HEADER  = "#ecf0f8"

_GREEN        = "#2ecc71"
_GREEN_DIM    = "#1a7a44"
_AMBER        = "#f0a500"
_AMBER_DIM    = "#5a3c00"
_RED          = "#e63946"
_RED_DIM      = "#5a1020"
_CYAN         = "#4a90d9"
_CYAN_DIM     = "#1a3a5a"
_GRAY_IDLE    = "#4a5060"

_BUTTON_BG      = "#1e2229"
_BUTTON_HOVER   = "#252b35"
_BUTTON_PRESSED = "#181e24"
_BUTTON_DISABLED= "#16181c"

# ---------------------------------------------------------------------------
# Public Color Constants (panel code imports these by name)
# ---------------------------------------------------------------------------
COLOR_BG_DARK              = _BG_BASE
COLOR_BG_PANEL             = _BG_PANEL
COLOR_BG_INPUT             = _BG_INPUT
COLOR_BG_HEADER            = _BG_HEADER

COLOR_ACCENT               = _CYAN
COLOR_ACCENT_HOVER         = "#5a9fea"
COLOR_ACCENT_PRESSED       = "#3a7ac0"

COLOR_ALERT                = _RED
COLOR_ALERT_HOVER          = "#f04050"
COLOR_ALERT_PRESSED        = "#c02030"

COLOR_TEXT                 = _TEXT_PRIMARY
COLOR_TEXT_DIM             = _TEXT_DIM
COLOR_TEXT_DARK            = _GRAY_IDLE

COLOR_BORDER               = _BORDER
COLOR_BORDER_LIGHT         = _BORDER_MID

COLOR_STATUS_CONNECTED     = _GREEN
COLOR_STATUS_DISCONNECTED  = _RED
COLOR_STATUS_WARNING       = _AMBER
COLOR_STATUS_IDLE          = _CYAN
COLOR_STATUS_MOVING        = _AMBER
COLOR_STATUS_STOPPED       = _RED

COLOR_BUTTON_BG            = _BUTTON_BG
COLOR_BUTTON_HOVER         = _BUTTON_HOVER
COLOR_BUTTON_PRESSED       = _BUTTON_PRESSED
COLOR_BUTTON_DISABLED      = _BUTTON_DISABLED

COLOR_GROUPBOX_BORDER      = _BORDER
COLOR_GROUPBOX_TITLE       = _TEXT_DIM

COLOR_SCROLLBAR_BG         = _BG_INPUT
COLOR_SCROLLBAR_HANDLE     = _BORDER
COLOR_SCROLLBAR_HANDLE_HOVER = "#3a4050"

COLOR_TAB_BG               = _BG_PANEL
COLOR_TAB_SELECTED         = _BUTTON_BG
COLOR_TAB_HOVER            = "#1a1e24"

# ---------------------------------------------------------------------------
# Comprehensive QSS Dark Stylesheet
# ---------------------------------------------------------------------------
DARK_STYLESHEET = """
/* =============================== */
/*  Global Application Styling     */
/* =============================== */
QWidget {
    background-color: %(bg_dark)s;
    color: %(text)s;
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 11px;
}

QMainWindow {
    background-color: %(bg_dark)s;
}

/* =============================== */
/*  Labels                         */
/* =============================== */
QLabel {
    color: %(text)s;
    background-color: transparent;
    border: none;
    padding: 0px;
}

QLabel[objectName="valueLabel"] {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: %(text_mono)s;
    background-color: %(bg_input)s;
    border: 1px solid %(border)s;
    border-radius: 2px;
    padding: 2px 6px;
    min-width: 60px;
}

QLabel[objectName="statusDot"] {
    background-color: transparent;
    border: none;
    padding: 0px;
}

/* =============================== */
/*  Push Buttons                   */
/* =============================== */
QPushButton {
    background-color: %(button_bg)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 3px;
    padding: 5px 12px;
    font-weight: bold;
    min-height: 24px;
}

QPushButton:hover {
    background-color: %(button_hover)s;
}

QPushButton:pressed {
    background-color: %(button_pressed)s;
}

QPushButton:disabled {
    background-color: %(button_disabled)s;
    color: #3a4050;
    border: 1px solid #22262e;
}

QPushButton[objectName="stopButton"] {
    background-color: %(alert)s;
    color: white;
    font-size: 14px;
    font-weight: bold;
    border: 2px solid %(alert_hover)s;
    border-radius: 3px;
    padding: 8px 24px;
    min-height: 44px;
}

QPushButton[objectName="stopButton"]:hover {
    background-color: %(alert_hover)s;
}

QPushButton[objectName="stopButton"]:pressed {
    background-color: %(alert_pressed)s;
}

QPushButton[objectName="connectButton"] {
    background-color: #1a4030;
    border: 1px solid %(status_connected)s;
    color: %(text)s;
}

QPushButton[objectName="connectButton"]:hover {
    background-color: #224838;
}

QPushButton[objectName="disconnectButton"] {
    background-color: #401a1a;
    border: 1px solid %(alert)s;
    color: %(text)s;
}

QPushButton[objectName="disconnectButton"]:hover {
    background-color: #522020;
}

QPushButton[objectName="jogButton"] {
    min-width: 36px;
    min-height: 32px;
    font-size: 11px;
    padding: 3px 6px;
    background-color: #1e2535;
    border: 1px solid %(accent)s;
    border-radius: 3px;
    color: %(text)s;
    font-weight: bold;
}

QPushButton[objectName="jogButton"]:hover {
    background-color: #253045;
}

QPushButton[objectName="jogButton"]:pressed {
    background-color: #182030;
}

QPushButton[objectName="primaryJogBtn"] {
    min-height: 42px;
    font-size: 13px;
    font-weight: bold;
    background-color: #1a2d48;
    border: 1px solid #4a90d9;
    border-radius: 4px;
    color: #ecf0f8;
    padding: 6px 14px;
}

QPushButton[objectName="primaryJogBtn"]:hover {
    background-color: #243c60;
    border: 1px solid #66abf0;
}

QPushButton[objectName="primaryJogBtn"]:pressed {
    background-color: #132035;
}

QPushButton[objectName="presetBtn"] {
    min-height: 22px;
    min-width: 44px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: bold;
    background-color: #16181d;
    border: 1px solid #2a2e38;
    border-radius: 3px;
    color: #9ba3b4;
}

QPushButton[objectName="presetBtn"]:hover {
    background-color: #20242e;
    border: 1px solid #4a90d9;
    color: #dde1e9;
}

QPushButton[objectName="presetBtn"]:checked {
    background-color: #1a3a5a;
    border: 1px solid #4a90d9;
    color: #ffffff;
}

QPushButton[objectName="viewBtn"] {
    min-height: 26px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: bold;
    background-color: #16181d;
    border: 1px solid #2a2e38;
    border-radius: 3px;
    color: #9ba3b4;
}

QPushButton[objectName="viewBtn"]:hover {
    background-color: #20242e;
    color: #dde1e9;
    border: 1px solid #363b46;
}

QPushButton[objectName="viewBtn"]:checked {
    background-color: #142840;
    border: 1px solid #4a90d9;
    color: #4a90d9;
}

QPushButton[objectName="focusBtn"] {
    min-height: 28px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: bold;
    background-color: #0d2838;
    border: 1px solid #207a90;
    border-radius: 3px;
    color: #4cc9f0;
}

QPushButton[objectName="focusBtn"]:hover {
    background-color: #133a52;
    border: 1px solid #4cc9f0;
}

QPushButton[objectName="focusBtn"]:checked {
    background-color: #1a4f70;
    border: 1px solid #4cc9f0;
    color: #ffffff;
}

/* =============================== */
/*  Group Boxes                    */
/* =============================== */
QGroupBox {
    background-color: %(bg_section)s;
    border: 1px solid %(border)s;
    border-radius: 3px;
    margin-top: 14px;
    padding: 10px 6px 6px 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 2px 8px;
    color: %(text_dim)s;
    font-size: 11px;
    font-weight: bold;
    background-color: %(bg_section)s;
    border: 1px solid %(border)s;
    border-radius: 2px;
}

/* =============================== */
/*  Spin Boxes                     */
/* =============================== */
QDoubleSpinBox, QSpinBox {
    background-color: %(bg_input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 2px;
    padding: 2px 6px;
    min-height: 22px;
}

QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid %(border_focus)s;
}

QDoubleSpinBox::up-button, QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 16px;
    border-left: 1px solid %(border)s;
    background-color: %(button_bg)s;
    border-top-right-radius: 2px;
}

QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover {
    background-color: %(button_hover)s;
}

QDoubleSpinBox::down-button, QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 16px;
    border-left: 1px solid %(border)s;
    background-color: %(button_bg)s;
    border-bottom-right-radius: 2px;
}

QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background-color: %(button_hover)s;
}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid %(text)s;
}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid %(text)s;
}

/* =============================== */
/*  Combo Boxes                    */
/* =============================== */
QComboBox {
    background-color: %(bg_input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 2px;
    padding: 3px 8px;
    min-height: 22px;
}

QComboBox:hover {
    border: 1px solid %(border_light)s;
}

QComboBox:focus {
    border: 1px solid %(border_focus)s;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 18px;
    border-left: 1px solid %(border)s;
    background-color: %(button_bg)s;
    border-top-right-radius: 2px;
    border-bottom-right-radius: 2px;
}

QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid %(text)s;
}

QComboBox QAbstractItemView {
    background-color: %(bg_input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    selection-background-color: %(accent)s;
    selection-color: white;
}

/* =============================== */
/*  Line Edit                      */
/* =============================== */
QLineEdit {
    background-color: %(bg_input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 2px;
    padding: 3px 6px;
    min-height: 22px;
}

QLineEdit:focus {
    border: 1px solid %(border_focus)s;
}

/* =============================== */
/*  Sliders                        */
/* =============================== */
QSlider::groove:horizontal {
    border: 1px solid %(border)s;
    height: 4px;
    background: %(bg_input)s;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: %(accent)s;
    border: 1px solid %(border_light)s;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: %(accent_hover)s;
}

QSlider::sub-page:horizontal {
    background: #1a3a5a;
    border-radius: 2px;
}

/* =============================== */
/*  Scroll Bars                    */
/* =============================== */
QScrollBar:vertical {
    background: %(bg_input)s;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: %(scrollbar_handle)s;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: %(scrollbar_handle_hover)s;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: %(bg_input)s;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: %(scrollbar_handle)s;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: %(scrollbar_handle_hover)s;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* =============================== */
/*  Scroll Area                    */
/* =============================== */
QScrollArea {
    border: none;
    background-color: %(bg_dark)s;
}

/* =============================== */
/*  Tab Widget                     */
/* =============================== */
QTabWidget::pane {
    border: 1px solid %(border)s;
    background-color: %(bg_panel)s;
    border-radius: 3px;
}

QTabBar::tab {
    background-color: %(tab_bg)s;
    color: %(text_dim)s;
    border: 1px solid %(border)s;
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}

QTabBar::tab:selected {
    background-color: %(tab_selected)s;
    color: %(text)s;
    border-bottom-color: %(tab_selected)s;
}

QTabBar::tab:hover:!selected {
    background-color: %(tab_hover)s;
    color: %(text)s;
}

/* =============================== */
/*  Check Box                      */
/* =============================== */
QCheckBox {
    color: %(text)s;
    spacing: 6px;
    background-color: transparent;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid %(border)s;
    border-radius: 2px;
    background-color: %(bg_input)s;
}

QCheckBox::indicator:checked {
    background-color: %(accent)s;
    border: 1px solid %(accent_hover)s;
}

QCheckBox::indicator:hover {
    border: 1px solid %(border_focus)s;
}

/* =============================== */
/*  Progress Bar                   */
/* =============================== */
QProgressBar {
    border: 1px solid %(border)s;
    border-radius: 3px;
    text-align: center;
    background-color: %(bg_input)s;
    color: %(text)s;
    min-height: 16px;
}

QProgressBar::chunk {
    background-color: %(accent)s;
    border-radius: 2px;
}

/* =============================== */
/*  Tool Tips                      */
/* =============================== */
QToolTip {
    background-color: %(bg_panel)s;
    color: %(text)s;
    border: 1px solid %(border_light)s;
    padding: 4px;
    border-radius: 2px;
}

/* =============================== */
/*  Splitter                       */
/* =============================== */
QSplitter::handle {
    background-color: %(border)s;
}

QSplitter::handle:horizontal {
    width: 1px;
}

QSplitter::handle:vertical {
    height: 1px;
}

/* =============================== */
/*  Status Bar                     */
/* =============================== */
QStatusBar {
    background-color: %(bg_panel)s;
    color: %(text_dim)s;
    border-top: 1px solid %(border_light)s;
}

/* =============================== */
/*  Plain Text Edit (Log Console)  */
/* =============================== */
QPlainTextEdit {
    background-color: %(bg_input)s;
    color: %(text_mono)s;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    border: 1px solid %(border)s;
    border-radius: 2px;
}
""" % {
    "bg_dark":               _BG_BASE,
    "bg_panel":              _BG_PANEL,
    "bg_section":            _BG_SECTION,
    "bg_input":              _BG_INPUT,
    "accent":                _CYAN,
    "accent_hover":          "#5a9fea",
    "alert":                 _RED,
    "alert_hover":           "#f04050",
    "alert_pressed":         "#c02030",
    "text":                  _TEXT_PRIMARY,
    "text_dim":              _TEXT_DIM,
    "text_mono":             _TEXT_MONO,
    "border":                _BORDER,
    "border_light":          _BORDER_MID,
    "border_focus":          _BORDER_FOCUS,
    "button_bg":             _BUTTON_BG,
    "button_hover":          _BUTTON_HOVER,
    "button_pressed":        _BUTTON_PRESSED,
    "button_disabled":       _BUTTON_DISABLED,
    "scrollbar_handle":      _BORDER,
    "scrollbar_handle_hover":"#3a4050",
    "tab_bg":                _BG_PANEL,
    "tab_selected":          _BUTTON_BG,
    "tab_hover":             "#1a1e24",
    "status_connected":      _GREEN,
}


# ---------------------------------------------------------------------------
# Status Indicator Helpers
# ---------------------------------------------------------------------------

def create_status_indicator(color: str, size: int = 12) -> QLabel:
    """
    Create a small colored circle QLabel to use as a status indicator.

    Args:
        color: Hex color string (e.g., '#2ecc71').
        size:  Diameter of the circle in pixels (default 12).

    Returns:
        QLabel with a circular colored pixmap.
    """
    label = QLabel()
    label.setObjectName("statusDot")
    label.setFixedSize(size, size)
    _paint_indicator(label, color, size)
    return label


def update_status_indicator(label: QLabel, color: str, size: int = 12) -> None:
    """
    Update the color of an existing status indicator QLabel.

    Args:
        label: The QLabel created by create_status_indicator.
        color: New hex color string.
        size:  Diameter of the circle in pixels (default 12).
    """
    _paint_indicator(label, color, size)


def _paint_indicator(label: QLabel, color: str, size: int) -> None:
    """Internal helper: paint a solid anti-aliased circle onto *label*."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.NoPen)
    margin = max(1, size // 8)
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()

    label.setPixmap(pixmap)
