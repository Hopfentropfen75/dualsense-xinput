"""Isoliert: schreibt bekannte Werte und liest im selben Prozess zurueck."""
import time
import vgamepad as vg
import xinput_ref as xr

def snap(tag):
    print(f"  [{tag}] " + " | ".join(
        f"s{s}:L({x.lx},{x.ly}) pkt={x.packet}"
        for s in range(4) if (x := xr.read(s))))

print("vorher:", xr.connected()); snap("vorher")

pad = vg.VX360Gamepad()
time.sleep(0.8)
print("nach create:", xr.connected()); snap("create")

def cb(client, target, large_motor, small_motor, led_number, user_data):
    pass

pad.register_notification(callback_function=cb)
time.sleep(0.5)
print("nach register_notification:", xr.connected()); snap("register")

for val in (5000, -20000, 0):
    pad.report.sThumbLX = val
    pad.report.sThumbLY = val // 2
    pad.update()
    time.sleep(0.5)
    snap(f"wrote LX={val}")

print("\nGegenprobe ohne Notification:")
pad2 = vg.VX360Gamepad()
time.sleep(0.8)
pad2.report.sThumbLX = 12345
pad2.update()
time.sleep(0.5)
snap("pad2 LX=12345")
