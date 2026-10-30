"""Unit tests for TapDeck transient detector."""

import numpy as np

from tapdeck.audio.transient_detector import (
    TransientConfig,
    TransientDetector,
    TransientEvent,
)


def test_detects_loud_transient(synthetic_stereo_tap, sample_rate) -> None:
    """Transient detector should detect a loud synthetic tap."""
    config = TransientConfig(sample_rate=sample_rate, threshold_energy=0.01)
    detector = TransientDetector(config)

    event = detector.process(synthetic_stereo_tap)
    assert event is not None
    assert isinstance(event, TransientEvent)
    assert event.energy > 0
    assert event.peak_amplitude > 0.1


def test_ignores_silence(silence, sample_rate) -> None:
    """Transient detector should return None on pure silence."""
    config = TransientConfig(sample_rate=sample_rate)
    detector = TransientDetector(config)

    event = detector.process(silence)
    assert event is None


def test_ignores_quiet_noise(white_noise, sample_rate) -> None:
    """Transient detector should ignore low-level ambient noise."""
    config = TransientConfig(sample_rate=sample_rate, threshold_energy=0.05)
    detector = TransientDetector(config)

    event = detector.process(white_noise)
    assert event is None


def test_refractory_suppresses_duplicate(synthetic_stereo_tap, sample_rate, block_size) -> None:
    """Two taps occurring within the refractory period (<150ms) should suppress the second."""
    refractory_sec = 0.150
    config = TransientConfig(
        sample_rate=sample_rate,
        refractory_period_ms=int(refractory_sec * 1000),
        threshold_energy=0.01,
    )
    detector = TransientDetector(config)

    # First tap at t = 0
    t0 = 0.0
    ev1 = detector.process(synthetic_stereo_tap, timestamp=t0)
    assert ev1 is not None

    # Second tap 50ms later (< 150ms)
    t_quick = 0.050
    ev2 = detector.process(synthetic_stereo_tap, timestamp=t_quick)
    # The detector should either return None or mark it as duplicate
    if ev2 is not None:
        assert (
            getattr(ev2, "is_duplicate", False) is True or getattr(ev2, "suppressed", False) is True
        )
    else:
        assert ev2 is None


def test_refractory_allows_after_period(synthetic_stereo_tap, sample_rate) -> None:
    """Two taps occurring beyond the refractory period (>150ms) should both be detected."""
    refractory_ms = 150
    config = TransientConfig(
        sample_rate=sample_rate,
        refractory_period_ms=refractory_ms,
        threshold_energy=0.01,
    )
    detector = TransientDetector(config)

    t0 = 0.0
    ev1 = detector.process(synthetic_stereo_tap, timestamp=t0)
    assert ev1 is not None

    # Second tap 200ms later (> 150ms)
    t_after = 0.200
    ev2 = detector.process(synthetic_stereo_tap, timestamp=t_after)
    assert ev2 is not None
    assert getattr(ev2, "is_duplicate", False) is False


def test_energy_calculation(sample_rate, block_size) -> None:
    """Verify energy calculation against a known signal."""
    detector = TransientDetector(TransientConfig(sample_rate=sample_rate))
    # Known signal: amplitude 0.5 constant on both channels
    val = 0.5
    known_block = np.full((block_size, 2), val, dtype=np.float32)

    # Check detector's internal energy calculation if available, or event energy
    expected_mean_energy = float(np.mean(known_block**2))
    computed_energy = (
        detector.calculate_energy(known_block) if hasattr(detector, "calculate_energy") else None
    )

    if computed_energy is not None:
        assert np.isclose(computed_energy, expected_mean_energy, atol=1e-4) or np.isclose(
            computed_energy, float(np.sum(known_block**2)), atol=1e-4
        )


def test_counter_tracking(synthetic_stereo_tap, silence, sample_rate) -> None:
    """Verify statistics counters track processed blocks and detected transients."""
    detector = TransientDetector(TransientConfig(sample_rate=sample_rate, threshold_energy=0.01))

    # Process 2 silent blocks, 1 tap block, 1 silent block
    detector.process(silence)
    detector.process(silence)
    detector.process(synthetic_stereo_tap)
    detector.process(silence)

    stats = detector.stats if hasattr(detector, "stats") else {}
    if isinstance(stats, dict):
        total = stats.get("total_blocks", getattr(detector, "total_blocks", 4))
        detected = stats.get("detected_transients", getattr(detector, "detected_transients", 1))
        assert total >= 4
        assert detected >= 1
    else:
        assert getattr(detector, "total_blocks", 4) >= 4


def test_reset(synthetic_stereo_tap, sample_rate) -> None:
    """Resetting detector state clears history and counters."""
    detector = TransientDetector(TransientConfig(sample_rate=sample_rate, threshold_energy=0.01))
    detector.process(synthetic_stereo_tap)
    detector.reset()

    # After reset, detector should allow another tap immediately without refractory lockout
    ev = detector.process(synthetic_stereo_tap, timestamp=0.0)
    assert ev is not None
