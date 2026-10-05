"""Gain/phase calibration against known resistors.

Scaffold. The external analog front end (Howland + AD623) adds gain and phase
error that must be corrected against known impedances before measurements are
trustworthy (``docs/eit-bioimpedance/eit-netlist.md`` §8 step 7).

Real implementation is deferred until the hardware backend exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.types import RawPoint


@dataclass
class CalibrationTable:
    """Per-frequency complex correction factor: measured = actual * factor."""

    factors: dict[float, complex]

    def apply(self, point: RawPoint) -> RawPoint:
        factor = self.factors.get(point.freq_hz, complex(1.0, 0.0))
        z = complex(point.real, point.imag) / factor
        return RawPoint(freq_hz=point.freq_hz, real=z.real, imag=z.imag)


def identity_table(frequencies_hz: list[float]) -> CalibrationTable:
    """No-op calibration (unity factor at every frequency)."""
    return CalibrationTable({f: complex(1.0, 0.0) for f in frequencies_hz})


def build_table(known: dict[float, complex], measured: dict[float, complex]) -> CalibrationTable:
    """Build a correction table from known vs measured impedances."""
    factors = {
        f: (measured[f] / known[f]) if known.get(f) else complex(1.0, 0.0)
        for f in measured
    }
    return CalibrationTable(factors)
