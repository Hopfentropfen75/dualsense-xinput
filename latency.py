"""Latenz messen: wie lange braucht eine Eingabe bis ins Spiel?

Drei Abschnitte, jeder so ehrlich wie messbar:

  USB/Bluetooth   Der Controller sendet im festen Takt (USB gemessen 4 ms).
                  Im Mittel wartet eine Eingabe einen halben Takt - aus der
                  gemessenen Reportrate berechnet, nicht gemessen.
  Bruecke         Report gelesen -> an ViGEm uebergeben (gemessen, jeder
                  Report).
  ViGEm -> Spiel  Uebergabe an ViGEm -> XInput liefert den neuen Zustand
                  (gemessen: ein Thread fragt XInput ab, wie ein Spiel).

Dazu der Rueckstau: wie viele Reports pro Lesevorgang anfielen. Mehr als
einer heisst, die Bruecke kam nicht hinterher.

Waehrend der Messung muss sich am Controller etwas bewegen - XInput meldet
nur Aenderungen.
"""

from __future__ import annotations

import statistics
import threading
import time

import xinput_ref as xr

SECONDS = 4.0


class Probe:
    def __init__(self, bridge):
        self.bridge = bridge
        self.result: dict = {"state": "running", "left": SECONDS}
        threading.Thread(target=self._run, daemon=True,
                         name="latency").start()

    def _run(self) -> None:
        b, ds = self.bridge, self.bridge.ds
        slot = b.slot
        if slot is None:
            self.result = {"state": "error",
                           "message": "Kein virtueller Pad gefunden."}
            return
        samples: list[float] = []
        reads0, reports0 = ds.reads, ds.reports
        last_pkt = None
        start = time.perf_counter()
        end = start + SECONDS
        while (now := time.perf_counter()) < end:
            st = xr.read(slot)
            if st is not None and st.packet != last_pkt:
                t_upd = b.last_update_t
                if last_pkt is not None and t_upd:
                    dt = now - t_upd
                    if 0 <= dt < 0.05:
                        samples.append(dt * 1000)
                last_pkt = st.packet
            self.result["left"] = round(end - now, 1)
            # Nicht dauernd die CPU belegen - aber fein genug abtasten.
            time.sleep(0.0002)
        reads = max(1, ds.reads - reads0)
        backlog = (ds.reports - reports0) / reads - 1
        rate = b.report_rate or 1
        usb = 1000 / rate / 2
        if len(samples) < 10:
            self.result = {"state": "error", "message":
                           "Zu wenig Bewegung - bitte waehrend der Messung "
                           "die Sticks bewegen."}
            return
        samples.sort()
        vigem = statistics.median(samples)
        p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
        self.result = {
            "state": "done",
            "samples": len(samples),
            "usb_ms": round(usb, 2),
            "proc_ms": round(b.proc_ms, 3),
            "vigem_ms": round(vigem, 2),
            "vigem_p95_ms": round(p95, 2),
            "backlog": round(max(0.0, backlog), 2),
            "total_ms": round(usb + b.proc_ms + vigem, 2),
        }
