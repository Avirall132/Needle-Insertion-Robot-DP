"""
QThread-based worker for ESP32 communication.

Runs a ~5 Hz polling loop that reads telemetry and status from an
ESP32Controller instance, emitting Qt signals for every state change.
Commands from the GUI thread are passed through a thread-safe queue so the
worker can execute them sequentially on its own thread.

This worker does NOT modify GUI widgets directly.
"""

import logging
import queue
import time
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# Polling interval in seconds (~5 Hz)
_POLL_INTERVAL: float = 0.2


class _CommandType(Enum):
    """Internal command identifiers for the command queue."""
    CONNECT = auto()
    DISCONNECT = auto()
    MOVE_AXIS = auto()
    STOP = auto()
    HOME = auto()
    ENABLE = auto()
    DISABLE = auto()


class ESP32Worker(QThread):
    """
    Background worker that communicates with an ESP32 motor controller.

    Signals
    -------
    status_updated(dict)
        Emitted with a dictionary of current ESP32 status fields.
    connection_changed(bool)
        Emitted when the serial connection state changes.
    error_occurred(str)
        Emitted when an error is encountered.
    command_response(dict)
        Emitted with the response payload of a command.
    telemetry_received(dict)
        Emitted with incoming telemetry data (positions, limits, etc.).
    """

    # ---- Qt signals --------------------------------------------------
    status_updated = Signal(dict)
    connection_changed = Signal(bool)
    error_occurred = Signal(str)
    command_response = Signal(dict)
    telemetry_received = Signal(dict)

    def __init__(self, controller: Any, parent: Optional[Any] = None) -> None:
        """
        Args:
            controller: An ESP32Controller instance that provides:
                connect(port, baud) -> bool
                disconnect()
                is_connected -> bool
                get_status() -> dict | None
                get_telemetry() -> dict | None
                move_axis(axis, position, speed) -> dict | None
                stop() -> dict | None
                home(axis) -> dict | None
                enable() -> dict | None
                disable() -> dict | None
            parent: Optional QObject parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._command_queue: queue.Queue[Tuple[_CommandType, Dict[str, Any]]] = queue.Queue()
        self._running: bool = False

        # Cached state for change detection
        self._prev_status: Optional[Dict[str, Any]] = None
        self._prev_connected: Optional[bool] = None

        logger.info("ESP32Worker initialized")

    # ------------------------------------------------------------------
    # Public thread-safe command methods
    # ------------------------------------------------------------------

    def connect_device(self, port: str, baud: int = 115200) -> None:
        """Enqueue a CONNECT command."""
        self._command_queue.put(
            (_CommandType.CONNECT, {"port": port, "baud": baud})
        )

    def disconnect_device(self) -> None:
        """Enqueue a DISCONNECT command."""
        self._command_queue.put((_CommandType.DISCONNECT, {}))

    def move_axis(
        self,
        axis: int,
        position: float,
        speed: float = 1.0,
    ) -> None:
        """
        Enqueue a MOVE_AXIS command.

        Args:
            axis:     Axis identifier (0-based).
            position: Target position (units depend on ESP32 firmware).
            speed:    Movement speed factor.
        """
        self._command_queue.put(
            (
                _CommandType.MOVE_AXIS,
                {"axis": axis, "position": position, "speed": speed},
            )
        )

    def stop_device(self) -> None:
        """Enqueue a STOP command."""
        self._command_queue.put((_CommandType.STOP, {}))

    def home(self, axis: Optional[int] = None) -> None:
        """
        Enqueue a HOME command.

        Args:
            axis: Axis to home, or None to home all axes.
        """
        self._command_queue.put((_CommandType.HOME, {"axis": axis}))

    def enable(self) -> None:
        """Enqueue an ENABLE command (enable motor drivers)."""
        self._command_queue.put((_CommandType.ENABLE, {}))

    def disable(self) -> None:
        """Enqueue a DISABLE command (disable motor drivers)."""
        self._command_queue.put((_CommandType.DISABLE, {}))

    def request_stop(self) -> None:
        """Request the worker thread to stop its run loop."""
        self._running = False

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Main worker loop.

        Processes queued commands, then polls ESP32 status and telemetry,
        emitting signals for any changes. Runs at approximately 5 Hz.
        """
        self._running = True
        logger.info("ESP32Worker thread started")

        while self._running:
            loop_start = time.monotonic()

            # --- Process all pending commands -------------------------
            self._process_commands()

            # --- Poll device state if connected -----------------------
            self._poll_state()

            # --- Maintain ~5 Hz loop rate -----------------------------
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.0, _POLL_INTERVAL - elapsed)
            if sleep_time > 0:
                deadline = time.monotonic() + sleep_time
                while self._running and time.monotonic() < deadline:
                    time.sleep(min(0.01, deadline - time.monotonic()))

        # Cleanup on exit
        try:
            if self._controller.is_connected:
                self._controller.disconnect()
                self.connection_changed.emit(False)
        except Exception as exc:
            logger.warning("Error during ESP32Worker cleanup: %s", exc)

        logger.info("ESP32Worker thread stopped")

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
                    self._handle_connect(params["port"], params["baud"])
                elif cmd_type == _CommandType.DISCONNECT:
                    self._handle_disconnect()
                elif cmd_type == _CommandType.MOVE_AXIS:
                    self._handle_move_axis(
                        params["axis"],
                        params["position"],
                        params["speed"],
                    )
                elif cmd_type == _CommandType.STOP:
                    self._handle_stop()
                elif cmd_type == _CommandType.HOME:
                    self._handle_home(params.get("axis"))
                elif cmd_type == _CommandType.ENABLE:
                    self._handle_enable()
                elif cmd_type == _CommandType.DISABLE:
                    self._handle_disable()
            except Exception as exc:
                error_msg = f"ESP32Worker command error ({cmd_type.name}): {exc}"
                logger.exception(error_msg)
                self.error_occurred.emit(error_msg)

    # ---- individual command handlers ---------------------------------

    def _handle_connect(self, port: str, baud: int) -> None:
        logger.info("ESP32Worker connecting to %s @ %d baud", port, baud)
        try:
            success = self._controller.connect(port, baud)
            self.connection_changed.emit(success)
            if not success:
                self.error_occurred.emit(
                    f"Failed to connect to ESP32 on {port} @ {baud}"
                )
        except Exception as exc:
            self.connection_changed.emit(False)
            self.error_occurred.emit(f"ESP32 connection error: {exc}")

    def _handle_disconnect(self) -> None:
        logger.info("ESP32Worker disconnecting")
        try:
            self._controller.disconnect()
        except Exception as exc:
            logger.warning("Error during ESP32 disconnect: %s", exc)
        self.connection_changed.emit(False)

    def _handle_move_axis(
        self, axis: int, position: float, speed: float
    ) -> None:
        if not self._controller.is_connected:
            self.error_occurred.emit("Cannot move – ESP32 not connected")
            return
        response = self._controller.move_axis(axis, position, speed)
        if response is not None:
            self.command_response.emit(response)

    def _handle_stop(self) -> None:
        if not self._controller.is_connected:
            return
        try:
            response = self._controller.stop()
            if response is not None:
                self.command_response.emit(response)
        except Exception as exc:
            self.error_occurred.emit(f"ESP32 stop command failed: {exc}")

    def _handle_home(self, axis: Optional[int]) -> None:
        if not self._controller.is_connected:
            self.error_occurred.emit("Cannot home – ESP32 not connected")
            return
        try:
            response = self._controller.home(axis)
            if response is not None:
                self.command_response.emit(response)
        except Exception as exc:
            self.error_occurred.emit(f"ESP32 home command failed: {exc}")

    def _handle_enable(self) -> None:
        if not self._controller.is_connected:
            self.error_occurred.emit("Cannot enable – ESP32 not connected")
            return
        try:
            response = self._controller.enable()
            if response is not None:
                self.command_response.emit(response)
        except Exception as exc:
            self.error_occurred.emit(f"ESP32 enable command failed: {exc}")

    def _handle_disable(self) -> None:
        if not self._controller.is_connected:
            self.error_occurred.emit("Cannot disable – ESP32 not connected")
            return
        try:
            response = self._controller.disable()
            if response is not None:
                self.command_response.emit(response)
        except Exception as exc:
            self.error_occurred.emit(f"ESP32 disable command failed: {exc}")

    # ------------------------------------------------------------------
    # State polling
    # ------------------------------------------------------------------

    def _poll_state(self) -> None:
        """Read ESP32 state and emit signals when values change."""
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

        # Status
        try:
            status = self._controller.get_status()
            if status is not None and status != self._prev_status:
                self._prev_status = dict(status)
                self.status_updated.emit(dict(status))
        except Exception as exc:
            logger.debug("Failed to read ESP32 status: %s", exc)

        # Telemetry
        try:
            telemetry = self._controller.get_telemetry()
            if telemetry is not None:
                self.telemetry_received.emit(dict(telemetry))
        except Exception as exc:
            logger.debug("Failed to read ESP32 telemetry: %s", exc)
