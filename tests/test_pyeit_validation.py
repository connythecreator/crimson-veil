"""Validate the adapter with voltages sampled directly from FEM nodes.

The synthetic acquisition below follows the firmware's drive/sense sequence.
It never reads the adapter's mapping or pyEIT's measurement matrix, so reversed
polarity and ordering errors cannot cancel between the fixture and adapter.
"""

import asyncio
import json
import struct
from collections import deque
from dataclasses import replace

import pytest

pytest.importorskip("pyeit")
np = pytest.importorskip("numpy")
pytest.importorskip("matplotlib")

import pyeit.mesh as mesh
from pyeit.eit.fem import EITForward
from pyeit.mesh.wrapper import PyEITAnomaly_Circle

from software.core.types import MeshConfig, RawPoint, ScanData
from software.reconstruction.pyeit_solver import PyEITSolver, _build_project_protocol

FREQUENCY_HZ = 50_000.0
ELECTRODES = 8


def _acquire_node_voltages(solver, perm=None):
    """Sample V(sense_pos) - V(sense_neg), as the firmware wires its mux."""
    forward = EITForward(solver.mesh_obj, solver.protocol_obj)
    if perm is not None:
        forward.assemble_pde(perm)
    electrode_nodes = solver.mesh_obj.el_pos
    points = []
    for drive_pos in range(ELECTRODES):
        potentials = forward.solve(
            np.array([drive_pos, (drive_pos + 1) % ELECTRODES])
        )
        for offset in range(ELECTRODES - 3):
            sense_pos = (drive_pos + 2 + offset) % ELECTRODES
            sense_neg = (sense_pos + 1) % ELECTRODES
            voltage = (
                potentials[electrode_nodes[sense_pos]]
                - potentials[electrode_nodes[sense_neg]]
            )
            points.append(
                RawPoint(FREQUENCY_HZ, float(voltage.real), float(voltage.imag))
            )
    return ScanData(
        points=points,
        n_electrodes=ELECTRODES,
        frequency_hz=FREQUENCY_HZ,
        label="independent FEM acquisition",
    )


@pytest.fixture(scope="module")
def digital_solver():
    random_state = np.random.get_state()
    solver = PyEITSolver(grid_size=48)
    try:
        np.random.seed(20261014)
        solver.setup(ELECTRODES, MeshConfig(n_electrodes=ELECTRODES))
    finally:
        np.random.set_state(random_state)
    yield solver
    solver.close()


@pytest.fixture(scope="module")
def homogeneous_scan(digital_solver):
    return _acquire_node_voltages(digital_solver)


@pytest.mark.parametrize("n_electrodes", [4, 8, 16])
def test_adjacent_protocol_covers_every_firmware_measurement(n_electrodes):
    protocol, mapping = _build_project_protocol(n_electrodes)
    expected_count = n_electrodes * (n_electrodes - 3)
    assert len(protocol.ex_mat) == n_electrodes
    assert len(mapping) == expected_count
    assert sorted(index for index, _ in mapping) == list(range(expected_count))
    assert all(polarity == -1.0 for _, polarity in mapping)


def test_independent_acquisition_matches_upstream_boundary_voltages(
    digital_solver, homogeneous_scan
):
    adapter_values, frequency = digital_solver._values_for_scan(
        homogeneous_scan, "frame"
    )
    upstream_values = EITForward(
        digital_solver.mesh_obj, digital_solver.protocol_obj
    ).solve_eit()
    np.testing.assert_allclose(adapter_values, upstream_values, atol=1e-12, rtol=1e-10)
    assert frequency == FREQUENCY_HZ


def test_identical_baseline_and_frame_reconstruct_zero(
    digital_solver, homogeneous_scan
):
    values = np.asarray(
        digital_solver.reconstruct(homogeneous_scan, homogeneous_scan).values
    )
    assert values.shape == (48, 48)
    np.testing.assert_array_equal(values, np.zeros_like(values))


def test_missing_baseline_is_rejected_by_default(digital_solver, homogeneous_scan):
    assert not digital_solver.allow_homogeneous_reference
    with pytest.raises(ValueError, match="baseline"):
        digital_solver.reconstruct(homogeneous_scan)


def test_explicit_model_reference_matches_captured_model_baseline(
    digital_solver, homogeneous_scan, monkeypatch
):
    assert PyEITSolver(allow_homogeneous_reference=True).allow_homogeneous_reference
    altered_mesh = mesh.set_perm(
        digital_solver.mesh_obj,
        anomaly=PyEITAnomaly_Circle(center=[0.5, 0.5], r=0.18, perm=2.0),
        background=1.0,
    )
    frame = _acquire_node_voltages(digital_solver, altered_mesh.perm)
    measured_reference_result = digital_solver.reconstruct(frame, homogeneous_scan)
    monkeypatch.setattr(digital_solver, "allow_homogeneous_reference", True)
    model_reference_result = digital_solver.reconstruct(frame)
    np.testing.assert_allclose(
        model_reference_result.values, measured_reference_result.values,
        atol=1e-12, rtol=1e-10,
    )


