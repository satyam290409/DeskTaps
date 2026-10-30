"""Action dispatch system for executing desktop automation actions in Windows.

Provides native Windows hotkey synthesis via SendInput, media key controls,
application launches, shell commands, and safe testing mocks.
"""

from __future__ import annotations

import ctypes
import logging
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tapdeck.combos.combo_engine import TriggerToken

logger = logging.getLogger(__name__)

# ============================================================================
# Windows SendInput Structures & Constants
# ============================================================================

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    """Win32 KEYBDINPUT structure for keyboard input synthesis."""

    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    """Win32 MOUSEINPUT structure."""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    """Win32 HARDWAREINPUT structure."""

    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):  # noqa: N801
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    """Win32 INPUT structure for SendInput API."""

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT_UNION),
    ]


def _send_keyboard_events(events: list[tuple[int, int]]) -> bool:
    """Send a sequence of (vk_code, flags) using Windows SendInput.

    Args:
        events: List of tuples (virtual_key_code, flags).

    Returns:
        True if all events were accepted by SendInput, False otherwise.
    """
    if sys.platform != "win32":
        logger.warning("SendInput is only supported on Windows")
        return False

    n_inputs = len(events)
    if n_inputs == 0:
        return True

    input_arr = (INPUT * n_inputs)()
    for i, (vk, flags) in enumerate(events):
        input_arr[i].type = INPUT_KEYBOARD
        input_arr[i].ki.wVk = vk
        input_arr[i].ki.wScan = 0
        input_arr[i].ki.dwFlags = flags
        input_arr[i].ki.time = 0
        input_arr[i].ki.dwExtraInfo = 0

    cb_size = ctypes.sizeof(INPUT)
    sent = ctypes.windll.user32.SendInput(n_inputs, input_arr, cb_size)
    return bool(sent == n_inputs)


# Virtual-Key mapping table
VK_MAP: dict[str, int] = {
    # Modifiers
    "win": 0x5B,  # VK_LWIN
    "lwin": 0x5B,
    "rwin": 0x5C,  # VK_RWIN
    "ctrl": 0x11,  # VK_CONTROL
    "lctrl": 0xA2,  # VK_LCONTROL
    "rctrl": 0xA3,  # VK_RCONTROL
    "alt": 0x12,  # VK_MENU
    "lalt": 0xA4,  # VK_LMENU
    "ralt": 0xA5,  # VK_RMENU
    "shift": 0x10,  # VK_SHIFT
    "lshift": 0xA0,  # VK_LSHIFT
    "rshift": 0xA1,  # VK_RSHIFT
    # Navigation & control
    "tab": 0x09,  # VK_TAB
    "enter": 0x0D,  # VK_RETURN
    "return": 0x0D,
    "esc": 0x1B,  # VK_ESCAPE
    "escape": 0x1B,
    "space": 0x20,  # VK_SPACE
    "backspace": 0x08,  # VK_BACK
    "delete": 0x2E,  # VK_DELETE
    "insert": 0x2D,  # VK_INSERT
    "home": 0x24,  # VK_HOME
    "end": 0x23,  # VK_END
    "pageup": 0x21,  # VK_PRIOR
    "pagedown": 0x22,  # VK_NEXT
    "left": 0x25,  # VK_LEFT
    "up": 0x26,  # VK_UP
    "right": 0x27,  # VK_RIGHT
    "down": 0x28,  # VK_DOWN
    # Letters (A-Z)
    **{chr(c): c for c in range(0x41, 0x5B)},
    # Digits (0-9)
    **{str(d): 0x30 + d for d in range(10)},
    # Function keys (F1-F24)
    **{f"f{i}": 0x70 + (i - 1) for i in range(1, 25)},
}

MEDIA_VK_MAP: dict[str, int] = {
    "play_pause": 0xB3,  # VK_MEDIA_PLAY_PAUSE
    "next": 0xB0,  # VK_MEDIA_NEXT_TRACK
    "next_track": 0xB0,
    "previous": 0xB1,  # VK_MEDIA_PREV_TRACK
    "prev_track": 0xB1,
    "volume_up": 0xAF,  # VK_VOLUME_UP
    "volup": 0xAF,
    "volume_down": 0xAE,  # VK_VOLUME_DOWN
    "voldown": 0xAE,
    "mute": 0xAD,  # VK_VOLUME_MUTE
    "stop": 0xB2,  # VK_MEDIA_STOP
}


