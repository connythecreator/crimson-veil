"""Measurement sequencing.

Builds the ordered list of tetrapolar measurements to run. Uses the adjacent
drive pattern from ``docs/eit-bioimpedance/SENSOR-PLACEMENT.md``:

    drive+ = e,  drive- = e+4,  sense+ = e+2,  sense- = e+6   (mod N)

rotated through all electrodes, for a set of excitation frequencies.
"""

from __future__ import annotations

from ..core.types import Measurement
from . import electrode


def adjacent_drive_plan(
    frequencies_hz: list[float],
    n_electrodes: int = electrode.N_ELECTRODES,
) -> list[Measurement]:
    """Return the full plan of measurements for one frame.

    For each electrode index ``e`` the pattern uses four distinct electrodes
    (``e``, ``e+2``, ``e+4``, ``e+6`` mod N), so this is inherently valid for
    N a multiple of 4 (8 here). Each is measured once per frequency.
    """
    plan: list[Measurement] = []
    for freq in frequencies_hz:
        for e in range(n_electrodes):
            drive = (e % n_electrodes, (e + 4) % n_electrodes)
            sense = ((e + 2) % n_electrodes, (e + 6) % n_electrodes)
            electrode.validate(drive, sense, n_electrodes)
            plan.append(Measurement(freq_hz=freq, drive=drive, sense=sense))
    return plan
