"""Hardware self-test shown by the kiosk before the main HUD.

Produces an ordered list of named checks, each with a status of ``pass``,
``fail``, ``warn`` or ``skip`` and a short human-readable detail. The checks are
deliberately independent: one failing subsystem must not hide the state of the
others, so the terminal-style screen can show e.g. ``Battery....PASS`` and
``PyEIT....FAIL`` side by side.

The ESP32 checks command the firmware over the existing serial protocol:
``probe()`` asks it to re-announce itself, and ``selftest()`` asks it to verify
the AD5933/mux path. See ``hardware/esp32.py`` and ``firmware/mp-firm``.
"""

from __future__ import annotations

import importlib.util
import time
from dataclasses import asdict, dataclass

from . import metrics


@dataclass
class Check:
    name: str
    status: str  # pass | fail | warn | skip
    detail: str = ""


def _is_esp(hardware) -> bool:
    """True when the open backend is the real ESP32 (not the sim)."""
    return type(hardware).__name__ == "Esp32Hardware"


def battery_check() -> Check:
    """Witty Pi BMS: fresh snapshot and a plausible reading."""
    bms = metrics.read_bms()
    if not bms:
        return Check("Battery", "fail", "BMS telemetry missing (/run/veil-bms)")

    ts = bms.get("ts")
    try:
        fresh = ts is not None and abs(time.time() - float(ts)) <= 30.0
    except (TypeError, ValueError):
        fresh = False
    if not fresh:
        return Check("Battery", "fail", "BMS telemetry stale")

    mode = bms.get("power_mode")
    if mode is not None and int(mode) != 0:
        pct = metrics.soc_from_voltage(bms.get("vin_v"), bms.get("low_v"))
        detail = "on battery"
        if pct is not None:
            detail += f" {pct:.0f}%"
        if bms.get("vin_v") is not None:
            detail += f" / {float(bms['vin_v']):.2f} V"
        return Check("Battery", "pass", detail)
    return Check("Battery", "pass", "USB power")


def esp_check(session) -> Check:
    """Belt controller: command the ESP32 and wait for its ``hello``."""
    hardware = session.hardware
    if hardware is None:
        return Check(
            "Belt Controller (ESP)", "fail", session.boot_error or "not connected"
        )

    if not _is_esp(hardware):
        return Check(
            "Belt Controller (ESP)", "skip", f"mock backend ({session.identify()})"
        )

    try:
        hello = hardware.probe()
    except Exception as exc:  # noqa: BLE001 - report the failure, do not crash
        return Check("Belt Controller (ESP)", "fail", f"{type(exc).__name__}: {exc}")

    firmware = hello.get("firmware", "?")
    n_electrodes = hello.get("n_electrodes", "?")
    return Check(
        "Belt Controller (ESP)", "pass", f"fw {firmware}, {n_electrodes} electrodes"
    )


def impedance_check(session) -> Check:
    """Impedance subsystem: firmware probe of the AD5933 and mux bank."""
    hardware = session.hardware
    if hardware is None:
        return Check("Impedance Subsystem", "skip", "ESP not connected")
    if not _is_esp(hardware):
        return Check("Impedance Subsystem", "skip", "mock backend")

    try:
        result = hardware.selftest()
    except Exception as exc:  # noqa: BLE001 - report the failure, do not crash
        return Check("Impedance Subsystem", "fail", f"{type(exc).__name__}: {exc}")

    if not result.get("ad5933"):
        return Check(
            "Impedance Subsystem",
            "fail",
            str(result.get("error") or "AD5933 not responding"),
        )

    detail = "AD5933 responding"
    temp = result.get("temp_ad5933_c")
    if temp is not None:
        detail += f" ({float(temp):.1f} C)"
    return Check("Impedance Subsystem", "pass", detail)


def pyeit_check() -> Check:
    """Reconstruction: the solver is selected and importable."""
    from software.core import config

    if config.SOLVER_BACKEND != "pyeit":
        return Check("PyEIT", "fail", f"solver is {config.SOLVER_BACKEND!r}, not 'pyeit'")
    if importlib.util.find_spec("pyeit") is None:
        return Check("PyEIT", "fail", "pyeit not installed")
    return Check("PyEIT", "pass", "pyeit solver available")


def service_check(session) -> Check:
    """The control service itself (reaching this code proves it is up)."""
    return Check("Control Service", "pass", session.identify())


def run_self_test(session) -> list[dict]:
    """Run every check and return JSON-ready dicts.

    One boot retry happens first so hardware attached after the service started
    can come up without restarting the process. Failures are captured by the
    individual checks rather than raised.
    """
    if not session.booted:
        try:
            session.boot()
        except Exception:  # noqa: BLE001 - surfaced by esp_check's boot_error
            pass

    checks = [
        battery_check(),
        esp_check(session),
        impedance_check(session),
        pyeit_check(),
        service_check(session),
    ]
    return [asdict(check) for check in checks]
