"""End-to-end pipeline on the simulated backend - no hardware required."""

from software import pipeline
from software.acquisition import sequence
from software.core import config
from software.sim.sim_hardware import SimHardware
from software.sim.stub_solver import StubSolver

FREQS = [5_000.0, 50_000.0]


def test_run_scan_returns_png_bytes():
    data = pipeline.run_scan(frequencies_hz=FREQS)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_acquire_produces_one_point_per_measurement():
    hw = SimHardware()
    hw.open(config.device_config())
    frame = pipeline.acquire(hw, FREQS)
    assert len(frame.points) == len(sequence.adjacent_drive_plan(FREQS))
    assert len(frame.points) == len(frame.plan)
    hw.close()


def test_measure_before_open_raises():
    hw = SimHardware()
    try:
        hw.measure([])
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError when measuring before open()")


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
