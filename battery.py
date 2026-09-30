"""Batterieanzeige fuer den DualSense als Tray-Icon.

Laeuft unabhaengig von bridge.py - der Controller laesst sich parallel
oeffnen. Ohne Argumente landet das Symbol neben der Uhr.
"""

from __future__ import annotations

import argparse
import threading
import time

from PIL import Image, ImageDraw

from dualsense import DualSense

# Schwellen fuer die Farbgebung.
LEVEL_LOW = 20
LEVEL_MID = 50

GREEN = (64, 200, 96)
AMBER = (240, 176, 48)
RED = (232, 72, 72)
BLUE = (72, 160, 255)
GREY = (140, 140, 140)

POLL_SECONDS = 5.0
READ_WINDOW = 0.35


def windows_light_taskbar() -> bool:
    """Helle Taskleiste? Bestimmt, in welcher Farbe der Umriss sichtbar ist."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        return bool(value)
    except OSError:
        return False


class Status:
    def __init__(self):
        self.percent: int | None = None
        self.charging = False
        self.full = False
        self.link = "?"
        self.online = False

    def text(self) -> str:
        if not self.online:
            return "DualSense - nicht verbunden"
        state = "voll" if self.full else "laedt" if self.charging else "Akku"
        return f"DualSense - {self.percent}% ({state}, {self.link})"


def fill_color(st: Status) -> tuple[int, int, int]:
    if not st.online or st.percent is None:
        return GREY
    if st.charging or st.full:
        return BLUE
    if st.percent < LEVEL_LOW:
        return RED
    if st.percent < LEVEL_MID:
        return AMBER
    return GREEN


def make_icon(st: Status, size: int = 64, light: bool = False) -> Image.Image:
    """Tray-Symbol: das DS-Monogramm, der Unterstrich zeigt den Akku."""
    import logo

    return logo.tray_icon(st.percent, st.online, st.charging, st.full,
                          light=light, size=size)


def _battery_icon(st: Status, size: int = 64, light: bool = False) -> Image.Image:
    """Frueheres Akkusymbol, bleibt als Rueckfall."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    outline = (30, 30, 30, 255) if light else (240, 240, 240, 255)

    s = size / 64.0
    x0, y0, x1, y1 = 6 * s, 20 * s, 52 * s, 44 * s
    r = 4 * s
    w = max(1, int(3 * s))

    # Gehaeuse und Pluspol
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=outline, width=w)
    d.rounded_rectangle(
        [x1 + 2 * s, y0 + 7 * s, x1 + 8 * s, y1 - 7 * s],
        radius=2 * s, fill=outline,
    )

    # Fuellstand
    pad = w + 2 * s
    inner_w = (x1 - x0) - 2 * pad
    pct = 0 if st.percent is None else max(0, min(100, st.percent))
    if st.online and pct > 0:
        fw = max(2 * s, inner_w * pct / 100.0)
        d.rounded_rectangle(
            [x0 + pad, y0 + pad, x0 + pad + fw, y1 - pad],
            radius=2 * s, fill=fill_color(st),
        )

    if not st.online:
        # Durchgestrichen, wenn kein Controller da ist.
        d.line([x0 + 4 * s, y1 - 4 * s, x1 - 4 * s, y0 + 4 * s],
               fill=RED, width=max(1, int(4 * s)))
    elif st.charging or st.full:
        bolt = [
            (34 * s, 16 * s), (22 * s, 34 * s), (30 * s, 34 * s),
            (26 * s, 50 * s), (40 * s, 30 * s), (32 * s, 30 * s),
        ]
        d.polygon(bolt, fill=(255, 235, 120, 255), outline=outline)
    return img


