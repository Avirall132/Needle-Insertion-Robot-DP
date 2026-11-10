"""Design tokens and the application stylesheet for the workstation."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
from PySide6.QtWidgets import QLabel

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
_BG_BASE    = "#0b0f14"
_BG_PANEL   = "#111820"
_BG_SECTION = "#17212b"
_BG_INPUT   = "#0a1016"
_BG_HEADER  = "#0c131a"

_BORDER       = "#25313d"
_BORDER_MID   = "#344353"
_BORDER_FOCUS = "#58a6d8"

_TEXT_PRIMARY = "#e6edf3"
_TEXT_DIM     = "#8d9aaa"
_TEXT_MONO    = "#c7d4df"
_TEXT_HEADER  = "#f3f7fa"

_GREEN     = "#42c883"
_AMBER     = "#e6b45c"
_RED       = "#e2636f"
_ACCENT    = "#58a6d8"
_GRAY_IDLE = "#536273"

_BUTTON_BG       = "#1a2732"
_BUTTON_HOVER    = "#233544"
_BUTTON_PRESSED  = "#14202a"
_BUTTON_DISABLED = "#131b23"

# ---------------------------------------------------------------------------
# Public tokens (imported across the interface package)
# ---------------------------------------------------------------------------
COLOR_BG_DARK    = _BG_BASE
COLOR_BG_PANEL   = _BG_PANEL
COLOR_BG_INPUT   = _BG_INPUT
COLOR_BG_HEADER  = _BG_HEADER

COLOR_ACCENT         = _ACCENT
COLOR_ACCENT_HOVER   = "#5a9fea"
COLOR_ACCENT_PRESSED = "#3a7ac0"

COLOR_ALERT         = _RED
COLOR_ALERT_HOVER   = "#e96878"
COLOR_ALERT_PRESSED = "#c83b4c"

COLOR_TEXT      = _TEXT_PRIMARY
COLOR_TEXT_DIM  = _TEXT_DIM
COLOR_TEXT_DARK = _GRAY_IDLE

COLOR_BORDER       = _BORDER
COLOR_BORDER_LIGHT = _BORDER_MID

COLOR_STATUS_CONNECTED    = _GREEN
COLOR_STATUS_DISCONNECTED = _RED
COLOR_STATUS_WARNING      = _AMBER
COLOR_STATUS_IDLE         = _GRAY_IDLE
COLOR_STATUS_MOVING       = _AMBER
COLOR_STATUS_STOPPED      = _RED

COLOR_BUTTON_BG       = _BUTTON_BG
COLOR_BUTTON_HOVER    = _BUTTON_HOVER
COLOR_BUTTON_PRESSED  = _BUTTON_PRESSED
COLOR_BUTTON_DISABLED = _BUTTON_DISABLED

COLOR_GROUPBOX_BORDER = _BORDER
COLOR_GROUPBOX_TITLE  = _TEXT_DIM

COLOR_SCROLLBAR_BG           = _BG_INPUT
COLOR_SCROLLBAR_HANDLE       = "#2c3038"
COLOR_SCROLLBAR_HANDLE_HOVER = "#3a4049"

COLOR_TAB_BG       = _BG_PANEL
COLOR_TAB_SELECTED = _BG_PANEL
COLOR_TAB_HOVER    = _BG_PANEL

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------
DARK_STYLESHEET = """
QWidget {
    background-color: %(bg)s;
    color: %(text)s;
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 12px;
}

QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: %(bg)s;
}

QWidget#endEffectorPanel {
    background-color: %(bg)s;
}

QLabel {
    background: transparent;
    border: none;
    padding: 0;
}

QLabel[objectName="valueLabel"] {
    font-family: "Consolas", "Courier New", monospace;
    color: %(mono)s;
}

QLabel[objectName="statusDot"] {
    background: transparent;
    border: none;
    padding: 0;
}

QFrame#headerBar {
    background-color: %(header)s;
    border: none;
    border-bottom: 1px solid %(border_mid)s;
}

/* Buttons ---------------------------------------------------------------- */
QPushButton {
    background-color: %(btn)s;
    color: %(text)s;
    border: 1px solid %(border_mid)s;
    border-radius: 5px;
    padding: 6px 13px;
    min-height: 26px;
    font-weight: 600;
}

QPushButton:hover   { background-color: %(btn_hover)s; }
QPushButton:pressed { background-color: %(btn_pressed)s; }
QPushButton:focus   { border-color: %(accent)s; }

QPushButton:disabled {
    background-color: %(btn_disabled)s;
    color: #414652;
    border-color: %(border)s;
}

QPushButton[objectName="stopButton"] {
    background-color: %(alert)s;
    color: #ffffff;
    border: 1px solid %(alert_hover)s;
    border-radius: 5px;
    font-weight: 700;
    font-size: 12px;
    padding: 4px 15px;
    min-height: 34px;
}

QPushButton[objectName="stopButton"]:hover   { background-color: %(alert_hover)s; }
QPushButton[objectName="stopButton"]:pressed { background-color: %(alert_pressed)s; }

