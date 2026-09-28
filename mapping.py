"""Uebersetzt einen DualSense-Zustand in einen XInput-Zustand.

Diese Schicht ist bewusst treiberfrei: sie rechnet nur um. Erst der
Backend-Teil (ViGEmBus) macht daraus ein Geraet, das Windows sieht.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from dualsense import State

# DualSense-Taste -> XInput-Taste. Das ist der Teil, den man umkonfiguriert.
DEFAULT_BUTTON_MAP: dict[str, str] = {
    "cross": "a",
    "circle": "b",
    "square": "x",
    "triangle": "y",
    "l1": "lb",
    "r1": "rb",
    "l3": "l3",
    "r3": "r3",
    "create": "back",
    "options": "start",
    "ps": "guide",
    # Touchpad-Klick hat kein Xbox-Gegenstueck; per Default ungenutzt.
    "touchpad": "",
}

DPAD_BITS: dict[str, tuple[str, ...]] = {
    "N": ("dpad_up",),
    "NE": ("dpad_up", "dpad_right"),
    "E": ("dpad_right",),
    "SE": ("dpad_down", "dpad_right"),
    "S": ("dpad_down",),
    "SW": ("dpad_down", "dpad_left"),
    "W": ("dpad_left",),
    "NW": ("dpad_up", "dpad_left"),
    "none": (),
}

XINPUT_MASKS = {
    "dpad_up": 0x0001, "dpad_down": 0x0002, "dpad_left": 0x0004,
    "dpad_right": 0x0008, "start": 0x0010, "back": 0x0020,
    "l3": 0x0040, "r3": 0x0080, "lb": 0x0100, "rb": 0x0200,
    "guide": 0x0400, "a": 0x1000, "b": 0x2000, "x": 0x4000, "y": 0x8000,
}


@dataclass
class Config:
    # Radiale Deadzone in Stick-Einheiten (0..1), gegen Drift.
    left_deadzone: float = 0.08
    right_deadzone: float = 0.08
    # Aeussere Zone: ab (1 - outer) gilt der Stick als voll ausgelenkt.
    # Faengt Sticks ab, die den Rand nicht ganz erreichen.
    outer_deadzone: float = 0.0
    # Direkt hinter der Deadzone auf diesen Wert springen - gleicht die
    # Deadzone aus, die das Spiel selbst noch einmal abzieht.
    anti_deadzone: float = 0.0
    # Trigger: Leerweg (0..1) und Kurve (1 = linear, >1 = feiner am Anfang).
    trigger_deadzone: float = 0.0
    trigger_curve: float = 1.0
    # Ab welchem Rohwert ein Analogtrigger als Klick zaehlt.
    trigger_threshold: int = 30
    # Stick-Mittelpunkte; per calibrate() aus der Ruhelage bestimmt.
    center: dict[str, int] = field(
        default_factory=lambda: {"lx": 128, "ly": 128, "rx": 128, "ry": 128}
    )
    button_map: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_BUTTON_MAP)
    )
    invert_y: bool = True


@dataclass
class XPad:
    """Zielzustand im XInput-Format."""

    buttons: int = 0
    lt: int = 0
    rt: int = 0
    lx: int = 0
    ly: int = 0
    rx: int = 0
    ry: int = 0

    def names(self) -> set[str]:
        return {n for n, m in XINPUT_MASKS.items() if self.buttons & m}


def _axis(raw: int, center: int) -> float:
    """Rohwert 0..255 -> -1.0..1.0, um den gemessenen Mittelpunkt herum."""
    if raw >= center:
        span = 255 - center
        return (raw - center) / span if span else 0.0
    return (raw - center) / center if center else 0.0


def _apply_deadzone(x: float, y: float, dz: float, outer: float = 0.0,
                    anti: float = 0.0) -> tuple[float, float]:
    """Radiale Deadzone: skaliert den Rest auf den vollen Bereich, damit
    knapp ausserhalb der Zone kein Sprung entsteht."""
    mag = math.hypot(x, y)
    if mag <= dz or mag == 0.0:
        return 0.0, 0.0
    span = max(1.0 - dz - outer, 1e-6)
    scaled = min((mag - dz) / span, 1.0)
    if anti > 0.0:
        scaled = anti + (1.0 - anti) * scaled
    return x / mag * scaled, y / mag * scaled


def _trigger(raw: int, dz: float, curve: float) -> int:
    if dz <= 0.0 and curve == 1.0:
        return raw
    v = raw / 255.0
    if v <= dz:
        return 0
    v = (v - dz) / (1.0 - dz)
    return min(255, round(255 * v ** curve))


def _to_i16(v: float) -> int:
    return max(-32768, min(32767, int(round(v * 32767))))


def map_state(st: State, cfg: Config | None = None) -> XPad:
    cfg = cfg or Config()
    out = XPad()

    lx, ly = _apply_deadzone(
        _axis(st.lx, cfg.center["lx"]),
        _axis(st.ly, cfg.center["ly"]),
        cfg.left_deadzone, cfg.outer_deadzone, cfg.anti_deadzone,
    )
    rx, ry = _apply_deadzone(
        _axis(st.rx, cfg.center["rx"]),
        _axis(st.ry, cfg.center["ry"]),
        cfg.right_deadzone, cfg.outer_deadzone, cfg.anti_deadzone,
    )

    # DualSense zaehlt Y nach unten, XInput nach oben.
    if cfg.invert_y:
        ly, ry = -ly, -ry

    out.lx, out.ly = _to_i16(lx), _to_i16(ly)
    out.rx, out.ry = _to_i16(rx), _to_i16(ry)
    out.lt = _trigger(st.l2, cfg.trigger_deadzone, cfg.trigger_curve)
    out.rt = _trigger(st.r2, cfg.trigger_deadzone, cfg.trigger_curve)

    mask = 0
    for name in st.buttons:
        target = cfg.button_map.get(name, "")
        if target:
            mask |= XINPUT_MASKS.get(target, 0)
    for bit in DPAD_BITS.get(st.dpad, ()):
        mask |= XINPUT_MASKS[bit]
    out.buttons = mask
    return out


def calibrate(samples: list[State]) -> dict[str, int]:
    """Mittelt die Ruhelage - der Controller soll dabei unberuehrt liegen."""
    if not samples:
        return {"lx": 128, "ly": 128, "rx": 128, "ry": 128}
    n = len(samples)
    return {
        "lx": round(sum(s.lx for s in samples) / n),
        "ly": round(sum(s.ly for s in samples) / n),
        "rx": round(sum(s.rx for s in samples) / n),
        "ry": round(sum(s.ry for s in samples) / n),
    }
