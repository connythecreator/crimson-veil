"""AD5933 byte-wise/address-pointer protocol used by the MP hwtest driver."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

HWTEST = Path(__file__).resolve().parents[1] / "firmware" / "mp-firm" / "hwtest"


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "hwtest_ad5933_driver", HWTEST / "ad5933_driver.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def driver_module():
    return _load_driver()


class FakeI2C:
    """AD5933 model: writes are register,value; reads use pointer 0xB0."""

    def __init__(
        self,
        status=0x03,
        real=1000,
        imag=-250,
        temp_code=25 * 32,
        control=0x00,
        control2=0x00,
    ):
        self.registers: dict[int, int] = {
            0x80: control,
            0x81: control2,
            0x8F: status,
        }
        self._set16(0x94, real)
        self._set16(0x96, imag)
        self._set16(0x92, temp_code)
        self.pointer = 0
        self.writes: list[bytes] = []
        self.scan_result = [0x0D]

    def _set16(self, reg, value):
        value &= 0xFFFF
        self.registers[reg] = (value >> 8) & 0xFF
        self.registers[reg + 1] = value & 0xFF

    def writeto(self, _addr, data):
        data = bytes(data)
        self.writes.append(data)
        if len(data) >= 2 and data[0] == 0xB0:
            self.pointer = data[1]
            return
        if len(data) >= 2:
            self.pointer = data[0]
            for value in data[1:]:
                self.registers[self.pointer] = value
                self.pointer = (self.pointer + 1) & 0xFF

    def readfrom(self, _addr, nbytes):
        out = bytearray()
        for _ in range(nbytes):
            out.append(self.registers.get(self.pointer, 0))
            self.pointer = (self.pointer + 1) & 0xFF
        return bytes(out)

    def scan(self):
        return list(self.scan_result)


def _control_writes(i2c, value):
    return [write for write in i2c.writes if write == bytes([0x80, value])]


def test_initialize_is_byte_wise_and_configures_control(driver_module):
    i2c = FakeI2C(control=0x07)
    driver = driver_module.AD5933(i2c)

    driver.initialize()

    assert bytes([0x81, 0x10]) in i2c.writes  # reset
    assert bytes([0x81, 0x00]) in i2c.writes  # internal clock
    assert bytes([0x8A, 0x00]) in i2c.writes
    assert bytes([0x8B, 0x0F]) in i2c.writes
    assert i2c.registers[0x80] == 0x00  # range 2Vpp, PGA x1
    assert all(len(write) <= 2 for write in i2c.writes)


def test_set_start_frequency_writes_three_separate_bytes(driver_module):
    i2c = FakeI2C()
    driver = driver_module.AD5933(i2c)
    code = driver.frequency_code(50_000.0)

    driver.set_frequency(50_000.0)

    assert bytes([0x82, (code >> 16) & 0xFF]) in i2c.writes
    assert bytes([0x83, (code >> 8) & 0xFF]) in i2c.writes
    assert bytes([0x84, code & 0xFF]) in i2c.writes
    assert all(len(write) <= 2 for write in i2c.writes)


def test_set_increment_frequency_and_number_increments(driver_module):
    i2c = FakeI2C()
    driver = driver_module.AD5933(i2c)

    driver.set_increment_frequency(1_000.0)
    driver.set_number_increments(40)

    code = driver.frequency_code(1_000.0)
    assert bytes([0x85, (code >> 16) & 0xFF]) in i2c.writes
    assert bytes([0x86, (code >> 8) & 0xFF]) in i2c.writes
    assert bytes([0x87, code & 0xFF]) in i2c.writes
    assert bytes([0x88, 0x00]) in i2c.writes
    assert bytes([0x89, 40]) in i2c.writes


def test_measure_uses_pointer_reads_and_only_short_writes(driver_module):
    i2c = FakeI2C(real=1000, imag=-250)
    driver = driver_module.AD5933(i2c)

    real, imag = driver.measure(50_000.0)

    assert (real, imag) == (1000, -250)
    assert all(len(write) <= 2 for write in i2c.writes)
    for reg in (0x8F, 0x94, 0x95, 0x96, 0x97):
        assert bytes([0xB0, reg]) in i2c.writes
    for mode in (0xB0, 0x10, 0x20, 0xA0):
        assert _control_writes(i2c, mode)


def test_control_mode_preserves_range_and_pga(driver_module):
    i2c = FakeI2C(control=0x07)
    driver = driver_module.AD5933(i2c)

    driver.set_control_mode(driver_module.CMD_START_SWEEP)

    assert i2c.registers[0x80] == 0x27


def test_temperature_uses_pointer_registers(driver_module):
    i2c = FakeI2C(status=0x03, temp_code=25 * 32)
    driver = driver_module.AD5933(i2c)

    assert driver.read_temperature() == pytest.approx(25.0)
    assert bytes([0xB0, 0x92]) in i2c.writes
    assert bytes([0xB0, 0x93]) in i2c.writes


def test_temperature_returns_none_on_timeout(driver_module):
    i2c = FakeI2C(status=0)
    driver = driver_module.AD5933(i2c, timeout_ms=0)

    assert driver.temperature_c() is None


def test_measure_timeout_powers_down(driver_module):
    i2c = FakeI2C(status=0)
    driver = driver_module.AD5933(i2c, timeout_ms=0)

    with pytest.raises(driver_module.AD5933Error, match="status timeout"):
        driver.measure(50_000.0)

    assert bytes([0x80, 0xA0]) in i2c.writes


def test_set_frequency_rejects_out_of_range(driver_module):
    driver = driver_module.AD5933(FakeI2C())
    with pytest.raises(driver_module.AD5933Error, match="out of range"):
        driver.set_frequency(driver.mclk_hz)


def test_two_s_complement(driver_module):
    assert driver_module.AD5933._twos_complement(0xFFFF, 16) == -1
    assert driver_module.AD5933._twos_complement(0x7FFF, 16) == 32767
    assert driver_module.AD5933._twos_complement(0x1FFF, 14) == 8191
    assert driver_module.AD5933._twos_complement(0x2000, 14) == -8192
