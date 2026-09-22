"""Prueft: liegt der virtuelle Pad nach dem Start sauber auf Null?"""
import time, vgamepad as vg, xinput_ref as xr

before = xr.connected()
pad = vg.VX360Gamepad()
time.sleep(0.8)
slot = [s for s in xr.connected() if s not in before][0]
print("vor prime :", xr.read(slot))

pad.report.sThumbLX = 1
pad.update(); time.sleep(0.05)
pad.reset(); pad.update(); time.sleep(0.05)

st = xr.read(slot)
print("nach prime:", st)
ok = (st.lx, st.ly, st.rx, st.ry, st.lt, st.rt, st.buttons) == (0, 0, 0, 0, 0, 0, set())
print("NULLLAGE:", "OK" if ok else "FEHLT")
raise SystemExit(0 if ok else 1)
