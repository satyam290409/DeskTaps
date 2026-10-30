"""Calibration wizard engine and spatial profile builder for TapDeck.

Guides the user through sequential acoustic zone calibration, aggregates
empirical delay/HFR metrics, computes optimal decision boundaries, and assesses
statistical quality and cluster separability.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import numpy as np

from tapdeck.audio.zone_classifier import Zone

logger = logging.getLogger(__name__)


class CalibrationState(StrEnum):
    """Step-by-step states in the calibration wizard."""

    IDLE = "IDLE"
    SELECT_DEVICE = "SELECT_DEVICE"
    VERIFY_POSITION = "VERIFY_POSITION"
    TAP_LT = "TAP_LT"
    TAP_LB = "TAP_LB"
    TAP_RT = "TAP_RT"
    TAP_RB = "TAP_RB"
    REVIEW = "REVIEW"
    CALCULATE = "CALCULATE"
    SAVE = "SAVE"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"

    def __str__(self) -> str:
        return self.value


# Linear progression flow
CALIBRATION_FLOW: list[CalibrationState] = [
    CalibrationState.IDLE,
    CalibrationState.SELECT_DEVICE,
    CalibrationState.VERIFY_POSITION,
    CalibrationState.TAP_LT,
    CalibrationState.TAP_LB,
    CalibrationState.TAP_RT,
    CalibrationState.TAP_RB,
    CalibrationState.REVIEW,
    CalibrationState.CALCULATE,
    CalibrationState.SAVE,
    CalibrationState.COMPLETE,
]


@dataclass
class ZoneSample:
    """A single acoustic tap sample collected during calibration."""

    zone: Zone
    delay_ms: float
    hfr: float
    features: dict[str, float]
    timestamp: float
    is_valid: bool
    rejection_reason: str | None


@dataclass
class CalibrationQuality:
    """Statistical quality report evaluating zone separation and sample consistency."""

    total_samples: int
    valid_samples_per_zone: dict[Zone, int]
    rejected_per_zone: dict[Zone, int]
    zone_separability: float
    delay_overlap: bool
    hfr_overlap: bool
    quality_passed: bool
    issues: list[str]


@dataclass
class CalibrationProfile:
    """Complete calibrated spatial localization profile."""

    profile_name: str
    device_name: str
    sample_rate: int
    channels: int
    created_at: str
    schema_version: int = 1
    zones: dict[str, dict[str, Any]] = field(default_factory=dict)
    delay_threshold: float = 0.0
    hfr_threshold: float = 1.0
    quality: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


class CalibrationEngine:
    """Manages the calibration wizard state and computes spatial decision profiles."""

    def __init__(self, min_samples_per_zone: int = 5) -> None:
        """Initialize CalibrationEngine.

        Args:
            min_samples_per_zone: Minimum required valid taps per quadrant.
        """
        self.min_samples_per_zone = max(1, min_samples_per_zone)
        self.state: CalibrationState = CalibrationState.IDLE
        self._samples: dict[Zone, list[ZoneSample]] = {
            Zone.LT: [],
            Zone.LB: [],
            Zone.RT: [],
            Zone.RB: [],
        }

    def start_calibration(self) -> None:
        """Start calibration wizard sequence, advancing to SELECT_DEVICE."""
        self.reset()
        self.state = CalibrationState.SELECT_DEVICE
        logger.info("Calibration started: state -> %s", self.state)

    def advance(self) -> CalibrationState:
        """Advance the calibration wizard to the next logical state.

        Returns:
            The new CalibrationState.
        """
        try:
            curr_idx = CALIBRATION_FLOW.index(self.state)
            if curr_idx < len(CALIBRATION_FLOW) - 1:
                self.state = CALIBRATION_FLOW[curr_idx + 1]
            else:
                self.state = CalibrationState.COMPLETE
        except ValueError:
            self.state = CalibrationState.IDLE

        logger.info("Calibration advanced to: %s", self.state)
        return self.state

    def get_current_zone(self) -> Zone | None:
        """Return the target Zone corresponding to the current state, or None.

        Returns:
            Zone if current state is a tapping step, else None.
        """
        state_map = {
            CalibrationState.TAP_LT: Zone.LT,
            CalibrationState.TAP_LB: Zone.LB,
            CalibrationState.TAP_RT: Zone.RT,
            CalibrationState.TAP_RB: Zone.RB,
        }
        return state_map.get(self.state)

    def add_sample(
        self,
        zone: Zone,
        delay_ms: float,
        hfr: float,
        features: dict[str, float] | None = None,
    ) -> ZoneSample:
        """Add and validate an acoustic tap measurement for a given zone.

        Args:
            zone: Target spatial zone.
            delay_ms: Inter-channel delay in milliseconds.
            hfr: High frequency ratio.
            features: Optional dictionary of extracted acoustic features.

        Returns:
            The recorded ZoneSample.
        """
        if zone not in self._samples:
            self._samples[zone] = []

        feat = dict(features) if features is not None else {}
        feat.setdefault("delay_ms", delay_ms)
        feat.setdefault("hfr", hfr)

        # Validation rules:
        # Delay must be finite and within realistic acoustic limits (-30 to 30 ms)
        # HFR must be positive and non-zero
        is_valid = True
        rejection_reason: str | None = None

        if math.isnan(delay_ms) or math.isinf(delay_ms):
            is_valid = False
            rejection_reason = "delay_nan_or_inf"
        elif abs(delay_ms) > 30.0:
            is_valid = False
            rejection_reason = "delay_exceeds_30ms"
        elif math.isnan(hfr) or math.isinf(hfr) or hfr <= 0.0:
            is_valid = False
            rejection_reason = "invalid_hfr_value"

        sample = ZoneSample(
            zone=zone,
            delay_ms=float(delay_ms),
            hfr=float(hfr),
            features=feat,
            timestamp=time.time(),
            is_valid=is_valid,
            rejection_reason=rejection_reason,
        )

        self._samples[zone].append(sample)
        logger.debug(
            "Added calibration sample for %s: delay=%.2f ms, hfr=%.2f, valid=%s",
            zone.value,
            delay_ms,
            hfr,
            is_valid,
        )
        return sample

    def get_samples_for_zone(self, zone: Zone) -> list[ZoneSample]:
        """Retrieve all recorded samples for a specific zone.

        Args:
            zone: Spatial Zone.

        Returns:
            List of ZoneSample objects.
        """
        return list(self._samples.get(zone, []))

    def evaluate_quality(self) -> CalibrationQuality:
        """Assess statistical separation and consistency of the collected samples.

        Returns:
            CalibrationQuality containing diagnostic metrics and issue descriptions.
        """
        valid_counts: dict[Zone, int] = {}
        rejected_counts: dict[Zone, int] = {}
        issues: list[str] = []
        total_samples = 0

        target_zones = (Zone.LT, Zone.LB, Zone.RT, Zone.RB)

        for z in target_zones:
            samples = self._samples.get(z, [])
            total_samples += len(samples)
            valid = [s for s in samples if s.is_valid]
            rejected = [s for s in samples if not s.is_valid]

            valid_counts[z] = len(valid)
            rejected_counts[z] = len(rejected)

            if len(valid) < self.min_samples_per_zone:
                issues.append(
                    f"Zone {z.value} has only {len(valid)} valid samples "
                    f"(minimum required: {self.min_samples_per_zone})"
                )

        # Evaluate delay and HFR centers per zone
        zone_delay_medians: dict[Zone, float] = {}
        zone_hfr_medians: dict[Zone, float] = {}
        for z in target_zones:
            valid_delays = [s.delay_ms for s in self._samples.get(z, []) if s.is_valid]
            valid_hfrs = [s.hfr for s in self._samples.get(z, []) if s.is_valid]
            zone_delay_medians[z] = float(np.median(valid_delays)) if valid_delays else 0.0
            zone_hfr_medians[z] = float(np.median(valid_hfrs)) if valid_hfrs else 1.0

        # Check horizontal delay overlap between left and right zones
        left_delays = [
            s.delay_ms for z in (Zone.LT, Zone.LB) for s in self._samples.get(z, []) if s.is_valid
        ]
        right_delays = [
            s.delay_ms for z in (Zone.RT, Zone.RB) for s in self._samples.get(z, []) if s.is_valid
        ]

        delay_overlap = False
        if left_delays and right_delays:
            left_median = float(np.median(left_delays))
            right_median = float(np.median(right_delays))
            delay_separation = abs(right_median - left_median)

            if delay_separation < 0.02:
                delay_overlap = True
                issues.append(
                    f"Left/right separation too small ({delay_separation:.3f} ms < 0.02 ms)"
                )
        else:
            delay_overlap = True

        # Check vertical HFR overlap between top and bottom zones
        top_hfrs = [
            s.hfr for z in (Zone.LT, Zone.RT) for s in self._samples.get(z, []) if s.is_valid
        ]
        bottom_hfrs = [
            s.hfr for z in (Zone.LB, Zone.RB) for s in self._samples.get(z, []) if s.is_valid
        ]

        hfr_overlap = False
        if top_hfrs and bottom_hfrs:
            top_median = float(np.median(top_hfrs))
            bottom_median = float(np.median(bottom_hfrs))
            hfr_separation = abs(bottom_median - top_median)

            if hfr_separation < 0.05:
                hfr_overlap = True
                issues.append(
                    f"Top and bottom HFR separation is too small ({hfr_separation:.3f} < 0.05)"
                )
        else:
            hfr_overlap = True

        # Compute zone separability metric (normalized between 0.0 and 1.0)
        # Ratio of inter-cluster centroid distance to intra-cluster variance
        centroids: list[np.ndarray] = [
            np.array([zone_delay_medians[z], zone_hfr_medians[z]]) for z in target_zones
        ]
        inter_dist_sum = 0.0
        dist_count = 0
        for i in range(len(centroids)):
            for j in range(i + 1, len(centroids)):
                inter_dist_sum += float(np.linalg.norm(centroids[i] - centroids[j]))
                dist_count += 1
        avg_inter_dist = inter_dist_sum / max(1, dist_count)

        # Intra-cluster spreads
        spread_sum = 0.0
        for z in target_zones:
            delays = [s.delay_ms for s in self._samples.get(z, []) if s.is_valid]
            hfrs = [s.hfr for s in self._samples.get(z, []) if s.is_valid]
            d_mad = float(np.median(np.abs(delays - np.median(delays)))) if delays else 0.5
            h_mad = float(np.median(np.abs(hfrs - np.median(hfrs)))) if hfrs else 0.2
            spread_sum += (d_mad + h_mad) / 2.0
        avg_spread = spread_sum / len(target_zones)

        raw_separability = avg_inter_dist / (avg_spread + 1e-4)
        # Normalize into 0.0 to 1.0 using sigmoid-like curve
        separability = round(min(1.0, max(0.0, raw_separability / (raw_separability + 2.0))), 3)

        quality_passed = len(issues) == 0

        return CalibrationQuality(
            total_samples=total_samples,
            valid_samples_per_zone=valid_counts,
            rejected_per_zone=rejected_counts,
            zone_separability=separability,
            delay_overlap=delay_overlap,
            hfr_overlap=hfr_overlap,
            quality_passed=quality_passed,
            issues=issues,
        )

    def calculate_profile(
        self,
        profile_name: str,
        device_name: str,
        sample_rate: int,
        channels: int,
    ) -> CalibrationProfile:
        """Calculate and return a final CalibrationProfile based on collected samples.

        Args:
            profile_name: Identifying name for this profile.
            device_name: Audio capture device description.
            sample_rate: Sampling frequency in Hz.
            channels: Number of audio channels.

        Returns:
            Calculated CalibrationProfile ready for persistence or classification.
        """
        zones_summary: dict[str, dict[str, Any]] = {}
        target_zones = (Zone.LT, Zone.LB, Zone.RT, Zone.RB)

        delay_medians: dict[Zone, float] = {}
        hfr_medians: dict[Zone, float] = {}

        for z in target_zones:
            valid_samples = [s for s in self._samples.get(z, []) if s.is_valid]
            delays = np.array([s.delay_ms for s in valid_samples], dtype=float)
            hfrs = np.array([s.hfr for s in valid_samples], dtype=float)

            if len(delays) > 0:
                d_med = float(np.median(delays))
                d_mad = float(np.median(np.abs(delays - d_med)))
            else:
                d_med, d_mad = 0.0, 0.5

            if len(hfrs) > 0:
                h_med = float(np.median(hfrs))
                h_mad = float(np.median(np.abs(hfrs - h_med)))
            else:
                h_med, h_mad = 1.0, 0.2

            delay_medians[z] = d_med
            hfr_medians[z] = h_med

            zones_summary[z.value] = {
                "delay_median": round(d_med, 4),
                "delay_mad": round(d_mad, 4),
                "hfr_median": round(h_med, 4),
                "hfr_mad": round(h_mad, 4),
                "sample_count": len(valid_samples),
                "raw_delays": [round(float(d), 4) for d in delays],
                "raw_hfrs": [round(float(h), 4) for h in hfrs],
            }

        # Midpoint horizontal delay threshold between left zones and right zones
        left_avg_delay = (delay_medians[Zone.LT] + delay_medians[Zone.LB]) / 2.0
        right_avg_delay = (delay_medians[Zone.RT] + delay_medians[Zone.RB]) / 2.0
        delay_threshold = (left_avg_delay + right_avg_delay) / 2.0

        # Midpoint vertical HFR threshold between top zones and bottom zones
        top_avg_hfr = (hfr_medians[Zone.LT] + hfr_medians[Zone.RT]) / 2.0
        bottom_avg_hfr = (hfr_medians[Zone.LB] + hfr_medians[Zone.RB]) / 2.0
        hfr_threshold = (top_avg_hfr + bottom_avg_hfr) / 2.0

        quality = self.evaluate_quality()

        # Serialize quality dataclass (converting Zone enum keys to str)
        quality_dict = asdict(quality)
        quality_dict["valid_samples_per_zone"] = {
            z.value if isinstance(z, Zone) else str(z): count
            for z, count in quality.valid_samples_per_zone.items()
        }
        quality_dict["rejected_per_zone"] = {
            z.value if isinstance(z, Zone) else str(z): count
            for z, count in quality.rejected_per_zone.items()
        }

        profile = CalibrationProfile(
            profile_name=profile_name,
            device_name=device_name,
            sample_rate=sample_rate,
            channels=channels,
            created_at=datetime.now(UTC).isoformat(),
            schema_version=1,
            zones=zones_summary,
            delay_threshold=round(delay_threshold, 4),
            hfr_threshold=round(hfr_threshold, 4),
            quality=quality_dict,
            notes="",
        )

        logger.info(
            "Computed profile '%s': delay_thresh=%.3f, hfr_thresh=%.3f, quality_passed=%s",
            profile_name,
            delay_threshold,
            hfr_threshold,
            quality.quality_passed,
        )
        return profile

    def to_dict(self, profile: CalibrationProfile) -> dict[str, Any]:
        """Serialize a CalibrationProfile into a JSON-compatible dictionary.

        Args:
            profile: CalibrationProfile instance.

        Returns:
            Dictionary representation.
        """
        return asdict(profile)

    def from_dict(self, data: dict[str, Any]) -> CalibrationProfile:
        """Deserialize a dictionary into a CalibrationProfile.

        Args:
            data: Dictionary serialized from to_dict or loaded from JSON.

        Returns:
            CalibrationProfile instance.
        """
        return CalibrationProfile(
            profile_name=str(data.get("profile_name", "default")),
            device_name=str(data.get("device_name", "unknown")),
            sample_rate=int(data.get("sample_rate", 48000)),
            channels=int(data.get("channels", 2)),
            created_at=str(data.get("created_at", "")),
            schema_version=int(data.get("schema_version", 1)),
            zones=dict(data.get("zones", {})),
            delay_threshold=float(data.get("delay_threshold", 0.0)),
            hfr_threshold=float(data.get("hfr_threshold", 1.0)),
            quality=dict(data.get("quality", {})),
            notes=str(data.get("notes", "")),
        )

    def reset(self) -> None:
        """Clear all buffered samples and reset state to IDLE."""
        self.state = CalibrationState.IDLE
        self._samples = {
            Zone.LT: [],
            Zone.LB: [],
            Zone.RT: [],
            Zone.RB: [],
        }
        logger.debug("CalibrationEngine reset to IDLE")
