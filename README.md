# Teleoperated Robotic Needle Insertion System

A real-time Python desktop workstation for teleoperating a **Universal Robots UR7e** robotic arm and an **ESP32-driven 2-DOF needle positioning end-effector**. The end-effector provides linear needle insertion/retraction and adjustment of the needle-guide angle through a circular guide.

Designed for healthcare-related research experiments on fixtures and tissue phantoms.

---

## 1. System Architecture

The application is structured into three independent, decoupled subsystems coordinated through a PySide6 GUI dashboard:

```
needle_robot/
│
├── main.py                     # Workstation entry point & Qt event loop
├── config.py                   # Thread-safe configuration manager
├── config.json                 # System configuration file
├── requirements.txt            # Python dependencies
├── README.md                   # Complete system documentation
│
├── controllers/                # Hardware & simulation controllers
│   ├── __init__.py
│   ├── ur_controller.py        # UR7e controller (ur_rtde & simulation)
│   └── esp32_controller.py     # ESP32 JSON-over-serial protocol controller
│
├── vision/                     # Computer vision & needle tracking
│   ├── __init__.py
│   ├── camera.py               # Thread-safe OpenCV video capture
│   └── needle_detector.py      # Abstract detector (YOLO / ONNX / Mock)
│
├── workers/                    # Background QThread workers
│   ├── __init__.py
│   ├── ur_worker.py            # UR7e 10Hz telemetry & command queue
│   ├── esp32_worker.py         # ESP32 5Hz telemetry & command queue
│   └── vision_worker.py        # 30Hz frame capture, inference & annotation
│
├── interface/                  # PySide6 industrial workstation GUI
│   ├── __init__.py
│   ├── main_window.py          # 4-section workstation window
│   ├── robot_panel.py          # UR7e joint & Cartesian jog controls
│   ├── end_effector_panel.py   # ESP32 2-axis controls & homing
│   ├── vision_panel.py         # Live video feed & ML detection metrics
│   └── styles.py               # Dark industrial theme QSS & indicators
│
├── firmware/                   # Microcontroller embedded code
│   └── esp32_controller/
│       ├── esp32_controller.ino# ESP32-S 2-axis stepper firmware
│       └── README.md           # Wiring, pinouts & flashing guide
│
├── models/                     # ML model weights & specifications
│   └── README.md               # Model format, input dimensions & guide
│
├── tests/                      # Automated pytest suite
│   ├── __init__.py
│   ├── test_config.py          # Configuration loading & validation tests
│   ├── test_ur_controller.py   # UR7e state, jogging & limit tests
│   ├── test_esp32_protocol.py  # ESP32 protocol, sequence ID & limit tests
│   ├── test_vision.py          # Camera & needle detector tests
│   └── test_gui.py             # Main window integration test
│
└── logs/                       # Rotating application logs
    └── teleop.log
```

---

## 2. Subsystem Details

### Subsystem A: UR7e Robot Control
- **Protocol**: Ethernet communication via Universal Robots RTDE (`ur_rtde`).
- **Control Modes**:
  - **Joint-space jogging**: 6 independent axes (displayed in degrees, computed in radians).
  - **Cartesian jogging**: X, Y, Z translation (mm) and RX, RY, RZ rotation (deg).
- **Safety**:
  - Independent thread execution (`URWorker` at 10 Hz).
  - Velocity and acceleration clamping to configured limits.
  - Software joint angle and Cartesian travel bounds.
  - Simulation mode active by default until physical IP is configured.

### Subsystem B: ESP32 End-Effector Control
- **Protocol**: USB-serial at 115200 baud with newline-delimited JSON messages.
- **Commands**: `CONNECT`, `DISCONNECT`, `ENABLE`, `DISABLE`, `MOVE_ABS`, `MOVE_REL`, `HOME`, `STOP`, `HEARTBEAT`.
- **Safety**:
  - Software watchdog (2000 ms timeout) on ESP32; automatically halts motor pulses if PC communication ceases.
  - Movement commands are rejected until calibrated motor parameters (steps/mm for insertion, steps/degree for guide angle, travel limits) are set.
  - Reports estimated positions for open-loop steppers.

