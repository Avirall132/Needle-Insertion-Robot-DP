"""
Stylesheet module for the Needle Robot Teleoperation System.

Defines comprehensive QSS dark theme, color constants, and helper functions
for creating a professional industrial robotics workstation appearance.
"""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush

# ---------------------------------------------------------------------------
# Color Constants
# ---------------------------------------------------------------------------
COLOR_BG_DARK = "#1a1a2e"
COLOR_BG_PANEL = "#16213e"
COLOR_BG_INPUT = "#0d1b2a"
COLOR_BG_HEADER = "#0f3460"
COLOR_ACCENT = "#0f3460"
COLOR_ACCENT_HOVER = "#1a4a7a"
COLOR_ACCENT_PRESSED = "#0a2540"
COLOR_ALERT = "#e94560"
COLOR_ALERT_HOVER = "#ff5a75"
COLOR_ALERT_PRESSED = "#c03050"
COLOR_TEXT = "#eeeeee"
COLOR_TEXT_DIM = "#aaaaaa"
COLOR_TEXT_DARK = "#888888"
COLOR_BORDER = "#1e3a5f"
COLOR_BORDER_LIGHT = "#2a4a6f"

COLOR_STATUS_CONNECTED = "#00ff88"
COLOR_STATUS_DISCONNECTED = "#ff4444"
COLOR_STATUS_WARNING = "#ffaa00"
COLOR_STATUS_IDLE = "#00bfff"
COLOR_STATUS_MOVING = "#00ff88"
COLOR_STATUS_STOPPED = "#ff4444"

COLOR_BUTTON_BG = "#0f3460"
COLOR_BUTTON_HOVER = "#1a4a7a"
COLOR_BUTTON_PRESSED = "#0a2540"
COLOR_BUTTON_DISABLED = "#333355"

COLOR_GROUPBOX_BORDER = "#1e3a5f"
COLOR_GROUPBOX_TITLE = "#4da6ff"

COLOR_SCROLLBAR_BG = "#0d1b2a"
COLOR_SCROLLBAR_HANDLE = "#1e3a5f"
COLOR_SCROLLBAR_HANDLE_HOVER = "#2a5a8f"

COLOR_TAB_BG = "#16213e"
COLOR_TAB_SELECTED = "#0f3460"
COLOR_TAB_HOVER = "#1a3a5e"

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
    font-family: "Segoe UI", "Roboto", "Arial", sans-serif;
    font-size: 12px;
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
    padding: 1px;
}

QLabel[objectName="headerLabel"] {
    font-size: 16px;
    font-weight: bold;
    color: %(groupbox_title)s;
    padding: 4px 0px;
}

QLabel[objectName="valueLabel"] {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: %(text)s;
    background-color: %(bg_input)s;
    border: 1px solid %(border)s;
    border-radius: 3px;
    padding: 3px 6px;
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
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: bold;
    min-height: 24px;
}

QPushButton:hover {
    background-color: %(button_hover)s;
    border: 1px solid %(border_light)s;
}

QPushButton:pressed {
    background-color: %(button_pressed)s;
}

QPushButton:disabled {
    background-color: %(button_disabled)s;
    color: #666666;
    border: 1px solid #444444;
}

QPushButton[objectName="stopButton"] {
    background-color: %(alert)s;
    color: white;
    font-size: 18px;
    font-weight: bold;
    border: 2px solid #ff6680;
    border-radius: 8px;
    padding: 12px 24px;
    min-height: 50px;
}

QPushButton[objectName="stopButton"]:hover {
    background-color: %(alert_hover)s;
    border: 2px solid #ff8899;
}

QPushButton[objectName="stopButton"]:pressed {
    background-color: %(alert_pressed)s;
}

QPushButton[objectName="connectButton"] {
    background-color: #1a6630;
    border: 1px solid #22884a;
}

QPushButton[objectName="connectButton"]:hover {
    background-color: #228840;
}

QPushButton[objectName="disconnectButton"] {
    background-color: #663030;
    border: 1px solid #884040;
}

QPushButton[objectName="disconnectButton"]:hover {
    background-color: #884040;
}

QPushButton[objectName="jogButton"] {
    min-width: 32px;
    max-width: 40px;
    min-height: 28px;
    padding: 4px 8px;
    font-size: 14px;
    font-weight: bold;
    border-radius: 4px;
}

/* =============================== */
/*  Group Boxes                    */
/* =============================== */
QGroupBox {
    background-color: %(bg_panel)s;
    border: 1px solid %(groupbox_border)s;
    border-radius: 6px;
    margin-top: 14px;
    padding: 12px 8px 8px 8px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: %(groupbox_title)s;
    font-size: 12px;
    font-weight: bold;
    background-color: %(bg_panel)s;
    border: 1px solid %(groupbox_border)s;
    border-radius: 4px;
    left: 10px;
}

/* =============================== */
/*  Spin Boxes                     */
/* =============================== */
QDoubleSpinBox, QSpinBox {
    background-color: %(bg_input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 3px 6px;
    min-height: 22px;
}

QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid %(groupbox_title)s;
}

QDoubleSpinBox::up-button, QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid %(border)s;
    background-color: %(button_bg)s;
    border-top-right-radius: 4px;
}

QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover {
    background-color: %(button_hover)s;
}

