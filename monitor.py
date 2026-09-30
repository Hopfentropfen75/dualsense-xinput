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
from tkinter import messagebox, simpledialog
from pathlib import Path

import games
import rangecheck
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


GYRO_MODES = {"aus": "Aus", "l2": "Beim Zielen (L2)", "immer": "Immer"}


class ProfilePanel:
    """Rechte Spalte: Profil waehlen, anlegen, loeschen und einstellen.

    Jede Aenderung landet sofort in settings.json; die Bruecke uebernimmt
    sie innerhalb von etwa zwei Sekunden."""

    # Tab -> [(Abschnitt, [(Schluessel, Beschriftung, von, bis, Schritt,
    #                       Anzeige-Faktor, Einheit)])]
    LAYOUT = {
        "Trigger": [
            ("Widerstand", [
                ("brake_start", "Bremse: Druckpunkt", 0, 8, 1, 1, ""),
                ("brake_force", "Bremse: Kraft", 1, 8, 1, 1, ""),
                ("gas_force", "Gas: Widerstand", 0, 8, 1, 1, ""),
            ]),
            ("Feedback (Racing + Feedback)", [
                ("abs_strength", "ABS: Staerke", 0, 8, 1, 1, ""),
                ("abs_frequency", "ABS: Frequenz", 5, 60, 1, 1, " Hz"),
                ("spin_strength", "Durchdrehen", 0, 8, 1, 1, ""),
            ]),
            ("Eingabe", [
                ("l2_deadzone", "L2 Leerweg", 0, 0.20, 0.01, 100, "%"),
                ("r2_deadzone", "R2 Leerweg", 0, 0.20, 0.01, 100, "%"),
                ("l2_curve", "L2 Kurve", 0.5, 3.0, 0.1, 1, ""),
                ("r2_curve", "R2 Kurve", 0.5, 3.0, 0.1, 1, ""),
            ]),
            ("Vibration", [
                ("rumble_gain", "Staerke", 0, 2.0, 0.05, 100, "%"),
            ]),
        ],
        "Sticks": [
            ("Deadzones", [
                ("stick_deadzone", "Deadzone innen", 0, 0.25, 0.01, 100, "%"),
                ("stick_outer", "Aeussere Zone", 0, 0.25, 0.01, 100, "%"),
                ("anti_deadzone", "Anti-Deadzone", 0, 0.40, 0.01, 100, "%"),
            ]),
        ],
        "Gyro": [
            ("Zielen", [
                ("gyro_sensitivity", "Empfindlichkeit", 0.2, 4.0, 0.1, 1, ""),
                ("gyro_min", "Mindestausschlag", 0, 0.40, 0.01, 100, "%"),
            ]),
        ],
        "Spiele": [],
    }
    CHOICES = {"triggers": triggers.MODES, "gyro": GYRO_MODES}
    FLAGS = ("gyro_invert_x", "gyro_invert_y")

    def __init__(self, parent: tk.Widget, app: "Monitor"):
        self.app = app
        self.frame = tk.Frame(parent, bg=PANEL, padx=12, pady=10)
        self.edit: str | None = None
        self._loading = False
        self._pending: dict = {}
        self._loaded: dict[str, float] = {}
        self._save_job = None
        self._profiles: list[str] = []
        self.vars: dict[str, tk.DoubleVar] = {}
        self.vals: dict[str, tk.Label] = {}
        self.fmt: dict[str, tuple[float, str, float]] = {}
        self.choice_btns: dict[str, dict[str, tk.Button]] = {}
        self.choice_val: dict[str, str] = {}
        self.flags: dict[str, tk.BooleanVar] = {}
        f = self.frame

        # Profilauswahl
        row = tk.Frame(f, bg=PANEL)
        row.pack(fill="x")
        tk.Label(row, text="Profil", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        self.choice = tk.StringVar()
        self.menu = tk.OptionMenu(row, self.choice, "")
        self.menu.configure(bg=BODY, fg=TEXT, activebackground=ON,
                            activeforeground="white", relief="flat",
                            highlightthickness=0, font=("Segoe UI", 10),
                            width=12)
        self.menu["menu"].configure(bg=BODY, fg=TEXT, activebackground=ON)
        self.menu.pack(side="left", padx=8)
        for text, cmd in (("Neu", self._new), ("Loeschen", self._delete)):
            self._button(row, text, cmd).pack(side="left", padx=2)

        # Tabs
        tabbar = tk.Frame(f, bg=PANEL)
        tabbar.pack(fill="x", pady=(10, 0))
        self.tab_btns: dict[str, tk.Button] = {}
        self.tabs: dict[str, tk.Frame] = {}
        for name in self.LAYOUT:
            b = tk.Button(tabbar, text=name, relief="flat", bd=0, padx=12,
                          pady=3, font=("Segoe UI", 9, "bold"),
                          command=lambda n=name: self._show_tab(n))
            b.pack(side="left", padx=(0, 2))
            self.tab_btns[name] = b
        # Feste Hoehe fuer alle Tabs, sonst springt das Fenster beim Wechseln.
        self.tab_area = tk.Frame(f, bg=PANEL)
        self.tab_area.pack(fill="both", expand=True)
        for name in self.LAYOUT:
            self.tabs[name] = tk.Frame(self.tab_area, bg=PANEL)

        for name, sections in self.LAYOUT.items():
            tab = self.tabs[name]
            if name == "Trigger":
                self._choice_row(tab, "Modus", "triggers")
            if name == "Gyro":
                self._choice_row(tab, "Aktiv", "gyro")
            for title, items in sections:
                self._section(tab, title)
                grid = tk.Frame(tab, bg=PANEL)
                grid.pack(fill="x")
                grid.columnconfigure(1, weight=1)
                for r, spec in enumerate(items):
                    self._slider(grid, r, *spec)
            if name == "Sticks":
                self.measure_btn = self._button(tab, "Reichweite messen",
                                                self._measure)
                self.measure_btn.pack(anchor="w", pady=(8, 0))
                self._note(tab, "Beide Sticks nach dem Klick ein paar Mal "
                                "am Anschlag kreisen lassen.")
            if name == "Gyro":
                self._section(tab, "Richtung")
                for key, label in (("gyro_invert_x", "Links/rechts umkehren"),
                                   ("gyro_invert_y", "Oben/unten umkehren")):
                    self._flag(tab, key, label)
                self._note(tab, "Controller beim Start ruhig liegen lassen - "
                                "dabei wird auch der Gyro kalibriert.")
            if name == "Spiele":
                self._build_games(tab)
        self.tab_area.update_idletasks()
        self.tab_area.configure(
            width=max(t.winfo_reqwidth() for t in self.tabs.values()),
            height=max(t.winfo_reqheight() for t in self.tabs.values()))
        self.tab_area.pack_propagate(False)
        self._show_tab("Trigger")

    # --- Aufbau ---------------------------------------------------------

    def _button(self, parent, text, cmd) -> tk.Button:
        return tk.Button(parent, text=text, command=cmd, bg=BODY, fg=TEXT,
                         activebackground=ON, activeforeground="white",
                         relief="flat", padx=8, font=("Segoe UI", 9))

    def _section(self, parent, title: str) -> None:
        tk.Label(parent, text=title, bg=PANEL, fg=DIM,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))

    def _note(self, parent, text: str) -> None:
        tk.Label(parent, text=text, bg=PANEL, fg=DIM, font=("Segoe UI", 8),
                 wraplength=320, justify="left").pack(anchor="w", pady=(6, 0))

    def _choice_row(self, parent, title: str, key: str) -> None:
        self._section(parent, title)
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x")
        self.choice_btns[key] = {}
        for val, name in self.CHOICES[key].items():
            b = tk.Button(row, text=name, relief="flat", padx=6, bd=0,
                          font=("Segoe UI", 9),
                          command=lambda v=val, k=key: self._set_choice(k, v))
            b.pack(side="left", padx=(0, 4))
            self.choice_btns[key][val] = b

    def _flag(self, parent, key: str, label: str) -> None:
        var = tk.BooleanVar()
        tk.Checkbutton(parent, text=label, variable=var,
                       command=lambda k=key: self._set_flag(k),
                       bg=PANEL, fg=TEXT, selectcolor=BODY,
                       activebackground=PANEL, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(anchor="w")
        self.flags[key] = var

    def _slider(self, grid, row, key, label, lo, hi, step, factor, unit):
        tk.Label(grid, text=label, bg=PANEL, fg=TEXT, font=("Segoe UI", 9),
                 width=17, anchor="w").grid(row=row, column=0, sticky="w")
        var = tk.DoubleVar()
        tk.Scale(grid, from_=lo, to=hi, resolution=step, orient="horizontal",
                 variable=var, showvalue=False, length=150, width=12,
                 sliderlength=14, bg=ON, fg=TEXT, troughcolor=BODY,
                 activebackground="#6f9dff",
                 highlightthickness=0, bd=0, sliderrelief="flat",
                 command=lambda _v, k=key: self._changed(k)
                 ).grid(row=row, column=1, sticky="ew", padx=6, pady=2)
        val = tk.Label(grid, text="", bg=PANEL, fg=TEXT, width=6,
                       font=("Consolas", 9), anchor="e")
        val.grid(row=row, column=2)
        self.vars[key], self.vals[key] = var, val
        self.fmt[key] = (factor, unit, step)

    def _build_games(self, tab) -> None:
        self.auto = tk.BooleanVar()
        self._section(tab, "Automatisch umschalten")
        tk.Checkbutton(tab, text="Profil wechseln, wenn ein Spiel laeuft",
                       variable=self.auto, command=self._toggle_auto,
                       bg=PANEL, fg=TEXT, selectcolor=BODY,
                       activebackground=PANEL, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(anchor="w")
        self._section(tab, "Spiele dieses Profils (Teil des Exe-Namens)")
        self.games = tk.StringVar()
        entry = tk.Entry(tab, textvariable=self.games, bg=BODY, fg=TEXT,
                         insertbackground=TEXT, relief="flat",
                         font=("Segoe UI", 9))
        entry.pack(fill="x", ipady=3)
        entry.bind("<Return>", lambda _: self._save_games())
        entry.bind("<FocusOut>", lambda _: self._save_games())
        self._note(tab, "Mehrere mit Komma trennen, z. B. "
                        "forzahorizon, forzamotorsport")

        self._section(tab, "Forza-Telemetrie (fuer echtes ABS-Gefuehl)")
        self.tele_lbl = tk.Label(tab, text="", bg=PANEL, fg=DIM,
                                 font=("Segoe UI", 9), anchor="w")
        self.tele_lbl.pack(anchor="w")
        port = settings.load()["telemetry_port"]
        self._note(tab, "Im Spiel: Einstellungen > HUD und Gameplay > "
                        f"Data Out = An, IP 127.0.0.1, Port {port}. Ohne "
                        "Telemetrie wird ABS aus Bremsdruck und Rumble "
                        "geschaetzt.")

    def _show_tab(self, name: str) -> None:
        for n, tab in self.tabs.items():
            tab.pack_forget()
            on = n == name
            self.tab_btns[n].configure(
                bg=BODY if on else PANEL, fg=TEXT if on else DIM,
                activebackground=BODY, activeforeground=TEXT)
        self.tabs[name].pack(fill="both", expand=True)

    def _show_value(self, key: str) -> None:
        factor, unit, step = self.fmt[key]
        v = self.vars[key].get() * factor
        text = f"{v:.0f}{unit}" if step >= 1 or factor == 100 else f"{v:.1f}"
        self.vals[key].configure(text=text)

    def show_telemetry(self, status: dict) -> None:
        if status.get("telemetry_error"):
            self.tele_lbl.configure(text=status["telemetry_error"], fg=BAD)
        elif status.get("telemetry"):
            self.tele_lbl.configure(text="Empfaengt Daten - ABS aus echtem "
                                         "Reifenschlupf", fg=OK)
        elif status.get("telemetry_seen"):
            self.tele_lbl.configure(text="Verbunden, gerade kein Rennen",
                                    fg=WARN)
        else:
            self.tele_lbl.configure(text="Keine Daten", fg=DIM)

    # --- Abgleich mit settings.json -------------------------------------

    def sync(self, data: dict) -> None:
        """Zieht Aenderungen von aussen nach (Tray, anderes Fenster)."""
        names = list(data["profiles"])
        if names != self._profiles:
            self._profiles = names
            m = self.menu["menu"]
            m.delete(0, "end")
            for n in names:
                m.add_command(label=n, command=lambda n=n: self._select(n))
        self.auto.set(data["auto_game"])
        if self._pending:
            return          # nicht ueberschreiben, was gerade gespeichert wird
        if data["active"] != self.edit or not self._same(data):
            self._load(data["active"], data)

    def _same(self, data: dict) -> bool:
        p = data["profiles"].get(self.edit, {})
        # Das Spiele-Feld zaehlt nicht mit - sonst wuerde Getipptes
        # ueberschrieben, bevor es gespeichert ist.
        same = all(abs(float(p[k]) - self.vars[k].get()) < 1e-6
                   for k in self.vars)
        same = same and all(p[k] == v for k, v in self.choice_val.items())
        return same and all(bool(p[k]) == v.get()
                            for k, v in self.flags.items())

    def _load(self, name: str, data: dict) -> None:
        self._loading = True
        self.edit = name
        self.choice.set(name)
        p = data["profiles"][name]
        for k, var in self.vars.items():
            var.set(float(p[k]))
            self._loaded[k] = var.get()
            self._show_value(k)
        for k in self.CHOICES:
            self._show_choice(k, p[k])
        for k, var in self.flags.items():
            var.set(bool(p[k]))
        self.games.set(", ".join(p["games"]))
        self._loading = False

    # --- Aktionen -------------------------------------------------------

    def _select(self, name: str) -> None:
        data = settings.update(active=name)
        self._load(name, data)

    def _changed(self, key: str) -> None:
        self._show_value(key)
        if self._loading or self.edit is None:
            return
        v = self.vars[key].get()
        # Tk meldet auch per Programm gesetzte Werte - die nicht zurueckschreiben.
        if abs(v - self._loaded.get(key, float("nan"))) < 1e-9:
            return
        self._loaded[key] = v
        self._pending[key] = v
        # Beim Ziehen nicht bei jedem Pixel schreiben.
        if self._save_job:
            self.frame.after_cancel(self._save_job)
        self._save_job = self.frame.after(250, self._flush)

    def _flush(self) -> None:
        self._save_job = None
        changes, self._pending = self._pending, {}
        if self.edit and changes:
            settings.update_profile(self.edit, **changes)

    def _set_choice(self, key: str, val: str) -> None:
        self._show_choice(key, val)
        if self.edit:
            settings.update_profile(self.edit, **{key: val})

    def _show_choice(self, key: str, val: str) -> None:
        self.choice_val[key] = val
        for v, b in self.choice_btns[key].items():
            on = v == val
            b.configure(bg=ON if on else BODY, fg="white" if on else TEXT,
                        activebackground=ON, activeforeground="white")

    def _set_flag(self, key: str) -> None:
        if self.edit:
            settings.update_profile(self.edit, **{key: self.flags[key].get()})

    def _toggle_auto(self) -> None:
        settings.update(auto_game=self.auto.get())

    def _save_games(self) -> None:
        if not self.edit:
            return
        pats = [g.strip().lower() for g in self.games.get().split(",")
                if g.strip()]
        settings.update_profile(self.edit, games=pats)

    def _new(self) -> None:
        name = simpledialog.askstring(
            "Neues Profil", "Name (Kopie des aktuellen Profils):",
            parent=self.frame)
        if not name or not name.strip():
            return
        name = name.strip()
        data = settings.load()
        if name in data["profiles"]:
            messagebox.showinfo("Profil", f'"{name}" gibt es schon.')
            return
        base = dict(data["profiles"].get(self.edit, {}))
        base["games"] = []
        data["profiles"][name] = base
        data["active"] = name
        settings.save(data)
        self.sync(settings.load())

    def _delete(self) -> None:
        data = settings.load()
        if len(data["profiles"]) <= 1 or self.edit not in data["profiles"]:
            messagebox.showinfo("Profil", "Das letzte Profil bleibt.")
            return
        if not messagebox.askyesno("Profil loeschen",
                                   f'Profil "{self.edit}" loeschen?'):
            return
        del data["profiles"][self.edit]
        data["active"] = next(iter(data["profiles"]))
        settings.save(data)
        self.sync(settings.load())

    def _measure(self) -> None:
        self.measure_btn.configure(state="disabled", text="misst ...")

        def done(rec):
            self.measure_btn.configure(state="normal",
                                       text="Reichweite messen")
            if rec is not None:
                self.vars["stick_outer"].set(rec)
                self._changed("stick_outer")

        self.app.measure_reach(done)


class Monitor:
    W, H = 560, 330

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(TITLE)
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
        self._last_games = 0.0
        self._link = None
        self._running = False
        self._game: tuple[str, str] | None = None
        self._measure_msg: str | None = None

        self._build_status()
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", padx=12, pady=(4, 12))
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", anchor="n")
        self.cv = tk.Canvas(left, width=self.W, height=self.H, bg=BG,
                            highlightthickness=0)
        self.cv.pack()
        self.active_lbl = tk.Label(left, text="", bg=BG, fg=DIM,
                                   font=("Segoe UI", 9), anchor="w")
        self.active_lbl.pack(fill="x", pady=(6, 0))
        self.panel = ProfilePanel(body, self)
        self.panel.frame.pack(side="left", fill="y", padx=(12, 0))
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
                          str(tray), "--hidden"], cwd=str(tray.parent))
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

        if self._running:
            self.start_btn.pack_forget()
            self.start_btn.configure(text="Bruecke starten", state="normal")
        elif not self.start_btn.winfo_ismapped():
            self.start_btn.pack(side="right", padx=10)

        data = settings.load()
        now = time.time()
        if now - self._last_games > 2.0:
            self._last_games = now
            self._game = games.detect(data)
        eff = settings.effective(data, self._game[1] if self._game else None)
        status = settings.read_status() if self._running else {}
        self.panel.show_telemetry(status)
        if self._game and eff == self._game[1]:
            self.active_lbl.configure(
                text=f"Aktiv: {eff}  (automatisch - {self._game[0]} laeuft)",
                fg=OK)
        else:
            self.active_lbl.configure(text=f"Aktiv: {eff}", fg=DIM)
        self.panel.sync(data)

    # --- Reichweite messen ----------------------------------------------

    def measure_reach(self, done) -> None:
        def progress(rest, lc, rc):
            self._measure_msg = (
                f"Beide Sticks am Anschlag kreisen - noch {rest:3.1f}s   "
                f"L {lc:4.0%}  R {rc:4.0%}")

        def work():
            try:
                left, right = rangecheck.measure(progress=progress)
                rec = rangecheck.recommend(left, right)
            except Exception as e:  # Controller weg o. ae.
                rec, left, right = None, None, None
                self._measure_msg = f"Messung fehlgeschlagen: {e}"
            if rec is None and left is not None:
                self._measure_msg = ("Nicht alle Richtungen erreicht - "
                                     "nochmal ganz rundherum.")
            elif rec is not None:
                self._measure_msg = f"Aeussere Zone auf {rec:.0%} gesetzt."
            self.root.after(0, lambda: done(rec))
            time.sleep(4)
            self._measure_msg = None

        threading.Thread(target=work, daemon=True).start()

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

        if self._measure_msg:
            msg = self._measure_msg
        elif x is None:
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


TITLE = "DualSense - Anzeige"


def _focus_existing() -> bool:
    """Ist das Fenster schon offen, nur nach vorn holen statt ein zweites."""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, TITLE)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE, falls minimiert
    user32.SetForegroundWindow(hwnd)
    return True


if __name__ == "__main__":
    if not _focus_existing():
        Monitor().run()
