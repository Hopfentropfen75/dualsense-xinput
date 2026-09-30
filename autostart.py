"""Autostart mit Windows ueber den Run-Schluessel des Benutzers.

Kein Admin noetig, kein Dienst: Windows startet beim Anmelden die Bruecke
ohne Fenster (--hidden); das Cockpit oeffnet man bei Bedarf.
"""

from __future__ import annotations

import subprocess
import sys
import winreg
from pathlib import Path

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "DualSenseCockpit"


def command() -> str:
    if getattr(sys, "frozen", False):               # als .exe gebaut
        return subprocess.list2cmdline([sys.executable, "--hidden"])
    pyw = Path(sys.executable).with_name("pythonw.exe")
    tray = Path(__file__).with_name("tray.py")
    return subprocess.list2cmdline([str(pyw if pyw.exists() else
                                        sys.executable), str(tray),
                                    "--hidden"])


def enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> bool:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0,
                        winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass
    return enabled()
