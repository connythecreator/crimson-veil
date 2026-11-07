#!/usr/bin/env python3
"""Render the mock-firmware -> pyEIT difference image and its figures.

The mock firmware is run through its real command loop, so this exercises the
same baseline/target path as the kiosk. Output uses the classic EIT
difference-map convention: lower impedance (higher conductivity) is red, the
baseline is white, and higher impedance (lower conductivity) is blue.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "firmware" / "mp-firm" / "src"
FIGURES = ROOT / "software" / "reconstruction" / "figures"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
FREQ_HZ = 50_000.0
ELECTRODES = 8


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SRC / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _firmware_frames():
    for name in ("protocol", "ad5933_driver", "mock_ad5933", "status_led"):
        sys.modules[name] = _load(name)
    firmware_module = _load("main")
    mock = sys.modules["mock_ad5933"]

    replies = []
    firmware_module.protocol.sink = lambda line: replies.append(json.loads(line))
    firmware = firmware_module.Firmware(mock.MockAD5933(), mux=mock.MockMux())
    firmware.handle({"type": "scan"})  # baseline
    firmware.handle({"type": "scan"})  # target 0
    return replies[0], replies[1]


def _reconstruct(baseline, target):
    from software.core.types import MeshConfig, RawPoint, ScanData
    from software.reconstruction.pyeit_solver import PyEITSolver

    def as_scan(frame):
        return ScanData(
            points=[RawPoint(point["f"], point["re"], point["im"]) for point in frame["points"]],
            n_electrodes=ELECTRODES,
            frequency_hz=FREQ_HZ,
        )

    state = np.random.get_state()
    try:
        np.random.seed(20261014)
        solver = PyEITSolver(grid_size=96)
        solver.setup(ELECTRODES, MeshConfig(n_electrodes=ELECTRODES))
    finally:
        np.random.set_state(state)
    try:
        return solver.reconstruct(as_scan(target), as_scan(baseline))
    finally:
        solver.close()


def _save_figure(cmap, destination):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    from software.reconstruction.image import (
        HEATMAP_BLUE,
        HEATMAP_NEUTRAL,
        HEATMAP_RED,
    )

    def unit(rgb):
        return tuple(channel / 255.0 for channel in rgb)

    heat = LinearSegmentedColormap.from_list(
        "crimson_veil_eit",
        [unit(HEATMAP_BLUE), unit(HEATMAP_NEUTRAL), unit(HEATMAP_RED)],
    )

    values = np.asarray(cmap.values, dtype=float)
    scale = float(np.max(np.abs(values)))
    xx, yy = np.meshgrid(
        np.linspace(-1.0, 1.0, values.shape[1]),
        np.linspace(1.0, -1.0, values.shape[0]),
    )
    shown = np.ma.masked_where(xx * xx + yy * yy > 1.0, values)

    fig, ax = plt.subplots(figsize=(6.1, 5.6), dpi=200)
    image = ax.imshow(
        shown,
        cmap=heat,
        vmin=-scale,
        vmax=scale,
        origin="upper",
        extent=[-1.0, 1.0, -1.0, 1.0],
        interpolation="nearest",
    )
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Mock firmware -> pyEIT difference image (8 electrodes)",
        fontsize=10,
    )
    ax.text(
        0.0,
        -1.08,
        "red = lower impedance (higher conductivity);  blue = higher impedance;  white = baseline",
        ha="center",
        va="top",
        fontsize=7,
    )
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.02)
    colorbar.set_label("Delta sigma (a.u.)", fontsize=8)
    colorbar.ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(destination)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/plot_mock_reconstruction.py")
    parser.add_argument("--output-dir", default=str(FIGURES), help="figure directory")
    args = parser.parse_args(argv)

    from PIL import Image

    from software.reconstruction.image import conductivity_to_png

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline, target = _firmware_frames()
    cmap = _reconstruct(baseline, target)

    png_path = output_dir / "mock-firmware-pyeit.png"
    png_path.write_bytes(conductivity_to_png(cmap))

    with Image.open(png_path) as raw:
        raw.resize((raw.width * 4, raw.height * 4), Image.Resampling.NEAREST).save(
            output_dir / "mock-firmware-pyeit-4x.png"
        )
    _save_figure(cmap, output_dir / "mock-firmware-pyeit-figure.png")

    print(f"wrote {png_path}")
    print(f"wrote {output_dir / 'mock-firmware-pyeit-4x.png'}")
    print(f"wrote {output_dir / 'mock-firmware-pyeit-figure.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
