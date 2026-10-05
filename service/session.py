"""Scan session: boot the backends once and run scans single-flight.

This is the transport-free core of the control surface. It owns the hardware
and solver backends opened at boot and serialises scans so that a second
request while one is running yields a ``busy`` error instead of interleaving
hardware access.

Kept separate from :mod:`service.server` so it can be unit-tested without a
socket, and so a future companion/web front end can reuse it unchanged.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from software import pipeline
from software.core import config

ProgressFn = Callable[[str, str], None]


class BusyError(RuntimeError):
    """Raised when a scan is requested while another is running."""


class ScanSession:
    """Owns the boot-opened backends and runs one scan at a time."""

    def __init__(self) -> None:
        self._hardware = None
        self._solver = None
        self._boot_error: str | None = None
        self._booted = False
        # Reentrant: an outer guard serialises scans; the inner lock only
        # protects the small state swaps.
        self._scan_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._frequencies_hz: list[float] = list(config.DEFAULT_FREQUENCIES_HZ)

    # --- boot -------------------------------------------------------------

    def boot(self) -> str:
        """Open the configured backends. Returns the hardware identity.

        Records the error and re-raises if boot fails, so the caller can send a
        ``boot_error`` yet keep the process alive for retries.
        """
        with self._state_lock:
            if self._booted:
                return self.identify()
            try:
                hardware = pipeline.default_hardware()
                hardware.open(config.device_config())
                solver = pipeline.default_solver()
                solver.setup(config.N_ELECTRODES, config.mesh_config())
            except Exception as exc:  # noqa: BLE001 - surface anything to the client
                self._boot_error = f"{type(exc).__name__}: {exc}"
                raise
            self._hardware = hardware
            self._solver = solver
            self._booted = True
            self._boot_error = None
            return hardware.identify()

    @property
    def booted(self) -> bool:
        return self._booted

    @property
    def boot_error(self) -> str | None:
        return self._boot_error

    def ready_payload(self) -> dict:
        return {
            "backend": self.identify(),
            "solver": config.SOLVER_BACKEND,
            "n_electrodes": self.n_electrodes,
            "frequencies_hz": list(self._frequencies_hz),
        }

    def identify(self) -> str:
        with self._state_lock:
            if self._hardware is not None:
                return self._hardware.identify()
            return f"{config.HARDWARE_BACKEND}:not-open"

    @property
    def hardware(self):
        """The boot-opened hardware backend, or None. Used for telemetry."""
        with self._state_lock:
            return self._hardware

    @property
    def n_electrodes(self) -> int:
        """Electrode count, preferring the value the ESP32 reported."""
        with self._state_lock:
            hw = self._hardware
            if hw is not None and getattr(hw, "n_electrodes", 0):
                return int(hw.n_electrodes)
            return config.N_ELECTRODES

    # --- configuration ----------------------------------------------------

    def set_frequencies(self, frequencies_hz: list[float]) -> None:
        if not frequencies_hz:
            raise ValueError("frequencies_hz must not be empty")
        with self._state_lock:
            self._frequencies_hz = [float(f) for f in frequencies_hz]

    @property
    def frequencies_hz(self) -> list[float]:
        with self._state_lock:
            return list(self._frequencies_hz)

    # --- scanning ---------------------------------------------------------

    def run_scan(self, on_progress: ProgressFn | None = None) -> bytes:
        """Run a full scan and return PNG bytes.

        Serialised: raises :class:`BusyError` if another scan holds the lock.
        If boot never succeeded, falls back to a self-contained sim scan (the
        configured defaults), matching the old kiosk's degrade-to-sim behaviour.
        """
        if not self._scan_lock.acquire(blocking=False):
            raise BusyError("a scan is already running")
        try:
            if on_progress:
                on_progress("Scanning...")

            with self._state_lock:
                hardware = self._hardware
                solver = self._solver
                freqs = list(self._frequencies_hz)

            if hardware is None or solver is None:
                return pipeline.run_scan(frequencies_hz=freqs)

            return pipeline.run_scan(
                hardware=hardware,
                solver=solver,
                frequencies_hz=freqs,
            )
        finally:
            self._scan_lock.release()

    def close(self) -> None:
        with self._state_lock:
            if self._solver is not None:
                try:
                    self._solver.close()
                except Exception:  # noqa: BLE001 - best effort on shutdown
                    pass
            if self._hardware is not None:
                try:
                    self._hardware.close()
                except Exception:  # noqa: BLE001 - best effort on shutdown
                    pass
            self._hardware = None
            self._solver = None
            self._booted = False
