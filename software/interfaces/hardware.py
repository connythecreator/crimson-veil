"""Hardware backend contract.

The suite talks to *whatever* acquires measurements through this interface. It
is deliberately transport-agnostic: a Raspberry Pi driving the AD5933 and muxes
directly, a Pi talking to an ESP32 over serial, or a future network node are all
just implementations of :class:`HardwareBackend`. Nothing above this layer knows
which one is in use.

Implementations live elsewhere (``hardware/`` once written; ``software/sim/``
for the laptop/CI simulated backend). This module imports stdlib typing only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..core.types import DeviceConfig, Measurement, RawPoint


@runtime_checkable
class HardwareBackend(Protocol):
    """Acquires raw impedance measurements from the physical front end."""

    def open(self, cfg: DeviceConfig) -> None:
        """Initialise the transport and hardware. Raises on failure."""
        ...

    def identify(self) -> str:
        """Human-readable identity, e.g. ``"ad5933@0x0D"`` or ``"esp32:/dev/ttyUSB0"``."""
        ...

    def measure(self, plan: Sequence[Measurement]) -> list[RawPoint]:
        """Execute ``plan`` and return one :class:`RawPoint` per measurement.

        The returned list must align index-for-index with ``plan``.
        """
        ...

    def close(self) -> None:
        """Release the transport and hardware resources."""
        ...
