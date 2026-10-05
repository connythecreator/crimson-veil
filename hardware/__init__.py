"""Hardware backends for the Crimson Veil suite.

The physical front end is driven by an ESP32, which implements
:class:`software.interfaces.hardware.HardwareBackend` by talking over USB
serial. See :mod:`hardware.esp32`.
"""

from __future__ import annotations

__all__ = ["esp32"]
