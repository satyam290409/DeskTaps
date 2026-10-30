"""Audio preprocessing and bandpass filtering module."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import scipy.signal

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FilterConfig:
    """Configuration parameters for Butterworth bandpass filtering."""

    low_freq: float = 150.0
    high_freq: float = 3200.0
    order: int = 4
    sample_rate: int = 48000
    bypass: bool = False


class BandpassFilter:
    """Cascaded second-order sections (SOS) bandpass filter with continuous state."""

    def __init__(self, config: FilterConfig | None = None) -> None:
        self.config = config if config is not None else FilterConfig()
        self._validate_config(self.config)

        self._bypass: bool = self.config.bypass
        self.sos = scipy.signal.butter(
            self.config.order,
            [self.config.low_freq, self.config.high_freq],
            btype="band",
            fs=self.config.sample_rate,
            output="sos",
        )
        self._base_zi = scipy.signal.sosfilt_zi(self.sos)
        self._zi_1d: np.ndarray = np.zeros_like(self._base_zi)
        self._zi_channels: dict[int, np.ndarray] = {}

    @staticmethod
    def _validate_config(config: FilterConfig) -> None:
        """Validates filter frequency boundaries against Nyquist limit."""
        nyquist = config.sample_rate / 2.0
        if not (0 < config.low_freq < config.high_freq < nyquist):
            raise ValueError(
                f"Invalid filter frequencies: 0 < low_freq ({config.low_freq}) < "
                f"high_freq ({config.high_freq}) < Nyquist ({nyquist}) must hold."
            )
        if config.order <= 0:
            raise ValueError(f"Filter order must be positive, got {config.order}")

    @property
    def bypass(self) -> bool:
        """Indicates whether filtering is bypassed."""
        return self._bypass

    @bypass.setter
    def bypass(self, value: bool) -> None:
        """Enables or disables filter bypass."""
        self._bypass = bool(value)

    def reset(self) -> None:
        """Resets the internal filter state for all channels."""
        self._zi_1d = np.zeros_like(self._base_zi)
        self._zi_channels.clear()
        logger.debug("BandpassFilter state reset")

    def is_stable(self) -> bool:
        """Checks whether all filter poles lie strictly within the unit circle."""
        if np.any(np.isnan(self.sos)) or np.any(np.isinf(self.sos)):
            return False

        try:
            _, poles, _ = scipy.signal.sos2zpk(self.sos)
            return bool(np.all(np.abs(poles) < 1.0))
        except Exception as exc:
            logger.warning("Error computing filter stability: %s", exc)
            return False

    def get_frequency_response(self, n_points: int = 1024) -> tuple[np.ndarray, np.ndarray]:
        """Calculates frequency response of the SOS filter.

        Returns:
            frequencies: Array of frequencies in Hz.
            magnitude_db: Filter magnitude response in decibels (dB).
        """
        frequencies, response = scipy.signal.sosfreqz(
            self.sos,
            worN=n_points,
            fs=self.config.sample_rate,
        )
        magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), 1e-12))
        return frequencies, magnitude_db

    def process(self, data: np.ndarray) -> np.ndarray:
        """Filters input audio data maintaining continuous delay memory across frames.

        Args:
            data: Input numpy array, shape (N,) for mono or (N, C) for multi-channel.

        Returns:
            Filtered numpy array with identical shape and float32 dtype.
        """
        if self._bypass or data.size == 0:
            return data.copy()

        # Handle 1D mono audio
        if data.ndim == 1:
            filtered, self._zi_1d = scipy.signal.sosfilt(
                self.sos,
                data.astype(np.float32, copy=False),
                zi=self._zi_1d,
            )
            return filtered

        # Handle 2D multi-channel audio
        if data.ndim == 2:
            n_samples, n_channels = data.shape
            out = np.empty((n_samples, n_channels), dtype=np.float32)
            input_float = data.astype(np.float32, copy=False)

            for c in range(n_channels):
                if c not in self._zi_channels:
                    self._zi_channels[c] = np.zeros_like(self._base_zi)

                out[:, c], self._zi_channels[c] = scipy.signal.sosfilt(
                    self.sos,
                    input_float[:, c],
                    zi=self._zi_channels[c],
                )

            return out

        raise ValueError(f"Expected 1D or 2D audio array, got shape {data.shape}")
