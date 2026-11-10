"""
Vision Panel for camera feed display and ML object detection control.

Provides a live video feed display, camera connection controls,
ML detection parameters, and detection result readouts.
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
    COLOR_BG_INPUT, COLOR_TEXT_DIM, COLOR_GROUPBOX_TITLE,
)


class VisionPanel(QWidget):
    """
    Camera and ML vision panel.

    Features:
    - Live camera feed display with aspect-ratio preservation
    - Camera index selection and connection controls
    - ML model status and configuration
    - Detection result readout
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    camera_connect_requested = Signal(int)      # camera index
    camera_disconnect_requested = Signal()
    detection_enabled_changed = Signal(bool)
    confidence_threshold_changed = Signal(float)

    # Minimum feed display size
    MIN_FEED_WIDTH = 640
    MIN_FEED_HEIGHT = 480

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
        self._main_layout.setSpacing(8)
        self._main_layout.setContentsMargins(6, 6, 6, 6)

        self._build_feed_section()
        self._build_camera_controls_section()
        self._build_ml_section()
        self._build_detection_info_section()

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Camera Feed Section
    # ------------------------------------------------------------------
    def _build_feed_section(self) -> None:
        group = QGroupBox("Camera Feed")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        self._feed_label = QLabel()
        self._feed_label.setMinimumSize(self.MIN_FEED_WIDTH, self.MIN_FEED_HEIGHT)
        self._feed_label.setAlignment(Qt.AlignCenter)
        self._feed_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._feed_label.setStyleSheet(
            f"background-color: {COLOR_BG_INPUT}; border: 1px solid #1e3a5f; border-radius: 4px;"
        )
        self._set_placeholder()
        layout.addWidget(self._feed_label)

        self._main_layout.addWidget(group)

    def _set_placeholder(self) -> None:
        """Draw a 'No Camera' placeholder image."""
        w = self.MIN_FEED_WIDTH
        h = self.MIN_FEED_HEIGHT
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor(COLOR_BG_INPUT))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Camera-off icon (simple text placeholder)
        painter.setPen(QColor(COLOR_TEXT_DIM))
        font = QFont("Segoe UI", 28)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "📷  No Camera")

        painter.end()
        self._feed_label.setPixmap(pixmap)

    # ------------------------------------------------------------------
    # Camera Controls Section
    # ------------------------------------------------------------------
    def _build_camera_controls_section(self) -> None:
        group = QGroupBox("Camera Controls")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        # Status indicator
        self._cam_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED)
        self._cam_status_label = QLabel("Disconnected")
        layout.addWidget(self._cam_indicator, 0, 0)
        layout.addWidget(self._cam_status_label, 0, 1, 1, 2)

        # Camera index
        layout.addWidget(QLabel("Camera Index:"), 1, 0)
        self._cam_index_spin = QSpinBox()
        self._cam_index_spin.setRange(0, 10)
        self._cam_index_spin.setValue(0)
        layout.addWidget(self._cam_index_spin, 1, 1, 1, 2)

        # Resolution display
        layout.addWidget(QLabel("Resolution:"), 2, 0)
        self._resolution_label = QLabel("N/A")
        self._resolution_label.setObjectName("valueLabel")
        layout.addWidget(self._resolution_label, 2, 1, 1, 2)

        # FPS display
        layout.addWidget(QLabel("FPS:"), 3, 0)
        self._fps_label = QLabel("0.0")
        self._fps_label.setObjectName("valueLabel")
        layout.addWidget(self._fps_label, 3, 1, 1, 2)

        # Connect / Disconnect
        btn_row = QHBoxLayout()
        self._cam_connect_btn = QPushButton("Connect Camera")
        self._cam_connect_btn.setObjectName("connectButton")
        self._cam_connect_btn.clicked.connect(self._on_cam_connect)

        self._cam_disconnect_btn = QPushButton("Disconnect Camera")
        self._cam_disconnect_btn.setObjectName("disconnectButton")
        self._cam_disconnect_btn.setEnabled(False)
        self._cam_disconnect_btn.clicked.connect(self._on_cam_disconnect)

        btn_row.addWidget(self._cam_connect_btn)
        btn_row.addWidget(self._cam_disconnect_btn)
        layout.addLayout(btn_row, 4, 0, 1, 3)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # ML Detection Section
    # ------------------------------------------------------------------
    def _build_ml_section(self) -> None:
        group = QGroupBox("ML Detection")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        # Model status
        layout.addWidget(QLabel("Model Status:"), 0, 0)
        self._model_indicator = create_status_indicator(COLOR_STATUS_DISCONNECTED, 10)
        layout.addWidget(self._model_indicator, 0, 1)
        self._model_status_label = QLabel("Not Loaded")
        self._model_status_label.setObjectName("valueLabel")
        layout.addWidget(self._model_status_label, 0, 2)

        # Model path
        layout.addWidget(QLabel("Model Path:"), 1, 0)
        self._model_path_label = QLabel("N/A")
        self._model_path_label.setObjectName("valueLabel")
        self._model_path_label.setWordWrap(True)
        layout.addWidget(self._model_path_label, 1, 1, 1, 2)

        # Confidence threshold
        layout.addWidget(QLabel("Confidence (%):"), 2, 0)
        self._conf_slider = QSlider(Qt.Horizontal)
        self._conf_slider.setRange(0, 100)
        self._conf_slider.setValue(35)
        self._conf_slider.setTickInterval(5)
        self._conf_slider.valueChanged.connect(self._on_confidence_changed)
        layout.addWidget(self._conf_slider, 2, 1)

        self._conf_label = QLabel("35%")
        self._conf_label.setMinimumWidth(40)
        layout.addWidget(self._conf_label, 2, 2)

        # Detection count
        layout.addWidget(QLabel("Detections:"), 3, 0)
        self._detection_count_label = QLabel("0")
        self._detection_count_label.setObjectName("valueLabel")
        layout.addWidget(self._detection_count_label, 3, 1, 1, 2)

        # Last detection confidence
        layout.addWidget(QLabel("Last Conf.:"), 4, 0)
        self._last_conf_label = QLabel("N/A")
        self._last_conf_label.setObjectName("valueLabel")
        layout.addWidget(self._last_conf_label, 4, 1, 1, 2)

        # Enable / disable toggle
        self._detection_toggle = QCheckBox("Enable Detection")
        self._detection_toggle.setChecked(False)
        self._detection_toggle.toggled.connect(self._on_detection_toggled)
        layout.addWidget(self._detection_toggle, 5, 0, 1, 3)

        self._main_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Detection Info Section
    # ------------------------------------------------------------------
    def _build_detection_info_section(self) -> None:
        group = QGroupBox("Detection Info")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Detection status text
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        self._detection_status_label = QLabel("Inactive")
        self._detection_status_label.setObjectName("valueLabel")
        status_row.addWidget(self._detection_status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Confidence bar
        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("Confidence:"))
        self._conf_bar = QLabel("")
        self._conf_bar.setObjectName("valueLabel")
        self._conf_bar.setFixedHeight(20)
        self._conf_bar.setMinimumWidth(200)
        self._conf_bar.setStyleSheet(
            f"background-color: {COLOR_BG_INPUT}; border: 1px solid #1e3a5f; border-radius: 3px;"
        )
        conf_row.addWidget(self._conf_bar)
        layout.addLayout(conf_row)

        self._main_layout.addWidget(group)

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
            update_status_indicator(self._cam_indicator, COLOR_STATUS_CONNECTED)
            self._cam_status_label.setText("Connected")
            self._cam_connect_btn.setEnabled(False)
            self._cam_disconnect_btn.setEnabled(True)
            self._cam_index_spin.setEnabled(False)
        else:
            update_status_indicator(self._cam_indicator, COLOR_STATUS_DISCONNECTED)
            self._cam_status_label.setText("Disconnected")
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
        # Choose color based on confidence level
        if pct >= 70:
            bar_color = COLOR_STATUS_CONNECTED
        elif pct >= 40:
            bar_color = COLOR_STATUS_WARNING
        else:
            bar_color = COLOR_STATUS_DISCONNECTED

        self._conf_bar.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {bar_color}, stop:{pct / 100.0} {bar_color}, "
            f"stop:{pct / 100.0 + 0.001} {COLOR_BG_INPUT}, stop:1 {COLOR_BG_INPUT}); "
            f"border: 1px solid #1e3a5f; border-radius: 3px; "
            f"color: white; padding-left: 4px; font-size: 11px;"
        )
        self._conf_bar.setText(f"{pct:.1f}%")
