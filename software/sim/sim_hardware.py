"""Simulated hardware backend.

Implements the :class:`~software.interfaces.hardware.HardwareBackend` contract
without any physical hardware, so the full suite runs on a laptop or in CI. It
is selected when ``config.HARDWARE_BACKEND == "sim"``.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from ..acquisition import electrode
from ..core.types import DeviceConfig, Measurement, RawPoint
from . import phantom

# Simulated per-measurement acquisition time (keeps the spinner visible).
PER_MEASUREMENT_SECONDS = 0.02


class SimHardware:
    """In-memory stand-in for the AD5933 + multiplexer front end."""

    def __init__(self, include_bleed: bool = True) -> None:
        self.include_bleed = include_bleed
        self._open = False
        # Mirrors the ESP32 contract: the backend reports its electrode count.
        self.n_electrodes = electrode.N_ELECTRODES

    def open(self, cfg: DeviceConfig) -> None:
        self._open = True

    def identify(self) -> str:
        return "sim:phantom" + ("" if self.include_bleed else ":baseline")

    def measure(self, plan: Sequence[Measurement]) -> list[RawPoint]:
        if not self._open:
            raise RuntimeError("SimHardware.measure called before open()")

        points: list[RawPoint] = []
        for m in plan:
            z = phantom.impedance_for(m, include_bleed=self.include_bleed)
            time.sleep(PER_MEASUREMENT_SECONDS)
            points.append(RawPoint(freq_hz=m.freq_hz, real=z.real, imag=z.imag))
        return points

    def close(self) -> None:
        self._open = False
