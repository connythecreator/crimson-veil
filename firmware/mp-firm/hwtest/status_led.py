"""Fixed-duration flashing LED for self-test failure indication.

GPIO2 is active-high on this build and is driven low at boot. A hardware
timer toggles the LED at 5 Hz for a fixed window after ``fail()``; ``ok()``
clears the window and leaves the LED off.
"""

try:
    from machine import Pin, Timer
except ImportError:  # CPython / unit tests
    Pin = None
    Timer = None

try:
    from time import ticks_diff, ticks_ms
except ImportError:  # CPython / unit tests
    import time

    def ticks_ms():
        return int(time.monotonic() * 1000)

    def ticks_diff(later, earlier):
        return later - earlier


class StatusLED:
    """Flash an active-high LED for a fixed time after a failed self-test."""

    def __init__(self, pin, active_high=True, period_ms=100, duration_ms=5000):
        self._active_high = bool(active_high)
        self._period_ms = int(period_ms)
        self._duration_ms = int(duration_ms)
        self._failed_until = None
        self._on = False
        self._pin = Pin(pin, Pin.OUT) if Pin is not None else None
        self._write(False)
        self._timer = None
        if Timer is not None:
            self._timer = Timer(0)
            self._timer.init(
                period=self._period_ms,
                mode=Timer.PERIODIC,
                callback=self._tick,
            )

    def _write(self, on):
        if self._pin is not None:
            self._pin.value(1 if on == self._active_high else 0)

    def _tick(self, _timer=None):
        if self._failed_until is None:
            self._write(False)
            return
        if ticks_diff(ticks_ms(), self._failed_until) >= 0:
            self._failed_until = None
            self._on = False
            self._write(False)
            return
        self._on = not self._on
        self._write(self._on)

    def fail(self):
        """Start (or restart) the fixed-duration flash window."""
        self._failed_until = ticks_ms() + self._duration_ms
        self._on = False
        self._write(False)

    def ok(self):
        """Stop flashing immediately and leave the LED off."""
        self._failed_until = None
        self._on = False
        self._write(False)
