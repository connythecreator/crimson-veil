"""Metrics: BMS snapshot -> kiosk blob (battery SoC/runtime + all temps)."""

from __future__ import annotations

import pytest

from service import metrics


@pytest.fixture(autouse=True)
def _clear_runtime_window():
    metrics.reset_runtime_window()
    yield
    metrics.reset_runtime_window()


class FakeHardware:
    def __init__(self, tel: dict) -> None:
        self._tel = tel

    def telemetry(self) -> dict:
        return self._tel


BMS_ON_BATTERY = {
    "ts": 1700000000,
    "power_mode": 1,
    "vin_v": 3.85,
    "vout_v": 5.02,
    "iout_a": 0.5,
    "temp_c": 31.5,
    "charging": False,
    "standby": False,
    "low_v": 3.30,
}

BMS_ON_USB = dict(BMS_ON_BATTERY, power_mode=0, vin_v=5.0, charging=True)


# --- SoC curve -------------------------------------------------------------


def test_soc_anchors_at_full_and_low():
    assert metrics.soc_from_voltage(4.20, 3.30) == 100.0
    assert metrics.soc_from_voltage(3.30, 3.30) == 0.0
    assert metrics.soc_from_voltage(2.90, 3.30) == 0.0  # below floor -> clamped


def test_soc_midpoint_between_anchors():
    soc = metrics.soc_from_voltage(3.85, 3.30)
    assert 55.0 <= soc <= 65.0


def test_soc_none_without_voltage():
    assert metrics.soc_from_voltage(None, 3.30) is None


def test_soc_floor_moves_with_low_v():
    # A higher configured threshold reports less charge at the same voltage.
    assert metrics.soc_from_voltage(3.45, 3.40) < metrics.soc_from_voltage(3.45, 3.20)


# --- runtime ---------------------------------------------------------------


def test_runtime_from_charge_and_current():
    # 50% of 6000 mAh = 3000 mAh; at 0.5 A -> 6 h.
    assert metrics.runtime_s(50.0, 0.5) == 6 * 3600


def test_runtime_none_on_bad_inputs():
    assert metrics.runtime_s(None, 0.5) is None
    assert metrics.runtime_s(50.0, 0.0) is None
    assert metrics.runtime_s(50.0, None) is None


# --- runtime undershoot ----------------------------------------------------


def test_undershoot_holds_the_lowest_recent_estimate():
    assert metrics.undershoot_runtime(7200, now=0) == 7200
    assert metrics.undershoot_runtime(4000, now=60) == 4000
    # A rosier reading does not raise the displayed value while the low one is
    # still inside the window.
    assert metrics.undershoot_runtime(9000, now=120) == 4000


def test_undershoot_recovers_after_window_expires():
    metrics.undershoot_runtime(4000, now=0)
    metrics.undershoot_runtime(9000, now=120)
    # 301 s later the 4000 s low point has aged out of the 300 s window.
    assert metrics.undershoot_runtime(9000, now=301) == 9000


def test_undershoot_ignores_none():
    assert metrics.undershoot_runtime(None, now=0) is None
    metrics.undershoot_runtime(5000, now=1)
    assert metrics.undershoot_runtime(None, now=2) == 5000


# --- snapshot --------------------------------------------------------------


def _patch_bms(monkeypatch, data: dict):
    monkeypatch.setattr(metrics, "_read_bms", lambda: dict(data))


def test_on_battery_supplies_soc_runtime_and_voltage(monkeypatch):
    monkeypatch.setattr(metrics, "_read_bms", lambda: dict(BMS_ON_BATTERY))
    snap = metrics.snapshot(FakeHardware({}))
    assert snap["on_battery"] is True
    assert snap["battery_v"] == 3.85
    assert snap["battery_pct"] is not None
    assert snap["runtime_s"] is not None
    assert snap["battery_charging"] is False


def test_on_usb_reports_charging_and_no_soc(monkeypatch):
    monkeypatch.setattr(metrics, "_read_bms", lambda: dict(BMS_ON_USB))
    snap = metrics.snapshot(FakeHardware({}))
    assert snap["on_battery"] is False
    assert snap["battery_v"] is None  # no battery voltage on USB
    assert snap["runtime_s"] is None
    assert snap["battery_charging"] is True


def test_snapshot_runtime_undershoots_then_resets_off_battery(monkeypatch):
    monkeypatch.setattr(metrics, "_read_bms", lambda: dict(BMS_ON_BATTERY))
    first = metrics.snapshot(None)["runtime_s"]
    assert first is not None

    heavy = dict(BMS_ON_BATTERY, iout_a=1.2)  # heavier draw -> lower estimate
    monkeypatch.setattr(metrics, "_read_bms", lambda: dict(heavy))
    second = metrics.snapshot(None)["runtime_s"]
    assert second is not None and second < first

    monkeypatch.setattr(metrics, "_read_bms", lambda: dict(BMS_ON_USB))
    assert metrics.snapshot(None)["runtime_s"] is None


def test_temps_collected_from_all_sources(monkeypatch):
    monkeypatch.setattr(metrics, "_read_bms", lambda: dict(BMS_ON_BATTERY))
    monkeypatch.setattr(metrics, "_sysfs_temperature", lambda: 44.0)
    hw = FakeHardware({"temp_esp32_c": 52.0, "temp_ad5933_c": 38.5})
    snap = metrics.snapshot(hw)
    assert snap["temp_wittypi_c"] == 31.5
    assert snap["temp_esp32_c"] == 52.0
    assert snap["temp_ad5933_c"] == 38.5
    assert snap["temp_pi_c"] == 44.0


def test_esp_no_longer_reports_battery(monkeypatch):
    # ESP telemetry carries only temperatures now; battery must come from BMS.
    monkeypatch.setattr(metrics, "_read_bms", lambda: {})
    monkeypatch.setattr(metrics, "_sysfs_battery", lambda: (None, False))
    monkeypatch.setattr(metrics, "_sysfs_temperature", lambda: 50.0)
    snap = metrics.snapshot(FakeHardware({"temp_esp32_c": 40.0, "temp_ad5933_c": 35.0}))
    assert snap["battery_pct"] is None
    assert snap["battery_v"] is None
    assert snap["on_battery"] is False


def test_sysfs_battery_fallback_without_bms(monkeypatch):
    monkeypatch.setattr(metrics, "_read_bms", lambda: {})
    monkeypatch.setattr(metrics, "_sysfs_battery", lambda: (55.0, True))
    snap = metrics.snapshot(None)
    assert snap["battery_pct"] == 55.0
    assert snap["battery_charging"] is True


def test_bms_read_error_is_safe(monkeypatch):
    monkeypatch.setattr(metrics, "_read_bms", lambda: {})
    monkeypatch.setattr(metrics, "_sysfs_battery", lambda: (None, False))
    monkeypatch.setattr(metrics, "_sysfs_temperature", lambda: None)

    class Boom:
        def telemetry(self):
            raise RuntimeError("link down")

    snap = metrics.snapshot(Boom())
    assert snap["battery_pct"] is None
    assert snap["temp_esp32_c"] is None
