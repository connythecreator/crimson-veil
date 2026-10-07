"""ESP32 hardware backend, exercised with a fake serial transport."""

from __future__ import annotations

import json

import pytest

from hardware.esp32 import Esp32Error, Esp32Hardware
from software import pipeline
from software.core.types import DeviceConfig


class FakeTransport:
    """Scripted line transport: pre-loaded replies, records what was written."""

    def __init__(self, replies: list[dict | str]) -> None:
        self._replies = list(replies)
        self.written: list[dict] = []
        self.closed = False

    def write_line(self, text: str) -> None:
        self.written.append(json.loads(text))

    def read_line(self, timeout: float) -> str | None:
        if not self._replies:
            return None
        item = self._replies.pop(0)
        return item if isinstance(item, str) else json.dumps(item)

    def close(self) -> None:
        self.closed = True


def _hello(**over) -> dict:
    base = {
        "type": "hello",
        "firmware": "1.0.0",
        "n_electrodes": 8,
        "electrodes": list(range(8)),
        "sweep_hz": 50_000.0,
    }
    base.update(over)
    return base


def _frame(n_points: int, freq: float = 50_000.0) -> dict:
    return {
        "type": "frame",
        "points": [
            {"n": i, "f": freq, "re": 1000.0 + i, "im": -50.0 - i} for i in range(n_points)
        ],
    }


def test_open_learns_electrodes_and_frequency():
    t = FakeTransport([_hello(n_electrodes=8), _hello(n_electrodes=8)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={"port": "/dev/ttyACM0"}))
    assert hw.n_electrodes == 8
    assert hw.electrodes == list(range(8))
    assert hw.firmware == "1.0.0"
    assert hw.frequency_hz == 50_000.0
    assert hw.identify() == "esp32:/dev/ttyACM0"
    # It asked the ESP32 to identify itself.
    assert t.written[0]["type"] == "identify"


def test_scan_sends_bare_scan_and_parses_frame():
    # 8 electrodes -> 8 * (8 - 3) = 40 adjacent measurements.
    t = FakeTransport([_hello(), _hello(), _frame(40)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={"port": "/dev/ttyACM0"}))

    points = hw.scan()

    assert len(points) == 40
    # The scan command carried no plan (the firmware owns the sequence).
    scan = next(w for w in t.written if w["type"] == "scan")
    assert "plan" not in scan
    assert points[0].real == 1000.0
    assert points[0].imag == -50.0


def test_scan_absorbs_telemetry_then_reads_frame():
    tel = {"type": "telemetry", "battery_pct": 87.0, "battery_charging": False, "temp_c": 31.5}
    t = FakeTransport([_hello(), _hello(), tel, _frame(40)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))

    points = hw.scan()
    assert len(points) == 40
    assert hw.telemetry()["battery_pct"] == 87.0


def test_scan_before_open_raises():
    hw = Esp32Hardware(FakeTransport([]))
    with pytest.raises(RuntimeError):
        hw.scan()


def test_error_message_surfaces():
    t = FakeTransport([_hello(), _hello(), {"type": "error", "message": "mux fault"}])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))
    with pytest.raises(Esp32Error, match="mux fault"):
        hw.scan()


def test_bad_json_raises():
    t = FakeTransport([_hello(), _hello(), "{not json"])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))
    with pytest.raises(Esp32Error):
        hw.scan()


def test_close_sends_stop_and_closes():
    t = FakeTransport([_hello(), _hello()])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))
    hw.close()
    assert any(w["type"] == "stop" for w in t.written)
    assert t.closed


def test_pipeline_uses_esp32_backend(monkeypatch):
    """The pipeline requests a scan and collects the firmware's frame."""
    t = FakeTransport([_hello(n_electrodes=8), _hello(n_electrodes=8), _frame(40)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))

    frame = pipeline.acquire(hw)
    assert len(frame.points) == 40
    assert frame.n_electrodes == 8
    assert frame.label.startswith("esp32:")


def test_esp32_hardware_satisfies_protocol():
    from software.interfaces.hardware import HardwareBackend

    assert isinstance(Esp32Hardware(FakeTransport([])), HardwareBackend)
