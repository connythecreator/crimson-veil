"""ESP32 hardware backend.

The physical front end (AD5933 + mux bank) is driven by an ESP32, wired to the
host over USB serial. The ESP32 owns the *hardware configuration* and the
*scan process*: it runs its standard adjacent sequence itself, so this backend
neither builds a plan nor calibrates. It asks for a scan and receives one frame
of points already in the order the solver expects. Calibration is applied on
the ESP32.

Only single-shot scans cross the wire: the ESP32 measures its full sequence and
returns one frame. Continuous scanning is a host concern and lives in the
control service, never in the firmware.

Wire protocol (line-delimited JSON, one object per line, USB CDC at 115200):

    host -> esp   {"type": "identify"}
                  {"type": "scan"}                 # optional "f": <Hz>
                  {"type": "stop"}
    esp  -> host  {"type": "hello", "firmware": str, "n_electrodes": int,
                   "electrodes": [int, ...], "sweep_hz": float}
                  {"type": "frame", "points": [{"n": int, "f": Hz,
                                   "re": float, "im": float}, ...]}
                  {"type": "telemetry", "battery_pct": float|null,
                   "battery_charging": bool, "temp_c": float|null}
                  {"type": "error", "message": str}

`hello` is sent unsolicited on boot and again in reply to `identify`; the
backend learns `n_electrodes` and the scan frequency from it. `frame` carries
the firmware's adjacent-sequence points (``n * (n - 3)`` of them, tagged with
their index ``n``). `telemetry` is pushed periodically by the firmware.
"""

from __future__ import annotations

import json
import math
import threading
import time
from typing import Protocol, runtime_checkable

from software.core.types import DeviceConfig, RawPoint

DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT_S = 5.0
# The sim spends ~20 ms/point; give the ESP32 generous headroom per point.
PER_POINT_TIMEOUT_S = 0.5


@runtime_checkable
class LineTransport(Protocol):
    """A bi-directional line transport (real serial, or a test double)."""

    def write_line(self, text: str) -> None:
        """Send one line (a newline is appended by the transport)."""
        ...

    def read_line(self, timeout: float) -> str | None:
        """Return the next line, or None if `timeout` elapses first."""
        ...

    def close(self) -> None:
        ...


class SerialTransport:
    """`LineTransport` backed by pyserial."""

    def __init__(self, port: str, baud: int, timeout: float) -> None:
        import serial  # imported lazily so the suite does not need pyserial

        self._serial = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self._read_buffer = bytearray()

    def write_line(self, text: str) -> None:
        self._serial.write((text + "\n").encode("utf-8"))
        self._serial.flush()

    def read_line(self, timeout: float) -> str | None:
        # pyserial returns partial bytes when its timeout expires, especially
        # during a non-blocking telemetry poll. Retain those bytes until a
        # newline arrives instead of handing an incomplete JSON object onward.
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            newline = self._read_buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self._read_buffer[:newline])
                del self._read_buffer[:newline + 1]
                return raw.decode("utf-8", "replace").strip()
            self._serial.timeout = max(0.0, deadline - time.monotonic())
            raw = self._serial.readline()
            if not raw:
                return None
            self._read_buffer.extend(raw)
            if b"\n" not in self._read_buffer and time.monotonic() >= deadline:
                return None

    def close(self) -> None:
        self._serial.close()


class Esp32Error(RuntimeError):
    """Raised when the ESP32 reports an error or the link misbehaves."""


