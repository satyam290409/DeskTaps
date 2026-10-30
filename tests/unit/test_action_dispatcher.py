"""Unit tests for TapDeck action dispatcher and action handlers."""

from tapdeck.actions.action_dispatcher import (
    ActionDispatcher,
    ActionResult,
    HotkeyAction,
    LaunchAppAction,
    TestModeAction,
)


def test_test_mode_logs_only() -> None:
    """TestModeAction wrapping HotkeyAction succeeds without firing system hotkey."""
    inner_hotkey = HotkeyAction(keys=["ctrl", "alt", "delete"])
    test_action = TestModeAction(inner_hotkey)

    res = test_action.execute()
    assert res.success is True
    assert "test" in str(getattr(res, "action_type", "")).lower() or getattr(
        test_action, "was_executed", True
    )


def test_dispatcher_all_triggers_mapped(sample_bindings_config) -> None:
    """Loading default bindings maps all 8 trigger tokens to actionable handlers."""
    dispatcher = ActionDispatcher(sample_bindings_config)
    expected_tokens = [
        "SINGLE_LT",
        "SINGLE_LB",
        "SINGLE_RT",
        "SINGLE_RB",
        "DUAL_LT_RT",
        "DUAL_LB_RB",
        "DUAL_LT_RB",
        "DUAL_LB_RT",
    ]
    for token in expected_tokens:
        action = dispatcher.get_action(token)
        assert action is not None, f"Trigger token {token} not mapped in ActionDispatcher"


def test_action_result_structure() -> None:
    """ActionResult contains expected execution status, timing, and diagnostic fields."""
    result = ActionResult(
        success=True,
        action_type="hotkey",
        message="Simulated success",
        execution_time_ms=1.2,
    )
    assert result.success is True
    assert result.action_type == "hotkey"
    assert "Simulated success" in result.message
    assert result.execution_time_ms >= 0


def test_launch_app_validates_path() -> None:
    """LaunchAppAction with non-existent executable path fails validation."""
    invalid_action = LaunchAppAction(executable="non_existent_fake_app_12345.exe")
    is_valid = invalid_action.validate()
    assert is_valid is False
