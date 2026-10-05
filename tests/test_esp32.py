"""ESP32 hardware backend, exercised with a fake serial transport."""

from __future__ import annotations

import json

import pytest

from hardware.esp32 import Esp32Error, Esp32Hardware
from software import pipeline
from software.acquisition import sequence
from software.core.types import DeviceConfig, Measurement


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
        "firmware": "0.1.0",
        "n_electrodes": 8,
        "electrodes": list(range(8)),
        "sweep_hz": 1000.0,
    }
    base.update(over)
    return base


def _frame(plan) -> dict:
    return {
        "type": "frame",
        "points": [
            {"f": m.freq_hz, "re": 1000.0 + i, "im": -50.0 - i}
            for i, m in enumerate(plan)
        ],
    }


def test_open_learns_electrodes_from_hello():
    t = FakeTransport([_hello(n_electrodes=8), _hello(n_electrodes=8)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={"port": "/dev/ttyACM0"}))
    assert hw.n_electrodes == 8
    assert hw.electrodes == list(range(8))
    assert hw.firmware == "0.1.0"
    assert hw.identify() == "esp32:/dev/ttyACM0"
    # It asked the ESP32 to identify itself.
    assert t.written[0]["type"] == "identify"


def test_measure_sends_plan_and_parses_frame():
    plan = sequence.adjacent_drive_plan([5_000.0, 50_000.0])
    t = FakeTransport([_hello(), _hello(), _frame(plan)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={"port": "/dev/ttyACM0"}))

    points = hw.measure(plan)

    assert len(points) == len(plan)
    # The scan command carried the full plan, in order.
    scan = next(w for w in t.written if w["type"] == "scan")
    assert len(scan["plan"]) == len(plan)
    assert scan["plan"][0] == {
        "f": plan[0].freq_hz,
        "d": list(plan[0].drive),
        "s": list(plan[0].sense),
    }
    assert points[0].real == 1000.0
    assert points[0].imag == -50.0


def test_measure_absorbs_telemetry_then_reads_frame():
    plan = [Measurement(freq_hz=1_000.0, drive=(0, 4), sense=(2, 6))]
    tel = {"type": "telemetry", "battery_pct": 87.0, "battery_charging": False, "temp_c": 31.5}
    t = FakeTransport([_hello(), _hello(), tel, _frame(plan)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))

    points = hw.measure(plan)
    assert len(points) == 1
    assert hw.telemetry()["battery_pct"] == 87.0


def test_measure_before_open_raises():
    hw = Esp32Hardware(FakeTransport([]))
    with pytest.raises(RuntimeError):
        hw.measure([])


def test_frame_point_count_mismatch_raises():
    t = FakeTransport([_hello(), _hello(), _frame([Measurement(1.0, (0, 4), (2, 6))])])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))
    with pytest.raises(Esp32Error):
        hw.measure(sequence.adjacent_drive_plan([1_000.0, 2_000.0]))  # expects more points


def test_error_message_surfaces():
    t = FakeTransport([_hello(), _hello(), {"type": "error", "message": "mux fault"}])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))
    with pytest.raises(Esp32Error, match="mux fault"):
        hw.measure([Measurement(1.0, (0, 4), (2, 6))])


def test_bad_json_raises():
    t = FakeTransport([_hello(), _hello(), "{not json"])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))
    with pytest.raises(Esp32Error):
        hw.measure([Measurement(1.0, (0, 4), (2, 6))])


def test_close_sends_stop_and_closes():
    t = FakeTransport([_hello(), _hello()])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))
    hw.close()
    assert any(w["type"] == "stop" for w in t.written)
    assert t.closed


def test_pipeline_uses_esp32_backend_and_electrode_count(monkeypatch):
    """The host builds the plan for the electrode count the hardware reports."""
    plan = sequence.adjacent_drive_plan([5_000.0], n_electrodes=8)
    t = FakeTransport([_hello(n_electrodes=8), _hello(n_electrodes=8), _frame(plan)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))

    frame = pipeline.acquire(hw, [5_000.0])
    assert len(frame.points) == len(plan)
    assert frame.label.startswith("esp32:")


def test_esp32_hardware_satisfies_protocol():
    from software.interfaces.hardware import HardwareBackend

    assert isinstance(Esp32Hardware(FakeTransport([])), HardwareBackend)
