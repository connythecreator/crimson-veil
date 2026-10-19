"""Device metrics for the kiosk (battery, temperatures).

Battery comes from the **Witty Pi 4 L3V7 BMS**, which runs as its own systemd
unit (`veil-bms.service`) and writes a JSON snapshot. Battery state-of-charge
and runtime are *estimated here* (the L3V7 has no coulomb-counter fuel gauge -
it measures voltage/current and enforces a low-voltage threshold).

Temperature comes from several sensors: the Witty Pi's LM75B, the ESP32 die,
the AD5933 chip, and the Raspberry Pi SoC. Temperatures are surfaced to the
kiosk for its settings page only (not the status bar).

Every value is best-effort and may be ``None``. Sources are merged in priority
order: BMS -> ESP32 telemetry -> Linux sysfs.
"""

from __future__ import annotations

import glob
import json
import os
import time
from collections import deque

_POWER_SUPPLY = "/sys/class/power_supply"
_THERMAL = "/sys/class/thermal"

# BMS snapshot written by scripts/wittypi/veil-bms.sh.
BMS_STATUS = os.environ.get("CV_BMS_STATUS", "/run/veil-bms/telemetry.json")

# Battery: 3.7 V Li-ion/polymer, 6000 mAh. Overridable for a different cell.
BATTERY_CAPACITY_MAH = float(os.environ.get("CV_BATTERY_MAH", "6000"))
BATTERY_FULL_V = float(os.environ.get("CV_BATTERY_FULL_V", "4.20"))
BATTERY_LOW_V_DEFAULT = float(os.environ.get("CV_BATTERY_LOW_V", "3.30"))

# Runtime is reported as the *lowest* estimate seen in this trailing window, so
# the indicator undershoots (never overpromises) as the load varies.
RUNTIME_WINDOW_S = float(os.environ.get("CV_RUNTIME_WINDOW_S", "300"))
_runtime_window: deque[tuple[float, int]] = deque()

# Li-ion resting-voltage discharge shape as (fraction-of-usable-span, SoC 0..1).
# The span runs from the configured low-voltage floor (0.0) to full (1.0), so
# 0% always lands on the shutdown threshold. Anchors derived from a 3.30 V floor.
_CURVE: list[tuple[float, float]] = [
    (1.0000, 1.00),
    (0.7778, 0.80),
    (0.6111, 0.60),
    (0.4667, 0.40),
    (0.3111, 0.20),
    (0.1667, 0.08),
    (0.0000, 0.00),
]


def _read(path: str) -> str | None:
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return None


def soc_from_voltage(volts: float | None, low_v: float | None = None) -> float | None:
    """Estimate state-of-charge (0..100) from a Li-ion cell voltage.

    Anchored so ``low_v`` (the configured shutdown threshold) reads 0% and
    ``BATTERY_FULL_V`` reads 100%. Under load the cell sags, so this reads low -
    it is an estimate, not a coulomb count.
    """
    if volts is None:
        return None
    floor = low_v if low_v is not None else BATTERY_LOW_V_DEFAULT
    if volts <= floor:
        return 0.0
    if volts >= BATTERY_FULL_V:
        return 100.0
    span = BATTERY_FULL_V - floor
    if span <= 0:
        return 0.0
    frac = (volts - floor) / span
    # Piecewise-linear interpolation over the normalised discharge shape.
    for (f0, s0), (f1, s1) in zip(_CURVE, _CURVE[1:], strict=False):
        if f1 <= frac <= f0:
            width = f0 - f1
            t = 0.0 if width <= 0 else (frac - f1) / width
            return round((s1 + t * (s0 - s1)) * 100.0, 1)
    return 0.0


def runtime_s(soc_pct: float | None, iout_a: float | None) -> int | None:
    """Approximate remaining runtime in seconds from charge and current draw."""
    if soc_pct is None or not iout_a or iout_a <= 0:
        return None
    remaining_mah = BATTERY_CAPACITY_MAH * (soc_pct / 100.0)
    hours = remaining_mah / (iout_a * 1000.0)
    return int(hours * 3600.0)


