"""Standalone AD5933 driver for the bench hardware test.

The I2C protocol here mirrors the working ``mjmeli/arduino-ad5933`` library:

* writes are one register byte per I2C transaction (never multi-byte writes)
* reads use the AD5933 address-pointer register (``0xB0``)
* the control register is read/modify/written so range and PGA bits survive
* a single-point measurement uses standby -> init -> start -> data-valid
* temperature has explicit start/ready/raw/read functions with a timeout

The driver targets MicroPython on the ESP32 but also runs under CPython so the
measurement sequence can be unit-tested with a fake I2C bus.
"""

import time

# AD5933 I2C address pointer: write 0xB0, then the target register.
ADDR_PTR = 0xB0

# Register addresses.
REG_CONTROL = 0x80
REG_CONTROL_2 = 0x81
REG_START_FREQ = 0x82
REG_FREQ_INC = 0x85
REG_NUM_INC = 0x88
REG_SETTLE = 0x8A
REG_STATUS = 0x8F
REG_TEMP = 0x92
REG_REAL = 0x94
REG_IMAG = 0x96

# Control-register commands (D15-D12).
CMD_INIT_START_FREQ = 0x10
CMD_START_SWEEP = 0x20
CMD_INCREMENT_FREQ = 0x30
CMD_REPEAT_FREQ = 0x40
CMD_MEASURE_TEMP = 0x90
CMD_POWER_DOWN = 0xA0
CMD_STANDBY = 0xB0

# Control register 2 bits.
CTRL_RESET = 0x10
CLOCK_INTERNAL = 0x00
CLOCK_EXTERNAL = 0x08

# Output excitation range bits (control register D10-D9), matching the
# Arduino library's constants.
OUTPUT_RANGE_2VPP = 0x00
OUTPUT_RANGE_1VPP = 0x06
OUTPUT_RANGE_400MV = 0x04
OUTPUT_RANGE_200MV = 0x02

# PGA gain bits (control register D8).
PGA_GAIN_1 = 0
PGA_GAIN_5 = 1

# Status register bits.
STATUS_TEMP_VALID = 0x01
STATUS_DATA_VALID = 0x02
STATUS_SWEEP_DONE = 0x04
STATUS_ERROR = 0xFF

DEFAULT_I2C_ADDRESS = 0x0D
DEFAULT_MCLK_HZ = 16_776_000.0
DEFAULT_OUTPUT_RANGE = OUTPUT_RANGE_2VPP
DEFAULT_PGA_GAIN = PGA_GAIN_1
DEFAULT_SETTLE_CYCLES = 15
DEFAULT_TIMEOUT_MS = 1000

# The AD5933 real/imag registers are 16-bit two's complement. Treat values
# close to the limits as saturated: the bench test needs to reject clipped data
# rather than calibrate against it.
ADC_SATURATION_LIMIT = 32_700


def _ticks_ms():
    try:
        return time.ticks_ms()
    except AttributeError:  # CPython / unit tests
        return int(time.monotonic() * 1000)


def _ticks_add(ticks, delta):
    try:
        return time.ticks_add(ticks, delta)
    except AttributeError:  # CPython / unit tests
        return ticks + delta


def _ticks_diff(a, b):
    try:
        return time.ticks_diff(a, b)
    except AttributeError:  # CPython / unit tests
        return a - b


def _sleep_ms(milliseconds):
    try:
        time.sleep_ms(milliseconds)
    except AttributeError:  # CPython / unit tests
        time.sleep(max(0, milliseconds) / 1000.0)


class AD5933Error(RuntimeError):
    pass


