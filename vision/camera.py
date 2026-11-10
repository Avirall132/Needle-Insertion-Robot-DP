"""
Camera acquisition module for the needle robot teleoperation system.

Provides thread-safe camera capture using OpenCV with configurable resolution,
FPS, and camera index. Handles disconnection gracefully and releases resources
properly.
"""

import logging
import threading
from typing import Optional, Tuple, Dict, Any, List

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraManager:
    """
    Thread-safe camera manager using OpenCV VideoCapture.

    Supports configurable camera index, resolution, and frame rate.
    All public methods are protected by a reentrant lock for thread safety.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._capture: Optional[cv2.VideoCapture] = None
        self._camera_index: int = 0
        self._requested_width: int = 640
        self._requested_height: int = 480
        self._requested_fps: int = 30
        self._connected: bool = False
        logger.info("CameraManager initialized")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, camera_index: int = 0) -> bool:
        """
        Open a camera device by index.

        Args:
            camera_index: OS camera device index (default 0).

        Returns:
            True if the camera was opened successfully, False otherwise.
        """
        with self._lock:
            # Disconnect any existing camera first
            if self._connected:
                self._release_capture()

            self._camera_index = camera_index
            logger.info("Attempting to connect to camera index %d", camera_index)

            try:
                self._capture = cv2.VideoCapture(camera_index, cv2.CAP_ANY)
                if self._capture is None or not self._capture.isOpened():
                    logger.error("Failed to open camera index %d", camera_index)
                    self._connected = False
                    self._capture = None
                    return False

                # Apply stored resolution and FPS settings
                self._apply_settings()

                self._connected = True
                logger.info(
                    "Connected to camera index %d – resolution %dx%d @ %d FPS",
                    camera_index,
                    int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    int(self._capture.get(cv2.CAP_PROP_FPS)),
                )
                return True

            except Exception as exc:
                logger.exception("Exception while connecting to camera: %s", exc)
                self._connected = False
                self._capture = None
                return False

    def disconnect(self) -> None:
        """Release the camera and mark as disconnected."""
        with self._lock:
            self._release_capture()
            logger.info("Camera disconnected")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_resolution(self, width: int, height: int) -> bool:
        """
        Request a capture resolution. The camera driver may adjust to the
        nearest supported value.

        Args:
            width:  Desired frame width in pixels.
            height: Desired frame height in pixels.

        Returns:
            True if the property was set (actual resolution may differ).
        """
        with self._lock:
            self._requested_width = width
            self._requested_height = height
            if self._capture is not None and self._capture.isOpened():
                self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                actual_w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info(
                    "Resolution requested %dx%d – actual %dx%d",
                    width, height, actual_w, actual_h,
                )
                return True
            return False

    def set_fps(self, fps: int) -> bool:
        """
        Request a capture frame rate.

        Args:
            fps: Desired frames per second.

        Returns:
            True if the property was set (actual FPS may differ).
        """
        with self._lock:
            self._requested_fps = fps
            if self._capture is not None and self._capture.isOpened():
                self._capture.set(cv2.CAP_PROP_FPS, fps)
                actual_fps = int(self._capture.get(cv2.CAP_PROP_FPS))
                logger.info("FPS requested %d – actual %d", fps, actual_fps)
                return True
            return False

    # ------------------------------------------------------------------
    # Frame acquisition
    # ------------------------------------------------------------------

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a single frame from the camera.

        Returns:
            (success, frame) where *frame* is a BGR numpy array on success
            or None on failure. If the camera has become disconnected the
            internal state is updated accordingly.
        """
        with self._lock:
            if not self._connected or self._capture is None:
                return False, None

            try:
                ret, frame = self._capture.read()
                if not ret or frame is None:
                    logger.warning("Failed to read frame – camera may be disconnected")
                    self._connected = False
                    return False, None
                return True, frame

            except Exception as exc:
                logger.exception("Exception during frame read: %s", exc)
                self._connected = False
                return False, None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def resolution(self) -> Tuple[int, int]:
        """Return the current or requested capture resolution (width, height)."""
        return self.camera_info["resolution"]

    @property
    def fps(self) -> int:
        """Return the current or requested capture FPS."""
        return self.camera_info["fps"]

    @property
    def is_connected(self) -> bool:
        """Return True if the camera is currently open and readable."""
        with self._lock:
            if self._capture is not None and not self._capture.isOpened():
                self._connected = False
            return self._connected

    @property
    def camera_info(self) -> Dict[str, Any]:
        """
        Return a dictionary with current camera information.

        Keys:
            connected (bool): Whether the camera is connected.
            camera_index (int): The OS device index.
            resolution (tuple[int, int]): (width, height) in pixels.
            fps (int): Frames per second.
        """
        with self._lock:
            if self._capture is not None and self._capture.isOpened():
                return {
                    "connected": self._connected,
                    "camera_index": self._camera_index,
                    "resolution": (
                        int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    ),
                    "fps": int(self._capture.get(cv2.CAP_PROP_FPS)),
                }
            return {
                "connected": False,
                "camera_index": self._camera_index,
                "resolution": (self._requested_width, self._requested_height),
                "fps": self._requested_fps,
            }

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def detect_available_cameras(max_index: int = 8) -> List[int]:
        """
        Probe camera indices 0..max_index-1 and return those that can be
        opened.

        Args:
            max_index: Upper bound (exclusive) of indices to probe.

        Returns:
            Sorted list of available camera indices.
        """
        available: List[int] = []
        for idx in range(max_index):
            cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
            try:
                if cap is not None and cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        available.append(idx)
            finally:
                if cap is not None:
                    cap.release()
        logger.info("Detected available cameras: %s", available)
        return available

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_settings(self) -> None:
        """Apply stored resolution and FPS to the active capture device."""
        if self._capture is None:
            return
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._requested_width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._requested_height)
        self._capture.set(cv2.CAP_PROP_FPS, self._requested_fps)

    def _release_capture(self) -> None:
        """Release the underlying VideoCapture and reset state."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception as exc:
                logger.warning("Exception releasing camera: %s", exc)
            self._capture = None
        self._connected = False

    # ------------------------------------------------------------------
    # Context manager & destructor
    # ------------------------------------------------------------------

    def __enter__(self) -> "CameraManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def __del__(self) -> None:
        self.disconnect()
