"""Main.py: creates defaults and runs loop
"""

import json
import math
import sys
import time

try:
    from machine import I2C, Pin
except ImportError:  # host / CI
    I2C = None
    Pin = None

import protocol
import status_led
from ad5933_driver import (
    AD5933,
    OUTPUT_RANGE_1VPP,
    PGA_GAIN_1,
    AD5933Error,
)

# configuration
FIRMWARE_VERSION = "1.1.0"
CALIBRATION_FILE = "cal.json"
OUTPUT_RANGE_NAME = "1vpp"
CAL_REF_MAG_TOL_PCT = 10.0
CAL_REF_PHASE_TOL_DEG = 5.0
# A raw AD5933 magnitude below this is treated as an open circuit by the mux
# continuity test. It is only a reporting hint; the raw values are returned.
MUX_TEST_OPEN_RAW = 10.0

# GPIO2 is active-high on this build and must be low during boot.
LED_PIN = 2
LED_ACTIVE_HIGH = True
LED_FLASH_MS = 100
LED_FLASH_DURATION_MS = 5_000

# On-device configuration written by the uploader; --mock also works under CPython.
try:
    from board_config import N_ELECTRODES, USE_MOCK
except ImportError:  # host/CI without board_config.py
    USE_MOCK = False
    N_ELECTRODES = 8


def _mock_mode():
    return USE_MOCK or "--mock" in getattr(sys, "argv", [])

SUPPORTED_ELECTRODE_COUNTS = (4, 8, 16)
if N_ELECTRODES not in SUPPORTED_ELECTRODE_COUNTS:
    raise ValueError(f"unsupported N_ELECTRODES: {N_ELECTRODES!r}")

SWEEP_HZ = 50_000.0

I2C_ID = 0
I2C_SCL = 22
I2C_SDA = 21
I2C_FREQ = 100_000
AD5933_ADDR = 0x0D

AD5933_MCLK_HZ = 16_776_000.0
AD5933_OUTPUT_RANGE = OUTPUT_RANGE_1VPP
AD5933_PGA_GAIN = PGA_GAIN_1
AD5933_SETTLE_CYCLES = 15
AD5933_TIMEOUT_MS = 1000

# The four CD74HC4067 muxes have independent 3-bit address buses. The board
# ties every ~E pin low, so the muxes are always enabled and non-latching; the
# firmware must never rely on an enable line to isolate a role.
MUX_ROLES = ("drive_pos", "drive_neg", "sense_pos", "sense_neg")
MUX_ADDR = {
    "drive_pos": (25, 33, 32),  # S0, S1, S2
    "drive_neg": (14, 27, 26),
    "sense_pos": (16, 17, 19),
    "sense_neg": (18, 23, 13),
}
_MUX_BITS = {len(pins) for pins in MUX_ADDR.values()}
if len(_MUX_BITS) != 1:
    raise ValueError("all mux roles must use the same number of address bits")
MUX_BITS = _MUX_BITS.pop()

BATTERY_ADC_PIN = None
TELEMETRY_INTERVAL_MS = 5_000


def default_scan(n_electrodes=N_ELECTRODES):
    """Return the fixed adjacent-drive sequence for ``n_electrodes``."""
    if n_electrodes not in SUPPORTED_ELECTRODE_COUNTS:
        raise ValueError(f"unsupported electrode count {n_electrodes!r}")
    sequence = []
    for e in range(n_electrodes):
        drive = (e, (e + 1) % n_electrodes)
        for k in range(n_electrodes - 3):
            sense = ((e + 2 + k) % n_electrodes, (e + 3 + k) % n_electrodes)
            sequence.append((drive, sense))
    return sequence


class CalibrationTable:
    """Per-frequency complex calibration ``K``, where ``Z = K / raw``.

    The hwtest firmware writes the entries; this class loads them and picks the
    nearest measured frequency when the scan frequency is not an exact match.
    """

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
        # No calibration means no known Z = K / S mapping. Leave the value
        # unchanged rather than silently returning its reciprocal.
        if not self._factors:
            return real, imag
        raw = complex(real, imag)
        if raw == 0:
            raise AD5933Error("zero raw measurement; check the fixture/AD5933")
        z = self.factor(freq_hz) / raw
        return z.real, z.imag


