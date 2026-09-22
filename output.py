"""Output-Reports an den DualSense: Rumble, Lightbar, Player-LEDs.

USB und Bluetooth nutzen dasselbe Payload-Layout, aber BT schiebt es um
zwei Byte nach hinten und verlangt eine CRC32 am Ende.
"""

from __future__ import annotations

import zlib

USB_OUT_ID = 0x02
USB_OUT_SIZE = 48
BT_OUT_ID = 0x31
BT_OUT_SIZE = 78

# Bluetooth-CRC wird ueber ein vorangestelltes Seed-Byte mitgerechnet.
BT_CRC_SEED = 0xA2

FLAG0_RUMBLE = 0x01
FLAG1_LIGHTBAR = 0x04
FLAG1_PLAYER_LEDS = 0x10
FLAG1_RELEASE_LEDS = 0x08


class OutputReport:
    """Baut einen Output-Report fuer USB oder Bluetooth."""

    def __init__(self, bluetooth: bool):
        self.bluetooth = bluetooth
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
        self.buf[self._p(0)] |= FLAG0_RUMBLE
        self.buf[self._p(2)] = max(0, min(255, small))
        self.buf[self._p(3)] = max(0, min(255, large))
        return self

    def lightbar(self, r: int, g: int, b: int) -> "OutputReport":
        self.buf[self._p(1)] |= FLAG1_LIGHTBAR | FLAG1_RELEASE_LEDS
        self.buf[self._p(43)] = max(0, min(255, r))
        self.buf[self._p(44)] = max(0, min(255, g))
        self.buf[self._p(45)] = max(0, min(255, b))
        return self

    def player_leds(self, bits: int) -> "OutputReport":
        """Die fuenf LEDs unter dem Touchpad, als Bitmaske 0..0x1F."""
        self.buf[self._p(1)] |= FLAG1_PLAYER_LEDS
        self.buf[self._p(42)] = bits & 0x1F
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

    def __init__(self, dev, bluetooth: bool):
        self.dev = dev
        self.bluetooth = bluetooth
        self.seq = 0

    def send(self, report: OutputReport) -> None:
        data = report.finish(self.seq)
        self.seq = (self.seq + 1) & 0x0F
        self.dev.write(data)

    def new(self) -> OutputReport:
        return OutputReport(self.bluetooth)
