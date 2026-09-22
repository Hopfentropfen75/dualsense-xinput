import time
import vgamepad as vg
import xinput_ref as xr

before = xr.connected()
print("Slots vorher:", before)

pad = vg.VX360Gamepad()
time.sleep(1.0)

after = xr.connected()
print("Slots nachher:", after)
new = [s for s in after if s not in before]
if not new:
    print("FEHLER: kein neuer Slot aufgetaucht")
    raise SystemExit(1)
slot = new[0]
print(f"virtueller Pad -> Slot {slot}")

# Werte setzen und ueber XInput zurueckcheck: schliesst den Kreis.
pad.report.wButtons = 0x1000 | 0x0008      # A + dpad_right
pad.report.bRightTrigger = 140
pad.report.sThumbLX = -23170
pad.report.sThumbLY = 23170
pad.update()
time.sleep(0.3)

got = xr.read(slot)
print("zurueckgelesen:", got)

ok = (
    got.buttons == {"a", "dpad_right"}
    and got.rt == 140
    and abs(got.lx - (-23170)) < 300
    and abs(got.ly - 23170) < 300
)
print("ROUNDTRIP:", "OK" if ok else "ABWEICHUNG")
pad.reset(); pad.update()
raise SystemExit(0 if ok else 1)
