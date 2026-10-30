"""Action dispatch system for executing configured desktop actions."""

from tapdeck.actions.action_dispatcher import (
    ActionDispatcher,
    ActionResult,
    BaseAction,
    HotkeyAction,
    LaunchAppAction,
    MediaKeyAction,
    ShellCommandAction,
    TestModeAction,
)

__all__ = [
    "ActionDispatcher",
    "ActionResult",
    "BaseAction",
    "HotkeyAction",
    "LaunchAppAction",
    "MediaKeyAction",
    "ShellCommandAction",
    "TestModeAction",
]
