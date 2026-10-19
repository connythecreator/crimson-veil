"""ESP32 hardware backend, exercised with a fake serial transport."""

from __future__ import annotations

import json
import sys
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from hardware.esp32 import Esp32Error, Esp32Hardware, SerialTransport
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
    tel = {"type": "telemetry", "temp_esp32_c": 31.5, "temp_ad5933_c": 0.0}
    t = FakeTransport([_hello(), _hello(), tel, _frame(40)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))

    points = hw.scan()
    assert len(points) == 40
    assert hw.telemetry()["temp_esp32_c"] == 31.5


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


def test_telemetry_cannot_read_transport_during_scan():
    """The server's metrics thread must not steal a scan's serial reply."""
    reading_frame = threading.Event()
    release_frame = threading.Event()

    class BlockingTransport(FakeTransport):
        def __init__(self):
            super().__init__([_hello(), _frame(40)])
            self.read_count = 0

        def read_line(self, timeout):
            self.read_count += 1
            if self.read_count == 2:
                reading_frame.set()
                assert release_frame.wait(5), "test did not release scan reply"
            return super().read_line(timeout)

    transport = BlockingTransport()
    hardware = Esp32Hardware(transport)
    hardware.open(DeviceConfig(backend="esp32"))
    hardware._telemetry = {"temp_esp32_c": 87.0}
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(hardware.scan)
        try:
            assert reading_frame.wait(5), "scan did not start reading"
            assert hardware.telemetry() == {"temp_esp32_c": 87.0}
            assert transport.read_count == 2
        finally:
            release_frame.set()
        assert len(result.result(timeout=5)) == 40
    hardware.close()


def test_indexed_frame_is_restored_to_firmware_order():
    frame = _frame(40)
    frame["points"].reverse()
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    assert [point.real for point in hardware.scan()] == [1000.0 + i for i in range(40)]


def test_unindexed_legacy_frame_preserves_wire_order():
    frame = _frame(40)
    for point in frame["points"]:
        del point["n"]
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    assert [point.real for point in hardware.scan()] == [1000.0 + i for i in range(40)]


@pytest.mark.parametrize("count", [0, 39, 41])
def test_frame_rejects_incorrect_measurement_count(count):
    hardware = Esp32Hardware(FakeTransport([_hello(), _frame(count)]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="expected 40"):
        hardware.scan()


@pytest.mark.parametrize("index", [-1, 40, 1.5, "0", True, None])
def test_frame_rejects_invalid_indices(index):
    frame = _frame(40)
    frame["points"][0]["n"] = index
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="invalid index"):
        hardware.scan()


def test_frame_rejects_duplicate_index():
    frame = _frame(40)
    frame["points"][1]["n"] = 0
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="duplicate point index"):
        hardware.scan()


def test_frame_rejects_mixed_indexed_and_unindexed_points():
    frame = _frame(40)
    del frame["points"][0]["n"]
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="mixes indexed and unindexed"):
        hardware.scan()


@pytest.mark.parametrize("point", [None, [], "point", 1])
def test_frame_rejects_nonobject_points(point):
    frame = _frame(40)
    frame["points"][0] = point
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="JSON object"):
        hardware.scan()


@pytest.mark.parametrize("field,value", [("re", None), ("im", "bad"), ("f", [])])
def test_frame_rejects_invalid_numeric_data(field, value):
    frame = _frame(40)
    frame["points"][0][field] = value
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="invalid numeric data"):
        hardware.scan()


@pytest.mark.parametrize(
    "field,value",
    [("re", float("nan")), ("im", float("inf")), ("f", float("inf"))],
)
def test_frame_rejects_nonfinite_data(field, value):
    frame = _frame(40)
    frame["points"][0][field] = value
    hardware = Esp32Hardware(FakeTransport([_hello(), frame]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="non-finite"):
        hardware.scan()


@pytest.mark.parametrize("frequency", [0.0, -1.0])
def test_frame_rejects_nonpositive_frequency(frequency):
    hardware = Esp32Hardware(FakeTransport([_hello(), _frame(40, frequency)]))
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="frequency must be positive"):
        hardware.scan()


def test_serial_transport_preserves_partial_json_across_polls(monkeypatch):
    chunks = iter([b'{"type":"tele', b'', b'metry","temp_esp32_c":31.5}\r\n'])
    serial = SimpleNamespace(timeout=0.0, readline=lambda: next(chunks, b""))
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=lambda **_opts: serial))
    transport = SerialTransport("test", 115200, 0.0)

    assert transport.read_line(0.0) is None
    assert transport.read_line(0.0) is None
    assert json.loads(transport.read_line(0.0)) == {"type": "telemetry", "temp_esp32_c": 31.5}


