"""
UR7e robot controller for the needle teleoperation system.

Supports two operating modes:
  • **Simulation** – all motion is computed locally; no hardware required.
  • **Real** – communicates with a UR7e via the ur_rtde library.

Thread-safe: every public method acquires an internal lock before
reading or mutating state.  The controller does NOT emit Qt signals;
that responsibility belongs to the worker layer above it.
"""

from __future__ import annotations

import copy
import logging
import math
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NUM_JOINTS = 6
TWO_PI = 2.0 * math.pi

# Default safety envelopes (can be overridden per-instance)
DEFAULT_JOINT_LIMITS = [(-TWO_PI, TWO_PI)] * NUM_JOINTS  # (min, max) in rad
DEFAULT_CARTESIAN_LIMITS = {
    "x": (-1.0, 1.0),   # metres
    "y": (-1.0, 1.0),
    "z": (-0.1, 1.0),   # prevent driving into the table
    "rx": (-TWO_PI, TWO_PI),
    "ry": (-TWO_PI, TWO_PI),
    "rz": (-TWO_PI, TWO_PI),
}
CARTESIAN_AXES = ["x", "y", "z", "rx", "ry", "rz"]

DEFAULT_MAX_VELOCITY = 0.5       # rad/s  (conservative fallback)
DEFAULT_MAX_ACCELERATION = 0.5   # rad/s^2


