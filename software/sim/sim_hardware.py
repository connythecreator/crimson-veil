"""Simulated hardware backend.

Implements the :class:`~software.interfaces.hardware.HardwareBackend` contract
without any physical hardware, so the full suite runs on a laptop or in CI. It
is selected when ``config.HARDWARE_BACKEND == "sim"``.

Like the ESP32, the simulator is the *front end*: it owns the scan sequence and
generates a full frame itself. The host never sends it a plan.
"""

from __future__ import annotations

import time

from ..core import config
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
        self.n_electrodes = config.N_ELECTRODES
        self.frequency_hz = 50_000.0

    def open(self, cfg: DeviceConfig) -> None:
        self._open = True
        self.frequency_hz = float(cfg.frequency_hz)

    def identify(self) -> str:
        return "sim:phantom" + ("" if self.include_bleed else ":baseline")

    def _measurement_pairs(self) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """The simulator's own scan sequence (stand-in for the firmware's)."""
        n = self.n_electrodes
        pairs = []
        for e in range(n):
            drive = (e, (e + 1) % n)
            for k in range(n - 3):
                sense = ((e + 2 + k) % n, (e + 3 + k) % n)
                pairs.append((drive, sense))
        return pairs

    def scan(self) -> list[RawPoint]:
        if not self._open:
            raise RuntimeError("SimHardware.scan called before open()")

        points: list[RawPoint] = []
        for drive, sense in self._measurement_pairs():
            m = Measurement(freq_hz=self.frequency_hz, drive=drive, sense=sense)
            z = phantom.impedance_for(m, include_bleed=self.include_bleed)
            time.sleep(PER_MEASUREMENT_SECONDS)
            points.append(RawPoint(freq_hz=self.frequency_hz, real=z.real, imag=z.imag))
        return points

    def close(self) -> None:
        self._open = False
