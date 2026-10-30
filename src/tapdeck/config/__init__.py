"""Configuration management with validation and migration."""

from tapdeck.config.config_manager import (
    CONFIG_DIR,
    SCHEMA_VERSION,
    ConfigManager,
)

__all__ = [
    "CONFIG_DIR",
    "ConfigManager",
    "SCHEMA_VERSION",
]
