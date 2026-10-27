"""Standalone bench-test firmware command loop and result payloads."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HWTEST = Path(__file__).resolve().parents[1] / "firmware" / "mp-firm" / "hwtest"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HWTEST / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def firmware_module(monkeypatch):
    monkeypatch.syspath_prepend(str(HWTEST))
    for name in ("ad5933_driver", "hwtest_core"):
        monkeypatch.setitem(sys.modules, name, _load(name, f"{name}.py"))
    return _load("hwtest_main_under_test", "main.py")


class FakeI2C:
    def __init__(self, found=True):
        self.found = found

    def scan(self):
        return [0x0D] if self.found else [0x50]


class FakeDriver:
    def __init__(self, raw=(1000.0, 0.0), temperature=30.0, error=None, found=True):
        self.raw = raw
        self.temperature = temperature
        self.error = error
        self.i2c = FakeI2C(found=found)
        self.halted = False

    def measure(self, _frequency):
        if self.error:
            raise self.error
        return self.raw

    def temperature_c(self):
        return self.temperature

    def halt(self):
        self.halted = True


def _capture(monkeypatch, module):
    replies = []
    monkeypatch.setattr(module, "sink", lambda line: replies.append(json.loads(line)))
    return replies


def test_bench_i2c_uses_gpio21_and_gpio22(firmware_module):
    assert firmware_module.I2C_SDA == 21
    assert firmware_module.I2C_SCL == 22


def test_boot_and_auto_run_pass(firmware_module, monkeypatch):
    replies = _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver())

    firmware.boot()
    result = firmware.run_once(seq=0)

    assert [reply["type"] for reply in replies] == ["hwtest_hello", "hwtest_result"]
    assert replies[0]["firmware"].startswith("hwtest")
    assert result["status"] == "pass"
    assert result["seq"] == 0
    assert result["expected"]["mag"] == pytest.approx(31.8309886, rel=1e-5)
    by_name = {check["name"]: check for check in result["checks"]}
    assert set(by_name) == {"i2c", "temperature", "acquisition", "stability", "impedance"}
    assert all(check["status"] == "pass" for check in result["checks"])


def test_command_loop_uses_requested_frequency_and_sequence(firmware_module, monkeypatch):
    replies = _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver())

    firmware.run(
        io.StringIO('{"type":"hwtest_run","seq":4,"f":10000,"samples":4}\n')
    )

    assert [reply["type"] for reply in replies] == ["hwtest_result"]
    result = replies[0]
    assert result["seq"] == 4
    assert result["f_hz"] == pytest.approx(10_000.0)
    assert result["expected"]["mag"] == pytest.approx(159.154943, rel=1e-5)
    assert result["status"] == "pass"


def test_acquisition_error_is_reported_not_raised(firmware_module, monkeypatch):
    replies = _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(
        FakeDriver(error=RuntimeError("i2c bus fault"))
    )

    result = firmware.run_once()

    assert replies[-1]["type"] == "hwtest_result"
    assert result["status"] == "fail"
    assert "i2c bus fault" in result["error"]
    by_name = {check["name"]: check for check in result["checks"]}
    assert by_name["acquisition"]["status"] == "fail"


def test_saturated_samples_fail_acquisition(firmware_module, monkeypatch):
    _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver(raw=(32_767.0, 0.0)))

    result = firmware.run_once()

    by_name = {check["name"]: check for check in result["checks"]}
    assert by_name["acquisition"]["status"] == "fail"
    assert result["status"] == "fail"


def test_missing_ad5933_fails_i2c_check(firmware_module, monkeypatch):
    _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver(found=False))

    result = firmware.run_once()

    by_name = {check["name"]: check for check in result["checks"]}
    assert by_name["i2c"]["status"] == "fail"
    assert result["status"] == "fail"


def test_unavailable_temperature_is_a_warning(firmware_module, monkeypatch):
    _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver(temperature=None))

    result = firmware.run_once()

    by_name = {check["name"]: check for check in result["checks"]}
    assert by_name["temperature"]["status"] == "warn"
    assert result["status"] == "warn"


def test_unknown_command_emits_error(firmware_module, monkeypatch):
    replies = _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver())

    firmware.run(io.StringIO('{"type":"scan"}\n'))

    assert replies == [
        {"type": "hwtest_error", "message": "unknown message type: 'scan'"}
    ]


def test_malformed_command_keeps_loop_alive(firmware_module, monkeypatch):
    replies = _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver())

    firmware.run(io.StringIO('not json\n{"type":"hwtest_identify"}\n'))

    assert [reply["type"] for reply in replies] == ["hwtest_error", "hwtest_hello"]


def test_stop_powers_down(firmware_module, monkeypatch):
    _capture(monkeypatch, firmware_module)
    driver = FakeDriver()
    firmware = firmware_module.HwTestFirmware(driver)

    firmware.run(io.StringIO('{"type":"hwtest_stop"}\n'))

    assert driver.halted is True


def test_firmware_does_not_import_mock_or_mux_modules():
    source = (HWTEST / "main.py").read_text()
    assert "mock_ad5933" not in source
    assert "mock_tables" not in source
    assert "select_measurement" not in source


def test_calibration_writes_file_and_reloads(firmware_module, monkeypatch, tmp_path):
    path = tmp_path / "cal.json"
    monkeypatch.setattr(firmware_module, "CALIBRATION_FILE", str(path))
    replies = _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver())

    result = firmware.calibrate(seq=5, freqs=[10_000, 50_000], samples=4)

    assert result["type"] == "hwtest_calibration"
    assert result["status"] == "pass"
    assert result["file"] == str(path)
    assert [entry["f"] for entry in result["entries"]] == [10_000.0, 50_000.0]
    assert replies[-1]["type"] == "hwtest_calibration"
    assert path.exists()

    entries, error = firmware_module.load_calibration_file()
    assert error is None
    assert sorted(entries) == [10_000.0, 50_000.0]


def test_boot_reports_loaded_calibration(firmware_module, monkeypatch, tmp_path):
    path = tmp_path / "cal.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"f": 10_000, "k_re": 1, "k_im": 0, "status": "pass"},
                    {"f": 50_000, "k_re": 2, "k_im": 0, "status": "pass"},
                ]
            }
        )
    )
    monkeypatch.setattr(firmware_module, "CALIBRATION_FILE", str(path))
    replies = _capture(monkeypatch, firmware_module)
    firmware = firmware_module.HwTestFirmware(FakeDriver())

    firmware.boot()

    hello = replies[-1]
    assert hello["type"] == "hwtest_hello"
    assert hello["calibration"]["present"] is True
    assert hello["calibration"]["entries"] == 2
    assert hello["calibration"]["error"] is None
