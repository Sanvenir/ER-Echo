#!/usr/bin/env python3
"""Tiny ViGEm virtual Xbox 360 pad (no Python deps, uses ViGEmClient.dll).

Usage:
  python vpad.py a           # tap A
  python vpad.py y           # tap Y (grace interact prompt)
  python vpad.py b / x / start / back
  python vpad.py hold Y 5    # hold a button for 5 seconds
  python vpad.py sequence start

Why: the game is in gamepad input mode and ignores synthetic keyboard/mouse for
the "press any button" / grace dialogs. ViGEmBus is already installed on this
machine; ViGEmClient.dll is vendored under tools/vigem/.
"""

import ctypes
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DLL = os.path.join(HERE, "vigem", "ViGEmClient.dll")

# XUSB_BUTTON
A = 0x1000
B = 0x2000
X = 0x4000
Y = 0x8000
START = 0x0010
BACK = 0x0020
DPAD_UP = 0x0001
DPAD_DOWN = 0x0002
DPAD_LEFT = 0x0004
DPAD_RIGHT = 0x0008
LB = 0x0100
RB = 0x0200

NAMES = {
    "a": A, "b": B, "x": X, "y": Y,
    "start": START, "back": BACK,
    "up": DPAD_UP, "down": DPAD_DOWN, "left": DPAD_LEFT, "right": DPAD_RIGHT,
    "lb": LB, "rb": RB,
}


class XUSB_REPORT(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


def open_pad():
    if not os.path.exists(DLL):
        raise SystemExit(f"missing {DLL}")
    dll = ctypes.WinDLL(DLL)
    dll.vigem_alloc.restype = ctypes.c_void_p
    dll.vigem_connect.argtypes = [ctypes.c_void_p]
    dll.vigem_connect.restype = ctypes.c_int
    dll.vigem_target_x360_alloc.restype = ctypes.c_void_p
    dll.vigem_target_add.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    dll.vigem_target_add.restype = ctypes.c_int
    dll.vigem_target_x360_update.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(XUSB_REPORT),
    ]
    dll.vigem_target_x360_update.restype = ctypes.c_int
    dll.vigem_target_remove.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    dll.vigem_target_free.argtypes = [ctypes.c_void_p]
    dll.vigem_disconnect.argtypes = [ctypes.c_void_p]
    dll.vigem_free.argtypes = [ctypes.c_void_p]

    client = dll.vigem_alloc()
    if not client:
        raise SystemExit("vigem_alloc failed")
    if (dll.vigem_connect(client) & 0xffffffff) != 0x20000000:
        raise SystemExit("vigem_connect failed (ViGEmBus not running?)")
    target = dll.vigem_target_x360_alloc()
    if not target:
        raise SystemExit("vigem_target_x360_alloc failed")
    if (dll.vigem_target_add(client, target) & 0xffffffff) != 0x20000000:
        raise SystemExit("vigem_target_add failed")
    return dll, client, target


def set_buttons(dll, client, target, buttons):
    report = XUSB_REPORT()
    report.wButtons = buttons
    rc = dll.vigem_target_x360_update(client, target, ctypes.byref(report))
    if (rc & 0xffffffff) != 0x20000000:
        raise SystemExit(f"update failed: {rc}")


def tap(button: str, ms: int = 120):
    mask = NAMES[button.lower()]
    dll, client, target = open_pad()
    try:
        time.sleep(0.25)
        set_buttons(dll, client, target, mask)
        time.sleep(ms / 1000.0)
        set_buttons(dll, client, target, 0)
        time.sleep(0.25)
    finally:
        dll.vigem_target_remove(client, target)
        dll.vigem_target_free(target)
        dll.vigem_disconnect(client)
        dll.vigem_free(client)


def hold(button: str, seconds: float):
    mask = NAMES[button.lower()]
    dll, client, target = open_pad()
    try:
        set_buttons(dll, client, target, mask)
        time.sleep(seconds)
        set_buttons(dll, client, target, 0)
    finally:
        dll.vigem_target_remove(client, target)
        dll.vigem_target_free(target)
        dll.vigem_disconnect(client)
        dll.vigem_free(client)


def sequence(name: str):
    """Press A every 1.5s for 60s (title / dialogs), then START/A."""
    dll, client, target = open_pad()
    try:
        end = time.time() + 90
        while time.time() < end:
            set_buttons(dll, client, target, A)
            time.sleep(0.12)
            set_buttons(dll, client, target, 0)
            time.sleep(1.5)
    finally:
        dll.vigem_target_remove(client, target)
        dll.vigem_target_free(target)
        dll.vigem_disconnect(client)
        dll.vigem_free(client)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cmd = sys.argv[1].lower()
    if cmd == "hold" and len(sys.argv) >= 4:
        hold(sys.argv[2], float(sys.argv[3]))
    elif cmd == "sequence":
        sequence(sys.argv[2] if len(sys.argv) > 2 else "start")
    elif cmd in NAMES:
        tap(cmd, int(sys.argv[2]) if len(sys.argv) > 2 else 120)
    else:
        print(__doc__)
        sys.exit(2)
