"""
Configuration management module for the needle robot teleoperation system.

Provides a thread-safe singleton Config class that loads/saves settings
from a JSON file. Creates a default configuration if none exists.
All safety-critical parameters default to None (null) until explicitly set.
"""

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default config file path (next to this module)
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class RobotConfig:
    """UR robot connection and motion settings."""
    ip: Optional[str] = None
    enabled: bool = False
    max_velocity: Optional[float] = None  # rad/s - must be explicitly set
    max_acceleration: Optional[float] = None  # rad/s^2 - must be explicitly set


@dataclass
class ESP32Config:
    """ESP32 end-effector serial connection settings."""
    serial_port: Optional[str] = None
    baud_rate: int = 115200
    enabled: bool = False


@dataclass
class CameraConfig:
    """Camera capture settings."""
    index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30


@dataclass
class VisionConfig:
    """Computer vision / model settings."""
    model_path: Optional[str] = None
    confidence_threshold: float = 0.5
    enabled: bool = False


@dataclass
class ApplicationConfig:
    """Top-level application behaviour settings."""
    simulation_mode: bool = True
    log_level: str = "INFO"


@dataclass
class ConfigData:
    """Aggregate of every configuration section."""
    robot: RobotConfig = field(default_factory=RobotConfig)
    esp32: ESP32Config = field(default_factory=ESP32Config)
    camera: CameraConfig = field(default_factory=CameraConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    application: ApplicationConfig = field(default_factory=ApplicationConfig)


class Config:
    """
    Thread-safe singleton configuration manager.

    Usage::

        cfg = Config()              # first call creates the singleton
        cfg = Config.instance()     # explicit accessor

        sim = cfg.application.simulation_mode
        cfg.robot.ip = "192.168.1.10"
        cfg.save()
    """

    _instance: Optional["Config"] = None
    _lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------
    def __new__(cls, config_path: Optional[Path] = None) -> "Config":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._initialized = False
                cls._instance = obj
            return cls._instance

    def __init__(self, config_path: Optional[Path] = None) -> None:
        with self._lock:
            if self._initialized:
                return
            self._config_path: Path = config_path or DEFAULT_CONFIG_PATH
            self._data = ConfigData()
            self._file_lock = threading.Lock()
            self._load()
            self._initialized = True

    @classmethod
    def instance(cls) -> "Config":
        """Return the existing singleton (creates one with defaults if needed)."""
        if cls._instance is None:
            return cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton – only useful in tests."""
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Section accessors (typed)
    # ------------------------------------------------------------------
    @property
    def robot(self) -> RobotConfig:
        return self._data.robot

    @property
    def esp32(self) -> ESP32Config:
        return self._data.esp32

    @property
    def camera(self) -> CameraConfig:
        return self._data.camera

    @property
    def vision(self) -> VisionConfig:
        return self._data.vision

    @property
    def application(self) -> ApplicationConfig:
        return self._data.application

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load configuration from JSON, creating a default file if absent."""
        with self._file_lock:
            if not self._config_path.exists():
                logger.info("No config file found at %s – creating defaults.", self._config_path)
                self._save_internal()
                return
            try:
                raw = self._config_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                self._apply_dict(data)
                self._validate()
                logger.info("Configuration loaded from %s", self._config_path)
            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON in %s: %s – using defaults.", self._config_path, exc)
                self._data = ConfigData()
            except Exception as exc:
                logger.error("Failed to load config: %s – using defaults.", exc)
                self._data = ConfigData()

    def save(self) -> None:
        """Persist current configuration to disk."""
        with self._file_lock:
            self._save_internal()

    def _save_internal(self) -> None:
        """Write current state to JSON (caller must hold _file_lock)."""
        try:
            payload = asdict(self._data)
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(
                json.dumps(payload, indent=4, default=str) + "\n",
                encoding="utf-8",
            )
            logger.info("Configuration saved to %s", self._config_path)
        except Exception as exc:
            logger.error("Failed to save config: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _apply_dict(self, data: dict) -> None:
        """Merge a raw dict into the typed dataclass hierarchy."""
        if "robot" in data and isinstance(data["robot"], dict):
            self._update_dataclass(self._data.robot, data["robot"])
        if "esp32" in data and isinstance(data["esp32"], dict):
            self._update_dataclass(self._data.esp32, data["esp32"])
        if "camera" in data and isinstance(data["camera"], dict):
            self._update_dataclass(self._data.camera, data["camera"])
        if "vision" in data and isinstance(data["vision"], dict):
            self._update_dataclass(self._data.vision, data["vision"])
        if "application" in data and isinstance(data["application"], dict):
            self._update_dataclass(self._data.application, data["application"])

    @staticmethod
    def _update_dataclass(dc: object, values: dict) -> None:
        """Set only those keys that already exist on the dataclass."""
        for key, value in values.items():
            if hasattr(dc, key):
                setattr(dc, key, value)

    def _validate(self) -> None:
        """
        Sanity-check loaded values.
        Resets obviously invalid values to safe defaults.
        """
        # Baud rate must be positive
        if self._data.esp32.baud_rate <= 0:
            logger.warning("Invalid baud_rate %s – resetting to 115200.", self._data.esp32.baud_rate)
            self._data.esp32.baud_rate = 115200

        # Camera dimensions must be positive
        for attr in ("width", "height", "fps"):
            val = getattr(self._data.camera, attr)
            if not isinstance(val, int) or val <= 0:
                logger.warning("Invalid camera.%s=%s – resetting.", attr, val)
                setattr(self._data.camera, attr, {"width": 640, "height": 480, "fps": 30}[attr])

        # Confidence threshold must be in [0, 1]
        if not (0.0 <= self._data.vision.confidence_threshold <= 1.0):
            logger.warning(
                "confidence_threshold %.3f out of range – clamping to 0.5.",
                self._data.vision.confidence_threshold,
            )
            self._data.vision.confidence_threshold = 0.5

        # Log level must be a recognised name
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self._data.application.log_level.upper() not in valid_levels:
            logger.warning(
                "Unknown log_level '%s' – resetting to INFO.",
                self._data.application.log_level,
            )
            self._data.application.log_level = "INFO"

        # Safety-critical parameters stay None until explicitly provided
        if self._data.robot.max_velocity is not None and self._data.robot.max_velocity <= 0:
            logger.warning("max_velocity must be positive – resetting to None.")
            self._data.robot.max_velocity = None

        if self._data.robot.max_acceleration is not None and self._data.robot.max_acceleration <= 0:
            logger.warning("max_acceleration must be positive – resetting to None.")
            self._data.robot.max_acceleration = None

    def __repr__(self) -> str:
        return f"Config({asdict(self._data)})"
