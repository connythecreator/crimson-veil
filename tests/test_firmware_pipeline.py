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
    for name in ("protocol", "ad5933_driver", "status_led"):
        monkeypatch.setitem(sys.modules, name, load(name, f"{name}.py"))
    return load("crimson_test_firmware", "main.py")


class FakeDriver:
    def __init__(self):
        self.measurements = 0
        self.halts = 0
        self.events = []

    def measure(self, _frequency):
        self.measurements += 1
        return float(self.measurements), 0.0

    def temperature_c(self):
        return 25.0

    def halt(self):
        self.halts += 1
        self.events.append("halt")


class FakeLED:
    def __init__(self):
        self.fail_count = 0
        self.ok_count = 0

    def fail(self):
        self.fail_count += 1

    def ok(self):
        self.ok_count += 1


class RecordingMux:
    ROLES = ("drive_pos", "drive_neg", "sense_pos", "sense_neg")

    def __init__(self, events=None):
        self.addresses = {role: 0 for role in self.ROLES}
        self.events = events if events is not None else []

    def set_address(self, role, electrode):
        if role not in self.addresses:
            raise ValueError(f"unknown mux role: {role!r}")
        self.addresses[role] = electrode

    def park_all(self):
        self.events.append("park")
        for role in self.addresses:
            self.addresses[role] = 0


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
                    {"f": 10_000, "range": "1vpp", "k_re": 10, "k_im": 0, "status": "pass"},
                    {"f": 50_000, "range": "1vpp", "k_re": 2, "k_im": 0, "status": "pass"},
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


def test_protocol_skips_non_utf8_serial_noise(firmware_module):
    stream = io.BytesIO(b"\xff\xfe\n" + b'{"type":"identify"}\n')
    assert firmware_module.protocol.read_line(stream) == ""
    assert firmware_module.protocol.read_line(stream) == '{"type":"identify"}'


def test_load_calibration_combines_resistor_magnitude_and_capacitor_phase(
    tmp_path, firmware_module
):
    path = tmp_path / "cal.json"
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "entries": [
                    {
                        "f": 50_000,
                        "fixture": "resistor",
                        "range": "1vpp",
                        "r_ohm": 100,
                        "k_re": 400,
                        "k_im": 0,
                        "status": "pass",
                    },
                    {
                        "f": 50_000,
                        "fixture": "capacitor",
                        "range": "1vpp",
                        "c_f": 1e-7,
                        "k_re": 398.5,
                        "k_im": -27.9,
                        "status": "pass",
                    },
                ],
            }
        )
    )
    table, error = firmware_module.load_calibration(str(path))
    assert error is None
    combined = table.factor(50_000)
    assert abs(combined) == pytest.approx(400.0, rel=1e-6)
    assert combined.imag < 0


def test_load_calibration_rejects_disagreeing_references(tmp_path, firmware_module):
    path = tmp_path / "cal.json"
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "entries": [
                    {
                        "f": 50_000,
                        "fixture": "resistor",
                        "range": "1vpp",
                        "k_re": 200,
                        "k_im": 20,
                        "status": "pass",
                    },
                    {
                        "f": 50_000,
                        "fixture": "capacitor",
                        "range": "1vpp",
                        "k_re": 0,
                        "k_im": -400,
                        "status": "pass",
                    },
                ],
            }
        )
    )
    table, error = firmware_module.load_calibration(str(path))
    assert len(table) == 0
    assert "references disagree" in error


def test_select_measurement_keeps_each_role_address(firmware_module):
    mux = RecordingMux()
    firmware = firmware_module.Firmware(FakeDriver(), mux=mux)

    firmware.select_measurement((0, 1), (2, 3))
    assert mux.addresses == {
        "drive_pos": 0,
        "drive_neg": 1,
        "sense_pos": 2,
        "sense_neg": 3,
    }

    firmware.select_measurement((4, 5), (6, 7))
    assert mux.addresses == {
        "drive_pos": 4,
        "drive_neg": 5,
        "sense_pos": 6,
        "sense_neg": 7,
    }


def test_select_measurement_rejects_overlapping_pairs(firmware_module):
    firmware = firmware_module.Firmware(FakeDriver(), mux=RecordingMux())

    with pytest.raises(ValueError, match="distinct"):
        firmware.select_measurement((0, 1), (1, 2))


def test_stop_powers_down_before_parking_all_roles(firmware_module):
    events = []
    driver = FakeDriver()
    driver.events = events
    mux = RecordingMux(events)
    firmware = firmware_module.Firmware(driver, mux=mux)

    firmware.select_measurement((0, 1), (2, 3))
    firmware.stop()

    assert events == ["halt", "park"]
    assert driver.halts == 1
    assert mux.addresses == {role: 0 for role in RecordingMux.ROLES}


def test_muxbank_drives_independent_address_buses(firmware_module, monkeypatch):
    class FakePin:
        OUT = "out"
        by_number = {}

        def __init__(self, number, _mode):
            self.number = number
            self.level = None
            FakePin.by_number[number] = self

        def value(self, level=None):
            if level is None:
                return self.level
            self.level = level

    monkeypatch.setattr(firmware_module, "Pin", FakePin)
    mux = firmware_module.MuxBank()

    def levels(role):
        return [FakePin.by_number[pin].level for pin in firmware_module.MUX_ADDR[role]]

    assert all(levels(role) == [0, 0, 0] for role in firmware_module.MUX_ROLES)

    mux.set_address("drive_pos", 5)
    mux.set_address("drive_neg", 6)
    mux.set_address("sense_pos", 7)
    mux.set_address("sense_neg", 0)

    assert levels("drive_pos") == [1, 0, 1]
    assert levels("drive_neg") == [0, 1, 1]
    assert levels("sense_pos") == [1, 1, 1]
    assert levels("sense_neg") == [0, 0, 0]

    mux.set_address("drive_pos", 0)
    assert levels("drive_pos") == [0, 0, 0]
    assert levels("drive_neg") == [0, 1, 1]

    with pytest.raises(ValueError, match="out of range"):
        mux.set_address("drive_pos", 8)
    with pytest.raises(ValueError, match="unknown mux role"):
        mux.set_address("bogus", 0)


