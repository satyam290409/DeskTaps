"""Main application controller and background audio processing pipeline for TapDeck 2.0."""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import asdict
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from tapdeck.actions.action_dispatcher import ActionDispatcher
from tapdeck.audio.capture import AudioCapture
from tapdeck.audio.device_manager import DeviceManager
from tapdeck.audio.diagnostics import DiagnosticsCollector
from tapdeck.audio.feature_extractor import FeatureConfig, FeatureExtractor
from tapdeck.audio.gcc_phat import gcc_phat
from tapdeck.audio.preprocessing import BandpassFilter, FilterConfig
from tapdeck.audio.transient_detector import DetectorConfig, TransientDetector
from tapdeck.audio.zone_classifier import ClassifierConfig, Zone, ZoneClassifier
from tapdeck.combos.combo_engine import ComboConfig, ComboEngine
from tapdeck.config.config_manager import ConfigManager
from tapdeck.tray.tray_manager import TrayManager, TrayState
from tapdeck.ui.diagnostics_window import DiagnosticsWindow

logger = logging.getLogger(__name__)


class ProcessingWorker(QObject):
    """Audio processing worker that consumes frames from AudioCapture and runs DSP detection."""

    tap_detected = Signal(dict)
    trigger_emitted = Signal(str, float)
    error_occurred = Signal(str)
    diagnostics_updated = Signal(dict)

    def __init__(
        self,
        capture: AudioCapture,
        filter_stage: BandpassFilter,
        detector: TransientDetector,
        feature_extractor: FeatureExtractor,
        classifier: ZoneClassifier,
        combo_engine: ComboEngine,
        diagnostics: DiagnosticsCollector,
        engine_lock: threading.Lock,
        sample_rate: int = 48000,
    ) -> None:
        super().__init__()
        self.capture = capture
        self.filter = filter_stage
        self.detector = detector
        self.feature_extractor = feature_extractor
        self.classifier = classifier
        self.combo_engine = combo_engine
        self.diagnostics = diagnostics
        self._engine_lock = engine_lock
        self.sample_rate = sample_rate
        self._running: bool = False
        self._last_diag_time: float = 0.0

    @Slot()
    def start_processing(self) -> None:
        """Continuously consume and process audio frames from the capture queue."""
        self._running = True
        logger.info("ProcessingWorker loop started.")

        while self._running:
            try:
                frame = self.capture.get_frame(timeout=0.02)
                now = time.time()

                # Check combo engine coincidence timeouts
                with self._engine_lock:
                    timeout_events = self.combo_engine.check_timeout(now)
                for event in timeout_events:
                    self.trigger_emitted.emit(event.token.value, event.confidence)

                if frame is None:
                    continue

                t0 = time.perf_counter()

                # Stage 1: Bandpass Preprocessing
                filtered = self.filter.process(frame.data)

                # Stage 2: Transient Detection
                transient = self.detector.process(
                    frame=filtered,
                    timestamp=frame.timestamp,
                    frame_index=frame.frame_index,
                )

                latency_ms = (time.perf_counter() - t0) * 1000.0

                # Stage 3: Localization & Classification for accepted transients
                if transient is not None and not transient.is_duplicate:
                    delay_ms = 0.0
                    gcc_conf = 0.0

                    # Multi-channel GCC-PHAT delay estimation
                    if filtered.ndim == 2 and filtered.shape[1] >= 2:
                        gcc_res = gcc_phat(
                            filtered[:, 0],
                            filtered[:, 1],
                            sample_rate=self.sample_rate,
                        )
                        delay_ms = gcc_res.delay_ms
                        gcc_conf = gcc_res.confidence

                    # Feature extraction
                    features = self.feature_extractor.extract(filtered)
                    hfr = features.hfr

                    # Spatial quadrant classification
                    classification = self.classifier.classify(
                        delay_ms=delay_ms,
                        hfr=hfr,
                        features={
                            "peak_to_rms": features.peak_to_rms,
                            "spectral_centroid_hz": features.spectral_centroid_hz,
                            "gcc_confidence": gcc_conf,
                        },
                    )

                    tap_data = {
                        "timestamp": transient.timestamp,
                        "frame_index": transient.frame_index,
                        "zone": classification.zone.value,
                        "confidence": classification.confidence,
                        "delay_ms": delay_ms,
                        "hfr": hfr,
                        "energy": transient.energy,
                        "peak_amplitude": transient.peak_amplitude,
                        "per_zone_scores": {
                            z.value: s for z, s in classification.per_zone_scores.items()
                        },
                        "rejection_reason": classification.rejection_reason,
                    }
                    self.tap_detected.emit(tap_data)

                    # Pass into combo state machine if zone is valid
                    if classification.zone != Zone.UNKNOWN:
                        with self._engine_lock:
                            triggers = self.combo_engine.process_tap(
                                zone=classification.zone,
                                timestamp=transient.timestamp,
                                confidence=classification.confidence,
                                features={"delay_ms": delay_ms, "hfr": hfr},
                            )
                        for trig in triggers:
                            self.trigger_emitted.emit(trig.token.value, trig.confidence)

                # Stage 4: Diagnostics Telemetry Update
                self.diagnostics.update(
                    capture_stats={
                        "frames_captured": self.capture.stats.frames_captured,
                        "frames_dropped": self.capture.stats.frames_dropped,
                        "overflows": self.capture.stats.overflows,
                        "underflows": self.capture.stats.underflows,
                        "stream_active": self.capture.state.value == "RUNNING",
                    },
                    detector_stats={
                        "candidates": self.detector.stats.candidates,
                        "accepted": self.detector.stats.accepted,
                        "rejected": self.detector.stats.rejected,
                        "duplicates": self.detector.stats.duplicates,
                    },
                    processing_latency=latency_ms,
                )

                # Emit diagnostic telemetry periodically (~5 Hz)
                if now - self._last_diag_time >= 0.2:
                    self._last_diag_time = now
                    snap = self.diagnostics.snapshot()
                    self.diagnostics_updated.emit(asdict(snap))

            except Exception as exc:
                logger.exception("Error in processing worker: %s", exc)
                self.error_occurred.emit(str(exc))

        logger.info("ProcessingWorker loop terminated.")

    @Slot()
    def stop_processing(self) -> None:
        """Request graceful termination of the processing loop."""
        self._running = False


