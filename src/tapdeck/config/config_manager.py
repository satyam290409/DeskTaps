"""Configuration management module for TapDeck.

Handles loading, validating, backing up, and migrating configuration files
including trigger bindings, audio preferences, and calibration profiles.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR: Path = Path(os.environ.get("LOCALAPPDATA", ".")) / "TapDeck"
SCHEMA_VERSION: int = 1

ALL_TRIGGERS: frozenset[str] = frozenset(
    {
        "SINGLE_LT",
        "SINGLE_LB",
        "SINGLE_RT",
        "SINGLE_RB",
        "DUAL_LT_RT",
        "DUAL_LB_RB",
        "DUAL_LT_RB",
        "DUAL_LB_RT",
    }
)

VALID_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "hotkey",
        "media_key",
        "media_play_pause",
        "launch_app",
        "shell_command",
        "test_mode",
    }
)


class ConfigManager:
    """Thread-safe configuration manager for application state and preferences."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize ConfigManager.

        Args:
            config_dir: Root directory for TapDeck configuration and profile data.
        """
        self._config_dir = Path(config_dir) if config_dir is not None else CONFIG_DIR
        self._lock = threading.Lock()
        self.ensure_dirs()

    @property
    def config_dir(self) -> Path:
        """Config directory path."""
        return self._config_dir

    def ensure_dirs(self) -> None:
        """Create configuration directories if they do not exist."""
        with self._lock:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            (self._config_dir / "calibration").mkdir(parents=True, exist_ok=True)
            (self._config_dir / "recordings").mkdir(parents=True, exist_ok=True)
            (self._config_dir / "logs").mkdir(parents=True, exist_ok=True)

    def get_default_bindings(self) -> dict[str, Any]:
        """Return the 8 default bindings defined by the TapDeck specification.

        Returns:
            Dictionary matching the bindings schema.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "bindings": {
                "SINGLE_LT": {
                    "action_type": "media_key",
                    "params": {"media_key": "volume_up"},
                },
                "SINGLE_LB": {
                    "action_type": "media_key",
                    "params": {"media_key": "volume_down"},
                },
                "SINGLE_RT": {
                    "action_type": "media_key",
                    "params": {"media_key": "play_pause"},
                },
                "SINGLE_RB": {
                    "action_type": "media_key",
                    "params": {"media_key": "mute"},
                },
                "DUAL_LT_RT": {
                    "action_type": "hotkey",
                    "params": {"keys": ["win", "tab"]},
                },
                "DUAL_LB_RB": {
                    "action_type": "hotkey",
                    "params": {"keys": ["win", "d"]},
                },
                "DUAL_LT_RB": {
                    "action_type": "launch_app",
                    "params": {"executable": "calc.exe", "args": []},
                },
                "DUAL_LB_RT": {
                    "action_type": "launch_app",
                    "params": {"executable": "notepad.exe", "args": []},
                },
            },
        }

    def load_bindings(self) -> dict[str, Any]:
        """Load and validate bindings.json.

        If the file does not exist, creates it with default bindings.
        Automatically migrates older schema versions.

        Returns:
            Validated configuration dictionary.
        """
        with self._lock:
            bindings_path = self._config_dir / "bindings.json"
            if not bindings_path.exists():
                defaults = self.get_default_bindings()
                self._save_json_atomic(bindings_path, defaults)
                return defaults

            try:
                with open(bindings_path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                logger.error("Failed to parse %s: %s; falling back to defaults", bindings_path, exc)
                return self.get_default_bindings()

            # Handle migrations
            file_version = data.get("schema_version", 1)
            if file_version < SCHEMA_VERSION:
                logger.info(
                    "Migrating bindings from version %d to %d", file_version, SCHEMA_VERSION
                )
                data = self._migrate_config(data, from_version=file_version)
                self._backup_file(bindings_path)
                self._save_json_atomic(bindings_path, data)

            valid, errors = self._validate_bindings(data)
            if not valid:
                logger.warning("Bindings validation warnings: %s", errors)

            return data

    def save_bindings(self, bindings: dict[str, Any]) -> None:
        """Validate and save bindings to bindings.json with automatic backup.

        Args:
            bindings: Configuration dictionary to save.

        Raises:
            ValueError: If bindings data fails schema validation.
        """
        with self._lock:
            valid, errors = self._validate_bindings(bindings)
            if not valid:
                raise ValueError(f"Invalid bindings configuration: {'; '.join(errors)}")

            # Ensure schema_version is set
            data_to_save = dict(bindings)
            data_to_save["schema_version"] = SCHEMA_VERSION

            bindings_path = self._config_dir / "bindings.json"
            if bindings_path.exists():
                self._backup_file(bindings_path)

            self._save_json_atomic(bindings_path, data_to_save)
            logger.info("Saved bindings configuration to %s", bindings_path)

    def load_audio_prefs(self) -> dict[str, Any]:
        """Load device audio preferences from audio_prefs.json.

        Returns:
            Dictionary with device preferences.
        """
        with self._lock:
            prefs_path = self._config_dir / "audio_prefs.json"
            default_prefs = {
                "schema_version": SCHEMA_VERSION,
                "device_name": None,
                "device_index": None,
                "sample_rate": 48000,
                "channels": 2,
                "buffer_size": 256,
            }

            if not prefs_path.exists():
                return default_prefs

            try:
                with open(prefs_path, encoding="utf-8") as f:
                    data = json.load(f)
                    return {**default_prefs, **data}
            except Exception as exc:
                logger.warning("Could not read %s: %s; returning defaults", prefs_path, exc)
                return default_prefs

    def save_audio_prefs(self, prefs: dict[str, Any]) -> None:
        """Save audio device preferences with automatic backup.

        Args:
            prefs: Preferences dictionary.
        """
        with self._lock:
            prefs_path = self._config_dir / "audio_prefs.json"
            if prefs_path.exists():
                self._backup_file(prefs_path)

            data_to_save = dict(prefs)
            data_to_save["schema_version"] = SCHEMA_VERSION
            self._save_json_atomic(prefs_path, data_to_save)
            logger.info("Saved audio preferences to %s", prefs_path)

    def load_calibration(self, profile_name: str) -> dict[str, Any] | None:
        """Load a calibration profile by name.

        Args:
            profile_name: Name of profile (without extension).

        Returns:
            Dictionary containing calibration profile data, or None if not found.
        """
        with self._lock:
            clean_name = Path(profile_name).stem
            path = self._config_dir / "calibration" / f"{clean_name}.json"
            if not path.exists():
                logger.warning("Calibration profile not found: %s", path)
                return None

            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.error("Failed to read calibration file %s: %s", path, exc)
                return None

    def save_calibration(self, profile_name: str, data: dict[str, Any]) -> None:
        """Save a calibration profile to disk.

        Args:
            profile_name: Name of the profile.
            data: Calibration data dictionary.
        """
        with self._lock:
            clean_name = Path(profile_name).stem
            cal_dir = self._config_dir / "calibration"
            cal_dir.mkdir(parents=True, exist_ok=True)

            path = cal_dir / f"{clean_name}.json"
            if path.exists():
                self._backup_file(path)

            self._save_json_atomic(path, data)
            logger.info("Saved calibration profile %s to %s", profile_name, path)

    def list_calibration_profiles(self) -> list[str]:
        """List all available calibration profile names.

        Returns:
            List of profile name strings.
        """
        with self._lock:
            cal_dir = self._config_dir / "calibration"
            if not cal_dir.exists():
                return []
            return sorted([p.stem for p in cal_dir.glob("*.json")])

    def validate_bindings(self, bindings: dict[str, Any]) -> bool:
        """Public validation method returning True if valid, False otherwise."""
        valid, _ = self._validate_bindings(bindings)
        return valid

    def _validate_bindings(self, bindings: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate structure and parameters of bindings configuration.

        Args:
            bindings: Configuration dictionary to validate.

        Returns:
            Tuple of (is_valid, list_of_error_strings).
        """
        errors: list[str] = []

        # Validate schema version
        ver = bindings.get("schema_version", 1)
        if isinstance(ver, (int, float)) and ver > SCHEMA_VERSION:
            return False, [
                f"Unsupported schema version {ver} (maximum supported is {SCHEMA_VERSION})"
            ]

        mapping = bindings.get("bindings", bindings)

        if not isinstance(mapping, dict):
            return False, ["Root configuration must contain a 'bindings' dictionary"]

        # Check all 8 required triggers are present
        missing_triggers = ALL_TRIGGERS - set(mapping.keys())
        if missing_triggers:
            errors.append(f"Missing required triggers: {', '.join(sorted(missing_triggers))}")

        # Validate each trigger's action config
        for trigger, action in mapping.items():
            if not isinstance(action, dict):
                errors.append(f"Trigger '{trigger}' must map to a dictionary")
                continue

            action_type = action.get("action_type") or action.get("action")
            is_valid_type = action_type in VALID_ACTION_TYPES or (
                isinstance(action_type, str) and action_type.startswith("media_")
            )
            if not action_type or not is_valid_type:
                errors.append(
                    f"Trigger '{trigger}' has invalid action_type '{action_type}'. "
                    f"Must be one of: {', '.join(sorted(VALID_ACTION_TYPES))}"
                )
                continue

            params = action.get("params")
            if params is not None and not isinstance(params, dict):
                errors.append(f"Trigger '{trigger}' 'params' must be a dictionary")
                continue
            params = params or {}

            # Validate specific action parameters
            if action_type == "hotkey":
                keys = params.get("keys")
                if not isinstance(keys, list) or len(keys) == 0:
                    errors.append(f"Hotkey for '{trigger}' must include non-empty 'keys' list")
            elif action_type == "media_key" and not action_type.startswith("media_"):
                mk = params.get("media_key")
                if not isinstance(mk, str) or not mk.strip():
                    errors.append(
                        f"Media key for '{trigger}' must have non-empty 'media_key' string"
                    )
            elif action_type == "launch_app":
                exe = params.get("executable")
                if not isinstance(exe, str) or not exe.strip():
                    errors.append(f"Launch app for '{trigger}' must specify 'executable'")
            elif action_type == "shell_command":
                cmd = params.get("command")
                if not isinstance(cmd, str) or not cmd.strip():
                    errors.append(f"Shell command for '{trigger}' must specify 'command'")

        return len(errors) == 0, errors

    def _backup_file(self, filepath: Path) -> None:
        """Create a timestamped backup copy of a file before overwriting.

        Args:
            filepath: Path of file to back up.
        """
        if not filepath.exists():
            return

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filepath.stem}_{ts}{filepath.suffix}.bak"
        backup_path = filepath.parent / backup_name
        try:
            shutil.copy2(filepath, backup_path)
            logger.debug("Created backup: %s", backup_path)
        except OSError as exc:
            logger.warning("Failed to create backup for %s: %s", filepath, exc)

    def _migrate_config(self, config: dict[str, Any], from_version: int) -> dict[str, Any]:
        """Migrate configuration data from an older schema version to current.

        Args:
            config: Original configuration dictionary.
            from_version: Source schema version integer.

        Returns:
            Migrated configuration dictionary.
        """
        migrated = dict(config)
        # Handle sequential migrations up to SCHEMA_VERSION
        if from_version < 1:
            # Upgrade pre-1.0 configs if necessary
            migrated.setdefault("schema_version", 1)
            migrated.setdefault("bindings", {})

        migrated["schema_version"] = SCHEMA_VERSION
        return migrated

    def _save_json_atomic(self, path: Path, data: dict[str, Any]) -> None:
        """Atomically write dictionary as JSON to disk using temporary file.

        Args:
            path: Target destination path.
            data: Data dictionary to serialize.
        """
        temp_path = path.with_suffix(f".tmp_{os.getpid()}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(path)
        except Exception:
            if temp_path.exists():
                with contextlib.suppress(OSError):
                    temp_path.unlink()
            raise
