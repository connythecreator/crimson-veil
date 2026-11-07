"""Standalone impedance-repeatability firmware for the bench capacitor rig.

This tree is separate from both the production EIT firmware and the hwtest
firmware. It uses the same AD5933 driver and calibration rules, but instead of
summarising one acquisition it returns every individual complex sample at one
frequency. The host repeats the same physical measurement 40 times so the 40
boundary values can be compared with the ideal capacitor and projected through
the EIT solver.

Bench fixture (no mux):
    C between Drive+ and Drive-
    Sense+ strapped to Drive+, Sense- strapped to Drive-

Protocol (one JSON object per line):

    host -> ESP32
        {"type":"imperr_identify"}
        {"type":"imperr_run","seq":1,"f":50000,"samples":40,
         "range":"1vpp","discard":1,"apply_calibration":true}
        {"type":"imperr_stop"}

    ESP32 -> host
        {"type":"imperr_hello","firmware":"imperr 1.0.0","default_f":50000,
         "default_samples":40,"range":"1vpp",
         "calibration":{"present":true,"entries":2,"error":null}}
        {"type":"imperr_result","seq":1,"f_hz":50000,
         "temp_ad5933_c":30.0,"status":"pass","error":null,
         "calibration":{"present":true,"error":null,"k_re":...,"k_im":...},
         "samples":[{"n":0,"raw_re":...,"raw_im":...,"z_re":...,
                     "z_im":...,"saturated":false}, ...]}
"""

import json
import math
import sys
import time

try:
    from machine import I2C, Pin
except ImportError:  # CPython / unit tests
    I2C = None
    Pin = None

import status_led
from ad5933_driver import (
    AD5933,
    OUTPUT_RANGE_1VPP,
    OUTPUT_RANGE_2VPP,
    OUTPUT_RANGE_200MV,
    OUTPUT_RANGE_400MV,
    PGA_GAIN_1,
    AD5933Error,
)

FIRMWARE_VERSION = "imperr 1.0.0"
CALIBRATION_FILE = "cal.json"
DEFAULT_FREQ_HZ = 50_000.0
DEFAULT_SAMPLES = 40
DEFAULT_RANGE_NAME = "1vpp"
CAL_REF_MAG_TOL_PCT = 10.0
CAL_REF_PHASE_TOL_DEG = 5.0

RANGE_VALUES = {
    "2vpp": OUTPUT_RANGE_2VPP,
    "1vpp": OUTPUT_RANGE_1VPP,
    "400mv": OUTPUT_RANGE_400MV,
    "200mv": OUTPUT_RANGE_200MV,
}

I2C_ID = 0
# Bench wiring: GPIO22 = SCL, GPIO21 = SDA.
I2C_SCL = 22
I2C_SDA = 21
I2C_FREQ = 100_000
AD5933_ADDR = 0x0D

AD5933_MCLK_HZ = 16_776_000.0
AD5933_OUTPUT_RANGE = OUTPUT_RANGE_1VPP
AD5933_PGA_GAIN = PGA_GAIN_1
AD5933_SETTLE_CYCLES = 15
AD5933_TIMEOUT_MS = 1000

# GPIO2 is active-high on this build and must be low during boot.
LED_PIN = 2
LED_ACTIVE_HIGH = True
LED_FLASH_MS = 100
LED_FLASH_DURATION_MS = 5_000


def _default_sink(line):
    print(line)


sink = _default_sink


def emit(message):
    sink(json.dumps(message))


def read_line(stream):
    raw = stream.readline()
    if not raw:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeError:
            # Serial noise on open must not crash the command loop.
            return ""
    return raw.rstrip("\r\n")


def wrap_deg(angle):
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


