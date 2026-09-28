"""Anzeigefenster: Verbindungsstatus und Live-Eingaben als Schema.

Zeigt, was ein Spiel tatsaechlich sieht - gelesen wird der virtuelle
Xbox-Pad ueber XInput, nicht der DualSense direkt. Leuchtet hier etwas,
funktioniert die ganze Kette Controller -> Bruecke -> Pad.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import settings
import triggers
import xinput_ref as xr
from battery import read_status
from dualsense import DualSense, find, is_usb

MUTEX_NAME = "Local\\dualsense_xinput_tray"
FRAME_MS = 16

BG = "#16181d"
PANEL = "#20232a"
BODY = "#2b2f38"
EDGE = "#3a3f4b"
TEXT = "#e6e6e6"
DIM = "#7c8290"
OFF = "#454a56"
ON = "#3d7bff"
OK = "#40c860"
WARN = "#f0b030"
BAD = "#e84848"

FACE = {  # Xbox-Taste -> (Farbe, PlayStation-Gegenstueck)
    "a": ("#40c860", "✕"),
    "b": ("#e84848", "○"),
    "x": ("#3d7bff", "□"),
    "y": ("#f0b030", "△"),
}


def bridge_running() -> bool:
    k32 = ctypes.windll.kernel32
    h = k32.OpenMutexW(0x00100000, False, MUTEX_NAME)  # SYNCHRONIZE
    if h:
        k32.CloseHandle(h)
        return True
    return False


class BatteryWatcher:
    """Liest den Akku im Hintergrund; der Controller laesst sich parallel
    zur Bruecke oeffnen."""

    def __init__(self):
        self.text = "-"
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        dev = None
        while not self._stop.is_set():
            try:
                if dev is None:
                    dev = DualSense()
                    dev.enable_full_bt()
                st = read_status(dev)
            except Exception:
                st = None
            if st is None or st.percent is None:
                self.text = "-"
                if dev is not None:
                    try:
                        dev.close()
                    except Exception:
                        pass
                    dev = None
            else:
                extra = " voll" if st.full else " laedt" if st.charging else ""
                self.text = f"{st.percent}%{extra}"
            self._stop.wait(5.0)

    def stop(self) -> None:
        self._stop.set()


class Monitor:
    W, H = 560, 330

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DualSense - Anzeige")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        ico = Path(__file__).with_name("dualsense.ico")
        if ico.exists():
            try:
                self.root.iconbitmap(str(ico))
            except tk.TclError:
                pass

        self.battery = BatteryWatcher()
        self.slot: int | None = None
        self._last_scan = 0.0
        self._link = None
        self._running = False

        self._build_status()
        self.cv = tk.Canvas(self.root, width=self.W, height=self.H, bg=BG,
                            highlightthickness=0)
        self.cv.pack(padx=12, pady=(4, 4))
        self._build_profiles()
        self._draw_static()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # --- Statusleiste ---------------------------------------------------

    def _build_status(self) -> None:
        bar = tk.Frame(self.root, bg=PANEL)
        bar.pack(fill="x", padx=12, pady=(12, 4))
        self.lamps = {}
        for key, label in (("ds", "DualSense"), ("br", "Bruecke"),
                           ("xp", "Xbox-Pad")):
            f = tk.Frame(bar, bg=PANEL)
            f.pack(side="left", padx=10, pady=8)
            dot = tk.Canvas(f, width=12, height=12, bg=PANEL,
                            highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=OFF, outline="", tags="d")
            dot.pack(side="left")
            txt = tk.Label(f, text=label, bg=PANEL, fg=TEXT,
                           font=("Segoe UI", 10))
            txt.pack(side="left", padx=(6, 0))
            self.lamps[key] = (dot, txt, label)
        self.start_btn = tk.Button(
            bar, text="Bruecke starten", command=self._start_bridge,
            bg=ON, fg="white", activebackground="#2d62d8",
            activeforeground="white", relief="flat", padx=10,
            font=("Segoe UI", 9, "bold"))

    def _lamp(self, key: str, color: str, detail: str = "") -> None:
        dot, txt, label = self.lamps[key]
        dot.itemconfigure("d", fill=color)
        txt.configure(text=f"{label}: {detail}" if detail else label)

    def _start_bridge(self) -> None:
        exe = Path(sys.executable).with_name("pythonw.exe")
        tray = Path(__file__).with_name("tray.py")
        subprocess.Popen([str(exe if exe.exists() else sys.executable),
                          str(tray)], cwd=str(tray.parent))
        self.start_btn.configure(text="startet ...", state="disabled")

    def _scan(self) -> None:
        """Langsame Abfragen nur zweimal pro Sekunde."""
        devs = find()
        self._link = None if not devs else (
            "USB" if is_usb(devs[0]) else "Bluetooth")
        self._running = bridge_running()
        slots = xr.connected()
        if self.slot not in slots:
            self.slot = slots[0] if slots else None

        if self._link:
            self._lamp("ds", OK, f"{self._link}, Akku {self.battery.text}")
        else:
            self._lamp("ds", BAD, "nicht gefunden")
        self._lamp("br", OK if self._running else BAD,
                   "laeuft" if self._running else "aus")
        if self.slot is not None:
            self._lamp("xp", OK, f"Slot {self.slot + 1}")
        else:
            self._lamp("xp", WARN if self._running else BAD, "kein Pad")

        # Auch im Tray umschaltbar - Anzeige nachziehen.
        self._show_profile(settings.load()["trigger_profile"])

        if self._running:
            self.start_btn.pack_forget()
            self.start_btn.configure(text="Bruecke starten", state="normal")
        elif not self.start_btn.winfo_ismapped():
            self.start_btn.pack(side="right", padx=10)

    # --- Trigger-Profile ------------------------------------------------

    def _build_profiles(self) -> None:
        bar = tk.Frame(self.root, bg=PANEL)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(bar, text="Trigger L2/R2:", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 6), pady=8)
        self.profile_btns = {}
        for key, prof in triggers.PROFILES.items():
            b = tk.Button(bar, text=prof.name, relief="flat", padx=10,
                          font=("Segoe UI", 9), bd=0,
                          command=lambda k=key: self._set_profile(k))
            b.pack(side="left", padx=3, pady=8)
            self.profile_btns[key] = b
        self._show_profile(settings.load()["trigger_profile"])

    def _set_profile(self, key: str) -> None:
        settings.save(trigger_profile=key)
        self._show_profile(key)

    def _show_profile(self, current: str) -> None:
        for key, b in self.profile_btns.items():
            on = key == current
            b.configure(bg=ON if on else BODY, fg="white" if on else TEXT,
                        activebackground=ON, activeforeground="white")

    # --- Schema ---------------------------------------------------------

    def _draw_static(self) -> None:
        c = self.cv
        # Gehaeuse: Mittelteil plus zwei Griffe.
        c.create_oval(40, 110, 200, 320, fill=BODY, outline=EDGE, width=2)
        c.create_oval(360, 110, 520, 320, fill=BODY, outline=EDGE, width=2)
        c.create_rectangle(110, 70, 450, 250, fill=BODY, outline="")
        c.create_oval(60, 60, 220, 250, fill=BODY, outline="")
        c.create_oval(340, 60, 500, 250, fill=BODY, outline="")

        # Trigger als Balken, Schultertasten darunter.
        self.trig = {}
        for side, x0 in (("lt", 70), ("rt", 390)):
            c.create_rectangle(x0, 8, x0 + 100, 24, fill=PANEL, outline=EDGE)
            self.trig[side] = (c.create_rectangle(x0, 8, x0, 24, fill=ON,
                                                  outline=""), x0)
            c.create_text(x0 + 50, 16, text=side.upper(), fill=TEXT,
                          font=("Segoe UI", 8, "bold"))
        self.btn = {}
        self.btn["lb"] = c.create_rectangle(80, 34, 180, 50, fill=OFF,
                                            outline="")
        self.btn["rb"] = c.create_rectangle(380, 34, 480, 50, fill=OFF,
                                            outline="")
        c.create_text(130, 42, text="LB", fill=TEXT, font=("Segoe UI", 8))
        c.create_text(430, 42, text="RB", fill=TEXT, font=("Segoe UI", 8))

        # Sticks: Ring (leuchtet bei L3/R3) und beweglicher Punkt.
        self.stick = {}
        for name, cx, cy in (("l", 130, 140), ("r", 360, 225)):
            ring = c.create_oval(cx - 38, cy - 38, cx + 38, cy + 38,
                                 fill=PANEL, outline=EDGE, width=3)
            c.create_line(cx - 38, cy, cx + 38, cy, fill=EDGE)
            c.create_line(cx, cy - 38, cx, cy + 38, fill=EDGE)
            dot = c.create_oval(cx - 9, cy - 9, cx + 9, cy + 9, fill=ON,
                                outline="")
            val = c.create_text(cx, cy + 50, text="", fill=DIM,
                                font=("Consolas", 8))
            self.stick[name] = (ring, dot, val, cx, cy)

        # Steuerkreuz
        dx, dy, s = 200, 225, 14
        for key, (x, y) in {"dpad_up": (dx, dy - 2 * s),
                            "dpad_down": (dx, dy + 2 * s),
                            "dpad_left": (dx - 2 * s, dy),
                            "dpad_right": (dx + 2 * s, dy)}.items():
            self.btn[key] = c.create_rectangle(x - s, y - s, x + s, y + s,
                                               fill=OFF, outline="")
        c.create_rectangle(dx - s, dy - s, dx + s, dy + s, fill=OFF,
                           outline="")

        # Aktionstasten
        fx, fy, g = 430, 140, 30
        self.face_color = {}
        for key, (x, y) in {"y": (fx, fy - g), "a": (fx, fy + g),
                            "x": (fx - g, fy), "b": (fx + g, fy)}.items():
            color, ps = FACE[key]
            self.btn[key] = c.create_oval(x - 15, y - 15, x + 15, y + 15,
                                          fill=OFF, outline=color, width=2)
            self.face_color[key] = color
            c.create_text(x, y - 1, text=key.upper(), fill=TEXT,
                          font=("Segoe UI", 10, "bold"))
            c.create_text(x + 21, y + 13, text=ps, fill=DIM,
                          font=("Segoe UI", 8))

        # Mitte: Back / Guide / Start
        for key, x, label in (("back", 240, "Back"), ("guide", 280, "PS"),
                              ("start", 320, "Start")):
            r = 14 if key == "guide" else 10
            self.btn[key] = c.create_oval(x - r, 130 - r, x + r, 130 + r,
                                          fill=OFF, outline="")
            c.create_text(x, 130 + r + 10, text=label, fill=DIM,
                          font=("Segoe UI", 7))

        self.hint = c.create_text(self.W // 2, 300, text="", fill=DIM,
                                  font=("Segoe UI", 9))

    def _render(self, x: xr.XState | None) -> None:
        c = self.cv
        buttons = x.buttons if x else set()

        for key, item in self.btn.items():
            on = key in buttons
            if key in self.face_color:
                c.itemconfigure(item, fill=self.face_color[key] if on else OFF)
            else:
                c.itemconfigure(item, fill=ON if on else OFF)

        for side in ("lt", "rt"):
            item, x0 = self.trig[side]
            v = getattr(x, side) if x else 0
            c.coords(item, x0, 8, x0 + 100 * v / 255, 24)
            c.itemconfigure(item, state="normal" if v else "hidden")

        for name in ("l", "r"):
            ring, dot, val, cx, cy = self.stick[name]
            sx = getattr(x, f"{name}x") if x else 0
            sy = getattr(x, f"{name}y") if x else 0
            px, py = cx + 29 * sx / 32768, cy - 29 * sy / 32768
            c.coords(dot, px - 9, py - 9, px + 9, py + 9)
            c.itemconfigure(ring, outline=ON if f"{name}3" in buttons
                            else EDGE)
            c.itemconfigure(val, text=f"{sx:+6d} {sy:+6d}" if x else "")

        if x is None:
            if not self._running:
                msg = "Bruecke ist aus - oben starten."
            elif not self._link:
                msg = "Controller einschalten oder per USB anstecken."
            else:
                msg = "Warte auf virtuellen Pad ..."
        else:
            msg = ""
        c.itemconfigure(self.hint, text=msg)

    # --- Ablauf ---------------------------------------------------------

    def _tick(self) -> None:
        now = time.time()
        if now - self._last_scan > 0.5:
            self._last_scan = now
            self._scan()
        x = xr.read(self.slot) if self.slot is not None else None
        self._render(x)
        self.root.after(FRAME_MS, self._tick)

    def _close(self) -> None:
        self.battery.stop()
        self.root.destroy()

    def run(self) -> None:
        self._tick()
        self.root.mainloop()


if __name__ == "__main__":
    Monitor().run()