QDoubleSpinBox::down-button, QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid %(border)s;
    background-color: %(button_bg)s;
    border-bottom-right-radius: 4px;
}

QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background-color: %(button_hover)s;
}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid %(text)s;
}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid %(text)s;
}

/* =============================== */
/*  Combo Boxes                    */
/* =============================== */
QComboBox {
    background-color: %(bg_input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}

QComboBox:hover {
    border: 1px solid %(border_light)s;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border-left: 1px solid %(border)s;
    background-color: %(button_bg)s;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}

QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid %(text)s;
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
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}

QLineEdit:focus {
    border: 1px solid %(groupbox_title)s;
}

/* =============================== */
/*  Sliders                        */
/* =============================== */
QSlider::groove:horizontal {
    border: 1px solid %(border)s;
    height: 6px;
    background: %(bg_input)s;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: %(groupbox_title)s;
    border: 1px solid %(border_light)s;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #66bbff;
}

QSlider::sub-page:horizontal {
    background: %(accent)s;
    border-radius: 3px;
}

/* =============================== */
/*  Scroll Bars                    */
/* =============================== */
QScrollBar:vertical {
    background: %(scrollbar_bg)s;
    width: 12px;
    margin: 0;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: %(scrollbar_handle)s;
    min-height: 30px;
    border-radius: 6px;
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
    background: %(scrollbar_bg)s;
    height: 12px;
    margin: 0;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: %(scrollbar_handle)s;
    min-width: 30px;
    border-radius: 6px;
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
    border-radius: 4px;
}

QTabBar::tab {
    background-color: %(tab_bg)s;
    color: %(text_dim)s;
    border: 1px solid %(border)s;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: %(tab_selected)s;
    color: white;
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
    spacing: 8px;
    background-color: transparent;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid %(border)s;
    border-radius: 3px;
    background-color: %(bg_input)s;
}

QCheckBox::indicator:checked {
    background-color: %(accent)s;
    border: 1px solid %(groupbox_title)s;
}

QCheckBox::indicator:hover {
    border: 1px solid %(groupbox_title)s;
}

/* =============================== */
/*  Progress Bar                   */
/* =============================== */
QProgressBar {
    border: 1px solid %(border)s;
    border-radius: 4px;
    text-align: center;
    background-color: %(bg_input)s;
    color: %(text)s;
    min-height: 18px;
}

QProgressBar::chunk {
    background-color: %(accent)s;
    border-radius: 3px;
}

/* =============================== */
/*  Tool Tips                      */
/* =============================== */
QToolTip {
    background-color: %(bg_panel)s;
    color: %(text)s;
    border: 1px solid %(border_light)s;
    padding: 4px;
    border-radius: 3px;
}

/* =============================== */
/*  Splitter                       */
/* =============================== */
QSplitter::handle {
    background-color: %(border)s;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* =============================== */
/*  Status Bar                     */
/* =============================== */
QStatusBar {
    background-color: %(bg_panel)s;
    color: %(text_dim)s;
    border-top: 1px solid %(border)s;
}
""" % {
    "bg_dark": COLOR_BG_DARK,
    "bg_panel": COLOR_BG_PANEL,
    "bg_input": COLOR_BG_INPUT,
    "accent": COLOR_ACCENT,
    "accent_hover": COLOR_ACCENT_HOVER,
    "alert": COLOR_ALERT,
    "alert_hover": COLOR_ALERT_HOVER,
    "alert_pressed": COLOR_ALERT_PRESSED,
    "text": COLOR_TEXT,
    "text_dim": COLOR_TEXT_DIM,
    "border": COLOR_BORDER,
    "border_light": COLOR_BORDER_LIGHT,
    "button_bg": COLOR_BUTTON_BG,
    "button_hover": COLOR_BUTTON_HOVER,
    "button_pressed": COLOR_BUTTON_PRESSED,
    "button_disabled": COLOR_BUTTON_DISABLED,
    "groupbox_border": COLOR_GROUPBOX_BORDER,
    "groupbox_title": COLOR_GROUPBOX_TITLE,
    "scrollbar_bg": COLOR_SCROLLBAR_BG,
    "scrollbar_handle": COLOR_SCROLLBAR_HANDLE,
    "scrollbar_handle_hover": COLOR_SCROLLBAR_HANDLE_HOVER,
    "tab_bg": COLOR_TAB_BG,
    "tab_selected": COLOR_TAB_SELECTED,
    "tab_hover": COLOR_TAB_HOVER,
}


def create_status_indicator(color: str, size: int = 12) -> QLabel:
    """
    Create a small colored circle QLabel to use as a status indicator.

    Args:
        color: Hex color string (e.g., '#00ff88').
        size: Diameter of the circle in pixels (default 12).

    Returns:
        QLabel with a circular colored pixmap.
    """
    label = QLabel()
    label.setObjectName("statusDot")
    label.setFixedSize(size, size)

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()

    label.setPixmap(pixmap)
    return label


def update_status_indicator(label: QLabel, color: str, size: int = 12) -> None:
    """
    Update the color of an existing status indicator QLabel.

    Args:
        label: The QLabel created by create_status_indicator.
        color: New hex color string.
        size: Diameter of the circle in pixels (default 12).
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()

    label.setPixmap(pixmap)
