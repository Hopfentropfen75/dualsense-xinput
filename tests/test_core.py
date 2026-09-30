"""Tests fuer alles, was ohne Controller und ohne ViGEm pruefbar ist.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import math
import socket
import struct
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import output                                         # noqa: E402
import rangecheck                                     # noqa: E402
import settings                                       # noqa: E402
import triggers                                       # noqa: E402
from dualsense import State, decode                   # noqa: E402
from gyro import LSB_PER_DPS, GyroAim                 # noqa: E402
from mapping import (XINPUT_MASKS, Config, XPad, _apply_deadzone,  # noqa: E402
                     _trigger, map_state)
from telemetry import Telemetry                       # noqa: E402


class Mapping(unittest.TestCase):
    def test_deadzone_cuts_and_rescales(self):
        self.assertEqual(_apply_deadzone(0.05, 0, 0.08), (0.0, 0.0))
        x, _ = _apply_deadzone(0.5, 0, 0.08)
        self.assertAlmostEqual(x, (0.5 - 0.08) / 0.92)
        self.assertAlmostEqual(_apply_deadzone(1.0, 0, 0.08)[0], 1.0)

    def test_outer_zone_reaches_full_early(self):
        x, _ = _apply_deadzone(0.96, 0, 0.0, outer=0.04)
        self.assertAlmostEqual(x, 1.0)

    def test_anti_deadzone_jumps_to_threshold(self):
        x, _ = _apply_deadzone(0.081, 0, 0.08, anti=0.2)
        self.assertGreaterEqual(x, 0.2)

    def test_direction_is_kept(self):
        x, y = _apply_deadzone(0.5, 0.5, 0.1)
        self.assertAlmostEqual(math.atan2(y, x), math.pi / 4)

    def test_trigger_deadzone_and_curve(self):
        self.assertEqual(_trigger(5, 0.03, 1.0), 0)
        self.assertEqual(_trigger(255, 0.03, 2.0), 255)
        self.assertLess(_trigger(128, 0.0, 2.0), _trigger(128, 0.0, 1.0))
        self.assertEqual(_trigger(77, 0.0, 1.0), 77)   # unveraendert

    def test_map_state_buttons_and_inverted_y(self):
        st = State(ly=0, l2=255)
        st.buttons = {"cross", "options"}
        st.dpad = "NE"
        x = map_state(st, Config(left_deadzone=0.0))
        for name in ("a", "start", "dpad_up", "dpad_right"):
            self.assertTrue(x.buttons & XINPUT_MASKS[name], name)
        self.assertGreater(x.ly, 30000)              # Stick hoch = +Y
        self.assertEqual(x.lt, 255)


class Decode(unittest.TestCase):
    def _usb(self, kv: dict):
        r = bytearray(64)
        r[0] = 0x01
        r[1:5] = bytes([128, 128, 128, 128])
        for k, v in kv.items():
            r[k] = v
        return bytes(r)

    def test_usb_report(self):
        st = decode(self._usb({1: 10, 5: 200, 8: 0x28, 53: 0x15}))
        self.assertEqual((st.lx, st.l2), (10, 200))
        self.assertIn("cross", st.buttons)
        self.assertEqual(st.dpad, "none")            # Hat 8 = nicht gedrueckt
        self.assertTrue(st.charging)
        self.assertEqual(st.battery_percent, 55)

    def test_unknown_report_is_ignored(self):
        self.assertIsNone(decode(bytes([0x01] + [0] * 9)))


class OutputReports(unittest.TestCase):
    def test_usb_layout(self):
        b = (output.OutputReport(False, True).rumble(200, 100)
             .triggers(triggers.feedback(3, 6), triggers.feedback(1, 2))
             .lightbar(1, 2, 3).player_leds(4).finish())
        p = 1
        self.assertEqual(len(b), output.USB_OUT_SIZE)
        self.assertEqual(b[0], output.USB_OUT_ID)
        self.assertEqual(b[p + 0], 0x0E)             # Haptik + beide Trigger
        self.assertEqual(b[p + 38], 0x04)            # Vibration v2
        self.assertEqual((b[p + 2], b[p + 3]), (100, 200))
        self.assertEqual(b[p + 10], 0x21)            # R2-Effekt
        self.assertEqual(b[p + 21], 0x21)            # L2-Effekt
        self.assertEqual(b[p + 43], 4)
        self.assertEqual(tuple(b[p + 44:p + 47]), (1, 2, 3))

    def test_bluetooth_crc(self):
        b = output.OutputReport(True).lightbar(0, 60, 255).finish(seq=5)
        self.assertEqual(len(b), output.BT_OUT_SIZE)
        self.assertEqual(b[1] >> 4, 5)
        crc = zlib.crc32(bytes([output.BT_CRC_SEED]))
        crc = zlib.crc32(b[:-4], crc)
        self.assertEqual(b[-4:], crc.to_bytes(4, "little"))

    def test_old_firmware_uses_classic_rumble(self):
        b = output.OutputReport(False, False).rumble(1, 1).finish()
        self.assertEqual(b[1] & 0x03, 0x03)
        self.assertEqual(b[1 + 38], 0)


class Triggers(unittest.TestCase):
    def test_encodings(self):
        self.assertEqual(triggers.feedback(3, 6).hex(), "21f80300dab62d00000000")
        self.assertEqual(triggers.weapon(4, 6, 6).hex(), "25500005000000000000"
                                                         "00")
        v = triggers.vibration(1, 8, 40)
        self.assertEqual((v[0], v[9]), (0x26, 40))
        self.assertEqual(len(triggers.off()), 11)

    def test_build_modes(self):
        p = dict(settings.PROFILE_DEFAULTS)
        self.assertEqual(triggers.build(p).left, triggers.off())
        p["triggers"] = "racing_live"
        s = triggers.build(p)
        self.assertTrue(s.live)
        self.assertEqual(s.left[0], 0x21)

    def test_abs_estimate_without_telemetry(self):
        s = triggers.build({**settings.PROFILE_DEFAULTS,
                            "triggers": "racing_live"})
        a, _ = s.levels((200, 50), l2=220, r2=0, tele=None)
        self.assertGreater(a, 0)
        self.assertEqual(s.effects((200, 50), 220, 0, None)[0][0], 0x26)
        self.assertEqual(s.levels((0, 0), l2=220)[0], 0)   # kein Rumble

    def test_abs_from_telemetry(self):
        class Tele:
            fresh, speed = True, 30.0
            slip = (0.2, 0.3, 0.3, 0.2)
        s = triggers.build({**settings.PROFILE_DEFAULTS,
                            "triggers": "racing_live"})
        self.assertEqual(s.levels(l2=200, tele=Tele)[0], 0)
        Tele.slip = (1.5, 1.2, 0.3, 0.2)
        self.assertGreater(s.levels(l2=200, tele=Tele)[0], 0)
        Tele.slip = (0.1, 0.1, 1.8, 1.7)
        self.assertGreater(s.levels(r2=255, tele=Tele)[1], 0)


class Settings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = settings.PATH
        settings.PATH = Path(self.tmp.name) / "settings.json"

    def tearDown(self):
        settings.PATH = self.old
        self.tmp.cleanup()

    def test_defaults(self):
        d = settings.load()
        self.assertEqual(set(d["profiles"]), {"Standard", "Forza", "Shooter"})

    def test_migrates_old_formats(self):
        settings.PATH.write_text(json.dumps({"trigger_profile": "racing"}))
        self.assertEqual(settings.load()["active"], "Forza")
        settings.PATH.write_text(json.dumps({"active": "A", "profiles": {
            "A": {"trigger_deadzone": 0.05, "trigger_curve": 2.0}}}))
        a = settings.load()["profiles"]["A"]
        self.assertEqual((a["l2_deadzone"], a["r2_curve"]), (0.05, 2.0))
        self.assertNotIn("trigger_deadzone", a)

    def test_update_profile_roundtrip(self):
        settings.update_profile("Forza", brake_force=8)
        self.assertEqual(settings.load()["profiles"]["Forza"]["brake_force"], 8)

    def test_effective_prefers_running_game(self):
        d = settings.load()
        self.assertEqual(settings.effective(d, "Forza"), "Forza")
        d["auto_game"] = False
        self.assertEqual(settings.effective(d, "Forza"), d["active"])


class Gyro(unittest.TestCase):
    def test_only_while_aiming(self):
        g = GyroAim()
        p = {**settings.PROFILE_DEFAULTS, "gyro": "l2"}
        st = State()
        st.gyro = (0, int(-60 * LSB_PER_DPS), 0)   # nach rechts drehen
        x = XPad()
        self.assertFalse(g.apply(st, x, p))
        st.l2 = 200
        self.assertTrue(g.apply(st, x, p))
        self.assertGreater(x.rx, 0)

    def test_rest_is_quiet(self):
        g = GyroAim()
        st = State(l2=200)
        st.gyro = (5, -5, 0)
        x = XPad()
        g.apply(st, x, {**settings.PROFILE_DEFAULTS, "gyro": "immer"})
        self.assertEqual((x.rx, x.ry), (0, 0))


class Reach(unittest.TestCase):
    def test_recommend(self):
        left, right = rangecheck.Reach(), rangecheck.Reach()
        for i in range(64):
            a = i / 64 * 2 * math.pi
            left.add(math.cos(a), math.sin(a))
            right.add(0.95 * math.cos(a), 0.95 * math.sin(a))
        self.assertAlmostEqual(rangecheck.recommend(left, right), 0.06, 2)

    def test_incomplete_circle(self):
        r = rangecheck.Reach()
        r.add(1, 0)
        self.assertIsNone(rangecheck.recommend(r, r))


class TelemetryUdp(unittest.TestCase):
    def test_parses_forza_packet(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        t = Telemetry(port)
        try:
            b = bytearray(324)
            struct.pack_into("<i", b, 0, 1)
            struct.pack_into("<3f", b, 32, 3.0, 0.0, 4.0)
            struct.pack_into("<4f", b, 84, 0.1, 0.2, 1.5, 0.3)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(bytes(b), ("127.0.0.1", port))
            deadline = time.time() + 2
            while not t.fresh and time.time() < deadline:
                time.sleep(0.02)
            self.assertTrue(t.fresh)
            self.assertAlmostEqual(t.speed, 5.0, places=4)
            self.assertAlmostEqual(t.slip[2], 1.5, places=4)
        finally:
            t.close()


if __name__ == "__main__":
    unittest.main()
