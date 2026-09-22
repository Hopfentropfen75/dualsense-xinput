import time, xinput_ref as xr
print("Slots:", xr.connected())
for i in range(6):
    for s in xr.connected():
        st = xr.read(s)
        print(f"  t={i} slot{s}: L({st.lx:6d},{st.ly:6d}) R({st.rx:6d},{st.ry:6d}) "
              f"LT{st.lt:3d} RT{st.rt:3d} pkt={st.packet} btn={sorted(st.buttons)}")
    print()
    time.sleep(1.0)