@pytest.mark.parametrize("center", [(0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5), (0.5, -0.5)])
@pytest.mark.parametrize("conductivity", [0.5, 2.0])
def test_conductivity_change_sign_and_quadrant(
    digital_solver, homogeneous_scan, center, conductivity
):
    altered_mesh = mesh.set_perm(
        digital_solver.mesh_obj,
        anomaly=PyEITAnomaly_Circle(center=list(center), r=0.18, perm=conductivity),
        background=1.0,
    )
    frame = _acquire_node_voltages(digital_solver, altered_mesh.perm)
    values = np.asarray(digital_solver.reconstruct(frame, homogeneous_scan).values)
    assert np.isfinite(values).all()
    row, column = np.unravel_index(np.argmax(np.abs(values)), values.shape)
    assert abs(values[row, column]) > 1e-8
    assert np.sign(values[row, column]) == np.sign(conductivity - 1.0)
    assert (column > (values.shape[1] - 1) / 2) == (center[0] > 0)
    assert (row < (values.shape[0] - 1) / 2) == (center[1] > 0)


@pytest.mark.parametrize("component", ["real", "imag"])
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("scan_name", ["frame", "baseline"])
def test_nonfinite_measurements_are_rejected(
    digital_solver, homogeneous_scan, component, bad_value, scan_name
):
    points = list(homogeneous_scan.points)
    points[7] = replace(points[7], **{component: bad_value})
    invalid_scan = replace(homogeneous_scan, points=points)
    frame = invalid_scan if scan_name == "frame" else homogeneous_scan
    baseline = invalid_scan if scan_name == "baseline" else homogeneous_scan
    with pytest.raises(ValueError):
        digital_solver.reconstruct(frame, baseline)


def test_zero_real_baseline_is_rejected_before_bp_normalization(
    digital_solver, homogeneous_scan
):
    points = list(homogeneous_scan.points)
    points[7] = replace(points[7], real=0.0, imag=1.0)
    baseline = replace(homogeneous_scan, points=points)
    with pytest.raises(ValueError):
        digital_solver.reconstruct(homogeneous_scan, baseline)


@pytest.mark.parametrize("scan_name", ["frame", "baseline"])
@pytest.mark.parametrize("mismatch", ["electrodes", "count", "point_frequency"])
def test_invalid_scan_metadata_is_rejected(
    digital_solver, homogeneous_scan, scan_name, mismatch
):
    if mismatch == "electrodes":
        invalid_scan = replace(homogeneous_scan, n_electrodes=16)
    elif mismatch == "count":
        invalid_scan = replace(homogeneous_scan, points=homogeneous_scan.points[:-1])
    else:
        points = list(homogeneous_scan.points)
        points[7] = replace(points[7], freq_hz=40_000.0)
        invalid_scan = replace(homogeneous_scan, points=points)
    frame = invalid_scan if scan_name == "frame" else homogeneous_scan
    baseline = invalid_scan if scan_name == "baseline" else homogeneous_scan
    with pytest.raises(ValueError):
        digital_solver.reconstruct(frame, baseline)


def test_frame_and_baseline_frequencies_must_match(digital_solver, homogeneous_scan):
    other_frequency = replace(
        homogeneous_scan,
        frequency_hz=40_000.0,
        points=[replace(point, freq_hz=40_000.0) for point in homogeneous_scan.points],
    )
    with pytest.raises(ValueError, match="frequenc"):
        digital_solver.reconstruct(homogeneous_scan, other_frequency)


