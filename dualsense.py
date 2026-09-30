"""DualSense (PS5) HID-Reader.

Dekodiert die Input-Reports des Controllers ueber USB und Bluetooth.
Reine Userspace-Bibliothek - kein Treiber noetig.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

import hid

SONY_VID = 0x054C
DUALSENSE_PIDS = {
    0x0CE6: "DualSense",
    0x0DF2: "DualSense Edge",
}

# Report-IDs: USB liefert 0x01 (64 Byte), Bluetooth 0x31 (78 Byte).
# Das BT-Layout ist gegenueber USB um genau ein Byte verschoben.
USB_REPORT_ID = 0x01
BT_REPORT_ID = 0x31

DPAD_DIRECTIONS = [
    "N", "NE", "E", "SE", "S", "SW", "W", "NW", "none",
]


@dataclass
class State:
    """Ein dekodierter Input-Report."""

    # Sticks und Trigger, roh wie der Controller sie liefert (0..255).
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    l2: int = 0
    r2: int = 0

    dpad: str = "none"
    buttons: set[str] = field(default_factory=set)

    gyro: tuple[int, int, int] = (0, 0, 0)
    accel: tuple[int, int, int] = (0, 0, 0)

    touch1: tuple[int, int] | None = None
    touch2: tuple[int, int] | None = None

    battery_percent: int | None = None
    charging: bool = False
    battery_full: bool = False

    def held(self, name: str) -> bool:
        return name in self.buttons


def _s16(lo: int, hi: int) -> int:
    v = lo | (hi << 8)
    return v - 0x10000 if v & 0x8000 else v


def _touch(data: bytes, at: int) -> tuple[int, int] | None:
    # Bit 7 des ersten Bytes ist low-active: 0 = Finger liegt auf.
    if data[at] & 0x80:
        return None
    x = data[at + 1] | ((data[at + 2] & 0x0F) << 8)
    y = (data[at + 2] >> 4) | (data[at + 3] << 4)
    return x, y


def decode(data: bytes) -> State | None:
    """Dekodiert einen rohen Input-Report. None, wenn unbekanntes Format."""
    if not data:
        return None

    if data[0] == USB_REPORT_ID and len(data) >= 64:
        o = 1
    elif data[0] == BT_REPORT_ID and len(data) >= 78:
        o = 2
    else:
        # Der BT-Minimalreport 0x01 (10 Byte) kommt, solange der volle
        # Modus nicht angefordert wurde - siehe DualSense.enable_full_bt().
        return None

    st = State()
    st.lx, st.ly, st.rx, st.ry = data[o], data[o + 1], data[o + 2], data[o + 3]
    st.l2, st.r2 = data[o + 4], data[o + 5]

    b0, b1, b2 = data[o + 7], data[o + 8], data[o + 9]

    hat = b0 & 0x0F
    st.dpad = DPAD_DIRECTIONS[hat] if hat < len(DPAD_DIRECTIONS) else "none"

    for mask, name in (
        (0x10, "square"), (0x20, "cross"), (0x40, "circle"), (0x80, "triangle"),
    ):
        if b0 & mask:
            st.buttons.add(name)

    for mask, name in (
        (0x01, "l1"), (0x02, "r1"), (0x04, "l2_click"), (0x08, "r2_click"),
        (0x10, "create"), (0x20, "options"), (0x40, "l3"), (0x80, "r3"),
    ):
        if b1 & mask:
            st.buttons.add(name)

    for mask, name in ((0x01, "ps"), (0x02, "touchpad"), (0x04, "mute")):
        if b2 & mask:
            st.buttons.add(name)

    st.gyro = (
        _s16(data[o + 15], data[o + 16]),
        _s16(data[o + 17], data[o + 18]),
        _s16(data[o + 19], data[o + 20]),
    )
    st.accel = (
        _s16(data[o + 21], data[o + 22]),
        _s16(data[o + 23], data[o + 24]),
        _s16(data[o + 25], data[o + 26]),
    )

    st.touch1 = _touch(data, o + 32)
    st.touch2 = _touch(data, o + 36)

    # Statusbyte: unteres Nibble = Ladestufe 0..10, oberes = Ladezustand.
    batt = data[o + 52]
    level = batt & 0x0F
    charge_state = (batt >> 4) & 0x0F

    if charge_state == 0x02:          # voll
        st.battery_percent = 100
        st.battery_full = True
    elif level >= 10:
        st.battery_percent = 100
    else:
        # Die Stufe ist ein Zehner-Bucket; die Mitte trifft am besten.
        st.battery_percent = level * 10 + 5
    st.charging = charge_state == 0x01

    return st


def is_usb(dev: dict) -> bool:
    """Ueber USB meldet der Controller eine Interface-Nummer, ueber
    Bluetooth nicht."""
    return dev.get("interface_number", -1) != -1


def find() -> list[dict]:
    """Alle angeschlossenen DualSense-Interfaces, USB zuerst.

    Haengt der Controller gleichzeitig am Kabel und an Bluetooth, sind
    beide Interfaces da. USB ist das bessere: hoehere Reportrate, keine
    CRC noetig, und der Akku laedt dabei."""
    found = [d for d in hid.enumerate(SONY_VID, 0)
             if d["product_id"] in DUALSENSE_PIDS]
    found.sort(key=lambda d: not is_usb(d))
    return found


class DualSense:
    def __init__(self, path: bytes | None = None):
        devices = find()
        if not devices:
            raise RuntimeError(
                "Kein DualSense gefunden. Per USB einstecken oder ueber "
                "Bluetooth verbinden (PS + Create gedrueckt halten)."
            )
        self.info = next((d for d in devices if d["path"] == path), devices[0])
        self.dev = hid.device()
        self.dev.open_path(self.info["path"])
        self.dev.set_nonblocking(True)
        self.bluetooth = False
        self.state = State()
        # Gelesene Reports insgesamt - daraus ergibt sich die Reportrate.
        # reads zaehlt die Lesevorgaenge; reports/reads > 1 = Rueckstau.
        self.reports = 0
        self.reads = 0

    def enable_full_bt(self) -> None:
        """Ueber BT liefert der Controller erst nach diesem Feature-Report
        den vollen 0x31-Report mit Gyro, Touchpad und Batterie."""
        try:
            self.dev.get_feature_report(0x05, 41)
        except Exception:
            pass

    def vibration_v2(self) -> bool:
        """Kann der Controller die kraeftigere Rumble-Emulation? Ab
        Firmware 2.21, die Edge immer. Steht im Feature-Report 0x20."""
        if self.info["product_id"] == 0x0DF2:
            return True
        try:
            r = self.dev.get_feature_report(0x20, 64)
            return len(r) >= 46 and (r[44] | (r[45] << 8)) >= 0x0221
        except Exception:
            return False

    def poll(self) -> State | None:
        data = self.dev.read(78)
        if not data:
            return None
        st = decode(bytes(data))
        if st is None:
            return None
        self.bluetooth = data[0] == BT_REPORT_ID
        self.state = st
        return st

    def poll_latest(self, timeout_ms: int = 4) -> State | None:
        """Wartet bis zu timeout_ms auf einen Report und leert dann die
        Warteschlange, damit nur der neueste zaehlt.

        Ueber USB kommen 1000 Reports/s. Wer pro Durchlauf nur einen liest,
        faellt knapp zurueck, bis der Windows-Puffer voll ist - dann haengt
        die Eingabe dauerhaft zig Millisekunden hinterher."""
        data = self.dev.read(78, timeout_ms)
        if not data:
            return None
        self.reports += 1
        self.reads += 1
        # Begrenzt, damit ein Dauerstrom die Schleife nicht festhaelt.
        for _ in range(256):
            newer = self.dev.read(78)
            if not newer:
                break
            data = newer
            self.reports += 1
        st = decode(bytes(data))
        if st is None:
            return None
        self.bluetooth = data[0] == BT_REPORT_ID
        self.state = st
        return st

    def close(self) -> None:
        self.dev.close()

    def __enter__(self) -> "DualSense":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _monitor() -> int:
    devices = find()
    if not devices:
        print("Kein DualSense gefunden.")
        print("  USB:       Kabel einstecken (empfohlen, einfachstes Protokoll)")
        print("  Bluetooth: PS-Taste + Create ~5s halten, dann in Windows koppeln")
        return 1

    for d in devices:
        name = DUALSENSE_PIDS.get(d["product_id"], "?")
        print(f"gefunden: {name}  usage_page=0x{d['usage_page']:04x} "
              f"usage=0x{d['usage']:02x}")

    ds = DualSense()
    ds.enable_full_bt()
    print("\nLive-Reader laeuft - Strg+C zum Beenden.\n")

    last = 0.0
    try:
        while True:
            st = ds.poll()
            now = time.time()
            if st and now - last > 0.05:
                last = now
                link = "BT " if ds.bluetooth else "USB"
                btns = " ".join(sorted(st.buttons)) or "-"
                touch = f"{st.touch1}" if st.touch1 else "-"
                sys.stdout.write(
                    f"\r{link} | L({st.lx:3d},{st.ly:3d}) R({st.rx:3d},{st.ry:3d}) "
                    f"| L2 {st.l2:3d} R2 {st.r2:3d} | dpad {st.dpad:<4} "
                    f"| bat {st.battery_percent:3d}%{'+' if st.charging else ' '} "
                    f"| touch {touch:<12} | {btns:<40}"
                )
                sys.stdout.flush()
            time.sleep(0.001)
    except KeyboardInterrupt:
        print("\nbeendet.")
    finally:
        ds.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_monitor())
