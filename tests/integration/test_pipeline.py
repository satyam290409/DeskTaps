"""Integration tests for the complete TapDeck acoustic detection pipeline."""

from tapdeck.audio.feature_extractor import FeatureConfig, FeatureExtractor
from tapdeck.audio.gcc_phat import gcc_phat
from tapdeck.audio.preprocessing import BandpassFilter, FilterConfig
from tapdeck.audio.transient_detector import TransientConfig, TransientDetector
from tapdeck.audio.zone_classifier import ClassifierConfig, ZoneClassifier
from tapdeck.combos.combo_engine import ComboConfig, ComboEngine


def _unpack_gcc(res):
    if hasattr(res, "delay") and hasattr(res, "confidence"):
        return float(res.delay), float(res.confidence)
    return float(res[0]), float(res[1])


def _zone_str(res) -> str:
    val = getattr(res, "zone", res)
    return getattr(val, "name", str(val))


def test_synthetic_tap_full_pipeline(sample_rate, synthetic_delayed_tap) -> None:
    """A delayed tap passes through filter, detector, GCC-PHAT, features, and classifier."""
    # 1. Setup pipeline stages
    filter_stage = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    detector_stage = TransientDetector(
        TransientConfig(sample_rate=sample_rate, threshold_energy=0.0005)
    )
    extractor_stage = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
    classifier_stage = ZoneClassifier(
        ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0, confidence_threshold=2.0)
    )

    # 2. Input: delayed stereo tap (e.g. 4 samples delay, left leading)
    raw_signal = synthetic_delayed_tap(delay_samples=-4)

    # 3. Preprocess
    filtered = filter_stage.process(raw_signal)

    # 4. Detect transient
    event = detector_stage.process(filtered, timestamp=1.0)
    assert event is not None, "Pipeline failed to detect transient event from tap"

    # 5. Spatial GCC-PHAT delay
    gcc_res = gcc_phat(filtered[:, 0], filtered[:, 1], fs=sample_rate)
    delay, confidence = _unpack_gcc(gcc_res)

    # 6. Feature extraction
    features = extractor_stage.extract(filtered[:, 0], sample_rate=sample_rate)
    hfr = getattr(features, "hfr", 0.5)

    # 7. Zone classification
    classification = classifier_stage.classify(delay=delay, hfr=hfr, confidence=confidence)
    zone_name = _zone_str(classification)

    assert zone_name not in ("UNKNOWN", "None", "")
    assert zone_name in ("LT", "LB", "RT", "RB", "Zone.LT", "Zone.LB", "Zone.RT", "Zone.RB")


def test_silence_no_triggers(silence, sample_rate) -> None:
    """Silent input through pipeline yields no transient events and zero downstream triggers."""
    filter_stage = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    detector_stage = TransientDetector(TransientConfig(sample_rate=sample_rate))

    filtered = filter_stage.process(silence)
    event = detector_stage.process(filtered)

    assert event is None, "Silence triggered a false transient event"


def test_noise_rejection(white_noise, sample_rate) -> None:
    """Low-level background noise is rejected before zone classification or combo stage."""
    filter_stage = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    detector_stage = TransientDetector(
        TransientConfig(sample_rate=sample_rate, threshold_energy=0.05)
    )

    filtered = filter_stage.process(white_noise)
    event = detector_stage.process(filtered)

    assert event is None, "Ambient white noise triggered a transient event"


def test_dual_tap_integration(sample_rate, synthetic_delayed_tap) -> None:
    """Two taps separated by 100ms trigger dual-tap combo token in the combo engine."""
    filter_stage = BandpassFilter(FilterConfig(sample_rate=sample_rate))
    detector_stage = TransientDetector(
        TransientConfig(sample_rate=sample_rate, threshold_energy=0.0005)
    )
    classifier_stage = ZoneClassifier(ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0))
    combo_stage = ComboEngine(ComboConfig(window_ms=150))

    emitted_tokens = []
    if hasattr(combo_stage, "set_callback"):
        combo_stage.set_callback(lambda t: emitted_tokens.append(str(t)))

    # First tap (LT): negative delay, low HFR
    tap_lt = synthetic_delayed_tap(delay_samples=-4)
    filt_lt = filter_stage.process(tap_lt)
    ev1 = detector_stage.process(filt_lt, timestamp=1.000)
    assert ev1 is not None

    delay1, conf1 = _unpack_gcc(gcc_phat(filt_lt[:, 0], filt_lt[:, 1], fs=sample_rate))
    zone1 = classifier_stage.classify(delay=delay1, hfr=0.5, confidence=conf1)
    res1 = combo_stage.process_tap(_zone_str(zone1), timestamp=1.000)
    if res1:
        emitted_tokens.extend([str(r) for r in (res1 if isinstance(res1, list) else [res1])])

    # Second tap (RT): 100ms later, positive delay, low HFR
    detector_stage.reset()  # Reset refractory for testing combo integration
    tap_rt = synthetic_delayed_tap(delay_samples=4)
    filt_rt = filter_stage.process(tap_rt)
    ev2 = detector_stage.process(filt_rt, timestamp=1.100)
    assert ev2 is not None

    delay2, conf2 = _unpack_gcc(gcc_phat(filt_rt[:, 0], filt_rt[:, 1], fs=sample_rate))
    zone2 = classifier_stage.classify(delay=delay2, hfr=0.5, confidence=conf2)
    res2 = combo_stage.process_tap(_zone_str(zone2), timestamp=1.100)
    if res2:
        emitted_tokens.extend([str(r) for r in (res2 if isinstance(res2, list) else [res2])])

    assert any("DUAL_LT_RT" in t for t in emitted_tokens), f"Emitted: {emitted_tokens}"
