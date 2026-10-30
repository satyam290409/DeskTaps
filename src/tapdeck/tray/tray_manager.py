"""System tray icon and context menu management using PySide6."""

from __future__ import annotations

import logging
from enum import StrEnum

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

logger = logging.getLogger(__name__)


class TrayState(StrEnum):
    """Visual states for the system tray icon."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    DISABLED = "DISABLED"

    def __str__(self) -> str:
        return self.value


# Hex colors for tray icon states
STATE_COLORS: dict[TrayState, str] = {
    TrayState.ACTIVE: "#22C55E",  # Emerald green
    TrayState.PAUSED: "#EAB308",  # Amber yellow
    TrayState.ERROR: "#EF4444",  # Red
    TrayState.DISABLED: "#6B7280",  # Gray
}

STATE_TOOLTIPS: dict[TrayState, str] = {
    TrayState.ACTIVE: "TapDeck 2.0 — Detection Active",
    TrayState.PAUSED: "TapDeck 2.0 — Detection Paused",
    TrayState.ERROR: "TapDeck 2.0 — Audio / Device Error",
    TrayState.DISABLED: "TapDeck 2.0 — Disabled",
}


class TrayManager(QObject):
    """Manages the Windows taskbar notification area (tray) icon and menu.

    Communicates state transitions and user intentions exclusively via Qt signals.
    """

    show_requested = Signal()
    pause_toggled = Signal(bool)  # Emits True when entering paused state, False when resuming
    settings_requested = Signal()
    diagnostics_requested = Signal()
    exit_requested = Signal()

    def __init__(self, app: QApplication) -> None:
        """Initialize the TrayManager.

        Args:
            app: QApplication instance managing the desktop lifecycle.
        """
        super().__init__()
        self._app = app
        self._state: TrayState = TrayState.ACTIVE
        self._is_paused: bool = False

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.activated.connect(self._on_tray_activated)

        # Context Menu
        self._menu = QMenu()

        self._show_action = QAction("Show TapDeck", self._menu)
        self._show_action.triggered.connect(self.show_requested.emit)
        self._menu.addAction(self._show_action)

        self._pause_action = QAction("Pause Detection", self._menu)
        self._pause_action.triggered.connect(self._on_pause_action_triggered)
        self._menu.addAction(self._pause_action)

        self._menu.addSeparator()

        self._settings_action = QAction("Settings", self._menu)
        self._settings_action.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(self._settings_action)

        self._diagnostics_action = QAction("Diagnostics", self._menu)
        self._diagnostics_action.triggered.connect(self.diagnostics_requested.emit)
        self._menu.addAction(self._diagnostics_action)

        self._menu.addSeparator()

        self._exit_action = QAction("Exit", self._menu)
        self._exit_action.triggered.connect(self.exit_requested.emit)
        self._menu.addAction(self._exit_action)

        self._tray_icon.setContextMenu(self._menu)

        # Apply initial active state
        self.set_state(TrayState.ACTIVE)
        self._tray_icon.show()
        logger.info("TrayManager initialized and tray icon displayed.")

    @property
    def state(self) -> TrayState:
        """Return the current tray state."""
        return self._state

    def _create_icon(self, color_hex: str) -> QIcon:
        """Create a crisp colored circle icon using QPainter.

        Args:
            color_hex: Hex color code (e.g., '#22C55E').

        Returns:
            A QIcon containing the rendered circle pixmap.
        """
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Outer border / subtle ring
        pen = QPen(QColor("#111827"), 1.5)
        painter.setPen(pen)

        # Fill circle
        brush = QBrush(QColor(color_hex))
        painter.setBrush(brush)

        margin = 4
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
        painter.end()

        return QIcon(pixmap)

    @Slot(TrayState)
    def set_state(self, state: TrayState) -> None:
        """Update the icon, tooltip, and menu state.

        Args:
            state: TrayState enum value.
        """
        self._state = state
        self._is_paused = state == TrayState.PAUSED

        # Update action label
        if self._is_paused:
            self._pause_action.setText("Resume Detection")
        else:
            self._pause_action.setText("Pause Detection")

        # Update icon and tooltip
        color_hex = STATE_COLORS.get(state, "#22C55E")
        icon = self._create_icon(color_hex)
        self._tray_icon.setIcon(icon)

        tooltip = STATE_TOOLTIPS.get(state, "TapDeck 2.0")
        self._tray_icon.setToolTip(tooltip)
        logger.debug("Tray state updated to %s", state.value)

    @Slot()
    def _on_pause_action_triggered(self) -> None:
        """Toggle paused state and notify observers."""
        if self._state == TrayState.PAUSED:
            self.set_state(TrayState.ACTIVE)
            self.pause_toggled.emit(False)
        else:
            self.set_state(TrayState.PAUSED)
            self.pause_toggled.emit(True)

    @Slot(QSystemTrayIcon.ActivationReason)
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle primary clicks on the tray icon."""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_requested.emit()

    def show_notification(self, title: str, message: str, duration_ms: int = 3000) -> None:
        """Display a native desktop balloon notification from the tray icon.

        Args:
            title: Notification title header.
            message: Body message string.
            duration_ms: Duration in milliseconds before fading out.
        """
        if self._tray_icon.isVisible():
            self._tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                duration_ms,
            )

    def hide(self) -> None:
        """Hide the tray icon upon application shutdown."""
        self._tray_icon.hide()