class AD5933:
    """AD5933 impedance converter on a MicroPython ``machine.I2C`` bus."""

    def __init__(
        self,
        i2c,
        addr=DEFAULT_I2C_ADDRESS,
        mclk_hz=DEFAULT_MCLK_HZ,
        output_range=DEFAULT_OUTPUT_RANGE,
        pga_gain=DEFAULT_PGA_GAIN,
        settle_cycles=DEFAULT_SETTLE_CYCLES,
        timeout_ms=DEFAULT_TIMEOUT_MS,
    ):
        self.i2c = i2c
        self.addr = addr
        self.mclk_hz = mclk_hz
        self.output_range = output_range
        self.pga_gain = pga_gain
        self.settle_cycles = settle_cycles
        self.timeout_ms = timeout_ms

    # --- transport --------------------------------------------------------

    def _send_byte(self, reg, value):
        """Write one register byte using a 2-byte I2C transaction."""
        self.i2c.writeto(self.addr, bytes([reg & 0xFF, value & 0xFF]))

    def _get_byte(self, reg):
        """Read one register byte through the AD5933 address pointer."""
        self.i2c.writeto(self.addr, bytes([ADDR_PTR, reg & 0xFF]))
        data = self.i2c.readfrom(self.addr, 1)
        if not data:
            raise AD5933Error("empty I2C read")
        return data[0]

    def _write_bytes(self, reg, value, nbytes):
        """Write a 16/24-bit value one register byte at a time."""
        for index in range(nbytes - 1, -1, -1):
            self._send_byte(reg + (nbytes - 1 - index), (value >> (8 * index)) & 0xFF)

    def _read_bytes(self, reg, nbytes):
        value = 0
        for index in range(nbytes):
            value = (value << 8) | self._get_byte(reg + index)
        return value

    # --- configuration ----------------------------------------------------

    def reset(self):
        value = self._get_byte(REG_CONTROL_2)
        self._send_byte(REG_CONTROL_2, value | CTRL_RESET)

    def set_internal_clock(self, internal=True):
        self._send_byte(REG_CONTROL_2, CLOCK_INTERNAL if internal else CLOCK_EXTERNAL)

    def set_range(self):
        value = self._get_byte(REG_CONTROL)
        value = (value & 0xF9) | (self.output_range & 0x06)
        self._send_byte(REG_CONTROL, value)

    def set_pga_gain(self):
        value = self._get_byte(REG_CONTROL)
        value = (value & 0xFE) | (self.pga_gain & 0x01)
        self._send_byte(REG_CONTROL, value)

    def set_settling_cycles(self):
        self._write_bytes(REG_SETTLE, int(self.settle_cycles) & 0x1FF, 2)

    def initialize(self):
        """Reset and configure clock/range/PGA/settling once at boot."""
        self.reset()
        self.set_internal_clock(True)
        self.set_range()
        self.set_pga_gain()
        self.set_settling_cycles()

    def set_control_mode(self, mode):
        """Read/modify/write the control register, preserving range/PGA."""
        value = self._get_byte(REG_CONTROL)
        value = (value & 0x0F) | (mode & 0xF0)
        self._send_byte(REG_CONTROL, value)

    def standby(self):
        self.set_control_mode(CMD_STANDBY)

    def power_down(self):
        self.set_control_mode(CMD_POWER_DOWN)

    def halt(self):
        self.power_down()

    # --- sweep configuration ---------------------------------------------

    def set_frequency(self, freq_hz):
        if not 0 < freq_hz < self.mclk_hz / 4.0:
            raise AD5933Error("frequency " + str(freq_hz) + " out of range")
        self._write_bytes(REG_START_FREQ, self.frequency_code(freq_hz), 3)

    def set_increment_frequency(self, freq_hz):
        self._write_bytes(REG_FREQ_INC, self.frequency_code(freq_hz), 3)

    def set_number_increments(self, count):
        self._write_bytes(REG_NUM_INC, int(count) & 0xFFFF, 2)

    def configure_sweep(self, freq_hz):
        """Configure one measurement at ``freq_hz`` with no increments."""
        self.set_frequency(freq_hz)
        self.set_increment_frequency(0)
        self.set_number_increments(0)
        self.set_settling_cycles()

    def start_sweep(self):
        self.set_control_mode(CMD_START_SWEEP)

    def data_ready(self):
        return bool(self._get_byte(REG_STATUS) & STATUS_DATA_VALID)

    def read_impedance(self):
        real = self._twos_complement(self._read_bytes(REG_REAL, 2), 16)
        imag = self._twos_complement(self._read_bytes(REG_IMAG, 2), 16)
        return real, imag

    def measure(self, freq_hz):
        """Return one raw ``(real, imag)`` point at ``freq_hz``."""
        # Return to standby before reprogramming the sweep registers. The part
        # may have been left in temperature mode or power-down by a prior call.
        self.standby()
        self.configure_sweep(freq_hz)
        self.set_control_mode(CMD_INIT_START_FREQ)
        self._sleep_settling(freq_hz)

        # A previous timed-out conversion can leave DATA_VALID set. Read and
        # discard stale data so the next start-sweep wait is for fresh samples.
        if self._get_byte(REG_STATUS) & STATUS_DATA_VALID:
            self.read_impedance()

        try:
            self.set_control_mode(CMD_START_SWEEP)
            self._wait_status(STATUS_DATA_VALID)
            return self.read_impedance()
        finally:
            self.power_down()

    def _sleep_settling(self, freq_hz):
        cycles = max(1, int(self.settle_cycles))
        milliseconds = int((cycles * 1000.0) / freq_hz) + 5
        _sleep_ms(milliseconds)

    # --- temperature ------------------------------------------------------

    def start_temperature(self):
        self.set_control_mode(CMD_MEASURE_TEMP)

    def temperature_ready(self):
        status = self._get_byte(REG_STATUS)
        return status != STATUS_ERROR and bool(status & STATUS_TEMP_VALID)

    def read_temperature_raw(self):
        value = self._read_bytes(REG_TEMP, 2)
        raw = value & 0x1FFF
        if value & 0x2000:
            raw -= 0x4000
        return raw

    def read_temperature(self, timeout_ms=None):
        self.start_temperature()
        self._wait_status(STATUS_TEMP_VALID, timeout_ms)
        return self.read_temperature_raw() / 32.0

    def get_temperature(self, timeout_ms=None):
        return self.read_temperature(timeout_ms)

    def temperature_c(self):
        try:
            return self.read_temperature()
        except Exception:  # noqa: BLE001 - report the failure, do not crash
            return None

    # --- helpers ----------------------------------------------------------

    def frequency_code(self, freq_hz):
        return int(freq_hz * (1 << 27) / (self.mclk_hz / 4.0)) & 0xFFFFFF

    def _wait_status(self, mask, timeout_ms=None):
        timeout = self.timeout_ms if timeout_ms is None else timeout_ms
        deadline = _ticks_add(_ticks_ms(), timeout)
        while True:
            status = self._get_byte(REG_STATUS)
            if status == STATUS_ERROR:
                raise AD5933Error("AD5933 status read failed")
            if status & mask:
                return status
            if _ticks_diff(deadline, _ticks_ms()) <= 0:
                raise AD5933Error("AD5933 status timeout")
            _sleep_ms(1)

    @staticmethod
    def _twos_complement(value, bits):
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value
