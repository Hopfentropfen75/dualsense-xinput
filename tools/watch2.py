import time, xinput_ref as xr
slots = xr.connected()
print("Slots:", slots)
base = {s: xr.read(s).packet for s in slots}
seen = {s: set() for s in slots}
t0 = time.time()
while time.time() - t0 < 8:
    for s in slots:
        st = xr.read(s)
        if st: seen[s].add((st.lx, st.ly, st.rx, st.ry, st.lt, st.rt, st.buttons and 1 or 0))
    time.sleep(0.02)
for s in slots:
    st = xr.read(s)
    print(f"slot{s}: pkt {base[s]} -> {st.packet} (delta {st.packet-base[s]}), "
          f"{len(seen[s])} verschiedene Zustaende, jetzt L({st.lx},{st.ly}) R({st.rx},{st.ry})")
