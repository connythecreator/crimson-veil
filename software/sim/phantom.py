"""Synthetic saline phantom used by the simulated hardware backend.

Represents the physical phantom described in ``docs/eit-bioimpedance``: a
circular conductive body with a high-conductivity inclusion (a simulated bleed).
The real front end never sees this module; it exists only to make the suite
run end-to-end on a laptop.
"""

from __future__ import annotations

import math

from ..core.types import ConductivityMap, Measurement

WIDTH = 256
HEIGHT = 256
BACKGROUND = 12.0        # outside the body
TISSUE = 90.0            # saline background conductivity
INCLUSION = 230.0        # simulated bleed (high conductivity)
BLEND = 150.0            # partial-volume edge


def _geometry() -> tuple[float, float, float, float, float, float]:
    cx, cy = WIDTH / 2.0, HEIGHT / 2.0
    body_r = min(WIDTH, HEIGHT) * 0.42
    inclusion_r = min(WIDTH, HEIGHT) * 0.16
    inc_cx, inc_cy = cx + WIDTH * 0.12, cy - HEIGHT * 0.10
    return cx, cy, body_r, inc_cx, inc_cy, inclusion_r


def ground_truth(include_bleed: bool = True) -> ConductivityMap:
    """Render the phantom's conductivity map."""
    cx, cy, body_r, inc_cx, inc_cy, inclusion_r = _geometry()
    values: list[list[float]] = []
    for y in range(HEIGHT):
        row: list[float] = []
        for x in range(WIDTH):
            if math.hypot(x - cx, y - cy) > body_r:
                row.append(BACKGROUND)
                continue
            value = TISSUE
            if include_bleed:
                d = math.hypot(x - inc_cx, y - inc_cy)
                if d < inclusion_r:
                    value = INCLUSION
                elif d < inclusion_r * 1.25:
                    value = BLEND
            row.append(value)
        values.append(row)
    return ConductivityMap(values=values)


def impedance_for(measurement: Measurement, include_bleed: bool = True) -> complex:
    """Fake a complex impedance for one tetrapolar measurement.

    A crude model: a baseline tissue impedance that drops when the drive/sense
    span crosses the inclusion, plus mild frequency dispersion. Good enough to
    exercise the pipeline and produce visibly different frames with/without a
    simulated bleed.
    """
    e0, e1 = measurement.drive
    s0, s1 = measurement.sense

    # Angular position of electrodes on the ring (8 evenly spaced).
    def angle(i: int) -> float:
        return 2.0 * math.pi * i / 8.0

    # Approximate whether the measurement chord passes near the inclusion.
    mid_drive = (angle(e0) + angle(e1)) / 2.0
    mid_sense = (angle(s0) + angle(s1)) / 2.0
    bleed_angle = math.atan2(-0.10, 0.12)  # direction of the inclusion
    proximity = math.cos(mid_sense - bleed_angle) * math.cos(mid_drive - bleed_angle)

    base = 1000.0
    if include_bleed:
        # Bleed pools near one side: lower impedance where the span crosses it.
        base -= 180.0 * max(0.0, proximity)

    # Mild frequency dispersion (reactance grows with frequency).
    f = measurement.freq_hz
    real = base
    imag = -base * (0.05 + 0.15 * (f / 100_000.0))
    return complex(real, imag)
