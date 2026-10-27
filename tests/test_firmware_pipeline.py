"""Exercise the MicroPython command loop with a host-side acquisition double."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def firmware_module(monkeypatch):
    source = Path(__file__).resolve().parents[1] / "firmware" / "mp-firm" / "src"

    def load(name, filename):
        spec = importlib.util.spec_from_file_location(name, source / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # Firmware uses flat imports on the ESP32. Restore the host module table
    # after each test so these names cannot affect other pipeline tests.
    for name in ("protocol", "ad5933_driver"):
        monkeypatch.setitem(sys.modules, name, load(name, f"{name}.py"))
    return load("crimson_test_firmware", "main.py")


class FakeDriver:
    def __init__(self):
        self.measurements = 0
        self.halts = 0

    def measure(self, _frequency):
        self.measurements += 1
        return float(self.measurements), 0.0

    def temperature_c(self):
        return 25.0

    def halt(self):
        self.halts += 1


def test_firmware_handles_repeated_scans_and_identify(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    driver = FakeDriver()
    firmware = firmware_module.Firmware(driver)
    firmware.run(io.StringIO('{"type":"scan"}\n{"type":"scan"}\n{"type":"identify"}\n'))

    assert [reply["type"] for reply in replies] == ["frame", "frame", "hello"]
    assert driver.measurements == 80
    assert driver.halts == 2
    for reply in replies[:2]:
        assert [point["n"] for point in reply["points"]] == list(range(40))


def test_firmware_stop_keeps_command_loop_available(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    driver = FakeDriver()
    firmware = firmware_module.Firmware(driver)
    firmware.run(io.StringIO('{"type":"stop"}\n{"type":"identify"}\n{"type":"scan"}\n'))

    assert [reply["type"] for reply in replies] == ["hello", "frame"]
    assert driver.halts == 2


def test_firmware_acquisition_error_keeps_command_loop_available(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))

    class TransientFailureDriver(FakeDriver):
        def measure(self, frequency):
            if self.measurements == 0:
                self.measurements += 1
                raise firmware_module.AD5933Error("test acquisition failure")
            return super().measure(frequency)

    driver = TransientFailureDriver()
    firmware = firmware_module.Firmware(driver)
    firmware.run(io.StringIO('{"type":"scan"}\n{"type":"scan"}\n'))

    assert [reply["type"] for reply in replies] == ["error", "frame"]
    assert "test acquisition failure" in replies[0]["message"]
    assert len(replies[1]["points"]) == 40


def test_load_calibration_missing_file(tmp_path, firmware_module):
    table, error = firmware_module.load_calibration(str(tmp_path / "cal.json"))
    assert len(table) == 0
    assert "missing" in error


def test_load_calibration_loads_entries_and_uses_nearest(tmp_path, firmware_module):
    path = tmp_path / "cal.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"f": 10_000, "k_re": 10, "k_im": 0, "status": "pass"},
                    {"f": 50_000, "k_re": 2, "k_im": 0, "status": "pass"},
                    {"f": 1_000, "k_re": 99, "k_im": 0, "status": "skip"},
                ]
            }
        )
    )
    table, error = firmware_module.load_calibration(str(path))
    assert error is None
    assert len(table) == 2
    assert table.factor(49_000) == complex(2.0, 0.0)
    re, im = table.apply(50_000, 1000, 0)
    assert re == pytest.approx(0.002)
    assert im == pytest.approx(0.0)


def test_firmware_refuses_scan_without_calibration(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    firmware = firmware_module.Firmware(
        FakeDriver(), calibration_error="calibration file missing: cal.json"
    )

    firmware.handle({"type": "scan"})

    assert replies == [
        {
            "type": "error",
            "message": "calibration unavailable: calibration file missing: cal.json",
        }
    ]


def test_selftest_reports_missing_calibration(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    firmware = firmware_module.Firmware(
        FakeDriver(), calibration_error="calibration file missing: cal.json"
    )

    firmware._selftest()

    result = replies[-1]
    assert result["type"] == "selftest_result"
    assert result["calibration"] is False
    assert result["calibration_entries"] == 0
    assert "calibration file missing" in result["calibration_error"]
    assert "calibration file missing" in result["error"]


def test_scan_applies_complex_calibration(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    table = firmware_module.CalibrationTable({50_000.0: complex(2.0, 0.0)})
    firmware = firmware_module.Firmware(FakeDriver(), calibration=table)

    firmware.handle({"type": "scan"})

    frame = replies[-1]
    assert frame["type"] == "frame"
    assert frame["points"][0]["re"] == pytest.approx(2.0)
    assert frame["points"][0]["im"] == pytest.approx(0.0)