### Subsystem C: Live ML Needle Detection
- **Pipeline**: Camera → OpenCV BGR → PyTorch/ONNX Inference → Annotation → QImage RGB → GUI.
- **Backends**:
  - `.pt` PyTorch / TorchScript (Ultralytics YOLO)
  - `.onnx` ONNX Runtime (CPU / CUDA)
  - `MockDetector` fallback: used when no model is loaded. Continues streaming video with zero latency.
- **Decoupling**: The ML model strictly provides visual overlays and metrics. It **never** issues robot motion commands.

---

## 3. Installation & Setup

### Prerequisites
- Python 3.10 to 3.13 (64-bit)
- Windows, Linux, or macOS

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Optional: UR RTDE Library (for physical UR7e arm)
For connecting to the real UR7e arm over Ethernet:
```bash
pip install ur_rtde
```
*(On Windows, compiling `ur_rtde` from source requires Visual Studio C++ Build Tools and CMake. If not installed, the application runs seamlessly in simulated dry-run mode).*

### 3. Run Automated Tests
```bash
pytest -v tests
```
All 19 tests verify configuration validation, kinematics bounds, ESP32 JSON protocol parsing, camera lifecycle, and GUI initialization.

---

## 4. Configuration (`config.json`)

The system loads settings from `config.json`. Unknown safety parameters default to `null` to prevent uncontrolled movement:

```json
{
    "robot": {
        "ip": null,
        "enabled": false,
        "max_velocity": 0.5,
        "max_acceleration": 0.5
    },
    "esp32": {
        "serial_port": null,
        "baud_rate": 115200,
        "enabled": false
    },
    "camera": {
        "index": 0,
        "width": 640,
        "height": 480,
        "fps": 30
    },
    "vision": {
        "model_path": null,
        "confidence_threshold": 0.40,
        "enabled": false
    },
    "application": {
        "simulation_mode": true,
        "log_level": "INFO"
    }
}
```

- To enable physical hardware, set `"simulation_mode": false` and provide the UR IP and ESP32 COM port.

---

## 5. Launching the Workstation

Start the desktop workstation with:

```bash
python main.py
```

### GUI Layout:
1. **Header Bar**: Subsystem status indicators (UR7e, ESP32, Vision), Simulation mode banner, and prominent **ALL STOP** button.
2. **Left Panel (Top)**: UR7e 6-Axis Joint & Cartesian jog controls with step increment, speed sliders, and live TCP pose readouts.
3. **Left Panel (Bottom)**: ESP32 2-Axis End-Effector controls (Insertion & Guide Angle) with motor enable toggle, homing, and port selector.
4. **Right Panel**: High-resolution camera feed with needle detection bounding box, confidence score, FPS counter, and threshold adjustment.
5. **Bottom Panel**: System Activity & Safety Audit Log tracking every command, acknowledgement, and safety event with millisecond timestamps.

---

## 6. Physical Hardware Integration Checklist

To transition from the tested simulation mode to the physical robot and end-effector, obtain and configure the following physical parameters:

| Parameter | Required Value | Where to Configure |
|---|---|---|
| **UR7e IP Address** | e.g. `192.168.1.100` | `config.json` -> `robot.ip` |
| **PolyScope Version** | PolyScope 5.x | Verified via UR Teach Pendant |
| **ESP32 COM Port** | e.g. `COM3` (Win) or `/dev/ttyUSB0` (Linux) | `config.json` -> `esp32.serial_port` |
| **Axis 1 (Insertion) Ratio** | Steps/mm | `firmware/esp32_controller/esp32_controller.ino` |
| **Axis 2 (Guide Angle) Ratio** | Steps/degree | `firmware/esp32_controller/esp32_controller.ino` |
| **Mechanical Travel Limits** | Min/Max physical limits | `esp32_controller.py` & firmware |
| **Needle Detection Model** | Trained `.pt` or `.onnx` file | Place in `models/` & set in `config.json` |

---

## 7. Safety Constraints & Disclaimers

> [!CAUTION]
> **RESEARCH PLATFORM ONLY - NOT A MEDICAL DEVICE**
> 
> 1. This application is an experimental engineering research tool intended strictly for teleoperation on inanimate fixtures and tissue phantoms.
> 2. The software STOP button on the screen is an operational convenience and **does NOT replace the physical hardware Emergency Stop button** provided with the Universal Robots control box.
> 3. Autonomous needle insertion is strictly prohibited. All motion requires active operator authorization.
> 4. The robot will never move automatically on startup or upon reconnection after a network failure.
