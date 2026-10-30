"""Unit tests for TapDeck dual-tap combination engine."""

from tapdeck.combos.combo_engine import ComboConfig, ComboEngine


class TokenCollector:
    """Helper to collect tokens emitted via callback or direct return."""

    def __init__(self, engine: ComboEngine):
        self.engine = engine
        self.tokens: list[str] = []
        if hasattr(engine, "set_callback"):
            engine.set_callback(self._on_token)
        elif hasattr(engine, "callback"):
            engine.callback = self._on_token

    def _on_token(self, token: str) -> None:
        self.tokens.append(str(token))

    def feed(self, zone, timestamp: float) -> list[str]:
        res = self.engine.process_tap(zone, timestamp=timestamp)
        if res:
            if isinstance(res, list):
                self.tokens.extend([str(t) for t in res])
            else:
                self.tokens.append(str(res))
        return self.tokens

    def timeout(self, current_time: float) -> list[str]:
        if hasattr(self.engine, "check_timeout"):
            res = self.engine.check_timeout(current_time=current_time)
            if res:
                if isinstance(res, list):
                    self.tokens.extend([str(t) for t in res])
                else:
                    self.tokens.append(str(res))
        return self.tokens

    def flush(self) -> list[str]:
        if hasattr(self.engine, "flush"):
            res = self.engine.flush()
            if res:
                if isinstance(res, list):
                    self.tokens.extend([str(t) for t in res])
                else:
                    self.tokens.append(str(res))
        return self.tokens


def test_single_tap_after_timeout() -> None:
    """One tap followed by window timeout emits a single tap token."""
    config = ComboConfig(window_ms=120)
    engine = ComboEngine(config)
    collector = TokenCollector(engine)

    collector.feed("LT", timestamp=1.000)
    assert len(collector.tokens) == 0  # Still waiting for combo window

    collector.timeout(current_time=1.150)  # 150ms > 120ms
    assert len(collector.tokens) == 1
    assert "SINGLE_LT" in collector.tokens[0]


def test_dual_tap_within_window() -> None:
    """LT followed by RT within 120ms produces DUAL_LT_RT immediately."""
    config = ComboConfig(window_ms=120)
    engine = ComboEngine(config)
    collector = TokenCollector(engine)

    collector.feed("LT", timestamp=1.000)
    collector.feed("RT", timestamp=1.080)  # 80ms later

    assert any("DUAL_LT_RT" in t for t in collector.tokens)


def test_dual_tap_outside_window() -> None:
    """LT followed by RT after 200ms (> 120ms) produces two single tokens."""
    config = ComboConfig(window_ms=120)
    engine = ComboEngine(config)
    collector = TokenCollector(engine)

    collector.feed("LT", timestamp=1.000)
    # Exceed window
    collector.timeout(current_time=1.150)
    collector.feed("RT", timestamp=1.200)
    collector.timeout(current_time=1.350)

    assert any("SINGLE_LT" in t for t in collector.tokens)
    assert any("SINGLE_RT" in t for t in collector.tokens)
    assert not any("DUAL" in t for t in collector.tokens)


def test_all_combo_pairs() -> None:
    """Verify all 4 valid dual combinations emit correct combo tokens."""
    valid_pairs = [
        ("LT", "RT", "DUAL_LT_RT"),
        ("LB", "RB", "DUAL_LB_RB"),
        ("LT", "RB", "DUAL_LT_RB"),
        ("LB", "RT", "DUAL_LB_RT"),
    ]

    for z1, z2, expected in valid_pairs:
        engine = ComboEngine(ComboConfig(window_ms=150))
        collector = TokenCollector(engine)
        collector.feed(z1, timestamp=1.000)
        collector.feed(z2, timestamp=1.050)
        assert any(expected in t for t in collector.tokens), f"Failed for pair ({z1}, {z2})"


def test_reverse_order() -> None:
    """RT then LT should still produce DUAL_LT_RT (order independent)."""
    engine = ComboEngine(ComboConfig(window_ms=150))
    collector = TokenCollector(engine)

    collector.feed("RT", timestamp=1.000)
    collector.feed("LT", timestamp=1.050)

    assert any("DUAL_LT_RT" in t for t in collector.tokens)


def test_invalid_combo() -> None:
    """LT then LB is not a valid combo (same side), should resolve to two singles."""
    engine = ComboEngine(ComboConfig(window_ms=150))
    collector = TokenCollector(engine)

    collector.feed("LT", timestamp=1.000)
    collector.feed("LB", timestamp=1.050)
    collector.timeout(current_time=1.250)

    assert not any("DUAL" in t for t in collector.tokens)
    assert any("SINGLE_LT" in t for t in collector.tokens)
    assert any("SINGLE_LB" in t for t in collector.tokens)


def test_same_zone_twice() -> None:
    """Tapping the same zone twice (LT then LT) is handled properly without invalid combo."""
    engine = ComboEngine(ComboConfig(window_ms=150))
    collector = TokenCollector(engine)

    collector.feed("LT", timestamp=1.000)
    collector.feed("LT", timestamp=1.060)
    collector.timeout(current_time=1.250)

    # Should not produce DUAL, but either two single LTs or one replaced LT
    assert not any("DUAL" in t for t in collector.tokens)
    assert any("SINGLE_LT" in t for t in collector.tokens)


def test_flush() -> None:
    """Pending tap flushed immediately emits pending single tap."""
    engine = ComboEngine(ComboConfig(window_ms=200))
    collector = TokenCollector(engine)

    collector.feed("RB", timestamp=1.000)
    collector.flush()

    assert any("SINGLE_RB" in t for t in collector.tokens)


def test_unknown_zone_ignored() -> None:
    """UNKNOWN zones produce no events and do not disrupt state."""
    engine = ComboEngine(ComboConfig(window_ms=150))
    collector = TokenCollector(engine)

    collector.feed("UNKNOWN", timestamp=1.000)
    collector.timeout(current_time=1.200)

    assert len(collector.tokens) == 0
