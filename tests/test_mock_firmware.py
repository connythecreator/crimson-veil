"""MicroPython firmware with the synthetic AD5933/mux mock driver."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

FREQ_HZ = 50_000.0
SRC = Path(__file__).resolve().parents[1] / "firmware" / "mp-firm" / "src"


@pytest.fixture(autouse=True)
def _firmware_imports(monkeypatch):
    """Let MockAD5933 import its flat table modules by name."""
    monkeypatch.syspath_prepend(str(SRC))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SRC / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def firmware_module(monkeypatch):
    for name in ("protocol", "ad5933_driver", "mock_ad5933", "status_led"):
        monkeypatch.setitem(sys.modules, name, _load(name, f"{name}.py"))
    return _load("crimson_mock_firmware", "main.py")


def test_mock_driver_serves_baseline_then_target():
    mock = _load("mock_ad5933_standalone", "mock_ad5933.py")
    driver = mock.MockAD5933()

    baseline = [driver.measure(FREQ_HZ) for _ in range(40)]
    target = [driver.measure(FREQ_HZ) for _ in range(40)]
    assert len(baseline) == 40 and len(target) == 40
    assert baseline != target

    driver.set_mode("baseline")
    assert [driver.measure(FREQ_HZ) for _ in range(40)] == baseline


def test_mock_driver_supports_4_8_16_electrodes():
    mock = _load("mock_ad5933_counts", "mock_ad5933.py")
    for n_electrodes in (4, 8, 16):
        driver = mock.MockAD5933(n_electrodes=n_electrodes)
        points = n_electrodes * (n_electrodes - 3)
        assert len([driver.measure(FREQ_HZ) for _ in range(points)]) == points


def test_mock_driver_cycles_anomaly_positions():
    mock = _load("mock_ad5933_standalone", "mock_ad5933.py")
    driver = mock.MockAD5933()

    baseline = [driver.measure(FREQ_HZ) for _ in range(40)]
    first = [driver.measure(FREQ_HZ) for _ in range(40)]
    second = [driver.measure(FREQ_HZ) for _ in range(40)]
    assert baseline != first
    assert first != second  # monitor mode sees a moving anomaly

    # Eight target tables; after the 8th, cycling wraps to the first.
    for _ in range(6):
        [driver.measure(FREQ_HZ) for _ in range(40)]
    assert [driver.measure(FREQ_HZ) for _ in range(40)] == first

    driver.set_mode("target")
    assert [driver.measure(FREQ_HZ) for _ in range(40)] == first


def test_firmware_mock_scan_and_selftest(firmware_module):
    replies: list[dict] = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))

    mock = sys.modules["mock_ad5933"]
    driver = mock.MockAD5933()
    firmware = firmware_module.Firmware(driver, mux=mock.MockMux())
    firmware.run(
        io.StringIO(
            '{"type":"scan"}\n'
            '{"type":"selftest"}\n'
            '{"type":"mock_mode","mode":"target"}\n'
            '{"type":"identify"}\n'
        )
    )

    assert [reply["type"] for reply in replies] == [
        "frame",
        "selftest_result",
        "mock_mode_result",
        "hello",
    ]
    frame, selftest, mock_mode, hello = replies
    assert [point["n"] for point in frame["points"]] == list(range(40))
    assert all(point["re"] < 0 for point in frame["points"])
    assert selftest["ad5933"] is True and selftest["mux"] is True
    assert mock_mode["mode"] == "target"
    assert hello["n_electrodes"] == 8


def test_empty_calibration_does_not_invert_measurements(firmware_module):
    table = firmware_module.CalibrationTable()
    assert table.apply(FREQ_HZ, -0.11, 0.02) == (-0.11, 0.02)


def test_mock_driver_bypasses_calibration(firmware_module):
    import mock_tables_8

    replies: list[dict] = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    mock = sys.modules["mock_ad5933"]
    driver = mock.MockAD5933()
    table = firmware_module.CalibrationTable({FREQ_HZ: complex(2.0, 0.0)})
    firmware = firmware_module.Firmware(driver, mux=mock.MockMux(), calibration=table)

    assert driver.is_mock
    firmware.handle({"type": "scan"})

    assert replies[-1]["type"] == "frame"
    assert replies[-1]["points"][0]["re"] == pytest.approx(mock_tables_8.BASELINE[0])


def test_mock_firmware_target_reconstructs_white_low_impedance(firmware_module):
    np = pytest.importorskip("numpy")
    pytest.importorskip("pyeit")
    pytest.importorskip("matplotlib")

    from software.core.types import MeshConfig, RawPoint, ScanData
    from software.reconstruction.image import HEATMAP_NEUTRAL, colorize
    from software.reconstruction.pyeit_solver import PyEITSolver

    replies: list[dict] = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    mock = sys.modules["mock_ad5933"]
    firmware = firmware_module.Firmware(mock.MockAD5933(), mux=mock.MockMux())

    firmware.handle({"type": "scan"})  # baseline
    firmware.handle({"type": "scan"})  # target 0 (higher conductivity)
    baseline, target = replies

    def as_scan(frame):
        return ScanData(
            points=[RawPoint(point["f"], point["re"], point["im"]) for point in frame["points"]],
            n_electrodes=8,
            frequency_hz=FREQ_HZ,
        )

    random_state = np.random.get_state()
    try:
        np.random.seed(20261014)
        solver = PyEITSolver(grid_size=96)
        solver.setup(8, MeshConfig(n_electrodes=8))
    finally:
        np.random.set_state(random_state)

    try:
        cmap = solver.reconstruct(as_scan(target), as_scan(baseline))
        values = np.asarray(cmap.values)
        row, column = np.unravel_index(np.argmax(np.abs(values)), values.shape)
        rows = colorize(cmap.values)
        red, green, blue = rows[row][column * 3 : column * 3 + 3]

        assert cmap.centered
        assert values[row, column] > 0
        assert red > blue and red > green
        assert tuple(rows[0][0:3]) == HEATMAP_NEUTRAL
    finally:
        solver.close()
