"""Unit tests for TapDeck Generalized Cross-Correlation with Phase Transform (GCC-PHAT)."""

import numpy as np

from tapdeck.audio.gcc_phat import gcc_phat


def _unpack_gcc(result):
    """Helper to extract delay and confidence from tuple or result object."""
    if hasattr(result, "delay") and hasattr(result, "confidence"):
        return float(result.delay), float(result.confidence)
    return float(result[0]), float(result[1])


def _make_impulse(length: int = 1024, center: int = 512, width: float = 3.0) -> np.ndarray:
    """Generate a clean Gaussian impulse signal."""
    x = np.arange(length)
    pulse = np.exp(-((x - center) ** 2) / (2 * width**2))
    return pulse.astype(np.float32)


def test_zero_delay(sample_rate) -> None:
    """Identical signals on both channels should result in delay ≈ 0."""
    sig = _make_impulse(1024, 512)
    res = gcc_phat(sig, sig, fs=sample_rate)
    delay, confidence = _unpack_gcc(res)
    assert abs(delay) < 0.25, f"Expected delay ≈ 0, got {delay}"
    assert confidence > 5.0, f"Expected high confidence, got {confidence}"


def test_positive_delay_5(sample_rate) -> None:
    """Shift sig2 by +5 samples (sig2 leads sig1): delay ≈ 5 (±1 for interpolation)."""
    sig1 = _make_impulse(1024, 512)
    sig2 = _make_impulse(1024, 512 + 5)
    res = gcc_phat(sig1, sig2, fs=sample_rate)
    delay, _ = _unpack_gcc(res)
    assert abs(delay - 5.0) <= 1.0, f"Expected delay ≈ 5, got {delay}"


def test_negative_delay_5(sample_rate) -> None:
    """Shift sig2 by -5 samples (sig1 leads sig2): delay ≈ -5 (±1 for interpolation)."""
    sig1 = _make_impulse(1024, 512)
    sig2 = _make_impulse(1024, 512 - 5)
    res = gcc_phat(sig1, sig2, fs=sample_rate)
    delay, _ = _unpack_gcc(res)
    assert abs(delay - (-5.0)) <= 1.0, f"Expected delay ≈ -5, got {delay}"


def test_sub_sample_accuracy(sample_rate) -> None:
    """Fractional delay estimation using parabolic or sinc interpolation."""
    # Create frequency-domain fractional shifted signal
    n = 1024
    shift = 2.4  # 2.4 samples
    sig1 = _make_impulse(n, 512)

    # Frequency domain shift for true sub-sample precision
    fft_val = np.fft.rfft(sig1)
    freqs = np.fft.rfftfreq(n)
    shifted_fft = fft_val * np.exp(-2j * np.pi * freqs * shift)
    sig2 = np.fft.irfft(shifted_fft, n=n).astype(np.float32)

    res = gcc_phat(sig1, sig2, fs=sample_rate, interp=16)
    delay, _ = _unpack_gcc(res)
    assert abs(delay - shift) < 0.5, f"Sub-sample shift {shift} estimated as {delay}"


def test_max_delay_clamp(sample_rate) -> None:
    """When max_delay_samples is specified, delay estimate should be clamped within bounds."""
    sig1 = _make_impulse(1024, 500)
    sig2 = _make_impulse(1024, 510)  # 10 sample true delay
    max_delay = 3

    res = gcc_phat(sig1, sig2, fs=sample_rate, max_delay_samples=max_delay)
    delay, _ = _unpack_gcc(res)
    assert -max_delay <= delay <= max_delay, f"Delay {delay} exceeded max bounds ±{max_delay}"


def test_confidence_clean_signal(sample_rate) -> None:
    """Clean delayed signal should exhibit high GCC-PHAT peak confidence (>5)."""
    sig1 = _make_impulse(1024, 512)
    sig2 = _make_impulse(1024, 515)
    res = gcc_phat(sig1, sig2, fs=sample_rate)
    _, confidence = _unpack_gcc(res)
    assert confidence > 5.0, f"Expected confidence > 5.0, got {confidence}"


def test_confidence_uncorrelated(sample_rate) -> None:
    """Uncorrelated white noise signals should have low confidence (<3)."""
    np.random.seed(123)
    sig1 = np.random.randn(1024).astype(np.float32)
    sig2 = np.random.randn(1024).astype(np.float32)
    res = gcc_phat(sig1, sig2, fs=sample_rate)
    _, confidence = _unpack_gcc(res)
    assert confidence < 3.0, f"Uncorrelated noise yielded confidence {confidence}, expected < 3.0"


def test_empty_signals_handled(sample_rate) -> None:
    """Zero-length arrays should not crash GCC-PHAT calculation."""
    sig_empty = np.array([], dtype=np.float32)
    try:
        res = gcc_phat(sig_empty, sig_empty, fs=sample_rate)
        delay, conf = _unpack_gcc(res)
        assert delay == 0.0 or np.isnan(delay)
    except (ValueError, IndexError):
        # Graceful handling through standard exception is also valid
        pass


def test_dc_offset(sample_rate) -> None:
    """GCC-PHAT should reject DC offsets and compute correct delay."""
    sig1 = _make_impulse(1024, 512) + 2.5
    sig2 = _make_impulse(1024, 512 + 4) + 5.0
    res = gcc_phat(sig1, sig2, fs=sample_rate)
    delay, _ = _unpack_gcc(res)
    assert abs(delay - 4.0) <= 1.0, f"Expected delay ≈ 4 with DC offset, got {delay}"


def test_sign_convention(sample_rate) -> None:
    """Document and verify sign convention: positive delay means sig2 leads sig1."""
    # When sig2 event occurs earlier in array index than sig1 (sig2 leads):
    # e.g., sig2 pulse at sample 500, sig1 pulse at sample 504
    sig_leader = _make_impulse(1024, 500)
    sig_trailer = _make_impulse(1024, 504)

    # gcc_phat(sig1, sig2) where sig2 is delayed relative to sig1
    res = gcc_phat(sig_leader, sig_trailer, fs=sample_rate)
    delay, _ = _unpack_gcc(res)
    assert delay > 0, f"Positive delay expected when sig2 leads, got {delay}"
