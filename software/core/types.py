"""Shared data types for the Crimson Veil suite.

These are plain dataclasses (stdlib only) so that the interface contracts in
``software.interfaces`` never pull in numpy, pyserial, or any other heavy
dependency. Backends and solvers may convert these to their own representations
internally, but the wire between the suite and its backends is these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Measurement:
    """One tetrapolar measurement: a drive pair and a disjoint sense pair.

    Used by the simulated front end to model a phantom reading; the real front
    end owns its own scan sequence and does not send measurements to the host.
    """

    freq_hz: float
    drive: tuple[int, int]
    sense: tuple[int, int]


@dataclass(frozen=True)
class RawPoint:
    """A single measured complex impedance point, before calibration."""

    freq_hz: float
    real: float
    imag: float

    @property
    def magnitude(self) -> float:
        return (self.real**2 + self.imag**2) ** 0.5

    @property
    def phase(self) -> float:
        import math

        return math.atan2(self.imag, self.real)


@dataclass
class ScanData:
    """A full frame of raw measurements from one scan.

    ``points`` are in the front end's standard adjacent order (the front end
    owns the scan plan). ``baseline`` frames (plain saline, no simulated bleed)
    are stored separately so the solver can difference against them.
    """

    points: list[RawPoint] = field(default_factory=list)
    label: str = ""
    n_electrodes: int = 0
    frequency_hz: float = 0.0

    def __len__(self) -> int:
        return len(self.points)


@dataclass
class ConductivityMap:
    """A reconstructed 2D conductivity distribution.

    ``values`` is row-major [y][x], one float per pixel (arbitrary units).
    Kept as plain lists so this type stays dependency-free.
    """

    values: list[list[float]] = field(default_factory=list)

    @property
    def height(self) -> int:
        return len(self.values)

    @property
    def width(self) -> int:
        return len(self.values[0]) if self.values else 0


@dataclass
class MeshConfig:
    """Mesh parameters handed to a solver during setup."""

    n_electrodes: int = 8
    shape: str = "circle"


@dataclass
class DeviceConfig:
    """Runtime configuration for opening a hardware backend.

    ``frequency_hz`` is the single excitation frequency for a scan (the front
    end runs one frequency per scan). ``options`` carries backend-specific
    settings (I2C address, serial port, GPIO profile, ...) so new backends can
    be added without changing this type.
    """

    backend: str = "sim"
    frequency_hz: float = 50_000.0
    options: dict = field(default_factory=dict)
