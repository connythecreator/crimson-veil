"""Status LED flash behavior (active-high, boot-low, fixed duration)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "firmware" / "mp-firm" / "src"


def _load():
    spec = importlib.util.spec_from_file_location("status_led_under_test", SRC / "status_led.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePin:
    OUT = "out"
    instances = {}

    def __init__(self, number, mode):
        self.number = number
        self.mode = mode
        self.level = None
        FakePin.instances[number] = self

    def value(self, level=None):
        if level is None:
            return self.level
        self.level = level


class FakeTimer:
    PERIODIC = "periodic"
    instances = []

    def __init__(self, number):
        self.number = number
        self.callback = None
        self.period = None
        self.mode = None
        FakeTimer.instances.append(self)

    def init(self, period=None, mode=None, callback=None):
        self.period = period
        self.mode = mode
        self.callback = callback


def _led(active_high=True, duration_ms=5000, pin=2):
    module = _load()
    module.Pin = FakePin
    module.Timer = FakeTimer
    FakePin.instances.clear()
    FakeTimer.instances.clear()
    led = module.StatusLED(pin, active_high, 100, duration_ms)
    return module, led, FakePin.instances[pin]


def test_led_is_low_at_boot_active_high():
    _, _, pin = _led(active_high=True)
    assert pin.level == 0


def test_led_flashes_on_fail_and_stops_on_ok():
    _, led, pin = _led(active_high=True)
    assert FakeTimer.instances[0].period == 100

    led.fail()
    led._tick()
    assert pin.level == 1
    led._tick()
    assert pin.level == 0

    led.fail()
    led._tick()
    assert pin.level == 1
    led.ok()
    assert pin.level == 0


def test_led_active_low_is_off_at_boot_and_flashes_low():
    _, led, pin = _led(active_high=False)
    assert pin.level == 1

    led.fail()
    led._tick()
    assert pin.level == 0
    led.ok()
    assert pin.level == 1


def test_led_flash_window_is_fixed():
    _, led, pin = _led(active_high=True, duration_ms=0)
    led.fail()
    led._tick()
    assert pin.level == 0
    assert led._failed_until is None
