"""Adaptive Trigger: Effekt-Bytes und Profile.

XInput kennt keinen Trigger-Widerstand - kein Spiel kann ihn ueber den
virtuellen Pad anfordern. Die Bruecke setzt ihn deshalb selbst, fest pro
Profil oder abgeleitet aus dem Rumble, das das Spiel schickt.

Der Trigger-Weg ist in zehn Zonen geteilt (0 = Ruhe, 9 = durchgedrueckt),
Staerken laufen von 1 bis 8. Kodierung nach Nielk1s TriggerEffectGenerator.
"""

from __future__ import annotations

from dataclasses import dataclass

MODE_OFF = 0x05
MODE_FEEDBACK = 0x21
MODE_WEAPON = 0x25
MODE_VIBRATION = 0x26


def off() -> bytes:
    return bytes([MODE_OFF] + [0] * 10)


def _zones(position: int, strength: int) -> tuple[int, int]:
    """Ab `position` bis zum Anschlag dieselbe Staerke; 3 Bit pro Zone."""
    level = (max(1, min(8, strength)) - 1) & 0x07
    active = values = 0
    for i in range(max(0, min(9, position)), 10):
        active |= 1 << i
        values |= level << (3 * i)
    return active, values


def feedback(position: int, strength: int) -> bytes:
    """Gleichmaessiger Widerstand ab `position`."""
    active, values = _zones(position, strength)
    return bytes([MODE_FEEDBACK, active & 0xFF, active >> 8,
                  *values.to_bytes(4, "little"), 0, 0, 0, 0])


def weapon(start: int, end: int, strength: int) -> bytes:
    """Druckpunkt zwischen `start` (2..7) und `end` (start+1..8), der
    hinter `end` nachgibt - wie ein Abzug."""
    zones = (1 << start) | (1 << end)
    return bytes([MODE_WEAPON, zones & 0xFF, zones >> 8,
                  max(1, min(8, strength)) - 1, 0, 0, 0, 0, 0, 0, 0])


def vibration(position: int, amplitude: int, frequency: int) -> bytes:
    """Trigger vibriert ab `position` mit `frequency` Hz."""
    active, values = _zones(position, amplitude)
    return bytes([MODE_VIBRATION, active & 0xFF, active >> 8,
                  *values.to_bytes(4, "little"), 0, 0,
                  max(1, min(255, frequency)), 0])


# Unter dieser Rumble-Staerke bleibt der Trigger beim festen Effekt.
LIVE_THRESHOLD = 40
LIVE_FREQUENCY = 40

MODES: dict[str, str] = {
    "aus": "Aus",
    "racing": "Racing",
    "racing_live": "Racing + Rumble",
    "shooter": "Shooter",
}


@dataclass(frozen=True)
class Setup:
    left: bytes
    right: bytes
    # Gas-Trigger vibriert mit, wenn das Spiel rumblet (Durchdrehen,
    # Rumpeln, Einschlaege).
    live: bool = False

    def effects(self, large: int, small: int) -> tuple[bytes, bytes]:
        if not self.live:
            return self.left, self.right
        level = max(large, small)
        if level < LIVE_THRESHOLD:
            return self.left, self.right
        # Auf acht Stufen quantisiert - sonst ginge bei jeder kleinen
        # Rumble-Aenderung ein neuer Report raus.
        amp = 1 + level * 7 // 255
        return self.left, vibration(1, amp, LIVE_FREQUENCY)


def build(p: dict) -> Setup:
    """Trigger-Effekte aus einem Profil (siehe settings.PROFILE_DEFAULTS).

    Racing: Bremse (L2) mit Druckpunkt ab `brake_start`, Gas (R2) nur
    leicht gedaempft, damit es sich fein dosieren laesst."""
    mode = p.get("triggers", "aus")
    if mode in ("racing", "racing_live"):
        brake = feedback(int(p["brake_start"]), int(p["brake_force"]))
        gas = (feedback(1, int(p["gas_force"])) if int(p["gas_force"]) > 0
               else off())
        return Setup(brake, gas, live=mode == "racing_live")
    if mode == "shooter":
        return Setup(feedback(2, 3), weapon(4, 6, 6))
    return Setup(off(), off())
