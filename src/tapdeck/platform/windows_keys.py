"""Windows virtual key code constants and SendInput keyboard synthesis helpers."""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from ctypes import wintypes
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# ============================================================================
# SendInput Event Flags & Types
# ============================================================================

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# ============================================================================
# Virtual Key Codes (VK_*)
# ============================================================================

# Mouse / System
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_CANCEL = 0x03
VK_MBUTTON = 0x04
VK_XBUTTON1 = 0x05
VK_XBUTTON2 = 0x06

# Control keys
VK_BACK = 0x08
VK_TAB = 0x09
VK_CLEAR = 0x0C
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_PAUSE = 0x13
VK_CAPITAL = 0x14  # Caps Lock
VK_ESCAPE = 0x1B
VK_SPACE = 0x20

# Navigation / Edit
VK_PRIOR = 0x21  # Page Up
VK_NEXT = 0x22  # Page Down
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SELECT = 0x29
VK_PRINT = 0x2A
VK_EXECUTE = 0x2B
VK_SNAPSHOT = 0x2C  # Print Screen
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_HELP = 0x2F

# Numbers 0-9 (ASCII '0'-'9')
VK_0 = 0x30
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34
VK_5 = 0x35
VK_6 = 0x36
VK_7 = 0x37
VK_8 = 0x38
VK_9 = 0x39

# Letters A-Z (ASCII 'A'-'Z')
VK_A = 0x41
VK_B = 0x42
VK_C = 0x43
VK_D = 0x44
VK_E = 0x45
VK_F = 0x46
VK_G = 0x47
VK_H = 0x48
VK_I = 0x49
VK_J = 0x4A
VK_K = 0x4B
VK_L = 0x4C
VK_M = 0x4D
VK_N = 0x4E
VK_O = 0x4F
VK_P = 0x50
VK_Q = 0x51
VK_R = 0x52
VK_S = 0x53
VK_T = 0x54
VK_U = 0x55
VK_V = 0x56
VK_W = 0x57
VK_X = 0x58
VK_Y = 0x59
VK_Z = 0x5A

# Windows keys
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_APPS = 0x5D
VK_SLEEP = 0x5F

# Numpad
VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_NUMPAD3 = 0x63
VK_NUMPAD4 = 0x64
VK_NUMPAD5 = 0x65
VK_NUMPAD6 = 0x66
VK_NUMPAD7 = 0x67
VK_NUMPAD8 = 0x68
VK_NUMPAD9 = 0x69
VK_MULTIPLY = 0x6A
VK_ADD = 0x6B
VK_SEPARATOR = 0x6C
VK_SUBTRACT = 0x6D
VK_DECIMAL = 0x6E
VK_DIVIDE = 0x6F

# Function keys F1-F24
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_F13 = 0x7C
VK_F14 = 0x7D
VK_F15 = 0x7E
VK_F16 = 0x7F
VK_F17 = 0x80
VK_F18 = 0x81
VK_F19 = 0x82
VK_F20 = 0x83
VK_F21 = 0x84
VK_F22 = 0x85
VK_F23 = 0x86
VK_F24 = 0x87

# Locks
VK_NUMLOCK = 0x90
VK_SCROLL = 0x91

# Left and Right Modifiers
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

# Browser Keys
VK_BROWSER_BACK = 0xA6
VK_BROWSER_FORWARD = 0xA7
VK_BROWSER_REFRESH = 0xA8
VK_BROWSER_STOP = 0xA9
VK_BROWSER_SEARCH = 0xAA
VK_BROWSER_FAVORITES = 0xAB
VK_BROWSER_HOME = 0xAC

# Media & Volume Keys
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_LAUNCH_MAIL = 0xB4
VK_LAUNCH_MEDIA_SELECT = 0xB5
VK_LAUNCH_APP1 = 0xB6
VK_LAUNCH_APP2 = 0xB7

# OEM Punctuation
VK_OEM_1 = 0xBA  # ';:' for US
VK_OEM_PLUS = 0xBB  # '+'
VK_OEM_COMMA = 0xBC  # ','
VK_OEM_MINUS = 0xBD  # '-'
VK_OEM_PERIOD = 0xBE  # '.'
VK_OEM_2 = 0xBF  # '/?'
VK_OEM_3 = 0xC0  # '`~'
VK_OEM_4 = 0xDB  # '[{'
VK_OEM_5 = 0xDC  # '\|'
VK_OEM_6 = 0xDD  # ']}'
VK_OEM_7 = 0xDE  # ''"'

