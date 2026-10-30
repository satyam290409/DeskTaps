"""Generalized Cross-Correlation with Phase Transform (GCC-PHAT) for time delay estimation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GCCResult:
    """Result of GCC-PHAT time-delay estimation between two microphone channels.

    Sign Convention:
        A POSITIVE delay indicates that sig2 leads sig1 (sound reached mic2 first).
        A NEGATIVE delay indicates that sig1 leads sig2 (sound reached mic1 first).
    """

    delay_samples: float
    delay_seconds: float
    delay_ms: float
    confidence: float
    peak_to_sidelobe: float
    raw_correlation: np.ndarray

    @property
    def delay(self) -> float:
        """Alias for delay_samples."""
        return self.delay_samples

    def __getitem__(self, index: int) -> float:
        if index == 0:
            return self.delay_samples
        elif index == 1:
            return self.confidence
        raise IndexError(f"Index {index} out of range for GCCResult")


def gcc_phat(
    sig1: np.ndarray,
    sig2: np.ndarray,
    sample_rate: int | None = None,
    max_delay_samples: int | None = None,
    interp: bool = True,
    fs: int | None = None,
) -> GCCResult:
    """Computes the Generalized Cross-Correlation with Phase Transform (GCC-PHAT).

    Args:
        sig1: First audio signal (1D array).
        sig2: Second audio signal (1D array).
        sample_rate: Audio sampling frequency in Hz.
        max_delay_samples: Optional maximum physically feasible delay in samples.
            Restricts the peak search range to [-max_delay, +max_delay].
        interp: Whether to apply sub-sample parabolic interpolation around the peak.
        fs: Alias for sample_rate.

    Returns:
        GCCResult containing delay estimates, confidence metrics, and shifted correlation curve.
    """
    if sample_rate is None:
        sample_rate = fs if fs is not None else 48000
    # Flatten inputs to 1D and remove DC bias
    s1 = np.asarray(sig1, dtype=np.float64).ravel()
    s2 = np.asarray(sig2, dtype=np.float64).ravel()
    if s1.size > 0:
        s1 = s1 - np.mean(s1)
    if s2.size > 0:
        s2 = s2 - np.mean(s2)

    # Handle zero-length inputs
    if s1.size == 0 or s2.size == 0:
        logger.warning("Empty signal passed to gcc_phat")
        return GCCResult(
            delay_samples=0.0,
            delay_seconds=0.0,
            delay_ms=0.0,
            confidence=0.0,
            peak_to_sidelobe=1.0,
            raw_correlation=np.zeros(0, dtype=np.float32),
        )

    # Handle all-zero inputs
    s1_energy = np.sum(s1**2)
    s2_energy = np.sum(s2**2)
    if s1_energy < 1e-15 or s2_energy < 1e-15:
        logger.debug("One or both signals are all-zero in gcc_phat")
        return GCCResult(
            delay_samples=0.0,
            delay_seconds=0.0,
            delay_ms=0.0,
            confidence=0.0,
            peak_to_sidelobe=1.0,
            raw_correlation=np.zeros(s1.size, dtype=np.float32),
        )

    # Use next power of 2 of at least 2*L - 1 for linear cross-correlation
    n_pts = max(s1.size, s2.size)
    min_fft_size = 2 * n_pts - 1
    n_fft = 1 << (min_fft_size - 1).bit_length()
    n_fft = max(n_fft, 32)

    x1 = np.fft.fft(s1, n=n_fft)
    x2 = np.fft.fft(s2, n=n_fft)

    # Cross-power spectrum: X2 * conj(X1)
    # Positive delay indicates sig2 leads sig1 (sound arrives at mic 2 first)
    r12 = x2 * np.conj(x1)
    magnitude = np.abs(r12) + 1e-10
    g_phat = r12 / magnitude

    # Inverse FFT to time-domain cross-correlation
    correlation = np.real(np.fft.ifft(g_phat))
    shifted_corr = np.fft.fftshift(correlation)

    center_idx = n_fft // 2

    # Determine candidate search range
    if max_delay_samples is not None and max_delay_samples > 0:
        start_idx = max(0, center_idx - max_delay_samples)
        end_idx = min(n_fft - 1, center_idx + max_delay_samples)
    else:
        start_idx = 0
        end_idx = n_fft - 1

    search_slice = np.arange(start_idx, end_idx + 1)
    if search_slice.size == 0:
        search_slice = np.array([center_idx])

    peak_local_idx = int(np.argmax(shifted_corr[search_slice]))
    peak_idx = int(search_slice[peak_local_idx])
    peak_value = float(shifted_corr[peak_idx])

    # Parabolic (3-point) sub-sample interpolation
    interpolated_idx = float(peak_idx)
    if interp and 0 < peak_idx < n_fft - 1:
        alpha = float(shifted_corr[peak_idx - 1])
        beta = float(shifted_corr[peak_idx])
        gamma = float(shifted_corr[peak_idx + 1])
        denominator = 2.0 * (alpha - 2.0 * beta + gamma)
        if abs(denominator) > 1e-12:
            delta = (alpha - gamma) / denominator
            delta = max(-0.5, min(0.5, delta))
            interpolated_idx += delta

    # Convert peak index to delay
    delay_samples = interpolated_idx - center_idx
    delay_seconds = delay_samples / float(sample_rate)
    delay_ms = delay_seconds * 1000.0

    # Confidence: ratio of peak to 90th percentile of absolute correlation in search window
    p90 = float(np.percentile(np.abs(shifted_corr[search_slice]), 90.0))
    confidence = float(peak_value / (p90 + 1e-10))

    # Peak-to-sidelobe ratio: compare to highest peak outside ±2 samples of main peak
    sidelobe_mask = (search_slice < peak_idx - 2) | (search_slice > peak_idx + 2)
    sidelobe_indices = search_slice[sidelobe_mask]

    if sidelobe_indices.size > 0:
        second_highest = float(np.max(shifted_corr[sidelobe_indices]))
        peak_to_sidelobe = float(peak_value / (max(second_highest, 0.0) + 1e-10))
    else:
        peak_to_sidelobe = 1.0

    return GCCResult(
        delay_samples=delay_samples,
        delay_seconds=delay_seconds,
        delay_ms=delay_ms,
        confidence=confidence,
        peak_to_sidelobe=peak_to_sidelobe,
        raw_correlation=shifted_corr.astype(np.float32),
    )