# ============================================================================
# Action Interfaces and Base Classes
# ============================================================================


@dataclass
class ActionResult:
    """Outcome of an executed desktop action."""

    success: bool
    action_type: str
    trigger: str = ""
    error_message: str | None = None
    execution_time_ms: float = 0.0
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message and self.error_message:
            self.message = self.error_message
        elif self.message and not self.error_message:
            self.error_message = self.message


class BaseAction(ABC):
    """Abstract base class for all TapDeck desktop actions."""

    @property
    @abstractmethod
    def action_type(self) -> str:
        """String identifier for this action type."""

    @abstractmethod
    def validate(self, detailed: bool = False) -> bool | tuple[bool, str]:
        """Validate action configuration.

        Returns:
            Boolean or tuple of (is_valid, error_message).
        """

    @abstractmethod
    def execute(self) -> ActionResult:
        """Execute the action.

        Returns:
            ActionResult detailing execution status.
        """

    @abstractmethod
    def describe(self) -> str:
        """Provide a human-readable description of the action."""


# ============================================================================
# Concrete Action Implementations
# ============================================================================


class LaunchAppAction(BaseAction):
    """Action to launch an external executable or application."""

    def __init__(self, executable: str, args: list[str] | None = None) -> None:
        """Initialize LaunchAppAction.

        Args:
            executable: Path to executable or command available on PATH.
            args: Optional command line arguments.
        """
        self.executable = executable.strip()
        self.args = list(args) if args is not None else []

    @property
    def action_type(self) -> str:
        return "launch_app"

    def validate(self, detailed: bool = False) -> bool | tuple[bool, str]:
        if not self.executable:
            return (False, "Executable path cannot be empty") if detailed else False

        # Check if file exists directly or can be resolved on system PATH
        if Path(self.executable).exists() or shutil.which(self.executable):
            return (True, "") if detailed else True

        return (
            (False, f"Executable '{self.executable}' not found on disk or PATH")
            if detailed
            else False
        )

    def execute(self) -> ActionResult:
        t0 = time.perf_counter()
        valid, err = self.validate(detailed=True)
        if not valid:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=err,
                execution_time_ms=(time.perf_counter() - t0) * 1000.0,
            )

        cmd = [self.executable, *self.args]
        try:
            # Launch non-blocking background process
            subprocess.Popen(
                cmd,
                shell=False,
                creationflags=subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0,
            )
            elapsed = (time.perf_counter() - t0) * 1000.0
            logger.info("Launched application: %s", " ".join(cmd))
            return ActionResult(
                success=True,
                action_type=self.action_type,
                trigger="",
                error_message=None,
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            logger.error("Failed to launch %s: %s", self.executable, exc)
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=str(exc),
                execution_time_ms=elapsed,
            )

    def describe(self) -> str:
        args_str = f" {' '.join(self.args)}" if self.args else ""
        return f"Launch: {self.executable}{args_str}"


class HotkeyAction(BaseAction):
    """Action to simulate a keyboard hotkey combination."""

    def __init__(self, keys: list[str]) -> None:
        """Initialize HotkeyAction.

        Args:
            keys: Sequence of key names to press simultaneously (e.g. ['ctrl', 'c']).
        """
        self.keys = [k.lower().strip() for k in keys]

    @property
    def action_type(self) -> str:
        return "hotkey"

    def validate(self) -> tuple[bool, str]:
        if not self.keys:
            return False, "Hotkey sequence cannot be empty"

        invalid_keys: list[str] = [k for k in self.keys if k not in VK_MAP]
        if invalid_keys:
            return False, f"Unknown key name(s): {', '.join(invalid_keys)}"

        return True, ""

    def execute(self) -> ActionResult:
        t0 = time.perf_counter()
        valid, err = self.validate()
        if not valid:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=err,
                execution_time_ms=(time.perf_counter() - t0) * 1000.0,
            )

        vk_list = [VK_MAP[k] for k in self.keys]

        # Key down events in order
        events: list[tuple[int, int]] = []
        for vk in vk_list:
            events.append((vk, 0))

        # Key up events in reverse order
        for vk in reversed(vk_list):
            events.append((vk, KEYEVENTF_KEYUP))

        success = _send_keyboard_events(events)
        elapsed = (time.perf_counter() - t0) * 1000.0

        if success:
            logger.info("Sent hotkey combination: %s", "+".join(self.keys))
            return ActionResult(
                success=True,
                action_type=self.action_type,
                trigger="",
                error_message=None,
                execution_time_ms=elapsed,
            )
        else:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message="SendInput rejected hotkey events",
                execution_time_ms=elapsed,
            )

    def describe(self) -> str:
        return f"Hotkey: {' + '.join(k.upper() for k in self.keys)}"


