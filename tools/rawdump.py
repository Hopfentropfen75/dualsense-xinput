"""Rohdaten-Dump zum Verifizieren der Report-Offsets."""
import sys, time
import dualsense as ds

d = ds.DualSense()
d.enable_full_bt()
print(f"link={'BT' if d.info['product_id'] else ''} path={d.info['path']}")

seen = []
t0 = time.time()
while time.time() - t0 < 6.0:
    raw = d.dev.read(78)
    if raw:
        seen.append(bytes(raw))
    time.sleep(0.002)
d.close()

if not seen:
    print("keine Reports empfangen")
    raise SystemExit(1)

r = seen[-1]
print(f"reports={len(seen)} report_id=0x{r[0]:02x} len={len(r)}")
print("hex:")
for i in range(0, len(r), 16):
    chunk = r[i:i+16]
    print(f"  {i:3d}: " + " ".join(f"{b:02x}" for b in chunk))

# Welche Bytes aendern sich ueber die Zeit? Das entlarvt Zaehler und Sensoren.
varying = sorted({i for a in seen for i, (x, y) in enumerate(zip(a, seen[0])) if x != y})
print(f"\nveraenderliche Offsets: {varying}")
