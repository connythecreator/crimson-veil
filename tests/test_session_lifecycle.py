"""Reference retention and resource ownership in the host scan pipeline."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from service.session import BusyError, ScanSession
from software import pipeline
from software.core.types import ConductivityMap, RawPoint


class Hardware:
    n_electrodes = 8
    frequency_hz = 32_000.0

    def __init__(self):
        self.closed = False
        self.scans = 0

    def open(self, cfg):
        pass

    def identify(self):
        return "test:reference-lifecycle"

    def scan(self):
        self.scans += 1
        return [RawPoint(self.frequency_hz, float(self.scans), 0.0)] * 40

    def close(self):
        self.closed = True


class Solver:
    def __init__(self):
        self.closed = False
        self.calls = []

    def setup(self, n_electrodes, mesh):
        pass

    def reconstruct(self, frame, baseline=None):
        assert not self.closed
        if baseline is None:
            raise ValueError("Capture a baseline")
        self.calls.append((frame, baseline))
        return ConductivityMap([[frame.points[0].real - baseline.points[0].real]])

    def close(self):
        self.closed = True


@pytest.fixture
def backends(monkeypatch):
    hardware, solver = Hardware(), Solver()
    monkeypatch.setattr(pipeline, "default_hardware", lambda: hardware)
    monkeypatch.setattr(pipeline, "default_solver", lambda: solver)
    return hardware, solver


def test_session_retains_a_separate_reference_until_frequency_changes(backends):
    hardware, solver = backends
    session = ScanSession()
    session.boot()
    try:
        assert session.frequency_hz == hardware.frequency_hz == 32_000.0
        assert not session.baseline_ready
        session.capture_baseline()
        captured = solver.calls[-1][0]
        assert solver.calls[-1][1] is captured
        session.run_scan()
        session.run_scan()
        assert solver.calls[-1][1] is captured
        assert solver.calls[-2][1] is captured
        assert solver.calls[-1][0] is not captured
        session.set_frequency(32_000.0)
        assert session.baseline_ready
        session.set_frequency(40_000.0)
        assert not session.baseline_ready
        with pytest.raises(ValueError, match="baseline"):
            session.run_scan()
        session.capture_baseline()
        assert session.baseline_ready
        assert solver.calls[-1][1].frequency_hz == 40_000.0
    finally:
        session.close()
    assert hardware.closed and solver.closed
    assert not session.baseline_ready


def test_preboot_frequency_override_applies_after_hardware_handshake(backends):
    session = ScanSession()
    session.set_frequency(60_000.0)
    session.boot()
    try:
        assert session.frequency_hz == session.hardware.frequency_hz == 60_000.0
    finally:
        session.close()


@pytest.mark.parametrize("frequency", [float("nan"), float("inf"), 0, -1])
def test_session_rejects_invalid_frequency(frequency):
    with pytest.raises(ValueError, match="finite and positive"):
        ScanSession().set_frequency(frequency)


def test_unbooted_session_does_not_silently_create_a_scan():
    session = ScanSession()
    with pytest.raises(RuntimeError, match="boot"):
        session.run_scan()
    with pytest.raises(RuntimeError, match="boot"):
        session.capture_baseline()


@pytest.mark.parametrize("entrypoint", ["pipeline", "session"])
def test_setup_failure_closes_partially_opened_backends(backends, monkeypatch, entrypoint):
    hardware, solver = backends

    def fail(*_args):
        raise ValueError("solver setup failed")

    monkeypatch.setattr(solver, "setup", fail)
    operation = pipeline.run_scan if entrypoint == "pipeline" else ScanSession().boot
    with pytest.raises(ValueError, match="solver setup failed"):
        operation()
    assert hardware.closed and solver.closed


def test_frequency_change_and_close_cannot_race_an_acquisition(backends, monkeypatch):
    hardware, solver = backends
    session = ScanSession()
    session.boot()
    session.capture_baseline()
    entered, release, closing = threading.Event(), threading.Event(), threading.Event()
    original_scan = hardware.scan

    def scan():
        entered.set()
        assert release.wait(timeout=5)
        assert not hardware.closed
        return original_scan()

    def close():
        closing.set()
        session.close()

    monkeypatch.setattr(hardware, "scan", scan)
    with ThreadPoolExecutor(max_workers=2) as workers:
        running = workers.submit(session.run_scan)
        try:
            assert entered.wait(timeout=5)
            with pytest.raises(BusyError):
                session.set_frequency(40_000.0)
            with pytest.raises(BusyError):
                session.capture_baseline()
            shutdown = workers.submit(close)
            assert closing.wait(timeout=5)
            assert not hardware.closed and not solver.closed
        finally:
            release.set()
        assert running.result(timeout=5).startswith(b"\x89PNG")
        shutdown.result(timeout=5)
    assert hardware.closed and solver.closed