def _wrap_deg(angle):
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def load_calibration(path=CALIBRATION_FILE):
    """Load ``K`` entries written by the hwtest firmware.

    Returns ``(CalibrationTable, error)``. An empty table with an error string
    means the main firmware must refuse scans and report a hardware failure.
    """
    try:
        handle = open(path)
        try:
            data = json.loads(handle.read())
        finally:
            handle.close()
    except OSError:
        return CalibrationTable(), "calibration file missing: " + path
    except ValueError as exc:
        return CalibrationTable(), "calibration file invalid: " + str(exc)

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
        if str(entry.get("range", "2vpp")).lower() != OUTPUT_RANGE_NAME:
            continue
        by_freq.setdefault(freq, {})[fixture] = complex(k_re, k_im)

    # Combine the two references at each frequency: the 10k resistor is the
    # accurate magnitude reference, the capacitor is the known-phase reference.
    # Reject the table if the two references disagree; that means the front end
    # was nonlinear/clipped during one of the calibration stages.
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
                _wrap_deg(
                    math.degrees(math.atan2(resistor.imag, resistor.real))
                    - math.degrees(math.atan2(capacitor.imag, capacitor.real))
                )
            )
            if (
                mag_diff > CAL_REF_MAG_TOL_PCT
                or phase_diff > CAL_REF_PHASE_TOL_DEG
            ):
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
        )
    if not factors:
        return CalibrationTable(), "calibration file has no usable entries: " + path
    return CalibrationTable(factors), None


class MuxBank:
    """CD74HC4067 bank with independent address buses and no enable control.

    The board ties every ``~E`` pin low, so all four muxes are always enabled.
    Because the muxes are non-latching, each role keeps the electrode on its
    own S0..S2 bus; changing one role must not disturb the other three.
    """

    def __init__(self):
        self._addr = {
            role: [Pin(pin, Pin.OUT) for pin in MUX_ADDR[role]]
            for role in MUX_ROLES
        }
        self.park_all()

    def set_address(self, role, electrode):
        pins = self._addr.get(role)
        if pins is None:
            raise ValueError(f"unknown mux role: {role!r}")
        if not 0 <= electrode < (1 << len(pins)):
            raise ValueError(
                f"electrode {electrode!r} out of range for {role} "
                f"({len(pins)} address bits)"
            )
        for bit, pin in enumerate(pins):
            pin.value((electrode >> bit) & 1)

    def park_all(self):
        for role in MUX_ROLES:
            self.set_address(role, 0)


