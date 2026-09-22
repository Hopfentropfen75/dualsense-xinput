"""Meldet Zustandsaenderungen am virtuellen Pad (Slot 1)."""
import pathlib, sys, time

# Die Module liegen eine Ebene hoeher.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import xinput_ref as xr

SLOT = int(sys.argv[1]) if len(sys.argv) > 1 else 1
DZ = 6000
last = None
t0 = time.time()
while time.time() - t0 < 1700:
    st = xr.read(SLOT)
    if st is None:
        time.sleep(0.5); continue
    sig = (
        "L+" if st.lx > DZ else "L-" if st.lx < -DZ else "",
        "U" if st.ly > DZ else "D" if st.ly < -DZ else "",
        "R+" if st.rx > DZ else "R-" if st.rx < -DZ else "",
        "RU" if st.ry > DZ else "RD" if st.ry < -DZ else "",
        "LT" if st.lt > 40 else "", "RT" if st.rt > 40 else "",
        tuple(sorted(st.buttons)),
    )
    if sig != last and any(sig[:6]) or (last is not None and sig[6] != last[6]):
        parts = [p for p in sig[:6] if p] + list(sig[6])
        if parts:
            print(f"EINGABE: {' '.join(parts)}  "
                  f"L({st.lx},{st.ly}) R({st.rx},{st.ry}) LT{st.lt} RT{st.rt}",
                  flush=True)
        last = sig
    else:
        last = sig
    time.sleep(0.08)
print("Monitor beendet.", flush=True)
