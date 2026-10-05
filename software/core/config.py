"""Suite configuration.

Central place for selecting the hardware backend, solver backend, and scan
parameters. ``main.py`` reads this at boot; ``dev.py`` may override fields.

Defaults target a development laptop: the ``sim`` backend runs with no hardware.
On the device the ESP32 is the primary interface and is selected with
``CV_BACKEND=esp32``; install ``requirements-pi.txt`` for the serial transport.
"""

from __future__ import annotations

import os

from .types import DeviceConfig, MeshConfig

# "sim"   -> software.sim.sim_hardware (no hardware, laptop/CI)
# "esp32" -> hardware.esp32 (the ESP32 over USB serial; the device default)
HARDWARE_BACKEND = os.environ.get("CV_BACKEND", "sim")

# "stub" -> software.sim.stub_solver (placeholder image)
# "pyeit" -> real reconstruction (TODO)
SOLVER_BACKEND = os.environ.get("CV_SOLVER", "stub")

# AD5933 ceiling is ~100 kHz, so the research-recommended 300-500 kHz points
# are NOT reachable on the current front end. Keep every point <= 100 kHz.
DEFAULT_FREQUENCIES_HZ = [5_000.0, 20_000.0, 50_000.0, 75_000.0, 100_000.0]

# The ESP32 is authoritative for the electrode count and pairing; this value is
# only a fallback used by the sim backend and before the ESP32 handshake.
N_ELECTRODES = 8

# USB serial to the ESP32.
ESP32_PORT = os.environ.get("CV_ESP32_PORT", "/dev/ttyACM0")
ESP32_BAUD = int(os.environ.get("CV_ESP32_BAUD", "115200"))

# Kiosk display: typical 3.5" Raspberry Pi panel (unused by the Rust kiosk,
# which is 800x480; kept for reference/tools).
KIOSK_WIDTH = 480
KIOSK_HEIGHT = 320


def device_config(backend: str | None = None) -> DeviceConfig:
    """Build a :class:`DeviceConfig` from the current suite settings."""
    return DeviceConfig(
        backend=backend or HARDWARE_BACKEND,
        frequencies_hz=list(DEFAULT_FREQUENCIES_HZ),
        settle_cycles=15,
        options={"port": ESP32_PORT, "baud": ESP32_BAUD},
    )


def mesh_config() -> MeshConfig:
    return MeshConfig(n_electrodes=N_ELECTRODES, shape="circle")
