"""Feature extraction for acoustic tap transient characterization."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TapFeatures:
    """Acoustic feature representation of an individual tap transient."""

    hfr: float
    peak_to_rms: float
    attack_time_ms: float
    decay_time_ms: float
    envelope_duration_ms: float
    spectral_centroid_hz: float
    noise_floor: float
    is_clipped: bool
    clipping_ratio: float
    raw_energy: float

    @property
    def spectral_centroid(self) -> float:
        """Alias for spectral_centroid_hz."""
        return self.spectral_centroid_hz


@dataclass(slots=True)
class FeatureConfig:
    """Configuration parameters for acoustic feature extraction."""

    hfr_low_band: tuple[float, float] = (150.0, 800.0)
    hfr_high_band: tuple[float, float] = (800.0, 2500.0)
    clipping_threshold: float = 0.98
    sample_rate: int = 48000


class FeatureExtractor:
    """Extracts spectral, temporal envelope, and amplitude features from transient taps."""

    def __init__(self, config: FeatureConfig | None = None) -> None:
        self.config = config if config is not None else FeatureConfig()

    def extract(self, signal: np.ndarray, sample_rate: int | None = None) -> TapFeatures:
        """Extracts complete feature set from an audio segment.

        Args:
            signal: Audio signal array (1D array or 2D multi-channel array).
            sample_rate: Optional sample rate override.

        Returns:
            TapFeatures dataclass containing all computed acoustic metrics.
        """
        sr = float(sample_rate if sample_rate is not None else self.config.sample_rate)
        # Collapse multi-channel array to 1D primary reference channel
        if signal.ndim == 2:
            s = signal[:, 0].astype(np.float64, copy=False)
        else:
            s = signal.astype(np.float64, copy=False).ravel()

        if s.size == 0:
            logger.warning("Empty signal array provided to FeatureExtractor")
            return TapFeatures(
                hfr=0.0,
                peak_to_rms=0.0,
                attack_time_ms=0.0,
                decay_time_ms=0.0,
                envelope_duration_ms=0.0,
                spectral_centroid_hz=0.0,
                noise_floor=0.0,
                is_clipped=False,
                clipping_ratio=0.0,
                raw_energy=0.0,
            )

        abs_sig = np.abs(s)
        peak_amp = float(np.max(abs_sig))
        raw_energy = float(np.sum(s**2))
        sr = float(self.config.sample_rate)

        # 1. Peak-to-RMS ratio
        rms_amp = float(np.sqrt(np.mean(s**2)))
        peak_to_rms = float(peak_amp / (rms_amp + 1e-12))

        # 2. Clipping detection
        clipped_samples = int(np.sum(abs_sig >= self.config.clipping_threshold))
        clipping_ratio = float(clipped_samples / s.size)
        is_clipped = clipping_ratio > 0.0

        # 3. Noise floor: median of bottom 25% of abs(signal)
        p25 = float(np.percentile(abs_sig, 25.0))
        bottom_quarter = abs_sig[abs_sig <= p25]
        noise_floor = float(np.median(bottom_quarter)) if bottom_quarter.size > 0 else 0.0

        # 4. Temporal Envelope features (attack, decay, duration)
        th10 = 0.1 * peak_amp
        th90 = 0.9 * peak_amp

        peak_idx = int(np.argmax(abs_sig))

        # Attack time: time from 10% to 90% of peak before/at peak index
        pre_peak = abs_sig[: peak_idx + 1]
        idx_10_candidates = np.where(pre_peak >= th10)[0]
        idx_90_candidates = np.where(pre_peak >= th90)[0]

        idx_10 = int(idx_10_candidates[0]) if idx_10_candidates.size > 0 else peak_idx
        idx_90 = int(idx_90_candidates[0]) if idx_90_candidates.size > 0 else peak_idx

        attack_samples = max(0, idx_90 - idx_10)
        attack_time_ms = float((attack_samples / sr) * 1000.0)

        # Decay time: time from 90% to 10% of peak after peak index
        post_peak = abs_sig[peak_idx:]
        decay_start_candidates = np.where(post_peak <= th90)[0]
        decay_end_candidates = np.where(post_peak <= th10)[0]

        decay_start = int(decay_start_candidates[0]) if decay_start_candidates.size > 0 else 0
        decay_end = (
            int(decay_end_candidates[0]) if decay_end_candidates.size > 0 else post_peak.size - 1
        )

        decay_samples = max(0, decay_end - decay_start)
        decay_time_ms = float((decay_samples / sr) * 1000.0)

        # Envelope duration: total time above 10% threshold
        samples_above_10 = int(np.sum(abs_sig >= th10))
        envelope_duration_ms = float((samples_above_10 / sr) * 1000.0)

        # 5. Spectral features (FFT, HFR, Spectral Centroid)
        fft_vals = np.fft.rfft(s)
        power_spectrum = np.abs(fft_vals) ** 2
        freqs = np.fft.rfftfreq(s.size, d=1.0 / sr)

        # High-to-Low Frequency Ratio (HFR)
        low_min, low_max = self.config.hfr_low_band
        high_min, high_max = self.config.hfr_high_band

        low_mask = (freqs >= low_min) & (freqs < low_max)
        high_mask = (freqs >= high_min) & (freqs <= high_max)

        low_energy = float(np.sum(power_spectrum[low_mask]))
        high_energy = float(np.sum(power_spectrum[high_mask]))
        hfr = float(high_energy / (low_energy + 1e-12))

        # Spectral Centroid: sum(f * |X(f)|^2) / sum(|X(f)|^2)
        total_power = float(np.sum(power_spectrum))
        if total_power > 1e-12:
            spectral_centroid_hz = float(np.sum(freqs * power_spectrum) / total_power)
        else:
            spectral_centroid_hz = 0.0

        return TapFeatures(
            hfr=hfr,
            peak_to_rms=peak_to_rms,
            attack_time_ms=attack_time_ms,
            decay_time_ms=decay_time_ms,
            envelope_duration_ms=envelope_duration_ms,
            spectral_centroid_hz=spectral_centroid_hz,
            noise_floor=noise_floor,
            is_clipped=is_clipped,
            clipping_ratio=clipping_ratio,
            raw_energy=raw_energy,
        )
