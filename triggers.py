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
SPIN_FREQUENCY = 40
# Pedal gilt ab diesem Rohwert als gedrueckt.
PEDAL = 40
# Ohne Telemetrie: ABS nur bei kraeftigem Bremsen und Rumble schaetzen.
HARD_BRAKE = 150
# Reifenschlupf aus der Telemetrie: ab hier beginnt der Grip zu reissen.
SLIP_START = 0.9
MIN_SPEED = 3.0   # m/s - im Stand blockiert nichts

MODES: dict[str, str] = {
    "aus": "Aus",
    "racing": "Racing",
    "racing_live": "Racing + Feedback",
    "shooter": "Shooter",
}


def _slip_level(slip: float) -> float:
    """0 bei Grip, steigt ab SLIP_START und ist bei doppeltem Schlupf voll."""
    if slip < SLIP_START:
        return 0.0
    return min(1.0, 0.4 + (slip - SLIP_START) * 0.6)


@dataclass(frozen=True)
class Setup:
    left: bytes
    right: bytes
    # Racing + Feedback: L2 pulsiert bei blockierenden Raedern (ABS), R2
    # vibriert bei durchdrehenden. Mit Forza-Telemetrie aus dem echten
    # Reifenschlupf, sonst aus Pedal und Rumble geschaetzt.
    live: bool = False
    abs_strength: int = 0
    abs_frequency: int = 20
    spin_strength: int = 0

    def effects(self, rumble: tuple[int, int] = (0, 0), l2: int = 0,
                r2: int = 0, tele=None) -> tuple[bytes, bytes]:
        if not self.live:
            return self.left, self.right
        left, right = self.left, self.right
        a = self._abs(rumble, l2, tele)
        if a > 0 and self.abs_strength > 0:
            # Auf ganze Stufen gerundet - sonst ginge bei jeder kleinen
            # Aenderung ein neuer Report raus.
            amp = max(1, round(self.abs_strength * a))
            left = vibration(0, amp, self.abs_frequency)
        w = self._spin(rumble, l2, r2, tele)
        if w > 0 and self.spin_strength > 0:
            amp = max(1, round(self.spin_strength * w))
            right = vibration(1, amp, SPIN_FREQUENCY)
        return left, right

    @staticmethod
    def _abs(rumble, l2, tele) -> float:
        if l2 < PEDAL:
            return 0.0
        if tele is not None and tele.fresh:
            if tele.speed < MIN_SPEED:
                return 0.0
            return _slip_level(max(abs(s) for s in tele.slip))
        level = max(rumble)
        if l2 < HARD_BRAKE or level < LIVE_THRESHOLD:
            return 0.0
        return level / 255

    @staticmethod
    def _spin(rumble, l2, r2, tele) -> float:
        if r2 < PEDAL or l2 >= PEDAL:
            return 0.0
        if tele is not None and tele.fresh:
            # Hinterraeder - Durchdrehen beim Anfahren zaehlt ausdruecklich.
            return _slip_level(max(abs(s) for s in tele.slip[2:]))
        level = max(rumble)
        return level / 255 if level >= LIVE_THRESHOLD else 0.0


def build(p: dict) -> Setup:
    """Trigger-Effekte aus einem Profil (siehe settings.PROFILE_DEFAULTS).

    Racing: Bremse (L2) mit Druckpunkt ab `brake_start`, Gas (R2) nur
    leicht gedaempft, damit es sich fein dosieren laesst."""
    mode = p.get("triggers", "aus")
    if mode in ("racing", "racing_live"):
        brake = feedback(int(p["brake_start"]), int(p["brake_force"]))
        gas = (feedback(1, int(p["gas_force"])) if int(p["gas_force"]) > 0
               else off())
        return Setup(brake, gas, live=mode == "racing_live",
                     abs_strength=int(p["abs_strength"]),
                     abs_frequency=int(p["abs_frequency"]),
                     spin_strength=int(p["spin_strength"]))
    if mode == "shooter":
        return Setup(feedback(2, 3), weapon(4, 6, 6))
    return Setup(off(), off())
