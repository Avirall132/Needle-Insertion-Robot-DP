"""
QThread-based worker for camera capture and machine-learning inference.

Captures frames from a CameraManager, runs needle detection via a
NeedleDetector, annotates the frame, and emits Qt signals with the results.
Uses a latest-frame strategy (drops stale frames) to prevent backlog.
Converts OpenCV BGR images to RGB QImage for PySide6 display.

This worker does NOT control the robot in any way.
"""

import logging
import time
from typing import Any, List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from vision.camera import CameraManager
from vision.needle_detector import Detection, NeedleDetector, draw_detections

logger = logging.getLogger(__name__)

# Target loop rate
_TARGET_FPS: float = 30.0
_LOOP_INTERVAL: float = 1.0 / _TARGET_FPS


class VisionWorker(QThread):
    """
    Background worker for camera acquisition and needle detection.

    Signals
    -------
    frame_ready(object)
        Emitted with a QImage (RGB888) of the latest annotated frame.
    detection_updated(list)
        Emitted with a list of Detection objects from the latest inference.
    fps_updated(float)
        Emitted with the measured processing FPS.
    camera_status_changed(bool)
        Emitted when the camera connection state changes.
    model_status_changed(str)
        Emitted with the detector's status message when it changes.
    error_occurred(str)
        Emitted when an error is encountered.
    """

    # ---- Qt signals --------------------------------------------------
    frame_ready = Signal(object)
    detection_updated = Signal(list)
    fps_updated = Signal(float)
    camera_status_changed = Signal(bool)
    model_status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        camera_manager: CameraManager,
        needle_detector: NeedleDetector,
        parent: Optional[Any] = None,
    ) -> None:
        """
        Args:
            camera_manager:  A CameraManager instance for frame capture.
            needle_detector: A NeedleDetector instance for inference.
            parent:          Optional QObject parent.
        """
        super().__init__(parent)
        self._camera = camera_manager
        self._detector = needle_detector
        self._running: bool = False

        # Detection toggle (can be disabled to just stream raw frames)
        self._detection_enabled: bool = True

        # State tracking
        self._prev_camera_connected: Optional[bool] = None
        self._prev_model_status: Optional[str] = None

        # FPS calculation
        self._fps_window_size: int = 30
        self._frame_times: List[float] = []

        logger.info("VisionWorker initialized")

    # ------------------------------------------------------------------
    # Public thread-safe methods
    # ------------------------------------------------------------------

    def set_detection_enabled(self, enabled: bool) -> None:
        """Enable or disable ML detection (still streams camera feed)."""
        self._detection_enabled = enabled
        logger.info("Detection %s", "enabled" if enabled else "disabled")

    def request_stop(self) -> None:
        """Request the worker thread to stop its run loop."""
        self._running = False

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Main worker loop.

        1. Capture a frame (latest-frame strategy).
        2. Optionally run detection.
        3. Annotate the frame with detections.
        4. Convert BGR → RGB QImage and emit.
        5. Calculate and emit FPS.
        """
        self._running = True
        self._frame_times.clear()
        logger.info("VisionWorker thread started")

        while self._running:
            loop_start = time.monotonic()

            # ---- Check and emit camera status changes ----------------
            cam_connected = self._camera.is_connected
            if cam_connected != self._prev_camera_connected:
                self._prev_camera_connected = cam_connected
                self.camera_status_changed.emit(cam_connected)

            # ---- Check and emit model status changes -----------------
            model_status = self._detector.status_message
            if model_status != self._prev_model_status:
                self._prev_model_status = model_status
                self.model_status_changed.emit(model_status)

            # ---- Capture frame (latest-frame strategy) ---------------
            if not cam_connected:
                # Camera not connected – sleep briefly and retry
                time.sleep(0.1)
                continue

            success, frame = self._camera.read_frame()
            if not success or frame is None:
                # The camera may have disconnected mid-loop
                time.sleep(0.05)
                continue

            # Drop any stale buffered frames by reading until the most
            # recent one.  Cap at 5 reads to avoid an infinite loop on a
            # fast camera.
            for _ in range(5):
                ret, new_frame = self._camera.read_frame()
                if not ret or new_frame is None:
                    break
                frame = new_frame

            # ---- Run detection ---------------------------------------
            detections: List[Detection] = []
            if self._detection_enabled and self._detector.is_loaded:
                try:
                    detections = self._detector.detect(frame)
                except Exception as exc:
                    logger.exception("Detection error: %s", exc)
                    self.error_occurred.emit(f"Detection error: {exc}")

            # Emit detections regardless (empty list is valid)
            self.detection_updated.emit(detections)

            # ---- Annotate frame --------------------------------------
            if detections:
                try:
                    frame = draw_detections(frame, detections)
                except Exception as exc:
                    logger.warning("Annotation error: %s", exc)

            # ---- Convert BGR → RGB QImage and emit -------------------
            try:
                qimage = self._bgr_to_qimage(frame)
                self.frame_ready.emit(qimage)
            except Exception as exc:
                logger.exception("Frame conversion error: %s", exc)
                self.error_occurred.emit(f"Frame conversion error: {exc}")

            # ---- Calculate FPS ---------------------------------------
            now = time.monotonic()
            self._frame_times.append(now)
            # Trim window
            if len(self._frame_times) > self._fps_window_size:
                self._frame_times = self._frame_times[-self._fps_window_size:]
            if len(self._frame_times) >= 2:
                dt = self._frame_times[-1] - self._frame_times[0]
                if dt > 0:
                    fps = (len(self._frame_times) - 1) / dt
                    self.fps_updated.emit(round(fps, 1))

            # ---- Maintain target frame rate --------------------------
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.0, _LOOP_INTERVAL - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

        # ------------------------------------------------------------------
        # Cleanup
        # ------------------------------------------------------------------
        logger.info("VisionWorker stopping – releasing camera")
        try:
            self._camera.disconnect()
        except Exception as exc:
            logger.warning("Error releasing camera during shutdown: %s", exc)

        self.camera_status_changed.emit(False)
        logger.info("VisionWorker thread stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _bgr_to_qimage(frame: np.ndarray) -> QImage:
        """
        Convert an OpenCV BGR frame to a PySide6 QImage in RGB888 format.

        A deep copy of the pixel data is made so the QImage outlives the
        numpy array.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        # QImage does not own the data buffer, so we must keep a reference
        # or copy.  Using .copy() on the QImage ensures it owns its data.
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return qimg.copy()
