"""Baut DualSense.exe - laeuft ohne installiertes Python.

    python -m pip install pyinstaller
    python build.py              # baut nach dist/
    python build.py --install    # ... und installiert fuer diesen Benutzer

Ergebnis: dist/DualSense/DualSense.exe (Ordner mit allem Noetigen). Der
Ordner laesst sich beliebig verschieben; Einstellungen und Logs liegen
unter %LOCALAPPDATA%\\DualSenseCockpit. Auf dem Zielrechner braucht es nur
den ViGEmBus-Treiber (und, falls gewuenscht, HidHide).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
TARGET = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "DualSense"


def _stop_running() -> None:
    """Laufende DualSense.exe beenden - sonst sind ihre Dateien gesperrt."""
    subprocess.call(["taskkill", "/IM", "DualSense.exe", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def main() -> int:
    _stop_running()
    sep = ";"                      # PyInstaller-Trenner fuer --add-data unter Windows
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--windowed",                          # kein Konsolenfenster
        "--name", "DualSense",
        "--icon", str(HERE / "dualsense.ico"),
        "--add-data", f"{HERE / 'ui'}{sep}ui",
        "--add-data", f"{HERE / 'assets'}{sep}assets",
        "--add-data", f"{HERE / 'dualsense.ico'}{sep}.",
        # ViGEmClient.dll liegt im Paket und wird zur Laufzeit per Pfad geladen.
        "--collect-all", "vgamepad",
        "--hidden-import", "pystray._win32",
        str(HERE / "tray.py"),
    ]
    rc = subprocess.call(args, cwd=HERE)
    if rc == 0 and "--install" in sys.argv:
        rc = install()
    return rc


def install() -> int:
    r"""Nach %LOCALAPPDATA%\Programs\DualSense kopieren und in HidHide
    freigeben - sonst saehe die .exe den versteckten Controller nicht."""
    _stop_running()
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(HERE / "dist" / "DualSense", TARGET)
    exe = TARGET / "DualSense.exe"
    print(f"installiert: {exe}")
    sys.path.insert(0, str(HERE))
    import hidhide
    if hidhide.cli() and hidhide.register(str(exe)):
        print("in HidHide freigegeben")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
