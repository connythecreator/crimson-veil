"""Image encoding for reconstruction output.

Dependency-free PNG encoding plus normalisation of a
:class:`~software.core.types.ConductivityMap` into gray pixels. Kept separate
from the solver so any solver backend can reuse it.
"""

from __future__ import annotations

import struct
import zlib

from ..core.types import ConductivityMap


def encode_png(pixels: list[bytearray], width: int, height: int) -> bytes:
    """Encode an 8-bit grayscale image to PNG bytes using only the stdlib.

    ``pixels`` is a row-major sequence of rows, each row a sequence of 0-255
    gray values.
    """
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter type 0 (None) for this scanline
        raw.extend(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        crc = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + body + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)  # 8-bit grayscale
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def normalize(values: list[list[float]]) -> list[bytearray]:
    """Map arbitrary conductivity values to 0-255 gray rows.

    Values are linearly normalised across the frame's own min/max; a flat frame
    maps to mid-gray.
    """
    flat = [v for row in values for v in row]
    if not flat:
        return []
    lo, hi = min(flat), max(flat)
    span = hi - lo
    if span <= 0:
        return [bytearray([128] * len(row)) for row in values]
    out: list[bytearray] = []
    for row in values:
        out.append(bytearray(int((v - lo) / span * 255) for v in row))
    return out


def conductivity_to_png(cmap: ConductivityMap) -> bytes:
    """Render a conductivity map to PNG bytes."""
    rows = normalize(cmap.values)
    if not rows:
        return encode_png([bytearray()], 0, 0)
    return encode_png(rows, len(rows[0]), len(rows))
