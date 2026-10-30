"""Diagnostics and telemetry window for TapDeck 2.0."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ZoneBox(QFrame):
    """Visual widget representing a single acoustic zone quadrant."""

    def __init__(self, zone_name: str, label_text: str) -> None:
        super().__init__()
        self.zone_name = zone_name
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setMinimumSize(120, 80)

        layout = QVBoxLayout(self)
        self.title_label = QLabel(label_text)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        self.conf_label = QLabel("Idle")
        self.conf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.conf_label.setFont(QFont("Segoe UI", 9))

        layout.addWidget(self.title_label)
        layout.addWidget(self.conf_label)

        self.reset_visual()

    def highlight(self, confidence: float) -> None:
        """Highlight quadrant upon detected tap."""
        self.setStyleSheet(
            "QFrame { background-color: #065F46; border: 2px solid #10B981; border-radius: 8px; }"
            "QLabel { color: #ECFDF5; }"
        )
        self.conf_label.setText(f"Tap: {confidence:.2f}")

    def reset_visual(self) -> None:
        """Reset to normal non-active appearance."""
        self.setStyleSheet(
            "QFrame { background-color: #1F2937; border: 2px solid #374151; border-radius: 8px; }"
            "QLabel { color: #9CA3AF; }"
        )
        self.conf_label.setText("Idle")


class DiagnosticsWindow(QMainWindow):
    """Main diagnostics window displaying acoustic features, metrics, and zone activity."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TapDeck 2.0 — Diagnostics & Telemetry")
        self.resize(850, 620)
        self.setStyleSheet("background-color: #111827; color: #F3F4F6;")

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # 1. Header / Stream Stats
        stats_group = QGroupBox("Stream & Pipeline Health")
        stats_group.setStyleSheet("QGroupBox { font-weight: bold; color: #60A5FA; }")
        stats_layout = QHBoxLayout(stats_group)

        self.lbl_device = QLabel("Device: Initializing...")
        self.lbl_latency = QLabel("Latency: 0.0 ms")
        self.lbl_cpu = QLabel("CPU: 0.0%")
        self.lbl_memory = QLabel("RAM: 0.0 MB")
        self.lbl_dropped = QLabel("Dropped: 0")

        for lbl in (
            self.lbl_device,
            self.lbl_latency,
            self.lbl_cpu,
            self.lbl_memory,
            self.lbl_dropped,
        ):
            lbl.setFont(QFont("Segoe UI", 9))
            stats_layout.addWidget(lbl)

        root_layout.addWidget(stats_group)

        # 2. Middle section: Zone Visualization & Actions
        mid_layout = QHBoxLayout()

        # Quadrant Box
        quad_group = QGroupBox("Spatial Acoustic Localization")
        quad_group.setStyleSheet("QGroupBox { font-weight: bold; color: #34D399; }")
        quad_grid = QGridLayout(quad_group)

        self.box_lt = ZoneBox("left_top", "Top-Left (LT)")
        self.box_rt = ZoneBox("right_top", "Top-Right (RT)")
        self.box_lb = ZoneBox("left_bottom", "Bottom-Left (LB)")
        self.box_rb = ZoneBox("right_bottom", "Bottom-Right (RB)")

        quad_grid.addWidget(self.box_lt, 0, 0)
        quad_grid.addWidget(self.box_rt, 0, 1)
        quad_grid.addWidget(self.box_lb, 1, 0)
        quad_grid.addWidget(self.box_rb, 1, 1)
        mid_layout.addWidget(quad_group, stretch=1)

        # Controls box
        ctrl_group = QGroupBox("Engine Controls")
        ctrl_group.setStyleSheet("QGroupBox { font-weight: bold; color: #FBBF24; }")
        ctrl_layout = QVBoxLayout(ctrl_group)

        self.btn_clear = QPushButton("Clear Event Log")
        self.btn_clear.setStyleSheet(
            "background-color: #374151; color: white; padding: 6px; border-radius: 4px;"
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
        log_group = QGroupBox("Detected Tap Events")
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

    @Slot(dict)
    def update_diagnostics(self, diag: dict[str, Any]) -> None:
        """Update telemetry metrics display."""
        dev = diag.get("device_name", "Default")
        lat = diag.get("processing_latency_ms", 0.0)
        cpu = diag.get("cpu_percent", 0.0)
        mem = diag.get("memory_mb", 0.0)
        drop = diag.get("frames_dropped", 0)

        self.lbl_device.setText(f"Device: {dev}")
        self.lbl_latency.setText(f"Latency: {lat:.1f} ms")
        self.lbl_cpu.setText(f"CPU: {cpu:.1f}%")
        self.lbl_memory.setText(f"RAM: {mem:.1f} MB")
        self.lbl_dropped.setText(f"Dropped: {drop}")

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
        if "top" in zone and "left" in zone:
            self.box_lt.highlight(conf)
        elif "top" in zone and "right" in zone:
            self.box_rt.highlight(conf)
        elif "bottom" in zone and "left" in zone:
            self.box_lb.highlight(conf)
        elif "bottom" in zone and "right" in zone:
            self.box_rb.highlight(conf)

        # Insert row in table (keep last 100 rows)
        row = 0
        self.table.insertRow(row)
        import datetime

        timestr = datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]

        self.table.setItem(row, 0, QTableWidgetItem(timestr))
        self.table.setItem(row, 1, QTableWidgetItem(zone.upper()))
        self.table.setItem(row, 2, QTableWidgetItem(f"{conf:.2f}"))
        self.table.setItem(row, 3, QTableWidgetItem(f"{delay:.2f}"))
        self.table.setItem(row, 4, QTableWidgetItem(f"{hfr:.2f}"))
        self.table.setItem(row, 5, QTableWidgetItem(f"{energy:.4f}"))

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