class CalibrationTable:
    """Per-frequency complex calibration ``K``, where ``Z = K / raw``."""

    def __init__(self, factors=None):
        self._factors = dict(factors or {})

    def __len__(self):
        return len(self._factors)

    def factor(self, freq_hz):
        if not self._factors:
            return complex(1.0, 0.0)
        exact = self._factors.get(freq_hz)
        if exact is not None:
            return exact
        best = None
        best_diff = None
        for candidate, factor in self._factors.items():
            diff = abs(candidate - freq_hz)
            if best_diff is None or diff < best_diff:
                best = factor
                best_diff = diff
        return best if best is not None else complex(1.0, 0.0)

    def apply(self, freq_hz, real, imag):
        raw = complex(real, imag)
        if raw == 0:
            raise AD5933Error("zero raw measurement; check the fixture/AD5933")
        z = self.factor(freq_hz) / raw
        return z.real, z.imag


def load_calibration(path=CALIBRATION_FILE):
    """Load and combine the resistor/capacitor references like production.

    Returns ``(CalibrationTable, error, factors)``. The magnitude reference is
    the resistor and the phase reference is the capacitor. A missing or invalid
    file returns an empty table and an error string. ``factors`` is a
    JSON-ready list of the combined per-frequency factors so the host can pick
    an exact-frequency reference without reading the filesystem again.
    """
    try:
        handle = open(path)
        try:
            data = json.loads(handle.read())
        finally:
            handle.close()
    except OSError:
        return CalibrationTable(), "calibration file missing: " + path, []
    except ValueError as exc:
        return CalibrationTable(), "calibration file invalid: " + str(exc), []

    entries = data.get("entries") if isinstance(data, dict) else None
    by_freq = {}
    for entry in entries or []:
        try:
            if entry.get("status", "pass") not in ("pass", "warn"):
                continue
            freq = float(entry["f"])
            k_re = float(entry["k_re"])
            k_im = float(entry["k_im"])
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if freq <= 0:
            continue
        fixture = str(entry.get("fixture", "capacitor")).lower()
        if fixture not in ("capacitor", "resistor"):
            continue
        entry_range = str(entry.get("range", DEFAULT_RANGE_NAME)).lower()
        if entry_range != DEFAULT_RANGE_NAME:
            continue
        by_freq.setdefault(freq, {})[fixture] = complex(k_re, k_im)

    factors = {}
    mismatches = []
    for freq, references in by_freq.items():
        resistor = references.get("resistor")
        capacitor = references.get("capacitor")
        if resistor is not None and capacitor is not None:
            resistor_mag = abs(resistor)
            capacitor_mag = abs(capacitor)
            mag_diff = (
                abs(resistor_mag - capacitor_mag) / resistor_mag * 100.0
                if resistor_mag
                else 0.0
            )
            phase_diff = abs(
                wrap_deg(
                    math.degrees(math.atan2(resistor.imag, resistor.real))
                    - math.degrees(math.atan2(capacitor.imag, capacitor.real))
                )
            )
            if mag_diff > CAL_REF_MAG_TOL_PCT or phase_diff > CAL_REF_PHASE_TOL_DEG:
                mismatches.append(
                    str(freq)
                    + " Hz: "
                    + str(round(mag_diff, 1))
                    + "% / "
                    + str(round(phase_diff, 1))
                    + " deg"
                )
            phase = math.atan2(capacitor.imag, capacitor.real)
            factors[freq] = complex(
                abs(resistor) * math.cos(phase), abs(resistor) * math.sin(phase)
            )
        elif resistor is not None:
            factors[freq] = resistor
        else:
            factors[freq] = capacitor

    if mismatches:
        return CalibrationTable(), (
            "calibration references disagree: " + "; ".join(mismatches)
        ), []
    if not factors:
        return CalibrationTable(), "calibration file has no usable entries: " + path, []

    factor_info = []
    for frequency in sorted(factors):
        factor = factors[frequency]
        references = by_freq.get(frequency, {})
        factor_info.append(
            {
                "f": frequency,
                "k_re": factor.real,
                "k_im": factor.imag,
                "sources": sorted(references.keys()),
            }
        )
    return CalibrationTable(factors), None, factor_info


