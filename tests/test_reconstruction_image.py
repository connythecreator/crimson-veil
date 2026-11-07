"""Rendering convention for reconstructed conductivity maps."""

from __future__ import annotations

from software.core.types import ConductivityMap
from software.reconstruction.image import (
    HEATMAP_BLUE,
    HEATMAP_NEUTRAL,
    HEATMAP_RED,
    colorize,
    conductivity_to_png,
    normalize,
)


def _pixel(row: bytearray, index: int) -> tuple[int, int, int]:
    return tuple(row[index * 3 : index * 3 + 3])


def test_centered_map_red_is_low_impedance_blue_is_high_impedance():
    values = [[0.0, 0.5, -0.5], [1.0, -1.0, 0.0]]

    rows = colorize(values)

    assert _pixel(rows[0], 0) == HEATMAP_NEUTRAL
    red, green, blue = _pixel(rows[0], 1)
    assert red > blue and red > green
    red, green, blue = _pixel(rows[0], 2)
    assert blue > red and blue > green
    assert _pixel(rows[1], 0) == HEATMAP_RED
    assert _pixel(rows[1], 1) == HEATMAP_BLUE
    assert _pixel(rows[1], 2) == HEATMAP_NEUTRAL


def test_centered_flat_map_is_the_white_baseline():
    rows = colorize([[0.0, 0.0], [0.0, 0.0]])
    for row in rows:
        assert _pixel(row, 0) == HEATMAP_NEUTRAL
        assert _pixel(row, 1) == HEATMAP_NEUTRAL


def test_absolute_map_still_uses_its_own_range():
    rows = normalize([[10.0, 20.0], [30.0, 40.0]])
    assert rows[0][0] == 0
    assert rows[1][1] == 255


def test_png_uses_rgb_for_centered_maps_and_gray_for_absolute():
    centered = ConductivityMap(values=[[0.0, 1.0], [-1.0, 0.0]], centered=True)
    absolute = ConductivityMap(values=[[0.0, 1.0], [-1.0, 0.0]], centered=False)

    centered_png = conductivity_to_png(centered)
    absolute_png = conductivity_to_png(absolute)

    assert centered_png[25] == 2  # PNG IHDR color type: RGB
    assert absolute_png[25] == 0  # PNG IHDR color type: grayscale
    assert centered_png != absolute_png
    assert centered_png.startswith(b"\x89PNG\r\n\x1a\n")
