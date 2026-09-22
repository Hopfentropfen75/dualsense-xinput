"""DualSense -> virtueller Xbox-360-Controller.

Liest den DualSense per HID, uebersetzt nach XInput und schiebt das
Ergebnis ueber ViGEmBus in einen virtuellen Pad. Rumble laeuft zurueck.
"""

from __future__ import annotations

import argparse
import gc
import sys
import threading
import time

import vgamepad as vg

import xinput_ref as xr
from dualsense import DualSense, State
from mapping import Config, calibrate, map_state
from output import OutputChannel

# Farbe der Lightbar, solange die Bruecke laeuft.
ACTIVE_COLOR = (0, 60, 255)


class Bridge:
    def __init__(self, cfg: Config | None = None, quiet: bool = False):
        self.ds = DualSense()
        self.ds.enable_full_bt()
        self.cfg = cfg or Config()
        self.quiet = quiet
        # Belegte Slots merken, bevor der eigene Pad dazukommt - sonst
        # findet die Erkennung sich selbst in "vorher" wieder.
        self._slots_before = xr.connected()
        self.pad = vg.VX360Gamepad()
        self.out: OutputChannel | None = None
        self.slot: int | None = None
        # Von aussen setzbar (Tray-Menue), wird im Loop abgearbeitet.
        self.recalibrate_requested = False

        # Rumble kommt aus einem ViGEm-Thread; das HID-Handle gehoert dem
        # Hauptthread, also hier nur merken und dort senden.
        self._rumble = (0, 0)
        self._rumble_dirty = False
        self.pad.register_notification(callback_function=self._on_notification)

    def _on_notification(self, client, target, large_motor, small_motor,
                         led_number, user_data):
        if (large_motor, small_motor) != self._rumble:
            self._rumble = (large_motor, small_motor)
            self._rumble_dirty = True

    def _first_state(self, timeout: float = 3.0) -> State:
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.ds.poll()
            if st:
                return st
            time.sleep(0.002)
        raise RuntimeError("Keine Input-Reports vom DualSense empfangen.")

    def calibrate(self, seconds: float = 1.0) -> None:
        self._first_state()
        self.out = OutputChannel(self.ds.dev, self.ds.bluetooth)
        if not self.quiet:
            print(f"Kalibriere {seconds:.0f}s - Controller nicht anfassen ...")
        samples: list[State] = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            st = self.ds.poll()
            if st:
                samples.append(st)
            time.sleep(0.002)
        centers = calibrate(samples)
        # Wird beim Start ein Stick gehalten, waere dieser Punkt als "Mitte"
        # fatal: der Stick haette dann in die Gegenrichtung Vollausschlag.
        held = [ax for ax, v in centers.items() if abs(v - 128) > 25]
        if held:
            if not self.quiet:
                print(f"  Achtung: {', '.join(held)} weit ausgelenkt - Stick "
                      f"beim Start gehalten? Nehme Werksmitte.")
            for ax in held:
                centers[ax] = 128
        self.cfg.center = centers
        if not self.quiet:
            print(f"Mittelpunkte: {self.cfg.center}  ({len(samples)} Samples)")

    def _prime(self) -> None:
        """ViGEm uebernimmt nur Reports, die sich vom vorigen unterscheiden.
        Der Default-Report ist bereits Null - liegt der DualSense in Ruhe,
        schicken wir also nur Nullen und der Pad bliebe auf seinem
        uninitialisierten Startzustand haengen. Einmal anstossen."""
        self.pad.report.sThumbLX = 1
        self.pad.update()
        time.sleep(0.02)
        self.pad.reset()
        self.pad.update()
        time.sleep(0.02)

    def _detect_slot(self) -> None:
        for _ in range(50):
            new = [s for s in xr.connected() if s not in self._slots_before]
            if new:
                self.slot = new[0]
                return
            time.sleep(0.05)

    def _flush_rumble(self) -> None:
        if not self._rumble_dirty or self.out is None:
            return
        large, small = self._rumble
        try:
            self.out.send(self.out.new().rumble(large, small)
                          .lightbar(*ACTIVE_COLOR))
        except OSError:
            pass
        self._rumble_dirty = False

    def run(self, duration: float | None = None,
            stop: threading.Event | None = None) -> None:
        self.calibrate()
        self._detect_slot()
        self._prime()
        if self.out:
            self.out.send(self.out.new().lightbar(*ACTIVE_COLOR).player_leds(0x04))

        link = "Bluetooth" if self.ds.bluetooth else "USB"
        if not self.quiet:
            print(f"\nDualSense ({link}) -> virtueller Xbox-Pad"
                  f"{f' auf XInput-Slot {self.slot}' if self.slot is not None else ''}")
            print("Strg+C zum Beenden.\n")

        end = time.time() + duration if duration else None
        last_draw = 0.0
        try:
            while (end is None or time.time() < end) and not (
                    stop is not None and stop.is_set()):
                if self.recalibrate_requested:
                    self.recalibrate_requested = False
                    self.calibrate()

                st = self.ds.poll()
                if st:
                    x = map_state(st, self.cfg)
                    r = self.pad.report
                    r.wButtons = x.buttons
                    r.bLeftTrigger = x.lt
                    r.bRightTrigger = x.rt
                    r.sThumbLX, r.sThumbLY = x.lx, x.ly
                    r.sThumbRX, r.sThumbRY = x.rx, x.ry
                    self.pad.update()

                    now = time.time()
                    if not self.quiet and now - last_draw > 0.05:
                        last_draw = now
                        sys.stdout.write(
                            f"\rL({x.lx:6d},{x.ly:6d}) R({x.rx:6d},{x.ry:6d}) "
                            f"LT {x.lt:3d} RT {x.rt:3d} "
                            f"rumble {self._rumble[0]:3d}/{self._rumble[1]:3d} | "
                            f"{' '.join(sorted(x.names())) or '-':<46}"
                        )
                        sys.stdout.flush()

                self._flush_rumble()
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def close(self) -> None:
        try:
            self.pad.reset()
            self.pad.update()
        except Exception:
            pass
        # vgamepad entfernt den virtuellen Pad erst im Destruktor. Der
        # Rumble-Callback haelt aber eine Referenz auf die Bruecke und die
        # Bruecke eine auf den Pad - ein Zyklus, den das Refcounting nicht
        # aufloest. Ohne das hier bliebe bei jedem Neustart ein Pad stehen,
        # und das Spiel saehe wieder mehrere Controller.
        try:
            self.pad.cmp_func = None
            pad, self.pad = self.pad, None
            del pad
            gc.collect()
        except Exception:
            pass
        if self.out:
            try:
                self.out.send(self.out.new().rumble(0, 0).lightbar(0, 0, 0))
            except OSError:
                pass
        self.ds.close()
        if not self.quiet:
            print("\nbeendet.")


def main() -> int:
    ap = argparse.ArgumentParser(description="DualSense als Xbox-Controller")
    ap.add_argument("--seconds", type=float, default=None,
                    help="nach N Sekunden automatisch beenden")
    ap.add_argument("--deadzone", type=float, default=0.08)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    cfg = Config(left_deadzone=a.deadzone, right_deadzone=a.deadzone)
    try:
        Bridge(cfg, quiet=a.quiet).run(duration=a.seconds)
    except RuntimeError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