class Firmware:
    """Protocol state machine; owns the scan process and mux selection."""

    def __init__(
        self,
        driver,
        mux=None,
        calibration=None,
        calibration_error=None,
        led=None,
    ):
        self._driver = driver
        self._mux = mux
        self._calibration = calibration or CalibrationTable()
        self._calibration_error = calibration_error
        self._led = led
        self._running = False
        # The mock driver already returns impedance-like boundary voltages, so
        # the K / S calibration must not be applied to it (it would invert the
        # difference image).
        self._apply_calibration = not getattr(driver, "is_mock", False)

    def boot(self):
        protocol.send_hello(
            firmware=FIRMWARE_VERSION,
            n_electrodes=N_ELECTRODES,
            electrodes=list(range(N_ELECTRODES)),
            sweep_hz=SWEEP_HZ,
        )

    def stop(self):
        """Power down acquisition, then park every mux role on electrode 0."""
        try:
            if self._driver is not None:
                self._driver.halt()
        finally:
            if self._mux is not None:
                self._mux.park_all()

    def select_measurement(self, drive, sense):
        """Configure the four independent mux buses for one tetrapolar pair."""
        if self._mux is None:
            return
        electrodes = tuple(drive) + tuple(sense)
        for electrode in electrodes:
            if not 0 <= electrode < N_ELECTRODES:
                raise ValueError(f"electrode pair out of range: {drive} / {sense}")
        if len(set(electrodes)) != 4:
            raise ValueError(
                f"drive and sense must be four distinct electrodes: {drive} / {sense}"
            )

        self._mux.set_address("drive_pos", drive[0])
        self._mux.set_address("drive_neg", drive[1])
        self._mux.set_address("sense_pos", sense[0])
        self._mux.set_address("sense_neg", sense[1])

    def handle(self, message):
        kind = message.get("type")
        if kind == "identify":
            self.boot()
        elif kind == "scan":
            self._scan(message)
        elif kind == "selftest":
            self._selftest()
        elif kind == "mux_test":
            self._mux_test(message)
        elif kind == "mock_mode":
            self._mock_mode(message)
        elif kind == "stop":
            self.stop()
        else:
            protocol.send_error(f"unknown message type: {kind!r}")
        return kind

    def _scan(self, message):
        if self._calibration_error:
            protocol.send_error("calibration unavailable: " + self._calibration_error)
            return

        try:
            freq = float(message.get("f", SWEEP_HZ))
        except (TypeError, ValueError):
            protocol.send_error("bad scan frequency")
            return

        points = []
        for index, (drive, sense) in enumerate(default_scan(N_ELECTRODES)):
            try:
                self.select_measurement(drive, sense)
                re, im = self._driver.measure(freq)
                if self._apply_calibration:
                    re, im = self._calibration.apply(freq, re, im)
            except AD5933Error as exc:
                self.stop()
                protocol.send_error(f"acquisition failed: {exc}")
                return
            points.append({"n": index, "f": freq, "re": re, "im": im})
        self.stop()
        protocol.send_frame(points)

    def _mux_test(self, message):
        """Measure each electrode with all four mux roles on that electrode.

        With only electrode 0 wired, electrode 0 should show a finite loop
        (the mux on-resistance) and every other electrode should read open.
        The current ``cal.json`` is applied when it is valid; it is never
        modified. Raw values are always returned so a marginal threshold does
        not hide the hardware result.
        """
        if self._mux is None:
            protocol.send_error("mux_test needs a mux bank")
            return

        try:
            freq = float(message.get("f", SWEEP_HZ))
            min_raw = float(message.get("min_raw", MUX_TEST_OPEN_RAW))
            d_neg = message.get("d_neg")
            if d_neg is not None:
                d_neg = int(d_neg)
        except (TypeError, ValueError):
            protocol.send_error("bad mux_test frequency, min_raw or d_neg")
            return
        if min_raw < 0:
            protocol.send_error("min_raw must be non-negative")
            return
        if d_neg is not None and not 0 <= d_neg < N_ELECTRODES:
            protocol.send_error(f"d_neg {d_neg} out of range")
            return

        points = []
        try:
            for electrode in range(N_ELECTRODES):
                drive_neg = electrode if d_neg is None else d_neg
                self._mux.set_address("drive_pos", electrode)
                self._mux.set_address("drive_neg", drive_neg)
                self._mux.set_address("sense_pos", electrode)
                self._mux.set_address("sense_neg", electrode)
                raw_re, raw_im = self._driver.measure(freq)
                raw_abs = math.sqrt(raw_re * raw_re + raw_im * raw_im)
                entry = {
                    "e": electrode,
                    "drive_neg": drive_neg,
                    "raw_re": raw_re,
                    "raw_im": raw_im,
                    "raw_abs": raw_abs,
                    "status": "open" if raw_abs < min_raw else "connected",
                }
                if (
                    entry["status"] == "connected"
                    and self._calibration_error is None
                    and self._apply_calibration
                ):
                    z_re, z_im = self._calibration.apply(freq, raw_re, raw_im)
                    entry["z_re"] = z_re
                    entry["z_im"] = z_im
                    entry["z_abs"] = math.sqrt(z_re * z_re + z_im * z_im)
                points.append(entry)
        except AD5933Error as exc:
            self.stop()
            protocol.send_error(f"mux test failed: {exc}")
            return

        self.stop()
        protocol.emit(
            {
                "type": "mux_test_result",
                "frequency_hz": freq,
                "min_raw": min_raw,
                "d_neg": d_neg,
                "calibration": self._calibration_error is None,
                "points": points,
            }
        )

    def _mock_mode(self, message):
        setter = getattr(self._driver, "set_mode", None)
        if setter is None:
            protocol.send_error("mock_mode is only available with the mock driver")
            return
        try:
            mode = setter(message.get("mode", "auto"))
        except Exception as exc:  # noqa: BLE001
            protocol.send_error(f"bad mock mode: {exc}")
            return
        protocol.emit({"type": "mock_mode_result", "mode": mode})

    def _selftest(self):
        """Verify the AD5933, mux continuity and calibration state."""
        temp = None
        error = None
        ad5933 = False
        mux = self._mux is not None
        open_electrodes = []

        try:
            temp = self._driver.temperature_c()
            ad5933 = temp is not None
            if not ad5933:
                error = "AD5933 temperature read failed"
        except Exception as exc:  # noqa: BLE001 - report, never crash the loop
            error = f"AD5933: {exc}"

        if mux and not getattr(self._mux, "is_mock", False):
            # Continuity check: every mux role on the same electrode should
            # form a finite loop through that channel. An open channel reads
            # near zero. This deliberately does not use the bench-only D- C1
            # workaround; production hardware has no C0/C1 short. The mock mux
            # has no real channels, so it skips this check.
            try:
                for electrode in range(N_ELECTRODES):
                    for role in MUX_ROLES:
                        self._mux.set_address(role, electrode)
                    raw_re, raw_im = self._driver.measure(SWEEP_HZ)
                    raw_abs = math.sqrt(raw_re * raw_re + raw_im * raw_im)
                    if raw_abs < MUX_TEST_OPEN_RAW:
                        open_electrodes.append(electrode)
            except Exception as exc:  # noqa: BLE001
                mux = False
                error = f"mux: {exc}"
            finally:
                self._mux.park_all()

            if open_electrodes:
                mux = False
                error = "mux open: electrode(s) " + ", ".join(
                    str(electrode) for electrode in open_electrodes
                )

        calibration = self._calibration_error is None
        if not calibration and error is None:
            error = self._calibration_error

        if self._led is not None:
            if not ad5933 or not mux or not calibration or error is not None:
                self._led.fail()
            else:
                self._led.ok()

        protocol.send_selftest_result(
            ad5933=ad5933,
            mux=mux,
            temp_ad5933_c=temp,
            firmware=FIRMWARE_VERSION,
            error=error,
            calibration=calibration,
            calibration_entries=len(self._calibration),
            calibration_error=self._calibration_error,
        )

    def telemetry(self):
        # Battery is owned by the Witty Pi BMS on the host; the ESP32 reports
        # only its own die temperature and the AD5933 chip temperature.
        try:
            temp_ad5933 = self._driver.temperature_c()
        except Exception:  # noqa: BLE001
            temp_ad5933 = None
        try:
            import esp32  # MicroPython ESP32 module

            temp_esp32 = esp32.mcu_temperature()
        except Exception:  # noqa: BLE001
            temp_esp32 = None
        protocol.send_telemetry(temp_esp32_c=temp_esp32, temp_ad5933_c=temp_ad5933)

    def run(self, stream=None):
        if stream is None:
            stream = sys.stdin
        self._running = True
        while self._running:
            line = protocol.read_line(stream)
            if line is None:
                # On the ESP32 ``sys.stdin.readline()`` can return None when the
                # USB host has not opened the port yet. Keep the firmware alive
                # so the service can connect later instead of dropping to the
                # REPL. A host-side test stream still ends at EOF.
                if stream is sys.stdin:
                    time.sleep(0.01)
                    continue
                self._running = False
                break
            if not line:
                continue
            try:
                message = protocol.decode(line)
            except ValueError as exc:
                protocol.send_error(f"malformed message: {exc}")
                continue
            try:
                self.handle(message)
            except Exception as exc:  # noqa: BLE001
                protocol.send_error(f"internal error: {exc}")


def main():
    if _mock_mode():
        from mock_ad5933 import MockAD5933, MockMux

        led = status_led.StatusLED(
            LED_PIN, LED_ACTIVE_HIGH, LED_FLASH_MS, LED_FLASH_DURATION_MS
        )
        firmware = Firmware(
            MockAD5933(n_electrodes=N_ELECTRODES), mux=MockMux(), led=led
        )
        firmware.boot()
        firmware.run()
        return

    if N_ELECTRODES > (1 << MUX_BITS):
        raise ValueError(
            f"N_ELECTRODES={N_ELECTRODES} needs {N_ELECTRODES.bit_length()} "
            f"address bits per mux; the map provides {MUX_BITS}"
        )

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
    except Exception:  # noqa: BLE001 - selftest/scan report the failure
        pass
    calibration, calibration_error = load_calibration()
    led = status_led.StatusLED(
        LED_PIN, LED_ACTIVE_HIGH, LED_FLASH_MS, LED_FLASH_DURATION_MS
    )
    firmware = Firmware(
        driver,
        mux=MuxBank(),
        calibration=calibration,
        calibration_error=calibration_error,
        led=led,
    )
    firmware.boot()
    firmware.run()


if __name__ == "__main__":
    main()
