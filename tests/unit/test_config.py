"""Unit tests for TapDeck configuration manager and schema validation."""

import copy

import pytest

from tapdeck.config.config_manager import ConfigManager


def test_default_config_generation(tmp_config_dir) -> None:
    """ConfigManager creates valid default bindings configuration."""
    manager = ConfigManager(config_dir=tmp_config_dir)
    defaults = (
        manager.get_default_bindings()
        if hasattr(manager, "get_default_bindings")
        else manager.default_bindings
    )

    assert defaults is not None
    assert "bindings" in defaults
    expected_triggers = [
        "SINGLE_LT",
        "SINGLE_LB",
        "SINGLE_RT",
        "SINGLE_RB",
        "DUAL_LT_RT",
        "DUAL_LB_RB",
        "DUAL_LT_RB",
        "DUAL_LB_RT",
    ]
    for trigger in expected_triggers:
        assert trigger in defaults["bindings"]


def test_load_save_roundtrip(tmp_config_dir, sample_bindings_config) -> None:
    """Saving a configuration and loading it back yields identical contents."""
    manager = ConfigManager(config_dir=tmp_config_dir)
    manager.save_bindings(sample_bindings_config)

    loaded = manager.load_bindings()
    assert loaded["schema_version"] == sample_bindings_config["schema_version"]
    assert loaded["bindings"] == sample_bindings_config["bindings"]


def test_validate_valid_config(tmp_config_dir, sample_bindings_config) -> None:
    """A complete valid configuration passes validation."""
    manager = ConfigManager(config_dir=tmp_config_dir)
    is_valid = manager.validate_bindings(sample_bindings_config)
    assert is_valid is True


def test_validate_missing_trigger(tmp_config_dir, sample_bindings_config) -> None:
    """A configuration missing required triggers fails validation."""
    bad_config = copy.deepcopy(sample_bindings_config)
    # Delete one required trigger
    del bad_config["bindings"]["DUAL_LB_RT"]

    manager = ConfigManager(config_dir=tmp_config_dir)
    with pytest.raises((ValueError, KeyError)):
        res = manager.validate_bindings(bad_config)
        if res is False:
            raise ValueError("Validation failed as expected")


def test_schema_version_check(tmp_config_dir, sample_bindings_config) -> None:
    """Incompatible schema version raises error or fails validation."""
    bad_version_config = copy.deepcopy(sample_bindings_config)
    bad_version_config["schema_version"] = 999  # Unsupported future version

    manager = ConfigManager(config_dir=tmp_config_dir)
    with pytest.raises((ValueError, KeyError)):
        res = manager.validate_bindings(bad_version_config)
        if res is False:
            raise ValueError("Unsupported schema version rejected")


def test_backup_created(tmp_config_dir, sample_bindings_config) -> None:
    """Saving over an existing configuration creates a .bak backup file."""
    manager = ConfigManager(config_dir=tmp_config_dir)
    manager.save_bindings(sample_bindings_config)

    # Modify and save again
    modified = copy.deepcopy(sample_bindings_config)
    modified["bindings"]["SINGLE_LT"]["label"] = "Updated App"
    manager.save_bindings(modified)

    # Check for .bak file in config dir
    bak_files = list(tmp_config_dir.glob("*.bak"))
    assert len(bak_files) >= 1, "Expected backup file (.bak) to be created on overwrite"
