"""
Needle detection module for the needle robot teleoperation system.

Provides an abstract NeedleDetector interface with concrete implementations
for ONNX Runtime, Ultralytics YOLO, and a fallback mock detector. A factory
function auto-selects the right backend based on the model file extension.

IMPORTANT: The detection pipeline is purely informational — it does NOT
control the robot in any way.
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ======================================================================
# Data structures
# ======================================================================

@dataclass
class Detection:
    """A single object detection result."""

    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) in pixels
    confidence: float                          # 0.0 – 1.0
    class_name: str = "needle"
    mask: Optional[np.ndarray] = field(default=None, repr=False)

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.bbox[0] + self.bbox[2]) / 2.0,
            (self.bbox[1] + self.bbox[3]) / 2.0,
        )


# ======================================================================
# Abstract base class
# ======================================================================

class NeedleDetector(ABC):
    """Abstract interface for all needle detector backends."""

    def __init__(self) -> None:
        self._loaded: bool = False
        self._model_path: Optional[str] = None
        self._status_message: str = "No model loaded"

    # ---- public API --------------------------------------------------

    @abstractmethod
    def load_model(self, path: str) -> bool:
        """
        Load a detection model from *path*.

        Returns:
            True on success; False on any error.
        """
        ...

    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a BGR frame.

        Returns:
            A (possibly empty) list of Detection objects.
        """
        ...

    # ---- properties --------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """True if a model has been loaded successfully."""
        return self._loaded

    @property
    def status_message(self) -> str:
        """Human-readable status string."""
        return self._status_message


# ======================================================================
# ONNX Runtime detector
# ======================================================================

class ONNXDetector(NeedleDetector):
    """Needle detector backed by ONNX Runtime inference."""

    def __init__(self) -> None:
        super().__init__()
        self._session = None
        self._input_name: Optional[str] = None
        self._input_shape: Optional[Tuple[int, ...]] = None
        self._ort_available: bool = False

        try:
            import onnxruntime  # noqa: F401
            self._ort_available = True
        except ImportError:
            self._status_message = (
                "onnxruntime is not installed. "
                "Install it with: pip install onnxruntime"
            )
            logger.warning(self._status_message)

    # ---- public API --------------------------------------------------

    def load_model(self, path: str) -> bool:
        if not self._ort_available:
            logger.error("Cannot load ONNX model – onnxruntime not installed")
            return False

        if not os.path.isfile(path):
            self._status_message = f"Model file not found: {path}"
            logger.error(self._status_message)
            return False

        try:
            import onnxruntime as ort

            self._session = ort.InferenceSession(
                path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            meta = self._session.get_inputs()[0]
            self._input_name = meta.name
            self._input_shape = tuple(meta.shape)  # e.g. (1, 3, 640, 640)
            self._model_path = path
            self._loaded = True
            self._status_message = f"ONNX model loaded: {os.path.basename(path)}"
            logger.info(self._status_message)
            return True

        except Exception as exc:
            self._loaded = False
            self._session = None
            self._status_message = f"Failed to load ONNX model: {exc}"
            logger.exception(self._status_message)
            return False

    def detect(self, frame: np.ndarray) -> List[Detection]:
        if not self._loaded or self._session is None:
            return []

        try:
            # Determine model input height/width from shape
            # Expected shapes: (1, 3, H, W) or (batch, 3, H, W)
            if self._input_shape is not None and len(self._input_shape) == 4:
                # Shape entries may be strings ('batch') or ints
                h = self._input_shape[2] if isinstance(self._input_shape[2], int) else 640
                w = self._input_shape[3] if isinstance(self._input_shape[3], int) else 640
            else:
                h, w = 640, 640

            img_h, img_w = frame.shape[:2]

            # Pre-process: resize, BGR→RGB, HWC→CHW, normalise, add batch dim
            blob = cv2.resize(frame, (w, h))
            blob = cv2.cvtColor(blob, cv2.COLOR_BGR2RGB)
            blob = blob.astype(np.float32) / 255.0
            blob = np.transpose(blob, (2, 0, 1))  # CHW
            blob = np.expand_dims(blob, axis=0)     # NCHW

            outputs = self._session.run(None, {self._input_name: blob})

            detections = self._parse_onnx_output(outputs, img_w, img_h, w, h)
            return detections

        except Exception as exc:
            logger.exception("ONNX inference failed: %s", exc)
            return []

    # ---- internal helpers --------------------------------------------

    @staticmethod
    def _parse_onnx_output(
        outputs: list,
        img_w: int,
        img_h: int,
        model_w: int,
        model_h: int,
        conf_threshold: float = 0.25,
    ) -> List[Detection]:
        """
        Parse raw ONNX output into Detection objects.

        Supports the common YOLO-style output tensor of shape
        (1, N, 5+C) or transposed (1, 5+C, N).
        """
        detections: List[Detection] = []
        if not outputs:
            return detections

        preds = np.array(outputs[0])

        # Flatten batch dimension if present
        if preds.ndim == 3:
            preds = preds[0]

        # Transpose so rows are detections: shape (N, 5+C)
        if preds.ndim == 2 and preds.shape[0] < preds.shape[1]:
            preds = preds.T

        if preds.ndim != 2 or preds.shape[1] < 5:
            return detections

        scale_x = img_w / model_w
        scale_y = img_h / model_h

        for row in preds:
            # row layout: cx, cy, w, h, conf (or cx, cy, w, h, cls_scores…)
            cx, cy, bw, bh = row[:4]

            if preds.shape[1] == 5:
                conf = float(row[4])
                class_id = 0
            else:
                class_scores = row[4:]
                class_id = int(np.argmax(class_scores))
                conf = float(class_scores[class_id])

            if conf < conf_threshold:
                continue

            x1 = (cx - bw / 2) * scale_x
            y1 = (cy - bh / 2) * scale_y
            x2 = (cx + bw / 2) * scale_x
            y2 = (cy + bh / 2) * scale_y

            # Clamp to image bounds
            x1 = max(0.0, min(float(x1), float(img_w)))
            y1 = max(0.0, min(float(y1), float(img_h)))
            x2 = max(0.0, min(float(x2), float(img_w)))
            y2 = max(0.0, min(float(y2), float(img_h)))

            detections.append(
                Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    class_name=f"class_{class_id}",
                )
            )

        return detections


