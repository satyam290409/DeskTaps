"""Unit tests for TapDeck acoustic feature extraction."""

import numpy as np

from tapdeck.audio.feature_extractor import FeatureConfig, FeatureExtractor


def _get_val(feat, key, default=None):
    if hasattr(feat, key):
        return getattr(feat, key)
    if isinstance(feat, dict) and key in feat:
        return feat[key]
    return default


def test_hfr_high_freq_dominant(sample_rate) -> None:
    """A 1500Hz sine wave (above split point ~800-1000Hz) should produce HFR > 1.0."""
    extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    t = np.arange(2048) / sample_rate
    sig = np.sin(2 * np.pi * 1500.0 * t).astype(np.float32)

    features = extractor.extract(sig, sample_rate=sample_rate)
    hfr = _get_val(features, "hfr")
    assert hfr is not None
    assert hfr > 1.0, f"Expected HFR > 1.0 for 1500Hz signal, got {hfr}"


def test_hfr_low_freq_dominant(sample_rate) -> None:
    """A 300Hz sine wave (below split point) should produce HFR < 1.0."""
    extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    t = np.arange(2048) / sample_rate
    sig = np.sin(2 * np.pi * 300.0 * t).astype(np.float32)

    features = extractor.extract(sig, sample_rate=sample_rate)
    hfr = _get_val(features, "hfr")
    assert hfr is not None
    assert hfr < 1.0, f"Expected HFR < 1.0 for 300Hz signal, got {hfr}"


def test_peak_to_rms_impulse(sample_rate) -> None:
    """A sharp impulse signal should exhibit a high peak-to-RMS ratio (>5)."""
    extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    sig = np.zeros(1024, dtype=np.float32)
    sig[512] = 1.0  # isolated delta peak

    features = extractor.extract(sig, sample_rate=sample_rate)
    peak_to_rms = _get_val(features, "peak_to_rms")
    assert peak_to_rms is not None
    assert peak_to_rms > 5.0, f"Expected peak_to_rms > 5.0 for impulse, got {peak_to_rms}"


def test_peak_to_rms_sine(sample_rate) -> None:
    """A pure continuous sine wave has theoretical peak-to-RMS of sqrt(2) ≈ 1.414."""
    extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    t = np.arange(4096) / sample_rate
    sig = np.sin(2 * np.pi * 440.0 * t).astype(np.float32)

    features = extractor.extract(sig, sample_rate=sample_rate)
    peak_to_rms = _get_val(features, "peak_to_rms")
    assert peak_to_rms is not None
    assert abs(peak_to_rms - np.sqrt(2)) < 0.1, f"Expected peak_to_rms ≈ 1.414, got {peak_to_rms}"


def test_clipping_detection_clean(sample_rate) -> None:
    """A signal bounded to amplitude 0.5 should not be flagged as clipped."""
    extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    sig = (0.5 * np.ones(512)).astype(np.float32)

    features = extractor.extract(sig, sample_rate=sample_rate)
    is_clipped = _get_val(features, "is_clipped")
    assert is_clipped is False


def test_clipping_detection_clipped(sample_rate) -> None:
    """A signal with values saturating at or above 0.99 should be flagged as clipped."""
    extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    sig = (0.5 * np.ones(512)).astype(np.float32)
    sig[100:110] = 0.999

    features = extractor.extract(sig, sample_rate=sample_rate)
    is_clipped = _get_val(features, "is_clipped")
    assert is_clipped is True


def test_spectral_centroid_pure_tone(sample_rate) -> None:
    """A pure 1000Hz tone should yield a spectral centroid ≈ 1000 Hz (±100 Hz)."""
    extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    t = np.arange(4096) / sample_rate
    sig = np.sin(2 * np.pi * 1000.0 * t).astype(np.float32)

    features = extractor.extract(sig, sample_rate=sample_rate)
    centroid = _get_val(features, "spectral_centroid")
    assert centroid is not None
    assert abs(centroid - 1000.0) < 100.0, f"Expected centroid ≈ 1000 Hz, got {centroid}"
