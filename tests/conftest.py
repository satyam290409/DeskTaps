"""Shared test fixtures for TapDeck test suite."""

from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def sample_rate() -> int:
    """Default sample rate for tests."""
    return 48000


@pytest.fixture
def block_size() -> int:
    """Default block size for tests."""
    return 512


@pytest.fixture
def synthetic_tap(sample_rate: int, block_size: int) -> np.ndarray:
    """Generate a synthetic tap signal — short burst with exponential decay."""
    np.random.seed(42)
    onset = np.zeros(block_size, dtype=np.float32)
    tap_start = block_size // 4
    tap_length = block_size // 4
    decay = np.exp(-np.arange(tap_length) / (sample_rate * 0.002))
    noise_burst = np.random.randn(tap_length) * decay
    onset[tap_start : tap_start + tap_length] = noise_burst * 0.5
    return onset.astype(np.float32)


@pytest.fixture
def synthetic_stereo_tap(synthetic_tap: np.ndarray) -> np.ndarray:
    """Generate a 2-channel tap signal (same on both channels)."""
    return np.column_stack([synthetic_tap, synthetic_tap]).astype(np.float32)


@pytest.fixture
def synthetic_delayed_tap(sample_rate: int, block_size: int):
    """Factory fixture: generates stereo tap with configurable delay."""

    def _make(delay_samples: int = 3) -> np.ndarray:
        np.random.seed(42)
        tap_start = block_size // 2
        tap_length = block_size // 4
        decay = np.exp(-np.arange(tap_length) / (sample_rate * 0.002))
        noise_burst = np.random.randn(tap_length) * decay * 0.5

        total_length = block_size * 2
        ch1 = np.zeros(total_length, dtype=np.float32)
        ch2 = np.zeros(total_length, dtype=np.float32)

        ch1[tap_start : tap_start + tap_length] = noise_burst
        shifted_start = tap_start + delay_samples
        if 0 <= shifted_start < len(ch2) - tap_length:
            ch2[shifted_start : shifted_start + tap_length] = noise_burst

        return np.column_stack([ch1, ch2]).astype(np.float32)

    return _make


@pytest.fixture
def silence(block_size: int) -> np.ndarray:
    """Generate silent stereo signal."""
    return np.zeros((block_size, 2), dtype=np.float32)


@pytest.fixture
def white_noise(block_size: int) -> np.ndarray:
    """Generate low-level white noise stereo signal."""
    np.random.seed(42)
    return (np.random.randn(block_size, 2) * 0.001).astype(np.float32)


@pytest.fixture
def sine_wave(sample_rate: int, block_size: int):
    """Factory: generate stereo sine wave at given frequency."""

    def _make(freq: float = 1000.0, amplitude: float = 0.5) -> np.ndarray:
        t = np.arange(block_size) / sample_rate
        sig = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        return np.column_stack([sig, sig])

    return _make


@pytest.fixture
def sample_bindings_config() -> dict:
    """Valid TapDeck bindings configuration."""
    return {
        "schema_version": 1,
        "bindings": {
            "SINGLE_LT": {
                "category": "app_launch",
                "action": "launch_app",
                "params": {"executable": "code", "args": []},
                "label": "Open VS Code",
            },
            "SINGLE_LB": {
                "category": "media_control",
                "action": "media_play_pause",
                "params": {},
                "label": "Play/Pause Media",
            },
            "SINGLE_RT": {
                "category": "app_launch",
                "action": "launch_app",
                "params": {"executable": "wt", "args": []},
                "label": "Open Terminal",
            },
            "SINGLE_RB": {
                "category": "system_toggle",
                "action": "hotkey",
                "params": {"keys": ["win", "alt", "k"]},
                "label": "Mute/Unmute Mic",
            },
            "DUAL_LT_RT": {
                "category": "window_action",
                "action": "hotkey",
                "params": {"keys": ["ctrl", "win", "right"]},
                "label": "Desktop Right",
            },
            "DUAL_LB_RB": {
                "category": "window_action",
                "action": "hotkey",
                "params": {"keys": ["ctrl", "win", "left"]},
                "label": "Desktop Left",
            },
            "DUAL_LT_RB": {
                "category": "focus_utility",
                "action": "hotkey",
                "params": {"keys": ["win", "tab"]},
                "label": "Task View",
            },
            "DUAL_LB_RT": {
                "category": "system_action",
                "action": "hotkey",
                "params": {"keys": ["win", "d"]},
                "label": "Minimize All",
            },
        },
    }


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Temporary directory for config tests."""
    config_dir = tmp_path / "TapDeck"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