def test_serial_transport_joins_partial_telemetry_before_scan_frame(monkeypatch):
    """A scan can take over an incomplete message from the metrics poll."""
    hello = json.dumps(_hello()).encode() + b"\n"
    frame = json.dumps(_frame(40)).encode() + b"\n"
    chunks = iter([hello, b'{"type":"tele', b'metry","temp_esp32_c":31.5}\n', frame])
    serial = SimpleNamespace(
        timeout=0.0,
        readline=lambda: next(chunks, b""),
        write=lambda _data: None,
        flush=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=lambda **_opts: serial))
    hardware = Esp32Hardware(SerialTransport("test", 115200, 0.0))
    hardware.open(DeviceConfig(backend="esp32"))

    assert hardware.telemetry() == {}
    assert len(hardware.scan()) == 40
    assert hardware.telemetry()["temp_esp32_c"] == 31.5


def test_scan_failure_releases_transport_for_telemetry_and_retry():
    tel = {"type": "telemetry", "temp_esp32_c": 31.5}
    transport = FakeTransport([_hello(), {"type": "error", "message": "test fault"}])
    hardware = Esp32Hardware(transport)
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="test fault"):
        hardware.scan()

    transport._replies.append(tel)
    assert hardware.telemetry()["temp_esp32_c"] == 31.5
    transport._replies.extend([_hello(), _frame(40)])
    assert len(hardware.scan()) == 40


@pytest.mark.parametrize("prefix_length", [0, 100])
def test_retry_resynchronizes_delayed_frame_before_requesting_new_scan(monkeypatch, prefix_length):
    """A timed-out reply must never be mistaken for a later frame or baseline."""
    frequency = 40_000.0
    old_frame = json.dumps(_frame(40, frequency)).encode() + b"\n"
    new_data = _frame(40, frequency)
    for point in new_data["points"]:
        point["re"] += 2000.0
    new_frame = json.dumps(new_data).encode() + b"\n"
    hello = json.dumps(_hello()).encode() + b"\n"

    class DelayedSerial:
        def __init__(self, **_options):
            self.timeout = 0.0
            self.chunks = deque()
            self.commands = []
            self.scans = 0

        def write(self, data):
            command = json.loads(data)
            self.commands.append(command)
            if command["type"] == "identify":
                if self.scans:
                    self.chunks.append(old_frame[prefix_length:])
                self.chunks.append(hello)
            elif command["type"] == "scan":
                self.scans += 1
                if self.scans == 1:
                    if prefix_length:
                        self.chunks.append(old_frame[:prefix_length])
                    self.chunks.append(b"")  # acquisition timed out
                else:
                    self.chunks.append(new_frame)

        def readline(self):
            return self.chunks.popleft() if self.chunks else b""

        def flush(self):
            pass

    serial = DelayedSerial()
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=lambda **_opts: serial))
    hardware = Esp32Hardware(SerialTransport("test", 115200, 0.0))
    hardware.open(DeviceConfig(backend="esp32"))
    hardware.frequency_hz = frequency

    with pytest.raises(Esp32Error, match="timed out"):
        hardware.scan()
    result = hardware.scan()

    assert [point.real for point in result] == [3000.0 + index for index in range(40)]
    assert [command["type"] for command in serial.commands] == [
        "identify", "scan", "identify", "scan",
    ]
    assert all(
        command["f"] == frequency
        for command in serial.commands if command["type"] == "scan"
    )
    assert hardware.frequency_hz == frequency
    assert not serial.chunks


def test_recovery_rejects_changed_electrode_count_before_acquiring_again():
    transport = FakeTransport([_hello(), "{bad JSON", _hello(n_electrodes=16)])
    hardware = Esp32Hardware(transport)
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="bad line"):
        hardware.scan()
    with pytest.raises(Esp32Error, match="electrode count changed"):
        hardware.scan()
    assert hardware.n_electrodes == 8
    assert [command["type"] for command in transport.written] == ["identify", "scan", "identify"]


def test_recovery_timeout_does_not_request_another_scan():
    transport = FakeTransport([_hello(), "{bad JSON"])
    hardware = Esp32Hardware(transport)
    hardware.open(DeviceConfig(backend="esp32"))
    with pytest.raises(Esp32Error, match="bad line"):
        hardware.scan()
    with pytest.raises(Esp32Error, match="timed out"):
        hardware.scan()
    assert [command["type"] for command in transport.written] == ["identify", "scan", "identify"]


def test_probe_reidentifies_the_esp():
    t = FakeTransport([_hello(), _hello(firmware="2.0.0", n_electrodes=16)])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))

    hello = hw.probe()
    assert hello["firmware"] == "2.0.0"
    assert hw.n_electrodes == 16
    assert t.written[-1] == {"type": "identify"}


def test_selftest_reads_result_and_absorbs_telemetry():
    telemetry = {"type": "telemetry", "temp_esp32_c": 50.0, "temp_ad5933_c": 38.0}
    result = {
        "type": "selftest_result",
        "firmware": "1.0.0",
        "ad5933": True,
        "mux": True,
        "temp_ad5933_c": 38.0,
        "error": None,
    }
    t = FakeTransport([_hello(), telemetry, result])
    hw = Esp32Hardware(t)
    hw.open(DeviceConfig(backend="esp32", options={}))

    out = hw.selftest()
    assert out["ad5933"] is True
    assert t.written[-1] == {"type": "selftest"}
    assert hw.telemetry()["temp_esp32_c"] == 50.0
