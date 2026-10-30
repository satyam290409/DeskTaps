"""Unit tests for TapDeck preprocessing and bandpass filtering."""

import numpy as np

from tapdeck.audio.preprocessing import BandpassFilter, FilterConfig


def test_filter_creation_default() -> None:
    """Test default FilterConfig creates valid SOS matrix and is stable."""
    config = FilterConfig()
    filt = BandpassFilter(config)
    assert filt.sos is not None
    # SOS matrix shape for scipy is typically (n_sections, 6)
    assert filt.sos.ndim == 2
    assert filt.sos.shape[1] == 6
    assert filt.is_stable() is True


def test_filter_passes_in_band(sine_wave, sample_rate) -> None:
    """A 1kHz sine wave within the passband (300-3000 Hz) should retain >80% energy."""
    filt = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    # Generate 1024 samples of 1000 Hz tone to let transient settle
    t = np.arange(2048) / sample_rate
    sig_1k = (0.5 * np.sin(2 * np.pi * 1000.0 * t)).astype(np.float32)
    sig_stereo = np.column_stack([sig_1k, sig_1k])

    out = filt.process(sig_stereo)
    # Ignore initial filter ramp-up (first 256 samples)
    settled_in = sig_stereo[256:]
    settled_out = out[256:]

    energy_in = np.sum(settled_in**2)
    energy_out = np.sum(settled_out**2)

    ratio = energy_out / max(energy_in, 1e-12)
    assert ratio > 0.80, f"Passband energy retention was {ratio:.2f}, expected > 0.80"


def test_filter_attenuates_low_freq(sample_rate) -> None:
    """A 50Hz sine wave below low cutoff should lose >90% of its energy."""
    filt = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    t = np.arange(4096) / sample_rate
    sig_50 = (0.5 * np.sin(2 * np.pi * 50.0 * t)).astype(np.float32)
    sig_stereo = np.column_stack([sig_50, sig_50])

    out = filt.process(sig_stereo)
    settled_in = sig_stereo[512:]
    settled_out = out[512:]

    energy_in = np.sum(settled_in**2)
    energy_out = np.sum(settled_out**2)

    ratio = energy_out / max(energy_in, 1e-12)
    assert ratio < 0.10, f"Low frequency energy retention was {ratio:.2f}, expected < 0.10"


def test_filter_attenuates_high_freq(sample_rate) -> None:
    """A 5000Hz sine wave above high cutoff should lose >90% of its energy."""
    filt = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    t = np.arange(4096) / sample_rate
    sig_5k = (0.5 * np.sin(2 * np.pi * 5000.0 * t)).astype(np.float32)
    sig_stereo = np.column_stack([sig_5k, sig_5k])

    out = filt.process(sig_stereo)
    settled_in = sig_stereo[512:]
    settled_out = out[512:]

    energy_in = np.sum(settled_in**2)
    energy_out = np.sum(settled_out**2)

    ratio = energy_out / max(energy_in, 1e-12)
    assert ratio < 0.10, f"High frequency energy retention was {ratio:.2f}, expected < 0.10"


def test_filter_state_continuity(sample_rate, block_size) -> None:
    """Processing two consecutive blocks preserves filter state across boundaries."""
    filt_stream = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    filt_batch = BandpassFilter(FilterConfig(sample_rate=sample_rate))

    t1 = np.arange(block_size) / sample_rate
    t2 = np.arange(block_size, block_size * 2) / sample_rate
    block1 = np.column_stack([np.sin(2 * np.pi * 600 * t1), np.sin(2 * np.pi * 600 * t1)]).astype(
        np.float32
    )
    block2 = np.column_stack([np.sin(2 * np.pi * 600 * t2), np.sin(2 * np.pi * 600 * t2)]).astype(
        np.float32
    )
    combined = np.vstack([block1, block2])

    out1 = filt_stream.process(block1)
    out2 = filt_stream.process(block2)
    stream_out = np.vstack([out1, out2])

    batch_out = filt_batch.process(combined)

    np.testing.assert_allclose(stream_out, batch_out, atol=1e-5, rtol=1e-4)


def test_filter_reset(sample_rate, block_size) -> None:
    """Resetting filter state restores it to match an initial fresh filter."""
    filt = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    fresh_filt = BandpassFilter(FilterConfig(sample_rate=sample_rate))

    # Process some dirty audio
    noise = (np.random.randn(block_size, 2) * 0.5).astype(np.float32)
    _ = filt.process(noise)

    # Reset
    filt.reset()

    # Process identical test block on both
    test_block = (np.sin(np.linspace(0, 10, block_size))[:, None] * np.ones((1, 2))).astype(
        np.float32
    )
    out_after_reset = filt.process(test_block)
    out_fresh = fresh_filt.process(test_block)

    np.testing.assert_allclose(out_after_reset, out_fresh, atol=1e-6)


def test_filter_bypass(sample_rate, synthetic_stereo_tap) -> None:
    """When bypass is enabled, output equals input exactly."""
    config = FilterConfig(sample_rate=sample_rate, bypass=True)
    filt = BandpassFilter(config)

    out = filt.process(synthetic_stereo_tap)
    np.testing.assert_array_equal(out, synthetic_stereo_tap)


def test_filter_stability() -> None:
    """Verify is_stable() returns True for default configuration."""
    filt = BandpassFilter()
    assert filt.is_stable() is True