def test_mux_test_reports_only_electrode_zero_connected(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    mux = RecordingMux()

    class OnlyElectrodeZeroDriver:
        def measure(self, _frequency):
            return (1000.0, 0.0) if set(mux.addresses.values()) == {0} else (0.0, 0.0)

        def temperature_c(self):
            return 25.0

        def halt(self):
            pass

    table = firmware_module.CalibrationTable({50_000.0: complex(2.0, 0.0)})
    firmware = firmware_module.Firmware(
        OnlyElectrodeZeroDriver(), mux=mux, calibration=table
    )
    firmware.handle({"type": "mux_test"})

    result = replies[-1]
    assert result["type"] == "mux_test_result"
    assert result["calibration"] is True
    points = {point["e"]: point for point in result["points"]}

    assert points[0]["status"] == "connected"
    assert points[0]["raw_abs"] == pytest.approx(1000.0)
    assert points[0]["z_abs"] == pytest.approx(0.002)

    for electrode in range(1, 8):
        assert points[electrode]["status"] == "open"
        assert points[electrode]["raw_abs"] == 0.0
        assert "z_abs" not in points[electrode]

    assert mux.addresses == {role: 0 for role in RecordingMux.ROLES}


def test_mux_test_honours_min_raw_and_calibration_error(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    mux = RecordingMux()

    class WeakDriver:
        def measure(self, _frequency):
            return (5.0, 0.0) if set(mux.addresses.values()) == {0} else (0.0, 0.0)

        def temperature_c(self):
            return 25.0

        def halt(self):
            pass

    firmware = firmware_module.Firmware(
        WeakDriver(), mux=mux, calibration_error="calibration file missing"
    )
    firmware.handle({"type": "mux_test", "min_raw": 1.0})

    result = replies[-1]
    assert result["type"] == "mux_test_result"
    assert result["calibration"] is False
    points = {point["e"]: point for point in result["points"]}
    assert points[0]["status"] == "connected"
    assert "z_abs" not in points[0]
    assert points[1]["status"] == "open"


def test_mux_test_uses_drive_neg_c1_for_shorted_channels(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    mux = RecordingMux()

    class ShortedDriveNegDriver:
        def measure(self, _frequency):
            # Electrode 0 is wired. D- C0 is shorted to C1, so either address
            # reaches electrode 0; the test deliberately uses C1.
            connected = (
                mux.addresses["drive_pos"] == 0
                and mux.addresses["drive_neg"] in (0, 1)
                and mux.addresses["sense_pos"] == 0
                and mux.addresses["sense_neg"] == 0
            )
            return (1000.0, 0.0) if connected else (0.0, 0.0)

        def temperature_c(self):
            return 25.0

        def halt(self):
            pass

    firmware = firmware_module.Firmware(ShortedDriveNegDriver(), mux=mux)
    firmware.handle({"type": "mux_test", "d_neg": 1})

    result = replies[-1]
    assert result["type"] == "mux_test_result"
    assert result["d_neg"] == 1
    points = {point["e"]: point for point in result["points"]}

    assert points[0]["status"] == "connected"
    assert points[0]["drive_neg"] == 1
    assert points[0]["raw_abs"] == pytest.approx(1000.0)

    for electrode in range(1, 8):
        assert points[electrode]["status"] == "open"
        assert points[electrode]["drive_neg"] == 1


def test_selftest_passes_when_every_mux_electrode_is_connected(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    mux = RecordingMux()

    class ConnectedDriver:
        def measure(self, _frequency):
            return (1000.0, 0.0)

        def temperature_c(self):
            return 25.0

        def halt(self):
            pass

    led = FakeLED()
    firmware = firmware_module.Firmware(ConnectedDriver(), mux=mux, led=led)
    firmware._selftest()

    result = replies[-1]
    assert result["ad5933"] is True
    assert result["mux"] is True
    assert result["error"] is None
    assert mux.addresses == {role: 0 for role in RecordingMux.ROLES}
    assert led.ok_count == 1
    assert led.fail_count == 0


def test_selftest_fails_on_open_mux_electrode(firmware_module):
    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    mux = RecordingMux()

    class OpenElectrodeDriver:
        def measure(self, _frequency):
            return (0.0, 0.0) if set(mux.addresses.values()) == {3} else (1000.0, 0.0)

        def temperature_c(self):
            return 25.0

        def halt(self):
            pass

    led = FakeLED()
    firmware = firmware_module.Firmware(OpenElectrodeDriver(), mux=mux, led=led)
    firmware._selftest()

    result = replies[-1]
    assert result["ad5933"] is True
    assert result["mux"] is False
    assert "mux open" in result["error"]
    assert "electrode(s) 3" in result["error"]
    assert mux.addresses == {role: 0 for role in RecordingMux.ROLES}
    assert led.fail_count == 1
    assert led.ok_count == 0
