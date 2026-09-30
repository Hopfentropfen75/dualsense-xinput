"""Empfaengt Forzas Telemetrie ("Data Out") per UDP.

Forza Horizon und Motorsport schicken auf Wunsch jeden Frame ein Paket mit
dem Fahrzeugzustand. Fuer ABS und Durchdrehen reicht der vordere Teil
("Sled", 232 Byte), der in allen Formaten gleich aufgebaut ist:
Reifenschlupf pro Rad und Geschwindigkeit. Die Pedalstellung braucht es
nicht - die kennt die Bruecke vom Controller selbst.

Im Spiel: Einstellungen > HUD und Gameplay > Data Out = An,
IP 127.0.0.1, Port 5300.
"""

from __future__ import annotations

import logging
import math
import socket
import struct
import threading
import time

SLED_LEN = 232

log = logging.getLogger("dualsense.telemetry")
FRESH_SECONDS = 0.5


class Telemetry:
    def __init__(self, port: int):
        self.port = port
        self.error: str | None = None
        self.last = 0.0
        self.race_on = False
        self.speed = 0.0                      # m/s
        self.slip = (0.0, 0.0, 0.0, 0.0)      # FL, FR, RL, RR; |x| > 1 = Grip weg
        self._stop = threading.Event()
        self.sock: socket.socket | None = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind(("127.0.0.1", port))
            s.settimeout(0.5)
            self.sock = s
        except OSError as e:
            self.error = f"Port {port} belegt ({e.strerror or e})"
            log.warning("Telemetrie aus: %s", self.error)
            return
        threading.Thread(target=self._loop, daemon=True).start()

    @property
    def fresh(self) -> bool:
        """Kommen gerade Daten aus einem laufenden Rennen?"""
        return self.race_on and time.time() - self.last < FRESH_SECONDS

    @property
    def seen(self) -> bool:
        return self.last > 0 and time.time() - self.last < 5.0

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _ = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(data) < SLED_LEN:
                continue
            self.race_on = struct.unpack_from("<i", data, 0)[0] != 0
            vx, vy, vz = struct.unpack_from("<3f", data, 32)
            self.speed = math.sqrt(vx * vx + vy * vy + vz * vz)
            self.slip = struct.unpack_from("<4f", data, 84)
            self.last = time.time()

    def close(self) -> None:
        self._stop.set()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
