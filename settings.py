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

PROFILE_DEFAULTS: dict = {
    "triggers": "aus",          # Modus aus triggers.MODES
    "brake_start": 3,           # L2: Druckpunkt, Zone 0..8
    "brake_force": 6,           # L2: Staerke 1..8
    "gas_force": 2,             # R2: Staerke 0..8 (0 = kein Widerstand)
    "stick_deadzone": 0.08,
    "stick_outer": 0.03,
    "anti_deadzone": 0.0,
    "trigger_deadzone": 0.0,
    "trigger_curve": 1.0,
    "rumble_gain": 1.0,
    "games": [],                # Teile von Exe-Namen, z. B. "forzahorizon"
}

DEFAULT_PROFILES: dict[str, dict] = {
    "Standard": {},
    "Forza": {
        "triggers": "racing",
        "stick_deadzone": 0.06,
        "trigger_deadzone": 0.03,
        "games": ["forzahorizon", "forzamotorsport"],
    },
    "Shooter": {"triggers": "shooter"},
}


def _normalize(data: dict) -> dict:
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        profiles = copy.deepcopy(DEFAULT_PROFILES)
    profiles = {name: {**PROFILE_DEFAULTS, **(p or {})}
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


def mtime() -> float:
    try:
        return PATH.stat().st_mtime
    except OSError:
        return 0.0
