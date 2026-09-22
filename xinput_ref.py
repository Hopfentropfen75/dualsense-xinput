"""XInput-Leser ueber ctypes.

Dient als Referenz: so sieht der Zustand aus, den unser virtueller Pad
spaeter erzeugen muss.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

# Button-Masken laut XInput-Spezifikation.
BUTTONS = {
    0x0001: "dpad_up",
    0x0002: "dpad_down",
    0x0004: "dpad_left",
    0x0008: "dpad_right",
    0x0010: "start",
    0x0020: "back",
    0x0040: "l3",
    0x0080: "r3",
    0x0100: "lb",
    0x0200: "rb",
    0x0400: "guide",
    0x1000: "a",
    0x2000: "b",
    0x4000: "x",
    0x8000: "y",
}


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", XINPUT_GAMEPAD)]


def _load() -> ctypes.WinDLL:
    for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            return ctypes.WinDLL(name)
        except OSError:
            continue
    raise RuntimeError("Keine XInput-DLL gefunden.")


_dll = _load()
ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167


@dataclass
class XState:
    slot: int
    packet: int
    buttons: set[str]
    lt: int
    rt: int
    lx: int
    ly: int
    rx: int
    ry: int


def read(slot: int) -> XState | None:
    st = XINPUT_STATE()
    if _dll.XInputGetState(slot, ctypes.byref(st)) != ERROR_SUCCESS:
        return None
    g = st.Gamepad
    return XState(
        slot=slot,
        packet=st.dwPacketNumber,
        buttons={n for m, n in BUTTONS.items() if g.wButtons & m},
        lt=g.bLeftTrigger,
        rt=g.bRightTrigger,
        lx=g.sThumbLX,
        ly=g.sThumbLY,
        rx=g.sThumbRX,
        ry=g.sThumbRY,
    )


def connected() -> list[int]:
    return [s for s in range(4) if read(s) is not None]


if __name__ == "__main__":
    import sys, time

    slots = connected()
    print(f"XInput-Slots belegt: {slots or 'keine'}")
    if not slots:
        raise SystemExit(1)
    s = slots[0]
    print(f"lese Slot {s} - Strg+C zum Beenden\n")
    try:
        while True:
            x = read(s)
            if x:
                sys.stdout.write(
                    f"\rL({x.lx:6d},{x.ly:6d}) R({x.rx:6d},{x.ry:6d}) "
                    f"LT {x.lt:3d} RT {x.rt:3d} | "
                    f"{' '.join(sorted(x.buttons)) or '-':<50}"
                )
                sys.stdout.flush()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print()
