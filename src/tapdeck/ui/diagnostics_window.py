"""Diagnostics and telemetry window for TapDeck 2.0 with interactive controls."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ZoneBox(QFrame):
    """Visual widget representing a single acoustic zone quadrant."""

    clicked = Signal(str)

    def __init__(self, zone_name: str, label_text: str, default_action: str = "") -> None:
        super().__init__()
        self.zone_name = zone_name
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setMinimumSize(140, 95)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        self.title_label = QLabel(label_text)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        self.action_label = QLabel(default_action)
        self.action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.action_label.setFont(QFont("Segoe UI", 9))
        self.action_label.setStyleSheet("color: #60A5FA;")

        self.conf_label = QLabel("Idle (Click to Test)")
        self.conf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.conf_label.setFont(QFont("Segoe UI", 8))

        layout.addWidget(self.title_label)
        layout.addWidget(self.action_label)
        layout.addWidget(self.conf_label)

        self.reset_visual()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        """Handle click to test the zone action."""
        self.clicked.emit(self.zone_name)
        super().mousePressEvent(event)

    def highlight(self, confidence: float) -> None:
        """Highlight quadrant upon detected tap."""
        self.setStyleSheet(
            "QFrame { background-color: #065F46; border: 2px solid #10B981; border-radius: 8px; }"
            "QLabel { color: #ECFDF5; }"
        )
        self.conf_label.setText(f"Active: {confidence:.2f}")

    def reset_visual(self) -> None:
        """Reset to normal non-active appearance."""
        self.setStyleSheet(
            "QFrame { background-color: #1F2937; border: 2px solid #374151; border-radius: 8px; }"
            "QFrame:hover { border: 2px solid #3B82F6; background-color: #263345; }"
            "QLabel { color: #9CA3AF; }"
        )
        self.conf_label.setText("Idle (Click to Test)")


class DiagnosticsWindow(QMainWindow):
    """Main diagnostics window displaying acoustic features, metrics, and zone activity."""

    sensitivity_changed = Signal(float)
    device_changed = Signal(int)
    test_zone_clicked = Signal(str)
    pause_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TapDeck 2.0 — Diagnostics & Telemetry")
        self.resize(920, 680)
        self.setStyleSheet("background-color: #111827; color: #F3F4F6;")
        self._is_paused: bool = False

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # 1. Header / Stream Stats & Live Audio Meter
        stats_group = QGroupBox("Microphone & Audio Input Monitor")
        stats_group.setStyleSheet("QGroupBox { font-weight: bold; color: #60A5FA; }")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(8)

        # Top row: Device selector dropdown and live stats
        top_row = QHBoxLayout()
        lbl_dev_title = QLabel("Input Device:")
        lbl_dev_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        top_row.addWidget(lbl_dev_title)

        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet(
            "QComboBox { background-color: #1F2937; color: #F3F4F6; "
            "border: 1px solid #4B5563; padding: 4px; border-radius: 4px; min-width: 280px; }"
            "QComboBox QAbstractItemView { background-color: #1F2937; color: #F3F4F6; "
            "selection-background-color: #2563EB; }"
        )
        self.device_combo.currentIndexChanged.connect(self._on_device_combo_changed)
        top_row.addWidget(self.device_combo, stretch=2)

        self.lbl_latency = QLabel("Latency: 0.0 ms")
        self.lbl_cpu = QLabel("CPU: 0.0%")
        self.lbl_memory = QLabel("RAM: 0.0 MB")
        self.lbl_dropped = QLabel("Dropped: 0")

        for lbl in (self.lbl_latency, self.lbl_cpu, self.lbl_memory, self.lbl_dropped):
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #D1D5DB;")
            top_row.addWidget(lbl)

        stats_layout.addLayout(top_row)

        # Bottom row: Live Microphone VU Audio Level Meter
        meter_row = QHBoxLayout()
        lbl_vu_title = QLabel("Live Audio Input:")
        lbl_vu_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        meter_row.addWidget(lbl_vu_title)

        self.vu_bar = QProgressBar()
        self.vu_bar.setRange(0, 100)
        self.vu_bar.setValue(0)
        self.vu_bar.setTextVisible(True)
        self.vu_bar.setFormat("Live Volume: %p%")
        self.vu_bar.setStyleSheet(
            "QProgressBar { background-color: #1F2937; border: 1px solid #374151; "
            "border-radius: 5px; text-align: center; color: #FFFFFF; "
            "font-weight: bold; height: 20px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #10B981, stop:0.6 #F59E0B, stop:1 #EF4444); border-radius: 4px; }"
        )
        meter_row.addWidget(self.vu_bar, stretch=3)
        stats_layout.addLayout(meter_row)

        root_layout.addWidget(stats_group)

        # 2. Middle section: Zone Visualization & Actions
        mid_layout = QHBoxLayout()

        # Quadrant Box
        quad_group = QGroupBox("Spatial Acoustic Localization (Click Any to Test)")
        quad_group.setStyleSheet("QGroupBox { font-weight: bold; color: #34D399; }")
        quad_grid = QGridLayout(quad_group)
        quad_grid.setSpacing(10)

        self.box_lt = ZoneBox("LT", "Top-Left (LT)", "Single: Play / Pause")
        self.box_rt = ZoneBox("RT", "Top-Right (RT)", "Single: Next Track")
        self.box_lb = ZoneBox("LB", "Bottom-Left (LB)", "Single: Prev Track")
        self.box_rb = ZoneBox("RB", "Bottom-Right (RB)", "Single: Mute Audio")

        for b in (self.box_lt, self.box_rt, self.box_lb, self.box_rb):
            b.clicked.connect(self._on_zone_clicked)

        quad_grid.addWidget(self.box_lt, 0, 0)
        quad_grid.addWidget(self.box_rt, 0, 1)
        quad_grid.addWidget(self.box_lb, 1, 0)
        quad_grid.addWidget(self.box_rb, 1, 1)
        mid_layout.addWidget(quad_group, stretch=2)

        # Controls box
        ctrl_group = QGroupBox("Interactive Controls")
        ctrl_group.setStyleSheet("QGroupBox { font-weight: bold; color: #FBBF24; }")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.setSpacing(8)

        # Sensitivity Slider
        self.lbl_sens = QLabel("Sensitivity: High (Threshold: 0.0003)")
        self.lbl_sens.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_sens.setStyleSheet("color: #FCD34D;")
        ctrl_layout.addWidget(self.lbl_sens)

        self.slider_sens = QSlider(Qt.Orientation.Horizontal)
        self.slider_sens.setRange(1, 100)
        self.slider_sens.setValue(80)  # Default High sensitivity
        self.slider_sens.setStyleSheet(
            "QSlider::groove:horizontal { height: 6px; background: #374151; border-radius: 3px; }"
            "QSlider::sub-page:horizontal { background: #3B82F6; border-radius: 3px; }"
            "QSlider::handle:horizontal { background: #60A5FA; width: 16px; margin: -5px 0; "
            "border-radius: 8px; }"
        )
        self.slider_sens.valueChanged.connect(self._on_sensitivity_slider_changed)
        ctrl_layout.addWidget(self.slider_sens)

        # Pause / Resume Button
        self.btn_pause = QPushButton("⏸ Pause Detection")
        self.btn_pause.setStyleSheet(
            "background-color: #374151; color: white; padding: 7px; "
            "border-radius: 4px; font-weight: bold;"
        )
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        ctrl_layout.addWidget(self.btn_pause)

        # Clear Event Log Button
        self.btn_clear = QPushButton("Clear Event Log")
        self.btn_clear.setStyleSheet(
            "background-color: #1F2937; color: #9CA3AF; padding: 6px; "
            "border: 1px solid #374151; border-radius: 4px;"
        )
        self.btn_clear.clicked.connect(self._clear_table)
        ctrl_layout.addWidget(self.btn_clear)

        self.lbl_last_trigger = QLabel("Last Trigger: None")
        self.lbl_last_trigger.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_last_trigger.setStyleSheet("color: #A78BFA;")
        ctrl_layout.addWidget(self.lbl_last_trigger)
        ctrl_layout.addStretch()

        mid_layout.addWidget(ctrl_group, stretch=1)
        root_layout.addLayout(mid_layout)

        # 3. Detection Event Table
        log_group = QGroupBox("Detected Tap Events (Real-time)")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; color: #E5E7EB; }")
        log_layout = QVBoxLayout(log_group)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Time", "Zone", "Confidence", "Delay (ms)", "HFR", "Energy"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #1F2937; gridline-color: #374151; "
            "color: #E5E7EB; border: none; }"
            "QHeaderView::section { background-color: #111827; color: #9CA3AF; padding: 4px; }"
        )
        log_layout.addWidget(self.table)
        root_layout.addWidget(log_group, stretch=2)

    def set_devices(self, devices: list[dict[str, Any]], current_index: int | None) -> None:
        """Populate device selector dropdown."""
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        selected_idx = 0
        for i, dev in enumerate(devices):
            dev_idx = dev.get("index", i)
            name = dev.get("name", f"Device {dev_idx}")
            self.device_combo.addItem(f"{dev_idx}: {name}", dev_idx)
            if current_index is not None and dev_idx == current_index:
                selected_idx = i
        if self.device_combo.count() > 0:
            self.device_combo.setCurrentIndex(selected_idx)
        self.device_combo.blockSignals(False)

    @Slot(int)
    def _on_device_combo_changed(self, combo_index: int) -> None:
        """Handle device selection change."""
        device_idx = self.device_combo.itemData(combo_index)
        if device_idx is not None:
            self.device_changed.emit(int(device_idx))

    @Slot(int)
    def _on_sensitivity_slider_changed(self, value: int) -> None:
        """Map slider value (1-100) to energy threshold exponentially."""
        # 100 = 0.00005 (ultra), 80 = 0.0003 (high), 50 = 0.0012 (medium), 1 = 0.008 (low)
        norm = value / 100.0
        # Exponential curve: 0.008 down to 0.00005
        thresh = float(0.008 * (0.00625 ** norm))
        if value >= 85:
            level_str = "Ultra Sensitive"
        elif value >= 65:
            level_str = "High (Recommended)"
        elif value >= 35:
            level_str = "Medium"
        else:
            level_str = "Low"
        self.lbl_sens.setText(f"Sensitivity: {level_str} ({thresh:.5f})")
        self.sensitivity_changed.emit(thresh)

    @Slot()
    def _on_pause_clicked(self) -> None:
        """Toggle pause state."""
        self._is_paused = not self._is_paused
        if self._is_paused:
            self.btn_pause.setText("▶ Resume Detection")
            self.btn_pause.setStyleSheet(
                "background-color: #B45309; color: white; padding: 7px; "
                "border-radius: 4px; font-weight: bold;"
            )
        else:
            self.btn_pause.setText("⏸ Pause Detection")
            self.btn_pause.setStyleSheet(
                "background-color: #374151; color: white; padding: 7px; "
                "border-radius: 4px; font-weight: bold;"
            )
        self.pause_toggled.emit(self._is_paused)

    @Slot(str)
    def _on_zone_clicked(self, zone_name: str) -> None:
        """Handle click on quadrant box."""
        self.test_zone_clicked.emit(zone_name)

    @Slot(dict)
    def update_diagnostics(self, diag: dict[str, Any]) -> None:
        """Update telemetry metrics display."""
        lat = diag.get("processing_latency_ms", 0.0)
        cpu = diag.get("cpu_percent", 0.0)
        mem = diag.get("memory_mb", 0.0)
        drop = diag.get("frames_dropped", 0)

        self.lbl_latency.setText(f"Latency: {lat:.1f} ms")
        self.lbl_cpu.setText(f"CPU: {cpu:.1f}%")
        self.lbl_memory.setText(f"RAM: {mem:.1f} MB")
        self.lbl_dropped.setText(f"Dropped: {drop}")

        # Update Live Audio Input VU Meter
        rms = float(diag.get("input_level_rms", 0.0))
        # Map RMS amplitude to 0-100% scale (0.05 RMS is full-scale for finger taps)
        vu_val = min(100, int(rms * 2500.0))
        self.vu_bar.setValue(vu_val)

    @Slot(dict)
    def handle_tap_detected(self, tap: dict[str, Any]) -> None:
        """Update quadrant indicators and append row to event table."""
        zone = str(tap.get("zone", "")).lower()
        conf = float(tap.get("confidence", 0.0))
        delay = float(tap.get("delay_ms", 0.0))
        hfr = float(tap.get("hfr", 0.0))
        energy = float(tap.get("energy", 0.0))
        timestamp = float(tap.get("timestamp", 0.0))

        # Reset all quadrants
        self.box_lt.reset_visual()
        self.box_rt.reset_visual()
        self.box_lb.reset_visual()
        self.box_rb.reset_visual()

        # Highlight recognized quadrant
        if "top" in zone and "left" in zone or zone == "lt":
            self.box_lt.highlight(conf)
        elif "top" in zone and "right" in zone or zone == "rt":
            self.box_rt.highlight(conf)
        elif "bottom" in zone and "left" in zone or zone == "lb":
            self.box_lb.highlight(conf)
        elif "bottom" in zone and "right" in zone or zone == "rb":
            self.box_rb.highlight(conf)

        # Insert row in table (keep last 100 rows)
        row = 0
        self.table.insertRow(row)
        timestr = datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]

        self.table.setItem(row, 0, QTableWidgetItem(timestr))
        self.table.setItem(row, 1, QTableWidgetItem(zone.upper()))
        self.table.setItem(row, 2, QTableWidgetItem(f"{conf:.2f}"))
        self.table.setItem(row, 3, QTableWidgetItem(f"{delay:.2f}"))
        self.table.setItem(row, 4, QTableWidgetItem(f"{hfr:.2f}"))
        self.table.setItem(row, 5, QTableWidgetItem(f"{energy:.5f}"))

        if self.table.rowCount() > 100:
            self.table.removeRow(self.table.rowCount() - 1)

    @Slot(str, float)
    def handle_trigger(self, token: str, confidence: float) -> None:
        """Update last trigger label."""
        self.lbl_last_trigger.setText(f"Last Trigger: {token} ({confidence:.2f})")

    @Slot()
    def _clear_table(self) -> None:
        """Clear all event log entries."""
        self.table.setRowCount(0)

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        """Minimize to system tray on close instead of destroying process."""
        event.ignore()
        self.hide()
