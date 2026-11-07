"""Mock front end for host/pipeline bring-up without an AD5933 or mux bank.

`MockAD5933` returns pre-computed FEM boundary voltages for circular electrode
arrays at 50 kHz, in the firmware's adjacent drive/sense order (`N * (N - 3)`
points). Tables exist for 4, 8 and 16 electrodes in separate modules so the
ESP32 only imports the set for the configured `N_ELECTRODES`.

  baseline = homogeneous unit-conductivity mesh
  targets  = eight anomalies (`PyEITAnomaly_Circle`, r 0.18, perm 2.0) around
             the unit disk; see `mock_tables_N.py`

The first full scan serves the baseline (so the host can capture it as the
pyEIT reference). In the default ``continuous``/``auto`` mode each following
scan cycles to the next anomaly position, so monitor mode shows a moving
anomaly. ``set_mode("baseline")`` / ``set_mode("target")`` force a table.

The tables are impedance-like boundary voltages, i.e. the post-calibration
quantity the solver expects. They are *not* raw AD5933 DFT counts, so the
firmware must not apply its ``Z = K / S`` calibration to them. ``is_mock``
marks this driver so the scan loop bypasses calibration.

`MockMux` is a no-op implementation of the mux interface so `select_measurement`
and the firmware self-test run unchanged. It records the independent address for
each role, matching the real always-enabled, non-latching mux bank.

This is a host/solver validation tool, not a physical acquisition model.
"""


def _tables(n_electrodes):
    n = int(n_electrodes)
    if n == 4:
        import mock_tables_4 as tables
    elif n == 8:
        import mock_tables_8 as tables
    elif n == 16:
        import mock_tables_16 as tables
    else:
        raise ValueError("mock supports 4, 8 or 16 electrodes")
    return tables


class MockAD5933:
    """Drop-in stand-in for :class:`ad5933_driver.AD5933`.

    Returns post-calibration, impedance-like values; calibration is bypassed.
    """

    is_mock = True

    def __init__(self, n_electrodes=8, baseline=None, targets=None):
        n = int(n_electrodes)
        self.n_electrodes = n
        self._points_per_scan = n * (n - 3)
        if baseline is None or targets is None:
            tables = _tables(n)
            if baseline is None:
                baseline = tables.BASELINE
            if targets is None:
                targets = tables.TARGETS
        self._baseline = baseline
        self._targets = targets
        self._index = 0
        self._scan_number = 0
        self._forced = None

    def _target_table(self):
        index = (max(self._scan_number, 1) - 1) % len(self._targets)
        return self._targets[index]

    def measure(self, freq_hz):
        if self._forced == "baseline":
            table = self._baseline
        elif self._forced == "target":
            table = self._targets[0]
        elif self._scan_number == 0:
            table = self._baseline
        else:
            table = self._target_table()

        offset = 2 * self._index
        value = (table[offset], table[offset + 1])
        self._index += 1
        if self._index >= self._points_per_scan:
            self._index = 0
            self._scan_number += 1
        return value

    def set_mode(self, mode):
        """baseline | target | continuous/auto (cycle the anomaly positions)."""
        mode = str(mode).lower()
        if mode == "baseline":
            self._forced = "baseline"
            self._index = 0
            self._scan_number = 0
        elif mode == "target":
            self._forced = "target"
            self._index = 0
            self._scan_number = 1
        elif mode in ("continuous", "auto"):
            self._forced = None
            self._index = 0
            self._scan_number = 0
        else:
            raise ValueError(
                "mock mode must be baseline, target, continuous or auto"
            )
        return self._forced or "continuous"

    def halt(self):
        pass

    def temperature_c(self):
        return 30.0


class MockMux:
    """Recording no-op mux bank with one independent address per role."""

    ROLES = ("drive_pos", "drive_neg", "sense_pos", "sense_neg")
    is_mock = True

    def __init__(self):
        self.addresses = {role: 0 for role in self.ROLES}

    def set_address(self, role, electrode):
        if role not in self.addresses:
            raise ValueError(f"unknown mux role: {role!r}")
        if not 0 <= electrode < 16:
            raise ValueError("mock electrode out of range")
        self.addresses[role] = electrode

    def park_all(self):
        for role in self.addresses:
            self.addresses[role] = 0
