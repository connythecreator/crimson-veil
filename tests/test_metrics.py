"""Metrics: ESP32 telemetry takes priority, sysfs is the fallback."""

from __future__ import annotations

from service import metrics


class FakeHardware:
    def __init__(self, tel: dict) -> None:
        self._tel = tel

    def telemetry(self) -> dict:
        return self._tel


def test_esp_telemetry_supplies_all_fields():
    hw = FakeHardware({"battery_pct": 42.0, "battery_charging": True, "temp_c": 40.0})
    snap = metrics.snapshot(hw)
    assert snap == {"battery_pct": 42.0, "battery_charging": True, "temp_c": 40.0}


def test_missing_esp_fields_fall_back_to_sysfs(monkeypatch):
    monkeypatch.setattr(metrics, "_sysfs_battery", lambda: (55.0, False))
    monkeypatch.setattr(metrics, "_sysfs_temperature", lambda: 33.0)
    hw = FakeHardware({"battery_pct": None, "battery_charging": None, "temp_c": None})
    snap = metrics.snapshot(hw)
    assert snap["battery_pct"] == 55.0
    assert snap["battery_charging"] is False
    assert snap["temp_c"] == 33.0


def test_no_hardware_uses_sysfs(monkeypatch):
    monkeypatch.setattr(metrics, "_sysfs_battery", lambda: (None, False))
    monkeypatch.setattr(metrics, "_sysfs_temperature", lambda: None)
    snap = metrics.snapshot(None)
    assert snap["battery_pct"] is None
    assert snap["temp_c"] is None


def test_telemetry_exception_is_swallowed(monkeypatch):
    class Boom:
        def telemetry(self):
            raise RuntimeError("link dropped")

    monkeypatch.setattr(metrics, "_sysfs_battery", lambda: (10.0, False))
    monkeypatch.setattr(metrics, "_sysfs_temperature", lambda: 20.0)
    snap = metrics.snapshot(Boom())
    assert snap["battery_pct"] == 10.0
