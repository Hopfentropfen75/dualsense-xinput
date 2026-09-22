"""USB-Report holen und mit dem BT-Dump vergleichen: Ladezustand muss
sich jetzt irgendwo als gesetztes Nibble zeigen."""
import time, hid
import dualsense as ds

for d in ds.find():
    print(f"interface: usage_page=0x{d['usage_page']:04x} path={d['path'][:60]}...")

dev = ds.DualSense()
dev.enable_full_bt()
frames = []
t0 = time.time()
while time.time() - t0 < 2.0:
    r = dev.dev.read(78)
    if r: frames.append(bytes(r))
    time.sleep(0.002)
dev.close()

r = frames[-1]
o = 1 if r[0] == 0x01 else 2
print(f"\nreport_id=0x{r[0]:02x} len={len(r)} payload-offset={o}  ({'USB' if o==1 else 'BT'})")
for i in range(0, len(r), 16):
    print(f"  {i:3d}: " + " ".join(f"{b:02x}" for b in r[i:i+16]))

const = [i for i in range(len(r)) if all(f[i] == r[i] for f in frames)]
print("\nkonstante Bytes != 0 im hinteren Bereich (Status-Kandidaten):")
for i in const:
    if i >= o + 40 and r[i] != 0:
        lo, hi = r[i] & 0x0F, (r[i] >> 4) & 0x0F
        print(f"  idx {i:3d} payload 0x{i-o:02x} = 0x{r[i]:02x}  low={lo} high={hi}")
