"""Host-side bench-test tool: result formatting, reply handling, upload set."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "hwtest.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("hwtest_tool_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tool():
    return _load_tool()


class FakeSerial:
    def __init__(self, lines):
        self.lines = list(lines)
        self.written = []

    def write_line(self, message):
        self.written.append(message)

    def read_line(self, _timeout):
        return self.lines.pop(0) if self.lines else None


def _args(**over):
    values = {
        "f": 50_000.0,
        "c_f": 0.1e-6,
        "samples": 16,
        "tol_pct": 5.0,
        "tol_deg": 5.0,
        "drift_pct": 2.0,
        "drift_deg": 2.0,
        "timeout": 10.0,
    }
    values.update(over)
    return SimpleNamespace(**values)


def test_run_test_sends_identify_then_run_and_filters_sequence(tool):
    result = {"type": "hwtest_result", "seq": 1, "status": "pass"}
    serial = FakeSerial(
        [
            json.dumps({"type": "hwtest_hello", "firmware": "hwtest 1.0.0"}),
            json.dumps({"type": "hwtest_result", "seq": 0, "status": "pass"}),
            json.dumps(result),
        ]
    )

    assert tool.run_test(serial, _args()) == result
    assert serial.written[0]["type"] == "hwtest_identify"
    assert serial.written[1]["type"] == "hwtest_run"
    assert serial.written[1]["seq"] == 1
    assert serial.written[1]["f"] == 50_000.0


def test_run_test_rejects_wrong_firmware(tool):
    serial = FakeSerial([json.dumps({"type": "hwtest_hello", "firmware": "1.0.0"})])
    with pytest.raises(tool.HwTestError, match="unexpected firmware"):
        tool.run_test(serial, _args())


def test_run_test_surfaces_firmware_error(tool):
    serial = FakeSerial(
        [
            json.dumps({"type": "hwtest_hello", "firmware": "hwtest 1.0.0"}),
            json.dumps({"type": "hwtest_error", "message": "AD5933 not found"}),
        ]
    )
    with pytest.raises(tool.HwTestError, match="AD5933 not found"):
        tool.run_test(serial, _args())


def test_format_result_includes_checks_and_status(tool):
    result = {
        "firmware": "hwtest 1.1.0",
        "f_hz": 50_000.0,
        "temp_ad5933_c": 30.0,
        "fixture": {"c_f": 0.1e-6},
        "expected": {"mag": 31.83, "phase_deg": -90.0},
        "raw": {"re_mean": 1000.0, "im_mean": 0.0, "n": 16, "mag_std_pct": 0.1},
        "calibration": {"k_mag": 31.83, "k_phase_deg": -90.0},
        "measured": {"mag": 31.82, "phase_deg": -89.9},
        "drift": {"mag_pct": 0.1, "phase_deg": 0.1},
        "checks": [{"name": "i2c", "status": "pass", "detail": "AD5933 at 0x0D"}],
        "status": "pass",
        "error": None,
    }

    text = tool.format_result(result)

    assert "bench hardware test" in text
    assert "temperature: 30.00 C" in text
    assert "[PASS] i2c" in text
    assert "status     : PASS" in text


def test_upload_copies_only_hwtest_files(tool, monkeypatch):
    commands = []
    monkeypatch.setattr(tool, "_mpremote_command", lambda: ["mpremote"])
    monkeypatch.setattr(tool, "_run", lambda command: commands.append(command))
    monkeypatch.setattr(tool.subprocess, "run", lambda *a, **k: None)

    files = tool.upload("/dev/ttyACM0")

    assert files == ["main.py", "hwtest_core.py", "ad5933_driver.py"]
    copied = [command[-1] for command in commands]
    assert copied == [":main.py", ":hwtest_core.py", ":ad5933_driver.py"]
    assert not any("mock" in command for command in copied)


def test_parse_freqs_rejects_bad_values(tool):
    assert tool._parse_freqs("10000, 50000") == [10_000.0, 50_000.0]
    with pytest.raises(tool.HwTestError):
        tool._parse_freqs("")
    with pytest.raises(tool.HwTestError):
        tool._parse_freqs("0")


def test_run_calibration_sends_frequencies(tool):
    result = {
        "type": "hwtest_calibration",
        "seq": 1,
        "file": "cal.json",
        "status": "pass",
        "entries": [],
    }
    serial = FakeSerial(
        [
            json.dumps({"type": "hwtest_hello", "firmware": "hwtest 1.2.0"}),
            json.dumps(result),
        ]
    )

    assert tool.run_calibration(serial, _args(), [10_000.0, 50_000.0]) == result
    assert serial.written[1]["type"] == "hwtest_calibrate"
    assert serial.written[1]["freqs"] == [10_000.0, 50_000.0]


def test_format_calibration_lists_entries(tool):
    text = tool.format_calibration(
        {
            "file": "cal.json",
            "status": "pass",
            "entries": [
                {
                    "f": 10_000,
                    "mag": 2767742.2,
                    "phase_deg": -163.27,
                    "status": "pass",
                }
            ],
            "error": None,
        }
    )
    assert "calibration written" in text
    assert "10000 Hz" in text or "10,000 Hz" in text
    assert "PASS" in text
