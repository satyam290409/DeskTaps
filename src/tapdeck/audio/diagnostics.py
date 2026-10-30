"""Diagnostics and performance monitoring for the audio pipeline."""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class AudioDiagnostics:
    """Comprehensive diagnostic snapshot of the audio capture and detection pipeline."""

    device_name: str
    device_index: int
    channels: int
    sample_rate: int
    stream_active: bool
    frames_captured: int
    frames_dropped: int
    overflows: int
    underflows: int
    processing_latency_ms: float
    peak_processing_latency_ms: float
    detection_candidates: int
    detection_accepted: int
    detection_rejected: int
    detection_duplicates: int
    cpu_percent: float
    memory_mb: float
    uptime_seconds: float


class DiagnosticsCollector:
    """Collects and aggregates real-time performance metrics and diagnostics.

    Tracks audio stream health, latency statistics, transient detection rates,
    and system resource utilization. Supports JSON and CSV time-series exports.
    """

    def __init__(self, max_history_entries: int = 1000) -> None:
        """Initialize DiagnosticsCollector.

        Args:
            max_history_entries: Maximum number of snapshots to retain in memory.
        """
        self._lock = threading.Lock()
        self._max_history = max(10, max_history_entries)
        self._process = psutil.Process(os.getpid())
        self._start_time = time.monotonic()

        # Stream & device stats
        self.device_name: str = "Uninitialized"
        self.device_index: int = -1
        self.channels: int = 2
        self.sample_rate: int = 48000
        self.stream_active: bool = False
        self.frames_captured: int = 0
        self.frames_dropped: int = 0
        self.overflows: int = 0
        self.underflows: int = 0

        # Latency stats
        self.processing_latency_ms: float = 0.0
        self.peak_processing_latency_ms: float = 0.0

        # Detection stats
        self.detection_candidates: int = 0
        self.detection_accepted: int = 0
        self.detection_rejected: int = 0
        self.detection_duplicates: int = 0

        # Time-series history: list of (monotonic_timestamp, AudioDiagnostics)
        self._history: list[tuple[float, AudioDiagnostics]] = []

    def update(
        self,
        capture_stats: dict[str, Any] | None = None,
        detector_stats: dict[str, Any] | None = None,
        processing_latency: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Update internal diagnostic metrics.

        Accepts dictionary summaries from subsystems or explicit metric arguments.

        Args:
            capture_stats: Dict of capture stats (e.g., frames_captured, overflows).
            detector_stats: Dict of detector stats (e.g., candidates, accepted).
            processing_latency: Processing latency in milliseconds for latest block.
            **kwargs: Direct field overrides matching AudioDiagnostics attributes.
        """
        with self._lock:
            # Handle capture_stats dictionary
            if capture_stats:
                if "device_name" in capture_stats:
                    self.device_name = str(capture_stats["device_name"])
                if "device_index" in capture_stats:
                    self.device_index = int(capture_stats["device_index"])
                if "channels" in capture_stats:
                    self.channels = int(capture_stats["channels"])
                if "sample_rate" in capture_stats:
                    self.sample_rate = int(capture_stats["sample_rate"])
                if "stream_active" in capture_stats:
                    self.stream_active = bool(capture_stats["stream_active"])
                if "frames_captured" in capture_stats:
                    self.frames_captured = int(capture_stats["frames_captured"])
                if "frames_dropped" in capture_stats:
                    self.frames_dropped = int(capture_stats["frames_dropped"])
                if "overflows" in capture_stats:
                    self.overflows = int(capture_stats["overflows"])
                if "underflows" in capture_stats:
                    self.underflows = int(capture_stats["underflows"])

            # Handle detector_stats dictionary
            if detector_stats:
                if "candidates" in detector_stats:
                    self.detection_candidates = int(detector_stats["candidates"])
                if "accepted" in detector_stats:
                    self.detection_accepted = int(detector_stats["accepted"])
                if "rejected" in detector_stats:
                    self.detection_rejected = int(detector_stats["rejected"])
                if "duplicates" in detector_stats:
                    self.detection_duplicates = int(detector_stats["duplicates"])

            # Handle latency
            lat = (
                processing_latency
                if processing_latency is not None
                else kwargs.get("processing_latency_ms")
            )
            if lat is not None:
                self.processing_latency_ms = float(lat)
                if self.processing_latency_ms > self.peak_processing_latency_ms:
                    self.peak_processing_latency_ms = self.processing_latency_ms

            # Handle direct keyword arguments
            for key, val in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, val)

    def snapshot(self) -> AudioDiagnostics:
        """Capture and record a current diagnostic snapshot.

        Returns:
            An AudioDiagnostics instance with up-to-date metrics.
        """
        with self._lock:
            uptime = max(0.0, time.monotonic() - self._start_time)

            cpu_val: float = 0.0
            mem_val: float = 0.0
            try:
                cpu_val = float(self._process.cpu_percent(interval=None))
                mem_info = self._process.memory_info()
                mem_val = float(mem_info.rss / (1024.0 * 1024.0))
            except Exception as exc:
                logger.debug("Failed to read process memory/cpu: %s", exc)

            snap = AudioDiagnostics(
                device_name=self.device_name,
                device_index=self.device_index,
                channels=self.channels,
                sample_rate=self.sample_rate,
                stream_active=self.stream_active,
                frames_captured=self.frames_captured,
                frames_dropped=self.frames_dropped,
                overflows=self.overflows,
                underflows=self.underflows,
                processing_latency_ms=self.processing_latency_ms,
                peak_processing_latency_ms=self.peak_processing_latency_ms,
                detection_candidates=self.detection_candidates,
                detection_accepted=self.detection_accepted,
                detection_rejected=self.detection_rejected,
                detection_duplicates=self.detection_duplicates,
                cpu_percent=cpu_val,
                memory_mb=round(mem_val, 2),
                uptime_seconds=round(uptime, 2),
            )

            # Record in history buffer
            self._history.append((time.time(), snap))
            if len(self._history) > self._max_history:
                self._history.pop(0)

            return snap

    def export_csv(self, filepath: Path | str) -> None:
        """Export time-series of recorded snapshots to a CSV file.

        Args:
            filepath: Destination CSV file path.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            records = list(self._history)
            if not records:
                # Capture at least one entry
                records = [(time.time(), self._snapshot_internal())]

        field_names = [
            "timestamp",
            "device_name",
            "device_index",
            "channels",
            "sample_rate",
            "stream_active",
            "frames_captured",
            "frames_dropped",
            "overflows",
            "underflows",
            "processing_latency_ms",
            "peak_processing_latency_ms",
            "detection_candidates",
            "detection_accepted",
            "detection_rejected",
            "detection_duplicates",
            "cpu_percent",
            "memory_mb",
            "uptime_seconds",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=field_names)
            writer.writeheader()
            for ts, snap in records:
                row = asdict(snap)
                row["timestamp"] = ts
                writer.writerow(row)

        logger.info("Exported %d diagnostic snapshots to CSV %s", len(records), path)

    def export_json(self, filepath: Path | str) -> None:
        """Export the current diagnostic snapshot to a JSON file.

        Args:
            filepath: Destination JSON file path.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        snap = self.snapshot()
        data = asdict(snap)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info("Exported diagnostics snapshot to JSON %s", path)

    def reset(self) -> None:
        """Reset all counters, latency peaks, and history snapshots."""
        with self._lock:
            self._start_time = time.monotonic()
            self.frames_captured = 0
            self.frames_dropped = 0
            self.overflows = 0
            self.underflows = 0
            self.processing_latency_ms = 0.0
            self.peak_processing_latency_ms = 0.0
            self.detection_candidates = 0
            self.detection_accepted = 0
            self.detection_rejected = 0
            self.detection_duplicates = 0
            self._history.clear()
            logger.info("Diagnostics collector counters and history reset")

    def _snapshot_internal(self) -> AudioDiagnostics:
        """Generate snapshot without acquiring lock (internal use)."""
        uptime = max(0.0, time.monotonic() - self._start_time)
        cpu_val = 0.0
        mem_val = 0.0
        try:
            cpu_val = float(self._process.cpu_percent(interval=None))
            mem_val = float(self._process.memory_info().rss / (1024.0 * 1024.0))
        except Exception:
            pass

        return AudioDiagnostics(
            device_name=self.device_name,
            device_index=self.device_index,
            channels=self.channels,
            sample_rate=self.sample_rate,
            stream_active=self.stream_active,
            frames_captured=self.frames_captured,
            frames_dropped=self.frames_dropped,
            overflows=self.overflows,
            underflows=self.underflows,
            processing_latency_ms=self.processing_latency_ms,
            peak_processing_latency_ms=self.peak_processing_latency_ms,
            detection_candidates=self.detection_candidates,
            detection_accepted=self.detection_accepted,
            detection_rejected=self.detection_rejected,
            detection_duplicates=self.detection_duplicates,
            cpu_percent=cpu_val,
            memory_mb=round(mem_val, 2),
            uptime_seconds=round(uptime, 2),
        )
