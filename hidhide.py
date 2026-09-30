"""HidHide: den echten DualSense vor Spielen verstecken.

Spiele mit eigener DualSense-Unterstuetzung sehen sonst zwei Controller -
den echten und den virtuellen Xbox-Pad - und bekommen doppelte Eingaben.
HidHide (Nefarius) blendet den echten aus; nur freigegebene Programme
sehen ihn noch. Die Bruecke muss deshalb auf der Freigabeliste stehen,
sonst findet sie den Controller selbst nicht mehr.

Gesteuert wird ueber HidHideCLI.exe. Schreiben klappt normalerweise ohne
Admin-Rechte; falls nicht, wird mit UAC-Abfrage erneut versucht.
"""

from __future__ import annotations

import ctypes
import logging
import os
import re
import subprocess
from ctypes import wintypes
from pathlib import Path

from dualsense import find

log = logging.getLogger("dualsense.hidhide")
DOWNLOAD = "https://github.com/nefarius/HidHide/releases"
_NO_WINDOW = 0x08000000


def cli() -> str | None:
    for var in ("ProgramFiles", "ProgramW6432"):
        base = os.environ.get(var)
        if base:
            p = (Path(base) / "Nefarius Software Solutions" / "HidHide"
                 / "x64" / "HidHideCLI.exe")
            if p.exists():
                return str(p)
    return None


def current_exe() -> str:
    """Pfad des laufenden Programms, so wie Windows ihn sieht - nicht der
    Store-Alias von Python, den HidHide nicht kennt."""
    buf = ctypes.create_unicode_buffer(32768)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR,
                                       wintypes.DWORD]
    k32.GetModuleFileNameW(None, buf, len(buf))
    return buf.value


def _run(*args: str) -> tuple[int, str]:
    exe = cli()
    if exe is None:
        return -1, "HidHide nicht installiert"
    try:
        # stdin zu: sonst wartet HidHideCLI unter Umstaenden auf Eingaben.
        p = subprocess.run([exe, *args], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=10,
                           creationflags=_NO_WINDOW)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)


def _quoted(text: str, option: str) -> list[str]:
    return re.findall(rf'{option}\s+"([^"]+)"', text)


def instance_from_hidpath(path: bytes | str) -> str | None:
    r"""hidapi-Pfad -> Geraeteinstanz, wie HidHide sie erwartet:
    \\?\HID#VID_054C&PID_0CE6&MI_03#8&17336b02&0&0000#{...}
      -> HID\VID_054C&PID_0CE6&MI_03\8&17336B02&0&0000"""
    if isinstance(path, bytes):
        path = path.decode(errors="replace")
    m = re.match(r"^\\\\\?\\(.+?)#(.+?)#(.+?)#\{", path)
    if not m:
        return None
    return "\\".join(m.groups()).upper()


def status() -> dict:
    exe = cli()
    if exe is None:
        return {"installed": False, "download": DOWNLOAD}
    _, cloak = _run("--cloak-state")
    _, apps_txt = _run("--app-list")
    _, devs_txt = _run("--dev-list")
    apps = _quoted(apps_txt, "--app-reg")
    devs = _quoted(devs_txt, "--dev-hide")
    me = current_exe()
    return {
        "installed": True,
        "cloak": "--cloak-on" in cloak,
        "app": me,
        "app_registered": any(a.lower() == me.lower() for a in apps),
        "dualsense_hidden": any("054C" in d.upper() for d in devs),
        "hidden_devices": [d for d in devs if "054C" in d.upper()],
    }


def _elevated(args: list[str]) -> bool:
    """Nochmal mit UAC-Abfrage - nur wenn es ohne Rechte nicht ging."""
    exe = cli()
    params = subprocess.list2cmdline(args)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params,
                                             None, 0)
    return rc > 32


def registered(path: str) -> bool:
    _, apps = _run("--app-list")
    return any(a.lower() == path.lower() for a in _quoted(apps, "--app-reg"))


def register(path: str) -> bool:
    """Ein Programm freigeben, damit es den versteckten Controller sieht."""
    rc, out = _run("--app-reg", path)
    # Erst nachsehen, ob es trotz Fehlercode geklappt hat - nur wenn nicht,
    # mit UAC-Abfrage erneut versuchen.
    if rc != 0 and not registered(path):
        log.warning("HidHide-Freigabe ohne Rechte abgelehnt: %s", out.strip())
        return _elevated(["--app-reg", path])
    log.info("HidHide-Freigabe: %s", path)
    return True


def setup() -> dict:
    """Dieses Programm freigeben, verbundene DualSense verstecken, Schutz an."""
    args = ["--app-reg", current_exe()]
    for dev in find():
        inst = instance_from_hidpath(dev["path"])
        if inst:
            args += ["--dev-hide", inst]
    args.append("--cloak-on")
    rc, out = _run(*args)
    if rc != 0 and not registered(current_exe()):
        log.warning("HidHide ohne Rechte abgelehnt (%s): %s", rc, out.strip())
        if not _elevated(args):
            return {"error": "HidHide-Einrichtung abgebrochen."}
    log.info("HidHide eingerichtet: %s", " ".join(args))
    return status()


def set_cloak(on: bool) -> dict:
    rc, out = _run("--cloak-on" if on else "--cloak-off")
    if rc != 0 and not _elevated(["--cloak-on" if on else "--cloak-off"]):
        return {"error": "HidHide hat die Aenderung abgelehnt."}
    log.info("HidHide-Schutz %s", "an" if on else "aus")
    return status()
