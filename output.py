"""Output-Reports an den DualSense: Rumble, Trigger, Lightbar, Player-LEDs.

USB und Bluetooth nutzen dasselbe Payload-Layout, aber BT schiebt es um
zwei Byte nach hinten und verlangt eine CRC32 am Ende. Die Offsets folgen
dem Linux-Treiber hid-playstation.
"""

from __future__ import annotations

import zlib

USB_OUT_ID = 0x02
USB_OUT_SIZE = 48
BT_OUT_ID = 0x31
BT_OUT_SIZE = 78

# Bluetooth-CRC wird ueber ein vorangestelltes Seed-Byte mitgerechnet.
BT_CRC_SEED = 0xA2

FLAG0_COMPAT_VIBRATION = 0x01
FLAG0_HAPTICS_SELECT = 0x02
FLAG0_RIGHT_TRIGGER = 0x04
FLAG0_LEFT_TRIGGER = 0x08
FLAG1_LIGHTBAR = 0x04
FLAG1_RELEASE_LEDS = 0x08
FLAG1_PLAYER_LEDS = 0x10
# Ab Firmware 2.21 gibt es eine zweite, kraeftigere Rumble-Emulation.
FLAG2_COMPAT_VIBRATION2 = 0x04

# Payload-Offsets
P_FLAG0, P_FLAG1 = 0, 1
P_MOTOR_SMALL, P_MOTOR_LARGE = 2, 3
P_RIGHT_TRIGGER, P_LEFT_TRIGGER = 10, 21   # je 11 Byte Effekt
P_FLAG2 = 38
P_PLAYER_LEDS = 43
P_LIGHTBAR = 44                             # R, G, B


class OutputReport:
    """Baut einen Output-Report fuer USB oder Bluetooth."""

    def __init__(self, bluetooth: bool, vibration_v2: bool = False):
        self.bluetooth = bluetooth
        self.vibration_v2 = vibration_v2
        # Offset des Payloads: USB direkt hinter der Report-ID, BT hinter
        # Report-ID + Sequenz-Tag + Feld-Tag.
        self.base = 3 if bluetooth else 1
        size = BT_OUT_SIZE if bluetooth else USB_OUT_SIZE
        self.buf = bytearray(size)
        self.buf[0] = BT_OUT_ID if bluetooth else USB_OUT_ID
        if bluetooth:
            self.buf[2] = 0x10

    def _p(self, offset: int) -> int:
        """Payload-Offset -> absoluter Index im Puffer."""
        return self.base + offset

    def rumble(self, large: int, small: int) -> "OutputReport":
        """large = schwerer Motor (links), small = leichter Motor (rechts)."""
        self.buf[self._p(P_FLAG0)] |= FLAG0_HAPTICS_SELECT
        if self.vibration_v2:
            self.buf[self._p(P_FLAG2)] |= FLAG2_COMPAT_VIBRATION2
        else:
            self.buf[self._p(P_FLAG0)] |= FLAG0_COMPAT_VIBRATION
        self.buf[self._p(P_MOTOR_SMALL)] = max(0, min(255, small))
        self.buf[self._p(P_MOTOR_LARGE)] = max(0, min(255, large))
        return self

    def triggers(self, left: bytes | None = None,
                 right: bytes | None = None) -> "OutputReport":
        """Adaptive Trigger; Effekte kommen aus triggers.py (je 11 Byte)."""
        if right is not None:
            self.buf[self._p(P_FLAG0)] |= FLAG0_RIGHT_TRIGGER
            at = self._p(P_RIGHT_TRIGGER)
            self.buf[at:at + 11] = right
        if left is not None:
            self.buf[self._p(P_FLAG0)] |= FLAG0_LEFT_TRIGGER
            at = self._p(P_LEFT_TRIGGER)
            self.buf[at:at + 11] = left
        return self

    def lightbar(self, r: int, g: int, b: int) -> "OutputReport":
        self.buf[self._p(P_FLAG1)] |= FLAG1_LIGHTBAR | FLAG1_RELEASE_LEDS
        for i, v in enumerate((r, g, b)):
            self.buf[self._p(P_LIGHTBAR + i)] = max(0, min(255, v))
        return self

    def player_leds(self, bits: int) -> "OutputReport":
        """Die fuenf LEDs unter dem Touchpad, als Bitmaske 0..0x1F."""
        self.buf[self._p(P_FLAG1)] |= FLAG1_PLAYER_LEDS
        self.buf[self._p(P_PLAYER_LEDS)] = bits & 0x1F
        return self

    def finish(self, seq: int = 0) -> bytes:
        if self.bluetooth:
            self.buf[1] = (seq & 0x0F) << 4
            crc = zlib.crc32(bytes([BT_CRC_SEED]))
            crc = zlib.crc32(bytes(self.buf[: BT_OUT_SIZE - 4]), crc)
            self.buf[BT_OUT_SIZE - 4 :] = crc.to_bytes(4, "little")
        return bytes(self.buf)


class OutputChannel:
    """Haelt den Sequenzzaehler und schreibt auf das HID-Geraet."""

    def __init__(self, dev, bluetooth: bool, vibration_v2: bool = False):
        self.dev = dev
        self.bluetooth = bluetooth
        self.vibration_v2 = vibration_v2
        self.seq = 0

    def send(self, report: OutputReport) -> None:
        data = report.finish(self.seq)
        self.seq = (self.seq + 1) & 0x0F
        self.dev.write(data)

    def new(self) -> OutputReport:
        return OutputReport(self.bluetooth, self.vibration_v2)
