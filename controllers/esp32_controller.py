"""
ESP32 end-effector controller for the needle teleoperation system.

Communicates with an ESP32 micro-controller over USB-serial using a
JSON-based command/response protocol (newline-delimited).  Supports:

  • Two-axis stepper control (linear insertion & guide-angle adjustment).
  • A software watchdog that halts the ESP32 if heartbeats stop.
  • Full simulation mode for development without hardware.

Thread-safe: every public method acquires an internal lock.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol version
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = 1

# ---------------------------------------------------------------------------
# Command names
# ---------------------------------------------------------------------------
CMD_CONNECT = "CONNECT"
CMD_DISCONNECT = "DISCONNECT"
CMD_HOME = "HOME"
CMD_MOVE_ABS = "MOVE_ABS"
CMD_MOVE_REL = "MOVE_REL"
CMD_STOP = "STOP"
CMD_GET_STATUS = "GET_STATUS"
CMD_ENABLE = "ENABLE"
CMD_DISABLE = "DISABLE"
CMD_HEARTBEAT = "HEARTBEAT"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_BAUD = 115200
WATCHDOG_TIMEOUT_S = 2.0
COMMAND_TIMEOUT_S = 2.0
HEARTBEAT_INTERVAL_S = 0.5
NUM_AXES = 2


class ESP32Controller:
    """
    Controller for the ESP32-based needle end-effector.

    Parameters
    ----------
    simulation_mode : bool
        When *True* no serial port is opened; responses are generated
        locally.
    watchdog_timeout : float
        Seconds between heartbeats before the ESP32 halts its motors.
    motor_params_configured : bool
        Set to *True* only after motor parameters (steps/rev, speed
        limits, etc.) have been correctly configured.  The controller
        refuses to issue real movement commands until this is *True*.
    """

    def __init__(
        self,
        simulation_mode: bool = True,
        watchdog_timeout: float = WATCHDOG_TIMEOUT_S,
        motor_params_configured: bool = False,
        baud_rate: int = DEFAULT_BAUD,
    ) -> None:
        self._lock = threading.Lock()
        self._simulation_mode = simulation_mode
        self._watchdog_timeout = watchdog_timeout
        self._motor_params_configured = motor_params_configured
        if baud_rate <= 0:
            raise ValueError(f"baud_rate must be positive, got {baud_rate}.")
        self._axis_limits: Dict[int, tuple] = {
            0: (-180.0, 180.0),  # insertion travel in mm; calibrate to mechanism
            1: (-360.0, 360.0),
        }
        self._steps_per_unit: Dict[int, float] = {
            0: 8.88889,  # steps/mm for the insertion guide; calibrate mechanically
            1: 8.88889,
        }

        # Serial handle (real mode)
        self._serial = None  # serial.Serial

        # Connection bookkeeping
        self._connected = False
        self._port: Optional[str] = None
        self._baud_rate: int = baud_rate

        # Command sequencing
        self._seq_id: int = 0

        # Background reader thread
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_running = False

        # Heartbeat thread
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_running = False

        # Pending response synchronisation
        self._pending_id: Optional[int] = None
        self._pending_event = threading.Event()
        self._pending_response: Optional[dict] = None

        # Latest telemetry (updated asynchronously)
        self._last_telemetry: Optional[dict] = None

        # Open-loop position estimate (degrees), kept up to date in every mode.
        # The end-effector has no gyro/encoder feedback: position is the sum of
        # the steps we commanded, mirroring the firmware's own step counter.
        self._est_positions: List[float] = [0.0] * NUM_AXES
        self._est_homed: List[bool] = [False] * NUM_AXES
        self._motors_enabled: bool = False

        # Simulated axis state (shares the estimate storage, so the simulator
        # and the real firmware report position the same way)
        self._sim_positions: List[float] = self._est_positions
        self._sim_homed: List[bool] = self._est_homed
        self._sim_enabled: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def simulation_mode(self) -> bool:
        return self._simulation_mode

    @property
    def motor_params_configured(self) -> bool:
        return self._motor_params_configured

    @motor_params_configured.setter
    def motor_params_configured(self, value: bool) -> None:
        self._motor_params_configured = bool(value)

    @property
    def last_telemetry(self) -> Optional[dict]:
        with self._lock:
            return dict(self._last_telemetry) if self._last_telemetry else None

    # ------------------------------------------------------------------
    # Serial port discovery
    # ------------------------------------------------------------------
    @staticmethod
    def list_serial_ports() -> List[str]:
        """Return a list of available serial port names."""
        try:
            from serial.tools.list_ports import comports
            return [p.device for p in comports()]
        except ImportError:
            logger.warning("pyserial is not installed – cannot list ports.")
            return []
        except Exception as exc:
            logger.error("Failed to list serial ports: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self, port: str, baud_rate: Optional[int] = None) -> bool:
        """
        Open a serial connection to the ESP32.

        Returns ``True`` on success.
        """
        with self._lock:
            if self._connected:
                logger.warning("Already connected on %s.", self._port)
                return True

            self._port = port
            self._baud_rate = baud_rate if baud_rate is not None else self._baud_rate
            self._seq_id = 0

            if self._simulation_mode:
                self._connected = True
                for i in range(NUM_AXES):
                    self._est_positions[i] = 0.0
                    self._est_homed[i] = False
                self._sim_enabled = False
                self._motors_enabled = False
                logger.info("Simulation: connected to ESP32 on %s", port)
                self._start_heartbeat()
                return True

            # --- Real hardware ---
            try:
                import serial as pyserial

                self._serial = pyserial.Serial(
                    port=port,
                    baudrate=baud_rate,
                    timeout=0.1,
                )
                self._connected = True
                logger.info("Connected to ESP32 on %s @ %d baud.", port, baud_rate)

                # Start background reader
                self._reader_running = True
                self._reader_thread = threading.Thread(
                    target=self._reader_loop, daemon=True, name="ESP32-Reader"
                )
                self._reader_thread.start()

                # Start heartbeat
                self._start_heartbeat()

                # Send initial CONNECT command
                self._send_command_unlocked(CMD_CONNECT)
                return True
            except ImportError:
                logger.error("pyserial is not installed.  pip install pyserial")
                return False
            except Exception as exc:
                logger.error("Failed to open serial port %s: %s", port, exc)
                self._serial = None
                return False

    def disconnect(self) -> None:
        """Close the serial connection and stop background threads."""
        with self._lock:
            if not self._connected:
                return

            # Stop heartbeat first
            self._heartbeat_running = False

            if self._simulation_mode:
                self._connected = False
                logger.info("Simulation: disconnected from ESP32.")
                return

            # --- Real hardware ---
            try:
                self._send_command_unlocked(CMD_DISCONNECT)
            except Exception:
                pass

            self._reader_running = False
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None
            self._connected = False
            logger.info("Disconnected from ESP32 on %s.", self._port)

        # Wait for threads outside the lock
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Command interface
    # ------------------------------------------------------------------
    def send_command(self, cmd: str, **params: Any) -> Optional[dict]:
        """
        Send a command and wait for the matching response.

        Parameters
        ----------
        cmd : str
            One of the ``CMD_*`` constants.
        **params
            Extra key-value pairs included in the JSON payload.

        Returns
        -------
        dict or None
            The parsed response dict, or ``None`` on timeout / error.
        """
        with self._lock:
            return self._send_command_unlocked(cmd, **params)

    def _send_command_unlocked(self, cmd: str, **params: Any) -> Optional[dict]:
        """
        Build, send, and wait for a command response.

        Caller **must** hold ``self._lock``.
        """
        if not self._connected:
            raise RuntimeError("Not connected to ESP32.")

        self._seq_id += 1
        msg_id = self._seq_id

        payload: Dict[str, Any] = {"v": PROTOCOL_VERSION, "id": msg_id, "cmd": cmd}
        payload.update(params)
        line = json.dumps(payload, separators=(",", ":")) + "\n"

        if self._simulation_mode:
            return self._simulate_response(cmd, msg_id, params)

        # --- Real hardware ---
        try:
            self._pending_id = msg_id
            self._pending_event.clear()
            self._pending_response = None

            self._serial.write(line.encode("utf-8"))
            self._serial.flush()
            logger.debug("TX → %s", line.strip())
        except Exception as exc:
            logger.error("Serial write failed: %s", exc)
            return None

        # Wait for matching response (reader thread sets the event)
        # We must release the lock while waiting
        # Use a temporary reference so we can release safely
        event = self._pending_event

        # Release lock, wait, re-acquire
        self._lock.release()
        try:
            got_it = event.wait(timeout=COMMAND_TIMEOUT_S)
        finally:
            self._lock.acquire()

        if not got_it:
            logger.warning("Timeout waiting for response to cmd=%s id=%d", cmd, msg_id)
            return None

        return self._pending_response

    # ------------------------------------------------------------------
    # High-level motion commands & Configuration
    # ------------------------------------------------------------------
    @staticmethod
    def _to_index(axis: int) -> int:
        """
        Convert a public 1-based axis id (1, 2) to a 0-based index.

        Legacy callers may pass 0 or 1 for the first axis; 0 maps to index 0.
        """
        return axis - 1 if axis in (1, 2) else axis

    def set_motor_parameters(
        self,
        axis1_steps_per_mm: Optional[float] = None,
        axis2_steps_per_deg: Optional[float] = None,
        axis1_limits: Optional[Tuple[float, float]] = None,
        axis2_limits: Optional[Tuple[float, float]] = None,
        **legacy: Any,
    ) -> None:
        """Configure insertion/angle calibration and travel limits."""
        with self._lock:
            if axis1_steps_per_mm is None and "axis1_steps_per_deg" in legacy:
                axis1_steps_per_mm = legacy["axis1_steps_per_deg"]
            if axis1_steps_per_mm is not None:
                self._steps_per_unit[0] = float(axis1_steps_per_mm)
            if axis2_steps_per_deg is not None:
                self._steps_per_unit[1] = float(axis2_steps_per_deg)
            if axis1_limits is not None:
                self._axis_limits[0] = axis1_limits
            if axis2_limits is not None:
                self._axis_limits[1] = axis2_limits
            self._motor_params_configured = True
            logger.info("Motor parameters configured: limits=%s", self._axis_limits)

    def _check_movement_allowed(self) -> Optional[dict]:
        """Check if movement is safe; returns error response dict if not allowed."""
        if not self._connected:
            return {"ok": False, "error": "Not connected to ESP32."}
        if not self._motor_params_configured:
            return {
                "ok": False,
                "error": "Motor parameters not configured. Calibration required.",
            }
        return None

    def move_axis(self, axis: int, target_position: float, speed: float = 100.0) -> Optional[dict]:
        """
        Move an axis to an absolute position.

        Parameters
        ----------
        axis : int
            0 or 1 (or 1 or 2, 1-based).
        target_position : float
            Axis 1 insertion position in mm or Axis 2 guide angle in degrees.
        speed : float
            Movement speed (device units).
        """
        with self._lock:
            err = self._check_movement_allowed()
            if err is not None:
                return err

            # Normalize 1-based (1, 2) to 0-based (0, 1)
            idx = self._to_index(axis)
            if not (0 <= idx < NUM_AXES):
                return {"ok": False, "error": f"Invalid axis: {axis}."}

            # Check travel limits
            limits = self._axis_limits.get(idx, (-180.0, 180.0))
            if target_position < limits[0] or target_position > limits[1]:
                return {
                    "ok": False,
                    "error": f"Target {target_position:.2f} exceeds axis {axis} limit [{limits[0]}, {limits[1]}].",
                }

            unit_key = "target_mm" if idx == 0 else "target_deg"
            resp = self._send_command_unlocked(
                CMD_MOVE_ABS,
                axis=idx + 1,
                target=target_position,
                **{unit_key: target_position},
                speed=speed,
            )
            if resp is not None and resp.get("ok"):
                self._est_positions[idx] = float(target_position)
            return resp

    def move_axis_relative(self, axis: int, delta_position: float, speed: float = 100.0) -> Optional[dict]:
        """
        Move an axis by a relative amount.

        Parameters
        ----------
        axis : int
            0 or 1 (or 1 or 2, 1-based).
        delta_position : float
            Axis 1 insertion delta in mm or Axis 2 guide-angle delta in degrees.
        speed : float
            Movement speed.
        """
        with self._lock:
            err = self._check_movement_allowed()
            if err is not None:
                return err

            idx = self._to_index(axis)
            if not (0 <= idx < NUM_AXES):
                return {"ok": False, "error": f"Invalid axis: {axis}."}

            # Reject a relative jog that would run outside the travel limits.
            limits = self._axis_limits.get(idx, (-180.0, 180.0))
            target = self._est_positions[idx] + delta_position
            if target < limits[0] or target > limits[1]:
                return {
                    "ok": False,
                    "error": f"Target {target:.2f} exceeds axis {axis} limit [{limits[0]}, {limits[1]}].",
                }

            unit_key = "delta_mm" if idx == 0 else "delta_deg"
            resp = self._send_command_unlocked(
                CMD_MOVE_REL,
                axis=idx + 1,
                delta=delta_position,
                **{unit_key: delta_position},
                speed=speed,
            )
            if resp is not None and resp.get("ok"):
                self._est_positions[idx] = target
            return resp

    def stop(self) -> Optional[dict]:
        """Immediately stop all axes."""
        with self._lock:
            if not self._connected:
                return None
            return self._send_command_unlocked(CMD_STOP)

    def home(self, axis: Optional[int] = None) -> Optional[dict]:
        """
        Home one or all axes.

        Parameters
        ----------
        axis : int or None
            If ``None``, home all axes.
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to ESP32.")

            idx: Optional[int] = None
            if axis is not None:
                idx = self._to_index(axis)
                if not (0 <= idx < NUM_AXES):
                    raise ValueError(f"axis must be 1–{NUM_AXES} or None, got {axis}.")

            params: Dict[str, Any] = {}
            if idx is not None:
                params["axis"] = idx + 1
            resp = self._send_command_unlocked(CMD_HOME, **params)
            if resp is not None and resp.get("ok"):
                targets = range(NUM_AXES) if idx is None else [idx]
                for i in targets:
                    self._est_positions[i] = 0.0
                    self._est_homed[i] = True
            return resp

    def enable(self) -> Optional[dict]:
        """Enable motor drivers."""
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to ESP32.")
            resp = self._send_command_unlocked(CMD_ENABLE)
            if resp is not None and resp.get("ok"):
                self._motors_enabled = True
            return resp

    def disable(self) -> Optional[dict]:
        """Disable motor drivers."""
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to ESP32.")
            resp = self._send_command_unlocked(CMD_DISABLE)
            if resp is not None and resp.get("ok"):
                self._motors_enabled = False
            return resp

    def get_status(self) -> Optional[dict]:
        """
        Query the ESP32 for current status.

        Returns
        -------
        dict
            ``{"axes": [{"position": float, "homed": bool}, ...], "enabled": bool}``
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to ESP32.")
            res = self._send_command_unlocked(CMD_GET_STATUS)
            if res is None:
                return None
            if "axes" not in res:
                if self._last_telemetry and "axes" in self._last_telemetry:
                    res["axes"] = copy.deepcopy(self._last_telemetry["axes"])
                else:
                    res["axes"] = self._estimated_axes()
            res.setdefault("connected", self._connected)
            res.setdefault("enabled", self._motors_enabled)
            return res

    def _estimated_axes(self) -> List[dict]:
        """Build a firmware-shaped axes list from the open-loop estimate."""
        return [
            {
                "axis": i + 1,
                "position": self._est_positions[i],
                **(
                    {"position_mm": self._est_positions[i]}
                    if i == 0
                    else {"position_deg": self._est_positions[i]}
                ),
                "homed": self._est_homed[i],
                "moving": False,
            }
            for i in range(NUM_AXES)
        ]

    def _sync_estimate_from_frame(self, frame: dict) -> None:
        """Adopt positions reported by the firmware (its own step counter)."""
        for ax in frame.get("axes", []):
            idx = self._to_index(ax.get("axis", 0))
            if not (0 <= idx < NUM_AXES):
                continue
            pos = ax.get("position_mm" if idx == 0 else "position_deg", ax.get("position"))
            if isinstance(pos, (int, float)):
                self._est_positions[idx] = float(pos)
            if "homed" in ax:
                self._est_homed[idx] = bool(ax["homed"])

    def get_telemetry(self) -> Optional[dict]:
        """
        Retrieve the latest telemetry frame from the ESP32.
        """
        with self._lock:
            if self._simulation_mode:
                return {
                    "v": PROTOCOL_VERSION,
                    "type": "telemetry",
                    "connected": self._connected,
                    "enabled": self._sim_enabled,
                    "axes": [
                        {
                            "axis": i + 1,
                            "position": self._sim_positions[i],
                            **(
                                {"position_mm": self._sim_positions[i]}
                                if i == 0
                                else {"position_deg": self._sim_positions[i]}
                            ),
                            "homed": self._sim_homed[i],
                            "moving": False,
                        }
                        for i in range(NUM_AXES)
                    ],
                }
            if self._last_telemetry is not None:
                frame = copy.deepcopy(self._last_telemetry)
                self._sync_estimate_from_frame(frame)
                frame.setdefault("axes", self._estimated_axes())
                frame.setdefault("enabled", self._motors_enabled)
                frame.setdefault("connected", self._connected)
                return frame

            # No telemetry stream (yet): report the commanded open-loop estimate
            # so the workstation always has a position to display.
            return {
                "v": PROTOCOL_VERSION,
                "type": "telemetry",
                "connected": self._connected,
                "enabled": self._motors_enabled,
                "axes": self._estimated_axes(),
            }

    # ------------------------------------------------------------------
    # Background reader (real mode)
    # ------------------------------------------------------------------
    def _reader_loop(self) -> None:
        """
        Continuously read lines from the serial port and dispatch them.

        Runs on a daemon thread.
        """
        logger.info("ESP32 reader thread started.")
        while self._reader_running:
            try:
                if self._serial is None or not self._serial.is_open:
                    break
                raw = self._serial.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                logger.debug("RX ← %s", line)
                self._dispatch_line(line)
            except Exception as exc:
                if self._reader_running:
                    logger.error("Reader error: %s", exc)
                break
        logger.info("ESP32 reader thread stopped.")

    def _dispatch_line(self, line: str) -> None:
        """Parse one JSON line and route it."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from ESP32: %s", line)
            return

        if not isinstance(data, dict):
            return

        msg_type = data.get("type")

        # Telemetry messages are unsolicited
        if msg_type == "telemetry":
            with self._lock:
                self._last_telemetry = data
                self._sync_estimate_from_frame(data)
                if "enabled" in data:
                    self._motors_enabled = bool(data["enabled"])
            return

        # Command responses carry an "id" field
        msg_id = data.get("id")
        if msg_id is not None:
            with self._lock:
                if msg_id == self._pending_id:
                    self._pending_response = data
                    self._pending_event.set()
            return

        logger.debug("Unhandled ESP32 message: %s", data)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------
    def _start_heartbeat(self) -> None:
        """Start the heartbeat background thread."""
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="ESP32-Heartbeat"
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat commands to keep the watchdog alive."""
        logger.info("ESP32 heartbeat thread started (interval=%.1fs).", HEARTBEAT_INTERVAL_S)
        while self._heartbeat_running and self._connected:
            try:
                with self._lock:
                    if self._connected:
                        if self._simulation_mode:
                            pass  # no actual heartbeat needed
                        else:
                            payload = {
                                "v": PROTOCOL_VERSION,
                                "id": 0,
                                "cmd": CMD_HEARTBEAT,
                            }
                            line = json.dumps(payload, separators=(",", ":")) + "\n"
                            try:
                                self._serial.write(line.encode("utf-8"))
                                self._serial.flush()
                            except Exception as exc:
                                logger.warning("Heartbeat send failed: %s", exc)
                                break
            except Exception as exc:
                logger.error("Heartbeat loop error: %s", exc)
                break
            time.sleep(HEARTBEAT_INTERVAL_S)
        logger.info("ESP32 heartbeat thread stopped.")

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------
    def _simulate_response(self, cmd: str, msg_id: int, params: dict) -> dict:
        """
        Generate a fake response for simulation mode.

        Caller must hold ``self._lock``.
        """
        base: Dict[str, Any] = {"v": PROTOCOL_VERSION, "id": msg_id, "ok": True}

        if cmd == CMD_CONNECT:
            return base

        if cmd == CMD_DISCONNECT:
            return base

        if cmd == CMD_ENABLE:
            self._sim_enabled = True
            return base

        if cmd == CMD_DISABLE:
            self._sim_enabled = False
            return base

        if cmd == CMD_HOME:
            axis = params.get("axis")
            if axis is not None:
                norm_axis = axis - 1 if axis in (1, 2) else axis
                self._sim_positions[norm_axis] = 0.0
                self._sim_homed[norm_axis] = True
            else:
                for i in range(NUM_AXES):
                    self._sim_positions[i] = 0.0
                    self._sim_homed[i] = True
            return base

        if cmd == CMD_STOP:
            return base

        if cmd == CMD_MOVE_ABS:
            axis = params.get("axis", 0)
            norm_axis = axis - 1 if axis in (1, 2) else axis
            target = params.get("target", 0.0)
            self._sim_positions[norm_axis] = target
            logger.debug("Sim MOVE_ABS axis=%d -> %.2f°", norm_axis, target)
            return base

        if cmd == CMD_MOVE_REL:
            axis = params.get("axis", 0)
            norm_axis = axis - 1 if axis in (1, 2) else axis
            delta = params.get("delta", 0.0)
            self._sim_positions[norm_axis] += delta
            logger.debug("Sim MOVE_REL axis=%d Δ %.2f° -> %.2f°", norm_axis, delta, self._sim_positions[norm_axis])
            return base

        if cmd == CMD_GET_STATUS:
            base["connected"] = self._connected
            base["axes"] = [
                {
                    "axis": i + 1,
                    "position": self._sim_positions[i],
                    **(
                        {"position_mm": self._sim_positions[i]}
                        if i == 0
                        else {"position_deg": self._sim_positions[i]}
                    ),
                    "homed": self._sim_homed[i],
                }
                for i in range(NUM_AXES)
            ]
            base["enabled"] = self._sim_enabled
            return base

        if cmd == CMD_HEARTBEAT:
            return base

        # Unknown command
        base["ok"] = False
        base["error"] = f"Unknown command: {cmd}"
        return base

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        mode = "SIM" if self._simulation_mode else "REAL"
        state = "CONNECTED" if self._connected else "DISCONNECTED"
        return f"ESP32Controller({mode}, {state}, port={self._port})"