class MediaKeyAction(BaseAction):
    """Action to trigger Windows media keys (volume, playback)."""

    def __init__(self, media_key: str) -> None:
        """Initialize MediaKeyAction.

        Args:
            media_key: One of 'play_pause', 'next', 'previous', 'volume_up', 'volume_down', 'mute'.
        """
        self.media_key = media_key.lower().strip()

    @property
    def action_type(self) -> str:
        return "media_key"

    def validate(self) -> tuple[bool, str]:
        if self.media_key not in MEDIA_VK_MAP:
            valid_opts = ", ".join(MEDIA_VK_MAP.keys())
            return False, f"Invalid media key '{self.media_key}'. Must be one of: {valid_opts}"
        return True, ""

    def execute(self) -> ActionResult:
        t0 = time.perf_counter()
        valid, err = self.validate()
        if not valid:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=err,
                execution_time_ms=(time.perf_counter() - t0) * 1000.0,
            )

        vk = MEDIA_VK_MAP[self.media_key]
        events = [
            (vk, KEYEVENTF_EXTENDEDKEY),
            (vk, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP),
        ]

        success = _send_keyboard_events(events)
        elapsed = (time.perf_counter() - t0) * 1000.0

        if success:
            logger.info("Triggered media key: %s", self.media_key)
            return ActionResult(
                success=True,
                action_type=self.action_type,
                trigger="",
                error_message=None,
                execution_time_ms=elapsed,
            )
        else:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=f"SendInput failed for media key '{self.media_key}'",
                execution_time_ms=elapsed,
            )

    def describe(self) -> str:
        return f"Media: {self.media_key.replace('_', ' ').title()}"


class ShellCommandAction(BaseAction):
    """Action to execute an arbitrary shell command."""

    def __init__(self, command: str, timeout: int = 10) -> None:
        """Initialize ShellCommandAction.

        Args:
            command: Shell command string to execute.
            timeout: Maximum execution timeout in seconds.
        """
        self.command = command.strip()
        self.timeout = max(1, timeout)

    @property
    def action_type(self) -> str:
        return "shell_command"

    def validate(self) -> tuple[bool, str]:
        if not self.command:
            return False, "Shell command cannot be empty"
        logger.warning(
            "Security notice: ShellCommandAction configured to run arbitrary command '%s'",
            self.command,
        )
        return True, ""

    def execute(self) -> ActionResult:
        t0 = time.perf_counter()
        valid, err = self.validate()
        if not valid:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=err,
                execution_time_ms=(time.perf_counter() - t0) * 1000.0,
            )

        try:
            proc = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            elapsed = (time.perf_counter() - t0) * 1000.0
            if proc.returncode == 0:
                logger.info("Shell command succeeded: %s", self.command)
                return ActionResult(
                    success=True,
                    action_type=self.action_type,
                    trigger="",
                    error_message=None,
                    execution_time_ms=elapsed,
                )
            else:
                err_text = proc.stderr.strip() or f"Process exited with code {proc.returncode}"
                logger.warning("Shell command failed: %s -> %s", self.command, err_text)
                return ActionResult(
                    success=False,
                    action_type=self.action_type,
                    trigger="",
                    error_message=err_text,
                    execution_time_ms=elapsed,
                )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=f"Command timed out after {self.timeout}s",
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ActionResult(
                success=False,
                action_type=self.action_type,
                trigger="",
                error_message=str(exc),
                execution_time_ms=elapsed,
            )

    def describe(self) -> str:
        return f"Shell: {self.command}"


class TestModeAction(BaseAction):
    """Wrapper action that logs execution details without performing physical side-effects."""

    __test__ = False

    def __init__(self, wrapped_action: BaseAction) -> None:
        """Initialize TestModeAction.

        Args:
            wrapped_action: BaseAction instance to wrap.
        """
        self.wrapped = wrapped_action

    @property
    def action_type(self) -> str:
        return f"test_mode[{self.wrapped.action_type}]"

    def validate(self) -> tuple[bool, str]:
        return self.wrapped.validate()

    def execute(self) -> ActionResult:
        desc = self.wrapped.describe()
        logger.info("[TEST MODE] Would execute: %s", desc)
        return ActionResult(
            success=True,
            action_type=self.action_type,
            trigger="",
            error_message=None,
            execution_time_ms=0.0,
        )

    def describe(self) -> str:
        return f"[Test Mode] {self.wrapped.describe()}"


