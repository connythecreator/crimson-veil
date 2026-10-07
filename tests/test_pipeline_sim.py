"""End-to-end pipeline on the simulated backend - no hardware required."""

from software import pipeline
from software.core import config
from software.sim.sim_hardware import SimHardware
from software.sim.stub_solver import StubSolver

# The front end owns the scan sequence, so a frame holds n * (n - 3) points.
EXPECTED_POINTS_8 = 8 * (8 - 3)


def test_run_scan_returns_png_bytes():
    data = pipeline.run_scan()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_acquire_produces_the_front_end_frame():
    hw = SimHardware()
    hw.open(config.device_config())
    frame = pipeline.acquire(hw)
    assert len(frame.points) == EXPECTED_POINTS_8
    assert frame.n_electrodes == hw.n_electrodes
    hw.close()


def test_scan_before_open_raises():
    hw = SimHardware()
    try:
        hw.scan()
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError when scanning before open()")


def test_sim_hardware_implements_protocol():
    from software.interfaces.hardware import HardwareBackend

    assert isinstance(SimHardware(), HardwareBackend)


def test_stub_solver_implements_protocol():
    from software.interfaces.solver import SolverBackend

    assert isinstance(StubSolver(), SolverBackend)


def test_stub_solver_returns_nonempty_map():
    solver = StubSolver()
    solver.setup(config.N_ELECTRODES, config.mesh_config())
    cmap = solver.reconstruct(frame=None)  # type: ignore[arg-type]
    assert cmap.width > 0 and cmap.height > 0
