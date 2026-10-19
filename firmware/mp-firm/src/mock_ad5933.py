"""Mock front end for host/pipeline bring-up without an AD5933 or mux bank.

`MockAD5933` returns pre-computed FEM boundary voltages for a circular
8-electrode array at 50 kHz, in the firmware's adjacent drive/sense order
(`8 * (8 - 3) = 40` points). The tables were generated with pyEIT's forward
solver:

  baseline = homogeneous unit-conductivity mesh
  target   = the same mesh with a `PyEITAnomaly_Circle` (centre [0.5, 0.5],
             r 0.18, perm 2.0)

The first full scan serves the baseline (so the host can capture it as the
pyEIT reference); subsequent scans serve the target. `set_mode("baseline")`
resets that behaviour, which is useful after a re-capture.

`MockMux` is a no-op implementation of the mux interface so `select_measurement`
and the firmware self-test run unchanged.

This is a host/solver validation tool, not a physical acquisition model.
"""

# (real, imag) values in the firmware's adjacent order, 8 electrodes @ 50 kHz.
_BASELINE = [
    (-0.110581707, 0),
    (-0.0599305835, 0),
    (-0.0503823652, 0),
    (-0.0599610632, 0),
    (-0.110300096, 0),
    (-0.110590551, 0),
    (-0.0599199617, 0),
    (-0.0504527884, 0),
    (-0.0599733634, 0),
    (-0.110336774, 0),
    (-0.110341396, 0),
    (-0.0599652459, 0),
    (-0.0504519344, 0),
    (-0.059900058, 0),
    (-0.110581707, 0),
    (-0.110249202, 0),
    (-0.0599429419, 0),
    (-0.0503594962, 0),
    (-0.0599305835, 0),
    (-0.110590551, 0),
    (-0.110507297, 0),
    (-0.0598492531, 0),
    (-0.0503823652, 0),
    (-0.0599199617, 0),
    (-0.110341396, 0),
    (-0.11048977, 0),
    (-0.0599610632, 0),
    (-0.0504527884, 0),
    (-0.0599652459, 0),
    (-0.110249202, 0),
    (-0.110300096, 0),
    (-0.0599733634, 0),
    (-0.0504519344, 0),
    (-0.0599429419, 0),
    (-0.110507297, 0),
    (-0.110336774, 0),
    (-0.059900058, 0),
    (-0.0503594962, 0),
    (-0.0598492531, 0),
    (-0.11048977, 0),
]

_TARGET = [
    (-0.108909373, 0),
    (-0.054487508, 0),
    (-0.0518063529, 0),
    (-0.0608498234, 0),
    (-0.111005018, 0),
    (-0.0948397542, 0),
    (-0.0617649223, 0),
    (-0.0519481932, 0),
    (-0.0612790337, 0),
    (-0.111811321, 0),
    (-0.095284726, 0),
    (-0.0551057208, 0),
    (-0.0477377739, 0),
    (-0.0578622119, 0),
    (-0.108909373, 0),
    (-0.10791242, 0),
    (-0.0573840534, 0),
    (-0.0471532672, 0),
    (-0.054487508, 0),
    (-0.0948397542, 0),
    (-0.111948482, 0),
    (-0.0611021137, 0),
    (-0.0518063529, 0),
    (-0.0617649223, 0),
    (-0.095284726, 0),
    (-0.111193605, 0),
    (-0.0608498234, 0),
    (-0.0519481932, 0),
    (-0.0551057208, 0),
    (-0.10791242, 0),
    (-0.111005018, 0),
    (-0.0612790337, 0),
    (-0.0477377739, 0),
    (-0.0573840534, 0),
    (-0.111948482, 0),
    (-0.111811321, 0),
    (-0.0578622119, 0),
    (-0.0471532672, 0),
    (-0.0611021137, 0),
    (-0.111193605, 0),
]

_POINTS_PER_SCAN = len(_BASELINE)


class MockAD5933:
    """Drop-in stand-in for :class:`ad5933_driver.AD5933`."""

    def __init__(self, baseline=None, target=None):
        self._baseline = list(baseline or _BASELINE)
        self._target = list(target or _TARGET)
        self._index = 0
        self._scan_number = 0
        self._forced = None

    def measure(self, freq_hz):
        if self._forced == "baseline":
            table = self._baseline
        elif self._forced == "target":
            table = self._target
        else:
            table = self._baseline if self._scan_number == 0 else self._target

        value = table[self._index]
        self._index += 1
        if self._index >= _POINTS_PER_SCAN:
            self._index = 0
            self._scan_number += 1
        return value

    def set_mode(self, mode):
        """``baseline``/``target`` force a table; ``auto`` restarts the cycle."""
        mode = str(mode).lower()
        if mode not in ("baseline", "target", "auto"):
            raise ValueError("mock mode must be baseline, target or auto")
        self._forced = None if mode == "auto" else mode
        if mode in ("baseline", "auto"):
            self._index = 0
            self._scan_number = 0
        return self._forced or "auto"

    def halt(self):
        pass

    def temperature_c(self):
        return 30.0


class MockMux:
    """No-op mux bank: keeps the firmware's selection path intact."""

    def disable_all(self):
        pass

    def enable(self, role):
        pass

    def disable(self, role):
        pass

    def set_address(self, electrode):
        if not 0 <= electrode < 16:
            raise ValueError("mock electrode out of range")
