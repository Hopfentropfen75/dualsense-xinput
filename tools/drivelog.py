"""Zeichnet auf, was die Bruecke waehrend der Fahrt wirklich ausgibt.

Beantwortet zwei Fragen:
  - Kommen Gas und Bremse je gleichzeitig aus UNSERER Bruecke?
  - Bricht die Lenkung zwischendurch weg (Luecken im Datenstrom)?

Ist die Ausgabe sauber, liegt das Problem hinter uns - im Spiel.
"""

from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import xinput_ref as xr

SLOT = int(sys.argv[1]) if len(sys.argv) > 1 else 0
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
RATE = 0.004  # 250 Hz, so schnell wie der Controller liefert


def main() -> int:
    if xr.read(SLOT) is None:
        print(f"Slot {SLOT} ist nicht belegt.")
        return 1

    print(f"Zeichne {SECONDS:.0f}s auf Slot {SLOT} auf - JETZT FAHREN.\n")
    samples = []
    t0 = time.time()
    while time.time() - t0 < SECONDS:
        st = xr.read(SLOT)
        if st:
            samples.append((time.time() - t0, st.lt, st.rt, st.lx, st.ly,
                            st.packet))
        time.sleep(RATE)

    if not samples:
        print("Keine Daten.")
        return 1

    n = len(samples)
    both = [s for s in samples if s[1] > 10 and s[2] > 10]
    gas = [s for s in samples if s[2] > 10]
    brake = [s for s in samples if s[1] > 10]
    steer = [s for s in samples if abs(s[3]) > 3000]

    # Groesste Luecke zwischen zwei Messpunkten - zeigt Aussetzer.
    gaps = [samples[i][0] - samples[i - 1][0] for i in range(1, n)]
    worst_gap = max(gaps) if gaps else 0.0

    # Hat sich der Paketzaehler bewegt? Stillstand = Bruecke sendet nichts.
    packets = samples[-1][5] - samples[0][5]

    print(f"{n} Messpunkte in {samples[-1][0]:.1f}s "
          f"({n / samples[-1][0]:.0f}/s), {packets} neue XInput-Pakete")
    print(f"  Gas (RT>10):          {len(gas):5d} Messpunkte")
    print(f"  Bremse (LT>10):       {len(brake):5d} Messpunkte")
    print(f"  BEIDE gleichzeitig:   {len(both):5d} Messpunkte", end="")
    print("   <== PROBLEM LIEGT BEI UNS" if both else "   <== sauber getrennt")
    print(f"  Lenkung (|LX|>3000):  {len(steer):5d} Messpunkte")
    print(f"  groesste Messluecke:  {worst_gap * 1000:.0f} ms")

    if both:
        print("\n  Beispiele fuer gleichzeitiges Gas+Bremse:")
        for t, lt, rt, lx, ly, pk in both[:8]:
            print(f"    t={t:5.2f}s  LT={lt:3d} RT={rt:3d}")

    # Lenkverlauf grob zeichnen, um Aussetzer sichtbar zu machen.
    print("\n  Lenkung ueber die Zeit (Zeile = 1s, Mitte = geradeaus):")
    width = 51
    sec = 0
    while sec < int(samples[-1][0]) + 1:
        chunk = [s for s in samples if sec <= s[0] < sec + 1]
        if chunk:
            avg = sum(c[3] for c in chunk) / len(chunk)
            pos = int((avg / 32767 + 1) / 2 * (width - 1))
            line = ["."] * width
            line[width // 2] = "|"
            line[max(0, min(width - 1, pos))] = "#"
            rt = max(c[2] for c in chunk)
            lt = max(c[1] for c in chunk)
            print(f"    {sec:3d}s {''.join(line)}  RT{rt:3d} LT{lt:3d}")
        sec += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
