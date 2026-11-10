/*
 * ============================================================================
 * ESP32-S TWO-AXIS NEEDLE INSERTION END-EFFECTOR CONTROLLER
 * ============================================================================
 * Healthcare Robotics Research Prototype
 * 
 * Hardware:
 *   - Microcontroller: ESP32-S Development Board
 *   - Drivers: Step/Dir Stepper Drivers (A4988 / DRV8825 / TMC2208/TMC2209)
 *   - Axis 1: Needle Insertion (Linear motion)
 *   - Axis 2: Needle Rotation (Rotational motion)
 *   - Limit switches for homing
 * 
 * Communication:
 *   - USB Serial @ 115200 baud
 *   - Newline-delimited JSON commands and telemetry (Protocol v1)
 * 
 * Safety features:
 *   - Communication watchdog: auto-halts motors if PC heartbeat stops (timeout: 2000ms)
 *   - Hardware limit switch detection
 *   - Software travel limits (degrees)
 *   - Safe stopping state on communication loss
 * ============================================================================
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ----------------------------------------------------------------------------
// PIN ASSIGNMENTS (Configurable for target hardware PCB/breadboard)
// ----------------------------------------------------------------------------
// Axis 1: Insertion
#define PIN_STEP_AXIS1      18
#define PIN_DIR_AXIS1       19
#define PIN_LIMIT_AXIS1     21  // Active-LOW limit switch with internal pullup

// Axis 2: Rotation
#define PIN_STEP_AXIS2      22
#define PIN_DIR_AXIS2       23
#define PIN_LIMIT_AXIS2     25  // Active-LOW limit switch with internal pullup

// Shared Stepper Driver Enable (Active-LOW for most drivers)
#define PIN_ENABLE_MOTORS   5

// On-board Status LED
#define PIN_LED_STATUS      2

// ----------------------------------------------------------------------------
// KINEMATIC & MOTOR PARAMETERS (Must match physical hardware)
// ----------------------------------------------------------------------------
// Calibration: Steps per Degree of output shaft
// Example: 200 steps/rev * 16 microsteps = 3200 steps/rev -> 3200 / 360 = 8.889 steps/deg
static float STEPS_PER_DEG_AXIS1 = 8.88889f;
static float STEPS_PER_DEG_AXIS2 = 8.88889f;

// Software travel limits (degrees)
static float LIMIT_MIN_AXIS1 = -180.0f;
static float LIMIT_MAX_AXIS1 =  180.0f;
static float LIMIT_MIN_AXIS2 = -360.0f;
static float LIMIT_MAX_AXIS2 =  360.0f;

// Speed & Acceleration defaults
static float DEFAULT_SPEED_DPS = 20.0f;     // deg / sec
static float MAX_SPEED_DPS     = 90.0f;     // deg / sec
static float ACCEL_DPS2        = 100.0f;    // deg / sec^2

// Watchdog timer (ms)
#define WATCHDOG_TIMEOUT_MS 2000
#define TELEMETRY_RATE_MS    200   // 5 Hz telemetry stream

// ----------------------------------------------------------------------------
// AXIS STATE STRUCTURE
// ----------------------------------------------------------------------------
struct AxisState {
    long current_step;
    long target_step;
    float current_deg;
    float target_deg;
    float speed_deg_s;
    bool is_moving;
    bool is_homed;
    int step_pin;
    int dir_pin;
    int limit_pin;
    float steps_per_deg;
    float limit_min;
    float limit_max;
    unsigned long step_interval_us;
    unsigned long last_step_time_us;
};

static AxisState axis1;
static AxisState axis2;

static bool g_pc_connected     = false;
static bool g_motors_enabled   = false;
static unsigned long g_last_comm_time_ms = 0;
static unsigned long g_last_telem_time_ms = 0;

// Serial reception buffer
static String g_serial_buffer = "";

// ----------------------------------------------------------------------------
// FORWARD DECLARATIONS
// ----------------------------------------------------------------------------
void processLine(const String& line);
void handleCommand(JsonDocument& doc);
void sendResponse(long id, bool ok, const char* status, const char* errorMsg = nullptr);
void sendTelemetry();
void emergencyStop();
void setMotorsEnabled(bool enable);
void updateSteppers();
void homeAxis(int axis_num);

// ----------------------------------------------------------------------------
// SETUP
// ----------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000) {
        ; // Wait for serial port on native USB
    }

    pinMode(PIN_STEP_AXIS1, OUTPUT);
    pinMode(PIN_DIR_AXIS1, OUTPUT);
    pinMode(PIN_LIMIT_AXIS1, INPUT_PULLUP);

    pinMode(PIN_STEP_AXIS2, OUTPUT);
    pinMode(PIN_DIR_AXIS2, OUTPUT);
    pinMode(PIN_LIMIT_AXIS2, INPUT_PULLUP);

    pinMode(PIN_ENABLE_MOTORS, OUTPUT);
    pinMode(PIN_LED_STATUS, OUTPUT);

    // Initialize Axis 1
    axis1.current_step       = 0;
    axis1.target_step        = 0;
    axis1.current_deg        = 0.0f;
    axis1.target_deg         = 0.0f;
    axis1.speed_deg_s        = DEFAULT_SPEED_DPS;
    axis1.is_moving          = false;
    axis1.is_homed           = false;
    axis1.step_pin           = PIN_STEP_AXIS1;
    axis1.dir_pin            = PIN_DIR_AXIS1;
    axis1.limit_pin          = PIN_LIMIT_AXIS1;
    axis1.steps_per_deg      = STEPS_PER_DEG_AXIS1;
    axis1.limit_min          = LIMIT_MIN_AXIS1;
    axis1.limit_max          = LIMIT_MAX_AXIS1;
    axis1.step_interval_us   = 1000;
    axis1.last_step_time_us  = 0;

    // Initialize Axis 2
    axis2.current_step       = 0;
    axis2.target_step        = 0;
    axis2.current_deg        = 0.0f;
    axis2.target_deg         = 0.0f;
    axis2.speed_deg_s        = DEFAULT_SPEED_DPS;
    axis2.is_moving          = false;
    axis2.is_homed           = false;
    axis2.step_pin           = PIN_STEP_AXIS2;
    axis2.dir_pin            = PIN_DIR_AXIS2;
    axis2.limit_pin          = PIN_LIMIT_AXIS2;
    axis2.steps_per_deg      = STEPS_PER_DEG_AXIS2;
    axis2.limit_min          = LIMIT_MIN_AXIS2;
    axis2.limit_max          = LIMIT_MAX_AXIS2;
    axis2.step_interval_us   = 1000;
    axis2.last_step_time_us  = 0;

    // Default to motors disabled (safe state)
    setMotorsEnabled(false);

    digitalWrite(PIN_LED_STATUS, LOW);
    g_last_comm_time_ms = millis();
}

// ----------------------------------------------------------------------------
// MAIN LOOP
// ----------------------------------------------------------------------------
void loop() {
    unsigned long now = millis();

    // 1. Process incoming Serial bytes
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (g_serial_buffer.length() > 0) {
                processLine(g_serial_buffer);
                g_serial_buffer = "";
            }
        } else {
            g_serial_buffer += c;
            if (g_serial_buffer.length() > 512) {
                g_serial_buffer = ""; // prevent buffer overflow
            }
        }
    }

    // 2. Communication Watchdog: if PC was connected but stopped communicating, halt motors
    if (g_pc_connected && (now - g_last_comm_time_ms > WATCHDOG_TIMEOUT_MS)) {
        emergencyStop();
        g_pc_connected = false;
        digitalWrite(PIN_LED_STATUS, LOW);
    }

    // 3. Update Stepper Motion
    if (g_motors_enabled) {
        updateSteppers();
    }

    // 4. Send Periodic Telemetry
    if (now - g_last_telem_time_ms >= TELEMETRY_RATE_MS) {
        g_last_telem_time_ms = now;
        sendTelemetry();
    }
}

// ----------------------------------------------------------------------------
// STEPPER GENERATOR (Time-sliced stepping)
// ----------------------------------------------------------------------------
void updateAxis(AxisState& ax) {
    if (!ax.is_moving) return;

    if (ax.current_step == ax.target_step) {
        ax.is_moving = false;
        return;
    }

    unsigned long now_us = micros();
    if (now_us - ax.last_step_time_us >= ax.step_interval_us) {
        ax.last_step_time_us = now_us;

        // Set direction pin
        if (ax.target_step > ax.current_step) {
            digitalWrite(ax.dir_pin, HIGH);
            ax.current_step++;
        } else {
            digitalWrite(ax.dir_pin, LOW);
            ax.current_step--;
        }

        // Generate pulse
        digitalWrite(ax.step_pin, HIGH);
        delayMicroseconds(4);
        digitalWrite(ax.step_pin, LOW);

        ax.current_deg = (float)ax.current_step / ax.steps_per_deg;
    }
}

void updateSteppers() {
    updateAxis(axis1);
    updateAxis(axis2);
}

// ----------------------------------------------------------------------------
// COMMAND PROCESSING
// ----------------------------------------------------------------------------
void processLine(const String& line) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) {
        return;
    }

    g_last_comm_time_ms = millis();
    handleCommand(doc);
}

void handleCommand(JsonDocument& doc) {
    int v = doc["v"] | 1;
    long id = doc["id"] | 0;
    const char* cmd = doc["cmd"] | "";

    if (strcmp(cmd, "CONNECT") == 0) {
        g_pc_connected = true;
        digitalWrite(PIN_LED_STATUS, HIGH);
        sendResponse(id, true, "connected");
        return;
    }

    if (strcmp(cmd, "DISCONNECT") == 0) {
        emergencyStop();
        g_pc_connected = false;
        digitalWrite(PIN_LED_STATUS, LOW);
        sendResponse(id, true, "disconnected");
        return;
    }

    if (strcmp(cmd, "HEARTBEAT") == 0) {
        sendResponse(id, true, "heartbeat_ack");
        return;
    }

    if (strcmp(cmd, "ENABLE") == 0) {
        setMotorsEnabled(true);
        sendResponse(id, true, "enabled");
        return;
    }

    if (strcmp(cmd, "DISABLE") == 0) {
        setMotorsEnabled(false);
        sendResponse(id, true, "disabled");
        return;
    }

    if (strcmp(cmd, "STOP") == 0) {
        emergencyStop();
        sendResponse(id, true, "stopped");
        return;
    }

    if (strcmp(cmd, "HOME") == 0) {
        int axis_id = doc["axis"] | 0; // 0 = both
        if (!g_motors_enabled) {
            sendResponse(id, false, "error", "Motors not enabled");
            return;
        }
        if (axis_id == 0 || axis_id == 1) homeAxis(1);
        if (axis_id == 0 || axis_id == 2) homeAxis(2);
        sendResponse(id, true, "homing_complete");
        return;
    }

    if (strcmp(cmd, "MOVE_ABS") == 0) {
        int axis_id = doc["axis"] | 0;
        float target_deg = doc["target_deg"] | 0.0f;
        float speed = doc["speed"] | DEFAULT_SPEED_DPS;

        if (!g_motors_enabled) {
            sendResponse(id, false, "rejected", "Motors disabled");
            return;
        }

        AxisState* ax = nullptr;
        if (axis_id == 1) ax = &axis1;
        else if (axis_id == 2) ax = &axis2;
        else {
            sendResponse(id, false, "rejected", "Invalid axis");
            return;
        }

        // Bounded movement check
        if (target_deg < ax->limit_min || target_deg > ax->limit_max) {
            sendResponse(id, false, "rejected", "Target exceeds software travel limits");
            return;
        }

        speed = constrain(speed, 0.1f, MAX_SPEED_DPS);
        ax->speed_deg_s = speed;
        ax->target_deg = target_deg;
        ax->target_step = (long)(target_deg * ax->steps_per_deg);
        
        float steps_per_sec = speed * ax->steps_per_deg;
        if (steps_per_sec > 0.0f) {
            ax->step_interval_us = (unsigned long)(1000000.0f / steps_per_sec);
        }
        ax->is_moving = true;

        sendResponse(id, true, "accepted");
        return;
    }

    if (strcmp(cmd, "MOVE_REL") == 0) {
        int axis_id = doc["axis"] | 0;
        float delta_deg = doc["delta_deg"] | 0.0f;
        float speed = doc["speed"] | DEFAULT_SPEED_DPS;

        if (!g_motors_enabled) {
            sendResponse(id, false, "rejected", "Motors disabled");
            return;
        }

        AxisState* ax = (axis_id == 1) ? &axis1 : ((axis_id == 2) ? &axis2 : nullptr);
        if (!ax) {
            sendResponse(id, false, "rejected", "Invalid axis");
            return;
        }

        float target_deg = ax->current_deg + delta_deg;
        if (target_deg < ax->limit_min || target_deg > ax->limit_max) {
            sendResponse(id, false, "rejected", "Target exceeds software travel limits");
            return;
        }

        speed = constrain(speed, 0.1f, MAX_SPEED_DPS);
        ax->speed_deg_s = speed;
        ax->target_deg = target_deg;
        ax->target_step = (long)(target_deg * ax->steps_per_deg);

        float steps_per_sec = speed * ax->steps_per_deg;
        if (steps_per_sec > 0.0f) {
            ax->step_interval_us = (unsigned long)(1000000.0f / steps_per_sec);
        }
        ax->is_moving = true;

        sendResponse(id, true, "accepted");
        return;
    }

    if (strcmp(cmd, "GET_STATUS") == 0) {
        sendResponse(id, true, "status_ok");
        return;
    }

    sendResponse(id, false, "unrecognized_command");
}

// ----------------------------------------------------------------------------
// RESPONSE & TELEMETRY SERIALIZATION
// ----------------------------------------------------------------------------
void sendResponse(long id, bool ok, const char* status, const char* errorMsg) {
    JsonDocument doc;
    doc["v"] = 1;
    doc["id"] = id;
    doc["ok"] = ok;
    doc["status"] = status;
    if (errorMsg != nullptr) {
        doc["error"] = errorMsg;
    }
    serializeJson(doc, Serial);
    Serial.println();
}

void sendTelemetry() {
    JsonDocument doc;
    doc["v"] = 1;
    doc["type"] = "telemetry";
    doc["connected"] = g_pc_connected;
    doc["enabled"] = g_motors_enabled;

    JsonArray axes = doc["axes"].to<JsonArray>();

    JsonObject a1 = axes.add<JsonObject>();
    a1["axis"] = 1;
    a1["position_deg"] = axis1.current_deg;
    a1["homed"] = axis1.is_homed;
    a1["moving"] = axis1.is_moving;

    JsonObject a2 = axes.add<JsonObject>();
    a2["axis"] = 2;
    a2["position_deg"] = axis2.current_deg;
    a2["homed"] = axis2.is_homed;
    a2["moving"] = axis2.is_moving;

    serializeJson(doc, Serial);
    Serial.println();
}

// ----------------------------------------------------------------------------
// SAFETY & MOTOR CONTROLS
// ----------------------------------------------------------------------------
void emergencyStop() {
    axis1.target_step = axis1.current_step;
    axis1.target_deg  = axis1.current_deg;
    axis1.is_moving   = false;

    axis2.target_step = axis2.current_step;
    axis2.target_deg  = axis2.current_deg;
    axis2.is_moving   = false;
}

void setMotorsEnabled(bool enable) {
    g_motors_enabled = enable;
    if (!enable) {
        emergencyStop();
        digitalWrite(PIN_ENABLE_MOTORS, HIGH); // Driver DISABLE (active low)
    } else {
        digitalWrite(PIN_ENABLE_MOTORS, LOW);  // Driver ENABLE
    }
}

void homeAxis(int axis_num) {
    AxisState* ax = (axis_num == 1) ? &axis1 : &axis2;
    // Step toward limit switch at slow speed until triggered
    digitalWrite(ax->dir_pin, LOW);
    unsigned long timeout_start = millis();

    while (digitalRead(ax->limit_pin) == HIGH && (millis() - timeout_start < 5000)) {
        digitalWrite(ax->step_pin, HIGH);
        delayMicroseconds(5);
        digitalWrite(ax->step_pin, LOW);
        delayMicroseconds(2000);
    }

    // Zero position
    ax->current_step = 0;
    ax->target_step  = 0;
    ax->current_deg  = 0.0f;
    ax->target_deg   = 0.0f;
    ax->is_moving    = false;
    ax->is_homed     = true;
}
