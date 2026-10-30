"""Audio device enumeration, capability probing, and change detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import sounddevice as sd

logger = logging.getLogger(__name__)

STANDARD_SAMPLE_RATES: list[float] = [
    48000.0,
    44100.0,
    96000.0,
    32000.0,
    22050.0,
    16000.0,
    8000.0,
]


@dataclass(slots=True)
class AudioDeviceInfo:
    """Information and capabilities of an audio device."""

    index: int
    name: str
    hostapi: int
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_default: bool
    supported_rates: list[float] = field(default_factory=list)


@dataclass(slots=True)
class DeviceCapability:
    """Optimal configuration capability for an audio input device."""

    device_index: int
    channels: int
    sample_rate: int
    dtype: str
    hostapi_name: str


class DeviceManager:
    """Manages audio device enumeration, capability querying, and hardware change detection."""

    def __init__(self) -> None:
        self._cached_devices: list[AudioDeviceInfo] = []
        self._cached_signatures: set[tuple[int, str, int, float]] = set()
        # Initialize cache with current system devices
        self.enumerate_devices()

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        """Queries sounddevice and returns all available input devices."""
        devices: list[AudioDeviceInfo] = []
        try:
            device_list = sd.query_devices()
            if isinstance(device_list, dict):
                raw_devices: list[dict[str, Any]] = [device_list]
            else:
                raw_devices = list(device_list)
        except Exception as exc:
            logger.error("Failed to query sound devices: %s", exc, exc_info=True)
            return []

        default_input_index = -1
        try:
            default_devs = sd.default.device
            if isinstance(default_devs, (list, tuple)) and len(default_devs) > 0:
                default_input_index = int(default_devs[0])
            elif isinstance(default_devs, int):
                default_input_index = default_devs
        except Exception as exc:
            logger.debug("Could not determine default audio device: %s", exc)

        signatures: set[tuple[int, str, int, float]] = set()

        for idx, dev in enumerate(raw_devices):
            max_in = int(dev.get("max_input_channels", 0))
            if max_in <= 0:
                continue

            name = str(dev.get("name", f"Device {idx}"))
            hostapi = int(dev.get("hostapi", 0))
            default_sr = float(dev.get("default_samplerate", 44100.0))
            is_default = idx == default_input_index

            supported_rates: list[float] = []
            test_channels = min(max_in, 2)
            for rate in STANDARD_SAMPLE_RATES:
                if self.test_device_config(idx, test_channels, int(rate)):
                    supported_rates.append(rate)

            if not supported_rates and default_sr > 0:
                supported_rates.append(default_sr)

            info = AudioDeviceInfo(
                index=idx,
                name=name,
                hostapi=hostapi,
                max_input_channels=max_in,
                max_output_channels=int(dev.get("max_output_channels", 0)),
                default_samplerate=default_sr,
                is_default=is_default,
                supported_rates=supported_rates,
            )
            devices.append(info)
            signatures.add((idx, name, max_in, default_sr))

        self._cached_devices = devices
        self._cached_signatures = signatures
        logger.debug("Enumerated %d audio input devices", len(devices))
        return devices

    def get_default_input(self) -> AudioDeviceInfo | None:
        """Returns the Windows default input device, or None if unavailable."""
        devices = self.enumerate_devices()
        for device in devices:
            if device.is_default:
                return device
        return devices[0] if devices else None

    def find_stereo_inputs(self) -> list[AudioDeviceInfo]:
        """Filters input devices that have at least 2 input channels."""
        return [dev for dev in self.enumerate_devices() if dev.max_input_channels >= 2]

    def test_device_config(
        self,
        device_index: int,
        channels: int,
        sample_rate: int,
        dtype: str = "float32",
    ) -> bool:
        """Tests whether a specific input device configuration is supported."""
        try:
            sd.check_input_settings(
                device=device_index,
                channels=channels,
                samplerate=sample_rate,
                dtype=dtype,
            )
            return True
        except (sd.PortAudioError, ValueError, Exception) as exc:
            logger.debug(
                "Device config rejected for dev=%d ch=%d sr=%d dtype=%s: %s",
                device_index,
                channels,
                sample_rate,
                dtype,
                exc,
            )
            return False

    def get_best_config(self, device_index: int) -> DeviceCapability | None:
        """Finds the best supported configuration for a given device.

        Preference order:
        - Channel count: 4 channels if available, then 2 channels, then 1 channel.
        - Sample rate: 48 kHz, then 44.1 kHz, then other standard rates.
        """
        try:
            raw_info = sd.query_devices(device_index)
            if not isinstance(raw_info, dict):
                logger.error("Invalid device info returned for index %d", device_index)
                return None
        except Exception as exc:
            logger.error("Failed to query device %d: %s", device_index, exc)
            return None

        max_in = int(raw_info.get("max_input_channels", 0))
        if max_in <= 0:
            logger.warning("Device %d has no input channels", device_index)
            return None

        hostapi_idx = int(raw_info.get("hostapi", 0))
        hostapi_name = "Unknown"
        try:
            hostapis = sd.query_hostapis()
            if isinstance(hostapis, (list, tuple)) and 0 <= hostapi_idx < len(hostapis):
                hostapi_name = str(hostapis[hostapi_idx].get("name", "Unknown"))
            elif isinstance(hostapis, dict) and hostapis.get("index") == hostapi_idx:
                hostapi_name = str(hostapis.get("name", "Unknown"))
        except Exception as exc:
            logger.debug("Failed to query host API for index %d: %s", hostapi_idx, exc)

        # Candidate channel counts: prefer 4ch, then 2ch, then 1ch
        channel_candidates: list[int] = []
        if max_in >= 4:
            channel_candidates.append(4)
        if max_in >= 2 and 2 not in channel_candidates:
            channel_candidates.append(2)
        if max_in >= 1 and 1 not in channel_candidates:
            channel_candidates.append(1)
        if max_in not in channel_candidates:
            channel_candidates.append(max_in)

        # Candidate sample rates: prefer 48000, then 44100, then others
        rate_candidates = [48000, 44100, 96000, 32000, 22050, 16000]

        for ch in channel_candidates:
            for sr in rate_candidates:
                if self.test_device_config(
                    device_index, channels=ch, sample_rate=sr, dtype="float32"
                ):
                    logger.info(
                        "Selected best config for dev=%d: %d ch, %d Hz, %s (%s)",
                        device_index,
                        ch,
                        sr,
                        "float32",
                        hostapi_name,
                    )
                    return DeviceCapability(
                        device_index=device_index,
                        channels=ch,
                        sample_rate=sr,
                        dtype="float32",
                        hostapi_name=hostapi_name,
                    )

        logger.warning("No standard configuration found for device %d", device_index)
        return None

    def detect_device_change(self) -> bool:
        """Compares current device list with cached list and returns True if changed."""
        try:
            device_list = sd.query_devices()
            raw_devices = [device_list] if isinstance(device_list, dict) else list(device_list)
        except Exception as exc:
            logger.error("Failed to query devices during change detection: %s", exc)
            return False

        current_signatures: set[tuple[int, str, int, float]] = set()
        for idx, dev in enumerate(raw_devices):
            max_in = int(dev.get("max_input_channels", 0))
            if max_in > 0:
                name = str(dev.get("name", f"Device {idx}"))
                default_sr = float(dev.get("default_samplerate", 44100.0))
                current_signatures.add((idx, name, max_in, default_sr))

        if current_signatures != self._cached_signatures:
            logger.info("Audio device configuration change detected")
            self.enumerate_devices()
            return True

        return False
