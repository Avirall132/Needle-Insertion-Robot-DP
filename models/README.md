# Needle Detection ML Models

This directory holds the machine-learning weights and configuration for real-time visual needle tracking.

## 1. Supported Model Formats

The vision subsystem automatically selects the inference runtime based on the model file extension:

| Format | Extension | Preferred Framework | Runtime |
|---|---|---|---|
| **YOLO PyTorch** | `.pt` | Ultralytics YOLOv8 / YOLOv11 | PyTorch / TorchScript (`ultralytics`) |
| **ONNX** | `.onnx` | Exported from PyTorch/TensorFlow | ONNX Runtime (`onnxruntime` CPU or CUDA) |

---

## 2. Model Requirements

For accurate needle tracking in surgical phantom or tissue fixtures:
- **Task**: Object Detection (`detect`) or Instance Segmentation (`segment`)
- **Input Resolution**: Standard $640 \times 640$ pixels (RGB)
- **Classes**:
  - Class 0: `needle` (or `needle_tip`, `needle_shaft` if multi-part detection is trained)
- **Output**:
  - Bounding boxes: `[x1, y1, x2, y2]` in pixel coordinates
  - Confidence score: $0.0 - 1.0$
  - Class index / label
  - (Optional) Instance segmentation mask overlay for needle shaft curvature

---

## 3. How to Load a Model into the Application

1. Place your trained `.pt` or `.onnx` model file in this folder (e.g., `models/needle_yolov8n.pt`).
2. Open `config.json` and update the `vision` section:
   ```json
   {
       "vision": {
           "model_path": "models/needle_yolov8n.pt",
           "confidence_threshold": 0.40,
           "enabled": true
       }
   }
   ```
3. Alternatively, launch `main.py` and toggle detection on the **Vision & ML Panel**.

---

## 4. Current State: Mock Detector Fallback

If no trained model is configured or if `model_path` is null, the system automatically runs the `MockDetector`:
- It continues streaming the live camera feed without interruptions.
- It clearly displays `"Model not loaded - using mock detector"` on the status indicator.
- It does **not** generate fictitious bounding boxes.
- Robot teleoperation remains 100% independent and unaffected.

---

## 5. Training Recommendations for Needle Tracking

If you need to train a model:
1. Collect 300–500 images of the needle under the target camera lighting, fixture angles, and phantom materials.
2. Label with [Roboflow](https://roboflow.com) or [Label Studio](https://labelstud.io) using bounding boxes or polygon masks around the needle shaft and tip.
3. Train YOLOv8 nano or small:
   ```bash
   yolo detect train data=needle_dataset.yaml model=yolov8n.pt epochs=100 imgsz=640
   ```
4. Export to ONNX for lightweight inference:
   ```bash
   yolo export model=runs/detect/train/weights/best.pt format=onnx
   ```