def test_esp32_to_websocket_pyeit_pipeline(monkeypatch):
    """Run real serial parsing, session, reconstruction and binary delivery.

    Only the serial device and backend selection are substituted. The serial
    device replies on demand, so telemetry cannot consume future scan frames.
    """
    from websockets.asyncio.client import connect
    from websockets.asyncio.server import serve

    from hardware.esp32 import Esp32Hardware
    from service import protocol
    from service.server import ControlServer
    from service.session import ScanSession
    from software import pipeline
    from software.core import config
    from software.reconstruction.image import conductivity_to_png

    telemetry = {
        "type": "telemetry", "temp_esp32_c": 24.0, "temp_ad5933_c": 38.0,
    }

    class DigitalSerial:
        def __init__(self):
            self.responses = deque()
            self.frames = deque()
            self.commands = []
            self.closed = False

        def write_line(self, text):
            command = json.loads(text)
            self.commands.append(command)
            if command["type"] == "identify":
                self.responses.extend([
                    json.dumps({
                        "type": "hello", "firmware": "independent-fem",
                        "n_electrodes": ELECTRODES,
                        "electrodes": list(range(ELECTRODES)),
                        "sweep_hz": FREQUENCY_HZ,
                    }),
                    json.dumps(telemetry),
                ])
            elif command["type"] == "scan":
                assert self.frames, "Unexpected extra acquisition"
                scan = self.frames.popleft()
                points = [
                    {"n": i, "f": point.freq_hz, "re": point.real, "im": point.imag}
                    for i, point in enumerate(scan.points)
                ]
                # Deliberately scramble wire order: the n fields restore it.
                scrambled = points[1::2][::-1] + points[::2][::-1]
                self.responses.extend([
                    json.dumps(telemetry),
                    json.dumps({"type": "frame", "points": scrambled}),
                ])

        def read_line(self, timeout):
            return self.responses.popleft() if self.responses else None

        def close(self):
            self.closed = True

    transport = DigitalSerial()
    hardware = Esp32Hardware(transport=transport)
    solver = PyEITSolver(grid_size=48)
    monkeypatch.setattr(pipeline, "default_hardware", lambda: hardware)
    monkeypatch.setattr(pipeline, "default_solver", lambda: solver)
    monkeypatch.setattr(config, "SOLVER_BACKEND", "pyeit")
    session = ScanSession()
    random_state = np.random.get_state()
    try:
        np.random.seed(20261014)
        session.boot()
    finally:
        np.random.set_state(random_state)

    try:
        baseline = _acquire_node_voltages(solver)
        altered_mesh = mesh.set_perm(
            solver.mesh_obj,
            anomaly=PyEITAnomaly_Circle(center=[0.5, 0.5], r=0.18, perm=2.0),
            background=1.0,
        )
        target = _acquire_node_voltages(solver, altered_mesh.perm)
        expected_map = solver.reconstruct(target, baseline)
        expected_png = conductivity_to_png(expected_map)
        values = np.asarray(expected_map.values)
        row, column = np.unravel_index(np.argmax(np.abs(values)), values.shape)
        assert row < 24 and column >= 24 and values[row, column] > 0
        transport.frames.extend([baseline, target, target])

        async def receive_type(ws, wanted):
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                assert isinstance(raw, str), "PNG arrived without its result header"
                message = json.loads(raw)
                if message["type"] == wanted:
                    return message
                assert message["type"] != "scan_error", message

        async def run():
            server = ControlServer(session)
            async with serve(server.handler, "127.0.0.1", 0, max_size=None) as listener:
                port = listener.sockets[0].getsockname()[1]
                async with connect(
                    f"ws://127.0.0.1:{port}", proxy=None,
                    open_timeout=5, close_timeout=1,
                ) as ws:
                    ready = await receive_type(ws, "ready")
                    assert ready["solver"] == "pyeit"
                    assert not ready["baseline_ready"]
                    metrics = await receive_type(ws, "metrics")
                    assert metrics["temp_esp32_c"] == 24.0
                    assert metrics["temp_ad5933_c"] == 38.0
                    assert metrics["battery_pct"] is None
                    await ws.send(protocol.encode(protocol.CaptureBaseline(id="reference")))
                    captured = await receive_type(ws, "baseline_captured")
                    assert captured["id"] == "reference"
                    assert captured["n_electrodes"] == ELECTRODES
                    assert captured["frequency_hz"] == FREQUENCY_HZ
                    assert (await receive_type(ws, "ready"))["baseline_ready"]

                    for scan_id in ("target", "repeat"):
                        await ws.send(protocol.encode(protocol.ScanRequest(id=scan_id)))
                        result = await receive_type(ws, "scan_result")
                        assert result["id"] == scan_id
                        assert (result["width"], result["height"]) == (48, 48)
                        image = await asyncio.wait_for(ws.recv(), timeout=5)
                        assert isinstance(image, bytes)
                        assert len(image) == result["bytes"]
                        assert struct.unpack(">II", image[16:24]) == (48, 48)
                        assert image == expected_png
                        assert session.baseline_ready

                    assert len([
                        c for c in transport.commands if c["type"] == "scan"
                    ]) == 3
                    assert all(
                        c["f"] == FREQUENCY_HZ
                        for c in transport.commands if c["type"] == "scan"
                    )
                    await ws.send(protocol.encode(protocol.SetFrequency(frequency_hz=40_000.0)))
                    ready = await receive_type(ws, "ready")
                    assert ready["frequency_hz"] == 40_000.0
                    assert not ready["baseline_ready"]
                    transport.frames.append(replace(
                        target, frequency_hz=40_000.0,
                        points=[replace(p, freq_hz=40_000.0) for p in target.points],
                    ))
                    await ws.send(protocol.encode(protocol.ScanRequest(id="new-frequency")))
                    failure = await receive_type(ws, "scan_error")
                    assert failure["id"] == "new-frequency"
                    assert "baseline" in failure["message"].lower()

        asyncio.run(run())
    finally:
        session.close()
    assert transport.closed
