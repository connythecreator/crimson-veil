"""AD5933 impedance-converter I2C device driver.

Construct with the hardware I2C bus and config, then call action methods.
"""

import time

# Register address pointer.
REG_CONTROL = 0x80
REG_START_FREQ = 0x82
REG_FREQ_INC = 0x85
REG_NUM_INC = 0x88
REG_SETTLE = 0x8A
REG_STATUS = 0x8F
REG_TEMP = 0x92
REG_REAL = 0x94
REG_IMAG = 0x96

# Control-register command codes (D15-D12).
CMD_INIT_START_FREQ = 0x10
CMD_START_SWEEP = 0x20
CMD_INCREMENT_FREQ = 0x30
CMD_REPEAT_FREQ = 0x40
CMD_MEASURE_TEMP = 0x90
CMD_POWER_DOWN = 0xA0
CMD_STANDBY = 0xB0

# Control bits below the command.
OUTPUT_RANGE_2VPP = 0b00
OUTPUT_RANGE_1VPP = 0b01
OUTPUT_RANGE_400MV = 0b10
OUTPUT_RANGE_200MV = 0b11
PGA_GAIN_1 = 0
PGA_GAIN_5 = 1

# Status register bits.
STATUS_TEMP_VALID = 0x01
STATUS_DATA_VALID = 0x02

DEFAULT_I2C_ADDRESS = 0x0D
DEFAULT_MCLK_HZ = 16_776_000.0
DEFAULT_OUTPUT_RANGE = OUTPUT_RANGE_2VPP
DEFAULT_PGA_GAIN = PGA_GAIN_1
DEFAULT_SETTLE_CYCLES = 15
DEFAULT_TIMEOUT_MS = 1000


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

    def standby(self):
        self._command(CMD_STANDBY)

    def power_down(self):
        self._command(CMD_POWER_DOWN)

    def halt(self):
        self.power_down()

    def set_frequency(self, freq_hz):
        if not 0 < freq_hz < self.mclk_hz / 4.0:
            raise AD5933Error(f"frequency {freq_hz} out of range")
        self._write_reg(REG_START_FREQ, self.frequency_code(freq_hz), 3)

    def start_sweep(self):
        self._command(CMD_START_SWEEP)

    def data_ready(self):
        return bool(self._read_reg(REG_STATUS, 1) & STATUS_DATA_VALID)

    def read_impedance(self):
        real = self._twos_complement(self._read_reg(REG_REAL, 2), 16)
        imag = self._twos_complement(self._read_reg(REG_IMAG, 2), 16)
        return real, imag

    def measure(self, freq_hz):
        """Return one raw ``(real, imag)`` impedance point at ``freq_hz``."""
        raise AD5933Error(
            "AD5933 measurement sequence not brought up yet; verify on the "
            "bench (docs/eit-bioimpedance/eit-netlist.md section 8)"
        )

    def start_temperature(self):
        self._command(CMD_MEASURE_TEMP)

    def read_temperature(self):
        return self._twos_complement(self._read_reg(REG_TEMP, 2), 14) / 32.0

    def temperature_c(self):
        try:
            self.start_temperature()
            self._wait_status(STATUS_TEMP_VALID)
            return self.read_temperature()
        except Exception:  # noqa: BLE001
            return None

    def frequency_code(self, freq_hz):
        return int(freq_hz * (1 << 27) / (self.mclk_hz / 4.0)) & 0xFFFFFF

    def _control_word(self, command):
        range_bits = (self.output_range & 0b11) << 9
        gain_bit = (self.pga_gain & 0b1) << 8
        return command | range_bits | gain_bit

    def _command(self, command):
        self._write_reg(REG_CONTROL, self._control_word(command), 2)

    def _write_reg(self, reg, value, nbytes):
        self.i2c.writeto_mem(self.addr, reg, value.to_bytes(nbytes, "big"))

    def _read_reg(self, reg, nbytes):
        return int.from_bytes(self.i2c.readfrom_mem(self.addr, reg, nbytes), "big")

    def _wait_status(self, mask):
        deadline = time.ticks_add(time.ticks_ms(), self.timeout_ms)
        while not (self._read_reg(REG_STATUS, 1) & mask):
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise AD5933Error("AD5933 status timeout")
            time.sleep_ms(1)

    @staticmethod
    def _twos_complement(value, bits):
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value
