"""Dual-tap combination recognition engine for TapDeck.

Aggregates single-zone taps into composite gestures (chords) within a configurable
coincidence window, or flushes them as single-tap trigger events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tapdeck.audio.zone_classifier import Zone

logger = logging.getLogger(__name__)


class TriggerToken(StrEnum):
    """Recognized discrete action trigger tokens."""

    SINGLE_LT = "SINGLE_LT"
    SINGLE_LB = "SINGLE_LB"
    SINGLE_RT = "SINGLE_RT"
    SINGLE_RB = "SINGLE_RB"
    DUAL_LT_RT = "DUAL_LT_RT"
    DUAL_LB_RB = "DUAL_LB_RB"
    DUAL_LT_RB = "DUAL_LT_RB"
    DUAL_LB_RT = "DUAL_LB_RT"

    def __str__(self) -> str:
        return self.value


@dataclass
class TriggerEvent:
    """Action event emitted when a valid single tap or dual combo is recognized."""

    token: TriggerToken
    timestamp: float
    confidence: float
    zones: list[Zone]
    reason: str

    def __str__(self) -> str:
        return self.token.value


@dataclass
class ComboConfig:
    """Configuration options for coincidence timing and refractory periods."""

    coincidence_window_ms: float = 120.0
    refractory_ms: float = 150.0
    window_ms: float | None = None

    def __post_init__(self) -> None:
        if self.window_ms is not None:
            self.coincidence_window_ms = float(self.window_ms)


@dataclass
class _PendingTap:
    """Internal representation of a tap awaiting a potential chord partner."""

    zone: Zone
    timestamp: float
    confidence: float
    features: dict[str, Any] = field(default_factory=dict)


class _EngineState(StrEnum):
    """Internal state of the ComboEngine."""

    IDLE = "IDLE"
    WAITING_FOR_PARTNER = "WAITING_FOR_PARTNER"


class ComboEngine:
    """State machine recognizing single and dual-tap chord events.

    Listens for transient zone events, buffers candidates, and detects
    coincident pairs within the coincidence window or falls back to single-tap events.
    """

    def __init__(self, config: ComboConfig | None = None) -> None:
        """Initialize ComboEngine.

        Args:
            config: Optional ComboConfig. Defaults to standard 120ms coincidence window.
        """
        self.config = config if config is not None else ComboConfig()
        self._state: _EngineState = _EngineState.IDLE
        self._pending: _PendingTap | None = None
        self._last_event_time: float = -1.0

        # Mapping of valid 2-zone chord pairs to TriggerTokens
        self._combo_map: dict[frozenset[Zone], TriggerToken] = {
            frozenset({Zone.LT, Zone.RT}): TriggerToken.DUAL_LT_RT,
            frozenset({Zone.LB, Zone.RB}): TriggerToken.DUAL_LB_RB,
            frozenset({Zone.LT, Zone.RB}): TriggerToken.DUAL_LT_RB,
            frozenset({Zone.LB, Zone.RT}): TriggerToken.DUAL_LB_RT,
        }

        # Mapping of single zones to TriggerTokens
        self._single_map: dict[Zone, TriggerToken] = {
            Zone.LT: TriggerToken.SINGLE_LT,
            Zone.LB: TriggerToken.SINGLE_LB,
            Zone.RT: TriggerToken.SINGLE_RT,
            Zone.RB: TriggerToken.SINGLE_RB,
        }

    @property
    def state(self) -> _EngineState:
        """Current internal engine state."""
        return self._state

    def _delta_ms(self, t_current: float, t_previous: float) -> float:
        """Calculate elapsed milliseconds between two timestamps (seconds or ms)."""
        dt = t_current - t_previous
        if dt < 0:
            return 0.0
        # If timestamp is in seconds (e.g., monotonic clock), convert to ms
        if dt < 10.0:
            return dt * 1000.0
        return dt

    def process_tap(
        self,
        zone: Zone | str,
        timestamp: float,
        confidence: float = 1.0,
        features: dict[str, Any] | None = None,
    ) -> list[TriggerEvent]:
        """Process a newly classified tap transient.

        Args:
            zone: Classified spatial Zone or zone string name.
            timestamp: Event timestamp (seconds or milliseconds).
            confidence: Classification confidence (0.0 to 1.0).
            features: Optional dictionary of extracted DSP features.

        Returns:
            List of TriggerEvent objects (0, 1, or 2 events emitted).
        """
        if isinstance(zone, str):
            clean_str = zone.replace("Zone.", "").strip()
            lookup = {
                "LT": Zone.LT,
                "LB": Zone.LB,
                "RT": Zone.RT,
                "RB": Zone.RB,
                "left_top": Zone.LT,
                "left_bottom": Zone.LB,
                "right_top": Zone.RT,
                "right_bottom": Zone.RB,
                "UNKNOWN": Zone.UNKNOWN,
                "unknown": Zone.UNKNOWN,
            }
            zone = lookup.get(clean_str, Zone.UNKNOWN)

        if zone == Zone.UNKNOWN or zone not in self._single_map:
            logger.debug("Ignoring tap in zone '%s' with confidence %.2f", zone, confidence)
            return []

        feat = dict(features) if features is not None else {}
        events: list[TriggerEvent] = []

        if self._state == _EngineState.IDLE:
            # First tap of potential combo: buffer and wait
            self._pending = _PendingTap(
                zone=zone,
                timestamp=timestamp,
                confidence=confidence,
                features=feat,
            )
            self._state = _EngineState.WAITING_FOR_PARTNER
            logger.debug(
                "ComboEngine state: IDLE -> WAITING_FOR_PARTNER with zone %s (t=%.4f)",
                zone.value,
                timestamp,
            )
            return []

        # Current state is WAITING_FOR_PARTNER
        assert self._pending is not None
        dt_ms = self._delta_ms(timestamp, self._pending.timestamp)

        if dt_ms <= self.config.coincidence_window_ms:
            # Inside coincidence window — evaluate if pair forms a valid combo
            pair = frozenset({self._pending.zone, zone})
            if pair in self._combo_map:
                token = self._combo_map[pair]
                combo_conf = (self._pending.confidence + confidence) / 2.0
                event = TriggerEvent(
                    token=token,
                    timestamp=timestamp,
                    confidence=combo_conf,
                    zones=[self._pending.zone, zone],
                    reason=f"dual_combo_{token.value} (dt={dt_ms:.1f}ms)",
                )
                logger.info(
                    "Recognized combo %s with zones [%s, %s] (dt=%.1f ms, conf=%.2f)",
                    token.value,
                    self._pending.zone.value,
                    zone.value,
                    dt_ms,
                    combo_conf,
                )
                self._pending = None
                self._state = _EngineState.IDLE
                self._last_event_time = timestamp
                return [event]
            else:
                # Within window, but not a valid combo (e.g. same zone tapped twice rapidly)
                logger.debug(
                    "Pair {%s, %s} is not a valid combo (dt=%.1f ms); flushing pending as single",
                    self._pending.zone.value,
                    zone.value,
                    dt_ms,
                )
                # Emit single for pending tap
                pending_token = self._single_map[self._pending.zone]
                events.append(
                    TriggerEvent(
                        token=pending_token,
                        timestamp=self._pending.timestamp,
                        confidence=self._pending.confidence,
                        zones=[self._pending.zone],
                        reason="single_tap_unmatched_pair",
                    )
                )
                # Set new tap as pending
                self._pending = _PendingTap(
                    zone=zone,
                    timestamp=timestamp,
                    confidence=confidence,
                    features=feat,
                )
                self._state = _EngineState.WAITING_FOR_PARTNER
                return events
        else:
            # Outside coincidence window: pending tap expired, emit as single
            logger.debug(
                "Coincidence window expired (dt=%.1f ms > %.1f ms); emitting single for %s",
                dt_ms,
                self.config.coincidence_window_ms,
                self._pending.zone.value,
            )
            pending_token = self._single_map[self._pending.zone]
            events.append(
                TriggerEvent(
                    token=pending_token,
                    timestamp=self._pending.timestamp,
                    confidence=self._pending.confidence,
                    zones=[self._pending.zone],
                    reason=f"single_tap_timeout (dt={dt_ms:.1f}ms)",
                )
            )
            # Buffer current tap as new pending
            self._pending = _PendingTap(
                zone=zone,
                timestamp=timestamp,
                confidence=confidence,
                features=feat,
            )
            self._state = _EngineState.WAITING_FOR_PARTNER
            return events

    def flush(self) -> list[TriggerEvent]:
        """Flush any pending tap as a single-tap event and reset state to IDLE.

        Returns:
            List containing the flushed single TriggerEvent, or empty list.
        """
        if self._state == _EngineState.WAITING_FOR_PARTNER and self._pending is not None:
            zone = self._pending.zone
            token = self._single_map.get(zone)
            if token is not None:
                event = TriggerEvent(
                    token=token,
                    timestamp=self._pending.timestamp,
                    confidence=self._pending.confidence,
                    zones=[zone],
                    reason="single_tap_flushed",
                )
                logger.info(
                    "Flushed pending single tap %s (conf=%.2f)",
                    token.value,
                    self._pending.confidence,
                )
                self._pending = None
                self._state = _EngineState.IDLE
                return [event]

        self._pending = None
        self._state = _EngineState.IDLE
        return []

    def check_timeout(self, current_time: float) -> list[TriggerEvent]:
        """Check whether the buffered pending tap has exceeded the coincidence window.

        Args:
            current_time: Current timestamp (seconds or milliseconds).

        Returns:
            List containing flushed event if timed out, else empty list.
        """
        if self._state == _EngineState.WAITING_FOR_PARTNER and self._pending is not None:
            dt_ms = self._delta_ms(current_time, self._pending.timestamp)
            if dt_ms > self.config.coincidence_window_ms:
                logger.debug(
                    "Timeout detected: elapsed %.1f ms > window %.1f ms",
                    dt_ms,
                    self.config.coincidence_window_ms,
                )
                return self.flush()

        return []

    def reset(self) -> None:
        """Reset internal engine state and discard pending taps."""
        self._state = _EngineState.IDLE
        self._pending = None
        self._last_event_time = -1.0
        logger.debug("ComboEngine reset to IDLE")
