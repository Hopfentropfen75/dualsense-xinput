"""Cockpit: lokale Oberflaeche fuer Status, Live-Eingaben und Profile.

Laeuft im Tray-Prozess neben der Bruecke - die Live-Werte kommen direkt
aus ihrem Speicher, ohne Umweg ueber Dateien. Angezeigt wird ui/cockpit.html
in einem Edge-App-Fenster (ohne Adressleiste) auf 127.0.0.1.

Die API verlangt ein Zufallstoken, das nur im Link des Fensters steht:
andere Webseiten im Browser koennen es nicht lesen und damit auch keine
Einstellungen aendern.
"""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import settings
import triggers
from dualsense import find, is_usb
from mapping import XINPUT_MASKS, _axis

HERE = Path(__file__).parent
PAGE = HERE / "ui" / "cockpit.html"
ICON = HERE / "dualsense.ico"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", str(HERE))) / "DualSenseCockpit"
INFO = STATE_DIR / "ui.json"
TITLE = "DualSense Cockpit"
FPS = 30
GYRO_MODES = {"aus": "Aus", "l2": "Beim Zielen (L2)", "immer": "Immer"}


class Cockpit:
    def __init__(self, app):
        self.app = app
        self.token = secrets.token_urlsafe(18)
        self._ctl = (0.0, None)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        # Damit ein zweiter Start das Fenster dieser Instanz oeffnen kann.
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        INFO.write_text(json.dumps({"url": self.url}), encoding="utf-8")

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def open(self) -> None:
        open_window(self.url)

    def close(self) -> None:
        try:
            INFO.unlink()
        except OSError:
            pass
        self.httpd.shutdown()

    # --- Live-Zustand ---------------------------------------------------

    def _controller(self) -> str | None:
        """USB/Bluetooth/None - hoechstens einmal pro Sekunde nachsehen."""
        now = time.time()
        if now - self._ctl[0] > 1.0:
            devs = find()
            link = None
            if devs:
                link = "USB" if is_usb(devs[0]) else "Bluetooth"
            self._ctl = (now, link)
        return self._ctl[1]

    def snapshot(self) -> dict:
        app, b = self.app, self.app.bridge
        s: dict = {"bridge": False, "error": app.error,
                   "controller": self._controller()}
        if b is None or b.out is None or b.last_x is None:
            return s
        st, x, cfg = b.ds.state, b.last_x, b.cfg
        c = cfg.center
        t = b.tele
        s.update(
            bridge=True,
            link="Bluetooth" if b.ds.bluetooth else "USB",
            rate=round(b.report_rate),
            proc_ms=round(b.proc_ms, 2),
            slot=b.slot,
            battery=st.battery_percent,
            charging=st.charging,
            full=st.battery_full,
            profile=b.profile_name,
            game=b.game,
            raw={"lx": _axis(st.lx, c["lx"]), "ly": -_axis(st.ly, c["ly"]),
                 "rx": _axis(st.rx, c["rx"]), "ry": -_axis(st.ry, c["ry"]),
                 "l2": st.l2 / 255, "r2": st.r2 / 255},
            out={"lx": x.lx / 32767, "ly": x.ly / 32767,
                 "rx": x.rx / 32767, "ry": x.ry / 32767,
                 "lt": x.lt / 255, "rt": x.rt / 255,
                 "buttons": [n for n, m in XINPUT_MASKS.items()
                             if x.buttons & m]},
            gyro={"active": b.gyro_active, "x": b.gyro.rate[0],
                  "y": b.gyro.rate[1]},
            abs=b.feedback[0],
            spin=b.feedback[1],
            tele={"fresh": bool(t and t.fresh), "seen": bool(t and t.seen),
                  "error": t.error if t else None,
                  "speed": t.speed if t else 0.0,
                  "slip": list(t.slip) if t else [0, 0, 0, 0],
                  "port": t.port if t else None},
        )
        return s

    # --- Einstellungen --------------------------------------------------

    def _settings(self) -> dict:
        return {"settings": settings.load(), "modes": triggers.MODES,
                "gyro_modes": GYRO_MODES}

    def _post(self, path: str, body: dict) -> dict:
        b = self.app.bridge
        if path == "/api/profile":
            settings.update_profile(body["name"], **body["changes"])
        elif path == "/api/active":
            settings.update(active=body["name"])
        elif path == "/api/auto":
            settings.update(auto_game=bool(body["on"]))
        elif path == "/api/profile/new":
            data = settings.load()
            name = str(body["name"]).strip()
            if not name or name in data["profiles"]:
                return {"error": "Den Namen gibt es schon." if name
                        else "Bitte einen Namen eingeben."}
            base = dict(data["profiles"].get(body.get("from"), {}))
            base["games"] = []
            data["profiles"][name] = base
            data["active"] = name
            settings.save(data)
        elif path == "/api/profile/delete":
            data = settings.load()
            if len(data["profiles"]) > 1:
                data["profiles"].pop(body["name"], None)
                if data["active"] not in data["profiles"]:
                    data["active"] = next(iter(data["profiles"]))
                settings.save(data)
        elif path == "/api/abs-test":
            if b is not None:
                b.abs_test_until = time.time() + 1.5
        elif path == "/api/recalibrate":
            if b is not None:
                b.recalibrate_requested = True
        else:
            return {"error": "unbekannt"}
        return self._settings()

    # --- HTTP -----------------------------------------------------------

    def _handler(self):
        cockpit = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):     # kein Konsolenrauschen
                pass

            def _authorized(self, q: dict) -> bool:
                tok = self.headers.get("X-Token") or q.get("t", [""])[0]
                return secrets.compare_digest(tok, cockpit.token)

            def _send(self, code: int, body: bytes, ctype: str) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, data: dict, code: int = 200) -> None:
                self._send(code, json.dumps(data).encode(),
                           "application/json; charset=utf-8")

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path == "/":
                    self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
                elif u.path == "/favicon.ico" and ICON.exists():
                    self._send(200, ICON.read_bytes(), "image/x-icon")
                elif not self._authorized(q):
                    self._json({"error": "Token fehlt"}, 403)
                elif u.path == "/api/settings":
                    self._json(cockpit._settings())
                elif u.path == "/api/stream":
                    self._stream()
                else:
                    self._json({"error": "nicht gefunden"}, 404)

            def do_POST(self):
                u = urlparse(self.path)
                if not self._authorized(parse_qs(u.query)):
                    self._json({"error": "Token fehlt"}, 403)
                    return
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(n) or b"{}")
                    self._json(cockpit._post(u.path, body))
                except (ValueError, KeyError) as e:
                    self._json({"error": f"Ungueltige Anfrage: {e}"}, 400)

            def _stream(self):
                """Server-Sent Events: 30 Zustandsbilder pro Sekunde."""
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                try:
                    while True:
                        data = json.dumps(cockpit.snapshot())
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                        time.sleep(1 / FPS)
                except (OSError, ValueError):
                    pass

        return Handler


# --- Fenster ------------------------------------------------------------

def _edge() -> str | None:
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return str(p)
    return None


def focus_existing() -> bool:
    """Ist das Cockpit schon offen, nur nach vorn holen."""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, TITLE)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)              # SW_RESTORE, falls minimiert
    user32.SetForegroundWindow(hwnd)
    return True


def open_window(url: str) -> None:
    if focus_existing():
        return
    edge = _edge()
    if edge is None:
        webbrowser.open(url)
        return
    # Eigenes Profil: das Fenster ist unabhaengig vom normalen Browser und
    # merkt sich seine Groesse.
    subprocess.Popen([
        edge, f"--app={url}", f"--user-data-dir={STATE_DIR / 'edge'}",
        "--window-size=1280,880", "--no-first-run",
        "--no-default-browser-check",
    ])


def open_running() -> bool:
    """Aus einem zweiten Prozess: das Cockpit der laufenden Instanz oeffnen."""
    if focus_existing():
        return True
    try:
        url = json.loads(INFO.read_text(encoding="utf-8"))["url"]
    except (OSError, ValueError, KeyError):
        return False
    open_window(url)
    return True