# Set of keys requiring KEYEVENTF_EXTENDEDKEY flag on Windows
_EXTENDED_KEYS: frozenset[int] = frozenset(
    {
        VK_RCONTROL,
        VK_RMENU,
        VK_LWIN,
        VK_RWIN,
        VK_APPS,
        VK_INSERT,
        VK_DELETE,
        VK_HOME,
        VK_END,
        VK_PRIOR,
        VK_NEXT,
        VK_LEFT,
        VK_UP,
        VK_RIGHT,
        VK_DOWN,
        VK_NUMLOCK,
        VK_SNAPSHOT,
        VK_DIVIDE,
        VK_VOLUME_MUTE,
        VK_VOLUME_DOWN,
        VK_VOLUME_UP,
        VK_MEDIA_NEXT_TRACK,
        VK_MEDIA_PREV_TRACK,
        VK_MEDIA_STOP,
        VK_MEDIA_PLAY_PAUSE,
        VK_LAUNCH_MAIL,
        VK_LAUNCH_MEDIA_SELECT,
        VK_LAUNCH_APP1,
        VK_LAUNCH_APP2,
        VK_BROWSER_BACK,
        VK_BROWSER_FORWARD,
        VK_BROWSER_REFRESH,
        VK_BROWSER_STOP,
        VK_BROWSER_SEARCH,
        VK_BROWSER_FAVORITES,
        VK_BROWSER_HOME,
    }
)

# ============================================================================
# Ctypes Structures for Win32 SendInput
# ============================================================================

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    """Win32 KEYBDINPUT structure."""

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


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    """Win32 INPUT structure for SendInput."""

    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUTUNION),
    ]


# Safe dynamic loading of user32.SendInput
_SendInput = None
if sys.platform == "win32":
    try:
        _user32 = ctypes.WinDLL("user32", use_last_error=True)
        _SendInput = _user32.SendInput
        _SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        _SendInput.restype = wintypes.UINT
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to initialize user32.SendInput: %s", exc)


# ============================================================================
# Key Name Mapping
# ============================================================================

VK_NAME_MAP: dict[str, int] = {
    # Modifiers
    "win": VK_LWIN,
    "windows": VK_LWIN,
    "super": VK_LWIN,
    "meta": VK_LWIN,
    "lwin": VK_LWIN,
    "rwin": VK_RWIN,
    "ctrl": VK_CONTROL,
    "control": VK_CONTROL,
    "lctrl": VK_LCONTROL,
    "rctrl": VK_RCONTROL,
    "alt": VK_MENU,
    "menu": VK_MENU,
    "lalt": VK_LMENU,
    "ralt": VK_RMENU,
    "shift": VK_SHIFT,
    "lshift": VK_LSHIFT,
    "rshift": VK_RSHIFT,
    # Navigation & Edit
    "tab": VK_TAB,
    "enter": VK_RETURN,
    "return": VK_RETURN,
    "escape": VK_ESCAPE,
    "esc": VK_ESCAPE,
    "space": VK_SPACE,
    "spacebar": VK_SPACE,
    "backspace": VK_BACK,
    "back": VK_BACK,
    "bksp": VK_BACK,
    "delete": VK_DELETE,
    "del": VK_DELETE,
    "insert": VK_INSERT,
    "ins": VK_INSERT,
    "home": VK_HOME,
    "end": VK_END,
    "pageup": VK_PRIOR,
    "page_up": VK_PRIOR,
    "pgup": VK_PRIOR,
    "pagedown": VK_NEXT,
    "page_down": VK_NEXT,
    "pgdn": VK_NEXT,
    "left": VK_LEFT,
    "right": VK_RIGHT,
    "up": VK_UP,
    "down": VK_DOWN,
    "capslock": VK_CAPITAL,
    "caps": VK_CAPITAL,
    "printscreen": VK_SNAPSHOT,
    "prtscr": VK_SNAPSHOT,
    "prtsc": VK_SNAPSHOT,
    "scrolllock": VK_SCROLL,
    "pause": VK_PAUSE,
    "break": VK_PAUSE,
    "numlock": VK_NUMLOCK,
    # Media controls
    "volume_up": VK_VOLUME_UP,
    "volumeup": VK_VOLUME_UP,
    "volup": VK_VOLUME_UP,
    "volume_down": VK_VOLUME_DOWN,
    "volumedown": VK_VOLUME_DOWN,
    "voldown": VK_VOLUME_DOWN,
    "mute": VK_VOLUME_MUTE,
    "volume_mute": VK_VOLUME_MUTE,
    "volumemute": VK_VOLUME_MUTE,
    "play_pause": VK_MEDIA_PLAY_PAUSE,
    "playpause": VK_MEDIA_PLAY_PAUSE,
    "mediaplaypause": VK_MEDIA_PLAY_PAUSE,
    "next_track": VK_MEDIA_NEXT_TRACK,
    "nexttrack": VK_MEDIA_NEXT_TRACK,
    "medianext": VK_MEDIA_NEXT_TRACK,
    "prev_track": VK_MEDIA_PREV_TRACK,
    "prevtrack": VK_MEDIA_PREV_TRACK,
    "mediaprev": VK_MEDIA_PREV_TRACK,
    "media_stop": VK_MEDIA_STOP,
    "mediastop": VK_MEDIA_STOP,
    # Numpad operations
    "multiply": VK_MULTIPLY,
    "add": VK_ADD,
    "subtract": VK_SUBTRACT,
    "decimal": VK_DECIMAL,
    "divide": VK_DIVIDE,
}