def undershoot_runtime(runtime: int | None, now: float | None = None) -> int | None:
    """Report the lowest runtime estimate seen in the last ``RUNTIME_WINDOW_S``.

    Load and voltage wobble, so a single instantaneous estimate can overstate
    the remaining time. Tracking the worst recent value makes the indicator
    undershoot: it holds the pessimistic estimate for up to the window, then
    recovers once that low point ages out.
    """
    now = time.monotonic() if now is None else now
    while _runtime_window and now - _runtime_window[0][0] > RUNTIME_WINDOW_S:
        _runtime_window.popleft()
    if runtime is not None:
        _runtime_window.append((now, runtime))
    if not _runtime_window:
        return None
    return min(estimate for _, estimate in _runtime_window)


def reset_runtime_window() -> None:
    """Clear the undershoot window (used when leaving battery power, and tests)."""
    _runtime_window.clear()


def _read_bms() -> dict:
    raw = _read(BMS_STATUS)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def read_bms() -> dict:
    """Public accessor for the raw BMS snapshot (empty when unavailable)."""
    return _read_bms()


def _sysfs_battery() -> tuple[float | None, bool]:
    for d in sorted(glob.glob(os.path.join(_POWER_SUPPLY, "*"))):
        kind = _read(os.path.join(d, "type"))
        if kind not in ("Battery", "UPS"):
            continue
        cap = _read(os.path.join(d, "capacity"))
        status = (_read(os.path.join(d, "status")) or "").lower()
        pct = float(cap) if cap is not None else None
        charging = status in ("charging", "full")
        return pct, charging
    return None, False


def _sysfs_temperature() -> float | None:
    for zone in sorted(glob.glob(os.path.join(_THERMAL, "thermal_zone*"))):
        raw = _read(os.path.join(zone, "temp"))
        if raw is None:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        return value / 1000.0 if value > 1000 else value
    return None


def snapshot(hardware=None) -> dict:
    """Return the metrics blob sent to the kiosk (matches protocol.Metrics)."""
    bms = _read_bms()
    esp: dict = {}
    if hardware is not None and hasattr(hardware, "telemetry"):
        try:
            esp = hardware.telemetry() or {}
        except Exception:  # noqa: BLE001 - never let metrics break the loop
            esp = {}

    # --- battery: BMS first, sysfs fallback ---
    power_mode = bms.get("power_mode")
    on_battery = power_mode is not None and int(power_mode) != 0
    low_v = bms.get("low_v")
    vin_v = bms.get("vin_v") if on_battery else None
    charging = bool(bms.get("charging"))

    battery_v = vin_v
    battery_pct = soc_from_voltage(vin_v, low_v)
    if on_battery:
        runtime = undershoot_runtime(runtime_s(battery_pct, bms.get("iout_a")))
    else:
        reset_runtime_window()
        runtime = None

    if battery_pct is None and not on_battery:
        # No BMS (or on USB with no battery data): fall back to sysfs.
        battery_pct, sysfs_charging = _sysfs_battery()
        if not bms:
            charging = sysfs_charging

    # --- temperatures (settings page): LM75B, ESP32, AD5933, Pi SoC ---
    temp_wittypi_c = bms.get("temp_c")
    temp_esp32_c = esp.get("temp_esp32_c")
    temp_ad5933_c = esp.get("temp_ad5933_c")
    temp_pi_c = _sysfs_temperature()

    return {
        "battery_pct": battery_pct,
        "battery_charging": charging,
        "on_battery": on_battery,
        "battery_v": battery_v,
        "runtime_s": runtime,
        "low_v": low_v if low_v is not None else BATTERY_LOW_V_DEFAULT,
        "temp_wittypi_c": temp_wittypi_c,
        "temp_esp32_c": temp_esp32_c,
        "temp_ad5933_c": temp_ad5933_c,
        "temp_pi_c": temp_pi_c,
    }
