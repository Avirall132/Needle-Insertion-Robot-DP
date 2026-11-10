# ESP32 End-Effector Controller Firmware

Firmware for the ESP32-S microcontroller controlling the 2-DOF needle insertion end-effector.

## 1. Hardware Architecture

- **Microcontroller**: ESP32-S DevKit
- **Motor Drivers**: Step/Dir bipolar stepper drivers (A4988, DRV8825, TMC2208, or TMC2209 in standalone legacy mode)
- **Axis 1 (Insertion)**: Linear guide for forward/backward needle travel
- **Axis 2 (Guide angle)**: Circular guide for changing the needle insertion angle

### Default Pinout

| Function | ESP32 GPIO | Description |
|---|---|---|
| **Axis 1 STEP** | GPIO 18 | Step pulse to Driver 1 |
| **Axis 1 DIR** | GPIO 19 | Direction to Driver 1 |
| **Axis 1 LIMIT** | GPIO 21 | Active-LOW limit switch (uses internal pull-up) |
| **Axis 2 STEP** | GPIO 22 | Step pulse to Driver 2 |
| **Axis 2 DIR** | GPIO 23 | Direction to Driver 2 |
| **Axis 2 LIMIT** | GPIO 25 | Active-LOW limit switch (uses internal pull-up) |
| **ENABLE (Common)** | GPIO 5 | Driver Enable (Active-LOW: 0V = Enabled, 3.3V = Disabled) |
| **Status LED** | GPIO 2 | Onboard LED (illuminates on PC connect) |

> [!WARNING]
> Verify your driver logic levels before connecting. Standard ESP32 GPIOs operate at 3.3V. If using 5V driver inputs, confirm your drivers accept 3.3V logic (e.g., TMC2208/A4988 VIO pin must be tied to ESP32 3.3V).

---

## 2. Compilation and Flashing

### Requirements
- **Arduino IDE** (version 2.x) or **PlatformIO** (VS Code)
- ESP32 Board Package: `esp32` by Espressif Systems (v2.0.x or v3.0.x)
- Library: **ArduinoJson** (version 7.x, install via Arduino Library Manager)

### Flashing via Arduino IDE:
1. Open `firmware/esp32_controller/esp32_controller.ino`.
2. Select **Tools > Board > ESP32 Arduino > ESP32 Dev Module**.
3. Select the COM port corresponding to the connected USB-to-UART bridge.
4. Set **Upload Speed**: `921600` or `115200`.
5. Click **Upload**.

---

## 3. Motor Calibration & Configuration

Open `esp32_controller.ino` and configure the kinematic constants for your mechanical setup:

### Steps Per Motion Unit

Axis 1 is calibrated in **steps/mm** from the linear guide transmission:

$$\text{steps\_per\_mm} = \frac{\text{motor\_steps} \times \text{microstepping} \times \text{transmission\_ratio}}{\text{mm per motor revolution}}$$

Axis 2 is calibrated in **steps/degree** for the circular guide:

$$\text{steps\_per\_deg} = \frac{\text{motor\_steps\_per\_rev} \times \text{microstepping} \times \text{gear\_ratio}}{360.0}$$

**Example:**
- 1.8° stepper motor = 200 full steps/rev
- 1/16 microstepping = 16
- 1:1 direct drive = 1.0 gear ratio
- $\text{steps\_per\_deg} = \frac{200 \times 16 \times 1.0}{360} = \frac{3200}{360} = 8.88889 \text{ steps/degree}$

Update in the firmware:
```cpp
static float STEPS_PER_MM_AXIS1  = /* calibrate from the linear guide */;
static float STEPS_PER_DEG_AXIS2 = 8.88889f;

static float LIMIT_MIN_AXIS1_MM  = /* linear minimum */;
static float LIMIT_MAX_AXIS1_MM  = /* linear maximum */;
static float LIMIT_MIN_AXIS2_DEG = /* minimum guide angle */;
static float LIMIT_MAX_AXIS2_DEG = /* maximum guide angle */;
```

---

## 4. Communication Protocol (Newline-Delimited JSON)

All commands and responses are single-line JSON objects terminated by `\n`.

### A. Commands (PC -> ESP32)
- **Connect**: `{"v":1,"id":1,"cmd":"CONNECT"}`
- **Enable Drivers**: `{"v":1,"id":2,"cmd":"ENABLE"}`
- **Move insertion absolute**: `{"v":1,"id":3,"cmd":"MOVE_ABS","axis":1,"target_mm":45.0,"speed":15.0}`
- **Move guide angle relative**: `{"v":1,"id":4,"cmd":"MOVE_REL","axis":2,"delta_deg":-30.0,"speed":10.0}`
- **Home**: `{"v":1,"id":5,"cmd":"HOME","axis":1}` (axis 0 = both)
- **Stop**: `{"v":1,"id":6,"cmd":"STOP"}`
- **Heartbeat**: `{"v":1,"id":7,"cmd":"HEARTBEAT"}`

### B. Responses (ESP32 -> PC)
```json
{"v":1,"id":3,"ok":true,"status":"accepted"}
```

### C. Periodic Telemetry (ESP32 -> PC, 5 Hz)
```json
{"v":1,"type":"telemetry","connected":true,"enabled":true,"axes":[{"axis":1,"position_mm":45.0,"homed":true,"moving":false},{"axis":2,"position_deg":0.0,"homed":false,"moving":false}]}
```

### D. Safety Watchdog
The ESP32 firmware monitors incoming traffic. If a PC application crashes, loses connection, or disconnects without a clean stop, the ESP32 safety watchdog trips after **2000 ms** and automatically halts motor pulse generation.
