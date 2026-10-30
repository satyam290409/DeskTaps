"""Audio capture, DSP processing, and zone classification modules."""

from __future__ import annotations

from tapdeck.audio.capture import (
    AudioCapture,
    AudioFrame,
    CaptureState,
    CaptureStats,
)
from tapdeck.audio.device_manager import (
    AudioDeviceInfo,
    DeviceCapability,
    DeviceManager,
)
from tapdeck.audio.feature_extractor import (
    FeatureConfig,
    FeatureExtractor,
    TapFeatures,
)
from tapdeck.audio.gcc_phat import (
    GCCResult,
    gcc_phat,
)
from tapdeck.audio.preprocessing import (
    BandpassFilter,
    FilterConfig,
)
from tapdeck.audio.transient_detector import (
    DetectorConfig,
    DetectorStats,
    TransientConfig,
    TransientDetector,
    TransientEvent,
)

__all__ = [
    "AudioCapture",
    "AudioFrame",
    "CaptureState",
    "CaptureStats",
    "AudioDeviceInfo",
    "DeviceCapability",
    "DeviceManager",
    "BandpassFilter",
    "FilterConfig",
    "TransientDetector",
    "TransientEvent",
    "DetectorConfig",
    "DetectorStats",
    "TransientConfig",
    "gcc_phat",
    "GCCResult",
    "FeatureExtractor",
    "FeatureConfig",
    "TapFeatures",
]
