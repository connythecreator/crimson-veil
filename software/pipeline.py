"""Scan pipeline: the suite's top-level operation.

Ties together a hardware backend and a solver:

    scan -> solver.reconstruct -> PNG bytes

``run_scan`` is the seam the kiosk app calls; it returns PNG bytes and knows
nothing about the GUI. It also knows nothing about *which* hardware or solver
is in use -- those are injected, defaulting to the configured backends.

The front end owns the scan process and calibration: the host requests a scan
and receives points already in the solver's order, with no plan and no
host-side calibration step.
"""

from __future__ import annotations

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

    if config.SOLVER_BACKEND == "pyeit":
        from .reconstruction.pyeit_solver import PyEITSolver

        return PyEITSolver(frequency_hz=config.DEFAULT_FREQUENCY_HZ)

    raise NotImplementedError(
        f"solver backend {config.SOLVER_BACKEND!r} not implemented yet"
    )


def acquire(hardware: HardwareBackend) -> ScanData:
    """Run one frame: request a scan and collect the points.

    The scan plan (electrode pairs and order) is owned by the front end, so the
    host does not build one: it asks for a scan and tags the frame with the
    electrode count and frequency it was acquired at.
    """
    points = hardware.scan()
    n_electrodes = int(getattr(hardware, "n_electrodes", 0) or config.N_ELECTRODES)
    frequency_hz = float(
        getattr(hardware, "frequency_hz", 0.0) or config.DEFAULT_FREQUENCY_HZ
    )
    return ScanData(
        points=points,
        label=hardware.identify(),
        n_electrodes=n_electrodes,
        frequency_hz=frequency_hz,
    )


def run_scan(
    hardware: HardwareBackend | None = None,
    solver: SolverBackend | None = None,
    baseline: ScanData | None = None,
) -> bytes:
    """Run a full scan and return the reconstructed image as PNG bytes.

    If ``hardware``/``solver`` are not supplied, the configured defaults are
    created and closed here. If they are supplied (e.g. by ``main.py`` at boot),
    their lifecycle is the caller's responsibility. Difference solvers require
    a baseline captured separately from the target frame.
    """
    owns_hardware = hardware is None
    owns_solver = solver is None

    if hardware is None:
        hardware = default_hardware()
        hardware.open(config.device_config())
    if solver is None:
        solver = default_solver()
        n_electrodes = int(
            getattr(hardware, "n_electrodes", 0) or config.N_ELECTRODES
        )
        solver.setup(n_electrodes, config.mesh_config(n_electrodes))

    try:
        frame = acquire(hardware)
        cmap = solver.reconstruct(frame, baseline=baseline)
        return conductivity_to_png(cmap)
    finally:
        if owns_solver:
            solver.close()
        if owns_hardware:
            hardware.close()
