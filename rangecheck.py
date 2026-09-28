"""Misst, wie weit die Sticks wirklich ausschlagen.

Viele Sticks erreichen den Rand nicht ganz, besonders diagonal - dann
kommt im Spiel nie voller Lenkeinschlag an. Beide Sticks ein paar Mal
langsam am Anschlag kreisen lassen; der schwaechste Winkelbereich
bestimmt, ab wann der Stick als voll ausgelenkt gelten soll.
"""

from __future__ import annotations

import math
import time
from typing import Callable

from dualsense import DualSense
from mapping import _axis

SECTORS = 16
# Nur Samples nahe am Rand zaehlen - sonst verfaelscht der Weg dorthin.
MIN_MAG = 0.6
MARGIN = 0.01
MAX_OUTER = 0.25


class Reach:
    def __init__(self):
        self.best = [0.0] * SECTORS

    def add(self, x: float, y: float) -> None:
        mag = math.hypot(x, y)
        if mag < MIN_MAG:
            return
        sector = int((math.atan2(y, x) + math.pi) / (2 * math.pi) * SECTORS)
        sector %= SECTORS
        self.best[sector] = max(self.best[sector], mag)

    @property
    def coverage(self) -> float:
        return sum(1 for b in self.best if b > 0) / SECTORS

    @property
    def weakest(self) -> float | None:
        return min(self.best) if all(self.best) else None


def outer_for(reach: float | None) -> float | None:
    """Aeussere Zone, damit der schwaechste Bereich noch 100 % erreicht."""
    if reach is None:
        return None
    return round(max(0.0, min(MAX_OUTER, 1.0 - reach + MARGIN)), 3)


def measure(seconds: float = 6.0,
            progress: Callable[[float, float, float], None] | None = None,
            ds: DualSense | None = None) -> tuple[Reach, Reach]:
    """Sammelt `seconds` lang; progress(rest, links, rechts) mit Abdeckung."""
    own = ds is None
    ds = ds or DualSense()
    ds.enable_full_bt()
    left, right = Reach(), Reach()
    end = time.time() + seconds
    try:
        while (rest := end - time.time()) > 0:
            st = ds.poll_latest(timeout_ms=10)
            if st:
                left.add(_axis(st.lx, 128), _axis(st.ly, 128))
                right.add(_axis(st.rx, 128), _axis(st.ry, 128))
            if progress:
                progress(rest, left.coverage, right.coverage)
    finally:
        if own:
            ds.close()
    return left, right


def recommend(left: Reach, right: Reach) -> float | None:
    """Ein Wert fuer beide Sticks - der schwaechere bestimmt."""
    vals = [outer_for(r.weakest) for r in (left, right)]
    if any(v is None for v in vals):
        return None
    return max(vals)


def _main() -> int:
    print("Beide Sticks jetzt mehrmals langsam am Anschlag kreisen lassen ...")

    def show(rest, lc, rc):
        print(f"\r  noch {rest:4.1f}s   links {lc:4.0%}   rechts {rc:4.0%}   ",
              end="", flush=True)

    left, right = measure(progress=show)
    print()
    for name, r in (("links", left), ("rechts", right)):
        w = r.weakest
        print(f"  {name}: schwaechster Bereich "
              f"{f'{w:.0%}' if w is not None else 'nicht ganz gekreist'}")
    rec = recommend(left, right)
    if rec is None:
        print("Nicht alle Richtungen erreicht - bitte nochmal, ganz rundherum.")
        return 1
    print(f"Empfohlene aeussere Zone: {rec:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
