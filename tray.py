"""Alles in einem: Bruecke und Batterieanzeige als Tray-Icon.

Ein einziger Prozess oeffnet den Controller, uebersetzt ihn nach XInput
und zeigt nebenbei den Akkustand neben der Uhr. Beenden ueber das Menue.
"""

from __future__ import annotations

import threading
import time

import pystray

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

        self._stop = threading.Event()
        self._wake = threading.Event()

        self.icon = pystray.Icon(
            "dualsense_bridge",
            make_icon(self.status, light=self.light),
            "DualSense - startet ...",
            menu=pystray.Menu(
                pystray.MenuItem(lambda _: self._title(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Neu kalibrieren", self._recalibrate),
                pystray.MenuItem("Beenden", self._quit),
            ),
        )

    def _title(self) -> str:
        if self.error:
            return f"DualSense - {self.error}"
        if not self.status.online:
            return "DualSense - nicht verbunden"
        slot = self.bridge.slot if self.bridge else None
        where = f"XInput-Slot {slot}" if slot is not None else "aktiv"
        return f"{self.status.text()} - {where}"

    def _quit(self, *_):
        self._stop.set()
        self._wake.set()
        self.icon.stop()

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

    def run(self) -> None:
        threading.Thread(target=self._run_bridge, daemon=True).start()
        threading.Thread(target=self._run_ui, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    App().run()
