"""Standalone bench-test firmware for the AD5933 front end.

This firmware is intentionally separate from the production EIT firmware in
``firmware/mp-firm/src``. It does not use a mux, mock tables, pyEIT or the
Raspberry Pi backend; it only exercises the AD5933 and the analog channel that
is wired directly to it.

Bench fixture:
    C = 0.1 uF between Drive+ and Drive-
    Sense+ strapped to Drive+, Sense- strapped to Drive-

On boot it emits ``hwtest_hello`` and runs the default check (50 kHz). It then
accepts line-delimited JSON commands over USB serial.
"""

import json
import sys

try:
    from machine import I2C, Pin
except ImportError:  # CPython / unit tests
    I2C = None
    Pin = None

import hwtest_core
from ad5933_driver import AD5933, OUTPUT_RANGE_2VPP, PGA_GAIN_1, AD5933Error

FIRMWARE_VERSION = "hwtest 1.2.0"

CALIBRATION_FILE = "cal.json"
DEFAULT_FREQ_HZ = 50_000.0
DEFAULT_CAL_FREQS = (10_000.0, 50_000.0)
DEFAULT_CAPACITANCE_F = 0.1e-6
DEFAULT_SAMPLES = 16
DEFAULT_TOL_PCT = 5.0
DEFAULT_TOL_DEG = 5.0
DEFAULT_DRIFT_PCT = 2.0
DEFAULT_DRIFT_DEG = 2.0

I2C_ID = 0
# Bench wiring: GPIO22 = SCL, GPIO21 = SDA.
I2C_SCL = 22
I2C_SDA = 21
I2C_FREQ = 100_000
AD5933_ADDR = 0x0D

AD5933_MCLK_HZ = 16_776_000.0
AD5933_OUTPUT_RANGE = OUTPUT_RANGE_2VPP
AD5933_PGA_GAIN = PGA_GAIN_1
AD5933_SETTLE_CYCLES = 15
AD5933_TIMEOUT_MS = 1000


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
        raw = raw.decode("utf-8")
    return raw.rstrip("\r\n")


def _status(checks):
    if any(item["status"] == "fail" for item in checks):
        return "fail"
    if any(item["status"] == "warn" for item in checks):
        return "warn"
    return "pass"


def load_calibration_file(path=None):
    """Load existing entries so a calibration run can merge into them."""
    if path is None:
        path = CALIBRATION_FILE
    try:
        handle = open(path)
        try:
            data = json.loads(handle.read())
        finally:
            handle.close()
    except OSError:
        return {}, "calibration file missing: " + path
    except ValueError as exc:
        return {}, "calibration file invalid: " + str(exc)

    entries = data.get("entries") if isinstance(data, dict) else None
    result = {}
    for entry in entries or []:
        try:
            freq = float(entry["f"])
            k_re = float(entry["k_re"])
            k_im = float(entry["k_im"])
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if freq > 0:
            result[freq] = {
                "f": freq,
                "k_re": k_re,
                "k_im": k_im,
                "mag": entry.get("mag"),
                "phase_deg": entry.get("phase_deg"),
                "status": entry.get("status", "pass"),
            }
    return result, None


def save_calibration_file(entries, capacitance_f, path=None):
    if path is None:
        path = CALIBRATION_FILE
    ordered = [entries[freq] for freq in sorted(entries.keys())]
    data = {
        "version": 1,
        "fixture": {"kind": "capacitor", "c_f": float(capacitance_f)},
        "entries": ordered,
    }
    handle = open(path, "w")
    try:
        handle.write(json.dumps(data))
    finally:
        handle.close()
    return ordered


