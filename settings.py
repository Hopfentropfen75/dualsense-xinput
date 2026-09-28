"""Einstellungen und Profile, die Tray, Bruecke und Anzeigefenster teilen.

Liegen als settings.json neben dem Code. Die Bruecke schaut auf die
Aenderungszeit - so wirkt eine Aenderung im Anzeigefenster sofort, obwohl
das ein eigener Prozess ist.

Ein Profil buendelt alles, was sich pro Spiel unterscheiden soll: Trigger,
Deadzones, Kurven, Rumble. Laeuft ein Spiel aus der `games`-Liste eines
Profils, schaltet die Bruecke automatisch darauf um.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

PATH = Path(__file__).with_name("settings.json")
# Laufzeitstatus der Bruecke fuers Anzeigefenster (Profil, Telemetrie).
STATUS_PATH = Path(__file__).with_name("status.json")
TELEMETRY_PORT = 5300

PROFILE_DEFAULTS: dict = {
    "triggers": "aus",          # Modus aus triggers.MODES
    "brake_start": 3,           # L2: Druckpunkt, Zone 0..8
    "brake_force": 6,           # L2: Staerke 1..8
    "gas_force": 2,             # R2: Staerke 0..8 (0 = kein Widerstand)
    "abs_strength": 6,          # L2 pulsiert bei blockierenden Raedern, 0..8
    "abs_frequency": 20,        # Hz
    "spin_strength": 4,         # R2 vibriert bei durchdrehenden Raedern, 0..8
    "stick_deadzone": 0.08,
    "stick_outer": 0.03,
    "anti_deadzone": 0.0,
    "l2_deadzone": 0.0,         # Leerweg 0..1
    "r2_deadzone": 0.0,
    "l2_curve": 1.0,            # 1 = linear, >1 = feiner am Anfang
    "r2_curve": 1.0,
    "rumble_gain": 1.0,
    "gyro": "aus",              # aus | l2 (beim Zielen) | immer
    "gyro_sensitivity": 1.0,
    "gyro_min": 0.15,           # Mindestausschlag gegen die Deadzone des Spiels
    "gyro_invert_x": False,
    "gyro_invert_y": False,
    "games": [],                # Teile von Exe-Namen, z. B. "forzahorizon"
}

DEFAULT_PROFILES: dict[str, dict] = {
    "Standard": {},
    "Forza": {
        "triggers": "racing_live",
        "stick_deadzone": 0.06,
        "r2_deadzone": 0.03,
        "games": ["forzahorizon", "forzamotorsport"],
    },
    "Shooter": {"triggers": "shooter", "gyro": "l2"},
}


def _migrate_profile(p: dict) -> dict:
    """Frueher galten Leerweg und Kurve fuer beide Trigger gemeinsam."""
    p = dict(p or {})
    for old, new in (("trigger_deadzone", "deadzone"),
                     ("trigger_curve", "curve")):
        if old in p:
            v = p.pop(old)
            p.setdefault(f"l2_{new}", v)
            p.setdefault(f"r2_{new}", v)
    return p


def _normalize(data: dict) -> dict:
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        profiles = copy.deepcopy(DEFAULT_PROFILES)
    profiles = {name: {**PROFILE_DEFAULTS, **_migrate_profile(p)}
                for name, p in profiles.items()}

    active = data.get("active")
    if active not in profiles:
        # Altformat hatte nur ein Trigger-Profil.
        old = str(data.get("trigger_profile", ""))
        guess = {"racing": "Forza", "racing_live": "Forza",
                 "shooter": "Shooter"}.get(old, "Standard")
        active = guess if guess in profiles else next(iter(profiles))
    return {
        "active": active,
        "auto_game": bool(data.get("auto_game", True)),
        "telemetry_port": int(data.get("telemetry_port", TELEMETRY_PORT)),
        "profiles": profiles,
    }


def load() -> dict:
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return _normalize(data if isinstance(data, dict) else {})


def save(data: dict) -> None:
    data = _normalize(data)
    # Erst in eine Nebendatei, dann umbenennen: die Bruecke liest nie
    # eine halb geschriebene Datei.
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, PATH)


def update(**changes) -> dict:
    data = load()
    data.update(changes)
    save(data)
    return data


def update_profile(name: str, **changes) -> dict:
    data = load()
    if name in data["profiles"]:
        data["profiles"][name].update(changes)
        save(data)
    return data


def effective(data: dict, game_profile: str | None) -> str:
    """Welches Profil gilt: das eines laufenden Spiels, sonst das gewaehlte."""
    if data["auto_game"] and game_profile in data["profiles"]:
        return game_profile
    return data["active"]


def write_status(status: dict) -> None:
    try:
        tmp = STATUS_PATH.with_suffix(".stmp")
        tmp.write_text(json.dumps(status), encoding="utf-8")
        os.replace(tmp, STATUS_PATH)
    except OSError:
        pass


def read_status() -> dict:
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def mtime() -> float:
    try:
        return PATH.stat().st_mtime
    except OSError:
        return 0.0
