"""Pre-start hardware self-test checks (no hardware required)."""

from __future__ import annotations

import time

from service import metrics, selftest
from software.core import config


class Esp32Hardware:  # named to satisfy selftest._is_esp
    def __init__(self, probe=None, selftest_result=None, error=None):
        self._probe = probe or {
            "firmware": "1.0.0",
            "n_electrodes": 8,
            "electrodes": list(range(8)),
            "sweep_hz": 50_000.0,
        }
        self._result = selftest_result or {
            "ad5933": True,
            "mux": True,
            "temp_ad5933_c": 38.5,
        }
        self._error = error

    def probe(self):
        if self._error:
            raise RuntimeError(self._error)
        return dict(self._probe)

    def selftest(self):
        if self._error:
            raise RuntimeError(self._error)
        return dict(self._result)


class FakeSession:
    def __init__(self, hardware=None, booted=True, boot_error=None):
        self.hardware = hardware
        self.booted = booted
        self.boot_error = boot_error
        self.boot_calls = 0

    def boot(self):
        self.boot_calls += 1
        self.booted = True
        return "fake:open"

    def identify(self):
        return "fake:open"


def _fresh_bms(**over):
    data = {
        "ts": time.time(),
        "power_mode": 1,
        "vin_v": 4.0,
        "vout_v": 5.0,
        "iout_a": 0.6,
        "temp_c": 42.0,
        "charging": False,
        "standby": False,
        "low_v": 3.1,
    }
    data.update(over)
    return data


# --- battery ---------------------------------------------------------------


def test_battery_passes_on_battery(monkeypatch):
    monkeypatch.setattr(metrics, "read_bms", lambda: _fresh_bms())
    check = selftest.battery_check()
    assert check.status == "pass"
    assert "on battery" in check.detail
    assert "4.00 V" in check.detail


def test_battery_passes_on_usb(monkeypatch):
    monkeypatch.setattr(metrics, "read_bms", lambda: _fresh_bms(power_mode=0))
    check = selftest.battery_check()
    assert check.status == "pass"
    assert "USB" in check.detail


def test_battery_fails_when_missing(monkeypatch):
    monkeypatch.setattr(metrics, "read_bms", lambda: {})
    assert selftest.battery_check().status == "fail"


def test_battery_fails_when_stale(monkeypatch):
    monkeypatch.setattr(metrics, "read_bms", lambda: _fresh_bms(ts=0))
    assert selftest.battery_check().status == "fail"


# --- ESP / impedance -------------------------------------------------------


def test_esp_passes_with_hello():
    check = selftest.esp_check(FakeSession(hardware=Esp32Hardware()))
    assert check.status == "pass"
    assert "1.0.0" in check.detail


def test_esp_fails_without_hardware():
    check = selftest.esp_check(FakeSession(hardware=None, boot_error="no serial"))
    assert check.status == "fail"
    assert "no serial" in check.detail


def test_esp_skips_on_mock_backend():
    check = selftest.esp_check(FakeSession(hardware=object()))
    assert check.status == "skip"


def test_esp_fails_when_probe_errors():
    check = selftest.esp_check(FakeSession(hardware=Esp32Hardware(error="link down")))
    assert check.status == "fail"
    assert "link down" in check.detail


def test_impedance_passes_when_ad5933_responds():
    check = selftest.impedance_check(FakeSession(hardware=Esp32Hardware()))
    assert check.status == "pass"
    assert "38.5" in check.detail


def test_impedance_fails_when_ad5933_missing():
    hw = Esp32Hardware(selftest_result={"ad5933": False, "error": "no AD5933"})
    check = selftest.impedance_check(FakeSession(hardware=hw))
    assert check.status == "fail"
    assert "no AD5933" in check.detail


def test_impedance_skips_without_hardware():
    assert selftest.impedance_check(FakeSession()).status == "skip"


# --- PyEIT -----------------------------------------------------------------


def test_pyeit_fails_with_stub_solver(monkeypatch):
    monkeypatch.setattr(config, "SOLVER_BACKEND", "stub")
    check = selftest.pyeit_check()
    assert check.status == "fail"
    assert "stub" in check.detail


def test_pyeit_fails_when_not_installed(monkeypatch):
    monkeypatch.setattr(config, "SOLVER_BACKEND", "pyeit")
    monkeypatch.setattr(selftest.importlib.util, "find_spec", lambda name: None)
    check = selftest.pyeit_check()
    assert check.status == "fail"
    assert "not installed" in check.detail


# --- run_self_test ---------------------------------------------------------


def test_run_self_test_retries_boot_and_returns_all_checks(monkeypatch):
    monkeypatch.setattr(metrics, "read_bms", lambda: _fresh_bms())
    monkeypatch.setattr(config, "SOLVER_BACKEND", "stub")
    session = FakeSession(hardware=Esp32Hardware(), booted=False)

    checks = selftest.run_self_test(session)
    assert session.boot_calls == 1
    assert [c["name"] for c in checks] == [
        "Battery",
        "Belt Controller (ESP)",
        "Impedance Subsystem",
        "PyEIT",
        "Control Service",
    ]
    by_name = {c["name"]: c for c in checks}
    assert by_name["Battery"]["status"] == "pass"
    assert by_name["Belt Controller (ESP)"]["status"] == "pass"
    assert by_name["Impedance Subsystem"]["status"] == "pass"
    assert by_name["PyEIT"]["status"] == "fail"
    assert by_name["Control Service"]["status"] == "pass"


def test_impedance_fails_without_calibration():
    hw = Esp32Hardware(
        selftest_result={
            "ad5933": True,
            "mux": True,
            "calibration": False,
            "calibration_entries": 0,
            "calibration_error": "calibration file missing: cal.json",
            "error": "calibration file missing: cal.json",
        }
    )
    check = selftest.impedance_check(FakeSession(hardware=hw))
    assert check.status == "fail"
    assert "calibration file missing" in check.detail


def test_impedance_reports_loaded_calibration_points():
    hw = Esp32Hardware(
        selftest_result={
            "ad5933": True,
            "mux": True,
            "calibration": True,
            "calibration_entries": 2,
            "temp_ad5933_c": 25.0,
        }
    )
    check = selftest.impedance_check(FakeSession(hardware=hw))
    assert check.status == "pass"
    assert "2 calibration points" in check.detail