class Esp32Hardware:
    """`HardwareBackend` talking to the ESP32 over USB serial."""

    def __init__(self, transport: LineTransport | None = None) -> None:
        self._transport = transport
        self._port = ""
        self._baud = DEFAULT_BAUD
        self._timeout = DEFAULT_TIMEOUT_S
        self._open = False
        self._needs_resync = False
        # Learned from the ESP32's `hello`.
        self.n_electrodes = 0
        self.electrodes: list[int] = []
        self.firmware = ""
        self.frequency_hz = 0.0
        self._telemetry: dict = {}
        # A scan owns the transport until its reply arrives. Metrics are read
        # from another thread and must never consume that reply or change the
        # serial timeout while a scan is waiting.
        self._io_lock = threading.Lock()

    # --- HardwareBackend --------------------------------------------------

    def open(self, cfg: DeviceConfig) -> None:
        with self._io_lock:
            self._open_connection(cfg)

    def _open_connection(self, cfg: DeviceConfig) -> None:
        opts = cfg.options or {}
        self._port = str(opts.get("port", "/dev/ttyACM0"))
        self._baud = int(opts.get("baud", DEFAULT_BAUD))
        self._timeout = float(opts.get("timeout_s", DEFAULT_TIMEOUT_S))

        if self._transport is None:
            self._transport = SerialTransport(self._port, self._baud, self._timeout)

        # The ESP32 announces itself on boot; ask again in case we attached late.
        hello = self._await("hello", self._timeout, send={"type": "identify"})
        self._apply_hello(hello)
        # Fall back to the configured frequency if the firmware did not report one.
        if not self.frequency_hz:
            self.frequency_hz = float(cfg.frequency_hz)
        self._open = True
        self._needs_resync = False

    def identify(self) -> str:
        if self._open:
            return f"esp32:{self._port}"
        return f"esp32:{self._port}:not-open"

    def scan(self) -> list[RawPoint]:
        """Run one single-shot scan and return the firmware's frame."""
        with self._io_lock:
            if not self._open or self._transport is None:
                raise RuntimeError("Esp32Hardware.scan called before open()")
            try:
                if self._needs_resync:
                    self._resynchronize()
                return self._scan()
            except Esp32Error:
                # A delayed reply may still arrive after a timeout or malformed
                # line. Never let it become the next scan's (or baseline's) data.
                self._needs_resync = True
                raise

    def _resynchronize(self) -> None:
        # The firmware processes commands sequentially. Its identify response
        # therefore follows any outstanding scan reply, including a partial
        # line retained by SerialTransport. _await drains those older messages.
        hello = self._await("hello", self._timeout, send={"type": "identify"})
        if hello.get("n_electrodes") != self.n_electrodes:
            raise Esp32Error(
                "electrode count changed during serial recovery; reconnect "
                "and configure the solver again"
            )
        # The hello reports firmware defaults; the next scan must retain a
        # frequency selected by the host rather than reverting to that default.
        requested_frequency = self.frequency_hz
        self._apply_hello(hello)
        self.frequency_hz = requested_frequency
        self._needs_resync = False

    def _scan(self) -> list[RawPoint]:
        command = {"type": "scan"}
        # Echo the (possibly host-overridden) frequency so the firmware scans
        # where the host expects; it falls back to its own SWEEP_HZ if omitted.
        if self.frequency_hz:
            command["f"] = self.frequency_hz
        self._transport.write_line(json.dumps(command))

        # Read until a frame arrives, absorbing any telemetry in between.
        # One point per measurement; the firmware owns the sequence length.
        expected = self.n_electrodes * (self.n_electrodes - 3) or 1
        deadline = time.monotonic() + self._timeout + PER_POINT_TIMEOUT_S * expected
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Esp32Error("timed out waiting for frame")
            msg = self._read(timeout=remaining)
            kind = msg.get("type")
            if kind == "frame":
                return self._parse_frame(msg)
            if kind == "telemetry":
                self._telemetry = msg
                continue
            if kind == "error":
                raise Esp32Error(str(msg.get("message", "unknown ESP32 error")))
            # Ignore anything else (e.g. a stray hello).

    def close(self) -> None:
        with self._io_lock:
            if self._transport is not None:
                try:
                    self._transport.write_line(json.dumps({"type": "stop"}))
                except Exception:  # noqa: BLE001 - best effort on shutdown
                    pass
                self._transport.close()
            self._open = False

    # --- extras -----------------------------------------------------------

    def telemetry(self) -> dict:
        """Return the most recent telemetry pushed by the ESP32.

        Reads any lines already buffered (non-blocking) so periodic telemetry
        frames update the cache without delaying a scan. Fields are
        ``battery_pct`` (float|None), ``battery_charging`` (bool) and
        ``temp_c`` (float|None).
        """
        if not self._io_lock.acquire(blocking=False):
            return dict(self._telemetry)
        try:
            while self._open and self._transport is not None:
                try:
                    msg = self._read(timeout=0.0)
                except Esp32Error:
                    break
                if msg.get("type") == "telemetry":
                    self._telemetry = msg
            return dict(self._telemetry)
        finally:
            self._io_lock.release()

    # --- internals --------------------------------------------------------

    def _apply_hello(self, hello: dict) -> None:
        self.firmware = str(hello.get("firmware", ""))
        self.n_electrodes = int(hello.get("n_electrodes", 0))
        self.electrodes = [int(e) for e in hello.get("electrodes", [])]
        self.frequency_hz = float(hello.get("sweep_hz", 0.0) or 0.0)

    def _await(self, kind: str, timeout: float, send: dict | None = None) -> dict:
        if send is not None and self._transport is not None:
            self._transport.write_line(json.dumps(send))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Esp32Error(f"timed out waiting for '{kind}' from ESP32")
            msg = self._read(timeout=remaining)
            if msg.get("type") == kind:
                return msg
            if msg.get("type") == "telemetry":
                self._telemetry = msg
            elif msg.get("type") == "error":
                raise Esp32Error(str(msg.get("message", "unknown ESP32 error")))

    def _read(self, timeout: float) -> dict:
        if self._transport is None:
            raise Esp32Error("no transport")
        line = self._transport.read_line(timeout)
        if line is None:
            raise Esp32Error("serial read timed out")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Esp32Error(f"bad line from ESP32: {line!r}") from exc
        if not isinstance(msg, dict) or "type" not in msg:
            raise Esp32Error(f"expected a JSON object with a 'type': {line!r}")
        return msg

    def _parse_frame(self, msg: dict) -> list[RawPoint]:
        points = msg.get("points")
        if not isinstance(points, list):
            raise Esp32Error("frame is missing a 'points' list")
        expected = self.n_electrodes * (self.n_electrodes - 3)
        if self.n_electrodes < 4 or len(points) != expected:
            raise Esp32Error(
                f"frame contains {len(points)} points; expected {expected} "
                f"for {self.n_electrodes} electrodes"
            )
        if any(not isinstance(point, dict) for point in points):
            raise Esp32Error("every frame point must be a JSON object")

        indexed = ["n" in point for point in points]
        has_indices = all(indexed)
        if any(indexed) and not has_indices:
            raise Esp32Error("frame mixes indexed and unindexed points")
        # Older firmware may omit every index; those frames retain wire order.
        # Indexed frames must cover each position exactly once.
        out: dict[int, RawPoint] = {}
        for position, point in enumerate(points):
            index = point["n"] if has_indices else position
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < expected:
                raise Esp32Error(f"frame point has invalid index {index!r}")
            if index in out:
                raise Esp32Error(f"frame has duplicate point index {index}")
            try:
                frequency = float(point.get("f", self.frequency_hz))
                real = float(point["re"])
                imag = float(point["im"])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise Esp32Error(f"frame point {index} has invalid numeric data") from exc
            if not all(math.isfinite(value) for value in (frequency, real, imag)):
                raise Esp32Error(f"frame point {index} contains non-finite data")
            if frequency <= 0:
                raise Esp32Error(f"frame point {index} frequency must be positive")
            out[index] = RawPoint(freq_hz=frequency, real=real, imag=imag)
        return [out[index] for index in range(expected)]
