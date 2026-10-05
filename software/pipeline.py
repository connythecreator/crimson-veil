"""Scan pipeline: the suite's top-level operation.

Ties together sequencing, a hardware backend, calibration, and a solver:

    plan -> hardware.measure -> calibrate -> solver.reconstruct -> PNG bytes

``run_scan`` is the seam the kiosk app calls; it returns PNG bytes and knows
nothing about the GUI. It also knows nothing about *which* hardware or solver
is in use -- those are injected, defaulting to the configured backends.
"""

from __future__ import annotations

from .acquisition import calibration, sequence
from .core import config
from .core.types import ScanData
from .interfaces.hardware import HardwareBackend
from .interfaces.solver import SolverBackend
from .reconstruction.image import conductivity_to_png


def default_hardware() -> HardwareBackend:
    """Construct the configured hardware backend."""
    if config.HARDWARE_BACKEND == "sim":
        from .sim.sim_hardware import SimHardware

        return SimHardware()
    if config.HARDWARE_BACKEND == "esp32":
        from hardware.esp32 import Esp32Hardware

        return Esp32Hardware()
    raise NotImplementedError(
        f"hardware backend {config.HARDWARE_BACKEND!r} not implemented yet; "
        "see hardware/README.md"
    )


def default_solver() -> SolverBackend:
    """Construct the configured solver backend."""
    if config.SOLVER_BACKEND == "stub":
        from .sim.stub_solver import StubSolver

        return StubSolver()
    raise NotImplementedError(
        f"solver backend {config.SOLVER_BACKEND!r} not implemented yet"
    )


def acquire(
    hardware: HardwareBackend,
    frequencies_hz: list[float] | None = None,
) -> ScanData:
    """Run one frame: build the plan, measure, and calibrate.

    The scan plan (host-owned) is built for the electrode count the hardware
    reports, so an ESP32 that changes its ring size needs no host change.
    """
    freqs = frequencies_hz or list(config.DEFAULT_FREQUENCIES_HZ)
    n_electrodes = int(getattr(hardware, "n_electrodes", 0) or config.N_ELECTRODES)
    plan = sequence.adjacent_drive_plan(freqs, n_electrodes=n_electrodes)
    raw = hardware.measure(plan)

    table = calibration.identity_table(freqs)
    points = [table.apply(p) for p in raw]
    return ScanData(plan=plan, points=points, label=hardware.identify())


def run_scan(
    hardware: HardwareBackend | None = None,
    solver: SolverBackend | None = None,
    frequencies_hz: list[float] | None = None,
) -> bytes:
    """Run a full scan and return the reconstructed image as PNG bytes.

    If ``hardware``/``solver`` are not supplied, the configured defaults are
    created and closed here. If they are supplied (e.g. by ``main.py`` at boot),
    their lifecycle is the caller's responsibility.
    """
    owns_hardware = hardware is None
    owns_solver = solver is None

    if hardware is None:
        hardware = default_hardware()
        hardware.open(config.device_config())
    if solver is None:
        solver = default_solver()
        solver.setup(config.N_ELECTRODES, config.mesh_config())

    try:
        frame = acquire(hardware, frequencies_hz)
        cmap = solver.reconstruct(frame, baseline=None)
        return conductivity_to_png(cmap)
    finally:
        if owns_solver:
            solver.close()
        if owns_hardware:
            hardware.close()