class HwTestFirmware:
    """Owns the serial command loop and the bench measurement sequence."""

    def __init__(
        self,
        driver,
        capacitance_f=DEFAULT_CAPACITANCE_F,
        samples=DEFAULT_SAMPLES,
        tol_pct=DEFAULT_TOL_PCT,
        tol_deg=DEFAULT_TOL_DEG,
        drift_pct=DEFAULT_DRIFT_PCT,
        drift_deg=DEFAULT_DRIFT_DEG,
    ):
        self._driver = driver
        self._capacitance_f = float(capacitance_f)
        self._samples = int(samples)
        self._tol_pct = float(tol_pct)
        self._tol_deg = float(tol_deg)
        self._drift_pct = float(drift_pct)
        self._drift_deg = float(drift_deg)
        self._calibration_entries, self._calibration_error = load_calibration_file()
        self._running = False

    def boot(self):
        emit(
            {
                "type": "hwtest_hello",
                "firmware": FIRMWARE_VERSION,
                "fixture": {"kind": "capacitor", "c_f": self._capacitance_f},
                "default_f": DEFAULT_FREQ_HZ,
                "default_samples": self._samples,
                "calibration": {
                    "present": bool(self._calibration_entries),
                    "entries": len(self._calibration_entries),
                    "error": self._calibration_error,
                },
            }
        )

    def stop(self):
        try:
            self._driver.halt()
        except Exception:  # noqa: BLE001 - best effort on stop
            pass

    def _i2c_check(self):
        i2c = getattr(self._driver, "i2c", None)
        if i2c is None or not hasattr(i2c, "scan"):
            return hwtest_core.check("i2c", "skip", "no I2C handle")
        try:
            found = [int(address) for address in i2c.scan()]
        except Exception as exc:  # noqa: BLE001 - report, do not crash
            return hwtest_core.check("i2c", "fail", f"{type(exc).__name__}: {exc}")
        address = hex(AD5933_ADDR)
        if AD5933_ADDR in found:
            return hwtest_core.check("i2c", "pass", "AD5933 at " + address)
        return hwtest_core.check(
            "i2c",
            "fail",
            "AD5933 " + address + " not found; saw " + str(found),
        )

    def _temperature_check(self, temperature):
        if temperature is None:
            return hwtest_core.check("temperature", "warn", "AD5933 temperature unavailable")
        readable = str(round(float(temperature), 2)) + " C"
        if -40.0 <= float(temperature) <= 125.0:
            return hwtest_core.check("temperature", "pass", readable)
        return hwtest_core.check(
            "temperature", "warn", readable + " outside -40..125 C"
        )

    def _acquisition_check(self, samples, requested, error):
        if error:
            return hwtest_core.check("acquisition", "fail", error)
        if len(samples) != requested:
            return hwtest_core.check(
                "acquisition",
                "fail",
                f"collected {len(samples)} of {requested} samples",
            )
        if not samples or all(real == 0 and imag == 0 for real, imag in samples):
            return hwtest_core.check("acquisition", "fail", "raw AD5933 data is all zero")
        for index, (real, imag) in enumerate(samples):
            if hwtest_core.is_saturated(real, imag):
                return hwtest_core.check(
                    "acquisition",
                    "fail",
                    f"sample {index} saturated (re={real}, im={imag})",
                )
        return hwtest_core.check("acquisition", "pass", f"{len(samples)} samples")

    def run_once(
        self,
        seq=0,
        freq_hz=DEFAULT_FREQ_HZ,
        capacitance_f=None,
        samples=None,
        tol_pct=None,
        tol_deg=None,
        drift_pct=None,
        drift_deg=None,
        emit_result=True,
    ):
        freq_hz = float(freq_hz)
        capacitance_f = float(
            self._capacitance_f if capacitance_f is None else capacitance_f
        )
        requested = int(self._samples if samples is None else samples)
        tol_pct = float(self._tol_pct if tol_pct is None else tol_pct)
        tol_deg = float(self._tol_deg if tol_deg is None else tol_deg)
        drift_pct = float(self._drift_pct if drift_pct is None else drift_pct)
        drift_deg = float(self._drift_deg if drift_deg is None else drift_deg)

        try:
            temperature = self._driver.temperature_c()
        except Exception:  # noqa: BLE001 - the check reports the failure
            temperature = None

        checks = [self._i2c_check(), self._temperature_check(temperature)]
        raw_samples = []
        error = None

        try:
            if freq_hz <= 0:
                raise ValueError("frequency must be positive")
            if capacitance_f <= 0:
                raise ValueError("capacitance must be positive")
            if requested < 2:
                raise ValueError("samples must be at least 2")
            # Discard one warm-up point: the first post-configuration
            # conversion is often biased and would skew the calibration.
            self._driver.measure(freq_hz)
            for _ in range(requested):
                real, imag = self._driver.measure(freq_hz)
                raw_samples.append((float(real), float(imag)))
        except (AD5933Error, ValueError, TypeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001 - a hardware fault must be reported
            error = f"{type(exc).__name__}: {exc}"

        acquisition = self._acquisition_check(raw_samples, requested, error)
        checks.append(acquisition)

        result = {
            "type": "hwtest_result",
            "seq": seq,
            "firmware": FIRMWARE_VERSION,
            "f_hz": freq_hz,
            "temp_ad5933_c": temperature,
            "fixture": {"kind": "capacitor", "c_f": capacitance_f},
            "expected": None,
            "raw": None,
            "calibration": None,
            "measured": None,
            "drift": None,
            "tolerances": {
                "mag_pct": tol_pct,
                "phase_deg": tol_deg,
                "drift_pct": drift_pct,
                "drift_deg": drift_deg,
            },
            "checks": checks,
            "status": "fail",
            "error": error,
        }

        try:
            expected = hwtest_core.expected_impedance(freq_hz, capacitance_f)
            result["expected"] = {
                "re": expected.real,
                "im": expected.imag,
                "mag": hwtest_core.magnitude(expected),
                "phase_deg": hwtest_core.phase_deg(expected),
            }
        except ValueError as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"

        if acquisition["status"] == "pass":
            try:
                evaluation = hwtest_core.evaluate(
                    freq_hz,
                    capacitance_f,
                    raw_samples,
                    tol_pct=tol_pct,
                    tol_deg=tol_deg,
                    drift_pct=drift_pct,
                    drift_deg=drift_deg,
                )
                result.update(
                    {
                        "raw": evaluation["raw"],
                        "calibration": evaluation["calibration"],
                        "measured": evaluation["measured"],
                        "drift": evaluation["drift"],
                        "expected": evaluation["expected"],
                    }
                )
                checks.extend(evaluation["checks"])
            except (ValueError, ZeroDivisionError) as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
                checks.append(hwtest_core.check("calibration", "fail", str(exc)))

        result["status"] = _status(checks)
        if emit_result:
            emit(result)
        return result

    def calibrate(
        self,
        seq=0,
        freqs=None,
        capacitance_f=None,
        samples=None,
        tol_pct=None,
        tol_deg=None,
        drift_pct=None,
        drift_deg=None,
    ):
        """Measure each frequency, merge ``K`` entries, and write cal.json."""
        capacitance_f = float(
            self._capacitance_f if capacitance_f is None else capacitance_f
        )
        requested = int(self._samples if samples is None else samples)
        tol_pct = float(self._tol_pct if tol_pct is None else tol_pct)
        tol_deg = float(self._tol_deg if tol_deg is None else tol_deg)
        drift_pct = float(self._drift_pct if drift_pct is None else drift_pct)
        drift_deg = float(self._drift_deg if drift_deg is None else drift_deg)

        if freqs is None:
            freqs = list(DEFAULT_CAL_FREQS)
        elif isinstance(freqs, str):
            freqs = freqs.split(",")
        frequencies = []
        for value in freqs:
            try:
                frequency = float(value)
            except (TypeError, ValueError):
                continue
            if frequency > 0 and frequency not in frequencies:
                frequencies.append(frequency)

        existing, _ = load_calibration_file()
        entries = dict(existing or self._calibration_entries)
        results = []
        error = None

        if not frequencies:
            error = "no valid calibration frequencies"
        else:
            for frequency in frequencies:
                result = self.run_once(
                    seq=0,
                    freq_hz=frequency,
                    capacitance_f=capacitance_f,
                    samples=requested,
                    tol_pct=tol_pct,
                    tol_deg=tol_deg,
                    drift_pct=drift_pct,
                    drift_deg=drift_deg,
                    emit_result=False,
                )
                results.append(result)
                calibration = result.get("calibration")
                if result["status"] in ("pass", "warn") and calibration:
                    entries[frequency] = {
                        "f": frequency,
                        "k_re": calibration["k_re"],
                        "k_im": calibration["k_im"],
                        "mag": calibration["k_mag"],
                        "phase_deg": calibration["k_phase_deg"],
                        "status": result["status"],
                    }
                elif error is None:
                    error = result.get("error") or (
                        "calibration failed at " + str(frequency) + " Hz"
                    )

        ordered = []
        if entries:
            try:
                ordered = save_calibration_file(entries, capacitance_f)
                self._calibration_entries = entries
                self._calibration_error = None
            except OSError as exc:
                error = "could not write " + CALIBRATION_FILE + ": " + str(exc)

        passed = sum(1 for result in results if result["status"] in ("pass", "warn"))
        if not results or passed == 0:
            status = "fail"
        elif error:
            status = "warn"
        elif any(result["status"] == "warn" for result in results):
            status = "warn"
        else:
            status = "pass"

        payload = {
            "type": "hwtest_calibration",
            "seq": seq,
            "file": CALIBRATION_FILE,
            "entries": ordered,
            "status": status,
            "error": error,
        }
        emit(payload)
        return payload

    def _temperature_only(self):
        try:
            temperature = self._driver.temperature_c()
        except Exception as exc:  # noqa: BLE001
            emit({"type": "hwtest_error", "message": f"{type(exc).__name__}: {exc}"})
            return
        emit({"type": "hwtest_temp", "temp_ad5933_c": temperature})

    def handle(self, message):
        kind = message.get("type")
        if kind == "hwtest_run":
            self.run_once(
                seq=message.get("seq", 0),
                freq_hz=message.get("f", DEFAULT_FREQ_HZ),
                capacitance_f=message.get("c_f", self._capacitance_f),
                samples=message.get("samples", self._samples),
                tol_pct=message.get("tol_pct", self._tol_pct),
                tol_deg=message.get("tol_deg", self._tol_deg),
                drift_pct=message.get("drift_pct", self._drift_pct),
                drift_deg=message.get("drift_deg", self._drift_deg),
            )
        elif kind == "hwtest_calibrate":
            self.calibrate(
                seq=message.get("seq", 0),
                freqs=message.get("freqs", list(DEFAULT_CAL_FREQS)),
                capacitance_f=message.get("c_f", self._capacitance_f),
                samples=message.get("samples", self._samples),
                tol_pct=message.get("tol_pct", self._tol_pct),
                tol_deg=message.get("tol_deg", self._tol_deg),
                drift_pct=message.get("drift_pct", self._drift_pct),
                drift_deg=message.get("drift_deg", self._drift_deg),
            )
        elif kind == "hwtest_identify":
            self.boot()
        elif kind == "hwtest_temp":
            self._temperature_only()
        elif kind == "hwtest_stop":
            self.stop()
        else:
            emit({"type": "hwtest_error", "message": f"unknown message type: {kind!r}"})
        return kind

    def run(self, stream=None):
        if stream is None:
            stream = sys.stdin
        self._running = True
        while self._running:
            line = read_line(stream)
            if line is None:
                self._running = False
                break
            if not line:
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict) or "type" not in message:
                    raise ValueError("message must be a JSON object with a 'type'")
            except ValueError as exc:
                emit({"type": "hwtest_error", "message": f"malformed message: {exc}"})
                continue
            try:
                self.handle(message)
            except Exception as exc:  # noqa: BLE001 - never crash the command loop
                emit({"type": "hwtest_error", "message": f"internal error: {exc}"})


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
    firmware = HwTestFirmware(driver)
    firmware.boot()
    firmware.run_once(seq=0)
    firmware.run()


if __name__ == "__main__":
    main()
