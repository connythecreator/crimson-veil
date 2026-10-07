"""Hardware backend contract.

The suite talks to *whatever* acquires measurements through this interface. It
is deliberately transport-agnostic: a Raspberry Pi driving the AD5933 and muxes
directly, a Pi talking to an ESP32 over serial, or a future network node are all
just implementations of :class:`HardwareBackend`. Nothing above this layer knows
which one is in use.

The front end owns the scan process: it decides the electrode pairs and their
order. The host asks for a scan and receives one frame. Implementations live in
``hardware/`` (the ESP32 over serial) and ``software/sim/`` (laptop/CI). This
module imports stdlib typing only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..core.types import DeviceConfig, RawPoint


@runtime_checkable
class HardwareBackend(Protocol):
    """Acquires one raw impedance frame from the physical front end."""

    def open(self, cfg: DeviceConfig) -> None:
        """Initialise the transport and hardware. Raises on failure."""
        ...

    def identify(self) -> str:
        """Human-readable identity, e.g. ``"ad5933@0x0D"`` or ``"esp32:/dev/ttyACM0"``."""
        ...

    def scan(self) -> list[RawPoint]:
        """Run one single-shot scan and return the frame.

        The front end owns the electrode pairing and ordering (the firmware's
        standard adjacent sequence), so the returned points are in the order the
        solver expects. ``n_electrodes`` is reported on ``hello``.
        """
        ...

    def close(self) -> None:
        """Release the transport and hardware resources."""
        ...