# Populate digits 0-9
for d in range(10):
    VK_NAME_MAP[str(d)] = VK_0 + d
    VK_NAME_MAP[f"numpad{d}"] = VK_NUMPAD0 + d

# Populate letters a-z
for ch in range(ord("a"), ord("z") + 1):
    VK_NAME_MAP[chr(ch)] = VK_A + (ch - ord("a"))

# Populate function keys f1-f24
for f in range(1, 25):
    VK_NAME_MAP[f"f{f}"] = VK_F1 + (f - 1)


# ============================================================================
# Core Functions
# ============================================================================


def resolve_key_names(names: Sequence[str]) -> list[int]:
    """Convert a sequence of key string names to Windows virtual key codes.

    Args:
        names: Sequence of string key names (e.g., ['win', 'tab'] or ['ctrl', 'alt', 'd']).

    Returns:
        List of integer virtual key codes.

    Raises:
        ValueError: If any key name is unrecognized.
    """
    resolved: list[int] = []
    for raw in names:
        key = str(raw).strip().lower()
        if key in VK_NAME_MAP:
            resolved.append(VK_NAME_MAP[key])
        elif len(key) == 1 and (("a" <= key <= "z") or ("0" <= key <= "9")):
            resolved.append(ord(key.upper()))
        else:
            raise ValueError(f"Unrecognized virtual key name: '{raw}'")
    return resolved


def send_key_event(vk_code: int, key_up: bool = False, extended: bool = False) -> bool:
    """Send a single key event (press or release) using Win32 SendInput.

    Args:
        vk_code: Windows virtual key code.
        key_up: If True, release the key (KEYEVENTF_KEYUP); if False, press key down.
        extended: If True, explicitly specify KEYEVENTF_EXTENDEDKEY. Automatically
            set for known extended keys (navigation, media, etc.).

    Returns:
        True if the event was accepted by SendInput, False otherwise.
    """
    if _SendInput is None:
        logger.warning("SendInput unavailable (not running on Windows or API bind failed).")
        return False

    flags = 0
    if key_up:
        flags |= KEYEVENTF_KEYUP
    if extended or (vk_code in _EXTENDED_KEYS):
        flags |= KEYEVENTF_EXTENDEDKEY

    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk_code & 0xFFFF
    inp.ki.wScan = 0
    inp.ki.dwFlags = flags
    inp.ki.time = 0
    inp.ki.dwExtraInfo = 0

    sent = _SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        err = ctypes.get_last_error()
        logger.error("SendInput failed for vk_code=0x%02X (error=%d)", vk_code, err)
        return False
    return True


def tap_key(vk_code: int, extended: bool = False, delay: float = 0.01) -> bool:
    """Press and release a single key.

    Args:
        vk_code: Windows virtual key code.
        extended: Extended key flag.
        delay: Delay in seconds between press and release (default: 10ms).

    Returns:
        True if both press and release events succeeded.
    """
    press_ok = send_key_event(vk_code, key_up=False, extended=extended)
    if delay > 0:
        time.sleep(delay)
    release_ok = send_key_event(vk_code, key_up=True, extended=extended)
    return press_ok and release_ok


def press_keys(vk_codes: Sequence[int], delay: float = 0.01) -> bool:
    """Press all keys down in order, then release them in reverse order.

    Used for keyboard shortcuts (e.g. Win+Tab, Ctrl+Alt+Del, Win+D).

    Args:
        vk_codes: Sequence of virtual key codes.
        delay: Delay in seconds between individual key operations.

    Returns:
        True if all key events succeeded.
    """
    if not vk_codes:
        return True

    success = True
    pressed: list[int] = []
    try:
        for code in vk_codes:
            if not send_key_event(code, key_up=False):
                success = False
            pressed.append(code)
            if delay > 0:
                time.sleep(delay)
    finally:
        for code in reversed(pressed):
            if not send_key_event(code, key_up=True):
                success = False
            if delay > 0:
                time.sleep(delay)

    return success
