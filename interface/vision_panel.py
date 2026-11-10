"""
Vision Panel for camera feed display and ML object detection control.

Provides a live video feed display, camera connection controls,
ML detection parameters, and detection result readouts.

Design: secondary panel — unobtrusive, clearly labeled as optional subsystem.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QSpinBox, QSlider, QCheckBox,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QFont

from interface.styles import (
    create_status_indicator, update_status_indicator,
    COLOR_STATUS_CONNECTED, COLOR_STATUS_DISCONNECTED, COLOR_STATUS_WARNING,
    COLOR_BG_INPUT, COLOR_BORDER, COLOR_TEXT_DIM,
)

_GRAY_IDLE = "#4a5060"
_DIM2      = "#3a4050"
_DIM3      = "#2a3040"
_CYAN      = "#4a90d9"
_RED       = "#e63946"
_GREEN     = "#2ecc71"
_AMBER     = "#f0a500"
_TEXT      = "#dde1e9"
_DIM       = "#7a8194"


class VisionPanel(QWidget):
    """
    Camera and ML vision panel.

    Features:
    - Live camera feed display with aspect-ratio preservation
    - Camera index selection and connection controls
    - ML model status and configuration
    - Detection result readout (optional subsystem)
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    camera_connect_requested    = Signal(int)    # camera index
    camera_disconnect_requested = Signal()
    detection_enabled_changed   = Signal(bool)
    confidence_threshold_changed = Signal(float)

    # Minimum feed display size
    MIN_FEED_WIDTH  = 480
    MIN_FEED_HEIGHT = 360

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("visionPanel")
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
        self._main_layout.setSpacing(6)
        self._main_layout.setContentsMargins(6, 6, 6, 6)

        self._build_panel_header()
        self._build_feed_section()
        self._build_camera_controls_section()
        self._build_ml_section()
        self._build_detection_info_section()

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Panel Identity Header
    # ------------------------------------------------------------------
    def _build_panel_header(self) -> None:
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(hdr)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)

        title = QLabel("VISUAL MONITORING")
        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {_DIM}; background: transparent;")
        layout.addWidget(title)

        sub = QLabel("Camera feed & needle detection  ·  Optional subsystem")
        sub.setStyleSheet(f"color: {_GRAY_IDLE}; font-size: 10px; background: transparent;")
        layout.addWidget(sub)

        self._main_layout.addWidget(hdr)

    # ------------------------------------------------------------------
    # Camera Feed Section
    # ------------------------------------------------------------------
    def _build_feed_section(self) -> None:
        group = QGroupBox("CAMERA FEED")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        self._feed_label = QLabel()
        self._feed_label.setMinimumSize(self.MIN_FEED_WIDTH, self.MIN_FEED_HEIGHT)
        self._feed_label.setAlignment(Qt.AlignCenter)
        self._feed_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._feed_label.setStyleSheet(
            f"background-color: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER}; border-radius: 2px;"
        )
        self._set_placeholder()
        layout.addWidget(self._feed_label)

        self._main_layout.addWidget(group)

    def _set_placeholder(self) -> None:
        """Draw a professional 'Camera Offline' placeholder (no emoji)."""
        w = self.MIN_FEED_WIDTH
        h = self.MIN_FEED_HEIGHT
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor(COLOR_BG_INPUT))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        cx = w // 2
        cy = h // 2

        # Line 1 — CAMERA OFFLINE
        font1 = QFont("Segoe UI", 14)
        font1.setBold(False)
        painter.setFont(font1)
        painter.setPen(QColor(_GRAY_IDLE))
        from PySide6.QtCore import QRect
        rect1 = QRect(0, cy - 54, w, 32)
        painter.drawText(rect1, Qt.AlignCenter, "CAMERA OFFLINE")

        # Line 2
        font2 = QFont("Segoe UI", 10)
        painter.setFont(font2)
        painter.setPen(QColor(_DIM2))
        rect2 = QRect(0, cy - 16, w, 24)
        painter.drawText(rect2, Qt.AlignCenter, "Teleoperation remains available")

        # Line 3
        font3 = QFont("Segoe UI", 9)
        painter.setFont(font3)
        painter.setPen(QColor(_DIM3))
        rect3 = QRect(0, cy + 14, w, 24)
        painter.drawText(rect3, Qt.AlignCenter, "Connect a camera to enable visual monitoring")

        painter.end()
        self._feed_label.setPixmap(pixmap)

    # ------------------------------------------------------------------
    # Camera Controls Section
    # ------------------------------------------------------------------
    def _build_camera_controls_section(self) -> None:
        group = QGroupBox("CAMERA CONTROLS")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        # Status indicator row
        self._cam_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, size=11)
        self._cam_status_label = QLabel("Offline")
        self._cam_status_label.setStyleSheet(f"color: {_RED}; font-weight: bold; background: transparent;")
        layout.addWidget(self._cam_indicator, 0, 0)
        layout.addWidget(self._cam_status_label, 0, 1, 1, 2)

        # Camera index
        layout.addWidget(self._dim_lbl("Camera Index:"), 1, 0)
        self._cam_index_spin = QSpinBox()
        self._cam_index_spin.setRange(0, 10)
        self._cam_index_spin.setValue(0)
        layout.addWidget(self._cam_index_spin, 1, 1, 1, 2)

        # Resolution display
        layout.addWidget(self._dim_lbl("Resolution:"), 2, 0)
        self._resolution_label = QLabel("N/A")
        self._resolution_label.setObjectName("valueLabel")
        layout.addWidget(self._resolution_label, 2, 1, 1, 2)

        # FPS display
        layout.addWidget(self._dim_lbl("FPS:"), 3, 0)
        self._fps_label = QLabel("0.0")
        self._fps_label.setObjectName("valueLabel")
        layout.addWidget(self._fps_label, 3, 1, 1, 2)

        # Connect / Disconnect buttons
        btn_row = QHBoxLayout()
        self._cam_connect_btn = QPushButton("Connect Camera")
        self._cam_connect_btn.setObjectName("connectButton")
        self._cam_connect_btn.clicked.connect(self._on_cam_connect)
        btn_row.addWidget(self._cam_connect_btn)

        self._cam_disconnect_btn = QPushButton("Disconnect Camera")
        self._cam_disconnect_btn.setObjectName("disconnectButton")
        self._cam_disconnect_btn.setEnabled(False)
        self._cam_disconnect_btn.clicked.connect(self._on_cam_disconnect)
        btn_row.addWidget(self._cam_disconnect_btn)

        layout.addLayout(btn_row, 4, 0, 1, 3)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # ML Detection Section
    # ------------------------------------------------------------------
    def _build_ml_section(self) -> None:
        group = QGroupBox("NEEDLE DETECTION  ·  Optional")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        # Model status
        layout.addWidget(self._dim_lbl("Model:"), 0, 0)
        self._model_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        layout.addWidget(self._model_indicator, 0, 1)
        self._model_status_label = QLabel("Not Loaded")
        self._model_status_label.setObjectName("valueLabel")
        layout.addWidget(self._model_status_label, 0, 2)

        # Model path
        layout.addWidget(self._dim_lbl("Path:"), 1, 0)
        self._model_path_label = QLabel("N/A")
        self._model_path_label.setObjectName("valueLabel")
        self._model_path_label.setWordWrap(True)
        layout.addWidget(self._model_path_label, 1, 1, 1, 2)

        # Enable detection toggle
        self._detection_toggle = QCheckBox("Enable Detection")
        self._detection_toggle.setChecked(False)
        self._detection_toggle.toggled.connect(self._on_detection_toggled)
        layout.addWidget(self._detection_toggle, 2, 0, 1, 3)

        # Confidence threshold
        layout.addWidget(self._dim_lbl("Confidence:"), 3, 0)
        self._conf_slider = QSlider(Qt.Horizontal)
        self._conf_slider.setRange(0, 100)
        self._conf_slider.setValue(35)
        self._conf_slider.setTickInterval(5)
        self._conf_slider.valueChanged.connect(self._on_confidence_changed)
        layout.addWidget(self._conf_slider, 3, 1)

        self._conf_label = QLabel("35%")
        self._conf_label.setStyleSheet(f"color: {_CYAN}; font-weight: bold; background: transparent;")
        self._conf_label.setMinimumWidth(40)
        layout.addWidget(self._conf_label, 3, 2)

        # Detection count
        layout.addWidget(self._dim_lbl("Detections:"), 4, 0)
        self._detection_count_label = QLabel("0")
        self._detection_count_label.setObjectName("valueLabel")
        layout.addWidget(self._detection_count_label, 4, 1, 1, 2)

        # Last detection confidence
        layout.addWidget(self._dim_lbl("Last Conf.:"), 5, 0)
        self._last_conf_label = QLabel("N/A")
        self._last_conf_label.setObjectName("valueLabel")
        layout.addWidget(self._last_conf_label, 5, 1, 1, 2)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Detection Info Section
    # ------------------------------------------------------------------
    def _build_detection_info_section(self) -> None:
        group = QGroupBox("DETECTION STATUS")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        status_row = QHBoxLayout()
        status_row.addWidget(self._dim_lbl("Status:"))
        self._detection_status_label = QLabel("Inactive")
        self._detection_status_label.setObjectName("valueLabel")
        status_row.addWidget(self._detection_status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        conf_row = QHBoxLayout()
        conf_row.addWidget(self._dim_lbl("Confidence:"))
        self._conf_bar = QLabel("")
        self._conf_bar.setObjectName("valueLabel")
        self._conf_bar.setFixedHeight(18)
        self._conf_bar.setMinimumWidth(160)
        self._conf_bar.setStyleSheet(
            f"background-color: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER}; border-radius: 2px;"
        )
        conf_row.addWidget(self._conf_bar, 1)
        layout.addLayout(conf_row)

        self._main_layout.addWidget(group)

    # ==================================================================
    # Helpers
    # ==================================================================
    @staticmethod
    def _dim_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {_DIM}; font-size: 10px; background: transparent;")
        return lbl

    # ==================================================================
    # Internal Slots
    # ==================================================================
    def _on_cam_connect(self) -> None:
        idx = self._cam_index_spin.value()
        self.camera_connect_requested.emit(idx)

    def _on_cam_disconnect(self) -> None:
        self.camera_disconnect_requested.emit()

    def _on_confidence_changed(self, value: int) -> None:
        self._conf_label.setText(f"{value}%")
        self.confidence_threshold_changed.emit(value / 100.0)

    def _on_detection_toggled(self, checked: bool) -> None:
        self.detection_enabled_changed.emit(checked)

    # ==================================================================
    # Public API
    # ==================================================================
    def update_frame(self, image: QImage) -> None:
        """
        Display a new video frame, maintaining aspect ratio.

        Args:
            image: QImage to display (any format).
        """
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self._feed_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._feed_label.setPixmap(scaled)

    def clear_frame(self) -> None:
        """Reset the feed display to the placeholder."""
        self._set_placeholder()

    def set_camera_status(self, connected: bool) -> None:
        """Update camera connection indicator and button states."""
        if connected:
            update_status_indicator(self._cam_indicator, COLOR_STATUS_CONNECTED, size=11)
            self._cam_status_label.setText("Capturing")
            self._cam_status_label.setStyleSheet(
                f"color: {_GREEN}; font-weight: bold; background: transparent;"
            )
            self._cam_connect_btn.setEnabled(False)
            self._cam_disconnect_btn.setEnabled(True)
            self._cam_index_spin.setEnabled(False)
        else:
            update_status_indicator(self._cam_indicator, COLOR_STATUS_DISCONNECTED, size=11)
            self._cam_status_label.setText("Offline")
            self._cam_status_label.setStyleSheet(
                f"color: {_RED}; font-weight: bold; background: transparent;"
            )
            self._cam_connect_btn.setEnabled(True)
            self._cam_disconnect_btn.setEnabled(False)
            self._cam_index_spin.setEnabled(True)
            self.clear_frame()

    def set_resolution(self, width: int, height: int) -> None:
        """Display the current camera resolution."""
        self._resolution_label.setText(f"{width} × {height}")

    def set_fps(self, fps: float) -> None:
        """Update the live FPS counter."""
        self._fps_label.setText(f"{fps:.1f}")

    def set_model_status(self, status: str, loaded: bool) -> None:
        """
        Update the ML model status indicator.

        Args:
            status: Display string (e.g. 'Loaded', 'Error', 'Not Loaded').
            loaded: True if model is ready.
        """
        if loaded:
            color = COLOR_STATUS_CONNECTED
        elif status.lower() == "error":
            color = COLOR_STATUS_DISCONNECTED
        else:
            color = COLOR_STATUS_WARNING
        update_status_indicator(self._model_indicator, color, 10)
        self._model_status_label.setText(status)

    def set_model_path(self, path: str) -> None:
        """Display the ML model file path."""
        self._model_path_label.setText(path if path else "N/A")

    def set_detection_count(self, count: int) -> None:
        """Update the detection count display."""
        self._detection_count_label.setText(str(count))

    def set_last_confidence(self, confidence: float) -> None:
        """
        Update the last detection confidence display.

        Args:
            confidence: Value between 0.0 and 1.0.
        """
        self._last_conf_label.setText(f"{confidence * 100:.1f}%")

    def set_detection_status(self, status: str) -> None:
        """Update the detection status text (e.g. 'Detecting', 'Inactive')."""
        self._detection_status_label.setText(status)

    def set_confidence_bar(self, confidence: float) -> None:
        """
        Update the visual confidence bar.

        Args:
            confidence: Value between 0.0 and 1.0.
        """
        pct = max(0.0, min(1.0, confidence)) * 100.0

        if pct >= 70:
            bar_color = COLOR_STATUS_CONNECTED
        elif pct >= 40:
            bar_color = COLOR_STATUS_WARNING
        else:
            bar_color = COLOR_STATUS_DISCONNECTED

        stop = pct / 100.0
        stop2 = min(stop + 0.001, 1.0)
        self._conf_bar.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {bar_color}, stop:{stop:.4f} {bar_color}, "
            f"stop:{stop2:.4f} {COLOR_BG_INPUT}, stop:1 {COLOR_BG_INPUT}); "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 2px; "
            f"color: white; padding-left: 4px; font-size: 11px;"
        )
        self._conf_bar.setText(f"{pct:.1f}%")
