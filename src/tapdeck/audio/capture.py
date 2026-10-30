"""Real-time audio capture pipeline using sounddevice and threaded buffering."""

from __future__ import annotations

import contextlib
import logging
import queue
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import sounddevice as sd

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


class CaptureState(StrEnum):
    """Lifecycle states for the AudioCapture stream."""

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    STOPPING = "STOPPING"


@dataclass(slots=True)
class AudioFrame:
    """A single frame of captured audio with metadata."""

    data: np.ndarray
    timestamp: float
    frame_index: int
    channels: int
    sample_rate: int


@dataclass(slots=True)
class CaptureStats:
    """Telemetry counters and uptime stats for the capture stream."""

    frames_captured: int = 0
    frames_dropped: int = 0
    overflows: int = 0
    underflows: int = 0
    errors: int = 0
    uptime_seconds: float = 0.0


class AudioCapture:
    """Thread-safe real-time audio capture engine backed by PortAudio."""

    def __init__(
        self,
        device_index: int | None = None,
        channels: int = 2,
        sample_rate: int = 48000,
        block_size: int = 512,
        queue_size: int = 256,
    ) -> None:
        self.device_index = device_index
        self.channels = channels
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.queue_size = queue_size

        self._state: CaptureState = CaptureState.IDLE
        self._lock = threading.RLock()
        self._queue: queue.Queue[AudioFrame] = queue.Queue(maxsize=queue_size)
        self._stream: sd.InputStream | None = None

        self._frame_index: int = 0
        self._frames_captured: int = 0
        self._frames_dropped: int = 0
        self._overflows: int = 0
        self._underflows: int = 0
        self._errors: int = 0

        self._start_monotonic: float | None = None
        self._last_resume_monotonic: float | None = None
        self._accumulated_uptime: float = 0.0

    @property
    def state(self) -> CaptureState:
        """Returns the current capture state."""
        with self._lock:
            return self._state

    @property
    def stats(self) -> CaptureStats:
        """Returns a snapshot of current capture statistics."""
        with self._lock:
            uptime = self._accumulated_uptime
            if self._state == CaptureState.RUNNING and self._last_resume_monotonic is not None:
                uptime += time.monotonic() - self._last_resume_monotonic

            return CaptureStats(
                frames_captured=self._frames_captured,
                frames_dropped=self._frames_dropped,
                overflows=self._overflows,
                underflows=self._underflows,
                errors=self._errors,
                uptime_seconds=uptime,
            )

    def _set_state(self, new_state: CaptureState) -> None:
        """Updates internal state and logs transition."""
        logger.info("AudioCapture state changed: %s -> %s", self._state.value, new_state.value)
        self._state = new_state

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback invoked by PortAudio from a dedicated audio thread."""
        try:
            if status:
                if status.input_overflow:
                    self._overflows += 1
                    logger.warning("PortAudio input overflow occurred (count=%d)", self._overflows)
                if status.input_underflow:
                    self._underflows += 1
                    logger.warning(
                        "PortAudio input underflow occurred (count=%d)", self._underflows
                    )

            with self._lock:
                if self._state != CaptureState.RUNNING:
                    return
                current_frame_index = self._frame_index
                self._frame_index += 1

            frame = AudioFrame(
                data=indata.copy(),
                timestamp=time.time(),
                frame_index=current_frame_index,
                channels=self.channels,
                sample_rate=self.sample_rate,
            )

            try:
                self._queue.put_nowait(frame)
                self._frames_captured += 1
            except queue.Full:
                self._frames_dropped += 1
                logger.debug("Capture queue full, dropped frame index %d", current_frame_index)

        except Exception as exc:
            logger.error("Exception in audio callback: %s", exc, exc_info=True)
            with self._lock:
                self._errors += 1
                self._set_state(CaptureState.ERROR)

    def start(self) -> None:
        """Starts audio capture stream."""
        with self._lock:
            if self._state == CaptureState.RUNNING:
                logger.warning("AudioCapture is already running")
                return

            if self._state == CaptureState.PAUSED:
                self.resume()
                return

            self._set_state(CaptureState.STARTING)
            try:
                self._stream = sd.InputStream(
                    device=self.device_index,
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    blocksize=self.block_size,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                self._stream.start()
                now = time.monotonic()
                self._start_monotonic = now
                self._last_resume_monotonic = now
                self._set_state(CaptureState.RUNNING)
                logger.info(
                    "AudioCapture started on device %s (ch=%d, sr=%d, block=%d)",
                    self.device_index,
                    self.channels,
                    self.sample_rate,
                    self.block_size,
                )
            except Exception as exc:
                self._errors += 1
                self._set_state(CaptureState.ERROR)
                logger.error("Failed to start audio capture stream: %s", exc, exc_info=True)
                raise

    def pause(self) -> None:
        """Pauses audio capture, dropping subsequent incoming frames."""
        with self._lock:
            if self._state != CaptureState.RUNNING:
                logger.debug("pause() called while state is %s, ignoring", self._state.value)
                return

            if self._last_resume_monotonic is not None:
                self._accumulated_uptime += time.monotonic() - self._last_resume_monotonic
                self._last_resume_monotonic = None

            self._set_state(CaptureState.PAUSED)

    def resume(self) -> None:
        """Resumes audio capture from paused state."""
        with self._lock:
            if self._state != CaptureState.PAUSED:
                logger.debug("resume() called while state is %s, ignoring", self._state.value)
                return

            self._last_resume_monotonic = time.monotonic()
            self._set_state(CaptureState.RUNNING)

    def stop(self) -> None:
        """Stops the audio stream and releases hardware resources."""
        with self._lock:
            if self._state == CaptureState.IDLE:
                return

            self._set_state(CaptureState.STOPPING)

            if self._state == CaptureState.RUNNING and self._last_resume_monotonic is not None:
                self._accumulated_uptime += time.monotonic() - self._last_resume_monotonic
                self._last_resume_monotonic = None

            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as exc:
                    logger.warning("Error stopping audio stream: %s", exc)
                finally:
                    self._stream = None

            self._set_state(CaptureState.IDLE)
            logger.info("AudioCapture stopped successfully")

    def get_frame(self, timeout: float = 0.1) -> AudioFrame | None:
        """Fetches the next audio frame from the queue, returning None if timeout occurs."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def __del__(self) -> None:
        """Ensures underlying audio stream is closed when garbage collected."""
        with contextlib.suppress(Exception):
            self.stop()