class URController:
    """
    Low-level controller for a Universal Robots UR7e arm.

    Parameters
    ----------
    simulation_mode : bool
        When *True* (the default) all motion is simulated locally.
    max_velocity : float | None
        Maximum allowed joint velocity in rad/s.  ``None`` → use
        ``DEFAULT_MAX_VELOCITY``.
    max_acceleration : float | None
        Maximum allowed joint acceleration in rad/s².  ``None`` → use
        ``DEFAULT_MAX_ACCELERATION``.
    """

    def __init__(
        self,
        simulation_mode: bool = True,
        max_velocity: Optional[float] = None,
        max_acceleration: Optional[float] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._simulation_mode = simulation_mode

        # Safety limits
        self._max_velocity = max_velocity if max_velocity and max_velocity > 0 else DEFAULT_MAX_VELOCITY
        self._max_acceleration = max_acceleration if max_acceleration and max_acceleration > 0 else DEFAULT_MAX_ACCELERATION
        self._joint_limits: List[tuple] = list(DEFAULT_JOINT_LIMITS)
        self._cartesian_limits: dict = dict(DEFAULT_CARTESIAN_LIMITS)

        # Connection handles (real mode only)
        self._rtde_control = None  # RTDEControlInterface
        self._rtde_receive = None  # RTDEReceiveInterface

        # State
        self._connected = False
        self._ip: Optional[str] = None

        # Simulated state
        self._sim_joint_positions: List[float] = [0.0] * NUM_JOINTS
        self._sim_tcp_pose: List[float] = [0.0] * NUM_JOINTS  # [x, y, z, rx, ry, rz]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the controller has an active connection."""
        with self._lock:
            return self._connected

    @property
    def simulation_mode(self) -> bool:
        """Return ``True`` when running in simulation."""
        return self._simulation_mode

    @property
    def max_velocity(self) -> float:
        return self._max_velocity

    @max_velocity.setter
    def max_velocity(self, value: float) -> None:
        if value is not None and value > 0:
            self._max_velocity = value

    @property
    def max_acceleration(self) -> float:
        return self._max_acceleration

    @max_acceleration.setter
    def max_acceleration(self, value: float) -> None:
        if value is not None and value > 0:
            self._max_acceleration = value

    # ------------------------------------------------------------------
    # Limit configuration
    # ------------------------------------------------------------------
    def set_joint_limits(self, limits: List[tuple]) -> None:
        """
        Set per-joint position limits.

        Parameters
        ----------
        limits : list of (min_rad, max_rad) tuples – one per joint.
        """
        if len(limits) != NUM_JOINTS:
            raise ValueError(f"Expected {NUM_JOINTS} joint limits, got {len(limits)}.")
        with self._lock:
            self._joint_limits = list(limits)

    def set_cartesian_limits(self, limits: dict) -> None:
        """
        Set Cartesian workspace limits.

        Parameters
        ----------
        limits : dict  ``{"x": (min, max), "y": ..., "z": ..., ...}``
        """
        with self._lock:
            for key in CARTESIAN_AXES:
                if key in limits:
                    self._cartesian_limits[key] = limits[key]

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self, ip: str) -> bool:
        """
        Open a connection to the robot.

        In simulation mode the connection always succeeds immediately.

        Returns
        -------
        bool
            ``True`` on success.
        """
        with self._lock:
            if self._connected:
                logger.warning("Already connected to %s.", self._ip)
                return True

            self._ip = ip

            if self._simulation_mode:
                self._connected = True
                logger.info("Simulation: connected to %s", ip)
                return True

            # --- Real hardware ---
            try:
                from rtde_control import RTDEControlInterface
                from rtde_receive import RTDEReceiveInterface

                logger.info("Connecting to UR robot at %s …", ip)
                self._rtde_receive = RTDEReceiveInterface(ip)
                self._rtde_control = RTDEControlInterface(ip)
                self._connected = True
                logger.info("Connected to UR robot at %s.", ip)
                return True
            except ImportError:
                logger.error(
                    "ur_rtde is not installed.  Install it with "
                    "'pip install ur_rtde' or enable simulation_mode."
                )
                return False
            except Exception as exc:
                logger.error("Failed to connect to %s: %s", ip, exc)
                self._cleanup_rtde()
                return False

    def disconnect(self) -> None:
        """Close the connection to the robot."""
        with self._lock:
            if not self._connected:
                return

            if self._simulation_mode:
                self._connected = False
                logger.info("Simulation: disconnected from %s", self._ip)
                return

            # --- Real hardware ---
            try:
                self.stop()
            except Exception:
                pass
            self._cleanup_rtde()
            self._connected = False
            logger.info("Disconnected from %s", self._ip)

    def _cleanup_rtde(self) -> None:
        """Release ur_rtde handles (caller must hold the lock)."""
        try:
            if self._rtde_control is not None:
                self._rtde_control.disconnect()
        except Exception:
            pass
        try:
            if self._rtde_receive is not None:
                self._rtde_receive.disconnect()
        except Exception:
            pass
        self._rtde_control = None
        self._rtde_receive = None

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------
    def get_joint_positions(self) -> List[float]:
        """
        Return the current joint positions in radians.

        Returns
        -------
        list of 6 floats
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to robot.")

            if self._simulation_mode:
                return list(self._sim_joint_positions)

            try:
                return list(self._rtde_receive.getActualQ())
            except Exception as exc:
                logger.error("Failed to read joint positions: %s", exc)
                raise

    def get_tcp_pose(self) -> List[float]:
        """
        Return the current TCP pose ``[x, y, z, rx, ry, rz]``.

        Returns
        -------
        list of 6 floats
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to robot.")

            if self._simulation_mode:
                return list(self._sim_tcp_pose)

            try:
                return list(self._rtde_receive.getActualTCPPose())
            except Exception as exc:
                logger.error("Failed to read TCP pose: %s", exc)
                raise

    def get_robot_mode(self) -> int:
        """
        Return the UR robot mode integer.

        In simulation, returns ``7`` (RUNNING).
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to robot.")

            if self._simulation_mode:
                return 7  # ROBOT_MODE_RUNNING

            try:
                return self._rtde_receive.getRobotMode()
            except Exception as exc:
                logger.error("Failed to read robot mode: %s", exc)
                raise

    def get_safety_mode(self) -> int:
        """
        Return the UR safety mode integer.

        In simulation, returns ``1`` (NORMAL).
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to robot.")

            if self._simulation_mode:
                return 1  # SAFETY_MODE_NORMAL

            try:
                return self._rtde_receive.getSafetyMode()
            except Exception as exc:
                logger.error("Failed to read safety mode: %s", exc)
                raise

    # ------------------------------------------------------------------
    # Motion commands
    # ------------------------------------------------------------------
    def _clamp_velocity(self, speed: float) -> float:
        """Clamp *speed* to the configured maximum velocity."""
        return max(0.0, min(abs(speed), self._max_velocity))

    def _clamp_acceleration(self, accel: float) -> float:
        """Clamp *accel* to the configured maximum acceleration."""
        return max(0.0, min(abs(accel), self._max_acceleration))

    def jog_joint(
        self,
        joint_index: int,
        direction: int,
        speed: float = 0.1,
        increment: float = 0.01,
    ) -> bool:
        """
        Move a single joint by *increment* radians in *direction*.

        Parameters
        ----------
        joint_index : int
            0-based joint index (0–5).
        direction : int
            ``+1`` or ``-1``.
        speed : float
            Joint velocity in rad/s (clamped to max_velocity).
        increment : float
            Step size in radians (always positive).

        Returns
        -------
        bool
            ``True`` if the command was accepted.
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to robot.")

            if not (0 <= joint_index < NUM_JOINTS):
                raise ValueError(f"joint_index must be 0–{NUM_JOINTS - 1}, got {joint_index}.")

            direction = 1 if direction >= 0 else -1
            speed = self._clamp_velocity(speed)
            increment = abs(increment)
            delta = direction * increment

            if self._simulation_mode:
                new_pos = self._sim_joint_positions[joint_index] + delta

                # Check joint limits
                lo, hi = self._joint_limits[joint_index]
                if new_pos < lo or new_pos > hi:
                    logger.warning(
                        "Joint %d target %.4f rad exceeds limits [%.4f, %.4f].",
                        joint_index, new_pos, lo, hi,
                    )
                    return False

                self._sim_joint_positions[joint_index] = new_pos
                logger.debug(
                    "Sim jog_joint j%d → %.4f rad (Δ %.4f, v=%.3f)",
                    joint_index, new_pos, delta, speed,
                )
                return True

            # --- Real hardware ---
            try:
                current_q = list(self._rtde_receive.getActualQ())
                target_q = list(current_q)
                target_q[joint_index] += delta

                # Check joint limits
                lo, hi = self._joint_limits[joint_index]
                if target_q[joint_index] < lo or target_q[joint_index] > hi:
                    logger.warning(
                        "Joint %d target %.4f rad exceeds limits [%.4f, %.4f].",
                        joint_index, target_q[joint_index], lo, hi,
                    )
                    return False

                accel = self._clamp_acceleration(self._max_acceleration)
                self._rtde_control.moveJ(target_q, speed, accel, False)
                return True
            except Exception as exc:
                logger.error("jog_joint failed: %s", exc)
                return False

    def jog_cartesian(
        self,
        axis_index: int,
        direction: int,
        speed: float = 0.05,
        increment: float = 0.001,
    ) -> bool:
        """
        Move the TCP along one Cartesian axis by *increment*.

        Parameters
        ----------
        axis_index : int
            0=x, 1=y, 2=z, 3=rx, 4=ry, 5=rz.
        direction : int
            ``+1`` or ``-1``.
        speed : float
            Linear/rotational speed (clamped).
        increment : float
            Step size in metres (xyz) or radians (rotation).

        Returns
        -------
        bool
            ``True`` if the command was accepted.
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to robot.")

            if not (0 <= axis_index < 6):
                raise ValueError(f"axis_index must be 0–5, got {axis_index}.")

            direction = 1 if direction >= 0 else -1
            speed = self._clamp_velocity(speed)
            increment = abs(increment)
            delta = direction * increment
            axis_name = CARTESIAN_AXES[axis_index]

            if self._simulation_mode:
                new_val = self._sim_tcp_pose[axis_index] + delta

                # Check Cartesian limits
                lo, hi = self._cartesian_limits[axis_name]
                if new_val < lo or new_val > hi:
                    logger.warning(
                        "Cartesian %s target %.4f exceeds limits [%.4f, %.4f].",
                        axis_name, new_val, lo, hi,
                    )
                    return False

                self._sim_tcp_pose[axis_index] = new_val
                logger.debug(
                    "Sim jog_cartesian %s → %.4f (Δ %.4f, v=%.3f)",
                    axis_name, new_val, delta, speed,
                )
                return True

            # --- Real hardware ---
            try:
                current_pose = list(self._rtde_receive.getActualTCPPose())
                target_pose = list(current_pose)
                target_pose[axis_index] += delta

                # Check Cartesian limits
                lo, hi = self._cartesian_limits[axis_name]
                if target_pose[axis_index] < lo or target_pose[axis_index] > hi:
                    logger.warning(
                        "Cartesian %s target %.4f exceeds limits [%.4f, %.4f].",
                        axis_name, target_pose[axis_index], lo, hi,
                    )
                    return False

                accel = self._clamp_acceleration(self._max_acceleration)
                self._rtde_control.moveL(target_pose, speed, accel, False)
                return True
            except Exception as exc:
                logger.error("jog_cartesian failed: %s", exc)
                return False

    def stop(self) -> None:
        """
        Immediately stop all robot motion.

        Safe to call whether connected or not.
        """
        with self._lock:
            if not self._connected:
                return

            if self._simulation_mode:
                logger.info("Simulation: motion stopped.")
                return

            try:
                self._rtde_control.stopJ(2.0)  # deceleration rad/s^2
                logger.info("Robot motion stopped.")
            except Exception as exc:
                logger.error("stop() failed: %s", exc)

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        mode = "SIM" if self._simulation_mode else "REAL"
        state = "CONNECTED" if self._connected else "DISCONNECTED"
        return f"URController({mode}, {state}, ip={self._ip})"
