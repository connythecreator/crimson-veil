"""ESP32 hardware backend.

The physical front end (AD5933 + mux bank) is driven by an ESP32, wired to the
host over USB serial. The ESP32 owns the *hardware configuration*: on connect
it announces how many electrodes there are and which drive/sense pairs it can
form, so this backend never hardcodes pin maps. The host owns the *scan plan*
(:func:`software.acquisition.sequence.adjacent_drive_plan`) and sends it down
for the ESP32 to execute one measurement at a time.

Only single-shot scans cross the wire: the ESP32 measures exactly the plan it
is given and returns one frame. Continuous scanning is a host concern and lives
in the control service, never in the firmware.

Wire protocol (line-delimited JSON, one object per line, USB CDC at 115200):

    host -> esp   {"type": "identify"}
                  {"type": "scan", "plan": [{"f": <Hz>, "d": [a,b], "s": [c,d]}, ...]}
                  {"type": "stop"}
    esp  -> host  {"type": "hello", "firmware": str, "n_electrodes": int,
                   "electrodes": [int, ...], "sweep_hz": float}
                  {"type": "frame", "points": [{"f": Hz, "re": float, "im": float}, ...]}
                  {"type": "telemetry", "battery_pct": float|null,
                   "battery_charging": bool, "temp_c": float|null}
                  {"type": "error", "message": str}

`hello` is sent unsolicited on boot and again in reply to `identify`. `frame`
carries one point per plan entry, in order. `telemetry` is pushed periodically
by the firmware.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from software.core.types import DeviceConfig, Measurement, RawPoint

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

    def write_line(self, text: str) -> None:
        self._serial.write((text + "\n").encode("utf-8"))
        self._serial.flush()

    def read_line(self, timeout: float) -> str | None:
        self._serial.timeout = timeout
        raw = self._serial.readline()
        if not raw:
            return None
        return raw.decode("utf-8", "replace").strip()

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
        # Learned from the ESP32's `hello`.
        self.n_electrodes = 0
        self.electrodes: list[int] = []
        self.firmware = ""
        self._telemetry: dict = {}

    # --- HardwareBackend --------------------------------------------------

    def open(self, cfg: DeviceConfig) -> None:
        opts = cfg.options or {}
        self._port = str(opts.get("port", "/dev/ttyACM0"))
        self._baud = int(opts.get("baud", DEFAULT_BAUD))
        self._timeout = float(opts.get("timeout_s", DEFAULT_TIMEOUT_S))

        if self._transport is None:
            self._transport = SerialTransport(self._port, self._baud, self._timeout)

        # The ESP32 announces itself on boot; ask again in case we attached late.
        hello = self._await("hello", self._timeout, send={"type": "identify"})
        self._apply_hello(hello)
        self._open = True

    def identify(self) -> str:
        if self._open:
            return f"esp32:{self._port}"
        return f"esp32:{self._port}:not-open"

    def measure(self, plan: Sequence[Measurement]) -> list[RawPoint]:
        if not self._open or self._transport is None:
            raise RuntimeError("Esp32Hardware.measure called before open()")
        if not plan:
            return []

        payload = {
            "type": "scan",
            "plan": [
                {"f": m.freq_hz, "d": list(m.drive), "s": list(m.sense)} for m in plan
            ],
        }
        self._transport.write_line(json.dumps(payload))

        # Read until a frame arrives, absorbing any telemetry in between.
        deadline = time.monotonic() + self._timeout + PER_POINT_TIMEOUT_S * len(plan)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Esp32Error(f"timed out waiting for frame ({len(plan)} points)")
            msg = self._read(timeout=remaining)
            kind = msg.get("type")
            if kind == "frame":
                return self._parse_frame(msg, len(plan))
            if kind == "telemetry":
                self._telemetry = msg
                continue
            if kind == "error":
                raise Esp32Error(str(msg.get("message", "unknown ESP32 error")))
            # Ignore anything else (e.g. a stray hello).

    def close(self) -> None:
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
        while self._transport is not None:
            try:
                msg = self._read(timeout=0.0)
            except Esp32Error:
                break
            if msg.get("type") == "telemetry":
                self._telemetry = msg
        return dict(self._telemetry)

    # --- internals --------------------------------------------------------

    def _apply_hello(self, hello: dict) -> None:
        self.firmware = str(hello.get("firmware", ""))
        self.n_electrodes = int(hello.get("n_electrodes", 0))
        self.electrodes = [int(e) for e in hello.get("electrodes", [])]

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

    @staticmethod
    def _parse_frame(msg: dict, expected: int) -> list[RawPoint]:
        points = msg.get("points")
        if not isinstance(points, list):
            raise Esp32Error("frame is missing a 'points' list")
        if len(points) != expected:
            raise Esp32Error(
                f"frame has {len(points)} points, expected {expected}"
            )
        out: list[RawPoint] = []
        for p in points:
            out.append(
                RawPoint(
                    freq_hz=float(p["f"]),
                    real=float(p["re"]),
                    imag=float(p["im"]),
                )
            )
        return out
