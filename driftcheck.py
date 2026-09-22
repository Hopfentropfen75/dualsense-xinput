"""Misst Stickdrift und empfiehlt eine Deadzone.

Unterscheidet zwei Dinge, die beide "Drift" genannt werden:

  Versatz  - die Ruhelage liegt nicht auf der Mitte. Harmlos, solange sie
             stabil ist: die Kalibrierung beim Start zieht das glatt.
  Zittern  - die Ruhelage wandert oder rauscht. Das laesst sich nicht
             wegkalibrieren, nur mit einer Deadzone abdecken.
"""

from __future__ import annotations

import argparse
import math
import time

from dualsense import DualSense
from mapping import Config, calibrate, map_state

CENTER = 128.0
AXES = ("lx", "ly", "rx", "ry")


def collect(seconds: float) -> list:
    dev = DualSense()
    dev.enable_full_bt()
    link = "Bluetooth" if dev.bluetooth else "USB"
    samples = []
    end = time.time() + seconds
    while time.time() < end:
        st = dev.poll()
        if st:
            samples.append(st)
            link = "Bluetooth" if dev.bluetooth else "USB"
        time.sleep(0.002)
    dev.close()
    return samples, link


def verdict(offset_pct: float, jitter_pct: float) -> str:
    worst = offset_pct + jitter_pct
    if worst < 2.0:
        return "unauffaellig"
    if worst < 5.0:
        return "leicht - normal fuer einen benutzten Controller"
    if worst < 12.0:
        return "deutlich - in Spielen ohne eigene Deadzone spuerbar"
    return "stark - Stickmodul vermutlich verschlissen"


def main() -> int:
    ap = argparse.ArgumentParser(description="Stickdrift messen")
    ap.add_argument("--seconds", type=float, default=5.0)
    a = ap.parse_args()

    print(f"Messe {a.seconds:.0f}s Ruhelage - Controller hinlegen und "
          f"nicht beruehren ...\n")
    samples, link = collect(a.seconds)
    if not samples:
        print("Keine Reports empfangen.")
        return 1

    print(f"{len(samples)} Messwerte ueber {link}\n")
    print(f"{'Achse':<6}{'Ruhe':>7}{'Versatz':>10}{'Zittern':>10}"
          f"{'ohne Kal.':>12}")
    print("-" * 45)

    worst_offset = 0.0
    worst_jitter = 0.0
    for ax in AXES:
        vals = [getattr(s, ax) for s in samples]
        mean = sum(vals) / len(vals)
        offset = mean - CENTER
        jitter = max(vals) - min(vals)
        offset_pct = abs(offset) / CENTER * 100
        jitter_pct = jitter / CENTER * 100
        worst_offset = max(worst_offset, offset_pct)
        worst_jitter = max(worst_jitter, jitter_pct)
        # Was ein Spiel ohne Kalibrierung sehen wuerde.
        raw_xinput = int(offset / CENTER * 32767)
        print(f"{ax:<6}{mean:7.1f}{offset:+10.1f}{jitter:>10d}"
              f"{raw_xinput:+12d}")

    print()
    print(f"Groesster Versatz: {worst_offset:.1f} %  |  "
          f"groesstes Zittern: {worst_jitter:.1f} %")
    print(f"Einschaetzung: {verdict(worst_offset, worst_jitter)}")

    # Die Kalibrierung zieht den Versatz ab; uebrig bleibt das Zittern.
    cfg = Config(center=calibrate(samples))
    residual = 0.0
    for s in samples:
        x = map_state(s, cfg)
        residual = max(residual,
                       math.hypot(x.lx, x.ly) / 32767,
                       math.hypot(x.rx, x.ry) / 32767)

    print(f"\nNach Kalibrierung bleibt in Ruhe: {residual * 100:.2f} % "
          f"Restausschlag")
    need = max(0.02, worst_jitter / 100 * 1.5)
    print(f"Empfohlene Deadzone: {need:.2f}"
          f"  ->  python bridge.py --deadzone {need:.2f}")
    if residual == 0.0:
        print("Die Voreinstellung 0.08 deckt das bereits vollstaendig ab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
