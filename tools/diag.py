"""Zeigt roh -> kalibriert -> gemappt, um die Ruhelage zu pruefen."""
import time
from dualsense import DualSense
from mapping import Config, calibrate, map_state

ds = DualSense(); ds.enable_full_bt()

samples = []
t0 = time.time()
while time.time() - t0 < 1.0:
    st = ds.poll()
    if st: samples.append(st)
    time.sleep(0.002)
print(f"Kalibrier-Samples: {len(samples)}")
if not samples:
    print("KEINE REPORTS -> Verbindung weg"); raise SystemExit(1)

cfg = Config(center=calibrate(samples))
print("Mittelpunkte:", cfg.center)
raw = [(s.lx, s.ly, s.rx, s.ry) for s in samples]
print("roh min/max lx", min(r[0] for r in raw), max(r[0] for r in raw),
      "| ly", min(r[1] for r in raw), max(r[1] for r in raw),
      "| rx", min(r[2] for r in raw), max(r[2] for r in raw),
      "| ry", min(r[3] for r in raw), max(r[3] for r in raw))

print("\nLive (5s) - roh vs gemappt:")
t0 = time.time(); n = 0; last = 0
while time.time() - t0 < 5.0:
    st = ds.poll()
    if st:
        n += 1
        if time.time() - last > 0.5:
            last = time.time()
            x = map_state(st, cfg)
            print(f"  roh L({st.lx:3d},{st.ly:3d}) R({st.rx:3d},{st.ry:3d}) "
                  f"-> XIn L({x.lx:6d},{x.ly:6d}) R({x.rx:6d},{x.ry:6d})")
    time.sleep(0.002)
print(f"Reports in 5s: {n}  (~{n/5:.0f}/s)")
ds.close()
