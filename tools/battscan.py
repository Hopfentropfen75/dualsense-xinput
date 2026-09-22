"""Sucht Bytes, die als Batterie-Feld plausibel sind."""
import time, hid, dualsense as ds

d = ds.DualSense(); d.enable_full_bt()
frames = []
t0 = time.time()
while time.time() - t0 < 3:
    r = d.dev.read(78)
    if r: frames.append(bytes(r))
    time.sleep(0.002)
d.close()

r = frames[-1]
const = [i for i in range(len(r)) if all(f[i] == r[i] for f in frames)]
print("konstante Bytes mit Wert 1..10 (Batterie-Kandidaten, Level 0-10):")
for i in const:
    lo, hi = r[i] & 0x0F, (r[i] >> 4) & 0x0F
    if 1 <= lo <= 10:
        print(f"  idx {i:3d} (payload 0x{i-2:02x}) = 0x{r[i]:02x}  low={lo} -> {lo*10}%  high={hi}")