class ImperrFirmware:
    """Owns the serial command loop and the repeated-sample acquisition."""

    def __init__(self, driver, led=None):
        self._driver = driver
        self._led = led
        (
            self._calibration,
            self._calibration_error,
            self._calibration_info,
        ) = load_calibration()
        self._range_name = DEFAULT_RANGE_NAME
        self._running = False

    def _set_led(self, failed):
        if self._led is None:
            return
        if failed:
            self._led.fail()
        else:
            self._led.ok()

    def _apply_range(self, range_name=None):
        name = str(self._range_name if range_name is None else range_name).lower()
        if name not in RANGE_VALUES:
            raise ValueError("range must be 2vpp, 1vpp, 400mv or 200mv")
        setter = getattr(self._driver, "set_output_range", None)
        if setter is not None:
            setter(RANGE_VALUES[name])
        self._range_name = name
        return name

    def boot(self):
        emit(
            {
                "type": "imperr_hello",
                "firmware": FIRMWARE_VERSION,
                "default_f": DEFAULT_FREQ_HZ,
                "default_samples": DEFAULT_SAMPLES,
                "range": self._range_name,
                "calibration": {
                    "present": len(self._calibration) > 0,
                    "entries": len(self._calibration),
                    "error": self._calibration_error,
                    "factors": self._calibration_info,
                },
            }
        )

    def stop(self):
        try:
            self._driver.halt()
        except Exception:  # noqa: BLE001 - best effort on stop
            pass
        emit({"type": "imperr_stopped"})

    def _sample_record(self, index, raw_re, raw_im, freq_hz, apply_calibration):
        raw_mag = math.sqrt(raw_re * raw_re + raw_im * raw_im)
        record = {
            "n": index,
            "raw_re": raw_re,
            "raw_im": raw_im,
            "raw_mag": raw_mag,
            "saturated": abs(raw_re) >= 32_700 or abs(raw_im) >= 32_700,
            "z_re": None,
            "z_im": None,
            "z_mag": None,
            "z_phase_deg": None,
        }
        if apply_calibration and len(self._calibration) > 0:
            z_re, z_im = self._calibration.apply(freq_hz, raw_re, raw_im)
            record["z_re"] = z_re
            record["z_im"] = z_im
            record["z_mag"] = math.sqrt(z_re * z_re + z_im * z_im)
            record["z_phase_deg"] = math.degrees(math.atan2(z_im, z_re))
        return record

    def run_once(self, seq=0, freq_hz=DEFAULT_FREQ_HZ, samples=DEFAULT_SAMPLES,
                 range_name=None, discard=1, apply_calibration=True):
        try:
            frequency = float(freq_hz)
            requested = int(samples)
            skipped = int(discard)
            if frequency <= 0:
                raise ValueError("frequency must be positive")
            if requested < 1:
                raise ValueError("samples must be at least 1")
            if skipped < 0:
                raise ValueError("discard must be non-negative")
            if apply_calibration and len(self._calibration) == 0:
                raise ValueError(
                    "calibration unavailable: "
                    + str(self._calibration_error or "no entries")
                )
            self._apply_range(range_name)
        except (TypeError, ValueError) as exc:
            payload = {
                "type": "imperr_result",
                "seq": seq,
                "f_hz": freq_hz,
                "status": "fail",
                "error": f"{type(exc).__name__}: {exc}",
                "samples": [],
            }
            emit(payload)
            self._set_led(True)
            return payload

        try:
            temperature = self._driver.temperature_c()
        except Exception:  # noqa: BLE001 - reported as null, not fatal
            temperature = None

        records = []
        error = None
        try:
            for _ in range(skipped):
                self._driver.measure(frequency)
            for index in range(requested):
                raw_re, raw_im = self._driver.measure(frequency)
                records.append(
                    self._sample_record(
                        index, float(raw_re), float(raw_im), frequency,
                        bool(apply_calibration),
                    )
                )
        except (AD5933Error, ValueError, TypeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001 - a hardware fault must be reported
            error = f"{type(exc).__name__}: {exc}"

        if error is None and not records:
            error = "no samples acquired"
        if error is None:
            nonfinite = [
                record["n"]
                for record in records
                if not math.isfinite(record["raw_re"])
                or not math.isfinite(record["raw_im"])
            ]
            if nonfinite:
                error = "non-finite samples at " + str(nonfinite)
        if error is None and any(record["saturated"] for record in records):
            error = "saturated sample(s); reduce excitation or fixture current"

        k_re = None
        k_im = None
        if len(self._calibration) > 0:
            factor = self._calibration.factor(frequency)
            k_re = factor.real
            k_im = factor.imag

        status = "pass" if error is None else "fail"
        payload = {
            "type": "imperr_result",
            "seq": seq,
            "firmware": FIRMWARE_VERSION,
            "f_hz": frequency,
            "temp_ad5933_c": temperature,
            "range": self._range_name,
            "discard": max(0, int(discard)),
            "calibration": {
                "present": len(self._calibration) > 0,
                "error": self._calibration_error,
                "k_re": k_re,
                "k_im": k_im,
            },
            "samples": records,
            "status": status,
            "error": error,
        }
        emit(payload)
        self._set_led(status == "fail")
        return payload

    def handle(self, message):
        kind = message.get("type")
        if kind == "imperr_run":
            self.run_once(
                seq=message.get("seq", 0),
                freq_hz=message.get("f", DEFAULT_FREQ_HZ),
                samples=message.get("samples", DEFAULT_SAMPLES),
                range_name=message.get("range", self._range_name),
                discard=message.get("discard", 1),
                apply_calibration=message.get("apply_calibration", True),
            )
        elif kind == "imperr_identify":
            self.boot()
        elif kind == "imperr_stop":
            self.stop()
        else:
            emit({"type": "imperr_error", "message": "unknown message type: " + repr(kind)})
        return kind

    def run(self, stream=None):
        if stream is None:
            stream = sys.stdin
        self._running = True
        while self._running:
            line = read_line(stream)
            if line is None:
                # Keep the bench firmware alive when the USB host has not
                # opened the port yet; host-side test streams still end at EOF.
                if stream is sys.stdin:
                    time.sleep(0.01)
                    continue
                self._running = False
                break
            if not line:
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict) or "type" not in message:
                    raise ValueError("message must be a JSON object with a 'type'")
            except ValueError as exc:
                emit({"type": "imperr_error", "message": "malformed message: " + str(exc)})
                continue
            try:
                self.handle(message)
            except Exception as exc:  # noqa: BLE001 - never crash the command loop
                emit({"type": "imperr_error", "message": "internal error: " + str(exc)})


def main():
    if I2C is None or Pin is None:
        raise RuntimeError("machine.I2C is only available on the ESP32")
    i2c = I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
    driver = AD5933(
        i2c,
        addr=AD5933_ADDR,
        mclk_hz=AD5933_MCLK_HZ,
        output_range=AD5933_OUTPUT_RANGE,
        pga_gain=AD5933_PGA_GAIN,
        settle_cycles=AD5933_SETTLE_CYCLES,
        timeout_ms=AD5933_TIMEOUT_MS,
    )
    try:
        driver.initialize()
    except Exception:  # noqa: BLE001 - the first run reports the failure
        pass
    led = status_led.StatusLED(
        LED_PIN, LED_ACTIVE_HIGH, LED_FLASH_MS, LED_FLASH_DURATION_MS
    )
    firmware = ImperrFirmware(driver, led=led)
    firmware.boot()
    firmware.run()


if __name__ == "__main__":
    main()