class TapDeckApp:
    """Coordinates subsystems, lifecycle, background threads, and user interface."""

    def __init__(
        self,
        diagnostics_mode: bool = False,
        test_mode: bool = False,
        device_index: int | None = None,
    ) -> None:
        """Initialize TapDeckApp and instantiate all core subsystems.

        Args:
            diagnostics_mode: When True, opens the diagnostics window on startup.
            test_mode: When True, simulates action executions without side-effects.
            device_index: Optional PortAudio device index for capture stream.
        """
        self.diagnostics_mode = diagnostics_mode
        self.test_mode = test_mode
        self.device_index = device_index
        self._is_shutting_down = False
        self._engine_lock = threading.Lock()

        # Qt High DPI setup
        if QApplication.instance() is None:
            if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
                QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
            if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
                QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

        self.app.setApplicationName("TapDeck")
        self.app.setApplicationDisplayName("TapDeck 2.0")
        self.app.setQuitOnLastWindowClosed(False)

        # 1. Device Manager
        self.device_manager = DeviceManager()
        if self.device_index is None:
            # Query default device if available
            devices = self.device_manager.enumerate_devices()
            for dev in devices:
                if dev.is_default:
                    self.device_index = dev.index
                    break

        sample_rate = 48000
        channels = 2

        # 2. Audio Capture
        self.capture = AudioCapture(
            device_index=self.device_index,
            channels=channels,
            sample_rate=sample_rate,
            block_size=512,
        )

        # 3. DSP Filters & Detectors
        self.filter = BandpassFilter(
            FilterConfig(low_freq=150.0, high_freq=3200.0, order=4, sample_rate=sample_rate)
        )
        self.detector = TransientDetector(
            DetectorConfig(
                energy_threshold=0.01,
                sta_lta_ratio=3.0,
                peak_threshold=0.05,
                sample_rate=sample_rate,
            )
        )
        self.feature_extractor = FeatureExtractor(FeatureConfig(sample_rate=sample_rate))
        self.classifier = ZoneClassifier(ClassifierConfig())
        self.combo_engine = ComboEngine(ComboConfig(coincidence_window_ms=120.0))

        # 4. Action Dispatcher & Config Manager
        self.config_manager = ConfigManager()
        self.action_dispatcher = ActionDispatcher(test_mode=self.test_mode)
        bindings = self.config_manager.load_bindings()
        self.action_dispatcher.load_bindings(bindings)

        # 5. Diagnostics Telemetry
        self.diagnostics = DiagnosticsCollector()
        self.diagnostics.sample_rate = sample_rate
        self.diagnostics.channels = channels
        self.diagnostics.device_index = self.device_index if self.device_index is not None else -1

        # 6. Worker Thread Setup
        self.worker = ProcessingWorker(
            capture=self.capture,
            filter_stage=self.filter,
            detector=self.detector,
            feature_extractor=self.feature_extractor,
            classifier=self.classifier,
            combo_engine=self.combo_engine,
            diagnostics=self.diagnostics,
            engine_lock=self._engine_lock,
            sample_rate=sample_rate,
        )
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.start_processing)

        # Connect Worker Signals
        self.worker.tap_detected.connect(self._on_tap_detected)
        self.worker.trigger_emitted.connect(self._on_trigger)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.diagnostics_updated.connect(self._on_diagnostics_updated)

        # 7. System Tray
        self.tray = TrayManager(self.app)
        self.tray.show_requested.connect(self._on_show_requested)
        self.tray.pause_toggled.connect(self._on_pause_toggled)
        self.tray.settings_requested.connect(self._on_settings_requested)
        self.tray.diagnostics_requested.connect(self._on_diagnostics_requested)
        self.tray.exit_requested.connect(self.shutdown)

        # 8. Diagnostics Window (Lazy or Immediate)
        self.diag_window = DiagnosticsWindow()
        self.worker.diagnostics_updated.connect(self.diag_window.update_diagnostics)
        self.worker.tap_detected.connect(self.diag_window.handle_tap_detected)
        self.worker.trigger_emitted.connect(self.diag_window.handle_trigger)

        # 9. Periodic Combo Coincidence Timeout Timer (every 50ms)
        self._combo_timer = QTimer()
        self._combo_timer.setInterval(50)
        self._combo_timer.timeout.connect(self._check_combo_timeout)

        logger.info(
            "TapDeckApp initialized (diag_mode=%s, test_mode=%s, device=%s)",
            self.diagnostics_mode,
            self.test_mode,
            self.device_index,
        )

    @Slot()
    def _check_combo_timeout(self) -> None:
        """Periodic combo timeout checker (runs every 50ms on Qt event loop)."""
        now = time.time()
        with self._engine_lock:
            timed_out_events = self.combo_engine.check_timeout(now)
        for event in timed_out_events:
            self._on_trigger(event.token.value, event.confidence)

    @Slot(str, float)
    def _on_trigger(self, token_name: str, confidence: float) -> None:
        """Dispatches the configured desktop action for a trigger token."""
        logger.info("Trigger received: %s (confidence=%.2f)", token_name, confidence)
        try:
            result = self.action_dispatcher.dispatch(token_name)
            if result.success:
                logger.info(
                    "Action for %s executed successfully (type=%s, time=%.1fms)",
                    token_name,
                    result.action_type,
                    result.execution_time_ms,
                )
                if not self.diagnostics_mode:
                    self.tray.show_notification(
                        title="TapDeck Trigger",
                        message=f"Trigger: {token_name} ({confidence * 100:.0f}%)",
                        duration_ms=1500,
                    )
            else:
                logger.warning("Action failed for %s: %s", token_name, result.error_message)
        except Exception as exc:
            logger.exception("Error executing action for %s: %s", token_name, exc)
            self._on_error(f"Action failed for {token_name}: {exc}")

    @Slot(dict)
    def _on_tap_detected(self, tap_info: dict[str, Any]) -> None:
        """Handle tap detection event."""
        logger.debug(
            "Tap localized: zone=%s conf=%.2f delay=%.2fms hfr=%.2f",
            tap_info.get("zone"),
            tap_info.get("confidence", 0.0),
            tap_info.get("delay_ms", 0.0),
            tap_info.get("hfr", 0.0),
        )

    @Slot(dict)
    def _on_diagnostics_updated(self, diag: dict[str, Any]) -> None:
        """Handle telemetry diagnostic snapshot updates."""
        pass

    @Slot(str)
    def _on_error(self, message: str) -> None:
        """Handle error from audio pipeline or action dispatcher."""
        logger.error("TapDeck application error: %s", message)
        self.tray.set_state(TrayState.ERROR)
        self.tray.show_notification("TapDeck Error", message, duration_ms=4000)

    @Slot(bool)
    def _on_pause_toggled(self, is_paused: bool) -> None:
        """Pause or resume audio capture stream."""
        if is_paused:
            logger.info("Pausing audio capture detection...")
            self.capture.pause()
            self.tray.set_state(TrayState.PAUSED)
        else:
            logger.info("Resuming audio capture detection...")
            self.capture.resume()
            self.tray.set_state(TrayState.ACTIVE)

    @Slot()
    def _on_show_requested(self) -> None:
        """Show main interface window."""
        self.diag_window.show()
        self.diag_window.activateWindow()
        self.diag_window.raise_()

    @Slot()
    def _on_diagnostics_requested(self) -> None:
        """Open diagnostics telemetry window."""
        self._on_show_requested()

    @Slot()
    def _on_settings_requested(self) -> None:
        """Open settings dialog or window."""
        self._on_show_requested()

    def run(self) -> int:
        """Start audio capture, processing thread, and the Qt application event loop."""
        logger.info("Starting TapDeck 2.0 application pipeline...")
        try:
            self.capture.start()
            self.worker_thread.start()
            self._combo_timer.start()

            if self.diagnostics_mode:
                self.diag_window.show()

            logger.info("TapDeck 2.0 running. Entering Qt event loop.")
            return self.app.exec()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Gracefully stop background threads, audio capture, and exit."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        logger.info("Shutting down TapDeck 2.0 subsystems...")

        if hasattr(self, "_combo_timer") and self._combo_timer.isActive():
            self._combo_timer.stop()

        if hasattr(self, "worker"):
            self.worker.stop_processing()

        if hasattr(self, "worker_thread") and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(2000)

        if hasattr(self, "capture"):
            self.capture.stop()

        if hasattr(self, "tray"):
            self.tray.hide()

        if hasattr(self, "diag_window") and self.diag_window is not None:
            self.diag_window.close()

        self.app.quit()
        logger.info("TapDeck 2.0 terminated.")
