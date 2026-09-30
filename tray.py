"""Alles in einem: Bruecke, Tray-Icon und Cockpit.

Ein einziger Prozess oeffnet den Controller, uebersetzt ihn nach XInput,
zeigt den Akkustand neben der Uhr und stellt das Cockpit-Fenster bereit
(webui.py). Beenden ueber das Menue.
"""

from __future__ import annotations

import sys
import threading
import time

import pystray

import settings
import webui
from battery import Status, make_icon, windows_light_taskbar
from bridge import Bridge
from mapping import Config

REFRESH_SECONDS = 5.0


class App:
    def __init__(self, deadzone: float = 0.08):
        self.cfg = Config(left_deadzone=deadzone, right_deadzone=deadzone)
        self.light = windows_light_taskbar()
        self.status = Status()
        self.bridge: Bridge | None = None
        self.error: str | None = None
        self.cockpit: webui.Cockpit | None = None

        self._stop = threading.Event()
        self._wake = threading.Event()

        self.icon = pystray.Icon(
            "dualsense_bridge",
            make_icon(self.status, light=self.light),
            "DualSense - startet ...",
            menu=pystray.Menu(
                pystray.MenuItem(lambda _: self._title(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Cockpit oeffnen", self._open_cockpit,
                                 default=True),
                pystray.MenuItem("Profil", pystray.Menu(self._profile_items)),
                pystray.MenuItem("Neu kalibrieren", self._recalibrate),
                pystray.MenuItem("Beenden", self._quit),
            ),
        )

    def _title(self) -> str:
        if self.error:
            return f"DualSense - {self.error}"
        if not self.status.online:
            return "DualSense - nicht verbunden"
        b = self.bridge
        slot = b.slot if b else None
        where = f"Slot {slot + 1}" if slot is not None else "aktiv"
        prof = f" - {b.profile_name}" if b else ""
        return f"{self.status.text()} - {where}{prof}"

    def _quit(self, *_):
        self._stop.set()
        self._wake.set()
        if self.cockpit:
            self.cockpit.close()
        self.icon.stop()

    def _open_cockpit(self, *_):
        if self.cockpit:
            self.cockpit.open()

    @staticmethod
    def _profile_items():
        """Dynamisch, damit im Fenster angelegte Profile auftauchen. Die
        Bruecke merkt die geaenderte settings.json und schaltet um."""
        def item(name):
            return pystray.MenuItem(
                name,
                lambda *_: settings.update(active=name),
                checked=lambda _: settings.load()["active"] == name,
                radio=True)
        yield from (item(n) for n in settings.load()["profiles"])
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem(
            "Automatisch pro Spiel",
            lambda *_: settings.update(
                auto_game=not settings.load()["auto_game"]),
            checked=lambda _: settings.load()["auto_game"])

    def _recalibrate(self, *_):
        # Die Bruecke laeuft weiter; nur die Mittelpunkte werden neu gemessen.
        if self.bridge is not None:
            self.bridge.recalibrate_requested = True

    def _run_bridge(self) -> None:
        """Haelt die Bruecke am Leben und startet sie nach Verlust neu."""
        while not self._stop.is_set():
            try:
                self.bridge = Bridge(self.cfg, quiet=True)
                self.error = None
                self.bridge.run(stop=self._stop)
            except RuntimeError as e:
                self.error = str(e).split(".")[0]
                self.bridge = None
            except OSError:
                self.error = "Verbindung verloren"
                self.bridge = None
            # Vor dem naechsten Versuch aufraeumen, sonst sammeln sich
            # virtuelle Pads an.
            if self.bridge is not None:
                try:
                    self.bridge.close()
                except Exception:
                    pass
                self.bridge = None
            if self._stop.is_set():
                break
            # Controller weg oder aus - in Ruhe auf Rueckkehr warten.
            self.status = Status()
            self._wake.set()
            time.sleep(3.0)

    def _run_ui(self) -> None:
        while not self._stop.is_set():
            b = self.bridge
            st = Status()
            if b is not None and b.ds is not None:
                s = b.ds.state
                if s.battery_percent is not None:
                    st.percent = s.battery_percent
                    st.charging = s.charging
                    st.full = s.battery_full
                    st.link = "Bluetooth" if b.ds.bluetooth else "USB"
                    st.online = True
            self.status = st
            self.icon.icon = make_icon(st, light=self.light)
            self.icon.title = self._title()
            self._wake.wait(REFRESH_SECONDS)
            self._wake.clear()

    def run(self, show: bool = True) -> None:
        self.cockpit = webui.Cockpit(self)
        if show:
            self.cockpit.open()
        threading.Thread(target=self._run_bridge, daemon=True).start()
        threading.Thread(target=self._run_ui, daemon=True).start()
        self.icon.run(setup=self._on_ready)

    def _on_ready(self, icon) -> None:
        # Mit eigenem setup() macht pystray das Icon nicht selbst sichtbar.
        icon.visible = True
        try:
            icon.notify("Laeuft auch mit geschlossenem Fenster weiter - "
                        "Symbol neben der Uhr.", "DualSense")
        except Exception:
            pass


def _already_running() -> bool:
    """Ein zweiter Start wuerde einen zweiten virtuellen Pad anlegen - das
    Spiel saehe dann wieder zwei Controller. Ein benannter Mutex verhindert
    das; der Handle bleibt bis Prozessende offen."""
    import ctypes

    k32 = ctypes.windll.kernel32
    global _mutex
    _mutex = k32.CreateMutexW(None, False, "Local\\dualsense_xinput_tray")
    return k32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    # Ein Symbol fuer alles: startet die Bruecke und zeigt das Cockpit.
    # Laeuft sie schon, wird nur das Cockpit geoeffnet - nie ein zweiter
    # virtueller Pad. --hidden startet ohne Fenster (z. B. fuer Autostart).
    if _already_running():
        webui.open_running()
        raise SystemExit(0)
    App().run(show="--hidden" not in sys.argv)
