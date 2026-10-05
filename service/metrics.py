"""Device metrics for the kiosk status bar (battery, temperature).

The ESP32 is the primary source: it reports battery and temperature telemetry
over the serial link and the hardware backend caches it. When that data is
unavailable (sim backend, or an ESP32 that does not report a field) this falls
back to standard Linux sysfs nodes. Every value is best-effort and may be
``None``.
"""

from __future__ import annotations

import glob
import os

_POWER_SUPPLY = "/sys/class/power_supply"
_THERMAL = "/sys/class/thermal"


def _read(path: str) -> str | None:
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return None


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
    """Return battery/temperature metrics for the kiosk.

    Prefers telemetry reported by the ESP32 (via ``hardware.telemetry()``) and
    falls back to sysfs per field when the ESP32 has nothing to offer.
    """
    telemetry: dict = {}
    if hardware is not None and hasattr(hardware, "telemetry"):
        try:
            telemetry = hardware.telemetry() or {}
        except Exception:  # noqa: BLE001 - never let metrics break the loop
            telemetry = {}

    pct = telemetry.get("battery_pct")
    charging = telemetry.get("battery_charging")
    temp = telemetry.get("temp_c")

    if pct is None:
        pct, sysfs_charging = _sysfs_battery()
        if charging is None:
            charging = sysfs_charging
    if temp is None:
        temp = _sysfs_temperature()

    return {
        "battery_pct": pct,
        "battery_charging": bool(charging),
        "temp_c": temp,
    }