def read_status(dev: DualSense, window: float = READ_WINDOW) -> Status | None:
    """Sammelt kurz Reports; der letzte traegt den aktuellen Ladezustand."""
    last = None
    end = time.time() + window
    while time.time() < end:
        st = dev.poll()
        if st:
            last = st
        time.sleep(0.002)
    if last is None:
        return None
    out = Status()
    out.percent = last.battery_percent
    out.charging = last.charging
    out.full = last.battery_full
    out.link = "Bluetooth" if dev.bluetooth else "USB"
    out.online = True
    return out


class Tray:
    def __init__(self):
        import pystray

        self.pystray = pystray
        self.status = Status()
        self.light = windows_light_taskbar()
        self.dev: DualSense | None = None
        self.icon = pystray.Icon(
            "dualsense_battery",
            make_icon(self.status, light=self.light),
            self.status.text(),
            menu=pystray.Menu(
                pystray.MenuItem(lambda _: self.status.text(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Jetzt aktualisieren", self._refresh_now),
                pystray.MenuItem("Beenden", self._quit),
            ),
        )
        self._wake = threading.Event()
        self._stop = threading.Event()

    def _refresh_now(self, *_):
        self._wake.set()

    def _quit(self, *_):
        self._stop.set()
        self._wake.set()
        self.icon.stop()

    def _connect(self) -> None:
        if self.dev is not None:
            return
        try:
            self.dev = DualSense()
            self.dev.enable_full_bt()
        except Exception:
            self.dev = None

    def _tick(self) -> None:
        self._connect()
        new = None
        if self.dev is not None:
            try:
                new = read_status(self.dev)
            except OSError:
                new = None
            if new is None:
                # Verbindung weg - Handle schliessen und neu versuchen.
                try:
                    self.dev.close()
                except Exception:
                    pass
                self.dev = None
        self.status = new or Status()
        self.icon.icon = make_icon(self.status, light=self.light)
        self.icon.title = self.status.text()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._tick()
            self._wake.wait(POLL_SECONDS)
            self._wake.clear()

    def run(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()
        self.icon.run()


def print_once() -> int:
    try:
        dev = DualSense()
    except RuntimeError as e:
        print(f"{e}")
        return 1
    dev.enable_full_bt()
    st = read_status(dev, window=0.6)
    dev.close()
    if st is None:
        print("Keine Reports empfangen.")
        return 1
    filled = st.percent // 10
    bar = "#" * filled + "." * (10 - filled)
    state = "voll" if st.full else "laedt" if st.charging else "entlaedt"
    print(f"DualSense [{bar}] {st.percent:3d}%  {state}  ueber {st.link}")
    return 0


def save_preview(path: str) -> None:
    """Kontaktbogen aller Zustaende, hell und dunkel - zum Draufschauen."""
    cases = []
    for pct, chg, full, on in [
        (100, False, False, True), (85, False, False, True),
        (45, False, False, True), (15, False, False, True),
        (5, True, False, True), (70, True, False, True),
        (100, False, True, True), (0, False, False, False),
    ]:
        s = Status()
        s.percent, s.charging, s.full, s.online = pct, chg, full, on
        s.link = "USB"
        cases.append(s)

    cell = 72
    sheet = Image.new("RGB", (cell * len(cases), cell * 2), (255, 255, 255))
    rows = [(False, (32, 32, 32)), (True, (243, 243, 243))]
    for i, s in enumerate(cases):
        for row, (light, bg) in enumerate(rows):
            tile = Image.new("RGB", (cell, cell), bg)
            ic = make_icon(s, size=64, light=light)
            tile.paste(ic, (4, 4), ic)
            sheet.paste(tile, (i * cell, row * cell))
    sheet.save(path)
    print(f"Vorschau gespeichert: {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="DualSense-Batterieanzeige")
    ap.add_argument("--once", action="store_true",
                    help="einmal im Terminal ausgeben statt Tray-Icon")
    ap.add_argument("--preview", metavar="PFAD",
                    help="Symbolvarianten als PNG speichern")
    a = ap.parse_args()

    if a.once:
        return print_once()
    if a.preview:
        save_preview(a.preview)
        return 0

    try:
        Tray().run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