# ============================================================================
# Action Dispatcher
# ============================================================================


class ActionDispatcher:
    """Manages trigger token action bindings and coordinates action execution."""

    def __init__(
        self,
        bindings: dict[str, Any] | None = None,
        test_mode: bool = False,
    ) -> None:
        """Initialize ActionDispatcher.

        Args:
            bindings: Optional bindings dict to load on initialization.
            test_mode: When True, actions are logged without performing system side-effects.
        """
        if isinstance(bindings, bool) and not test_mode:
            self.test_mode = bindings
            self._actions: dict[str, BaseAction] = {}
        else:
            self.test_mode = test_mode
            self._actions = {}
            if isinstance(bindings, dict):
                self.load_bindings(bindings)

    def load_bindings(self, bindings: dict[str, Any]) -> None:
        """Parse binding dictionary and instantiate corresponding BaseAction objects.

        Args:
            bindings: Dictionary mapping TriggerToken names (e.g. 'SINGLE_LT') to action configs.
        """
        self._actions.clear()
        config_map = bindings.get("bindings", bindings)

        for trigger_name, action_info in config_map.items():
            if not isinstance(action_info, dict):
                continue

            action_type = action_info.get("action_type") or action_info.get("action")
            params = action_info.get("params", {})

            action: BaseAction | None = None
            if action_type == "hotkey":
                keys = params.get("keys", [])
                action = HotkeyAction(keys=keys)
            elif action_type == "media_key" or (
                isinstance(action_type, str) and action_type.startswith("media_")
            ):
                media_key = params.get("media_key", "")
                if (
                    not media_key
                    and isinstance(action_type, str)
                    and action_type.startswith("media_")
                ):
                    media_key = action_type.replace("media_", "")
                action = MediaKeyAction(media_key=media_key)
            elif action_type == "launch_app":
                exe = params.get("executable", "")
                args = params.get("args", [])
                action = LaunchAppAction(executable=exe, args=args)
            elif action_type == "shell_command":
                cmd = params.get("command", "")
                timeout = params.get("timeout", 10)
                action = ShellCommandAction(command=cmd, timeout=timeout)
            elif action_type == "test_mode":
                sub_action_type = params.get("action_type")
                sub_params = params.get("params", {})
                # Recursively parse wrapped action
                dummy_dict = {"tmp": {"action_type": sub_action_type, "params": sub_params}}
                sub_disp = ActionDispatcher()
                sub_disp.load_bindings(dummy_dict)
                sub_action = sub_disp.get_action("tmp")
                if sub_action:
                    action = TestModeAction(sub_action)

            if action is not None:
                if self.test_mode and not isinstance(action, TestModeAction):
                    action = TestModeAction(action)
                self._actions[str(trigger_name)] = action
                logger.debug("Bound trigger '%s' -> %s", trigger_name, action.describe())
            else:
                logger.warning("Unrecognized action configuration for trigger '%s'", trigger_name)

    def dispatch(self, token: TriggerToken | str) -> ActionResult:
        """Execute the configured action for a trigger token.

        Args:
            token: TriggerToken enum or string representation.

        Returns:
            ActionResult indicating execution outcome.
        """
        key = token.value if isinstance(token, TriggerToken) else str(token)
        action = self._actions.get(key)

        if action is None:
            logger.debug("No action bound to trigger '%s'", key)
            return ActionResult(
                success=False,
                action_type="none",
                trigger=key,
                error_message=f"No action bound to trigger '{key}'",
                execution_time_ms=0.0,
            )

        result = action.execute()
        result.trigger = key
        return result

    def get_action(self, token: TriggerToken | str) -> BaseAction | None:
        """Retrieve the BaseAction configured for a trigger token.

        Args:
            token: TriggerToken enum or string.

        Returns:
            Configured BaseAction instance, or None if unbound.
        """
        key = token.value if isinstance(token, TriggerToken) else str(token)
        return self._actions.get(key)

    def list_bindings(self) -> dict[str, str]:
        """Return a mapping of trigger names to human-readable action descriptions.

        Returns:
            Dict mapping trigger token name to action description string.
        """
        return {trigger: action.describe() for trigger, action in self._actions.items()}