# ======================================================================
# Ultralytics YOLO detector
# ======================================================================

class YOLODetector(NeedleDetector):
    """Needle detector backed by Ultralytics YOLO."""

    def __init__(self) -> None:
        super().__init__()
        self._model = None
        self._ultralytics_available: bool = False

        try:
            import ultralytics  # noqa: F401
            self._ultralytics_available = True
        except ImportError:
            self._status_message = (
                "ultralytics is not installed. "
                "Install it with: pip install ultralytics"
            )
            logger.warning(self._status_message)

    # ---- public API --------------------------------------------------

    def load_model(self, path: str) -> bool:
        if not self._ultralytics_available:
            logger.error("Cannot load YOLO model – ultralytics not installed")
            return False

        if not os.path.isfile(path):
            self._status_message = f"Model file not found: {path}"
            logger.error(self._status_message)
            return False

        try:
            from ultralytics import YOLO

            self._model = YOLO(path)
            self._model_path = path
            self._loaded = True
            self._status_message = f"YOLO model loaded: {os.path.basename(path)}"
            logger.info(self._status_message)
            return True

        except Exception as exc:
            self._loaded = False
            self._model = None
            self._status_message = f"Failed to load YOLO model: {exc}"
            logger.exception(self._status_message)
            return False

    def detect(self, frame: np.ndarray) -> List[Detection]:
        if not self._loaded or self._model is None:
            return []

        try:
            results = self._model(frame, verbose=False)
            detections: List[Detection] = []

            for result in results:
                if result.boxes is None:
                    continue

                boxes = result.boxes
                for i in range(len(boxes)):
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())

                    # Resolve class name from model metadata
                    if (
                        hasattr(result, "names")
                        and result.names
                        and cls_id in result.names
                    ):
                        class_name = result.names[cls_id]
                    else:
                        class_name = f"class_{cls_id}"

                    # Optional instance segmentation mask
                    mask_arr: Optional[np.ndarray] = None
                    if result.masks is not None and i < len(result.masks.data):
                        mask_arr = result.masks.data[i].cpu().numpy()

                    detections.append(
                        Detection(
                            bbox=(
                                float(xyxy[0]),
                                float(xyxy[1]),
                                float(xyxy[2]),
                                float(xyxy[3]),
                            ),
                            confidence=conf,
                            class_name=class_name,
                            mask=mask_arr,
                        )
                    )

            return detections

        except Exception as exc:
            logger.exception("YOLO inference failed: %s", exc)
            return []


