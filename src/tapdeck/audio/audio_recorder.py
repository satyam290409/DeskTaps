"""Audio recording and persistence module for TapDeck.

Handles saving diagnostic and transient tap audio buffers to disk as WAV files,
managing retention limits, and retrieving metadata.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile

logger = logging.getLogger(__name__)


@dataclass
class RecordingMetadata:
    """Metadata describing a saved acoustic tap recording."""

    filename: str
    device_name: str
    sample_rate: int
    channels: int
    duration_seconds: float
    timestamp_iso: str
    size_bytes: int
    label: str | None = None


class AudioRecorder:
    """Records audio buffers to disk and enforces retention policies."""

    def __init__(
        self,
        output_dir: Path | None = None,
        max_recordings: int = 100,
        sample_rate: int = 48000,
        channels: int = 2,
    ) -> None:
        """Initialize AudioRecorder.

        Args:
            output_dir: Target directory for WAV recordings.
                Defaults to %LOCALAPPDATA%/TapDeck/recordings.
            max_recordings: Maximum number of audio recordings to retain on disk.
            sample_rate: Default sample rate in Hz.
            channels: Default number of channels.
        """
        if output_dir is None:
            local_app_data = os.environ.get("LOCALAPPDATA", ".")
            self.output_dir = Path(local_app_data) / "TapDeck" / "recordings"
        else:
            self.output_dir = Path(output_dir)

        self.max_recordings = max(1, max_recordings)
        self.sample_rate = sample_rate
        self.channels = channels
        self._lock = threading.Lock()

        # Ensure target directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def record_buffer(
        self,
        buffer: np.ndarray,
        label: str | None = None,
        device_name: str = "default_device",
    ) -> RecordingMetadata:
        """Save an audio buffer as a WAV file with accompanying metadata.

        Args:
            buffer: Audio sample array (1D for mono, 2D for multi-channel).
            label: Optional label tag for the tap (e.g., 'LT', 'false_positive').
            device_name: Description or name of the capture audio device.

        Returns:
            RecordingMetadata describing the saved recording.
        """
        with self._lock:
            self.output_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now(UTC)
            timestamp_str = now.strftime("%Y%m%d_%H%M%S_%f")
            timestamp_iso = now.isoformat()

            # Clean label for safe filename usage
            if label:
                clean_label = re.sub(r"[^\w\-]", "_", label.strip())
                filename = f"tap_{timestamp_str}_{clean_label}.wav"
            else:
                filename = f"tap_{timestamp_str}.wav"

            wav_path = self.output_dir / filename
            json_path = wav_path.with_suffix(".json")

            # Determine channel count and samples count
            if buffer.ndim == 1:
                channels = 1
                sample_count = len(buffer)
            else:
                sample_count, channels = buffer.shape[0], buffer.shape[1]

            duration_seconds = (
                sample_count / float(self.sample_rate) if self.sample_rate > 0 else 0.0
            )

            # Normalize and convert buffer to float32 for WAV serialization
            audio_data = buffer.astype(np.float32)

            wavfile.write(str(wav_path), self.sample_rate, audio_data)
            size_bytes = wav_path.stat().st_size

            meta = RecordingMetadata(
                filename=filename,
                device_name=device_name,
                sample_rate=self.sample_rate,
                channels=channels,
                duration_seconds=duration_seconds,
                timestamp_iso=timestamp_iso,
                size_bytes=size_bytes,
                label=label,
            )

            # Persist sidecar metadata JSON
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(asdict(meta), f, indent=2)
            except OSError as exc:
                logger.warning("Failed to write metadata sidecar %s: %s", json_path, exc)

            # Prune oldest recordings if exceeding max_recordings
            self._prune_excess_recordings()

            logger.info(
                "Saved recording %s (%.2f s, %d bytes)", filename, duration_seconds, size_bytes
            )
            return meta

    def list_recordings(self) -> list[RecordingMetadata]:
        """List all recordings in the output directory, newest first.

        Returns:
            List of RecordingMetadata objects.
        """
        with self._lock:
            if not self.output_dir.exists():
                return []

            results: list[RecordingMetadata] = []
            wav_files = sorted(
                self.output_dir.glob("*.wav"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            for wav_path in wav_files:
                json_path = wav_path.with_suffix(".json")
                if json_path.exists():
                    try:
                        with open(json_path, encoding="utf-8") as f:
                            data: dict[str, Any] = json.load(f)
                            results.append(RecordingMetadata(**data))
                            continue
                    except Exception as exc:
                        logger.debug("Could not read sidecar %s: %s", json_path, exc)

                # Fallback to reading file stats if no valid sidecar exists
                try:
                    stat = wav_path.stat()
                    rate, data = wavfile.read(str(wav_path))
                    channels = 1 if data.ndim == 1 else data.shape[1]
                    dur = len(data) / float(rate) if rate > 0 else 0.0
                    iso_time = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()
                    results.append(
                        RecordingMetadata(
                            filename=wav_path.name,
                            device_name="unknown",
                            sample_rate=rate,
                            channels=channels,
                            duration_seconds=dur,
                            timestamp_iso=iso_time,
                            size_bytes=stat.st_size,
                            label=None,
                        )
                    )
                except Exception as exc:
                    logger.warning("Error reading WAV info for %s: %s", wav_path, exc)

            return results

    def delete_recording(self, filename: str) -> bool:
        """Delete a recording and its associated metadata sidecar.

        Args:
            filename: Base filename of the recording to delete.

        Returns:
            True if recording was found and deleted, False otherwise.
        """
        with self._lock:
            wav_path = self.get_recording_path(filename)
            json_path = wav_path.with_suffix(".json")

            deleted = False
            if wav_path.exists():
                try:
                    wav_path.unlink()
                    deleted = True
                except OSError as exc:
                    logger.error("Failed to delete WAV file %s: %s", wav_path, exc)

            if json_path.exists():
                try:
                    json_path.unlink()
                except OSError as exc:
                    logger.debug("Failed to delete JSON sidecar %s: %s", json_path, exc)

            return deleted

    def delete_all_recordings(self) -> int:
        """Delete all recordings and sidecar files in the output directory.

        Returns:
            Count of deleted WAV recordings.
        """
        with self._lock:
            if not self.output_dir.exists():
                return 0

            count = 0
            for wav_file in list(self.output_dir.glob("*.wav")):
                json_file = wav_file.with_suffix(".json")
                try:
                    wav_file.unlink()
                    count += 1
                except OSError as exc:
                    logger.error("Failed to delete %s: %s", wav_file, exc)

                if json_file.exists():
                    with contextlib.suppress(OSError):
                        json_file.unlink()

            logger.info("Deleted %d recordings from %s", count, self.output_dir)
            return count

    def get_recording_path(self, filename: str) -> Path:
        """Return the absolute Path for a given recording filename.

        Args:
            filename: Recording filename.

        Returns:
            Path object.
        """
        return self.output_dir / Path(filename).name

    def load_recording(self, filename: str) -> tuple[int, np.ndarray]:
        """Load audio sample data from a recording file.

        Args:
            filename: Recording filename.

        Returns:
            Tuple of (sample_rate, audio_data_array).

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        with self._lock:
            path = self.get_recording_path(filename)
            if not path.exists():
                raise FileNotFoundError(f"Recording file not found: {path}")

            rate, data = wavfile.read(str(path))
            return int(rate), data

    def _prune_excess_recordings(self) -> None:
        """Internal helper to remove oldest recordings if exceeding max_recordings."""
        wav_files = sorted(
            self.output_dir.glob("*.wav"),
            key=lambda p: p.stat().st_mtime,
        )

        excess = len(wav_files) - self.max_recordings
        if excess <= 0:
            return

        for path in wav_files[:excess]:
            try:
                path.unlink()
                sidecar = path.with_suffix(".json")
                if sidecar.exists():
                    sidecar.unlink()
                logger.debug("Pruned excess recording: %s", path.name)
            except OSError as exc:
                logger.warning("Failed to prune recording %s: %s", path, exc)
