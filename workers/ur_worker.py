"""
QThread-based worker for Universal Robots UR7e communication.

Runs a ~10 Hz polling loop that reads joint positions, TCP pose, robot mode,
and safety mode from a URController instance, emitting Qt signals for every
state change. Commands from the GUI thread are passed through a thread-safe
queue so the worker can execute them sequentially on its own thread.

This worker does NOT modify GUI widgets directly.
"""

import logging
import queue
import time
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# Polling interval in seconds (~10 Hz)
_POLL_INTERVAL: float = 0.1


class _CommandType(Enum):
    """Internal command identifiers for the command queue."""
    CONNECT = auto()
    DISCONNECT = auto()
    JOG_JOINT = auto()
    JOG_CARTESIAN = auto()
    STOP = auto()


class URWorker(QThread):
    """
    Background worker that communicates with a UR7e robot via a URController
    instance.

    Signals
    -------
    joint_positions_updated(list)
        Emitted with a list of 6 joint angles (radians).
    tcp_pose_updated(list)
        Emitted with a list of 6 TCP pose values [x, y, z, rx, ry, rz].
    connection_changed(bool)
        Emitted when the connection state changes.
    robot_mode_changed(str)
        Emitted when the robot mode changes (e.g. "RUNNING", "IDLE").
    safety_mode_changed(str)
        Emitted when the safety mode changes (e.g. "NORMAL", "PROTECTIVE_STOP").
    error_occurred(str)
        Emitted when an error is encountered.
    motion_status_changed(str)
        Emitted when the motion status changes (e.g. "MOVING", "STOPPED").
    """

    # ---- Qt signals --------------------------------------------------
    joint_positions_updated = Signal(list)
    tcp_pose_updated = Signal(list)
    connection_changed = Signal(bool)
    robot_mode_changed = Signal(str)
    safety_mode_changed = Signal(str)
    error_occurred = Signal(str)
    motion_status_changed = Signal(str)

    def __init__(self, controller: Any, parent: Optional[Any] = None) -> None:
        """
        Args:
            controller: A URController instance that provides:
                connect(ip) -> bool
                disconnect()
                is_connected -> bool
                get_joint_positions() -> list[float]
                get_tcp_pose() -> list[float]
                get_robot_mode() -> str
                get_safety_mode() -> str
                jog_joint(joint_index, direction, speed)
                jog_cartesian(axis, direction, speed)
                stop()
            parent: Optional QObject parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._command_queue: queue.Queue[Tuple[_CommandType, Dict[str, Any]]] = queue.Queue()
        self._running: bool = False

        # Cached state for change detection
        self._prev_joint_positions: Optional[List[float]] = None
        self._prev_tcp_pose: Optional[List[float]] = None
        self._prev_robot_mode: Optional[str] = None
        self._prev_safety_mode: Optional[str] = None
        self._prev_connected: Optional[bool] = None
        self._prev_motion_status: Optional[str] = None

        logger.info("URWorker initialized")

    # ------------------------------------------------------------------
    # Public thread-safe command methods
    # ------------------------------------------------------------------

    def connect_robot(self, ip: str) -> None:
        """Enqueue a CONNECT command."""
        self._command_queue.put((_CommandType.CONNECT, {"ip": ip}))

    def disconnect_robot(self) -> None:
        """Enqueue a DISCONNECT command."""
        self._command_queue.put((_CommandType.DISCONNECT, {}))

    def jog_joint(
        self, joint_index: int, direction: float, speed: float = 0.1
    ) -> None:
        """
        Enqueue a JOG_JOINT command.

        Args:
            joint_index: 0-based joint index (0–5).
            direction:   +1.0 or -1.0.
            speed:       Joint speed in rad/s.
        """
        self._command_queue.put(
            (
                _CommandType.JOG_JOINT,
                {"joint_index": joint_index, "direction": direction, "speed": speed},
            )
        )

    def jog_cartesian(
        self, axis: int, direction: float, speed: float = 0.01
    ) -> None:
        """
        Enqueue a JOG_CARTESIAN command.

        Args:
            axis:      0=X, 1=Y, 2=Z, 3=RX, 4=RY, 5=RZ.
            direction: +1.0 or -1.0.
            speed:     Linear speed in m/s (or rad/s for rotation).
        """
        self._command_queue.put(
            (
                _CommandType.JOG_CARTESIAN,
                {"axis": axis, "direction": direction, "speed": speed},
            )
        )

    def stop_robot(self) -> None:
        """Enqueue a STOP command."""
        self._command_queue.put((_CommandType.STOP, {}))

    def request_stop(self) -> None:
        """Request the worker thread to stop its run loop."""
        self._running = False

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Main worker loop.

        Processes queued commands, then polls robot state and emits signals
        for any changes. Runs at approximately 10 Hz.
        """
        self._running = True
        logger.info("URWorker thread started")

        while self._running:
            loop_start = time.monotonic()

            # --- Process all pending commands -------------------------
            self._process_commands()

            # --- Poll robot state if connected ------------------------
            self._poll_state()

            # --- Maintain ~10 Hz loop rate ----------------------------
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.0, _POLL_INTERVAL - elapsed)
            if sleep_time > 0:
                # Sleep in small increments so we can exit quickly
                deadline = time.monotonic() + sleep_time
                while self._running and time.monotonic() < deadline:
                    time.sleep(min(0.01, deadline - time.monotonic()))

        # Cleanup on exit
        try:
            if self._controller.is_connected:
                self._controller.disconnect()
                self.connection_changed.emit(False)
        except Exception as exc:
            logger.warning("Error during URWorker cleanup: %s", exc)

        logger.info("URWorker thread stopped")

    # ------------------------------------------------------------------
    # Command processing
    # ------------------------------------------------------------------

    def _process_commands(self) -> None:
        """Drain the command queue and execute each command."""
        while not self._command_queue.empty():
            try:
                cmd_type, params = self._command_queue.get_nowait()
            except queue.Empty:
                break

            try:
                if cmd_type == _CommandType.CONNECT:
                    self._handle_connect(params["ip"])
                elif cmd_type == _CommandType.DISCONNECT:
                    self._handle_disconnect()
                elif cmd_type == _CommandType.JOG_JOINT:
                    self._handle_jog_joint(
                        params["joint_index"],
                        params["direction"],
                        params["speed"],
                    )
                elif cmd_type == _CommandType.JOG_CARTESIAN:
                    self._handle_jog_cartesian(
                        params["axis"],
                        params["direction"],
                        params["speed"],
                    )
                elif cmd_type == _CommandType.STOP:
                    self._handle_stop()
            except Exception as exc:
                error_msg = f"URWorker command error ({cmd_type.name}): {exc}"
                logger.exception(error_msg)
                self.error_occurred.emit(error_msg)

    # ---- individual command handlers ---------------------------------

    def _handle_connect(self, ip: str) -> None:
        logger.info("URWorker connecting to %s", ip)
        try:
            success = self._controller.connect(ip)
            self.connection_changed.emit(success)
            if not success:
                self.error_occurred.emit(f"Failed to connect to UR robot at {ip}")
        except Exception as exc:
            self.connection_changed.emit(False)
            self.error_occurred.emit(f"Connection error: {exc}")

    def _handle_disconnect(self) -> None:
        logger.info("URWorker disconnecting")
        try:
            self._controller.disconnect()
        except Exception as exc:
            logger.warning("Error during disconnect: %s", exc)
        self.connection_changed.emit(False)

    def _handle_jog_joint(
        self, joint_index: int, direction: float, speed: float
    ) -> None:
        if not self._controller.is_connected:
            self.error_occurred.emit("Cannot jog – robot not connected")
            return
        self._controller.jog_joint(joint_index, direction, speed)
        self.motion_status_changed.emit("MOVING")

    def _handle_jog_cartesian(
        self, axis: int, direction: float, speed: float
    ) -> None:
        if not self._controller.is_connected:
            self.error_occurred.emit("Cannot jog – robot not connected")
            return
        self._controller.jog_cartesian(axis, direction, speed)
        self.motion_status_changed.emit("MOVING")

    def _handle_stop(self) -> None:
        if not self._controller.is_connected:
            return
        try:
            self._controller.stop()
        except Exception as exc:
            self.error_occurred.emit(f"Stop command failed: {exc}")
        self.motion_status_changed.emit("STOPPED")

    # ------------------------------------------------------------------
    # State polling
    # ------------------------------------------------------------------

    def _poll_state(self) -> None:
        """Read robot state and emit signals when values change."""
        try:
            connected = self._controller.is_connected
        except Exception:
            connected = False

        # Emit connection change
        if connected != self._prev_connected:
            self._prev_connected = connected
            self.connection_changed.emit(connected)

        if not connected:
            return

        # Joint positions
        try:
            joints = self._controller.get_joint_positions()
            if joints is not None and joints != self._prev_joint_positions:
                self._prev_joint_positions = list(joints)
                self.joint_positions_updated.emit(list(joints))
        except Exception as exc:
            logger.debug("Failed to read joint positions: %s", exc)

        # TCP pose
        try:
            tcp = self._controller.get_tcp_pose()
            if tcp is not None and tcp != self._prev_tcp_pose:
                self._prev_tcp_pose = list(tcp)
                self.tcp_pose_updated.emit(list(tcp))
        except Exception as exc:
            logger.debug("Failed to read TCP pose: %s", exc)

        # Robot mode
        try:
            mode = self._controller.get_robot_mode()
            if mode is not None and mode != self._prev_robot_mode:
                self._prev_robot_mode = mode
                self.robot_mode_changed.emit(str(mode))
        except Exception as exc:
            logger.debug("Failed to read robot mode: %s", exc)

        # Safety mode
        try:
            safety = self._controller.get_safety_mode()
            if safety is not None and safety != self._prev_safety_mode:
                self._prev_safety_mode = safety
                self.safety_mode_changed.emit(str(safety))
        except Exception as exc:
            logger.debug("Failed to read safety mode: %s", exc)
