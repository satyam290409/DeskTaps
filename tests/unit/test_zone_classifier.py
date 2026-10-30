"""Unit tests for TapDeck acoustic zone classification."""

from tapdeck.audio.zone_classifier import ClassifierConfig, ZoneClassifier


def _zone_str(res) -> str:
    """Helper to get string representation of Zone whether enum or string."""
    val = res.zone if hasattr(res, "zone") else res
    if hasattr(val, "name"):
        return val.name
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


def test_left_from_negative_delay() -> None:
    """A negative delay (ch1 leading / arrival at left mic first) classifies to Left zone."""
    classifier = ZoneClassifier(ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0))
    res = classifier.classify(delay=-0.5, hfr=0.5, confidence=8.0)
    zone = _zone_str(res)
    assert zone in ("LT", "LB", "Zone.LT", "Zone.LB")


def test_right_from_positive_delay() -> None:
    """A positive delay (ch2 leading / arrival at right mic first) classifies to Right zone."""
    classifier = ZoneClassifier(ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0))
    res = classifier.classify(delay=0.5, hfr=0.5, confidence=8.0)
    zone = _zone_str(res)
    assert zone in ("RT", "RB", "Zone.RT", "Zone.RB")


def test_top_from_low_hfr() -> None:
    """A lower HFR (desk surface tap, more low-frequency resonance) classifies to Top zone."""
    classifier = ZoneClassifier(ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0))
    res = classifier.classify(delay=-0.5, hfr=0.5, confidence=8.0)
    zone = _zone_str(res)
    assert zone in ("LT", "RT", "Zone.LT", "Zone.RT")


def test_bottom_from_high_hfr() -> None:
    """A higher HFR (chassis tap, high frequency edge click) classifies to Bottom zone."""
    classifier = ZoneClassifier(ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0))
    res = classifier.classify(delay=-0.5, hfr=1.5, confidence=8.0)
    zone = _zone_str(res)
    assert zone in ("LB", "RB", "Zone.LB", "Zone.RB")


def test_all_four_zones() -> None:
    """Verify all 4 quadrants (LT, LB, RT, RB) classify deterministically."""
    classifier = ZoneClassifier(
        ClassifierConfig(delay_threshold=0.0, hfr_threshold=1.0, confidence_threshold=3.0)
    )

    # LT: Left (delay < 0) + Top (hfr < 1.0)
    assert _zone_str(classifier.classify(delay=-0.5, hfr=0.5, confidence=5.0)) in ("LT", "Zone.LT")
    # LB: Left (delay < 0) + Bottom (hfr > 1.0)
    assert _zone_str(classifier.classify(delay=-0.5, hfr=1.5, confidence=5.0)) in ("LB", "Zone.LB")
    # RT: Right (delay > 0) + Top (hfr < 1.0)
    assert _zone_str(classifier.classify(delay=0.5, hfr=0.5, confidence=5.0)) in ("RT", "Zone.RT")
    # RB: Right (delay > 0) + Bottom (hfr > 1.0)
    assert _zone_str(classifier.classify(delay=0.5, hfr=1.5, confidence=5.0)) in ("RB", "Zone.RB")


def test_rejection_low_confidence() -> None:
    """Taps below the confidence threshold must be rejected or classified as UNKNOWN."""
    classifier = ZoneClassifier(ClassifierConfig(confidence_threshold=10.0))
    res = classifier.classify(delay=0.5, hfr=0.5, confidence=2.0)
    zone = _zone_str(res)
    assert zone in ("UNKNOWN", "Zone.UNKNOWN", "None", "")


def test_uncalibrated_returns_unknown() -> None:
    """When calibration is required or absent, uncalibrated classifier returns UNKNOWN."""
    classifier = ZoneClassifier(ClassifierConfig(require_calibration=True))
    if hasattr(classifier, "is_calibrated"):
        assert not classifier.is_calibrated
    res = classifier.classify(delay=0.5, hfr=0.5, confidence=5.0)
    zone = _zone_str(res)
    assert zone in ("UNKNOWN", "Zone.UNKNOWN")
