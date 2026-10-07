"""Main.py: creates defaults and runs loop
"""

import sys

try:
    from machine import I2C, Pin
except ImportError:  # host / CI
    I2C = None
    Pin = None

import protocol
from ad5933_driver import AD5933, OUTPUT_RANGE_2VPP, PGA_GAIN_1, AD5933Error

# configuration
FIRMWARE_VERSION = "1.0.0"

#eletrode defaults
N_ELECTRODES = 8
SUPPORTED_ELECTRODE_COUNTS = (4, 8, 16)

SWEEP_HZ = 50_000.0

I2C_ID = 0
I2C_SCL = 22
I2C_SDA = 21
I2C_FREQ = 400_000
AD5933_ADDR = 0x0D

AD5933_MCLK_HZ = 16_776_000.0
AD5933_OUTPUT_RANGE = OUTPUT_RANGE_2VPP
AD5933_PGA_GAIN = PGA_GAIN_1
AD5933_SETTLE_CYCLES = 15
AD5933_TIMEOUT_MS = 1000

MUX_ADDR = (25, 26, 27, 23)  # S0, S1, S2, S3
MUX_ENABLE = {
    "drive_pos": 32,
    "drive_neg": 33,
    "sense_pos": 14,
    "sense_neg": 13,
}

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
    """Per-frequency complex correction applied to raw data."""

    def __init__(self, factors=None):
        self._factors = dict(factors or {})

    def factor(self, freq_hz):
        return self._factors.get(freq_hz, complex(1.0, 0.0))

    def apply(self, freq_hz, real, imag):
        z = complex(real, imag) / self.factor(freq_hz)
        return z.real, z.imag


class MuxBank:
    """CD74HC4067 bank: shared address bits + active-low enable per role."""

    def __init__(self):
        self._addr = [Pin(pin, Pin.OUT) for pin in MUX_ADDR]
        self._enable = {role: Pin(pin, Pin.OUT) for role, pin in MUX_ENABLE.items()}
        self.disable_all()

    def disable_all(self):
        for pin in self._enable.values():
            pin.value(1)

    def enable(self, role):
        self._enable[role].value(0)

    def disable(self, role):
        self._enable[role].value(1)

    def set_address(self, electrode):
        if not 0 <= electrode < (1 << len(self._addr)):
            raise ValueError(f"electrode {electrode!r} out of address range")
        for bit, pin in enumerate(self._addr):
            pin.value((electrode >> bit) & 1)


class Firmware:
    """Protocol state machine; owns the scan process and mux selection."""

    def __init__(self, driver, mux=None, calibration=None):
        self._driver = driver
        self._mux = mux
        self._calibration = calibration or CalibrationTable()
        self._running = False

    def boot(self):
        protocol.send_hello(
            firmware=FIRMWARE_VERSION,
            n_electrodes=N_ELECTRODES,
            electrodes=list(range(N_ELECTRODES)),
            sweep_hz=SWEEP_HZ,
        )

    def stop(self):
        self._running = False
        if self._mux is not None:
            self._mux.disable_all()
        if self._driver is not None:
            self._driver.halt()

    def select_measurement(self, drive, sense):
        """Configure the mux bank for one tetrapolar drive/sense pair."""
        if self._mux is None:
            return
        for electrode in (*drive, *sense):
            if not 0 <= electrode < N_ELECTRODES:
                raise ValueError(f"electrode pair out of range: {drive} / {sense}")

        self._mux.disable_all()
        self._mux.set_address(drive[0])
        self._mux.enable("drive_pos")
        self._mux.set_address(drive[1])
        self._mux.enable("drive_neg")
        self._mux.set_address(sense[0])
        self._mux.enable("sense_pos")
        self._mux.set_address(sense[1])
        self._mux.enable("sense_neg")

    def handle(self, message):
        kind = message.get("type")
        if kind == "identify":
            self.boot()
        elif kind == "scan":
            self._scan(message)
        elif kind == "stop":
            self.stop()
        else:
            protocol.send_error(f"unknown message type: {kind!r}")
        return kind

    def _scan(self, message):
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
            except AD5933Error as exc:
                self.stop()
                protocol.send_error(f"acquisition failed: {exc}")
                return
            re, im = self._calibration.apply(freq, re, im)
            points.append({"n": index, "f": freq, "re": re, "im": im})
        self.stop()
        protocol.send_frame(points)

    def telemetry(self):
        try:
            temperature = self._driver.temperature_c()
        except Exception:  # noqa: BLE001
            temperature = None
        protocol.send_telemetry(
            battery_pct=None,
            battery_charging=False,
            temp_c=temperature,
        )

    def run(self, stream=None):
        if stream is None:
            stream = sys.stdin
        self._running = True
        while self._running:
            line = protocol.read_line(stream)
            if line is None:
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
    firmware = Firmware(driver, mux=MuxBank())
    firmware.boot()
    firmware.run()


if __name__ == "__main__":
    main()
