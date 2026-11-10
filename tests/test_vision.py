"""
Tests for Vision subsystem (vision/camera.py and vision/needle_detector.py).
"""

import numpy as np
import pytest
from vision.camera import CameraManager
from vision.needle_detector import (
    Detection,
    MockDetector,
    create_detector,
    draw_detections,
)


def test_detection_dataclass():
    det = Detection(bbox=(100.0, 50.0, 200.0, 150.0), confidence=0.88, class_name="needle")
    assert det.width == 100.0
    assert det.height == 100.0
    assert det.center == (150.0, 100.0)
    assert det.confidence == 0.88


def test_mock_detector_contract():
    detector = MockDetector()
    assert not detector.is_loaded
    assert "Mock" in detector.status_message or "not loaded" in detector.status_message

    # Inference should return empty detections without crashing
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = detector.detect(blank_frame)
    assert isinstance(detections, list)
    assert len(detections) == 0


def test_create_detector_factory():
    # Null path -> Mock detector
    det1 = create_detector(None)
    assert isinstance(det1, MockDetector)

    # Missing file -> Mock detector or unloaded detector
    det2 = create_detector("nonexistent_model.onnx")
    assert not det2.is_loaded


def test_draw_detections():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = [
        Detection(bbox=(50.0, 60.0, 150.0, 200.0), confidence=0.92, class_name="needle"),
    ]

    annotated = draw_detections(frame, detections)
    assert annotated.shape == (480, 640, 3)
    # The image should no longer be completely black
    assert np.any(annotated > 0)


def test_camera_manager_lifecycle():
    cam = CameraManager()
    assert not cam.is_connected

    # Set resolution
    cam.set_resolution(1280, 720)
    cam.set_fps(30)
    assert cam.resolution == (1280, 720)
    assert cam.fps == 30

    # Disconnect when already disconnected should not crash
    cam.disconnect()
    assert not cam.is_connected
