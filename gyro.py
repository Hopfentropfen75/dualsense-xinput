"""Gyro-Zielen: Drehbewegung des Controllers wird zum rechten Stick.

Der rechte Stick steuert in Spielen eine Drehgeschwindigkeit - also wird
die Drehrate des Controllers direkt als Stickausschlag weitergegeben.
Ruhig gehalten gibt es keinen Ausschlag; kleine Bewegungen werden auf
einen Mindestausschlag angehoben, sonst schluckt sie die Deadzone des
Spiels.
"""

from __future__ import annotations

import math

from dualsense import State
from mapping import XPad

# Rohwert pro Grad/s (Messbereich +-2000 dps auf 16 Bit).
LSB_PER_DPS = 16.4
# Darunter gilt der Controller als ruhig - filtert Sensorrauschen.
REST_DPS = 1.5
# Bei Empfindlichkeit 1 ergibt diese Drehrate vollen Stickausschlag.
FULL_DPS = 150.0
# L2 ab diesem Rohwert = "zielt gerade".
AIM_THRESHOLD = 50


class GyroAim:
    def __init__(self):
        self.bias = (0.0, 0.0, 0.0)

    def calibrate(self, samples: list[State]) -> None:
        """Ruhelage des Sensors - laeuft mit der Stick-Kalibrierung."""
        if samples:
            n = len(samples)
            self.bias = tuple(sum(s.gyro[i] for s in samples) / n
                              for i in range(3))

    def apply(self, st: State, x: XPad, p: dict) -> bool:
        """Addiert die Gyro-Bewegung auf den rechten Stick. True, wenn aktiv."""
        mode = p.get("gyro", "aus")
        if mode == "aus" or (mode == "l2" and st.l2 < AIM_THRESHOLD):
            return False
        pitch = (st.gyro[0] - self.bias[0]) / LSB_PER_DPS
        yaw = (st.gyro[1] - self.bias[1]) / LSB_PER_DPS
        # Nach links drehen = positive Gierrate, soll aber nach links zielen.
        gx, gy = -yaw, pitch
        if p.get("gyro_invert_x"):
            gx = -gx
        if p.get("gyro_invert_y"):
            gy = -gy
        mag = math.hypot(gx, gy)
        if mag < REST_DPS:
            return True
        sens = float(p.get("gyro_sensitivity", 1.0))
        lo = float(p.get("gyro_min", 0.15))
        v = min(1.0, (mag - REST_DPS) * sens / FULL_DPS)
        out = lo + (1.0 - lo) * v
        rx = x.rx / 32767 + gx / mag * out
        ry = x.ry / 32767 + gy / mag * out
        # Zusammen mit dem echten Stick nicht ueber den Rand hinaus.
        m = math.hypot(rx, ry)
        if m > 1.0:
            rx, ry = rx / m, ry / m
        x.rx = max(-32768, min(32767, round(rx * 32767)))
        x.ry = max(-32768, min(32767, round(ry * 32767)))
        return True