QPushButton[objectName="connectButton"] {
    background-color: #173126;
    border-color: #367251;
    color: #bcebd0;
}

QPushButton[objectName="disconnectButton"] {
    background-color: #321b21;
    border-color: #7a3944;
    color: #f5c2c8;
}

QPushButton[objectName="jogButton"] {
    min-width: 54px;
    min-height: 38px;
    padding: 0;
    font-size: 18px;
    font-weight: 600;
    background-color: #1a2a37;
}

QPushButton[objectName="jogButton"]:hover {
    background-color: #232b38;
    border-color: %(accent)s;
}

/* Group boxes: a rule and a label, nothing else -------------------------- */
QGroupBox {
    background-color: %(panel)s;
    border: 1px solid %(border)s;
    border-radius: 7px;
    margin-top: 18px;
    padding: 16px 14px 14px 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0;
    top: 0;
    padding: 0;
    color: %(dim)s;
    background: %(panel)s;
    border: none;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
}

/* Inputs ----------------------------------------------------------------- */
QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit {
    background-color: %(input)s;
    color: %(text)s;
    border: 1px solid %(border_mid)s;
    border-radius: 4px;
    padding: 4px 7px;
    min-height: 26px;
    selection-background-color: %(accent)s;
}

QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QLineEdit:focus {
    border-color: %(accent)s;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 18px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid %(dim)s;
}

QComboBox QAbstractItemView {
    background-color: %(input)s;
    color: %(text)s;
    border: 1px solid %(border_mid)s;
    selection-background-color: %(accent)s;
    selection-color: #ffffff;
}

QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {
    width: 14px;
    border: none;
    background: transparent;
}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    width: 0; height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid %(dim)s;
}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    width: 0; height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid %(dim)s;
}

/* Sliders ---------------------------------------------------------------- */
QSlider::groove:horizontal {
    height: 4px;
    background: #2a3946;
    border: none;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 6px;
    background: %(accent)s;
    border: none;
}

QSlider::handle:horizontal:hover { background: %(accent_hover)s; }
QSlider::sub-page:horizontal    { background: #2f4d6d; border-radius: 2px; }

/* Scrollbars ------------------------------------------------------------- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: %(scroll)s;
    min-height: 28px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover { background: %(scroll_hover)s; }

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: %(scroll)s;
    min-width: 28px;
    border-radius: 4px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

/* Tabs ------------------------------------------------------------------- */
QTabWidget::pane { border: none; background: transparent; }

QTabBar::tab {
    background: transparent;
    color: %(dim)s;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 6px 14px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    color: %(text)s;
    border-bottom: 2px solid %(accent)s;
}

QTabBar::tab:hover:!selected { color: %(text)s; }

/* Misc ------------------------------------------------------------------- */
QCheckBox { color: %(text)s; spacing: 7px; background: transparent; }

QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid %(border_mid)s;
    border-radius: 3px;
    background: %(input)s;
}

QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; }

QSplitter::handle { background-color: %(border)s; }
QSplitter::handle:horizontal { width: 1px; }

QStatusBar {
    background-color: %(header)s;
    color: %(dim)s;
    border-top: 1px solid %(border)s;
    padding: 0 10px;
}

QStatusBar::item { border: none; }

QToolTip {
    background-color: %(panel)s;
    color: %(text)s;
    border: 1px solid %(border_mid)s;
    padding: 4px 6px;
}
""" % {
    "bg":            _BG_BASE,
    "panel":         _BG_PANEL,
    "header":        _BG_HEADER,
    "input":         _BG_INPUT,
    "accent":        _ACCENT,
    "accent_hover":  "#5a9fea",
    "alert":         _RED,
    "alert_hover":   "#e96878",
    "alert_pressed": "#c83b4c",
    "text":          _TEXT_PRIMARY,
    "mono":          _TEXT_MONO,
    "dim":           _TEXT_DIM,
    "border":        _BORDER,
    "border_mid":    _BORDER_MID,
    "btn":           _BUTTON_BG,
    "btn_hover":     _BUTTON_HOVER,
    "btn_pressed":   _BUTTON_PRESSED,
    "btn_disabled":  _BUTTON_DISABLED,
    "scroll":        COLOR_SCROLLBAR_HANDLE,
    "scroll_hover":  COLOR_SCROLLBAR_HANDLE_HOVER,
}


# ---------------------------------------------------------------------------
# Status dots
# ---------------------------------------------------------------------------
def create_status_indicator(color: str, size: int = 10) -> QLabel:
    """Create a small filled circle used as a status dot."""
    label = QLabel()
    label.setObjectName("statusDot")
    label.setFixedSize(size, size)
    _paint_indicator(label, color, size)
    return label


def update_status_indicator(label: QLabel, color: str, size: int = 10) -> None:
    """Repaint an existing status dot."""
    _paint_indicator(label, color, size)


def _paint_indicator(label: QLabel, color: str, size: int) -> None:
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
