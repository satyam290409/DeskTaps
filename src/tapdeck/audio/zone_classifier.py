"""Acoustic zone classification module for TapDeck.

Maps transient acoustic features (inter-channel delay from GCC-PHAT and
high-frequency energy ratio) into spatial quadrants around the laptop keyboard/chassis.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


class Zone(StrEnum):
    """Spatial quadrants for tap localization."""

    LT = "left_top"
    LB = "left_bottom"
    RT = "right_top"
    RB = "right_bottom"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


@dataclass
class ClassificationResult:
    """Result of classifying a single acoustic tap transient."""

    zone: Zone
    confidence: float
    per_zone_scores: dict[Zone, float]
    rejection_reason: str | None
    features: dict[str, float]
    calibration_id: str | None
    delay_ms: float
    hfr: float


@dataclass
class CalibrationData:
    """Calibration profile data used by ZoneClassifier for localization."""

    delay_center: dict[Zone, float]
    delay_spread: dict[Zone, float]
    hfr_center: dict[Zone, float]
    hfr_spread: dict[Zone, float]
    calibration_id: str
    device_name: str
    sample_rate: int
    created_at: str


@dataclass
class ClassifierConfig:
    """Configuration options and thresholds for ZoneClassifier."""

    confidence_threshold: float = 0.6
    delay_threshold_ms: float = 0.0
    delay_threshold: float | None = None
    hfr_threshold: float = 1.0
    use_calibration: bool = False
    require_calibration: bool | None = None

    def __post_init__(self) -> None:
        if self.delay_threshold is not None:
            self.delay_threshold_ms = self.delay_threshold
        if self.require_calibration is not None:
            self.use_calibration = self.require_calibration


class ZoneClassifier:
    """Classifies acoustic tap coordinates into spatial zones.

    Uses inter-channel time delay (horizontal axis) and high-frequency ratio (vertical axis)
    combined with calibrated Gaussian-like likelihood scoring.
    """

    def __init__(self, config: ClassifierConfig | None = None) -> None:
        """Initialize the ZoneClassifier with optional configuration.

        Args:
            config: ClassifierConfig instance or None for defaults.
        """
        self.config = config if config is not None else ClassifierConfig()
        self.calibration: CalibrationData | None = None

    @property
    def is_calibrated(self) -> bool:
        """Returns True if a calibration profile is currently loaded."""
        return self.calibration is not None

    def load_calibration(self, cal: CalibrationData) -> None:
        """Load calibration data and update decision boundary thresholds.

        Args:
            cal: CalibrationData containing empirical centers and spreads.
        """
        self.calibration = cal

        # Update horizontal delay threshold as midpoint between left and right centers
        left_delays: list[float] = [
            cal.delay_center[z] for z in (Zone.LT, Zone.LB) if z in cal.delay_center
        ]
        right_delays: list[float] = [
            cal.delay_center[z] for z in (Zone.RT, Zone.RB) if z in cal.delay_center
        ]

        if left_delays and right_delays:
            left_mean = sum(left_delays) / len(left_delays)
            right_mean = sum(right_delays) / len(right_delays)
            self.config.delay_threshold_ms = (left_mean + right_mean) / 2.0
            logger.info(
                "Updated delay_threshold_ms to %.3f ms (left avg: %.3f, right avg: %.3f)",
                self.config.delay_threshold_ms,
                left_mean,
                right_mean,
            )

        # Update vertical HFR threshold as midpoint between top and bottom centers
        top_hfrs: list[float] = [
            cal.hfr_center[z] for z in (Zone.LT, Zone.RT) if z in cal.hfr_center
        ]
        bottom_hfrs: list[float] = [
            cal.hfr_center[z] for z in (Zone.LB, Zone.RB) if z in cal.hfr_center
        ]

        if top_hfrs and bottom_hfrs:
            top_mean = sum(top_hfrs) / len(top_hfrs)
            bottom_mean = sum(bottom_hfrs) / len(bottom_hfrs)
            self.config.hfr_threshold = (top_mean + bottom_mean) / 2.0
            logger.info(
                "Updated hfr_threshold to %.3f (top avg: %.3f, bottom avg: %.3f)",
                self.config.hfr_threshold,
                top_mean,
                bottom_mean,
            )

    def classify(
        self,
        delay_ms: float | None = None,
        hfr: float = 1.0,
        features: dict[str, float] | None = None,
        delay: float | None = None,
        confidence: float | None = None,
    ) -> ClassificationResult:
        """Classify a tap event given delay and HFR.

        Args:
            delay_ms: Time difference of arrival between channels in milliseconds.
            hfr: High frequency ratio (energy above cutoff / energy below cutoff).
            features: Optional dictionary of additional extracted feature values.
            delay: Alias for delay_ms.
            confidence: Optional upstream confidence score.

        Returns:
            ClassificationResult containing the assigned zone, confidence, and metrics.
        """
        if delay_ms is None:
            delay_ms = delay if delay is not None else 0.0
        input_confidence = confidence
        feat: dict[str, float] = dict(features) if features is not None else {}
        feat.setdefault("delay_ms", delay_ms)
        feat.setdefault("hfr", hfr)

        if self.calibration is None and self.config.use_calibration:
            logger.warning("Tap rejected: calibration required but none loaded")
            zero_scores: dict[Zone, float] = {
                Zone.LT: 0.0,
                Zone.LB: 0.0,
                Zone.RT: 0.0,
                Zone.RB: 0.0,
                Zone.UNKNOWN: 1.0,
            }
            return ClassificationResult(
                zone=Zone.UNKNOWN,
                confidence=0.0,
                per_zone_scores=zero_scores,
                rejection_reason="no_calibration",
                features=feat,
                calibration_id=None,
                delay_ms=delay_ms,
                hfr=hfr,
            )

        # Determine quadrant boundaries
        is_left = delay_ms < self.config.delay_threshold_ms
        is_top = hfr < self.config.hfr_threshold

        predicted: Zone
        if is_left and is_top:
            predicted = Zone.LT
        elif is_left and not is_top:
            predicted = Zone.LB
        elif not is_left and is_top:
            predicted = Zone.RT
        else:
            predicted = Zone.RB

        # Gaussian likelihood scoring if calibration is present
        raw_scores: dict[Zone, float] = {}
        active_zones = (Zone.LT, Zone.LB, Zone.RT, Zone.RB)

        if self.calibration is not None:
            for z in active_zones:
                c_delay = self.calibration.delay_center.get(z, 0.0)
                s_delay = max(self.calibration.delay_spread.get(z, 0.5), 1e-4)
                c_hfr = self.calibration.hfr_center.get(z, 1.0)
                s_hfr = max(self.calibration.hfr_spread.get(z, 0.2), 1e-4)

                norm_delay = (delay_ms - c_delay) / s_delay
                norm_hfr = (hfr - c_hfr) / s_hfr
                mahalanobis_sq = norm_delay**2 + norm_hfr**2

                # Guard against exp underflow/overflow
                mahalanobis_sq = min(mahalanobis_sq, 50.0)
                raw_scores[z] = math.exp(-0.5 * mahalanobis_sq)

            total_score = sum(raw_scores[z] for z in active_zones)
            if total_score > 1e-12:
                per_zone_scores = {z: raw_scores[z] / total_score for z in active_zones}
                per_zone_scores[Zone.UNKNOWN] = 0.0
                confidence = per_zone_scores[predicted]
            else:
                per_zone_scores = {z: 0.25 for z in active_zones}
                per_zone_scores[Zone.UNKNOWN] = 0.0
                confidence = 0.0
        else:
            # Fallback if use_calibration was explicitly False
            per_zone_scores = {z: (1.0 if z == predicted else 0.0) for z in active_zones}
            per_zone_scores[Zone.UNKNOWN] = 0.0
            confidence = 1.0

        if input_confidence is not None:
            confidence = input_confidence

        cal_id = self.calibration.calibration_id if self.calibration else None

        if confidence < self.config.confidence_threshold:
            logger.debug(
                "Tap rejected for low confidence (%.2f < %.2f) at delay=%.2f, hfr=%.2f",
                confidence,
                self.config.confidence_threshold,
                delay_ms,
                hfr,
            )
            return ClassificationResult(
                zone=Zone.UNKNOWN,
                confidence=confidence,
                per_zone_scores=per_zone_scores,
                rejection_reason="low_confidence",
                features=feat,
                calibration_id=cal_id,
                delay_ms=delay_ms,
                hfr=hfr,
            )

        return ClassificationResult(
            zone=predicted,
            confidence=confidence,
            per_zone_scores=per_zone_scores,
            rejection_reason=None,
            features=feat,
            calibration_id=cal_id,
            delay_ms=delay_ms,
            hfr=hfr,
        )

    def classify_uncalibrated(
        self,
        delay_ms: float,
        hfr: float,
        features: dict[str, float] | None = None,
    ) -> ClassificationResult:
        """Classify a tap event using default thresholds without requiring calibration.

        Args:
            delay_ms: Time difference of arrival in milliseconds.
            hfr: High frequency ratio.
            features: Optional dictionary of extracted features.

        Returns:
            ClassificationResult based purely on the configured boundary thresholds.
        """
        feat: dict[str, float] = dict(features) if features is not None else {}
        feat.setdefault("delay_ms", delay_ms)
        feat.setdefault("hfr", hfr)

        is_left = delay_ms < self.config.delay_threshold_ms
        is_top = hfr < self.config.hfr_threshold

        predicted: Zone
        if is_left and is_top:
            predicted = Zone.LT
        elif is_left and not is_top:
            predicted = Zone.LB
        elif not is_left and is_top:
            predicted = Zone.RT
        else:
            predicted = Zone.RB

        active_zones = (Zone.LT, Zone.LB, Zone.RT, Zone.RB)
        per_zone_scores: dict[Zone, float] = {
            z: (1.0 if z == predicted else 0.0) for z in active_zones
        }
        per_zone_scores[Zone.UNKNOWN] = 0.0

        return ClassificationResult(
            zone=predicted,
            confidence=1.0,
            per_zone_scores=per_zone_scores,
            rejection_reason=None,
            features=feat,
            calibration_id=None,
            delay_ms=delay_ms,
            hfr=hfr,
        )