# ======================================================================
# Mock detector (fallback)
# ======================================================================

class MockDetector(NeedleDetector):
    """
    A no-op detector that always returns an empty detection list.

    Useful as a fallback when no real model is available.
    """

    def __init__(self) -> None:
        super().__init__()
        self._status_message = "Model not loaded - using mock detector"
        logger.info(self._status_message)

    def load_model(self, path: str) -> bool:
        self._status_message = "Model not loaded - using mock detector"
        logger.info("MockDetector.load_model called with '%s' – ignoring", path)
        return False

    def detect(self, frame: np.ndarray) -> List[Detection]:
        return []


# ======================================================================
# Factory function
# ======================================================================

def create_detector(model_path: Optional[str] = None) -> NeedleDetector:
    """
    Create the appropriate NeedleDetector subclass based on the model file
    extension.

    Supported extensions:
        .onnx  -> ONNXDetector
        .pt    -> YOLODetector
        None / other -> MockDetector

    Args:
        model_path: Path to the model file, or None for the mock backend.

    Returns:
        An initialised NeedleDetector (model loaded if path was valid).
    """
    if model_path is None:
        logger.info("No model path provided – using MockDetector")
        return MockDetector()

    ext = os.path.splitext(model_path)[1].lower()

    if ext == ".onnx":
        detector = ONNXDetector()
    elif ext == ".pt":
        detector = YOLODetector()
    else:
        logger.warning("Unrecognised model extension '%s' – using MockDetector", ext)
        return MockDetector()

    success = detector.load_model(model_path)
    if not success:
        logger.warning(
            "Failed to load model '%s' – falling back to MockDetector", model_path
        )
        # Return the detector anyway so the caller can inspect status_message
        # but also provide a usable (mock) detector.
        if not detector.is_loaded:
            return detector  # still usable – detect() returns []

    return detector


# ======================================================================
# Drawing utility
# ======================================================================

# Colour palette for up to 20 classes (BGR)
_COLOURS: List[Tuple[int, int, int]] = [
    (0, 255, 0),
    (0, 0, 255),
    (255, 0, 0),
    (255, 255, 0),
    (0, 255, 255),
    (255, 0, 255),
    (128, 255, 0),
    (0, 128, 255),
    (255, 128, 0),
    (128, 0, 255),
    (0, 255, 128),
    (255, 0, 128),
    (64, 255, 64),
    (64, 64, 255),
    (255, 64, 64),
    (192, 192, 0),
    (0, 192, 192),
    (192, 0, 192),
    (128, 128, 255),
    (255, 128, 128),
]


def draw_detections(
    frame: np.ndarray,
    detections: List[Detection],
    thickness: int = 2,
    font_scale: float = 0.6,
) -> np.ndarray:
    """
    Draw bounding boxes, labels, and confidence scores on *frame*.

    Args:
        frame:      BGR image (modified in-place and returned).
        detections: List of Detection objects.
        thickness:  Line thickness for bounding boxes.
        font_scale: Font scale for label text.

    Returns:
        The annotated image (same reference as *frame*).
    """
    annotated = frame.copy()

    for idx, det in enumerate(detections):
        colour = _COLOURS[idx % len(_COLOURS)]
        x1, y1, x2, y2 = (
            int(det.bbox[0]),
            int(det.bbox[1]),
            int(det.bbox[2]),
            int(det.bbox[3]),
        )

        # Bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, thickness)

        # Label background
        label = f"{det.class_name} {det.confidence:.2f}"
        (tw, th), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
        )
        cv2.rectangle(
            annotated,
            (x1, y1 - th - baseline - 4),
            (x1 + tw + 4, y1),
            colour,
            cv2.FILLED,
        )

        # Label text
        cv2.putText(
            annotated,
            label,
            (x1 + 2, y1 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

        # Optional mask overlay
        if det.mask is not None:
            try:
                mask_resized = cv2.resize(
                    det.mask.astype(np.float32),
                    (annotated.shape[1], annotated.shape[0]),
                )
                mask_bool = mask_resized > 0.5
                overlay = annotated.copy()
                overlay[mask_bool] = colour
                cv2.addWeighted(overlay, 0.35, annotated, 0.65, 0, annotated)
            except Exception:
                pass  # Skip mask drawing on error

    return annotated
