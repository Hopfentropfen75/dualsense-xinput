"""Einstellungen, die Tray, Bruecke und Anzeigefenster teilen.

Liegen als settings.json neben dem Code. Die Bruecke schaut auf die
Aenderungszeit - so wirkt eine Auswahl im Anzeigefenster sofort, obwohl
das ein eigener Prozess ist.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PATH = Path(__file__).with_name("settings.json")
DEFAULTS = {"trigger_profile": "aus"}


def load() -> dict:
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **data}


def save(**changes) -> None:
    data = {**load(), **changes}
    # Erst in eine Nebendatei, dann umbenennen: die Bruecke liest nie
    # eine halb geschriebene Datei.
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, PATH)


def mtime() -> float:
    try:
        return PATH.stat().st_mtime
    except OSError:
        return 0.0
