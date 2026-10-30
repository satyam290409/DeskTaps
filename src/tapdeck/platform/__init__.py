"""Windows platform integration utilities."""

from tapdeck.platform.windows_keys import (
    INPUT,
    INPUT_KEYBOARD,
    KEYBDINPUT,
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    VK_NAME_MAP,
    press_keys,
    resolve_key_names,
    send_key_event,
    tap_key,
)

__all__ = [
    "INPUT",
    "INPUT_KEYBOARD",
    "KEYBDINPUT",
    "KEYEVENTF_EXTENDEDKEY",
    "KEYEVENTF_KEYUP",
    "VK_NAME_MAP",
    "press_keys",
    "resolve_key_names",
    "send_key_event",
    "tap_key",
]
