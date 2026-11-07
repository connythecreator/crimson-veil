"""Image encoding for reconstruction output.

Dependency-free PNG encoding plus colour mapping of a
:class:`~software.core.types.ConductivityMap`. Difference maps use the classic
EIT blue/white/red ramp; absolute maps keep the existing grayscale ramp. Kept
separate from the solver so any solver backend can reuse it.
"""

from __future__ import annotations

import struct
import zlib

from ..core.types import ConductivityMap

# Classic EIT difference-map palette: blue for decreasing conductivity
# (higher impedance), white for the baseline, red for increasing conductivity
# (lower impedance). The symmetric scale is the frame's largest absolute
# change.
HEATMAP_BLUE = (0, 0, 255)
HEATMAP_NEUTRAL = (255, 255, 255)
HEATMAP_RED = (255, 0, 0)


def encode_png(
    pixels: list[bytearray],
    width: int,
    height: int,
    *,
    color_type: int = 0,
) -> bytes:
    """Encode an 8-bit PNG using only the stdlib.

    ``color_type`` is 0 for grayscale (one byte per pixel) or 2 for RGB (three
    bytes per pixel). ``pixels`` is row-major, one row per scanline.
    """
    if color_type not in (0, 2):
        raise ValueError("color_type must be 0 (gray) or 2 (RGB)")
    channels = 1 if color_type == 0 else 3
    expected = width * channels
    for row in pixels:
        if len(row) != expected:
            raise ValueError(f"row has {len(row)} bytes; expected {expected} for width {width}")

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter type 0 (None) for this scanline
        raw.extend(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        crc = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + body + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _clamp_gray(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _lerp(start: tuple[int, int, int], end: tuple[int, int, int], t: float):
    return tuple(_clamp_gray(start[index] + (end[index] - start[index]) * t) for index in range(3))


def normalize(
    values: list[list[float]],
    *,
    centered: bool = False,
) -> list[bytearray]:
    """Map conductivity values to 0-255 grayscale rows.

    Absolute maps use their own min/max; a flat frame maps to mid-gray. The
    ``centered`` branch is a grayscale preview only; difference maps sent to
    the kiosk use :func:`colorize` instead.
    """
    flat = [v for row in values for v in row]
    if not flat:
        return []

    if centered:
        scale = max(abs(v) for v in flat)
        if scale <= 0:
            return [bytearray([128] * len(row)) for row in values]
        out: list[bytearray] = []
        for row in values:
            out.append(bytearray(_clamp_gray(127.5 + 127.5 * v / scale) for v in row))
        return out

    lo, hi = min(flat), max(flat)
    span = hi - lo
    if span <= 0:
        return [bytearray([128] * len(row)) for row in values]
    out = []
    for row in values:
        out.append(bytearray(int((v - lo) / span * 255) for v in row))
    return out


def colorize(values: list[list[float]]) -> list[bytearray]:
    """Map a zero-centred difference map to RGB heatmap rows.

    Classic EIT convention: negative values (decreasing conductivity, higher
    impedance) ramp from white to blue; positive values (increasing
    conductivity, lower impedance) ramp from white to red. The scale is the
    largest absolute value in the frame.
    """
    flat = [v for row in values for v in row]
    if not flat:
        return []

    scale = max(abs(v) for v in flat)
    out: list[bytearray] = []
    for row in values:
        data = bytearray()
        for value in row:
            if scale <= 0:
                data.extend(HEATMAP_NEUTRAL)
                continue
            t = max(-1.0, min(1.0, value / scale))
            if t < 0.0:
                data.extend(_lerp(HEATMAP_NEUTRAL, HEATMAP_BLUE, -t))
            else:
                data.extend(_lerp(HEATMAP_NEUTRAL, HEATMAP_RED, t))
        out.append(data)
    return out


def conductivity_to_png(cmap: ConductivityMap) -> bytes:
    """Render a conductivity map to PNG bytes.

    Difference maps are RGB heatmaps; absolute maps remain grayscale.
    """
    if not cmap.values or not cmap.values[0]:
        return encode_png([bytearray()], 0, 0)
    if cmap.centered:
        rows = colorize(cmap.values)
        return encode_png(
            rows,
            cmap.width,
            cmap.height,
            color_type=2,
        )
    rows = normalize(cmap.values)
    return encode_png(rows, cmap.width, cmap.height)
