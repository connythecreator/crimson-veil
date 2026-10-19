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


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SRC / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def firmware_module(monkeypatch):
    for name in ("protocol", "ad5933_driver", "mock_ad5933"):
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
