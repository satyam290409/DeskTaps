"""Acoustic transient detection using STA/LTA energy ratio and refractory filtering."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TransientEvent:
    """An acoustic transient candidate or accepted tap event."""

    timestamp: float
    channel_data: np.ndarray
    energy: float
    sta_lta_ratio: float
    peak_amplitude: float
    is_duplicate: bool
    frame_index: int


@dataclass
class DetectorConfig:
    """Detection parameters for transient energy spike extraction."""

    energy_threshold: float = 0.01
    threshold_energy: float | None = None
    sta_lta_ratio: float = 3.0
    peak_threshold: float = 0.05
    sta_window_ms: float = 10.0
    lta_window_ms: float = 500.0
    refractory_ms: float = 150.0
    refractory_period_ms: float | None = None
    sample_rate: int = 48000

    def __post_init__(self) -> None:
        if self.threshold_energy is not None:
            self.energy_threshold = self.threshold_energy
        if self.refractory_period_ms is not None:
            self.refractory_ms = float(self.refractory_period_ms)


# Alias for backward/test compatibility
TransientConfig = DetectorConfig


@dataclass(slots=True)
class DetectorStats:
    """Aggregate statistics for detected audio transients."""

    candidates: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0


class TransientDetector:
    """Detects rapid onset acoustic energy transients via exponential STA/LTA ratio."""

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self._stats = DetectorStats()

        self._sta: float = 0.0
        self._lta: float = 0.0
        self._frames_seen: int = 0
        self._last_accepted_timestamp: float | None = None

        # Number of initialization frames before accepting transients
        self._min_warmup_frames: int = 3

    @property
    def stats(self) -> DetectorStats:
        """Returns a snapshot of transient detector statistics."""
        return DetectorStats(
            candidates=self._stats.candidates,
            accepted=self._stats.accepted,
            rejected=self._stats.rejected,
            duplicates=self._stats.duplicates,
        )

    def reset(self) -> None:
        """Resets detector state, baseline averages, and counters."""
        self._sta = 0.0
        self._lta = 0.0
        self._frames_seen = 0
        self._last_accepted_timestamp = None
        self._stats = DetectorStats()
        logger.debug("TransientDetector state reset")

    def process(
        self,
        frame: np.ndarray,
        timestamp: float = 0.0,
        frame_index: int = 0,
    ) -> TransientEvent | None:
        """Processes an incoming audio frame and detects transient energy spikes.

        Args:
            frame: Numpy array of shape (samples, channels) or (samples,).
            timestamp: Capture timestamp in seconds.
            frame_index: Sequential integer index of the frame.

        Returns:
            TransientEvent if an energy candidate is detected, or None otherwise.
        """
        if frame.size == 0:
            self._stats.rejected += 1
            return None

        # Short-window energy: mean of squared samples across channels
        energy = float(np.mean(frame.astype(np.float64, copy=False) ** 2))
        peak_amplitude = float(np.max(np.abs(frame)))

        n_samples = frame.shape[0]
        dt = n_samples / float(self.config.sample_rate)

        # Alpha smoothing constants from window durations
        tau_sta = max(self.config.sta_window_ms / 1000.0, 1e-4)
        tau_lta = max(self.config.lta_window_ms / 1000.0, 1e-3)
        alpha_sta = min(1.0 - math.exp(-dt / tau_sta), 1.0)
        alpha_lta = min(1.0 - math.exp(-dt / tau_lta), 1.0)

        # Handle initial frames
        if self._frames_seen == 0:
            if (
                energy > self.config.energy_threshold
                and peak_amplitude > self.config.peak_threshold
            ):
                self._sta = energy
                self._lta = max(self.config.energy_threshold * 0.1, 1e-5)
            else:
                self._sta = energy
                self._lta = max(energy, 1e-6)
                self._frames_seen += 1
                self._stats.rejected += 1
                return None
        else:
            # Exponential moving averages update
            self._sta = (1.0 - alpha_sta) * self._sta + alpha_sta * energy
            self._lta = (1.0 - alpha_lta) * self._lta + alpha_lta * energy

        self._frames_seen += 1

        sta_lta_ratio = self._sta / max(self._lta, 1e-12)

        is_candidate = (
            energy > self.config.energy_threshold
            and sta_lta_ratio > self.config.sta_lta_ratio
            and peak_amplitude > self.config.peak_threshold
        )

        if not is_candidate:
            self._stats.rejected += 1
            return None

        self._stats.candidates += 1

        # Check refractory period against last accepted timestamp
        refractory_sec = self.config.refractory_ms / 1000.0
        is_duplicate = False
        if self._last_accepted_timestamp is not None:
            time_since_last = timestamp - self._last_accepted_timestamp
            if time_since_last < refractory_sec:
                is_duplicate = True

        if is_duplicate:
            self._stats.duplicates += 1
            logger.debug(
                "Duplicate transient ignored (timestamp=%.3f, frame=%d)",
                timestamp,
                frame_index,
            )
        else:
            self._stats.accepted += 1
            self._last_accepted_timestamp = timestamp
            logger.info(
                "Transient detected: frame=%d energy=%.4f ratio=%.2f peak=%.3f",
                frame_index,
                energy,
                sta_lta_ratio,
                peak_amplitude,
            )

        return TransientEvent(
            timestamp=timestamp,
            channel_data=frame.copy(),
            energy=energy,
            sta_lta_ratio=sta_lta_ratio,
            peak_amplitude=peak_amplitude,
            is_duplicate=is_duplicate,
            frame_index=frame_index,
        )
